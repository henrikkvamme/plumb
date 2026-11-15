"""Quantities that a contractor asks for, from a vector floor plan: perimeters, baseboards, walls and openings.

The same geometry runs on the Swiss vector PDF and on its DXF twin. Each reader gives rooms, walls, doors and
windows as polygons in its own drawing units; `measure` gives the quantities in metres.

Conventions (each result says which one it uses):
- Room perimeter: the length of the whole edge of the net floor polygon, shaft holes included. A door opening
  does not break it: the room polygon runs along the wall face across the opening.
- Baseboard (skirting): the perimeter minus the width of each door opening in the room edge. A door between two
  rooms is taken off in both rooms. `open_edge_m` is the edge that borders another room with no wall (an open
  kitchen); a baseboard cannot run there either, so `baseboard_walls_only_m` takes it off too.
- Door width: the long side of the door opening in the wall (the clear opening of the drawing, not the leaf).
- Wall length: the centre line of the wall network, with door and window openings filled, measured to the free
  end of each wall. This is not the per-element sum of a BIM model: elements overlap at each corner and T, so
  their sum is longer (about 13% on the Swiss source walls).
- Counts per room: each door or window place once. The sheet-wide door count of the Swiss source counts one
  door symbol per side of a shared wall; per room that rule makes no sense, so it is not used here.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Literal

import numpy as np
import shapely
from PIL import Image, ImageDraw
from shapely import affinity
from shapely.geometry import Polygon
from shapely.ops import unary_union

from bp.contract import Frozen

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from shapely.geometry.base import BaseGeometry

    from bp.tools import dxf_plan, swiss_plan
    from bp.tools.pdf_text import PdfPage

XY = tuple[float, float]

TOUCH_M = 0.03  # an edge part counts as on an opening or on another room within 3 cm
OPENING_SHARE = 0.5  # an opening is in a room edge when at least half its width lies on the edge
SKELETON_RES_M = 0.02  # raster step of the wall centre line
CLOSE_M = 0.01  # gaps up to 2 cm between wall pieces and opening boxes are closed
MAX_PIXELS = 4_000_000  # a larger wall piece gets a coarser raster
WALL_STROKE = 0.992  # Swiss PDF: the black outline of each wall piece
WALL_STROKE_TOL = 0.01
FRAME_SHARE = 0.9  # a path almost as wide as the page is the sheet frame, not a wall

# The room kind of each label, from 28,368 Swiss rooms matched to the source subtype (data/external/swiss-derived/
# label_map.json): the subtype that most rooms with the label have. "room" is the plain "Zimmer" (a bedroom or a
# study: the source does not say), "bedroom" is "Schlafzimmer".
KIND_OF_LABEL: dict[str, str] = {
    "Zimmer": "room", "Pièce": "room", "Stanza": "room",
    "Schlafzimmer": "bedroom", "Chambre à coucher": "bedroom", "Camera da letto": "bedroom",
    "Bad": "bathroom", "Bain": "bathroom", "Bagno": "bathroom",
    "Küche": "kitchen", "Cuisine": "kitchen", "Cucina": "kitchen", "Küche/Essen": "kitchen_dining",
    "Korridor": "corridor", "Couloir": "corridor", "Corridoio": "corridor", "Halle": "corridor", "Hall": "corridor",
    "Wohnen/Essen": "living_dining", "Séjour/repas": "living_dining", "Soggiorno/pranzo": "living_dining",
    "Wohnen": "living_room", "Séjour": "living_room", "Soggiorno": "living_room",
    "Essen": "dining", "Repas": "dining", "Pranzo": "dining",
    "Reduit": "storeroom", "Réduit": "storeroom", "Ripostiglio": "storeroom",
    "Treppenhaus": "staircase", "Cage d'escalier": "staircase", "Vano scala": "staircase",
    "Lift": "elevator", "Ascenseur": "elevator", "Ascensore": "elevator",
    "Balkon": "balcony", "Balcon": "balcony", "Balcone": "balcony",
    "Loggia": "loggia", "Terrasse": "terrace", "Terrazza": "terrace", "Sitzplatz": "patio", "Patio": "patio",
    "Garten": "garden", "Jardin": "garden", "Giardino": "garden",
    "Büro": "office", "Bürofläche": "office",
    "Waschen/Trocknen": "laundry", "Lavanderia": "laundry", "Buanderie": "laundry",
    "Wintergarten": "winter_garden", "Jardin d'hiver": "winter_garden", "Giardino d'inverno": "winter_garden",
    "Kellerabteil": "cellar", "Vano cantina": "cellar", "Compartiment cave": "cellar",
}  # fmt: skip


def room_kind(label: str | None) -> str | None:
    """The room kind of a label, or None for an unknown or missing label."""
    if not label:
        return None
    return KIND_OF_LABEL.get(" ".join(label.split()))


# ----------------------------------------------------------------------------- inputs and results


class RoomIn(Frozen):
    entity_id: str
    number: str | None
    label: str | None
    apartment: str | None
    outdoor: bool
    shared: bool  # outside every apartment (a stair hall, a lift)
    area_m2: float | None
    rings: tuple[tuple[XY, ...], ...]  # exterior first, then the holes, in drawing units


class OpeningIn(Frozen):
    entity_id: str
    kind: Literal["door", "window"]
    ring: tuple[XY, ...]  # the opening in the wall, in drawing units


class FloorIn(Frozen):
    unit_m: float  # metres per drawing unit
    rooms: tuple[RoomIn, ...]
    doors: tuple[OpeningIn, ...]  # each place once
    windows: tuple[OpeningIn, ...]  # each place once
    walls: tuple[tuple[tuple[XY, ...], ...], ...]  # wall pieces: rings (exterior, then holes)


class RoomQ(Frozen):
    entity_id: str
    number: str | None
    label: str | None
    kind: str | None
    apartment: str | None
    outdoor: bool
    shared: bool
    area_m2: float | None
    perimeter_m: float
    outer_perimeter_m: float  # the exterior ring only
    door_ids: tuple[str, ...]
    door_widths_m: tuple[float, ...]
    window_ids: tuple[str, ...]
    window_widths_m: tuple[float, ...]
    open_edge_m: float
    baseboard_m: float  # perimeter minus door widths
    baseboard_walls_only_m: float  # also minus the open edge
    exterior: tuple[XY, ...]  # for evidence


class OpeningQ(Frozen):
    entity_id: str
    kind: Literal["door", "window"]
    width_m: float
    depth_m: float  # the short side: about the wall thickness
    rooms: tuple[str, ...]  # entity ids of the rooms whose edge holds it
    ring: tuple[XY, ...]


class WallsQ(Frozen):
    centerline_m: float
    exterior_m: float  # centre line of walls on the outer edge of the floor
    interior_m: float
    footprint_m2: float  # walls with the openings filled
    pieces: int
    free_ends: int


class FloorQ(Frozen):
    unit_m: float
    rooms: tuple[RoomQ, ...]
    doors: tuple[OpeningQ, ...]
    windows: tuple[OpeningQ, ...]
    walls: WallsQ | None


# ----------------------------------------------------------------------------- geometry


def _polygon(rings: tuple[tuple[XY, ...], ...]) -> BaseGeometry:
    shell, *holes = rings
    shape = Polygon(shell, [h for h in holes if len(h) >= 3])
    return shape if shape.is_valid else shape.buffer(0)


def _parts(geom: BaseGeometry) -> list[Polygon]:
    if isinstance(geom, Polygon):
        return [] if geom.is_empty else [geom]
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon) and not g.is_empty]


def sides(ring: Iterable[XY]) -> tuple[float, float]:
    """The long and the short side of the smallest rotated rectangle around a ring."""
    rect = Polygon(list(ring)).minimum_rotated_rectangle
    if not isinstance(rect, Polygon) or rect.is_empty:
        return 0.0, 0.0
    c = list(rect.exterior.coords)
    if len(c) < 3:
        return 0.0, 0.0
    a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    return max(a, b), min(a, b)


def dominant_angle(geom: BaseGeometry) -> float:
    """The direction (0 to 90 degrees) that most edge length follows: the grid of the walls."""
    hist = np.zeros(90)
    for part in _parts(geom):
        for ring in (part.exterior, *part.interiors):
            c = np.asarray(ring.coords)
            d = np.diff(c, axis=0)
            length = np.hypot(d[:, 0], d[:, 1])
            angle = np.degrees(np.arctan2(d[:, 1], d[:, 0])) % 90
            np.add.at(hist, np.round(angle).astype(int) % 90, length)
    smooth = hist + np.roll(hist, 1) + np.roll(hist, -1)
    return float(np.argmax(smooth))


def _raster(geom: Polygon, res: float) -> tuple[np.ndarray, float, float]:
    x0, y0, x1, y1 = geom.bounds
    w = math.ceil((x1 - x0) / res) + 3
    h = math.ceil((y1 - y0) / res) + 3
    img = Image.new("1", (w, h), 0)
    draw = ImageDraw.Draw(img)

    def px(coords: Iterable[tuple[float, ...]]) -> list[tuple[float, float]]:
        return [((x - x0) / res + 1, (y - y0) / res + 1) for x, y, *_ in coords]

    draw.polygon(px(geom.exterior.coords), fill=1)
    for ring in geom.interiors:
        draw.polygon(px(ring.coords), fill=0)
    return np.array(img, dtype=bool), x0, y0


def _thin(mask: np.ndarray) -> np.ndarray:
    """Zhang-Suen thinning: a one-pixel 8-connected skeleton."""
    a = mask.astype(np.uint8)
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            p = np.pad(a, 1)
            p2, p3, p4 = p[:-2, 1:-1], p[:-2, 2:], p[1:-1, 2:]
            p5, p6, p7 = p[2:, 2:], p[2:, 1:-1], p[2:, :-2]
            p8, p9 = p[1:-1, :-2], p[:-2, :-2]
            ring = (p2, p3, p4, p5, p6, p7, p8, p9, p2)
            neighbours = sum(x.astype(np.int8) for x in ring[:8])
            transitions = sum(((ring[i] == 0) & (ring[i + 1] == 1)).astype(np.int8) for i in range(8))
            side = (
                (((p2 * p4 * p6) == 0) & ((p4 * p6 * p8) == 0))
                if step == 0
                else (((p2 * p4 * p8) == 0) & ((p2 * p6 * p8) == 0))
            )
            drop = (a == 1) & (neighbours >= 2) & (neighbours <= 6) & (transitions == 1) & side
            if drop.any():
                a[drop] = 0
                changed = True
    return a.astype(bool)


def _prune_corners(s: np.ndarray) -> np.ndarray:
    """Drop the corner pixel of each L step, so that a diagonal step counts once."""
    s = s.copy()
    p = np.pad(s, 1)
    n, so, e, w = p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, 2:], p[1:-1, :-2]
    count = sum(np.roll(np.roll(p, dy, 0), dx, 1)[1:-1, 1:-1].astype(np.int8)
                for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx)  # fmt: skip
    corner = s & (count == 2) & ((n & e) | (e & so) | (so & w) | (w & n))
    s[corner] = False
    return s


def _neighbours(s: np.ndarray) -> np.ndarray:
    p = np.pad(s, 1).astype(np.int8)
    shifted = [np.roll(np.roll(p, dy, 0), dx, 1)[1:-1, 1:-1] for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
    return np.sum(shifted, axis=0)


def _chain_length(s: np.ndarray, res: float) -> float:
    straight = int((s[:, :-1] & s[:, 1:]).sum() + (s[:-1, :] & s[1:, :]).sum())
    d1 = s[:-1, :-1] & s[1:, 1:] & ~s[:-1, 1:] & ~s[1:, :-1]
    d2 = s[:-1, 1:] & s[1:, :-1] & ~s[:-1, :-1] & ~s[1:, 1:]
    return (straight + math.sqrt(2) * int(d1.sum() + d2.sum())) * res


class Centerline(Frozen):
    length: float  # drawing units
    exterior: float
    free_ends: int


def centerline(geom: BaseGeometry, res: float, outside: BaseGeometry | None = None) -> Centerline:
    """The centre line length of a network of thin walls, in the units of `geom`.

    Each piece is turned so that its walls follow the raster grid, drawn at step `res`, and thinned. The chain
    length counts straight steps once and diagonal steps as the square root of two. Thinning stops half a wall
    short of a free end, so each free end gets its distance to the edge back. With `outside` (the area outside
    the floor), a centre line pixel that lies within its half thickness (plus `res`) of it counts as exterior.
    """
    total = exterior = 0.0
    ends = 0
    for piece in _parts(geom):
        angle = dominant_angle(piece)
        origin = piece.centroid
        turned = affinity.rotate(piece, -angle, origin=origin)
        x0, y0, x1, y1 = turned.bounds
        step = max(res, math.sqrt((x1 - x0) * (y1 - y0) / MAX_PIXELS))
        mask, ox, oy = _raster(turned, step)
        skeleton = _prune_corners(_thin(mask))
        length = _chain_length(skeleton, step)
        rows, cols = np.nonzero(skeleton)
        xs = ox + (cols - 1 + 0.5) * step
        ys = oy + (rows - 1 + 0.5) * step
        edge = turned.boundary
        free = _neighbours(skeleton)[rows, cols] == 1
        if free.any():
            length += float(shapely.distance(shapely.points(xs[free], ys[free]), edge).sum())
            ends += int(free.sum())
        total += length
        if outside is not None and len(xs):
            out_turned = affinity.rotate(outside, -angle, origin=origin)
            pts = shapely.points(xs, ys)
            half = shapely.distance(pts, edge)
            near = shapely.distance(pts, out_turned) <= half + 2 * step
            exterior += length * float(near.mean())
    return Centerline(length=total, exterior=exterior, free_ends=ends)


def _on_edge(edge: BaseGeometry, shape: BaseGeometry, tol: float) -> float:
    return float(edge.intersection(shape.buffer(tol)).length)


# ----------------------------------------------------------------------------- measure


def _openings(items: tuple[OpeningIn, ...], unit_m: float) -> list[tuple[OpeningIn, Polygon, float, float]]:
    out = []
    for item in items:
        if len(item.ring) < 3:
            continue
        shape = _polygon((item.ring,))
        long, short = sides(item.ring)
        out.append((item, shape, long * unit_m, short * unit_m))
    return out


def measure(floor: FloorIn, *, walls: bool = True) -> FloorQ:
    """The quantities of one floor. Lengths in metres, areas in square metres."""
    unit = floor.unit_m
    tol = TOUCH_M / unit
    shapes = [_polygon(r.rings) for r in floor.rooms]
    doors = _openings(floor.doors, unit)
    windows = _openings(floor.windows, unit)
    door_rooms: dict[str, list[str]] = {d.entity_id: [] for d, *_ in doors}
    window_rooms: dict[str, list[str]] = {w.entity_id: [] for w, *_ in windows}
    tree = shapely.STRtree(shapes)
    rooms: list[RoomQ] = []
    for i, (room, shape) in enumerate(zip(floor.rooms, shapes, strict=True)):
        edge = shape.boundary
        found: dict[str, list[tuple[str, float]]] = {"door": [], "window": []}
        for kind, items, back in (("door", doors, door_rooms), ("window", windows, window_rooms)):
            for item, opening, width_m, _ in items:
                if opening.distance(shape) > tol:
                    continue
                if _on_edge(edge, opening, tol) * unit >= OPENING_SHARE * width_m:
                    found[kind].append((item.entity_id, round(width_m, 3)))
                    back[item.entity_id].append(room.entity_id)
        near = [shapes[j] for j in tree.query(shape.buffer(tol)) if j != i]
        open_edge = _on_edge(edge, unary_union(near), tol) * unit if near else 0.0
        perimeter = shape.length * unit
        outer = sum(p.exterior.length for p in _parts(shape)) * unit
        door_sum = sum(w for _, w in found["door"])
        baseboard = max(0.0, perimeter - door_sum)
        exterior_ring = room.rings[0] if room.rings else ()
        rooms.append(
            RoomQ(
                entity_id=room.entity_id,
                number=room.number,
                label=room.label,
                kind=room_kind(room.label),
                apartment=room.apartment,
                outdoor=room.outdoor,
                shared=room.shared,
                area_m2=room.area_m2,
                perimeter_m=round(perimeter, 3),
                outer_perimeter_m=round(outer, 3),
                door_ids=tuple(d for d, _ in found["door"]),
                door_widths_m=tuple(w for _, w in found["door"]),
                window_ids=tuple(w for w, _ in found["window"]),
                window_widths_m=tuple(w for _, w in found["window"]),
                open_edge_m=round(open_edge, 3),
                baseboard_m=round(baseboard, 3),
                baseboard_walls_only_m=round(max(0.0, baseboard - open_edge), 3),
                exterior=exterior_ring,
            )
        )
    opening_rows = [
        OpeningQ(entity_id=item.entity_id, kind=item.kind, width_m=round(width, 3), depth_m=round(depth, 3),
                 rooms=tuple((door_rooms if item.kind == "door" else window_rooms)[item.entity_id]), ring=item.ring)
        for items in (doors, windows) for item, _, width, depth in items
    ]  # fmt: skip
    wall_q = None
    if walls and floor.walls:
        pieces = [_polygon(rings) for rings in floor.walls if rings and len(rings[0]) >= 3]
        network = unary_union(pieces + [s for _, s, _, _ in doors] + [s for _, s, _, _ in windows])
        # Close the hairline gaps between an opening box and its wall: each gap would make a loop in the centre line.
        close = CLOSE_M / unit
        network = network.buffer(close, join_style="mitre").buffer(-close, join_style="mitre")
        footprint = unary_union([network, *shapes]).buffer(tol).buffer(-tol)
        filled = unary_union([Polygon(p.exterior) for p in _parts(footprint)])
        bounds = filled.envelope.buffer(10 * tol)
        line = centerline(network, SKELETON_RES_M / unit, outside=bounds.difference(filled))
        wall_q = WallsQ(
            centerline_m=round(line.length * unit, 2),
            exterior_m=round(line.exterior * unit, 2),
            interior_m=round((line.length - line.exterior) * unit, 2),
            footprint_m2=round(network.area * unit * unit, 2),
            pieces=len(_parts(network)),
            free_ends=line.free_ends,
        )
    return FloorQ(
        unit_m=unit,
        rooms=tuple(rooms),
        doors=tuple(o for o in opening_rows if o.kind == "door"),
        windows=tuple(o for o in opening_rows if o.kind == "window"),
        walls=wall_q,
    )


# ----------------------------------------------------------------------------- readers


def _rings_of(geom: BaseGeometry) -> tuple[tuple[XY, ...], ...]:
    parts = _parts(geom)
    if not parts:
        return ()
    main = max(parts, key=lambda p: p.area)
    return (
        tuple((x, y) for x, y, *_ in main.exterior.coords),
        *(tuple((x, y) for x, y, *_ in r.coords) for r in main.interiors),
    )


def _all_rings(geom: BaseGeometry) -> list[tuple[tuple[XY, ...], ...]]:
    return [
        (
            tuple((x, y) for x, y, *_ in part.exterior.coords),
            *(tuple((x, y) for x, y, *_ in r.coords) for r in part.interiors),
        )
        for part in _parts(geom)
    ]


def swiss_floor(page: PdfPage, plan: swiss_plan.SwissPlan) -> FloorIn | None:
    """The rooms, walls, doors and windows of a Swiss plan page, in PDF points. None without a scale.

    The entity ids are those of `bp.facts_swiss`: `room:<number>`, `door:<n>` (each door place once, in drawing
    order) and `window:<n>` (each window box once, in drawing order).
    """
    from bp.tools import swiss_plan as sp  # noqa: PLC0415 - the PDF reader is only needed here

    if plan.scale is None:
        return None
    cut = plan.title_cut
    fills = [p for p in page.paths if p.bbox[1] <= cut and sp._is_room_fill(p) and p.fill is not None]  # noqa: SLF001
    nets = sp.net_holes([sp.path_area_shape(p) for p in fills])
    by_exterior = {sp._exterior(n): n for n in nets}  # noqa: SLF001
    rooms = []
    for r in plan.rooms:
        net = by_exterior.get(r.polygon)
        if net is None:
            continue
        rooms.append(RoomIn(entity_id=sp.room_id(r.number), number=r.number, label=r.label, apartment=r.apartment,
                            outdoor=r.outdoor, shared=r.fill == sp.SHARED_FILL, area_m2=r.area_m2,
                            rings=_rings_of(net)))  # fmt: skip
    quads = {
        tuple(round(v, 1) for v in p.bbox): p
        for p in page.paths
        if p.bbox[1] <= cut and sp._near(p.stroke, sp.DOOR_STROKE) and p.count("q")  # noqa: SLF001
    }
    seen: list[tuple[float, ...]] = []
    for e in plan.doors.evidence:  # the order of the door entities in the facts
        key = tuple(round(v, 1) for pt in e.points for v in pt)
        if key not in seen:
            seen.append(key)
    doors = tuple(
        OpeningIn(entity_id=f"door:{n}", kind="door", ring=tuple(quads[key].rings[0]))
        for n, key in enumerate(seen, start=1)
        if key in quads and quads[key].rings
    )
    boxes = {p.bbox: p for p in page.paths if p.bbox[1] <= cut and sp._is_box(p)}  # noqa: SLF001
    windows = []
    for n, f in enumerate((f for f in plan.fixtures if f.kind == "window"), start=1):
        box_path = boxes.get(f.bbox)
        ring = tuple(box_path.rings[0]) if box_path is not None and box_path.rings else (
            (f.bbox[0], f.bbox[1]), (f.bbox[2], f.bbox[1]), (f.bbox[2], f.bbox[3]), (f.bbox[0], f.bbox[3]))
        windows.append(OpeningIn(entity_id=f"window:{n}", kind="window", ring=ring))
    walls = [
        sp.path_area_shape(p)
        for p in page.paths
        if p.bbox[1] <= cut
        and p.stroke == (0.0, 0.0, 0.0)
        and abs(p.width - WALL_STROKE) < WALL_STROKE_TOL
        and len(p.points) >= 3
        and (p.bbox[2] - p.bbox[0]) < FRAME_SHARE * page.width
    ]
    return FloorIn(
        unit_m=plan.scale.metres_per_point,
        rooms=tuple(rooms),
        doors=doors,
        windows=tuple(windows),
        walls=tuple(r for w in walls for r in _all_rings(w)),
    )


def _dxf_walls(path: str | Path) -> list[BaseGeometry]:
    """The walls of a DXF: the ANSI31 hatches of layer WALL, their boundary loops joined by the even-odd rule.

    The WALL layer also holds the railings, as SOLID hatches; those are not walls. A drawing with no ANSI31 hatch
    falls back to the closed WALL polylines, nested by the even-odd rule.
    """
    import ezdxf  # noqa: PLC0415

    space = ezdxf.readfile(str(path)).modelspace()
    out: list[BaseGeometry] = []
    for hatch in space.query('HATCH[layer=="WALL"]'):
        if str(hatch.dxf.pattern_name).upper() != "ANSI31":
            continue
        shape: BaseGeometry | None = None
        for loop in hatch.paths:  # ty: ignore[missing-attribute]
            vertices = getattr(loop, "vertices", None)
            if not vertices or len(vertices) < 3:
                continue
            ring = Polygon([(float(v[0]), float(v[1])) for v in vertices]).buffer(0)
            shape = ring if shape is None else shape.symmetric_difference(ring)
        if shape is not None and not shape.is_empty:
            out.append(shape)
    if out:
        return out
    rings = []
    for entity in space.query('LWPOLYLINE[layer=="WALL"]'):
        points = [(float(p[0]), float(p[1])) for p in entity.get_points()]  # ty: ignore[missing-attribute]
        if len(points) >= 3:
            rings.append(Polygon(points).buffer(0))
    rings.sort(key=lambda g: -g.area)
    for ring in rings:
        depth = sum(1 for other in rings if other.area > ring.area and other.buffer(1e-6).contains(ring))
        if depth % 2 == 0:
            out.append(ring)
        else:
            holder = min((i for i, o in enumerate(out) if o.buffer(1e-6).contains(ring)),
                         key=lambda i: out[i].area, default=None)  # fmt: skip
            if holder is not None:
                out[holder] = out[holder].difference(ring)
    return out


def _first_of_place(rings: tuple[tuple[XY, ...], ...]) -> set[int]:
    """The 1-based indexes of the rings that are the first at their place: the drawing stacks copies."""
    seen: set[tuple[float, ...]] = set()
    out: set[int] = set()
    for n, ring in enumerate(rings, start=1):
        if len(ring) < 3:
            continue
        key = tuple(round(v, 2) for v in Polygon(ring).bounds)
        if key not in seen:
            seen.add(key)
            out.add(n)
    return out


def dxf_floor(path: str | Path, plan: dxf_plan.DxfPlan) -> FloorIn | None:
    """The rooms, walls, doors and windows of a DXF floor plan, in drawing units. None without a known unit.

    Entity ids as in `bp.facts_models.dxf_facts`: `dxf_plan.room_ids`, `door:<n>` and `window:<n>`. A room outline
    without a number (a shaft or a void) is a hole of the numbered outline that holds it.
    """
    from bp.tools import dxf_plan as dp  # noqa: PLC0415

    if plan.unit_m is None:
        return None
    ids = dp.room_ids(plan)
    first = _first_of_place(plan.windows)
    outlines = [_polygon((r.points,)) for r in plan.rooms]
    rooms = []
    for i, (r, outline) in enumerate(zip(plan.rooms, outlines, strict=True)):
        if not r.number:
            continue
        net = outline
        grown = outline.buffer(1e-6)
        for j, other in enumerate(outlines):
            if j != i and other.area < outline.area and grown.contains(other):
                net = net.difference(other)
        rooms.append(RoomIn(entity_id=ids[i], number=r.number, label=r.label, apartment=r.unit, outdoor=r.outdoor,
                            shared=r.unit is None, area_m2=round(net.area * plan.unit_m**2, 2),
                            rings=_rings_of(net)))  # fmt: skip
    return FloorIn(
        unit_m=plan.unit_m,
        rooms=tuple(rooms),
        doors=tuple(OpeningIn(entity_id=f"door:{n}", kind="door", ring=ring)
                    for n, ring in enumerate(plan.doors, start=1)),
        windows=tuple(OpeningIn(entity_id=f"window:{n}", kind="window", ring=ring)
                      for n, ring in enumerate(plan.windows, start=1) if n in first),
        walls=tuple(r for w in _dxf_walls(path) for r in _all_rings(w)),
    )  # fmt: skip


