"""Rooms on a raster floor plan: numbers and labels by OCR, regions and areas from pixels.

Everything works at one canonical scale: the image is resized so that one metre is 59.06 px (a 150 dpi sheet at
1:100), which is the scale the room model was trained at.

1. Text: room numbers ("2.07", "U1.04") from OCR, the label centred above each number, a printed area below it
   ("15.61 m²"), apartment tags ("Whg. A", "App. B").
2. Regions, two independent methods:
   - `baseline_regions`: image processing only. Ink is dark pixels; walls are the ink left after an opening by a
     5 px square. Light pixels form components. The component under a room number seeds the room. A component
     with no number (a door swing sector, a fixture box) joins the room that it shares the longest thin border
     with, if it is not a sliver (window bands and wall hatch). The room then takes the thin ink next to it.
   - `model_regions`: a U-Net (artifacts/raster-rooms/model.pt) gives room interior, wall, room boundary and opening
     probabilities. Cores (interior high, boundary low) are the markers of a watershed on the boundary
     probability. The core under a number names the room. Area = sum of the interior probability in the region.
3. Area of a room: the printed value when the sheet prints one and it agrees with the measured area within 5%,
   else the model area. Confidence is high only when the model and the baseline agree within 2% (or the print
   agrees). The rule is measured in experiments/tools/raster.json.
4. Apartments: the red dash-dot outline (colour segmentation) splits the plan into units; a tag inside a unit
   names it. Outdoor rooms are known by their label (Balkon, Loggia, Terrasse and the fr and it words) or by a
   grey fill.
"""

from __future__ import annotations

import math
import re
from functools import cache
from typing import TYPE_CHECKING, Literal

import cv2
import numpy as np
from PIL import Image

from bp.contract import Evidence, Frozen
from bp.paths import ARTIFACTS
from bp.tools import ocr
from bp.tools.raster_scale import RasterScale, measure_scale

if TYPE_CHECKING:
    from bp.tools.ocr import TextLine

CANON_PPM = 150.0 / 0.0254 / 100.0  # the model works at 59.06 px per metre (a 150 dpi sheet at 1:100)
MODEL_PATH = ARTIFACTS / "raster-rooms" / "model.pt"
INK = 200  # a pixel darker than this is ink
WALL_KERNEL = 5
SLIVER_DT = 3.0  # a component thinner than this (max distance to its border, px) is a window band or hatch
THIN_GROW = 4  # px of thin ink that a room takes from its border
LABEL_DX = 0.9  # a label is centred on the number: |dx| below this share of the label height ...
LABEL_DY = 2.6  # ... and at most this many number heights above it
HIGH_AGREE = 0.03  # model and baseline within this: high confidence
MEDIUM_LOW, MEDIUM_HIGH = 0.9, 1.12  # model / baseline in this range: medium
PRINT_AGREE = 0.05
TAG = re.compile(r"^(?:Whg|App|Appt|Apt)\.?\s*([A-Z]{1,2})$")
OUTDOOR_WORDS = frozenset(
    {
        "balkon", "balcon", "balcone", "loggia", "terrasse", "terrazza", "sitzplatz", "patio", "garten",
        "jardin", "giardino", "veranda", "wintergarten",
    }
)  # fmt: skip
RECOVER_MIN_M2 = 0.8  # a region without a number below this is a shaft or a gap, not a room
RECOVER_MAX = 25
RECOVER_PAD = 24  # input px around a region when it is read again
RECOVER_UPSCALE = 3.0
RED_MIN = 0.12  # (r - max(g, b)) / 255 above this is the red apartment outline


# ----------------------------------------------------------------------------- models


class RoomText(Frozen):
    number: str
    label: str | None
    printed_m2: float | None
    x: float  # canonical px
    y: float
    height: float
    score: float


class Room(Frozen):
    """One numbered room. Same field names as the vector tool where the meaning is the same."""

    number: str
    label: str | None
    area_m2: float | None
    area_source: Literal["printed", "model", "baseline", "none"]
    area_confidence: Literal["high", "medium", "low", "none"]
    model_area_m2: float | None
    baseline_area_m2: float | None
    printed_area_m2: float | None
    apartment: str | None
    outdoor: bool
    at: tuple[float, float]  # px of the input image
    polygon: tuple[tuple[float, float], ...]  # px of the input image

    def evidence(self) -> tuple[Evidence, ...]:
        out = [Evidence(kind="text_span", points=(self.at,), ref=self.number, note=self.label or "")]
        if self.polygon:
            out.append(Evidence(kind="polygon", points=self.polygon[:60], ref=self.number, note=f"{self.area_m2} m2"))
        return tuple(out)


class Apartment(Frozen):
    letter: str
    at: tuple[float, float]
    unit: int | None  # index of the outline region that holds the tag
    outline_area_m2: float | None = None  # the area inside the red outline (rooms, inner walls), None with no outline
    unread_area_m2: float | None = None  # room-like area inside the outline that no read number claims


class RasterPlan(Frozen):
    width: int
    height: int
    scale: RasterScale | None
    factor: float  # canonical px per input px
    rooms: tuple[Room, ...]
    apartments: tuple[Apartment, ...]
    texts: int
    model_used: bool
    plan_like: bool
    reasons: tuple[str, ...]
    unread_area_m2: float | None = None  # room-like area on the sheet that no read number claims (model only)


# ----------------------------------------------------------------------------- helpers


def canonical(rgb: np.ndarray, ppm: float) -> tuple[np.ndarray, float]:
    """The image resized to the canonical scale, and the factor that was applied."""
    factor = CANON_PPM / ppm
    if abs(factor - 1.0) < 1e-3:
        return rgb, 1.0
    h, w = rgb.shape[:2]
    size = (round(w * factor), round(h * factor))
    return np.asarray(Image.fromarray(rgb).resize(size, Image.Resampling.BICUBIC)), factor


def is_outdoor_label(label: str | None) -> bool:
    if not label:
        return False
    words = re.split(r"[\s/,-]+", label.lower())
    return any(w in OUTDOOR_WORDS for w in words)


def room_texts(lines: list[TextLine], factor: float = 1.0) -> list[RoomText]:
    """Room numbers with the label above and the printed area below, in canonical px."""
    numbers = [(n, line) for line in lines if (n := ocr.room_number(line.text))]
    others = [line for line in lines if ocr.room_number(line.text) is None and not TAG.match(line.text.strip())]
    out: list[RoomText] = []
    seen: set[str] = set()
    for number, line in sorted(numbers, key=lambda t: -t[1].score):
        if number in seen:
            continue
        seen.add(number)
        h = max(line.height, 4.0)

        def near(o: TextLine, *, above: bool, ref: TextLine = line, size: float = h) -> float | None:
            dy = ref.cy - o.cy if above else o.cy - ref.cy
            if 0 < dy < LABEL_DY * size and abs(o.cx - ref.cx) < max(LABEL_DX * size, 0.25 * o.width):
                return dy
            return None

        above = [(d, o) for o in others if (d := near(o, above=True)) is not None and ocr.area_value(o.text) is None]
        below = [
            (d, o) for o in others if (d := near(o, above=False)) is not None and ocr.area_value(o.text) is not None
        ]
        label = min(above, key=lambda t: t[0])[1].text.strip(" :;|.") if above else None
        printed = ocr.area_value(min(below, key=lambda t: t[0])[1].text) if below else None
        out.append(
            RoomText(number=number, label=label or None, printed_m2=printed, x=line.cx * factor, y=line.cy * factor,
                     height=h * factor, score=line.score)
        )  # fmt: skip
    return out


def _text_mask(shape: tuple[int, int], lines: list[TextLine], factor: float) -> np.ndarray:
    mask = np.zeros(shape, np.uint8)
    for line in lines:
        x0, y0, x1, y1 = (v * factor for v in line.bbox)
        cv2.rectangle(mask, (int(x0) - 1, int(y0) - 1), (math.ceil(x1) + 1, math.ceil(y1) + 1), 1, thickness=-1)
    return mask.astype(bool)


def _seed_label(labels: np.ndarray, x: float, y: float, radius: int = 6) -> int:
    h, w = labels.shape
    xi, yi = round(x), round(y)
    best, dist = 0, 1e9
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            yy, xx = yi + dy, xi + dx
            if 0 <= yy < h and 0 <= xx < w and labels[yy, xx] > 0 and dx * dx + dy * dy < dist:
                best, dist = int(labels[yy, xx]), dx * dx + dy * dy
    return best


# ----------------------------------------------------------------------------- baseline


def baseline_regions(gray: np.ndarray, seeds: list[tuple[float, float]], text: np.ndarray) -> np.ndarray:  # noqa: C901, PLR0912, PLR0915 - one pass, kept together
    """A label image: 0 nothing, i + 1 the room of seed i. Canonical scale."""
    ink = (gray < INK) & ~text
    kernel = np.ones((WALL_KERNEL, WALL_KERNEL), np.uint8)
    wall = cv2.morphologyEx(ink.astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(bool)
    thin = ink & ~wall
    count, comp, stats, _ = cv2.connectedComponentsWithStats((~ink).astype(np.uint8), connectivity=4)
    h, w = gray.shape
    owner = np.zeros(count, np.int32)  # component -> room id (0 none)
    for i, (x, y) in enumerate(seeds):
        c = _seed_label(comp, x, y)
        if c > 0 and owner[c] == 0:
            owner[c] = i + 1
    # components that touch the image border are the outside
    border = np.unique(np.concatenate([comp[0], comp[-1], comp[:, 0], comp[:, -1]]))
    outside = np.zeros(count, bool)
    outside[border] = True
    outside[0] = True
    big = stats[:, cv2.CC_STAT_AREA] > 0.25 * h * w
    outside |= big & (owner == 0)
    # thickness of each component: the largest distance to its border
    dist = cv2.distanceTransform((comp > 0).astype(np.uint8) * (~ink).astype(np.uint8), cv2.DIST_L2, 3)
    thick = np.zeros(count, np.float32)
    np.maximum.at(thick, comp.ravel(), dist.ravel())
    # adjacency across thin ink: label pairs at a distance of 2 or 3 px with thin ink between
    pairs: dict[tuple[int, int], int] = {}
    for dy, dx in ((0, 2), (0, 3), (2, 0), (3, 0)):
        a = comp[: h - dy, : w - dx]
        b = comp[dy:, dx:]
        mid = thin[dy // 2 : h - dy + dy // 2, dx // 2 : w - dx + dx // 2]
        ok = (a > 0) & (b > 0) & (a != b) & mid
        if not ok.any():
            continue
        av, bv = a[ok], b[ok]
        lo, hi = np.minimum(av, bv), np.maximum(av, bv)
        keys, counts = np.unique(lo.astype(np.int64) * count + hi, return_counts=True)
        for key, n in zip(keys.tolist(), counts.tolist(), strict=True):
            pair = (key // count, key % count)
            pairs[pair] = pairs.get(pair, 0) + n
    neighbours: dict[int, dict[int, int]] = {}
    for (a, b), n in pairs.items():
        neighbours.setdefault(a, {})[b] = n
        neighbours.setdefault(b, {})[a] = n
    for _ in range(6):  # a sector behind a fixture joins through the fixture
        changed = False
        for c in range(1, count):
            if owner[c] or outside[c] or thick[c] < SLIVER_DT:
                continue
            votes: dict[int, int] = {}
            for other, n in neighbours.get(c, {}).items():
                if owner[other]:
                    votes[int(owner[other])] = votes.get(int(owner[other]), 0) + n
                elif outside[other]:
                    votes[0] = votes.get(0, 0) + n
            if votes:
                best = max(votes, key=lambda k: votes[k])
                if best > 0 and votes[best] > votes.get(0, 0):
                    owner[c] = best
                    changed = True
        if not changed:
            break
    rooms = owner[comp]
    # each room takes the thin ink within THIN_GROW px of it (the nearest room wins)
    free = (rooms == 0).astype(np.uint8)
    dist2, nearest = cv2.distanceTransformWithLabels(free, cv2.DIST_L2, 3, labelType=cv2.DIST_LABEL_PIXEL)
    ys, xs = np.nonzero(rooms > 0)
    lookup = np.zeros(int(nearest.max()) + 1, np.int32)
    lookup[nearest[ys, xs]] = rooms[ys, xs]
    grow = thin & (rooms == 0) & (dist2 <= THIN_GROW)
    rooms[grow] = lookup[nearest[grow]]
    return rooms


# ----------------------------------------------------------------------------- model


@cache
def load_model() -> object | None:
    if not MODEL_PATH.exists():
        return None
    import segmentation_models_pytorch as smp  # noqa: PLC0415 - heavy, only when the model runs
    import torch  # noqa: PLC0415

    blob = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
    model = smp.Unet(blob["encoder"], encoder_weights=None, in_channels=3, classes=int(blob["classes"]))
    model.load_state_dict({k: v.float() for k, v in blob["state_dict"].items()})
    model.eval()
    return model


def predict(rgb: np.ndarray, tile: int = 1024, overlap: int = 128) -> np.ndarray | None:
    """Probabilities (H, W, 4) of the canonical image: interior, wall, boundary, opening. None without weights."""
    model = load_model()
    if model is None:
        return None
    import torch  # noqa: PLC0415

    mean = np.array([0.485, 0.456, 0.406], np.float32)
    std = np.array([0.229, 0.224, 0.225], np.float32)
    h, w = rgb.shape[:2]
    ph, pw = max(h, tile), max(w, tile)
    padded = np.full((ph, pw, 3), 255, np.uint8)
    padded[:h, :w] = rgb
    x = (padded.astype(np.float32) / 255.0 - mean) / std
    out = np.zeros((ph, pw, 4), np.float32)
    weight = np.zeros((ph, pw, 1), np.float32)
    ramp = np.minimum(np.arange(tile) + 1, np.arange(tile)[::-1] + 1).astype(np.float32)
    ramp = np.minimum(ramp / overlap, 1.0)
    win = (ramp[:, None] * ramp[None, :])[..., None]
    step = tile - overlap
    ys = [*list(range(0, ph - tile, step)), ph - tile]
    xs = [*list(range(0, pw - tile, step)), pw - tile]
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    net = model.to(device)  # ty: ignore[missing-attribute]
    with torch.no_grad():
        for y0 in ys:
            batch = [x[y0 : y0 + tile, x0 : x0 + tile] for x0 in xs]
            tensor = torch.from_numpy(np.stack(batch).transpose(0, 3, 1, 2).copy()).to(device)
            prob = torch.sigmoid(net(tensor)).cpu().numpy().transpose(0, 2, 3, 1)
            for x0, p in zip(xs, prob, strict=True):
                out[y0 : y0 + tile, x0 : x0 + tile] += p * win
                weight[y0 : y0 + tile, x0 : x0 + tile] += win
    return (out / np.maximum(weight, 1e-6))[:h, :w]


def model_regions(
    prob: np.ndarray, seeds: list[tuple[float, float]], split: np.ndarray | None = None
) -> tuple[np.ndarray, list[float], list[int]]:
    """Watershed of the room probability.

    It returns the label image (i + 1 = seed i), the soft areas in px and, per seed, how many seeds share its core (1 is clean).

    Every core (interior high, boundary low) is a marker, also a core without a number (a shaft, a room whose
    number OCR missed), so that no room spreads into a neighbour. The flood covers the whole image; the area of a
    room is the sum of the interior probability in its basin, so walls and the outside add nothing. A basin that
    several numbers share is cut by `split`, the baseline label image, whose regions stop at thin drawn lines.
    """
    interior, boundary = prob[..., 0], prob[..., 2]
    core = ((interior > 0.6) & (boundary < 0.3)).astype(np.uint8)
    core = cv2.erode(core, np.ones((3, 3), np.uint8))
    _, comp = cv2.connectedComponents(core, connectivity=4)
    seed_core = [_seed_label(comp, x, y, radius=10) for x, y in seeds]
    shared = [sum(1 for s in seed_core if s == c) if c else 0 for c in seed_core]
    markers = comp.astype(np.int32)
    # Flood on 1 - interior: a room fills its whole interior before it crosses a wall, and two floods meet on the
    # wall centre. (A relief of the boundary channel put the meeting line inside the edge band: 3% low.)
    relief = np.clip((1.0 - interior) * 255, 0, 255).astype(np.uint8)
    cv2.watershed(cv2.cvtColor(relief, cv2.COLOR_GRAY2BGR), markers)
    line = markers < 0
    if line.any():  # a watershed line pixel joins the largest label next to it
        grown = cv2.dilate(np.where(line, 0, markers).astype(np.float32), np.ones((3, 3), np.uint8))
        markers[line] = grown[line].astype(np.int32)
    sums = np.bincount(markers.ravel().clip(min=0), weights=interior.ravel(), minlength=int(markers.max()) + 1)
    labels = np.zeros(comp.shape, np.int32)
    areas: list[float] = [0.0] * len(seeds)
    for c in sorted({c for c in seed_core if c}):
        members = [i for i, s in enumerate(seed_core) if s == c]
        basin = markers == c
        if len(members) == 1 or split is None:
            i = members[0]
            labels[basin & (interior > 0.5) & (labels == 0)] = i + 1
            areas[i] = float(sums[c])
            continue
        for i, part in _split_basin(basin, members, split).items():
            labels[part & (interior > 0.5)] = i + 1
            areas[i] = float(interior[part].sum())
    return labels, areas, shared


def _split_basin(basin: np.ndarray, members: list[int], split: np.ndarray) -> dict[int, np.ndarray]:
    """Cut one basin that several numbers share (an open kitchen and a living room).

    The cut follows the thin line drawn between them: each pixel goes to the nearest baseline region of a member.
    """
    ys, xs = np.nonzero(basin)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    box, sub_split = basin[y0:y1, x0:x1], split[y0:y1, x0:x1]
    sub = np.zeros(box.shape, np.int32)
    for i in members:
        sub[(sub_split == i + 1) & box] = i + 1
    if not sub.any():
        return {members[0]: basin}
    source = (sub == 0).astype(np.uint8)
    _, nearest = cv2.distanceTransformWithLabels(source, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    owner = np.concatenate([[0], sub[source == 0]])[nearest]
    out: dict[int, np.ndarray] = {}
    for i in members:
        part = np.zeros(basin.shape, bool)
        part[y0:y1, x0:x1] = box & (owner == i + 1)
        if part.any():
            out[i] = part
    return out


# ----------------------------------------------------------------------------- apartments


def red_outline(rgb: np.ndarray) -> np.ndarray:
    f = rgb.astype(np.int16)
    redness = f[..., 0] - np.maximum(f[..., 1], f[..., 2])
    return redness > RED_MIN * 255


def unit_regions(rgb: np.ndarray) -> tuple[np.ndarray, int]:
    """Regions enclosed by the red dash-dot outline. The dashes are closed by a dilation first."""
    red = red_outline(rgb).astype(np.uint8)
    if red.sum() < 50:
        return np.zeros(red.shape, np.int32), 0
    closed = cv2.morphologyEx(red, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    count, comp = cv2.connectedComponents((closed == 0).astype(np.uint8), connectivity=4)
    border = set(np.unique(np.concatenate([comp[0], comp[-1], comp[:, 0], comp[:, -1]])).tolist())
    out = np.where(np.isin(comp, list(border)), 0, comp).astype(np.int32)
    return out, count


# ----------------------------------------------------------------------------- the plan


def _polygon(labels: np.ndarray, index: int, inv: float) -> tuple[tuple[float, float], ...]:
    mask = (labels == index).astype(np.uint8)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return ()
    c = max(contours, key=cv2.contourArea)
    c = cv2.approxPolyDP(c, 1.0, closed=True)
    return tuple((round(float(p[0][0]) * inv, 1), round(float(p[0][1]) * inv, 1)) for p in c)


def _recover_numbers(
    rgb: np.ndarray, prob: np.ndarray, labels: np.ndarray, factor: float, known: set[str]
) -> list[RoomText]:
    """Read again where the model sees a room that has no number: OCR misses small numbers in cramped rooms.

    Each room-like region without a seed (interior high, at least RECOVER_MIN_M2) is cut out of the input
    image with a margin and read at a larger upscale. A number found inside the region becomes a new seed.
    """
    free = ((prob[..., 0] > 0.6) & (labels == 0)).astype(np.uint8)
    count, comp, stats, _ = cv2.connectedComponentsWithStats(free, connectivity=4)
    min_px = RECOVER_MIN_M2 * CANON_PPM**2
    order = sorted(range(1, count), key=lambda c: -stats[c, cv2.CC_STAT_AREA])
    found: list[RoomText] = []
    h, w = rgb.shape[:2]
    for c in order[:RECOVER_MAX]:
        if stats[c, cv2.CC_STAT_AREA] < min_px:
            break
        x, y, bw, bh = (int(v) for v in stats[c, :4])
        x0, y0 = max(0, int(x / factor) - RECOVER_PAD), max(0, int(y / factor) - RECOVER_PAD)
        x1, y1 = min(w, int((x + bw) / factor) + RECOVER_PAD), min(h, int((y + bh) / factor) + RECOVER_PAD)
        crop = np.ascontiguousarray(rgb[y0:y1, x0:x1])
        lines = [
            ocr.TextLine(text=ln.text, box=tuple((px + x0, py + y0) for px, py in ln.box), score=ln.score)
            for ln in ocr.read_lines(crop, upscale=RECOVER_UPSCALE)
        ]
        for t in room_texts(lines, factor):
            if t.number in known or _seed_label(comp, t.x, t.y, radius=10) != c:
                continue
            known.add(t.number)
            found.append(t)
    return found


def _confidence(
    model: float | None, base: float | None, printed: float | None, shared: int
) -> tuple[float | None, str, str]:
    """The area, its source and its confidence.

    The model area is the answer; the baseline is a second witness. On val sheets a model area within 3% of the
    baseline, on a core no other number shares, was within 2% of the truth for most rooms; within 0.9 to 1.12 of
    the baseline it was within 5%; outside that the model often merged two rooms or lost one.
    """
    measured = model or base
    if printed is not None and measured and abs(printed / measured - 1) < PRINT_AGREE:
        return printed, "printed", "high"
    if model and base:
        ratio = model / base
        if shared == 1 and abs(ratio - 1) <= HIGH_AGREE:
            return model, "model", "high"
        return model, "model", "medium" if MEDIUM_LOW <= ratio <= MEDIUM_HIGH else "low"
    if model:
        return model, "model", "low"
    if base:
        return base, "baseline", "low"
    return None, "none", "none"


def read_plan(  # noqa: C901, PLR0912, PLR0915 - the steps in order
    image: np.ndarray | str, lines: list[TextLine] | None = None, scale: RasterScale | None = None, *,
    use_model: bool = True,
) -> RasterPlan:  # fmt: skip
    """Read the rooms of one raster plan. With no scale, rooms come from OCR only and have no area."""
    rgb = ocr.to_rgb(image)
    height, width = rgb.shape[:2]
    lines = ocr.read_lines(rgb) if lines is None else lines
    gray_full = rgb.mean(axis=2)
    scale = measure_scale(gray_full, lines) if scale is None else scale
    reasons: list[str] = []
    texts = room_texts(lines)
    if not texts:
        reasons.append("no room numbers")
    if scale is None:
        reasons.append("no scale")
    tags = [(m.group(1), line) for line in lines if (m := TAG.match(line.text.strip()))]
    if scale is None:
        rooms = tuple(
            Room(number=t.number, label=t.label, area_m2=None, area_source="none", area_confidence="none",
                 model_area_m2=None, baseline_area_m2=None, printed_area_m2=t.printed_m2, apartment=None,
                 outdoor=is_outdoor_label(t.label), at=(t.x, t.y), polygon=())
            for t in texts
        )  # fmt: skip
        apartments = tuple(Apartment(letter=letter, at=(ln.cx, ln.cy), unit=None) for letter, ln in tags)
        return RasterPlan(width=width, height=height, scale=None, factor=1.0, rooms=rooms, apartments=apartments,
                          texts=len(lines), model_used=False, plan_like=bool(texts), reasons=tuple(reasons))  # fmt: skip
    canon, factor = canonical(rgb, scale.ppm)
    inv = 1.0 / factor
    ctexts = room_texts(lines, factor)
    seeds = [(t.x, t.y) for t in ctexts]
    gray = canon.mean(axis=2)
    text_mask = _text_mask(gray.shape, lines, factor)
    base_labels = baseline_regions(gray, seeds, text_mask)
    base_px = np.bincount(base_labels.ravel(), minlength=len(seeds) + 1)
    prob = predict(canon) if use_model else None
    if prob is not None:
        model_labels, model_px, shared = model_regions(prob, seeds, base_labels)
        extra = _recover_numbers(rgb, prob, model_labels, factor, {t.number for t in ctexts})
        if extra:
            ctexts = [*ctexts, *extra]
            seeds = [(t.x, t.y) for t in ctexts]
            base_labels = baseline_regions(gray, seeds, text_mask)
            base_px = np.bincount(base_labels.ravel(), minlength=len(seeds) + 1)
            model_labels, model_px, shared = model_regions(prob, seeds, base_labels)
    else:
        model_labels, model_px, shared = base_labels, [0.0] * len(seeds), [0] * len(seeds)
    units, _ = unit_regions(rgb)  # the dashes have a fixed size on paper: find them at the input scale
    if factor != 1.0:
        units = cv2.resize(units, (canon.shape[1], canon.shape[0]), interpolation=cv2.INTER_NEAREST)
    unit_px = np.bincount(units.ravel().astype(np.int64))
    unit_letter: dict[int, str] = {}
    apartments: list[Apartment] = []
    for letter, line in tags:
        x, y = round(line.cx * factor), round(line.cy * factor)
        u = int(units[min(max(y, 0), units.shape[0] - 1), min(max(x, 0), units.shape[1] - 1)])
        if u and u not in unit_letter:
            unit_letter[u] = letter
        outline = float(unit_px[u]) / CANON_PPM**2 if u and u < len(unit_px) else None
        unread = None
        if u and prob is not None:
            free = (units == u) & (model_labels == 0) & (prob[..., 0] > 0.6)
            unread = round(float(prob[..., 0][free].sum()) / CANON_PPM**2, 2)
        apartments.append(
            Apartment(letter=letter, at=(line.cx, line.cy), unit=u or None,
                      outline_area_m2=round(outline, 2) if outline else None, unread_area_m2=unread)
        )  # fmt: skip
    grey_fill = gray
    rooms: list[Room] = []
    px2 = CANON_PPM**2
    for i, t in enumerate(ctexts):
        base = float(base_px[i + 1]) / px2 if base_px[i + 1] else None
        model = model_px[i] / px2 if model_px[i] else None
        area, source, level = _confidence(model, base, t.printed_m2, shared[i])
        region = (model_labels == i + 1) if prob is not None else (base_labels == i + 1)
        letters = []
        if region.any():
            ids, n = np.unique(units[region], return_counts=True)
            for uid, k in sorted(zip(ids.tolist(), n.tolist(), strict=True), key=lambda p: -p[1]):
                if uid and k > 0.5 * region.sum() and uid in unit_letter:
                    letters.append(unit_letter[uid])
        fill = float(np.median(grey_fill[region])) if region.any() else 255.0
        outdoor = is_outdoor_label(t.label) or (220 <= fill <= 233 and t.label is None)
        rooms.append(
            Room(
                number=t.number, label=t.label,
                area_m2=round(area, 2) if area else None, area_source=source,  # ty: ignore[invalid-argument-type]
                area_confidence=level,  # ty: ignore[invalid-argument-type]
                model_area_m2=round(model, 3) if model else None, baseline_area_m2=round(base, 3) if base else None,
                printed_area_m2=t.printed_m2, apartment=letters[0] if letters else None, outdoor=outdoor,
                at=(round(t.x * inv, 1), round(t.y * inv, 1)),
                polygon=_polygon(model_labels if prob is not None else base_labels, i + 1, inv),
            )
        )  # fmt: skip
    unread_sheet = None
    if prob is not None:
        free = (model_labels == 0) & (prob[..., 0] > 0.6)
        free_count, free_comp, free_stats, _ = cv2.connectedComponentsWithStats(free.astype(np.uint8), connectivity=4)
        big = [c for c in range(1, free_count) if free_stats[c, cv2.CC_STAT_AREA] >= RECOVER_MIN_M2 * px2]
        unread_sheet = round(float(prob[..., 0][np.isin(free_comp, big)].sum()) / px2, 2) if big else 0.0
    return RasterPlan(width=width, height=height, scale=scale, factor=factor, rooms=tuple(rooms),
                      apartments=tuple(apartments), texts=len(lines), model_used=prob is not None,
                      plan_like=bool(texts), reasons=tuple(reasons), unread_area_m2=unread_sheet)  # fmt: skip
