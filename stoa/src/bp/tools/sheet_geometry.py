r"""Geometry on a large drawing sheet: the scale from dimension lines, and the area of each colour zone.

The printed scale of a sheet does not give pixels per metre: the resolution of the image is not known, and a page
can be a reduced print ("1 inch = 30 feet" on a half-size sheet). The drawing itself is the witness. A dimension is
a text ("130'-0\"", "3600") on a line that ends at two ticks. The length of that line in pixels, divided by the
printed length, is the scale. Several dimensions must agree before the scale is used.

Zones: many plans fill each kind of area with one colour and name the colours in a legend. The area of a colour is
its pixels, with the thin lines inside it (furniture, partitions) closed.
"""

from __future__ import annotations

import colorsys
import re
from typing import TYPE_CHECKING

import cv2
import numpy as np

from bp.contract import Frozen
from bp.tools import sheet_scan, sheet_text

if TYPE_CHECKING:
    from bp.tools.ocr import TextLine
    from bp.tools.sheet_text import Label

DARK = 110  # a pixel of a line: every channel below this
GAP_PX = 3  # a dimension line can have a break this long
MIN_DIMENSION_M = 1.5
AGREE = 0.015  # dimensions agree when their scales lie within this of the median
MIN_WITNESSES = 3
ZONE_STEP = 4  # zones are found on the image shrunk by this factor
ZONE_TOLERANCE = 22  # largest channel difference to the zone colour
ZONE_MIN_SHARE = 0.001  # of the sheet
CLOSE_M = 0.15  # lines thinner than this inside a zone belong to the zone
SOLID_M = 0.5  # a zone is an area, not line work: a part of it survives an erosion by this
SOLID_SHARE = 0.2
MAX_ZONES = 8
FEET = re.compile(r"\d+'-\d+(?: \d+/\d+)?\"")
MILLIMETRES = re.compile(r"^\d{4,6}$")
BAR_LABEL = re.compile(r"^(\d{1,3})\s?(['m]?)$", re.IGNORECASE)
BAR_FIT = 0.02  # each label of a scale bar lies within this share of the bar length from the fitted line
BAR_WEIGHT = 2  # a scale bar with 3 labels on one line counts as two witnesses
FT_M = 0.3048


class Dimension(Frozen):
    text: str
    metres: float
    pixels: int
    ppm: float
    line: tuple[tuple[int, int], tuple[int, int]]  # the two ends of the dimension line


class DimensionScale(Frozen):
    ppm: float  # pixels per metre
    agreeing: int
    read: int
    spread: float  # of the agreeing dimensions, relative
    witnesses: tuple[Dimension, ...]


class Zone(Frozen):
    rgb: tuple[int, int, int]
    colour: str
    legend: str | None  # the text next to the legend swatch of this colour
    area_px: int  # in pixels of the full image, legend swatch excluded
    parts: int
    bbox: tuple[int, int, int, int]


def printed_length_m(text: str) -> float | None:
    """The length that a dimension text prints: feet and inches, or whole millimetres."""
    cleaned = re.sub(r"\s*-\s*", "-", sheet_text.clean(text)).replace("' ", "'").strip()
    feet = FEET.search(cleaned)
    if feet:
        return sheet_text.feet_inches_m(feet.group(0))
    if MILLIMETRES.match(cleaned):
        return int(cleaned) / 1000.0
    return None


def _run(row: np.ndarray, at: int) -> tuple[int, int] | None:
    """The ends of the dark run through index `at`, with breaks up to GAP_PX bridged."""
    if not row[max(0, at - 2) : at + 3].any():
        return None
    ends = []
    for step in (-1, 1):
        last, miss, i = at, 0, at
        while 0 < i < len(row) - 1 and miss <= GAP_PX:
            i += step
            if row[i]:
                last, miss = i, 0
            else:
                miss += 1
        ends.append(last)
    return ends[0], ends[1]


def _ticks(dark: np.ndarray, pos: int, lo: int, hi: int, height: int) -> list[int]:
    """Indexes along a line at row `pos` where a stroke crosses it (a tick or an extension line)."""
    band = dark[max(0, pos - height) : pos + height + 1, lo : hi + 1]
    mid = min(pos, height)
    need = max(2, round(0.3 * height))
    if mid < need or band.shape[0] - mid - 1 < need:
        return []
    above = band[mid - need : mid].all(axis=0)
    below = band[mid + 1 : mid + 1 + need].all(axis=0)
    return [lo + int(i) for i in np.flatnonzero(above & below)]


def _tick_centre(ticks: list[int], at: int) -> int:
    """The middle of the run of tick columns that holds `at`: on a scan a tick is a band 3 to 5 px wide."""
    found = set(ticks)
    lo, hi = at, at
    while lo - 1 in found:
        lo -= 1
    while hi + 1 in found:
        hi += 1
    return (lo + hi) // 2


def _dimension(dark: np.ndarray, line: TextLine, metres: float, *, scan: bool = False) -> Dimension | None:
    x0, y0, x1, y1 = (round(v) for v in line.bbox)
    horizontal = (x1 - x0) >= (y1 - y0)
    image = dark if horizontal else dark.T  # work as if the text were horizontal
    if not horizontal:
        x0, y0, x1, y1 = y0, x0, y1, x1
    height, centre = y1 - y0, (x0 + x1) // 2
    best: tuple[int, int, int, int] | None = None  # length, row, lo, hi
    rows = [*range(y1, min(image.shape[0], y1 + 2 * height)), *range(max(0, y0 - 2 * height), y0)]
    for row in rows:
        ends = _run(image[row], centre)
        if ends and (best is None or ends[1] - ends[0] > best[0]):
            best = (ends[1] - ends[0], row, ends[0], ends[1])
    if best is None:
        return None
    _, row, lo, hi = best
    ticks = _ticks(image, row, lo, hi, height)
    left = max((t for t in ticks if t < centre - height // 2), default=lo)
    right = min((t for t in ticks if t > centre + height // 2), default=hi)
    if scan:  # the inner edge of a blurred tick is 1 to 2 px inside its middle: 0.5% on a line of 400 px
        left = _tick_centre(ticks, left) if left in ticks else left
        right = _tick_centre(ticks, right) if right in ticks else right
    pixels = right - left
    if pixels < 3 * height:
        return None
    ends_xy = ((left, row), (right, row)) if horizontal else ((row, left), (row, right))
    return Dimension(
        text=line.text, metres=round(metres, 4), pixels=pixels, ppm=round(pixels / metres, 3), line=ends_xy
    )


def _moved(line: TextLine, up: sheet_scan.Upright) -> TextLine:
    """The text line in upright pixels: its box keeps its shape and moves with its centre."""
    if up.angle == 0.0:
        return line
    x, y = up.to_upright(line.cx, line.cy)
    dx, dy = x - line.cx, y - line.cy
    return line.model_copy(update={"box": tuple((px + dx, py + dy) for px, py in line.box)})


def _back(found: Dimension, up: sheet_scan.Upright) -> Dimension:
    """The dimension with its ends in the original pixels."""
    if up.angle == 0.0:
        return found
    ends = tuple(tuple(round(v) for v in up.to_original(x, y)) for x, y in found.line)
    return found.model_copy(update={"line": ends})


def scale_bars(lines: list[TextLine]) -> list[Dimension]:
    """Each graphic scale bar: labels on one row ("0", "15'", "30'", "60'") whose positions are linear in the values."""
    marks: list[tuple[TextLine, float, str]] = []
    for line in lines:
        m = BAR_LABEL.match(sheet_text.clean(line.text).strip())
        if m and (m.group(2) or m.group(1) == "0"):
            marks.append((line, float(m.group(1)), m.group(2).lower()))
    bars: list[Dimension] = []
    for unit, to_m in (("'", FT_M), ("m", 1.0)):
        ends = sorted((mk for mk in marks if mk[2] == unit), key=lambda mk: -mk[1])
        for last, top, _ in ends:
            row = [mk for mk in marks if mk[2] in (unit, "") and abs(mk[0].cy - last.cy) < 0.5 * last.height]
            row = [mk for mk in row if 0 <= last.cx - mk[0].cx <= 40 * last.height and mk[1] <= top]
            if len({mk[1] for mk in row}) < 3 or len(row) != len({mk[1] for mk in row}):
                continue
            values = np.array([mk[1] for mk in row])
            xs = np.array([mk[0].cx for mk in row])
            slope, start = np.polyfit(values, xs, 1)
            span = slope * (values.max() - values.min())
            if slope <= 0 or np.abs(xs - (slope * values + start)).max() > BAR_FIT * span:
                continue
            y = round(last.cy)
            metres = float(values.max() - values.min()) * to_m
            text = "scale bar " + " ".join(mk[0].text for mk in sorted(row, key=lambda mk: mk[1]))
            if any(b.text == text and b.line[0][1] == y for b in bars):
                continue
            bars.append(Dimension(
                text=text, metres=round(metres, 4), pixels=round(span), ppm=round(float(span) / metres, 3),
                line=((round(float(xs.min())), y), (round(float(xs.max())), y)),
            ))  # fmt: skip
            break  # the longest bar of this unit
    return bars


def dimension_scale(rgb: np.ndarray, lines: list[TextLine]) -> DimensionScale | None:
    """Pixels per metre from the dimension lines and the scale bar of the sheet.

    None when fewer than 3 witnesses agree. A scale bar counts as two: its labels agree with each other already.
    """
    # A scan is turned and has grey thin lines: the lines are read on the upright ink, and their ends go back to the
    # original pixels. The length of a line does not change when the image turns.
    up = sheet_scan.upright(rgb, DARK)
    bars = scale_bars(lines)
    read: list[Dimension] = []
    for line in lines:
        metres = printed_length_m(line.text)
        if metres is None or metres < MIN_DIMENSION_M:
            continue
        found = _dimension(up.dark, _moved(line, up), metres, scan=up.scan)
        if found is not None:
            read.append(_back(found, up))
    best: list[Dimension] = []
    weight = 0
    for candidate in [*read, *bars]:
        group = [d for d in [*read, *bars] if abs(d.ppm / candidate.ppm - 1) <= AGREE]
        total = sum(BAR_WEIGHT if d in bars else 1 for d in group)
        if total > weight:
            best, weight = group, total
    if weight < MIN_WITNESSES:
        return None
    # a dimension line ends at two ticks, so it is more exact than the label positions of a bar
    lines_only = [d for d in best if d not in bars] or best
    values = sorted(d.ppm for d in lines_only)
    ppm = values[(len(values) - 1) // 2]
    values = sorted(d.ppm for d in best)
    return DimensionScale(
        ppm=ppm, agreeing=weight, read=len(read) + len(bars), spread=round(values[-1] / values[0] - 1, 4),
        witnesses=tuple(sorted(best, key=lambda d: -d.pixels)[:8]),
    )  # fmt: skip


def colour_name(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    high, low = max(rgb), min(rgb)
    if high - low < 25:
        return "grey" if high < 235 else "white"
    hue = 360 * colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)[0]
    for limit, name in (
        (20, "red"),
        (45, "orange"),
        (70, "yellow"),
        (165, "green"),
        (200, "cyan"),
        (260, "blue"),
        (330, "purple"),
    ):
        if hue < limit:
            return name
    return "red"


def _legend_text(labels: list[Label], box: tuple[int, int, int, int]) -> str | None:
    """The label right of a legend swatch, on its row."""
    x0, y0, x1, y1 = box
    width = x1 - x0
    right = [
        lb for lb in labels
        if y0 - 0.2 * (y1 - y0) <= lb.at[1] <= y1 + 0.2 * (y1 - y0) and x1 <= lb.bbox[0] <= x1 + 3 * width
    ]  # fmt: skip
    return min(right, key=lambda lb: lb.bbox[0]).text if right else None


def colour_zones(rgb: np.ndarray, labels: list[Label], ppm: float) -> list[Zone]:
    """Each fill colour that covers an area of the drawing, largest first. Line work in grey is not a zone."""
    step = ZONE_STEP
    small = cv2.resize(rgb, (rgb.shape[1] // step, rgb.shape[0] // step), interpolation=cv2.INTER_AREA).astype(np.int16)
    left = (small.max(axis=2) > DARK) & (small.min(axis=2) <= 235)
    scale = ppm / step
    close = max(3, round(CLOSE_M * scale) | 1)
    solid = max(3, round(SOLID_M * scale) | 1)
    zones: list[Zone] = []
    for _ in range(MAX_ZONES * 2):
        if left.sum() < ZONE_MIN_SHARE * left.size or len(zones) >= MAX_ZONES:
            break
        bins = small[left].astype(np.int64) // 12
        keys, counts = np.unique(bins[:, 0] * 10000 + bins[:, 1] * 100 + bins[:, 2], return_counts=True)
        key = int(keys[counts.argmax()])
        seed = np.array([key // 10000, key // 100 % 100, key % 100]) * 12 + 6
        near = np.abs(small - seed).max(axis=2) <= ZONE_TOLERANCE
        colour = tuple(int(v) for v in small[near & left].mean(axis=0).round())
        near = (np.abs(small - np.array(colour)).max(axis=2) <= ZONE_TOLERANCE) & left
        left &= ~near
        mask = cv2.morphologyEx(near.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((close, close), np.uint8))
        if cv2.erode(mask, np.ones((solid, solid), np.uint8)).sum() < SOLID_SHARE * mask.sum():
            continue  # mostly thin strokes: walls, hatching or the edge of another colour, not an area
        count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        parts = [stats[i] for i in range(1, count) if stats[i][4] >= 0.5 * solid * solid]
        legend, kept, area = None, [], 0
        for x, y, w, h, pixels in parts:
            box = (int(x) * step, int(y) * step, int(x + w) * step, int(y + h) * step)
            text = _legend_text(labels, box) if pixels >= 0.9 * w * h and legend is None else None
            if text is not None and len(parts) > 1:
                legend = text  # a full rectangle with a text on its right: the legend swatch, not floor area
                continue
            kept.append(box)
            area += int(pixels)
        if not kept or area < ZONE_MIN_SHARE * left.size:
            continue
        bbox = (min(b[0] for b in kept), min(b[1] for b in kept), max(b[2] for b in kept), max(b[3] for b in kept))
        zones.append(Zone(rgb=colour, colour=colour_name(colour), legend=legend, area_px=area * step * step,  # ty: ignore[invalid-argument-type]
                          parts=len(kept), bbox=bbox))  # fmt: skip
    return sorted(zones, key=lambda z: -z.area_px)
