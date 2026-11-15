"""Labels and the benchmark for the CubiCasa symbol detector (`bp.tools.symbol_detector`).

Labels: one box per countable SVG element of the public CubiCasa5K `model.svg`, chosen by the rules that
reproduce Stoa's count answers (`analysis/cubicasa/count_rules.py`, `sauna_geometry.py`). SVG coordinates are
pixels of `F1_scaled.png`; the Stoa PNG is `F1_original.png`, so a point maps by `W_original / W_scaled`.

This module reads `data/` and `analysis/`. It runs in a normal process (prepare, verify, bench), never in a
solver. `bench()` writes `experiments/tools/cubicasa-detect.json`.
"""

from __future__ import annotations

import json
import math
import re
import struct
import time
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import cache
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

import numpy as np
from shapely.geometry import Point, Polygon

from bp.paths import DATA, DATASET, EXPERIMENTS
from bp.tools.symbol_detector import CLASSES, CONCEPTS, Detection

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from bp.contract import Item

EXT = DATA / "external" / "cubicasa5k"
ZIP = EXT / "cubicasa5k.zip"
SVG = "{http://www.w3.org/2000/svg}"
# Stoa family id -> the concept of `CONCEPTS` that answers it.
FAMILY_CONCEPT: dict[str, str] = {
    "F:cubicasa5k/T000": "floors",
    "F:cubicasa5k/T001": "windows",
    "F:cubicasa5k/T004": "toilets",
    "F:cubicasa5k/T006": "sinks",
    "F:cubicasa5k/T008": "showers_tubs",
    "F:cubicasa5k/T010": "doors",
    "F:cubicasa5k/T012": "saunas",
    "F:cubicasa5k/T014": "kitchens",
    "F:cubicasa5k/T016": "bedrooms",
    "F:cubicasa5k/T018": "bathrooms",
    "F:cubicasa5k/T020": "wc_rooms",
    "F:cubicasa5k/T022": "balconies",
}
SINKS = frozenset({"Sink", "RoundSink", "DoubleSink", "DoubleSinkRight", "SideSink", "CornerSink"})
MIN_SIDE = 2.0  # px; a box thinner than this is widened, never dropped (a count must stay exact)

Matrix = np.ndarray
Box = tuple[float, float, float, float]
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_PATH_TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_ARITY = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}


def _cls(element: ET.Element) -> str:
    return " ".join((element.get("class") or "").split())


def parse_transform(text: str | None) -> Matrix:
    """An SVG transform list as a 3x3 matrix (matrix, translate, scale, rotate)."""
    m = np.eye(3)
    if not text:
        return m
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", text):
        v = [float(x) for x in _NUMBER.findall(args)]
        if name == "matrix" and len(v) == 6:
            step = np.array([[v[0], v[2], v[4]], [v[1], v[3], v[5]], [0, 0, 1]])
        elif name == "translate" and v:
            step = np.array([[1, 0, v[0]], [0, 1, v[1] if len(v) > 1 else 0.0], [0, 0, 1]])
        elif name == "scale" and v:
            step = np.diag([v[0], v[1] if len(v) > 1 else v[0], 1.0])
        elif name == "rotate" and v:
            a = math.radians(v[0])
            step = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
            if len(v) == 3:
                shift = np.array([[1, 0, v[1]], [0, 1, v[2]], [0, 0, 1]])
                back = np.array([[1, 0, -v[1]], [0, 1, -v[2]], [0, 0, 1]])
                step = shift @ step @ back
        else:
            continue
        m = m @ step
    return m


def _pairs(values: list[float]) -> list[tuple[float, float]]:
    return list(zip(values[0::2], values[1::2], strict=False))


def path_points(d: str) -> list[tuple[float, float]]:
    """End and control points of an SVG path (enough for a bounding box)."""
    tokens = _PATH_TOKEN.findall(d)
    points: list[tuple[float, float]] = []
    x = y = sx = sy = 0.0
    command = ""
    i = 0
    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]
            i += 1
            if command in "Zz":
                x, y = sx, sy
                continue
        if not command:
            break
        arity = _ARITY[command.upper()]
        args = tokens[i : i + arity]
        letters = [k for k, a in enumerate(args) if a.isalpha()]
        if letters:  # a malformed segment: skip to the next command
            i += letters[0]
            continue
        if len(args) < arity or arity == 0:
            break
        v = [float(a) for a in args]
        i += arity
        rel = command.islower()
        up = command.upper()
        ox, oy = (x, y) if rel else (0.0, 0.0)
        if up == "H":
            x = v[0] + (x if rel else 0.0)
            points.append((x, y))
        elif up == "V":
            y = v[0] + (y if rel else 0.0)
            points.append((x, y))
        elif up == "A":
            x, y = v[5] + ox, v[6] + oy
            points.append((x, y))
        else:
            pts = [(px + ox, py + oy) for px, py in _pairs(v)]
            points.extend(pts)
            x, y = pts[-1]
        if up == "M":
            sx, sy = x, y
            command = "l" if rel else "L"  # extra pairs after a move are lines
    return points


def shape_points(element: ET.Element) -> list[tuple[float, float]]:
    """Points of one shape element in its own frame."""
    tag = element.tag.replace(SVG, "")
    get = element.get
    if tag in {"polygon", "polyline"}:
        return _pairs([float(v) for v in _NUMBER.findall(get("points") or "")])
    if tag == "line":
        return [(float(get("x1") or 0), float(get("y1") or 0)), (float(get("x2") or 0), float(get("y2") or 0))]
    if tag == "rect":
        x, y = float(get("x") or 0), float(get("y") or 0)
        w, h = float(get("width") or 0), float(get("height") or 0)
        return [(x, y), (x + w, y + h)]
    if tag in {"circle", "ellipse"}:
        cx, cy = float(get("cx") or 0), float(get("cy") or 0)
        rx = float(get("r") or get("rx") or 0)
        ry = float(get("r") or get("ry") or 0)
        return [(cx - rx, cy - ry), (cx + rx, cy + ry)]
    if tag == "path":
        return path_points(get("d") or "")
    return []


def _apply(m: Matrix, points: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    return [(m[0, 0] * x + m[0, 1] * y + m[0, 2], m[1, 0] * x + m[1, 1] * y + m[1, 2]) for x, y in points]


def geometry(element: ET.Element, m: Matrix, *, only: str = "") -> list[tuple[float, float]]:
    """All shape points under `element` in the outer frame. `only`: keep shapes under a child of this class."""
    out: list[tuple[float, float]] = []

    def walk(node: ET.Element, frame: Matrix, inside: bool) -> None:
        tag = node.tag.replace(SVG, "")
        if tag in {"defs", "text", "desc", "title"}:
            return
        here = frame @ parse_transform(node.get("transform"))
        inside = inside or (bool(only) and _cls(node) == only)
        if "display: none" in (node.get("style") or "") and node is not element:
            return
        if not only or inside:
            out.extend(_apply(here, shape_points(node)))
        for child in node:
            walk(child, here, inside)

    walk(element, m, False)
    return out


def _box(points: list[tuple[float, float]]) -> tuple[float, float, float, float] | None:
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _name_label(space: ET.Element) -> str:
    for node in space.iter():
        if _cls(node) == "TextLabel NameLabel":
            texts = ["".join(t.itertext()).strip() for t in node.iter(f"{SVG}text")]
            return " ".join(t for t in texts if t)
    return ""


@dataclass
class _Parsed:
    doors: list[tuple[str, tuple[float, float, float, float]]] = field(default_factory=list)
    windows: list[tuple[float, float, float, float]] = field(default_factory=list)
    furniture: list[tuple[str, tuple[float, float, float, float]]] = field(default_factory=list)
    spaces: list[tuple[str, str, Polygon]] = field(default_factory=list)
    floorplans: list[tuple[float, float, float, float]] = field(default_factory=list)


def _floor_box(node: ET.Element, frame: Matrix, here: Matrix) -> Box:
    pts: list[tuple[float, float]] = []
    for sub in node.iter():
        polygon = sub.find(f"{SVG}polygon")
        if _cls(sub).startswith(("Wall", "Space ")) and polygon is not None:
            pts.extend(_apply(here, shape_points(polygon)))
    # A floor with no geometry still counts (the reference counts Floorplan groups): a 1 px box at 0, 0.
    return _box(pts) or _box(geometry(node, frame)) or (0.0, 0.0, 1.0, 1.0)


def _leaf(parsed: _Parsed, first: str, c: str, node: ET.Element, frame: Matrix) -> bool:
    """Record a door, window or fixture. True when `node` was one (its children need no walk)."""
    if first in {"Door", "Window"}:
        box = _box(geometry(node, frame))
        if box and first == "Door":
            parsed.doors.append((c, box))
        elif box:
            parsed.windows.append(box)
        return True
    if first == "FixedFurniture":
        box = _box(geometry(node, frame, only="BoundaryPolygon")) or _box(geometry(node, frame))
        if box:
            parsed.furniture.append((c, box))
        return True
    return False


def parse_svg(text: str) -> _Parsed:
    """The countable elements of one model.svg, in SVG coordinates."""
    root = ET.fromstring(text)  # noqa: S314 - a local public dataset file
    parsed = _Parsed()

    def walk(node: ET.Element, frame: Matrix) -> None:
        if node.tag.replace(SVG, "") == "defs":
            return
        here = frame @ parse_transform(node.get("transform"))
        c = _cls(node)
        first = c.split(" ", 1)[0] if c else ""
        if _leaf(parsed, first, c, node, frame):
            return
        if first == "Floorplan":
            parsed.floorplans.append(_floor_box(node, frame, here))
        elif first == "Space":
            poly = node.find(f"{SVG}polygon")
            pts = _apply(here, shape_points(poly)) if poly is not None else []
            if len(pts) >= 3:
                parsed.spaces.append((c, _name_label(node), Polygon(pts).buffer(0)))
        for child in node:
            walk(child, here)

    walk(root, np.eye(3))
    return parsed


def _furniture_kind(c: str) -> str | None:
    parts = c.split()
    name = parts[1] if len(parts) > 1 else ""
    label = None
    if name == "Toilet":
        label = "toilet"
    elif name in SINKS:
        label = "sink"
    elif name == "Shower":
        label = "shower"
    elif name in {"Bathtub", "BathtubRound"}:
        label = "bathtub"
    elif name == "ShowerCab":
        label = "shower_cab"
    return label


def _room_kind(c: str, label: str) -> str | None:
    if c == "Space Bedroom" or c.startswith("Space Bedroom "):
        return "bedroom"
    if c == "Space Kitchen" or c.startswith("Space Kitchen "):
        return "kitchen"
    if c == "Space Bath":
        return "wc_room" if label.upper() == "WC" else "bathroom"
    if c == "Space Bath Shower":
        return "bathroom"
    if c == "Space Outdoor Balcony" or c.startswith("Space Outdoor Balcony "):
        return "balcony"
    return None


def boxes_from_svg(text: str) -> list[tuple[str, Box]]:
    """Labelled boxes in SVG coordinates, one per counted object."""
    p = parse_svg(text)
    out: list[tuple[str, Box]] = []
    for c, box in p.doors:
        out.append(("doorway" if c.startswith("Door None") else "door", box))
    out.extend(("window", box) for box in p.windows)
    stoves: list[Box] = []
    for c, box in p.furniture:
        kind = _furniture_kind(c)
        if kind:
            out.append((kind, box))
        if "SaunaStove" in c:
            stoves.append(box)
    for c, label, poly in p.spaces:
        kind = _room_kind(c, label)
        if kind and not poly.is_empty:
            out.append((kind, poly.bounds))
    # Saunas: rooms that hold a stove, union with Space Sauna rooms; a stove outside every room counts alone.
    rooms: set[int] = {i for i, (c, _, _) in enumerate(p.spaces) if c == "Space Sauna"}
    lonely: list[Box] = []
    for box in stoves:
        centre = Point((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        hits = [i for i, (_, _, poly) in enumerate(p.spaces) if poly.contains(centre)]
        if hits:
            rooms.add(min(hits, key=lambda i: p.spaces[i][2].area))
        else:
            lonely.append(box)
    out.extend(("sauna", p.spaces[i][2].bounds) for i in sorted(rooms) if not p.spaces[i][2].is_empty)
    out.extend(("sauna", box) for box in lonely)
    out.extend(("floorplan", box) for box in p.floorplans)
    return out


def _png_size(raw: bytes) -> tuple[int, int]:
    width, height = struct.unpack(">II", raw[16:24])
    return int(width), int(height)


@cache
def _zip() -> zipfile.ZipFile:
    return zipfile.ZipFile(ZIP)


def scaled_size(stem: str) -> tuple[int, int]:
    """Width and height of `F1_scaled.png` for a Stoa stem such as `high_quality-470`."""
    group, ident = stem.rsplit("-", 1)
    with _zip().open(f"cubicasa5k/{group}/{ident}/F1_scaled.png") as handle:
        return _png_size(handle.read(24))


@dataclass(frozen=True)
class PlanLabels:
    stem: str
    width: int
    height: int
    boxes: tuple[tuple[str, Box], ...]  # in original PNG pixels

    def count(self, labels: Iterable[str]) -> int:
        wanted = set(labels)
        return sum(1 for label, _ in self.boxes if label in wanted)


def plan_labels(stem: str) -> PlanLabels:
    """Boxes for the Stoa PNG `data/cubicasa5k/<stem>.png`, in its pixel space."""
    group, ident = stem.rsplit("-", 1)
    text = (EXT / "svg" / group / ident / "model.svg").read_text(errors="ignore")
    with (DATASET / "data" / "cubicasa5k" / f"{stem}.png").open("rb") as handle:
        width, height = _png_size(handle.read(24))
    sw, sh = scaled_size(stem)
    fx, fy = width / sw, height / sh
    boxes: list[tuple[str, Box]] = []
    for label, (x0, y0, x1, y1) in boxes_from_svg(text):
        a, b, c, d = x0 * fx, y0 * fy, x1 * fx, y1 * fy
        if c - a < MIN_SIDE:
            a, c = (a + c) / 2 - MIN_SIDE / 2, (a + c) / 2 + MIN_SIDE / 2
        if d - b < MIN_SIDE:
            b, d = (b + d) / 2 - MIN_SIDE / 2, (b + d) / 2 + MIN_SIDE / 2
        boxes.append((label, (float(a), float(b), float(c), float(d))))
    return PlanLabels(stem, width, height, tuple(boxes))


def stem_of(item: Item) -> str:
    return item.doc.rsplit("/", 1)[-1].removesuffix(".png")


def plans_by_partition(items: Iterable[Item]) -> dict[str, dict[str, list[Item]]]:
    """Partition -> stem -> the cubicasa count items of that plan."""
    out: dict[str, dict[str, list[Item]]] = defaultdict(lambda: defaultdict(list))
    for it in items:
        if it.source == "cubicasa5k" and it.family in FAMILY_CONCEPT:
            out[it.partition][stem_of(it)].append(it)
    return out


def verify(items: Iterable[Item], stems: Iterable[str] | None = None) -> dict[str, Any]:
    """Label boxes per concept against Stoa's key for each family, on the chosen plans (all plans when None)."""
    by_stem: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        if it.source == "cubicasa5k" and it.family in FAMILY_CONCEPT:
            by_stem[stem_of(it)].append(it)
    chosen = sorted(by_stem) if stems is None else [s for s in stems if s in by_stem]
    agree: Counter[str] = Counter()
    total: Counter[str] = Counter()
    bad_plans: dict[str, list[str]] = {}
    outside = 0
    boxes = 0
    for stem in chosen:
        labels = plan_labels(stem)
        for label, (x0, y0, x1, y1) in labels.boxes:
            boxes += 1
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if not (0 <= cx <= labels.width and 0 <= cy <= labels.height):
                outside += 1
            del label
        for it in by_stem[stem]:
            concept = FAMILY_CONCEPT[it.family]
            got = labels.count(CONCEPTS[concept])
            key = getattr(it.key, "value", None)
            total[concept] += 1
            if got == key:
                agree[concept] += 1
            else:
                bad_plans.setdefault(stem, []).append(f"{concept}: labels {got} key {key}")
    per = {c: {"n": total[c], "agree": round(agree[c] / total[c], 4)} for c in sorted(total)}
    n = sum(total.values())
    return {
        "plans": len(chosen),
        "questions": n,
        "agreement": round(sum(agree.values()) / n, 4) if n else 0.0,
        "per_concept": per,
        "plans_with_disagreement": len(bad_plans),
        "disagreements": dict(list(bad_plans.items())[:30]),
        "bad_plans": sorted(bad_plans),
        "boxes": boxes,
        "box_centres_outside_image": outside,
    }


# ----------------------------------------------------------------------------- benchmark


def match(preds: list[Detection], truth: list[Box], iou_min: float = 0.3) -> int:
    """Greedy one-to-one matches by IoU, highest score first. Returns the number of true positives."""
    used: set[int] = set()
    hits = 0
    for det in sorted(preds, key=lambda d: -d.score):
        best, best_iou = -1, iou_min
        for j, box in enumerate(truth):
            if j in used:
                continue
            value = _iou(det.box, box)
            if value >= best_iou:
                best, best_iou = j, value
        if best >= 0:
            used.add(best)
            hits += 1
    return hits


def _iou(a: Box, b: Box) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    inter = w * h
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def class_metrics(
    plans: list[tuple[PlanLabels, list[Detection]]], thresholds: dict[str, float]
) -> dict[str, dict[str, float]]:
    """Per class: precision, recall (IoU 0.3), exact-count rate per plan and mean absolute count error."""
    out: dict[str, dict[str, float]] = {}
    for label in CLASSES:
        tp = fp = fn = exact = 0
        abs_err = 0.0
        for labels, dets in plans:
            truth = [box for lab, box in labels.boxes if lab == label]
            kept = [d for d in dets if d.label == label and d.score >= thresholds.get(label, 0.5)]
            hits = match(kept, truth)
            tp += hits
            fp += len(kept) - hits
            fn += len(truth) - hits
            exact += int(len(kept) == len(truth))
            abs_err += abs(len(kept) - len(truth))
        n = max(1, len(plans))
        out[label] = {
            "objects": tp + fn,
            "precision": round(tp / (tp + fp), 4) if tp + fp else 0.0,
            "recall": round(tp / (tp + fn), 4) if tp + fn else 0.0,
            "exact_count_rate": round(exact / n, 4),
            "mean_abs_count_error": round(abs_err / n, 4),
        }
    return out


def _detections_for(
    stems: list[str],
    directory: Any,  # noqa: ANN401
    *,
    mirror: bool = False,
) -> Iterator[tuple[str, list[Detection]]]:
    from bp.tools.symbol_detector import Detector, load_rgb  # noqa: PLC0415

    detector = Detector.get(directory)
    for stem in stems:
        image = load_rgb(DATASET / "data" / "cubicasa5k" / f"{stem}.png")
        yield stem, detector.detect(image, mirror=mirror)


def bench(model: str = "", partition: str = "val", limit: int = 0) -> dict[str, Any]:
    """Run the detector on every plan of `partition` and score it against the SVG-rule labels."""
    from bp.solvers.cubicasa_detect import model_directory  # noqa: PLC0415
    from bp.suites import read_items  # noqa: PLC0415

    directory = model_directory(model)
    meta = json.loads((directory / "meta.json").read_text())
    stems = sorted(plans_by_partition(read_items("stoa"))[partition])
    if limit:
        stems = stems[:limit]
    started = time.perf_counter()
    plans = [(plan_labels(stem), dets) for stem, dets in _detections_for(stems, directory)]
    seconds = time.perf_counter() - started
    result = {
        "tool": "cubicasa-detect",
        "model": directory.name,
        "partition": partition,
        "plans": len(plans),
        "seconds_per_plan": round(seconds / max(1, len(plans)), 3),
        "thresholds": meta.get("thresholds", {}),
        "per_class": class_metrics(plans, meta.get("thresholds", {})),
    }
    target = EXPERIMENTS / "tools" / "cubicasa-detect.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=1))
    return result


# ----------------------------------------------------------------------------- calibration on held-out DEV

THRESHOLDS = tuple(round(0.05 + 0.025 * i, 3) for i in range(37))  # 0.05 .. 0.95
BANDS = tuple(round(0.025 * i, 3) for i in range(13))  # 0 .. 0.30
MAX_COUNTS = (3, 5, 8, 10, 12, 15, 20, 30, 10**6)


def detect_plans(
    stems: list[str],
    directory: Any,  # noqa: ANN401
    cache_file: Any = None,  # noqa: ANN401
    *,
    mirror: bool = False,
) -> dict[str, list[Detection]]:
    """Detections per plan, read from `cache_file` when it holds them, else computed and written there."""
    cached: dict[str, list[Detection]] = {}
    if cache_file is not None and cache_file.exists():
        raw = json.loads(cache_file.read_text())
        cached = {s: [Detection(d[0], d[1], tuple(d[2])) for d in v] for s, v in raw.items()}
    todo = [s for s in stems if s not in cached]
    for done, (stem, dets) in enumerate(_detections_for(todo, directory, mirror=mirror), start=1):
        cached[stem] = dets
        if cache_file is not None and (done % 50 == 0 or done == len(todo)):
            data = {
                s: [[d.label, round(d.score, 4), [round(v, 1) for v in d.box]] for d in v] for s, v in cached.items()
            }
            cache_file.write_text(json.dumps(data))
    return {s: cached[s] for s in stems}


Pair = tuple[list[float], list[float] | None, int]  # scores, mirror scores (or None), key


def _counts(pairs: Sequence[Pair], t: float, *, mirror: bool = False) -> np.ndarray:
    return np.array([sum(1 for s in (m if mirror else sc) or () if s >= t) for sc, m, _ in pairs])


def tune(pairs: Sequence[Pair], min_answered: int = 0) -> dict[str, float] | None:
    """The counting rule with the best +1/0/-1 score.

    A rule is a threshold, a band of doubt around it, a largest count, and whether the mirror count must agree.
    Ties go to more answers, then to a narrower band.
    """
    keys = np.array([k for _, _, k in pairs])
    n = len(pairs)
    has_mirror = all(m is not None for _, m, _ in pairs)
    best: tuple[float, ...] | None = None
    plain = (-1e9, 0.5, 0.0)
    for t in THRESHOLDS:
        counts = _counts(pairs, t)
        below = np.array([min((t - s for s in sc if s < t), default=9.0) for sc, _, _ in pairs])
        above = np.array([min((s - t for s in sc if s >= t), default=9.0) for sc, _, _ in pairs])
        disagree = (_counts(pairs, t, mirror=True) != counts) if has_mirror else np.zeros(n, dtype=bool)
        correct = counts == keys
        r0 = int(correct.sum())
        if 2 * r0 - n > plain[0]:
            plain = (2 * r0 - n, t, r0 / n)
        for b in BANDS:
            near = (below <= b) | (above < b) if b > 0 else np.zeros(n, dtype=bool)
            for m in MAX_COUNTS:
                for use_mirror in (False, True) if has_mirror else (False,):
                    answered = ~near & (counts <= m) & ~(disagree & use_mirror)
                    r = int((answered & correct).sum())
                    w = int((answered & ~correct).sum())
                    if r + w < min_answered:
                        continue
                    key = (r - w, r + w, -b, -use_mirror, t, b, m, use_mirror, r, w)
                    if best is None or key > best:
                        best = key
    if best is None:
        return None
    t, b, m, use_mirror, r, w = best[4:]
    return {
        "threshold": t, "band": b, "max_count": int(m), "mirror": bool(use_mirror), "n": n, "right": int(r),
        "wrong": int(w), "abstained": int(n - r - w), "score": round((r - w) / n, 4),
        "answered_accuracy": round(r / max(1, r + w), 4), "plain_threshold": plain[1],
        "plain_accuracy": round(plain[2], 4), "plain_score": round(plain[0] / n, 4),
    }  # fmt: skip


def calibrate(model: str = "", min_answered: int = 0, *, mirror: bool = True) -> dict[str, Any]:
    """Tune the counting rule per concept on the held-out DEV plans; write it into meta.json."""
    from bp.solvers.cubicasa_detect import model_directory  # noqa: PLC0415
    from bp.suites import read_items  # noqa: PLC0415

    directory = model_directory(model)
    plans_file = directory / "plans.json"
    hold = json.loads(plans_file.read_text())["hold"]
    items = read_items("stoa")
    dets = detect_plans(hold, directory, directory / "hold_detections.json")
    mirrored = detect_plans(hold, directory, directory / "hold_detections_mirror.json", mirror=True) if mirror else {}
    per_concept: dict[str, list[Pair]] = defaultdict(list)
    for it in items:
        if it.partition != "dev" or it.family not in FAMILY_CONCEPT or stem_of(it) not in dets:
            continue
        concept = FAMILY_CONCEPT[it.family]
        labels = CONCEPTS[concept]
        scores = [d.score for d in dets[stem_of(it)] if d.label in labels]
        other = [d.score for d in mirrored[stem_of(it)] if d.label in labels] if mirror else None
        per_concept[concept].append((scores, other, int(getattr(it.key, "value", -1))))
    calibration: dict[str, dict[str, float]] = {}
    for concept, pairs in sorted(per_concept.items()):
        rule = tune(pairs, min_answered)
        if rule is not None:
            calibration[concept] = rule
    # Derived concepts and class thresholds for the benchmark.
    if "showers_tubs" in calibration:
        for concept in ("showers", "bathtubs"):
            calibration.setdefault(concept, dict(calibration["showers_tubs"]))
    thresholds = {}
    for concept, rule in calibration.items():
        for label in CONCEPTS[concept]:
            thresholds.setdefault(label, rule["threshold"])
    meta = json.loads((directory / "meta.json").read_text())
    meta["calibration"] = calibration
    meta["thresholds"] = thresholds
    meta["calibrated_on"] = f"{len(hold)} held-out DEV plans"
    meta["mirror"] = any(rule.get("mirror") for rule in calibration.values())
    (directory / "meta.json").write_text(json.dumps(meta, indent=1))
    return {"plans": len(hold), "calibration": calibration}


def main() -> None:
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="Labels, calibration and the benchmark of the CubiCasa detector.")
    parser.add_argument("command", choices=["verify", "calibrate", "bench"])
    parser.add_argument("--model", default="")
    parser.add_argument("--partition", default="val")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    if args.command == "verify":
        from bp.suites import read_items  # noqa: PLC0415

        result = verify(read_items("stoa"))
        result.pop("bad_plans")
    elif args.command == "calibrate":
        result = calibrate(args.model)
    else:
        result = bench(args.model, args.partition, args.limit)
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
