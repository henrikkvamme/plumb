"""The facts of the contractor quantities: perimeter and baseboard of each room, and the wall centre line of a floor.

The values are those of the agent tools (`bp.solvers.quantity_tools`), so an answer from a tool row finds its margin
here. Rates and margins are from the held-out quantities bench (`experiments/tools/quantities.json`, val partition).
A failure here leaves the other facts as they are: the quantities are added only when they are measured.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from bp import rates
from bp.facts import Entity, Fact, rated
from bp.rates import Rate
from bp.solvers.quantity_tools import (
    BASEBOARD_RULE,
    ROOM_MARGIN_BASIS,
    ROOM_MARGIN_COVER,
    ROOM_MARGIN_SHARE,
    WALL_MARGIN_BASIS,
    WALL_MARGIN_SHARE,
    WALL_RULE,
)
from bp.tools import quantities as q

if TYPE_CHECKING:
    from pathlib import Path

    from bp.tools import dxf_plan, swiss_plan
    from bp.tools.pdf_text import PdfPage

ROOM_LENGTH = Rate(confidence=0.999, basis="perimeter and baseboard agreed with the DXF within 2% on all 5,577 "
                   "held-out rooms")  # fmt: skip
ROOM_DOORS = Rate(confidence=0.999, basis="door openings per room agreed with the DXF on all 5,577 held-out rooms")
WALL_LENGTH = Rate(confidence=0.97, basis="204 of 210 held-out floors within 2% of the wall centre line of the CAD "
                   "source")  # fmt: skip
WALL_EXTERIOR = Rate(confidence=0.9, basis="188 of 210 held-out floors within 2% of the exterior wall centre line of "
                     "the CAD source")  # fmt: skip
EXTERIOR_MARGIN_SHARE = 0.02
EXTERIOR_MARGIN_BASIS = "9 of 10 of 210 held-out floors within 2% of the exterior wall centre line of the CAD source"

Facts = tuple[dict[str, tuple[Fact, ...]], list[Fact], list[Entity]]


def floor_facts(floor: q.FloorQ | None) -> Facts:
    """Facts per room id, summary facts, and a `walls` entity (a box around the rooms) that holds the wall facts."""
    if floor is None:
        return {}, [], []
    rooms: dict[str, tuple[Fact, ...]] = {}
    for r in floor.rooms:
        rooms[r.entity_id] = (
            rated("perimeter", round(r.perimeter_m, 2), ROOM_LENGTH,
                  rates.relative(r.perimeter_m, ROOM_MARGIN_SHARE, ROOM_MARGIN_COVER, ROOM_MARGIN_BASIS, floor=0.01),
                  unit="m", source="edge of the net room polygon"),
            rated("baseboard", round(r.baseboard_m, 2), ROOM_LENGTH,
                  rates.relative(r.baseboard_m, ROOM_MARGIN_SHARE, ROOM_MARGIN_COVER, ROOM_MARGIN_BASIS, floor=0.01),
                  unit="m", source="perimeter minus door openings", note=BASEBOARD_RULE),
            rated("door_openings", len(r.door_ids), ROOM_DOORS, source="door openings in the room edge"),
        )  # fmt: skip
    walls = floor.walls
    if walls is None:
        return rooms, [], []
    facts = [
        rated("wall_centerline", walls.centerline_m, WALL_LENGTH,
              rates.relative(walls.centerline_m, WALL_MARGIN_SHARE, 0.9, WALL_MARGIN_BASIS, floor=0.01),
              unit="m", source="centre line of the wall network, openings filled", note=WALL_RULE),
        rated("wall_exterior", walls.exterior_m, WALL_EXTERIOR,
              rates.relative(walls.exterior_m, EXTERIOR_MARGIN_SHARE, 0.9, EXTERIOR_MARGIN_BASIS, floor=0.01),
              unit="m", source="centre line of the walls on the outer edge of the floor"),
    ]  # fmt: skip
    points = [p for r in floor.rooms for p in r.exterior]
    entities = []
    if points:
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        entities.append(Entity(id="walls", kind="element", group="walls", label="Walls of the floor", geometry="box",
                               points=((min(xs), min(ys)), (max(xs), max(ys))), facts=tuple(facts)))  # fmt: skip
    return rooms, facts, entities


def with_room_facts(entities: dict[str, Entity], extra: dict[str, tuple[Fact, ...]]) -> dict[str, Entity]:
    """The room entities with the quantity facts of each added."""
    return {k: e.model_copy(update={"facts": (*e.facts, *extra[k])}) if k in extra else e for k, e in entities.items()}


def swiss(page: PdfPage, plan: swiss_plan.SwissPlan) -> Facts:
    with contextlib.suppress(Exception):
        floor = q.swiss_floor(page, plan)
        return floor_facts(q.measure(floor) if floor is not None else None)
    return {}, [], []


def dxf(path: str | Path, plan: dxf_plan.DxfPlan) -> Facts:
    with contextlib.suppress(Exception):
        floor = q.dxf_floor(path, plan)
        return floor_facts(q.measure(floor) if floor is not None else None)
    return {}, [], []
