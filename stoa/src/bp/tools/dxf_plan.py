"""Read a CAD floor plan (DXF) by its layers: room outlines, room texts, doors, windows, unit outlines."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import ezdxf
import ezdxf.layouts
from pydantic import Field
from shapely.geometry import Point, Polygon

from bp.contract import Frozen

_AREA = re.compile(r"^(\d+(?:[.,]\d+)?)\s*m(?:²|2)$")
_NUMBER = re.compile(r"^(U\d+\.)?\d+\.\d+$|^U\d+\.\d+$")
_UNIT_TAG = re.compile(r"^(?:Whg\.|App\.)\s*([A-Z]+)$")
OUTDOOR = frozenset(
    {
        "balkon",
        "balcon",
        "balcone",
        "loggia",
        "terrasse",
        "terrazza",
        "sitzplatz",
        "patio",
        "garten",
        "jardin",
        "giardino",
    }
)
TOUCH_M = 0.06  # an opening belongs to a room when it lies within 6 cm of the room polygon
# One drawing unit in metres, by the $INSUNITS code of the DXF header.
_UNIT_M = {1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0}


class DxfRoom(Frozen):
    number: str | None
    label: str | None
    printed_area_m2: float | None
    area_m2: float
    unit: str | None  # the apartment whose outline holds the room
    outdoor: bool  # a balcony, loggia or terrace, by its label
    windows: int  # window outlines that touch the room
    doors: int  # distinct door openings that touch the room
    points: tuple[tuple[float, float], ...]


class DxfText(Frozen):
    text: str
    x: float  # drawing units, Y up
    y: float
    room: int | None  # the index of the room outline that holds the text


class DxfPlan(Frozen):
    unit_m: float | None  # None when the header gives no known unit
    layers: dict[str, int]
    rooms: tuple[DxfRoom, ...]
    units: tuple[str, ...]
    texts_outside_rooms: tuple[str, ...]
    # For the facts of the drawing: every text with its place, and the outlines of the distinct doors and windows.
    texts: tuple[DxfText, ...] = ()
    doors: tuple[tuple[tuple[float, float], ...], ...] = ()
    windows: tuple[tuple[tuple[float, float], ...], ...] = ()
    unit_outlines: dict[str, tuple[tuple[float, float], ...]] = Field(default_factory=dict)  # letter: its outline


def room_ids(plan: DxfPlan) -> list[str]:
    """The entity id of each room, in the order of `plan.rooms`: `room:<number>`, else `room:outline:<index>`."""
    numbers = Counter(r.number for r in plan.rooms if r.number)
    return [
        f"room:{r.number}" if r.number and numbers[r.number] == 1 else f"room:outline:{i}"
        for i, r in enumerate(plan.rooms)
    ]


def apartment_id(letter: str) -> str:
    return f"apartment:{letter}"


def _ring(polygon: Polygon) -> tuple[tuple[float, float], ...]:
    return tuple((round(x, 3), round(y, 3)) for x, y in polygon.exterior.coords)


def is_dxf(path: str | Path) -> bool:
    try:
        with Path(path).open("rb") as handle:
            head = handle.read(2048)
    except OSError:
        return False
    return b"SECTION" in head and b"\n" in head and not head.startswith((b"%PDF", b"ISO-10303"))


def _polygons(space: ezdxf.layouts.Modelspace, layer: str) -> list[Polygon]:
    out: list[Polygon] = []
    for entity in space.query(f'LWPOLYLINE[layer=="{layer}"]'):
        points = [(float(p[0]), float(p[1])) for p in entity.get_points()]  # ty: ignore[missing-attribute]
        if len(points) >= 3:
            polygon = Polygon(points)
            out.append(polygon if polygon.is_valid else polygon.buffer(0))
    return out


def read_dxf(path: str | Path) -> DxfPlan:
    document = ezdxf.readfile(str(path))
    space = document.modelspace()
    unit_m = _UNIT_M.get(int(document.header.get("$INSUNITS", 0)))
    scale = (unit_m or 1.0) ** 2
    layers = Counter(str(entity.dxf.layer) for entity in space)
    outlines = _polygons(space, "ROOM_OUTLINE")
    unit_outlines = _polygons(space, "UNIT_OUTLINE")
    texts = [
        (str(e.dxf.text).strip(), Point(float(e.dxf.insert[0]), float(e.dxf.insert[1]))) for e in space.query("TEXT")
    ]
    unit_tags = [(m.group(1), at) for text, at in texts if (m := _UNIT_TAG.match(text))]
    unit_of_outline: dict[int, str] = {}
    for letter, at in unit_tags:
        holders = [i for i, outline in enumerate(unit_outlines) if outline.contains(at)]
        if holders:
            unit_of_outline[min(holders, key=lambda i: unit_outlines[i].area)] = letter
    touch = TOUCH_M / (unit_m or 1.0)
    windows = _polygons(space, "WINDOW")
    seen: set[tuple[float, ...]] = set()
    doors: list[Polygon] = []
    for door in _polygons(space, "DOOR"):
        key = tuple(round(v, 2) for v in door.bounds)
        if key not in seen:
            seen.add(key)
            doors.append(door)
    used: set[int] = set()
    room_of_text: dict[int, int] = {}
    rooms: list[DxfRoom] = []
    for index, outline in enumerate(outlines):
        inside = [(i, text) for i, (text, at) in enumerate(texts) if outline.contains(at)]
        # A text belongs to the smallest outline that holds it.
        mine = [
            (i, text)
            for i, text in inside
            if not any(o.contains(texts[i][1]) and o.area < outline.area for o in outlines if o is not outline)
        ]
        used.update(i for i, _ in mine)
        room_of_text.update((i, index) for i, _ in mine)
        number = next((t for _, t in mine if _NUMBER.match(t)), None)
        printed = next((float(m.group(1).replace(",", ".")) for _, t in mine if (m := _AREA.match(t))), None)
        label = next(
            (t for _, t in mine if not _NUMBER.match(t) and not _AREA.match(t) and not _UNIT_TAG.match(t)), None
        )
        centre = outline.representative_point()
        holders = [i for i, unit in enumerate(unit_outlines) if unit.contains(centre)]
        unit = unit_of_outline.get(min(holders, key=lambda i: unit_outlines[i].area)) if holders else None
        rooms.append(
            DxfRoom(
                number=number,
                label=label,
                printed_area_m2=printed,
                area_m2=round(outline.area * scale, 2),
                unit=unit,
                outdoor=(label or "").strip().lower() in OUTDOOR,
                windows=sum(1 for w in windows if w.distance(outline) <= touch),
                doors=sum(1 for d in doors if d.distance(outline) <= touch),
                points=_ring(outline),
            )
        )
    outside = tuple(text for i, (text, _) in enumerate(texts) if i not in used)
    outlined = {letter: _ring(unit_outlines[i]) for i, letter in unit_of_outline.items()
                if isinstance(unit_outlines[i], Polygon)}  # fmt: skip
    return DxfPlan(
        unit_m=unit_m,
        layers=dict(layers),
        rooms=tuple(rooms),
        units=tuple(sorted({letter for letter, _ in unit_tags})),
        texts_outside_rooms=outside[:60],
        texts=tuple(
            DxfText(text=text, x=round(at.x, 3), y=round(at.y, 3), room=room_of_text.get(i))
            for i, (text, at) in enumerate(texts)
        ),
        doors=tuple(_ring(d) for d in doors if isinstance(d, Polygon)),
        windows=tuple(_ring(w) for w in windows if isinstance(w, Polygon)),
        unit_outlines=outlined,
    )
