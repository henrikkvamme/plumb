"""Which door or window belongs to which room on a raster plan: boxes of a symbol detector against room shapes.

A box touches a room when the box, grown by `REACH_M`, overlaps the room by at least `MIN_OVERLAP_M2`. A door box
holds the gap in the wall and the swing, so it touches the room on each side of the wall. A window box lies in the
outer wall and touches the room behind it. With the true boxes and the true room polygons of the Swiss floors the
rule gives the right count for 99 % of the rooms (`jobs/cubicasa-detect/eval_styles.py`, column `rule`).

The count of a room is `sure` when no box near the detector threshold touches it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from shapely.geometry import Polygon, box

if TYPE_CHECKING:
    from collections.abc import Sequence

    from shapely.geometry.base import BaseGeometry

    from bp.tools.symbol_detector import Detection

REACH_M = 0.10
MIN_OVERLAP_M2 = 0.02
DOOR_LEAF_M = 0.85  # a typical door leaf: gives a scale when the plan has none


@dataclass(frozen=True)
class RoomOpenings:
    count: int
    sure: bool
    boxes: tuple[tuple[float, float, float, float], ...]


def shape_of(points: Sequence[Sequence[float]]) -> BaseGeometry:
    shape = Polygon(points)
    return shape if shape.is_valid else shape.buffer(0)


def touches(b: Sequence[float], room: BaseGeometry, ppm: float, reach_m: float = REACH_M) -> bool:
    reach = reach_m * ppm
    grown = box(b[0] - reach, b[1] - reach, b[2] + reach, b[3] + reach)
    return grown.intersects(room) and grown.intersection(room).area >= MIN_OVERLAP_M2 * ppm * ppm


def door_scale(detections: Sequence[Detection], threshold: float) -> float | None:
    """Pixels per metre from the median door box (its long side is about one leaf). None with under 3 doors."""
    sides = sorted(max(d.box[2] - d.box[0], d.box[3] - d.box[1]) for d in detections
                   if d.label == "door" and d.score >= threshold)  # fmt: skip
    if len(sides) < 3:
        return None
    return sides[len(sides) // 2] / DOOR_LEAF_M


def room_openings(
    rooms: Sequence[BaseGeometry], detections: Sequence[Detection], label: str, threshold: float, band: float,
    ppm: float, reach_m: float = REACH_M,
) -> list[RoomOpenings]:  # fmt: skip
    """For each room: the boxes of `label` at or above the threshold that touch it."""
    mine = [d for d in detections if d.label == label and d.score >= threshold - band]
    out = []
    for room in rooms:
        near = [d for d in mine if touches(d.box, room, ppm, reach_m)]
        firm = [d for d in near if d.score >= threshold]
        doubt = any(d.score < threshold + band for d in near)
        out.append(RoomOpenings(count=len(firm), sure=not doubt, boxes=tuple(d.box for d in firm)))
    return out
