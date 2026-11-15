"""What a vector PDF sheet exported from a BIM model gives, read from the sheet alone.

A sheet of this kind (IfcConvert style) has:
- a title line "<project> - <view word>: <storey>" (the dash is an em dash on the sheet);
- a scale text "1:N" and a scale bar with the labels "0" and "5 m";
- each room (IfcSpace cut) as a light filled polygon, with its name and number as text inside.
The sheet prints no areas. A room area is the polygon area times the scale squared. Counts of doors, walls
and other elements are not marked in a way this tool can read, and model-wide or 3D quantities are not on a
storey sheet at all. Nothing here reads a label or a key.
"""

from __future__ import annotations

import math
import re
import unicodedata
from typing import TYPE_CHECKING, Literal

import pymupdf
from shapely.geometry import Point, Polygon
from shapely.validation import make_valid

from bp.contract import Frozen

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

PT_M = 0.0254 / 72.0  # one PDF point on paper, in metres
_ROOM_FILL_MIN = 0.80  # a room fill is light: every channel at least this
_ROOM_FILL_MAX_SPREAD = 0.20
_CUT_GREY = 0.29
_MIN_POLY_PT2 = 0.5
_SCALE_AGREE = 0.02
_DUPLICATE_RATIO = 1.3  # a second polygon at most this much larger is the same room twice
_TITLE_DASHES = (" \u2014 ", " \u2013 ", " - ")
_PLAN_WORDS = (
    "floor plan", "grundriss", "plantegning", "plattegrond", "plano", "planta", "plan", "korruse plaan",
    "rzut", "pianta", "planul",
)  # fmt: skip
_ELEVATION_WORDS = ("elevation", "ansicht", "facade", "facada", "aanzicht", "facade", "vaade", "elewacja", "prospetto")
_SECTION_WORDS = ("section", "schnitt", "snit", "doorsnede", "seccion", "lõige", "przekrój", "sezione", "sectiune")

SheetKind = Literal["room_plan", "plan_without_rooms", "elevation", "section", "unknown"]


class RoomRegion(Frozen):
    index: int
    area_m2: float
    area_pt2: float
    bbox: tuple[float, float, float, float]
    points: tuple[tuple[float, float], ...]  # the exterior ring in PDF points, simplified


class TextLine(Frozen):
    text: str
    x: float
    y: float
    height: float
    bbox: tuple[float, float, float, float]


class RoomTag(Frozen):
    name: str
    number: str
    x: float
    y: float
    region: int | None  # the smallest room region that holds the tag


class SheetFacts(Frozen):
    page_width: float
    page_height: float
    title: str
    project: str
    view: str
    storey: str
    kind: SheetKind
    scale_ratio: int | None  # 100 means 1:100
    m_per_pt_bar: float | None
    m_per_pt_text: float | None
    m_per_pt: float | None  # the value used: the bar when it agrees with the text, else the bar or the text
    scale_confirmed: bool  # two witnesses agree within 2%
    rooms: tuple[RoomRegion, ...]
    lines: tuple[TextLine, ...]
    cut_fills: int  # dark grey filled paths (cut walls and columns drawn the same way)


class RoomArea(Frozen):
    status: Literal["found", "no_label", "no_region", "ambiguous", "no_scale"]
    label: str
    area_m2: float | None = None
    region: int | None = None
    tag_xy: tuple[float, float] | None = None
    candidates: tuple[float, ...] = ()  # areas of the regions that other matching tags point at
    detail: str = ""


# ----------------------------------------------------------------------------- reading


def _is_room_fill(color: object) -> bool:
    if not isinstance(color, (tuple, list)) or len(color) != 3:
        return False
    channels = [float(c) for c in color]
    light = all(c >= _ROOM_FILL_MIN for c in channels)
    white = all(c > 0.995 for c in channels)
    tinted = max(channels) - min(channels) > 0.02
    return light and not white and tinted and max(channels) - min(channels) < _ROOM_FILL_MAX_SPREAD


def _is_cut_grey(color: object) -> bool:
    return isinstance(color, (tuple, list)) and len(color) == 3 and all(abs(float(c) - _CUT_GREY) < 0.02 for c in color)


def _point(p: object) -> tuple[float, float]:
    return float(p.x), float(p.y)  # ty: ignore[missing-attribute]


def _rings(items: list[tuple[object, ...]]) -> list[list[tuple[float, float]]]:
    """Closed rings of a drawing. A new sub-path starts when a segment does not continue the last point."""
    rings: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    for item in items:
        op = item[0]
        if op in {"l", "c"}:
            start = _point(item[1])
            end = _point(item[-1])
            if current and (abs(current[-1][0] - start[0]) > 0.01 or abs(current[-1][1] - start[1]) > 0.01):
                rings.append(current)
                current = []
            if not current:
                current.append(start)
            current.append(end)
        elif op == "re":
            r = item[1]
            x0, y0, x1, y1 = float(r.x0), float(r.y0), float(r.x1), float(r.y1)  # ty: ignore[missing-attribute]
            rings.append([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
        elif op == "qu":
            q = item[1]
            rings.append([_point(q.ul), _point(q.ur), _point(q.lr), _point(q.ll)])  # ty: ignore[missing-attribute]
    if current:
        rings.append(current)
    return [r for r in rings if len(r) >= 3]


def _shape(items: list[tuple[object, ...]]) -> BaseGeometry | None:
    """One filled shape. A ring inside a larger ring of the same path is a hole (even-odd)."""
    parts = [make_valid(Polygon(r)) for r in _rings(items)]
    parts = [p for p in parts if p.area > 0]
    if not parts:
        return None
    parts.sort(key=lambda g: -g.area)
    shape = parts[0]
    for part in parts[1:]:
        shape = shape.difference(part) if shape.contains(part) else shape.union(part)
    return shape


def _lines(page: pymupdf.Page) -> list[TextLine]:
    out: list[TextLine] = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"]).strip()
            if not text:
                continue
            x0, y0, x1, y1 = (float(v) for v in line["bbox"])
            out.append(TextLine(text=text, x=(x0 + x1) / 2, y=(y0 + y1) / 2, height=y1 - y0, bbox=(x0, y0, x1, y1)))
    return out


def _scale_bar(page: pymupdf.Page) -> float | None:
    """Metres per point from a scale bar labelled '0' ... 'N m' on one baseline."""
    words = page.get_text("words")
    best: float | None = None
    for unit in (w for w in words if w[4] == "m"):
        numbers = [
            w for w in words if re.fullmatch(r"\d+", w[4]) and abs(w[1] - unit[1]) < 2 and 0 < unit[0] - w[2] < 6
        ]
        if not numbers:
            continue
        length = float(numbers[0][4])
        x_end = (numbers[0][0] + unit[2]) / 2
        for zero in (w for w in words if w[4] == "0" and abs(w[1] - unit[1]) < 2 and w[0] < numbers[0][0]):
            x_zero = (zero[0] + zero[2]) / 2
            if x_end - x_zero > 1:
                best = length / (x_end - x_zero)
    return best


def _scale_ratio(text: str) -> int | None:
    match = re.search(r"\b1\s*:\s*(\d{1,4})\b", text)
    return int(match.group(1)) if match else None


def fold(text: str) -> str:
    """Case folded, accents removed, single spaces."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", stripped.casefold()).strip()


def _title(lines: list[TextLine]) -> tuple[str, str, str, str]:
    """(title, project, view, storey) from the largest line that has a dash and a colon."""
    for line in sorted(lines, key=lambda t: -t.height):
        for dash in _TITLE_DASHES:
            if dash in line.text and ":" in line.text.split(dash, 1)[1]:
                project, rest = line.text.split(dash, 1)
                view, storey = rest.split(":", 1)
                return line.text, project.strip(), view.strip(), storey.strip()
    return "", "", "", ""


def _kind(view: str, rooms: int) -> SheetKind:
    v = fold(view)
    if any(w in v for w in _ELEVATION_WORDS):
        return "elevation"
    if any(w in v for w in _SECTION_WORDS):
        return "section"
    if rooms:
        return "room_plan"
    if any(w in v for w in _PLAN_WORDS):
        return "plan_without_rooms"
    return "unknown"


def read_sheet(path: str) -> SheetFacts:
    """Read page 1 of a vector PDF sheet into facts. It does not decide whether the sheet is a BIM export."""
    with pymupdf.open(path) as document:
        page = document[0]
        lines = _lines(page)
        text = "\n".join(t.text for t in lines)
        ratio = _scale_ratio(text)
        bar = _scale_bar(page)
        by_text = PT_M * ratio if ratio else None
        confirmed = bar is not None and by_text is not None and abs(bar / by_text - 1) <= _SCALE_AGREE
        m_per_pt = bar if bar is not None else by_text
        regions: list[RoomRegion] = []
        cut = 0
        for drawing in page.get_drawings():
            fill = drawing.get("fill")
            if _is_cut_grey(fill):
                cut += 1
            if not _is_room_fill(fill):
                continue
            shape = _shape(drawing["items"])
            if shape is None or shape.area <= _MIN_POLY_PT2:
                continue
            main = (
                shape if shape.geom_type == "Polygon" else max(getattr(shape, "geoms", [shape]), key=lambda g: g.area)
            )
            if main.geom_type != "Polygon":
                continue
            ring = tuple((round(x, 3), round(y, 3)) for x, y in main.simplify(0.02).exterior.coords)
            regions.append(
                RoomRegion(
                    index=len(regions),
                    area_m2=shape.area * m_per_pt**2 if m_per_pt else math.nan,
                    area_pt2=shape.area,
                    bbox=tuple(float(v) for v in shape.bounds),
                    points=ring,
                )
            )
        title, project, view, storey = _title(lines)
        return SheetFacts(
            page_width=float(page.rect.width),
            page_height=float(page.rect.height),
            title=title,
            project=project,
            view=view,
            storey=storey,
            kind=_kind(view, len(regions)),
            scale_ratio=ratio,
            m_per_pt_bar=bar,
            m_per_pt_text=by_text,
            m_per_pt=m_per_pt,
            scale_confirmed=confirmed,
            rooms=tuple(regions),
            lines=tuple(lines),
            cut_fills=cut,
        )


# ----------------------------------------------------------------------------- queries


def is_bim_sheet(sheet: SheetFacts) -> bool:
    """A sheet of the kind this tool reads: a title with a storey or view, and a scale."""
    return bool(sheet.title) and sheet.m_per_pt is not None


def split_label(label: str) -> tuple[str, str | None]:
    """'Kontor (Rum nr. 305)' -> ('Kontor', 'Rum nr. 305'). A label without a number keeps None."""
    match = re.match(r"^(.*\S)\s*\(([^()]*)\)$", label.strip())
    return (match.group(1).strip(), match.group(2).strip()) if match else (label.strip(), None)


def _shapes(sheet: SheetFacts) -> list[Polygon]:
    return [Polygon(r.points) for r in sheet.rooms]


def region_at(sheet: SheetFacts, x: float, y: float, shapes: list[Polygon] | None = None) -> int | None:
    """The smallest room region that holds the point (by its exact area)."""
    polys = shapes if shapes is not None else _shapes(sheet)
    point = Point(x, y)
    inside = [r for r, poly in zip(sheet.rooms, polys, strict=True) if poly.buffer(0.01).contains(point)]
    return min(inside, key=lambda r: r.area_pt2).index if inside else None


def tag_positions(sheet: SheetFacts, label: str) -> list[tuple[float, float]]:
    """Where the room tag for `label` is: the number line with the name line just above, or the name alone."""
    name, number = split_label(label)
    lines = sheet.lines
    want_name, want_number = fold(name), fold(number) if number else None
    spots: list[tuple[float, float, bool]] = []
    if want_number is not None:
        for line in lines:
            if fold(line.text) != want_number:
                continue
            above = [
                t for t in lines
                if fold(t.text) == want_name and abs(t.x - line.x) < 40 and 0 < line.y - t.y < 2.5 * line.height
            ]  # fmt: skip
            spots.append((line.x, line.y - line.height / 2 if above else line.y, bool(above)))
        with_name = [(x, y) for x, y, named in spots if named]
        if with_name:
            return with_name
        # one line "Name (Number)" or the full label printed as one line
        joined = [(t.x, t.y) for t in lines if fold(t.text) == fold(label)]
        return joined or [(x, y) for x, y, _ in spots]
    return [(t.x, t.y) for t in lines if fold(t.text) == want_name]


def room_area(sheet: SheetFacts, label: str) -> RoomArea:
    """The area of the room region under the tag of `label`, from the polygon and the scale."""
    if sheet.m_per_pt is None:
        return RoomArea(status="no_scale", label=label, detail="no scale bar and no 1:N text on the sheet")
    spots = tag_positions(sheet, label)
    if not spots:
        return RoomArea(status="no_label", label=label, detail="no room tag with this name and number")
    shapes = _shapes(sheet)
    hits = [(xy, region_at(sheet, xy[0], xy[1], shapes)) for xy in spots]
    found = [(xy, idx) for xy, idx in hits if idx is not None]
    if not found:
        return RoomArea(status="no_region", label=label, tag_xy=spots[0], detail="the tag is not inside a room polygon")
    areas = sorted({round(sheet.rooms[idx].area_m2, 3) for _, idx in found})
    if areas[-1] > areas[0] * (1 + _SCALE_AGREE):
        return RoomArea(
            status="ambiguous", label=label, candidates=tuple(areas),
            detail=f"{len(found)} tags with this label point at rooms of different areas",
        )  # fmt: skip
    (xy, idx) = found[0]
    # Two room polygons of nearly the same place but different areas: the model holds the room twice.
    point = Point(*xy)
    overlapping = [
        r.area_m2 for r, poly in zip(sheet.rooms, shapes, strict=True)
        if r.index != idx and poly.buffer(0.01).contains(point)
        and poly.intersection(shapes[idx]).area > 0.8 * shapes[idx].area
        and r.area_pt2 < _DUPLICATE_RATIO * sheet.rooms[idx].area_pt2
    ]  # fmt: skip
    if overlapping:
        return RoomArea(
            status="ambiguous", label=label, region=idx, tag_xy=xy,
            candidates=(sheet.rooms[idx].area_m2, *overlapping),
            detail="the tag lies in two overlapping room polygons of different area (a duplicated space)",
        )  # fmt: skip
    return RoomArea(status="found", label=label, area_m2=sheet.rooms[idx].area_m2, region=idx, tag_xy=xy)


def total_room_area(sheet: SheetFacts) -> float | None:
    if sheet.m_per_pt is None or not sheet.rooms:
        return None
    return math.fsum(r.area_m2 for r in sheet.rooms)


def storey_matches(sheet: SheetFacts, storey: str) -> bool:
    return fold(sheet.storey) == fold(storey)
