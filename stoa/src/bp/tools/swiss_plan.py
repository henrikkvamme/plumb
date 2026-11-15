"""Read a Swiss Dwellings floor plan sheet (a vector PDF made by Matplotlib) into typed facts.

The sheets come from one generator, so their paths are typed by style:
- room fills: a grey (0.54) stroke of 0.37 pt; the fill is white (in an apartment), 0.95 (outside an
  apartment) or 0.89 (an outdoor room). A shaft or void is a separate unnumbered fill inside a room;
- apartment outlines: a red (0.69, 0.23, 0.18) dash-dot stroke, with a tag "Whg. A" or "App. A";
- door openings: a dark grey (0.27) path with a quad;
- fixtures and windows: a white box with a black 0.51 pt stroke, typed by what is drawn inside it;
- text: the label is centred above the room number ("Küche" over "1.03"), printed areas ("12.34 m²") sit
  below the number on some sheets, and the title block prints the scale ("1:100 (A3)") and a scale bar.
The generator stacks exact copies of a door or window that two units share. The counts here include each copy,
because that is the convention of the source data.

`compile_plan` reads a page once. The query functions answer from the compiled plan and return a `Fact` with
evidence and warnings. A warning means that the value can be wrong; a solver should then abstain.
`detect` tells whether a page is a sheet of this kind at all.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import TYPE_CHECKING, Literal

from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon

from bp.contract import Evidence, Frozen
from bp.tools.pdf_text import BBox, PdfPage, Point, TextSpan, VectorPath, read_page

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from shapely.geometry.base import BaseGeometry

RGB = tuple[float, float, float]

ROOM_STROKE: RGB = (0.54, 0.54, 0.54)
ROOM_WIDTH = 0.3685
UNIT_STROKE: RGB = (0.69, 0.23, 0.18)
DOOR_STROKE: RGB = (0.27, 0.27, 0.27)
BOX_WIDTH = 0.51
OUTDOOR_FILL = 0.89
SHARED_FILL = 0.95  # a room outside every apartment (a stair hall, a lift), even when a unit outline holds it
POINTS_PER_INCH = 72.0
METRES_PER_INCH = 0.0254
TITLE_BAND_PT = 45.0  # the title block starts about this far above the span that holds the scale
LABEL_DX_PT = 1.0  # a label or a printed area is centred on the number (same x within 1 pt)
LABEL_DY_SIZES = 2.5  # ... and at most 2.5 text heights above (label) or below (printed area)
BOX_TOL_PT = 0.3
GLASS_PARALLEL = 0.02
GLASS_SPAN = 0.9
DRAIN_MAX_M = 0.06
TAG_NEAR_PT = 30.0  # a tag outside every outline takes the nearest untagged outline within this distance
NEAR_FILL_PT = 1.0  # a number outside every fill takes the nearest fill within this distance
SAME_PRINT_TOL = 0.02
SUM_RISK_SHARE = 0.005  # doubtful rooms may move a sum by at most 0.5% (a quarter of the tolerance)  # printed and computed areas agree within 2%

ROOM_NUMBER = re.compile(r"^(U\d+\.)?\d+\.\d+$|^U\d+\.\d+$")
MERGED_NUMBERS = re.compile(r"^[U\d.]+$")
UNIT_TAG = re.compile(r"^(Whg\.|App\.)\s*([A-Z]+)$")
PRINTED_AREA = re.compile(r"^(\d+(?:\.\d+)?)\s*m²$")
SCALE_TITLE = re.compile(r"1:(\d+)\s*\((A\d)\)")
SCALE_ANY = re.compile(r"1:(\d+)")

# Room labels that mark an outdoor room. An outdoor room without a label is known by its fill (0.89).
OUTDOOR_LABELS = frozenset(
    {
        "Balkon", "Balcon", "Balcone", "Loggia", "Terrasse", "Terrazza", "Sitzplatz", "Patio",
        "Garten", "Jardin", "Giardino",
    }
)  # fmt: skip

FixtureKind = Literal["toilet", "washbasin", "bathtub", "shower", "kitchen", "window", "other"]
TUB_DRAIN = "C0.025"  # a box with only the drain of a tub
HOB_RINGS = 4
NEAR_COPY_AREA = 1.1  # boxes within 10% of the smallest holder share its inner shapes  # a kitchen box holds four hob circles (r = 0.08 m)


# ----------------------------------------------------------------------------- facts


class Detection(Frozen):
    """Whether a page is a Swiss Dwellings sheet, and the signals that decided it."""

    is_plan: bool
    room_fills: int
    room_numbers: int
    scale_ratio: int | None
    reasons: tuple[str, ...]


class Scale(Frozen):
    """The scale from the title block, checked against the scale bar."""

    ratio: int
    paper: str | None
    metres_per_point: float
    bar_points_per_metre: float | None
    agrees: bool | None  # None when there is no scale bar to check
    evidence: Evidence


class Room(Frozen):
    """One numbered room. `area_m2` is the polygon area minus the inner polygons (shafts), at the sheet scale."""

    number: str
    label: str | None
    at: Point
    printed_area_m2: float | None
    area_m2: float | None
    fill: float | None
    outdoor: bool
    apartment: str | None
    containing: int  # how many room fills hold the number point; 0 when the nearest fill was taken
    in_apartment_fill: bool  # white fill: the room belongs to some apartment
    outline: int | None  # the unit outline that holds the number
    polygon: tuple[Point, ...]
    holes: int

    @property
    def print_mismatch(self) -> bool:
        """The printed area and the polygon area differ by more than 2%."""
        if self.printed_area_m2 is None or self.area_m2 is None:
            return False
        return abs(self.printed_area_m2 - self.area_m2) > SAME_PRINT_TOL * max(self.printed_area_m2, 1e-9)

    def evidence(self) -> tuple[Evidence, ...]:
        out = [Evidence(kind="text_span", points=(self.at,), ref=self.number, note=self.label or "")]
        if self.polygon:
            out.append(Evidence(kind="polygon", points=self.polygon, ref=self.number, note=f"{self.area_m2} m2"))
        return tuple(out)


class Apartment(Frozen):
    letter: str
    at: Point
    outline: int | None  # index of the unit outline that holds the tag


class Fixture(Frozen):
    """A white box with a black 0.51 pt stroke and what is drawn inside it."""

    kind: FixtureKind
    signature: str
    copies: int  # the generator stacks a copy for each unit that lists the element
    glass: int
    bbox: BBox
    long_m: float  # the sides of the bounding box
    short_m: float
    edge_long_m: float  # the sides of the box itself (a rotated window has a square bounding box)
    edge_short_m: float


class Doors(Frozen):
    count: int  # every drawn copy (the source convention)
    distinct: int  # copies on the same place counted once (what a person sees)
    evidence: tuple[Evidence, ...]


class SwissPlan(Frozen):
    """Everything that the query functions need, read once from one page."""

    detection: Detection
    scale: Scale | None
    title_cut: float
    rooms: tuple[Room, ...]
    apartments: tuple[Apartment, ...]
    unit_outlines: int
    doors: Doors
    fixtures: tuple[Fixture, ...]
    printed_areas: bool
    unnumbered_fills: int


class Fact(Frozen):
    """An answer from the plan. `warnings` lists the reasons why the value can be wrong."""

    value: float | int | None
    unit: str | None = None
    evidence: tuple[Evidence, ...] = ()
    warnings: tuple[str, ...] = ()
    note: str = ""


# ----------------------------------------------------------------------------- helpers


def _near(colour: RGB | None, ref: RGB, tol: float = 0.01) -> bool:
    return colour is not None and all(abs(a - b) < tol for a, b in zip(colour, ref, strict=True))


def _polygon(points: Iterable[Point]) -> BaseGeometry:
    return Polygon(list(points)).buffer(0)


def path_area_shape(path: VectorPath) -> BaseGeometry:
    """The filled area of a path.

    Its rings combine by the even-odd rule: a ring inside another is a hole (the generator draws holes as
    reversed rings, so the nonzero rule gives the same), and separate rings add up.
    """
    shapes = [_polygon(r) for r in path.rings if len(r) >= 3]
    if not shapes:
        return _polygon(path.points)
    out = shapes[0]
    for shape in shapes[1:]:
        out = out.symmetric_difference(shape)
    return out


def _is_room_fill(path: VectorPath) -> bool:
    return (
        _near(path.stroke, ROOM_STROKE)
        and abs(path.width - ROOM_WIDTH) < 0.01
        and path.fill is not None
        and len(path.points) >= 3
    )


def _is_box(path: VectorPath) -> bool:
    return (
        _near(path.fill, (1.0, 1.0, 1.0), 0.02)
        and _near(path.stroke, (0.0, 0.0, 0.0), 0.02)
        and abs(path.width - BOX_WIDTH) < 0.01
        and (path.count("r") > 0 or path.count("l") == 4)
    )


def net_holes(polys: list[BaseGeometry]) -> list[BaseGeometry]:
    """Subtract every polygon that lies inside a larger one (a shaft or lift inside a stair hall)."""
    out: list[BaseGeometry] = []
    for i, p in enumerate(polys):
        net = p
        grown = p.buffer(1e-6)
        for j, q in enumerate(polys):
            if j != i and q.area < p.area and grown.contains(q):
                net = net.difference(q)
        out.append(net)
    return out


def _exterior(geometry: BaseGeometry) -> tuple[Point, ...]:
    if isinstance(geometry, Polygon):
        return tuple((float(x), float(y)) for x, y in geometry.exterior.coords)
    hull = geometry.convex_hull
    if isinstance(hull, Polygon):
        return tuple((float(x), float(y)) for x, y in hull.exterior.coords)
    return ()


# ----------------------------------------------------------------------------- page level readers


def title_cut(page: PdfPage) -> float:
    """The y where the title block band starts. Everything below is legend, scale bar and title."""
    ys = [s.bbox[1] for s in page.spans if SCALE_TITLE.search(s.text)]
    return ys[0] - TITLE_BAND_PT if ys else page.height * 0.82


def read_scale(page: PdfPage, cut: float | None = None) -> Scale | None:
    """The scale ratio from the title text, checked against the scale bar ticks "0" and "5" (or "10")."""
    cut = title_cut(page) if cut is None else cut
    titled = [(s, m) for s in page.spans for m in [SCALE_TITLE.search(s.text)] if m]
    loose = [(s, m) for s in page.spans for m in [SCALE_ANY.search(s.text)] if m]
    pick = titled[0] if titled else (loose[0] if loose else None)
    if pick is None:
        return None
    span, match = pick
    ratio = int(match.group(1))
    if ratio <= 0:
        return None
    paper = match.group(2) if match.re is SCALE_TITLE else None
    mpp = METRES_PER_INCH / POINTS_PER_INCH * ratio
    zero = [s for s in page.spans if s.text == "0" and s.bbox[1] > cut]
    tick = [s for s in page.spans if s.text in {"5", "10"} and s.bbox[1] > cut]
    bar = (tick[0].cx - zero[0].cx) / float(tick[0].text) if zero and tick else None
    agrees = None if bar is None else abs(bar * mpp - 1.0) < 0.01
    evidence = Evidence(kind="scale", page=page.page, points=((span.cx, span.cy),), ref=span.text)
    return Scale(
        ratio=ratio, paper=paper, metres_per_point=mpp, bar_points_per_metre=bar, agrees=agrees, evidence=evidence
    )


def detect(page: PdfPage) -> Detection:
    """A sheet of this kind has room fills of the generator style, room numbers and a printed scale."""
    fills = sum(1 for p in page.paths if _is_room_fill(p))
    numbers = sum(1 for s in page.runs if ROOM_NUMBER.match(s.text))
    scale = read_scale(page)
    reasons: list[str] = []
    if fills == 0:
        reasons.append("no room fills in the generator style")
    if numbers == 0:
        reasons.append("no room numbers")
    if scale is None:
        reasons.append("no scale text")
    if page.images:
        reasons.append(f"{page.images} raster images on the page")
    return Detection(
        is_plan=not reasons,
        room_fills=fills,
        room_numbers=numbers,
        scale_ratio=scale.ratio if scale else None,
        reasons=tuple(reasons),
    )


def _closest(target: TextSpan, pool: list[TextSpan], *, above: bool) -> TextSpan | None:
    limit = LABEL_DY_SIZES * target.size

    def gap(o: TextSpan) -> float:
        return target.cy - o.cy if above else o.cy - target.cy

    near = [o for o in pool if abs(o.cx - target.cx) < LABEL_DX_PT and 0 < gap(o) < limit]
    return min(near, key=gap) if near else None


def box_edges(box: VectorPath) -> tuple[float, float]:
    """The long and the short side of a (possibly rotated) box, in points."""
    pts = box.points
    if len(pts) < 3:
        return (0.0, 0.0)
    a = math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
    b = math.hypot(pts[2][0] - pts[1][0], pts[2][1] - pts[1][1])
    return (max(a, b), min(a, b))


def _window_glass(box: VectorPath, inner: list[tuple[str, VectorPath]]) -> int:
    """Thin lines parallel to the long side of the (possibly rotated) box that span it: the glass of a window."""
    pts = box.points
    if len(pts) < 4:
        return 0
    e1 = (pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
    e2 = (pts[2][0] - pts[1][0], pts[2][1] - pts[1][1])
    axis = e1 if math.hypot(*e1) >= math.hypot(*e2) else e2
    length = math.hypot(*axis)
    if length == 0:
        return 0
    glass = 0
    for signature, path in inner:
        if signature != "L1w0.37" or not path.lines:
            continue
        (x0, y0), (x1, y1) = path.lines[0]
        v = (x1 - x0, y1 - y0)
        lv = math.hypot(*v)
        if lv > GLASS_SPAN * length and abs(v[0] * axis[1] - v[1] * axis[0]) / (lv * length) < GLASS_PARALLEL:
            glass += 1
    return glass


def _drain(signature: str) -> bool:
    return any(t.startswith("C") and float(t[1:]) < DRAIN_MAX_M for t in signature.split("+") if len(t) > 1)


def classify_fixture(signature: str, copies: int, glass: int) -> FixtureKind:  # noqa: PLR0911 - one per kind
    """The kind of a box from the shapes inside it (vertex counts and drain circles of the generator)."""
    parts = signature.split("+")
    tokens = set(parts)
    if parts.count("C0.080") >= HOB_RINGS:  # a kitchen unit; its sink box overlaps it
        return "kitchen"
    if "L68w0.51" in tokens or signature == TUB_DRAIN:  # a narrow tub has no room for its inner outline
        return "bathtub"
    if "L47w0.51" in tokens and "L1w0.51" in tokens and not _drain(signature):
        return "toilet"
    if "L47w0.51" in tokens and _drain(signature):
        return "washbasin"
    if "Q" in tokens and _drain(signature):
        return "shower"
    if glass >= 2 * copies:
        return "window"
    return "other"


def _inner_signature(path: VectorPath, mpp: float) -> str | None:
    if path.fill is not None or not _near(path.stroke, (0.0, 0.0, 0.0)):
        return None
    if path.count("c") == 8:
        radius = (path.bbox[2] - path.bbox[0]) / 2 * mpp
        return f"C{radius:.3f}"
    if path.count("q"):
        return "Q"
    lines = path.count("l")
    if lines:
        return f"L{lines}w{path.width:.2f}"
    return None


def _box_key(box: VectorPath) -> tuple[float, ...]:
    return tuple(round(v, 1) for v in box.bbox)


def _box_area(b: BBox) -> float:
    return (b[2] - b[0]) * (b[3] - b[1])


def _holds(outer: BBox, inner: BBox) -> bool:
    return (
        inner[0] >= outer[0] - BOX_TOL_PT
        and inner[1] >= outer[1] - BOX_TOL_PT
        and inner[2] <= outer[2] + BOX_TOL_PT
        and inner[3] <= outer[3] + BOX_TOL_PT
    )


def read_fixtures(page: PdfPage, cut: float, mpp: float) -> tuple[Fixture, ...]:
    boxes: list[VectorPath] = []
    inner: list[tuple[str, VectorPath]] = []
    for path in page.paths:
        if path.bbox[1] > cut or _is_room_fill(path) or _near(path.stroke, UNIT_STROKE):
            continue
        if _near(path.stroke, DOOR_STROKE) and path.count("q"):
            continue
        if _is_box(path):
            boxes.append(path)
            continue
        signature = _inner_signature(path, mpp)
        if signature is not None:
            inner.append((signature, path))
    copies = Counter(_box_key(b) for b in boxes)
    unique: dict[tuple[float, ...], VectorPath] = {}
    for box in boxes:
        unique.setdefault(_box_key(box), box)
    # Each inner shape belongs to the smallest box that holds it: a sink box overlaps a kitchen box, a basin
    # box overlaps a tub box, a WC box overlaps a stair box.
    owned: dict[tuple[float, ...], list[tuple[str, VectorPath]]] = {key: [] for key in unique}
    for sig, p in inner:
        holders = [key for key, box in unique.items() if _holds(box.bbox, p.bbox)]
        if holders:
            least = min(_box_area(unique[k].bbox) for k in holders)
            for k in holders:  # two near copies of one box (two units list it) both keep the shape
                if _box_area(unique[k].bbox) <= least * NEAR_COPY_AREA:
                    owned[k].append((sig, p))
    out: list[Fixture] = []
    for key, box in unique.items():
        x0, y0, x1, y1 = box.bbox
        inside = owned[key]
        signature = "+".join(sorted(sig for sig, _ in inside))
        glass = _window_glass(box, inside)
        w, h = x1 - x0, y1 - y0
        edge_long, edge_short = box_edges(box)
        kind = classify_fixture(signature, copies[key], glass)
        if kind == "window" and glass != 2 * copies[key]:
            kind = "other"
        out.append(
            Fixture(
                kind=kind,
                signature=signature,
                copies=copies[key],
                glass=glass,
                bbox=box.bbox,
                long_m=round(max(w, h) * mpp, 3),
                short_m=round(min(w, h) * mpp, 3),
                edge_long_m=round(edge_long * mpp, 3),
                edge_short_m=round(edge_short * mpp, 3),
            )
        )
    return tuple(out)


def read_doors(page: PdfPage, cut: float) -> Doors:
    quads = [p for p in page.paths if p.bbox[1] <= cut and _near(p.stroke, DOOR_STROKE) and p.count("q")]
    distinct = {tuple(round(v, 1) for v in p.bbox) for p in quads}
    evidence = tuple(
        Evidence(kind="mark", page=page.page, points=((p.bbox[0], p.bbox[1]), (p.bbox[2], p.bbox[3])), ref="door")
        for p in quads
    )
    return Doors(count=len(quads), distinct=len(distinct), evidence=evidence)


def _read_apartments(tags: list[TextSpan], outlines: list[BaseGeometry]) -> tuple[dict[int, str], list[Apartment]]:
    """Give each unit tag ("Whg. A") its outline. It returns the letter of each tagged outline and the tags."""
    letter_of: dict[int, str] = {}
    apartments: list[Apartment] = []
    for tag in tags:
        match = UNIT_TAG.match(tag.text)
        if match is None:
            continue
        point = ShapelyPoint(tag.cx, tag.cy)
        hits = [i for i, u in enumerate(outlines) if u.contains(point)]
        if not hits:  # a tag at the centroid of a concave outline falls outside it: take the nearest free one
            free = [(u.distance(point), i) for i, u in enumerate(outlines) if i not in letter_of]
            free = [(d, i) for d, i in free if d < TAG_NEAR_PT]
            hits = [min(free)[1]] if free else []
        if hits:
            letter_of.setdefault(hits[0], match.group(2))
        apartments.append(Apartment(letter=match.group(2), at=(tag.cx, tag.cy), outline=hits[0] if hits else None))
    return letter_of, apartments


def compile_plan(page: PdfPage) -> SwissPlan:
    """Read rooms, apartments, doors and fixtures from a page. Call `detect` first; this assumes a plan."""
    detection = detect(page)
    cut = title_cut(page)
    scale = read_scale(page, cut)
    mpp = scale.metres_per_point if scale else 0.0
    plan_spans = [s for s in page.spans if s.bbox[1] < cut]
    # Numbers come from the text operators: PyMuPDF merges two numbers that overlap ("2.472.48") into one
    # span. Labels come from the merged spans: a ligature splits "Bürofläche" into several operators.
    numbers = [s for s in page.runs if s.bbox[1] < cut and ROOM_NUMBER.match(s.text)]
    tags = [s for s in plan_spans if UNIT_TAG.match(s.text)]
    others = [s for s in plan_spans if not MERGED_NUMBERS.match(s.text) and not UNIT_TAG.match(s.text)]
    printed = [s for s in others if PRINTED_AREA.match(s.text)]

    fills: list[tuple[BaseGeometry, float]] = []
    outlines: list[BaseGeometry] = []
    for path in page.paths:
        if path.bbox[1] > cut:
            continue
        if _is_room_fill(path) and path.fill is not None:
            fills.append((path_area_shape(path), round(path.fill[0], 2)))
        elif _near(path.stroke, UNIT_STROKE) and len(path.points) >= 3:
            outlines.append(path_area_shape(path))
    raw = [g for g, _ in fills]
    nets = net_holes(raw)
    holes = [
        sum(1 for j, q in enumerate(raw) if j != i and q.area < p.area and p.buffer(1e-6).contains(q))
        for i, p in enumerate(raw)
    ]

    letter_of, apartments = _read_apartments(tags, outlines)

    rooms: list[Room] = []
    used: set[int] = set()
    for number in numbers:
        label_span = _closest(number, others, above=True)
        area_span = _closest(number, printed, above=False)
        point = ShapelyPoint(number.cx, number.cy)
        hits = [i for i, p in enumerate(nets) if p.contains(point)]
        best = min(hits, key=lambda i: nets[i].area) if hits else None
        if best is None:  # the number can sit just outside a sliver of a room
            near = [(nets[i].distance(point), i) for i in range(len(nets))]
            near = [(d, i) for d, i in near if d < NEAR_FILL_PT]
            best = min(near)[1] if near else None
        if best is not None:
            used.add(best)
        units = [i for i, u in enumerate(outlines) if u.contains(point)]
        units.sort(key=lambda i: i not in letter_of)
        area_match = PRINTED_AREA.match(area_span.text) if area_span else None
        label = label_span.text if label_span else None
        fill = fills[best][1] if best is not None else None
        rooms.append(
            Room(
                number=number.text,
                label=label,
                at=(number.cx, number.cy),
                printed_area_m2=float(area_match.group(1)) if area_match else None,
                area_m2=round(nets[best].area * mpp * mpp, 4) if best is not None and mpp else None,
                fill=fill,
                outdoor=label in OUTDOOR_LABELS or fill == OUTDOOR_FILL,
                apartment=letter_of.get(units[0]) if units else None,
                containing=len(hits),
                in_apartment_fill=fill == 1.0,
                outline=units[0] if units else None,
                polygon=_exterior(nets[best]) if best is not None else (),
                holes=holes[best] if best is not None else 0,
            )
        )
    return SwissPlan(
        detection=detection,
        scale=scale,
        title_cut=cut,
        rooms=tuple(rooms),
        apartments=tuple(apartments),
        unit_outlines=len(outlines),
        doors=read_doors(page, cut),
        fixtures=read_fixtures(page, cut, mpp),
        printed_areas=bool(printed),
        unnumbered_fills=sum(1 for i in range(len(nets)) if i not in used),
    )


def read_plan(path: str | Path) -> SwissPlan:
    return compile_plan(read_page(path))


# ----------------------------------------------------------------------------- queries


def norm_label(text: str) -> str:
    """Fold every run of white space (also the no-break spaces of French quotes) into one space."""
    return re.sub(r"[\s\u00a0\u202f]+", " ", text).strip()


def room_id(number: str) -> str:
    """The entity id of a room, the same in the facts and in the rows of the agent tools."""
    return f"room:{number}"


def apartment_id(letter: str) -> str:
    return f"apartment:{letter}"


def room(plan: SwissPlan, number: str) -> Room | None:
    hits = [r for r in plan.rooms if r.number == number]
    return hits[0] if hits else None


def _room_warnings(r: Room) -> list[str]:
    out: list[str] = []
    if r.area_m2 is None:
        out.append(f"room {r.number}: no polygon")
    elif r.containing == 0:
        out.append(f"room {r.number}: the number is outside its polygon")
    elif r.containing > 1:
        out.append(f"room {r.number}: {r.containing} room fills overlap at the number")
    if r.print_mismatch:
        out.append(f"room {r.number}: printed {r.printed_area_m2} and polygon {r.area_m2} differ")
    return out


def _room_risk(r: Room) -> float | None:
    """The square metres that a doubtful room can move a sum by. None when nothing bounds it."""
    if r.area_m2 is None:
        return r.printed_area_m2
    if r.containing > 1:
        return None
    risk = 0.0
    if r.containing == 0:
        risk += r.area_m2
    if r.print_mismatch and r.printed_area_m2 is not None:
        risk += abs(r.printed_area_m2 - r.area_m2)
    return risk


def room_area(plan: SwissPlan, number: str) -> Fact:
    r = room(plan, number)
    if r is None:
        return Fact(value=None, warnings=(f"no room {number} on the sheet",))
    return Fact(value=r.area_m2, unit="m2", evidence=r.evidence(), warnings=tuple(_room_warnings(r)))


def labelled(plan: SwissPlan, label: str) -> tuple[Room, ...]:
    want = norm_label(label)
    return tuple(r for r in plan.rooms if r.label is not None and norm_label(r.label) == want)


def label_count(plan: SwissPlan, label: str) -> Fact:
    hits = labelled(plan, label)
    evidence = tuple(Evidence(kind="text_span", points=(r.at,), ref=r.number, note=r.label or "") for r in hits)
    return Fact(value=len(hits), evidence=evidence)


def _area_sum(rooms: Iterable[Room], what: str) -> Fact:
    chosen = list(rooms)
    if not chosen:
        return Fact(value=None, warnings=(f"no rooms for {what}",))
    total = round(sum(r.area_m2 or 0.0 for r in chosen), 2)
    risks = [_room_risk(r) for r in chosen]
    known = [x for x in risks if x is not None]
    if len(known) == len(risks) and sum(known) <= SUM_RISK_SHARE * total:
        warnings: list[str] = []  # the doubtful rooms cannot move the sum out of the tolerance
    else:
        warnings = [w for r in chosen for w in _room_warnings(r)]
    evidence = tuple(e for r in chosen for e in r.evidence())
    note = " + ".join(f"{r.number}:{r.area_m2}" for r in chosen)
    return Fact(value=total, unit="m2", evidence=evidence, warnings=tuple(warnings), note=note[:400])


def label_area(plan: SwissPlan, label: str) -> Fact:
    return _area_sum(labelled(plan, label), f"label {label!r}")


def total_area(plan: SwissPlan) -> Fact:
    """All numbered rooms minus outdoor rooms. Shafts and voids are unnumbered, so they are out already."""
    return _area_sum((r for r in plan.rooms if not r.outdoor), "the floor total")


def apartment_area(plan: SwissPlan, letter: str) -> Fact:
    """Rooms inside the outline that holds the tag of the apartment, minus outdoor rooms and shared rooms.

    A shared room (a stair hall or a lift, filled 0.95) can sit inside the red outline; the source gives it to
    no apartment.
    """
    if not any(a.letter == letter for a in plan.apartments):
        return Fact(value=None, warnings=(f"no apartment {letter} on the sheet",))

    def counted(r: Room) -> bool:
        return not r.outdoor and r.fill != SHARED_FILL

    chosen = [r for r in plan.rooms if r.apartment == letter and counted(r)]
    # A white room in an outline without a tag: a part of a tagged unit, or a unit that is not an apartment.
    orphans = [r for r in plan.rooms if r.apartment is None and r.outline is not None and r.in_apartment_fill
               and counted(r)]  # fmt: skip
    fact = _area_sum(chosen, f"apartment {letter}")
    if orphans:
        names = ", ".join(r.number for r in orphans)
        warning = f"rooms {names} sit in an outline without a tag"
        fact = fact.model_copy(update={"warnings": (*fact.warnings, warning)})
    return fact


def apartment_count(plan: SwissPlan) -> Fact:
    evidence = tuple(Evidence(kind="text_span", points=(a.at,), ref=a.letter) for a in plan.apartments)
    return Fact(value=len(plan.apartments), evidence=evidence)


def door_count(plan: SwissPlan) -> Fact:
    note = f"{plan.doors.count} drawn door openings ({plan.doors.distinct} distinct places)"
    return Fact(value=plan.doors.count, evidence=plan.doors.evidence, note=note)


def fixture_count(plan: SwissPlan, kind: FixtureKind) -> Fact:
    hits = [f for f in plan.fixtures if f.kind == kind]
    value = sum(f.copies for f in hits) if kind == "window" else len(hits)
    evidence = tuple(
        Evidence(kind="mark", points=((f.bbox[0], f.bbox[1]), (f.bbox[2], f.bbox[3])), ref=kind, note=f.signature)
        for f in hits
    )
    return Fact(value=value, evidence=evidence)
