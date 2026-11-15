"""Door swings and room areas on a large line drawing, from the pixels and a known scale.

A door is drawn as a leaf and a swing: a line from the hinge and a circular arc with the leaf length as its
radius. Straight lines are removed, so each swing stays as its own curved piece, and a circle is fitted to it.
A room is the white area around its label, inside the dark lines, with each door opening closed at the swing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from collections.abc import Iterator

DARK = 140  # grey level under which a pixel is ink
LEAF_M = (0.58, 1.40)  # the radius of a door swing: a toilet stall door to a wide single leaf
STRAIGHT_M = 0.40  # a run of ink longer than this in x or y is a straight line, not a swing
FIT_PX = 2.5  # the distance from the circle that still counts as on it
SWEEP_BIN = 5  # degrees
MIN_SWEEP = 75.0
MIN_SWEEP_WIDE = 55.0  # a wide leaf can be drawn half open; a chair back is a short arc with a small radius
WIDE_M = 0.85
MAX_SWEEP = 200.0
PAST_ARC = 70.0  # degrees of ink on the circle outside the swing: more is a full circle or a rounded box
JAMB = 0.15  # of the leaf length
SNAP_DEG = 15.0  # a closed leaf this close to an axis is also closed on the axis
WALL_LINE_PX = 2  # half the width of a wall line on a 300 dpi sheet
GAP_M = 2.0  # the longest gap in a wall that is an opening: a double door
WALL_M = 0.6  # the thickest wall
MIN_WALL_M = 1.2  # a thick mark shorter than this is text or a symbol, not a wall
CLOSE_M = 0.9  # a notch in a room narrower than this is furniture at the wall, not the wall
NECK_M = 0.4  # the fill does not pass a gap narrower than this
MAX_ROOM_SHARE = 0.25  # of the sheet: a larger region leaked out of the room
RENDER_DPI = (100, 150, 200, 300, 400, 600)  # the resolutions that a sheet is exported at
COMMON_LEAF_M = (0.84, 0.96)  # the median door leaf of a building: 3 ft, or 900 mm
MIN_DOORS = 6  # fewer swings do not prove a scale
SANE_LEAF_M = (0.78, 1.02)  # a median leaf outside this says that a measured scale is wrong
OUTLINE_PX = 4.0  # corners of a room outline closer than this to the line between their neighbours go


@dataclass(frozen=True)
class Swing:
    centre: tuple[float, float]  # the hinge, in px
    radius_px: float
    sweep: float  # degrees
    ends: tuple[float, float]  # the angles of the two ends of the arc, degrees
    leaf_end: int  # the index in `ends` of the end that the leaf goes to


def _fit(points: np.ndarray) -> tuple[np.ndarray, float]:
    sol, *_ = np.linalg.lstsq(np.c_[2 * points, np.ones(len(points))], (points**2).sum(1), rcond=None)
    centre = sol[:2]
    return centre, math.sqrt(max(sol[2] + centre @ centre, 0.0))


def _sweep(points: np.ndarray, centre: np.ndarray) -> tuple[float, tuple[float, float]]:
    """(sweep in degrees, the angles of the two ends) of the points around the centre."""
    angles = np.degrees(np.arctan2(points[:, 1] - centre[1], points[:, 0] - centre[0])) % 360
    bins = 360 // SWEEP_BIN
    filled = np.zeros(bins, bool)
    filled[(angles // SWEEP_BIN).astype(int) % bins] = True
    gap = run = end = 0
    for i, on in enumerate(np.r_[filled, filled]):
        run = 0 if on else run + 1
        if run > gap:
            gap, end = run, i
    gap = min(gap, bins)
    start = ((end + 1) * SWEEP_BIN) % 360  # the first bin after the gap
    turned = (angles - start) % 360
    return 360.0 - gap * SWEEP_BIN, ((start + turned.min()) % 360, (start + turned.max()) % 360)


def _circles(
    points: np.ndarray, lo: float, hi: float, rng: np.random.Generator
) -> Iterator[tuple[np.ndarray, float, np.ndarray]]:
    """Up to 3 circles through the points of one piece (RANSAC): two leaves of a double door are one piece."""
    for _ in range(3):
        if len(points) < 0.5 * lo:
            return
        pick = rng.integers(0, len(points), (300, 3))
        a, b, c = points[pick[:, 0]], points[pick[:, 1]], points[pick[:, 2]]
        d = 2 * (a[:, 0] * (b[:, 1] - c[:, 1]) + b[:, 0] * (c[:, 1] - a[:, 1]) + c[:, 0] * (a[:, 1] - b[:, 1]))
        ok = np.abs(d) > 1e-6
        a, b, c, d = a[ok], b[ok], c[ok], d[ok]
        sa, sb, sc = (a**2).sum(1), (b**2).sum(1), (c**2).sum(1)
        ux = (sa * (b[:, 1] - c[:, 1]) + sb * (c[:, 1] - a[:, 1]) + sc * (a[:, 1] - b[:, 1])) / d
        uy = (sa * (c[:, 0] - b[:, 0]) + sb * (a[:, 0] - c[:, 0]) + sc * (b[:, 0] - a[:, 0])) / d
        r = np.hypot(a[:, 0] - ux, a[:, 1] - uy)
        keep = (r >= lo) & (r <= hi)
        if not keep.any():
            return
        ux, uy, r = ux[keep], uy[keep], r[keep]
        sample = points if len(points) <= 800 else points[rng.choice(len(points), 800, replace=False)]
        off = np.abs(np.hypot(sample[:, 0][None] - ux[:, None], sample[:, 1][None] - uy[:, None]) - r[:, None])
        best = int((off < FIT_PX).sum(1).argmax())
        on = np.abs(np.hypot(points[:, 0] - ux[best], points[:, 1] - uy[best]) - r[best]) < FIT_PX
        if on.sum() < 0.5 * lo:
            return
        centre, radius = _fit(points[on])
        distance = np.abs(np.hypot(*(points - centre).T) - radius)
        if lo <= radius <= hi:
            yield centre, radius, points[distance < FIT_PX]
        points = points[distance > 3 * FIT_PX]


def _ink_on_line(dark: np.ndarray, centre: np.ndarray, radius: float, angle: float) -> float:
    """The share of a radius (from the hinge to the arc, at one angle) that has ink."""
    t = np.linspace(0.2, 0.85, 24) * radius
    xs = np.clip((centre[0] + t * math.cos(math.radians(angle))).astype(int), 2, dark.shape[1] - 3)
    ys = np.clip((centre[1] + t * math.sin(math.radians(angle))).astype(int), 2, dark.shape[0] - 3)
    return float(np.mean([dark[y - 2 : y + 3, x - 2 : x + 3].any() for x, y in zip(xs, ys, strict=True)]))


def door_swings(gray: np.ndarray, px_per_metre: float) -> list[Swing]:
    """Each door leaf of the drawing that is drawn with a swing arc."""
    dark = (gray < DARK).astype(np.uint8)
    run = max(int(STRAIGHT_M * px_per_metre), 12)
    straight = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((1, run), np.uint8))
    straight = np.maximum(straight, cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((run, 1), np.uint8)))
    curved = np.where(cv2.dilate(straight, np.ones((3, 3), np.uint8)) > 0, 0, dark).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(curved, connectivity=8)
    lo, hi = LEAF_M[0] * px_per_metre, LEAF_M[1] * px_per_metre
    rng = np.random.default_rng(7)
    ring = np.radians(np.arange(0, 360, 4))
    out: list[Swing] = []
    for i in range(1, count):
        x, y, w, h, area = stats[i]
        if max(w, h) < 0.9 * lo or max(w, h) > 4.5 * hi or area < lo or area > 40 * hi:
            continue
        ys, xs = np.nonzero(labels[y : y + h, x : x + w] == i)
        points = np.c_[xs + x, ys + y].astype(float)
        for centre, radius, on in _circles(points, lo, hi, rng):
            sweep, ends = _sweep(on, centre)
            wide = radius >= WIDE_M * px_per_metre
            if not (MIN_SWEEP_WIDE if wide else MIN_SWEEP) <= sweep <= MAX_SWEEP:
                continue
            if len(on) < 0.8 * radius * math.radians(sweep):
                continue
            cx = np.clip((centre[0] + radius * np.cos(ring)).astype(int), 1, dark.shape[1] - 2)
            cy = np.clip((centre[1] + radius * np.sin(ring)).astype(int), 1, dark.shape[0] - 2)
            inked = 360 * np.mean([dark[b - 1 : b + 2, a - 1 : a + 2].any() for a, b in zip(cx, cy, strict=True)])
            if inked > sweep + PAST_ARC:
                continue
            leaf = [_ink_on_line(dark, centre, radius, angle) for angle in ends]
            if max(leaf) < 0.75:
                continue
            same = any(
                math.dist(centre, s.centre) < 0.15 * px_per_metre and abs(radius - s.radius_px) < 0.12 * px_per_metre
                for s in out
            )
            if not same:
                out.append(Swing((float(centre[0]), float(centre[1])), radius, sweep, ends, int(np.argmax(leaf))))
    return out


@dataclass(frozen=True)
class Room:
    area_px: float
    bbox: tuple[int, int, int, int]
    doors: int  # door openings that were closed on the edge of the room
    mask: np.ndarray  # the room in the bbox, 1 inside

    def outline(self) -> list[tuple[int, int]]:
        """The corners of the room in page pixels."""
        contours, _ = cv2.findContours(self.mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return []
        largest = max(contours, key=cv2.contourArea)
        corners = cv2.approxPolyDP(largest, OUTLINE_PX, closed=True)
        return [(int(x) + self.bbox[0], int(y) + self.bbox[1]) for x, y in corners.reshape(-1, 2)]

    def perimeter_px(self) -> float:
        """The length of the outline: the walls of the room, with the door openings."""
        outline = np.array(self.outline(), np.int32).reshape(-1, 1, 2)
        return float(cv2.arcLength(outline, closed=True)) if len(outline) > 2 else 0.0

    def holds(self, x: float, y: float) -> bool:
        col, row = round(x) - self.bbox[0], round(y) - self.bbox[1]
        return 0 <= row < self.mask.shape[0] and 0 <= col < self.mask.shape[1] and bool(self.mask[row, col])

    def doors_on_edge(self, swings: list[Swing]) -> list[Swing]:
        """The swings with their hinge on the outline of the room: the doors of this room."""
        # the mask fills its box, so the outline is on the border of the array: erode with a 0 border
        inner = cv2.erode(self.mask, np.ones((3, 3), np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0)
        edge = self.mask - inner
        out = []
        for swing in swings:
            reach = max(int(0.35 * swing.radius_px), 4)
            col, row = round(swing.centre[0]) - self.bbox[0], round(swing.centre[1]) - self.bbox[1]
            near = edge[max(row - reach, 0) : max(row + reach + 1, 0), max(col - reach, 0) : max(col + reach + 1, 0)]
            if near.size and near.any():
                out.append(swing)
        return out


def room_barriers(gray: np.ndarray, swings: list[Swing], dark: int = DARK) -> np.ndarray:
    """The ink that bounds rooms: the drawing with each swing and leaf removed and each door opening closed."""
    barrier = (gray < dark).astype(np.uint8)
    closing: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for swing in swings:
        centre = (round(swing.centre[0]), round(swing.centre[1]))
        radius = round(swing.radius_px)
        first, last = swing.ends
        span = (last - first) % 360
        cv2.ellipse(barrier, centre, (radius, radius), 0, first - 4, first + span + 4, 0, 7)
        for index, angle in enumerate(swing.ends):
            ux, uy = math.cos(math.radians(angle)), math.sin(math.radians(angle))

            def at(share: float, ux: float = ux, uy: float = uy, swing: Swing = swing) -> tuple[int, int]:
                return (round(swing.centre[0] + share * swing.radius_px * ux),
                        round(swing.centre[1] + share * swing.radius_px * uy))  # fmt: skip

            if index == swing.leaf_end and swing.sweep < 150:
                cv2.line(barrier, at(0.12), at(1.0), 0, 9)  # the open leaf stands in the room
            else:
                closing.append((at(-JAMB), at(1 + JAMB)))  # past both jambs, into the wall
                # The arc ends a little before the wall, so the angle of the closed leaf can be some degrees off
                # and the line then misses the jamb. Most walls are on an axis: close on the axis too.
                square = 90.0 * round(angle / 90.0)
                if 1.0 < abs(angle - square) <= SNAP_DEG:
                    sx, sy = math.cos(math.radians(square)), math.sin(math.radians(square))
                    closing.append((at(-JAMB, sx, sy), at(1 + JAMB, sx, sy)))
    for a, b in closing:
        cv2.line(barrier, a, b, 1, 5)
    return barrier


def wall_barriers(barrier: np.ndarray, px_per_metre: float) -> np.ndarray:
    """The walls only: the thick lines, with each gap in a wall closed.

    Furniture, stair treads and hatches are thin lines, and they split a room. A window is thin lines too, and a
    cased opening has no line. So the thin lines go, and a gap between two wall ends on one line is closed when
    the gap is not longer than a double door and not thicker than a wall.
    """
    thick = cv2.morphologyEx(barrier, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    # bold text is thick too, and a bridge from a letter to a wall would split the room at its own label
    count, labels, stats, _ = cv2.connectedComponentsWithStats(thick, connectivity=8)
    long = np.zeros(count, np.uint8)
    long[1:] = np.maximum(stats[1:, cv2.CC_STAT_WIDTH], stats[1:, cv2.CC_STAT_HEIGHT]) >= MIN_WALL_M * px_per_metre
    thick = long[np.asarray(labels, np.intp)]
    gap = max(int(GAP_M * px_per_metre), 3)
    wall = max(int(WALL_M * px_per_metre), 4)
    out = thick.copy()
    for shape, across in (((1, gap), cv2.CC_STAT_HEIGHT), ((gap, 1), cv2.CC_STAT_WIDTH)):
        closed = cv2.morphologyEx(thick, cv2.MORPH_CLOSE, np.ones(shape, np.uint8))
        bridge = np.where(thick > 0, 0, closed).astype(np.uint8)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(bridge, connectivity=4)
        keep = np.zeros(count, np.uint8)
        keep[1:] = stats[1:, across] <= wall
        out |= keep[np.asarray(labels, np.intp)]
    return out


def room_at(barrier: np.ndarray, label_box: tuple[int, int, int, int], px_per_metre: float) -> Room | None:
    """The room around a label: the white area that the barriers bound, with furniture and text filled in."""
    height, width = barrier.shape
    x0, y0, x1, y1 = (int(v) for v in label_box)
    free = (barrier == 0).astype(np.uint8)
    free[max(y0 - 2, 0) : y1 + 3, max(x0 - 2, 0) : x1 + 3] = 1  # the label is not a wall
    seed = ((x0 + x1) // 2, (y0 + y1) // 2)
    mask = np.zeros((height + 2, width + 2), np.uint8)
    _, _, _, box = cv2.floodFill(free, mask, seed, 2, flags=4 | cv2.FLOODFILL_MASK_ONLY | (1 << 8))
    bx, by, bw, bh = box
    if bw * bh > MAX_ROOM_SHARE * width * height or bx <= 1 or by <= 1 or bx + bw >= width - 1 or by + bh >= height - 1:
        return None
    pad = int(CLOSE_M * px_per_metre) + 2
    region = np.zeros((bh + 2 * pad, bw + 2 * pad), np.uint8)
    region[pad : pad + bh, pad : pad + bw] = mask[by + 1 : by + 1 + bh, bx + 1 : bx + 1 + bw]
    filled = _finish(region, pad)
    return Room(float(filled.sum()), (bx, by, bx + bw, by + bh), 0, filled[pad : pad + bh, pad : pad + bw])


def _finish(region: np.ndarray, pad: int) -> np.ndarray:
    """Close the notches of furniture, fill the holes and go to the face of the wall."""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (pad - 2, pad - 2))
    region = cv2.morphologyEx(region, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    filled = np.zeros_like(region)
    cv2.drawContours(filled, contours, -1, 1, cv2.FILLED)
    # the area of a room goes to the face of the wall, which is the middle of the wall line, not its inner edge
    return cv2.dilate(filled, np.ones((2 * WALL_LINE_PX + 1, 2 * WALL_LINE_PX + 1), np.uint8))


def rooms_at(
    barrier: np.ndarray, boxes: list[tuple[int, int, int, int]], px_per_metre: float
) -> list[tuple[Room | None, int]]:
    """For each label box: (the room around it or None, the number of the region), in one pass over the sheet.

    Two boxes with the same region number are in the same white region. The caller decides what that means:
    two names in one region are two rooms with no wall between them.
    """
    height, width = barrier.shape
    free = (barrier == 0).astype(np.uint8)
    for x0, y0, x1, y1 in boxes:
        free[max(y0 - 2, 0) : y1 + 3, max(x0 - 2, 0) : x1 + 3] = 1  # a label is not a wall
    # The fill does not pass a gap narrower than NECK_M: the cavity of a wall that is drawn with two lines, or a
    # small gap between a closed door and its jamb. So it runs on the free space with its edge taken off.
    neck = 2 * max(int(NECK_M * px_per_metre / 2), 1) + 1
    kernel = np.ones((neck, neck), np.uint8)
    core = cv2.erode(free, kernel)
    _, labels, stats, _ = cv2.connectedComponentsWithStats(core, connectivity=4)
    pad = int(CLOSE_M * px_per_metre) + 2
    made: dict[int, Room | None] = {}
    out: list[tuple[Room | None, int]] = []
    for index, (x0, y0, x1, y1) in enumerate(boxes):
        row, col = min((y0 + y1) // 2, height - 1), min((x0 + x1) // 2, width - 1)
        region = int(labels[row, col])
        if region == 0:  # the label is in a place narrower than the neck: no room, and no region to share
            out.append((None, -1 - index))
            continue
        if region not in made:
            bx, by, bw, bh = (int(v) for v in stats[region, :4])
            bx, by = max(bx - neck, 0), max(by - neck, 0)
            bw, bh = min(bw + 2 * neck, width - bx), min(bh + 2 * neck, height - by)
            leaked = bw * bh > MAX_ROOM_SHARE * width * height or bx <= 1 or by <= 1
            leaked = leaked or bx + bw >= width - 1 or by + bh >= height - 1
            if leaked:
                made[region] = None
            else:
                whole = cv2.dilate((labels[by : by + bh, bx : bx + bw] == region).astype(np.uint8), kernel)
                grown = np.zeros((bh + 2 * pad, bw + 2 * pad), np.uint8)
                grown[pad : pad + bh, pad : pad + bw] = whole & free[by : by + bh, bx : bx + bw]
                filled = _finish(grown, pad)
                made[region] = Room(
                    float(filled.sum()), (bx, by, bx + bw, by + bh), 0, filled[pad : pad + bh, pad : pad + bw]
                )
        out.append((made[region], region))
    return out


def scale_from_detected(seen: list[Swing], ratio: int) -> tuple[float, list[Swing]] | None:
    """As `scale_from_doors`, with the door leaves of the trained detector. Their size in pixels is fixed.

    The arc finder needs clean lines, so on a scan it finds no doors and cannot confirm a resolution. The detector
    reads scans. At the right resolution most of its leaves have a door size and their median is a common door.
    """
    best: tuple[float, list[Swing]] | None = None
    for dpi in RENDER_DPI:
        ppm = dpi / 0.0254 / ratio
        doors = [s for s in seen if LEAF_M[0] <= s.radius_px / ppm <= LEAF_M[1]]
        if len(doors) < MIN_DOORS or (best is not None and len(doors) <= len(best[1])):
            continue
        median = float(np.median([s.radius_px for s in doors])) / ppm
        if COMMON_LEAF_M[0] <= median <= COMMON_LEAF_M[1]:
            best = (ppm, doors)
    return best


def doors_fit(swings: list[Swing], px_per_metre: float) -> bool:
    """False when the sheet has enough doors and their median leaf is not a door at this scale: the scale is wrong."""
    if len(swings) < MIN_DOORS:
        return True
    median = float(np.median([s.radius_px for s in swings])) / px_per_metre
    return SANE_LEAF_M[0] <= median <= SANE_LEAF_M[1]


def scale_from_doors(gray: np.ndarray, ratio: int) -> tuple[float, list[Swing]] | None:
    """(px per metre, the door swings) from the printed ratio 1:N, when the doors confirm one resolution.

    A printed ratio gives px per metre only with the resolution of the image, and a PNG does not record it. So each
    common resolution is tried. At the right one, the door finder sees many swings and their median leaf is a
    common door. At a wrong one, the same arcs are too small or too large for a door.
    """
    best: tuple[float, list[Swing]] | None = None
    for dpi in RENDER_DPI:
        ppm = dpi / 0.0254 / ratio
        swings = door_swings(gray, ppm)
        if len(swings) < MIN_DOORS or (best is not None and len(swings) <= len(best[1])):
            continue
        median = float(np.median([s.radius_px for s in swings])) / ppm
        if COMMON_LEAF_M[0] <= median <= COMMON_LEAF_M[1]:
            best = (ppm, swings)
    return best
