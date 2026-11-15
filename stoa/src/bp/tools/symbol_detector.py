"""Find countable things on a raster floor plan: doors, windows, fixtures, rooms and floor outlines.

A trained detector (exported to TorchScript, so inference needs only torch) looks at the plan through views:

- one global view: the whole plan, scaled to fit the model input (at most 2x up), padded with white;
- tiles at native scale when the plan is much larger than the input, so a 17 px shower stays 17 px.

Small classes (symbols) come from the tiles when there are tiles, else from the global view. Large classes
(rooms, floor outlines) always come from the global view. A tile owns a detection only when the box centre lies
in the tile's core (the tile minus half of the overlap on each inner side), so an object cut by a seam is
counted once. The same view code builds the training images (jobs/cubicasa-detect/prepare.py), so training and
inference see the same pixels.

The model files live in `artifacts/cubicasa-detect/<name>/`: `model.ts` (TorchScript) and `meta.json`
(backend, resolution, class names, per-class thresholds).
"""

from __future__ import annotations

import itertools
import json
import math
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np
from PIL import Image, ImageOps

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

CLASSES: tuple[str, ...] = (
    "door",
    "doorway",  # an open doorway without a leaf (CubiCasa `Door None`); never counted as a door
    "window",
    "toilet",
    "sink",
    "shower",
    "bathtub",
    "shower_cab",  # a shower cabin; not a shower by the reference rule
    "sauna",
    "floorplan",
    "kitchen",
    "bedroom",
    "bathroom",
    "wc_room",
    "balcony",
)
SMALL: frozenset[str] = frozenset({"door", "doorway", "window", "toilet", "sink", "shower", "bathtub", "shower_cab"})
LARGE: frozenset[str] = frozenset(CLASSES) - SMALL
# A countable concept (what a question asks) -> the classes whose marks it counts.
CONCEPTS: dict[str, tuple[str, ...]] = {
    "floors": ("floorplan",),
    "windows": ("window",),
    "toilets": ("toilet",),
    "sinks": ("sink",),
    "showers_tubs": ("shower", "bathtub"),
    "showers": ("shower",),
    "bathtubs": ("bathtub",),
    "doors": ("door",),
    "saunas": ("sauna",),
    "kitchens": ("kitchen",),
    "bedrooms": ("bedroom",),
    "bathrooms": ("bathroom",),
    "wc_rooms": ("wc_room",),
    "balconies": ("balcony",),
}

RESOLUTION = 1024
TILE_STEP_FRACTION = 0.75  # step 768 px for a 1024 px tile: 256 px overlap
MAX_UPSCALE = 2.0
TILE_WHEN_SCALE_BELOW = 0.8  # tile when the global view shrinks the plan below 80 %
MAX_TILED_SIDE = 4096  # sheets above this are shrunk before tiling
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


@dataclass(frozen=True)
class View:
    """A square window of the plan. Original pixel (x, y) maps to view pixel ((x - x0) * scale, (y - y0) * scale)."""

    kind: str  # "global" or "tile"
    x0: float
    y0: float
    scale: float
    size: int
    # The core of a tile, in original pixels: a detection whose centre lies here belongs to this tile.
    core: tuple[float, float, float, float] = (-math.inf, -math.inf, math.inf, math.inf)

    def to_original(self, box: Sequence[float]) -> tuple[float, float, float, float]:
        x0, y0, x1, y1 = box
        return (
            x0 / self.scale + self.x0,
            y0 / self.scale + self.y0,
            x1 / self.scale + self.x0,
            y1 / self.scale + self.y0,
        )

    def to_view(self, box: Sequence[float]) -> tuple[float, float, float, float]:
        x0, y0, x1, y1 = box
        s = self.scale
        return ((x0 - self.x0) * s, (y0 - self.y0) * s, (x1 - self.x0) * s, (y1 - self.y0) * s)

    def owns(self, box: Sequence[float]) -> bool:
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        a, b, c, d = self.core
        return a <= cx < c and b <= cy < d


@dataclass(frozen=True)
class Detection:
    label: str
    score: float
    box: tuple[float, float, float, float]  # x0, y0, x1, y1 in original pixels

    @property
    def centre(self) -> tuple[float, float]:
        return ((self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2)


def _starts(length: float, window: float, step: float) -> list[float]:
    if length <= window:
        return [0.0]
    count = math.ceil((length - window) / step) + 1
    gap = (length - window) / (count - 1)
    return [i * gap for i in range(count)]


def _cores(starts: list[float], window: float, length: float) -> list[tuple[float, float]]:
    """Split [0, length) among the windows: each boundary is the middle of the overlap of two neighbours."""
    cuts = [-math.inf]
    for left, right in itertools.pairwise(starts):
        cuts.append((left + window + right) / 2)
    cuts.append(math.inf)
    del length
    return [(cuts[i], cuts[i + 1]) for i in range(len(starts))]


def plan_views(width: int, height: int, resolution: int = RESOLUTION) -> list[View]:
    """The global view, then the tiles (none for a plan that fits the input)."""
    long_side = max(width, height)
    global_scale = min(resolution / long_side, MAX_UPSCALE)
    views = [View("global", 0.0, 0.0, global_scale, resolution)]
    if global_scale >= TILE_WHEN_SCALE_BELOW:
        return views
    scale = min(1.0, MAX_TILED_SIDE / long_side)
    window = resolution / scale  # the tile side in original pixels
    step = window * TILE_STEP_FRACTION
    xs, ys = _starts(width, window, step), _starts(height, window, step)
    for y, (cy0, cy1) in zip(ys, _cores(ys, window, height), strict=True):
        for x, (cx0, cx1) in zip(xs, _cores(xs, window, width), strict=True):
            views.append(View("tile", x, y, scale, resolution, core=(cx0, cy0, cx1, cy1)))
    return views


def load_rgb(path: str | Path) -> Image.Image:
    """Open an image and flatten any transparency onto white."""
    with Image.open(path) as raw:
        image = raw.copy()
    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        flat = Image.new("RGB", rgba.size, "white")
        flat.paste(rgba, mask=rgba.getchannel("A"))
        return flat
    return image.convert("RGB")


def render_view(image: Image.Image, view: View) -> Image.Image:
    """The view as a square RGB image, white where the plan does not reach."""
    size = view.size
    window = size / view.scale
    box = (view.x0, view.y0, min(view.x0 + window, image.width), min(view.y0 + window, image.height))
    crop = image.crop((round(box[0]), round(box[1]), round(box[2]), round(box[3])))
    out_w = max(1, round(crop.width * view.scale))
    out_h = max(1, round(crop.height * view.scale))
    resample = Image.Resampling.LANCZOS if view.scale < 1 else Image.Resampling.BICUBIC
    resized = crop.resize((min(out_w, size), min(out_h, size)), resample) if view.scale != 1 else crop
    canvas = Image.new("RGB", (size, size), "white")
    canvas.paste(resized, (0, 0))
    return canvas


def box_overlap(a: Sequence[float], b: Sequence[float]) -> float:
    """Intersection over the smaller box."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return (w * h) / smaller if smaller > 0 else 0.0


def dedupe(detections: list[Detection], overlap: float = 0.7) -> list[Detection]:
    """Per class, drop a box that lies mostly inside a higher-scoring box of the same class."""
    kept: list[Detection] = []
    for det in sorted(detections, key=lambda d: -d.score):
        if all(k.label != det.label or box_overlap(k.box, det.box) < overlap for k in kept):
            kept.append(det)
    return kept


def merge_views(per_view: list[tuple[View, list[Detection]]]) -> list[Detection]:
    """Combine view detections (boxes already in original pixels) by the global-or-tile rule above."""
    tiled = any(view.kind == "tile" for view, _ in per_view)
    out: list[Detection] = []
    for view, dets in per_view:
        for det in dets:
            if det.label in LARGE:
                if view.kind == "global":
                    out.append(det)
            elif view.kind == "tile":
                if view.owns(det.box):
                    out.append(det)
            elif not tiled:
                out.append(det)
    return dedupe(out)


def to_tensor(image: Image.Image) -> Any:  # noqa: ANN401 - torch is imported lazily
    import torch  # noqa: PLC0415 - heavy import only when a model runs

    array = np.asarray(image, dtype=np.float32) / 255.0
    array = (array - np.array(IMAGENET_MEAN, dtype=np.float32)) / np.array(IMAGENET_STD, dtype=np.float32)
    return torch.from_numpy(array.transpose(2, 0, 1).copy()).unsqueeze(0)


def decode_rfdetr(
    outputs: Any,  # noqa: ANN401 - torch tensors
    view: View,
    classes: Sequence[str],
    floor: float,
    top_k: int = 300,
) -> list[Detection]:
    """RF-DETR export output: (boxes [1, Q, 4] cx cy w h in 0..1, logits [1, Q, C]). Top-k over query x class."""
    import torch  # noqa: PLC0415

    boxes, logits = outputs[0], outputs[1]
    if boxes.shape[-1] != 4:  # some versions return (logits, boxes)
        boxes, logits = logits, boxes
    prob = logits[0].float().sigmoid()
    num_classes = prob.shape[1]
    flat = prob.flatten()
    k = min(top_k, flat.numel())
    scores, index = torch.topk(flat, k)
    queries = torch.div(index, num_classes, rounding_mode="floor")
    labels = index % num_classes
    cxcywh = boxes[0].float()[queries]
    size = view.size
    out: list[Detection] = []
    for score, label, (cx, cy, w, h) in zip(scores.tolist(), labels.tolist(), cxcywh.tolist(), strict=True):
        if score < floor or label >= len(classes) or not classes[label]:
            continue
        box = ((cx - w / 2) * size, (cy - h / 2) * size, (cx + w / 2) * size, (cy + h / 2) * size)
        out.append(Detection(classes[label], float(score), view.to_original(box)))
    return out


def decode_yolo(
    outputs: Any,  # noqa: ANN401 - torch tensors
    view: View,
    classes: Sequence[str],
    floor: float,
) -> list[Detection]:
    """Ultralytics TorchScript export, in input pixels.

    Two layouts: rows [1, N, 6] of x0 y0 x1 y1 score class (an end-to-end export), or the raw head
    [1, 4 + C, anchors] of cx cy w h and class scores. The raw head needs NMS. Ultralytics bakes NMS into the
    graph only with torchvision ops, which the solver sandbox does not have, so `nms` here does it in torch.
    """
    raw = outputs[0] if isinstance(outputs, (tuple, list)) else outputs
    raw = raw[0].float()
    out: list[Detection] = []
    if raw.shape[-1] == 6:  # rows of x0 y0 x1 y1 score class
        for x0, y0, x1, y1, score, label in raw.tolist():
            index = int(label)
            if score < floor or index >= len(classes):
                continue
            out.append(Detection(classes[index], float(score), view.to_original((x0, y0, x1, y1))))
        return out
    rows = raw.T  # [anchors, 4 + C]
    scores, labels = rows[:, 4:].max(dim=1)
    keep = scores >= floor
    rows, scores, labels = rows[keep], scores[keep], labels[keep]
    cx, cy, w, h = rows[:, 0], rows[:, 1], rows[:, 2], rows[:, 3]
    boxes = np.stack([(cx - w / 2).numpy(), (cy - h / 2).numpy(), (cx + w / 2).numpy(), (cy + h / 2).numpy()], 1)
    for i in nms(boxes, scores.numpy(), labels.numpy(), YOLO_IOU)[:YOLO_MAX_DET]:
        index = int(labels[i])
        if index < len(classes):
            out.append(Detection(classes[index], float(scores[i]), view.to_original(boxes[i].tolist())))
    return out


YOLO_IOU = 0.5  # gives the same boxes as Ultralytics 8.4 predict on the YOLO26 weights
YOLO_MAX_DET = 300


def nms(boxes: np.ndarray, scores: np.ndarray, labels: np.ndarray, iou: float) -> list[int]:
    """Greedy class-aware NMS (boxes x0 y0 x1 y1): indices of the kept boxes, best score first."""
    order = np.argsort(-scores, kind="stable")
    area = (boxes[:, 2] - boxes[:, 0]).clip(0) * (boxes[:, 3] - boxes[:, 1]).clip(0)
    keep: list[int] = []
    while order.size:
        i = int(order[0])
        keep.append(i)
        rest = order[1:]
        ix0 = np.maximum(boxes[i, 0], boxes[rest, 0])
        iy0 = np.maximum(boxes[i, 1], boxes[rest, 1])
        ix1 = np.minimum(boxes[i, 2], boxes[rest, 2])
        iy1 = np.minimum(boxes[i, 3], boxes[rest, 3])
        inter = (ix1 - ix0).clip(0) * (iy1 - iy0).clip(0)
        union = area[i] + area[rest] - inter
        overlap = np.where(union > 0, inter / np.maximum(union, 1e-9), 0.0)
        order = rest[(overlap <= iou) | (labels[rest] != labels[i])]
    return keep


def _on_cpu(outputs: object) -> object:
    """The model outputs on the CPU: the decoders use NumPy, which cannot read a CUDA tensor."""
    if isinstance(outputs, dict):
        return {key: _on_cpu(value) for key, value in outputs.items()}
    if isinstance(outputs, (list, tuple)):
        return type(outputs)(_on_cpu(value) for value in outputs)
    return outputs.cpu() if hasattr(outputs, "cpu") else outputs  # ty: ignore[not-callable]


class Detector:
    """A loaded model. One per process: `Detector.get(directory)` caches it."""

    _cache: ClassVar[dict[str, Detector]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, directory: Path, device: str | None = None) -> None:
        import torch  # noqa: PLC0415

        self.directory = directory
        self.meta: dict[str, Any] = json.loads((directory / "meta.json").read_text())
        self.backend: str = self.meta["backend"]
        self.resolution: int = int(self.meta["resolution"])
        self.classes: tuple[str, ...] = tuple(self.meta["classes"])
        self.thresholds: dict[str, float] = {k: float(v) for k, v in self.meta.get("thresholds", {}).items()}
        self.floor = float(self.meta.get("floor", 0.05))
        torch.set_num_threads(max(1, int(self.meta.get("threads", 4))))
        # MPS stays out: the default was the CPU on a Mac, and the TorchScript model is not checked there.
        self.device = device or self.meta.get("device") or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = torch.jit.load(str(directory / "model.ts"), map_location=self.device).eval()

    @classmethod
    def get(cls, directory: Path) -> Detector:
        key = str(directory)
        with cls._lock:
            if key not in cls._cache:
                cls._cache[key] = cls(directory)
            return cls._cache[key]

    def _run(self, image: Image.Image, view: View) -> list[Detection]:
        import torch  # noqa: PLC0415

        rendered = render_view(image, view)
        if self.backend == "yolo":  # Ultralytics takes 0..1 RGB without mean and std
            tensor = torch.from_numpy(np.asarray(rendered, dtype=np.float32) / 255.0)
            tensor = tensor.permute(2, 0, 1).unsqueeze(0).contiguous().to(self.device)
        else:
            tensor = to_tensor(rendered).to(self.device)
        with torch.inference_mode():
            outputs = _on_cpu(self.model(tensor))
        if self.backend == "yolo":
            return decode_yolo(outputs, view, self.classes, self.floor)
        return decode_rfdetr(outputs, view, self.classes, self.floor)

    def detect(self, image: Image.Image, *, mirror: bool = False) -> list[Detection]:
        """Every detection above the floor score, merged across views, in original pixels.

        `mirror` runs the model on the left-right mirror of the plan and maps the boxes back: a second look
        whose count should agree with the first when the count is sure.
        """
        source = ImageOps.mirror(image) if mirror else image
        views = plan_views(source.width, source.height, self.resolution)
        merged = merge_views([(view, self._run(source, view)) for view in views])
        if not mirror:
            return merged
        width = image.width
        return [Detection(d.label, d.score, (width - d.box[2], d.box[1], width - d.box[0], d.box[3])) for d in merged]


def count(detections: Sequence[Detection], labels: Sequence[str], thresholds: dict[str, float]) -> list[Detection]:
    """The detections of `labels` at or above their class threshold."""
    return [d for d in detections if d.label in labels and d.score >= thresholds.get(d.label, 0.5)]
