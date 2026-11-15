"""Sheets from the US Army Corps of Engineers standard designs: the held-out part of the `sheets` suite.

The PDFs are in `data/external/sheets/usace/` (not in git; `urls.txt` there has the addresses). They are Revit
exports: the walls, the door swings and the text are vectors, so three kinds of key are exact.

- `printed_area`, `printed_area_sum`, `label_count`, `scale`, `tag_count`: read from the text, as in `build_suite`.
- `room_area`: the area of one room on a render where every "NNN SF" text is removed. The key is the removed
  value. Only on sheets whose areas are measured (most values are not a multiple of 10: a programme area is).
- `door_leaves`: the number of door swing arcs. Each arc is a polyline on one circle with the radius of a door.

Facility types in `LOCK` are the held-out partition. Do not look at their results per item, and do not tune on them.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pymupdf

from bp.contract import CountKey, LookupKey, MeasureKey

Question = tuple[str, str, object, str]
LOCK = {"ortc", "yc", "temf", "cif"}
ORTC_LOCK_FROM = 88
SKIP = {"tdafw", "trw"}  # the same sheets as `tda`
MIN_SIDE_IN = 22
AREA = re.compile(r"([\d,]{2,7}) ?SF")
NAME = re.compile(r"[A-Z][A-Z0-9 .,'&/()\-]{1,40}")
SCALE = re.compile(r"(\d+(?:/\d+)?)\" ?= ?1'-0\"|1\" ?= ?(\d+)'(?:-0\")?")
PLAN = re.compile(r"FLOOR PLAN")
AREA_TOLERANCE = 0.05
ROOMS_PER_SHEET = 6
LEAF_DPI = 200
REPEATS_PER_SHEET = 3
Line = tuple[float, float, float, float, str]  # x0, y0, x1, y1, text


def text_lines(page: pymupdf.Page) -> list[Line]:
    out: list[Line] = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = " ".join("".join(s["text"] for s in line["spans"]).split())
            if text and abs(line["dir"][0]) > 0.99:
                out.append((*line["bbox"], text))
    return out


def room_areas(lines: list[Line]) -> list[tuple[str, int, Line]]:
    """(room name, printed area, the line of the area) for each "NNN SF" with a name above it."""
    out: list[tuple[str, int, Line]] = []
    for area in lines:
        m = AREA.fullmatch(area[4])
        if not m:
            continue
        cx, top, h = (area[0] + area[2]) / 2, area[1], area[3] - area[1]
        parts: list[str] = []
        reach = 2.5 * h
        while len(parts) < 4:
            above = [
                ln for ln in lines
                if NAME.fullmatch(ln[4]) and not AREA.fullmatch(ln[4])
                and abs((ln[0] + ln[2]) / 2 - cx) < max(2 * h, 0.25 * (ln[2] - ln[0]))
                and -0.4 * h < top - ln[3] < reach
            ]  # fmt: skip
            if not above:
                break
            nearest = max(above, key=lambda ln: ln[3])
            parts.insert(0, nearest[4])
            top, reach = nearest[1], 0.6 * (nearest[3] - nearest[1])
        name = " ".join(parts)
        if name and "TYPICAL" not in name and name not in {"UP", "DN", "DOWN"}:
            out.append((name, int(m.group(1).replace(",", "")), area))
    return out


def feet_per_inch(page: pymupdf.Page) -> tuple[str, float] | None:
    """The one scale of the sheet: its text and the feet of building per inch of paper."""
    found: dict[float, str] = {}
    for m in SCALE.finditer(" ".join(page.get_text("text").split())):
        if m.group(1):
            top, _, bottom = m.group(1).partition("/")
            found.setdefault(float(bottom or 1) / float(top), f'{m.group(1)}" = 1\'-0"')
        else:
            found.setdefault(float(m.group(2)), f'1" = {m.group(2)}\'-0"')
    if len(found) != 1:
        return None
    value, text = next(iter(found.items()))
    return text, value


def _segments(drawings: list[dict]) -> np.ndarray:
    """Every straight segment of the page as (x0, y0, x1, y1)."""
    rows: list[tuple[float, float, float, float]] = []
    for drawing in drawings:
        for item in drawing["items"]:
            if item[0] == "l":
                rows.append((*item[1], *item[2]))
            elif item[0] in ("re", "qu"):
                q = item[1].quad if item[0] == "re" else item[1]
                corners = [q.ul, q.ur, q.lr, q.ll]
                rows.extend((*corners[i], *corners[(i + 1) % 4]) for i in range(4))
    return np.array(rows) if rows else np.zeros((0, 4))


def _dark_line(dark: np.ndarray, a: np.ndarray, b: np.ndarray) -> bool:
    """True when the render has a line from a to b (the leaf, however the file draws it)."""
    t = np.linspace(0.2, 0.85, 24)[:, None]
    xy = (a + t * (b - a)).astype(int)
    hits = 0
    for x, y in xy:
        hits += bool(dark[max(y - 2, 0) : y + 3, max(x - 2, 0) : x + 3].any())
    return hits >= 18


# The door key is read from vector arcs with a leaf test: it can be 1 leaf off itself on a sheet with 50 doors.
DOOR_TOLERANCE = 0.03


def door_arcs(page: pymupdf.Page, ft_per_in: float) -> list[tuple[float, float]]:
    """The hinge point of each door swing."""
    return [(s[0], s[1]) for s in door_swings(page, ft_per_in)]


Swing = tuple[float, float, float, float, float, float, float, int]


def door_swings(page: pymupdf.Page, ft_per_in: float) -> list[Swing]:
    """Each door swing in page points: (hinge x, hinge y, radius, arc end 0 x, y, arc end 1 x, y, the leaf end).

    The leaf end is the arc end (0 or 1) that the open leaf is drawn to. The other end is where the closed leaf is.

    A swing is a polyline on one circle with a radius of 1.9 to 4.6 ft, with a leaf: a straight segment from the
    centre that is about as long as the radius. A rounded corner of a counter has no leaf, and a chair back is
    short (40 to 60 degrees).
    """
    pt_ft = 72 / ft_per_in
    drawings = page.get_drawings()
    segments = _segments(drawings)
    zoom = LEAF_DPI / 72
    pix = page.get_pixmap(dpi=LEAF_DPI, colorspace=pymupdf.csGRAY, alpha=False)
    dark = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width) < 140
    out: list[Swing] = []
    for drawing in drawings:
        runs: list[np.ndarray] = []
        run: list[tuple[float, float]] = []
        for item in [*drawing["items"], ("end",)]:
            joined = item[0] == "l" and run and math.dist(run[-1], item[1]) < 0.05
            if not joined:
                if len(run) >= 6:
                    runs.append(np.array(run))
                run = [tuple(item[1])] if item[0] == "l" else []
            if item[0] == "l":
                run.append(tuple(item[2]))
        for points in runs:
            # the leaf can be in the same polyline: keep the longest part with segments of the same short length
            step = np.hypot(*np.diff(points, axis=0).T)
            short = step < 2.5 * np.median(step)
            best, start = (0, 0), 0
            for i, ok in enumerate([*short, False]):
                if not ok:
                    if i - start > best[1] - best[0]:
                        best = (start, i)
                    start = i + 1
            p = points[best[0] : best[1] + 1]
            if len(p) < 6:
                continue
            sol, *_ = np.linalg.lstsq(np.c_[2 * p, np.ones(len(p))], (p**2).sum(1), rcond=None)
            centre = sol[:2]
            radius = math.sqrt(max(sol[2] + centre @ centre, 0))
            feet = radius / pt_ft
            if not 1.9 <= feet <= 4.6 or np.abs(np.hypot(*(p - centre).T) - radius).max() > 0.03 * radius:
                continue
            angle = np.unwrap(np.arctan2(p[:, 1] - centre[1], p[:, 0] - centre[0]))
            sweep = abs(angle[-1] - angle[0]) * 180 / math.pi
            if not ((feet >= 2.4 and 55 <= sweep <= 185) or (feet < 2.4 and 75 <= sweep <= 185)):
                continue
            # the leaf: one end at the hinge, the other end on the circle
            d0 = np.hypot(segments[:, 0] - centre[0], segments[:, 1] - centre[1])
            d1 = np.hypot(segments[:, 2] - centre[0], segments[:, 3] - centre[1])
            leaf = (np.minimum(d0, d1) < 0.25 * radius) & (np.abs(np.maximum(d0, d1) - radius) < 0.25 * radius)
            ends = [p[0], p[-1]]
            lines = [_dark_line(dark, centre * zoom, np.array(end) * zoom) for end in ends]
            duplicate = any(math.dist(centre, o[:2]) < 0.1 * pt_ft for o in out)
            if (leaf.any() or any(lines)) and not duplicate:
                out.append((float(centre[0]), float(centre[1]), float(radius), *map(float, p[0]), *map(float, p[-1]),
                            int(lines[1] and not lines[0])))  # fmt: skip
    return out


def pick(name: str, rows: list[tuple[str, int]], limit: int) -> list[tuple[str, int]]:
    return sorted(rows, key=lambda r: hashlib.sha256(f"{name}:{r[0]}".encode()).hexdigest())[:limit]


def questions(name: str, page: pymupdf.Page) -> tuple[list[Question], list[Question], list[Line]]:
    """(questions on the sheet as printed, questions on the sheet with the areas removed, the area lines)."""
    lines = text_lines(page)
    text = " ".join(page.get_text("text").split())
    rooms = room_areas(lines)
    by_name: dict[str, list[int]] = defaultdict(list)
    for room, value, _ in rooms:
        by_name[room].append(value)
    printed: list[Question] = []
    hidden: list[Question] = []

    single = [(room, values[0]) for room, values in sorted(by_name.items()) if len(values) == 1]
    for room, value in pick(name, single, ROOMS_PER_SHEET):
        printed.append(("printed_area", f"What floor area does this plan print for the room '{room}', in square feet?",
                        MeasureKey(value=float(value), unit="sqft", tolerance=0.005, decimals=0), "lookup/raster"))  # fmt: skip
    repeats = [(room, len(values)) for room, values in sorted(by_name.items()) if 2 <= len(values) <= 6]
    for room, _ in pick(name + ":repeat", repeats, REPEATS_PER_SHEET):
        values = by_name[room]
        if values:
            printed.append(("printed_area_sum", f"What is the total floor area of all rooms labelled '{room}' on this "
                            "plan, in square feet?",
                            MeasureKey(value=float(sum(values)), unit="sqft", tolerance=0.005, decimals=0),
                            "compound/raster"))  # fmt: skip
            printed.append(("label_count", f"How many rooms on this plan are labelled '{room}'?",
                            CountKey(value=len(values)), "count/raster"))  # fmt: skip

    values = [value for _, value, _ in rooms]
    measured = len(values) >= 6 and sum(v % 10 != 0 for v in values) > 0.5 * len(values)
    if measured:
        big = [(room, value) for room, value in single if value >= 60]
        for room, value in pick(name + ":hidden", big, ROOMS_PER_SHEET):
            hidden.append(("room_area", f"What is the floor area of the room '{room}' on this plan, in square feet? "
                           "The plan does not print room areas: measure the room.",
                           MeasureKey(value=float(value), unit="sqft", tolerance=AREA_TOLERANCE, decimals=0),
                           "measure/raster"))  # fmt: skip

    scale = feet_per_inch(page)
    if scale:
        label, feet = scale
        ratio = round(feet * 12)
        tight = label.replace(" ", "")
        printed.append(("scale", "What scale does this sheet print for its drawing? Answer as printed, such as "
                        "1/4\" = 1'-0\", or as a ratio such as 1:48.",
                        LookupKey(accepted=(label, tight, tight.replace("'-0\"", "'"), f"1:{ratio}", f"1 : {ratio}",
                                            f"1/{ratio}")), "lookup/raster"))  # fmt: skip
        arcs = door_arcs(page, feet)
        if PLAN.search(text) and len(arcs) >= 8:
            printed.append(("door_leaves", "How many swing door leaves does this floor plan draw? Count each leaf "
                            "once: a double door has two leaves. Include the doors of toilet stalls.",
                            CountKey(value=len(arcs), tolerance=DOOR_TOLERANCE), "count/raster"))  # fmt: skip
    return printed, hidden, [line for _, _, line in rooms]


def tag_free(page: pymupdf.Page) -> bool:
    """True when the page is a drawing sheet: large, with text, and a floor plan title."""
    long_side = max(page.rect.width, page.rect.height) / 72
    return long_side >= MIN_SIDE_IN and bool(PLAN.search(" ".join(page.get_text("text").split())))


def sheets(root: Path) -> list[tuple[str, str, str, pymupdf.Page]]:
    """(name, group, partition, page) for each floor plan sheet of the USACE sets."""
    out: list[tuple[str, str, str, pymupdf.Page]] = []
    for pdf in sorted(root.glob("*.pdf")):
        kind, _, rest = pdf.stem.partition("__")
        if kind in SKIP:
            continue
        short = hashlib.sha256(rest.encode()).hexdigest()[:6]
        doc = pymupdf.open(pdf)
        for i, page in enumerate(doc):
            if tag_free(page):
                page.remove_rotation()  # text directions and coordinates are then those of the render
                # the ORTC set has 9 buildings: the barracks sheets (to page 87) are in dev, so that dev has
                # enough rooms with a measured area. The other buildings stay held out.
                early = kind == "ortc" and i + 1 < ORTC_LOCK_FROM
                group = f"usace:{kind}-barracks" if early else f"usace:{kind}"
                partition = "lock" if kind in LOCK and not early else "dev"
                out.append((f"usace_{kind}_{short}_p{i + 1:03d}", group, partition, page))
    return out


def render_without_areas(page: pymupdf.Page, area_lines: list[Line], path: Path, dpi: int) -> None:
    """The sheet with each "NNN SF" text removed. The line art stays."""
    doc = pymupdf.open()
    doc.insert_pdf(page.parent, from_page=page.number, to_page=page.number)
    copy = doc[0]
    for line in area_lines:
        copy.add_redact_annot(pymupdf.Rect(line[:4]), fill=False)
    copy.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
    copy.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False).save(path)
