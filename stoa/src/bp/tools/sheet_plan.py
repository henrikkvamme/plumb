"""One large sheet as a plan: its scale, its door swings and its rooms, each computed once.

The agent tools and the document facts read the same object, so a room has one area and one id in both.
The ids are stable for one image: they hold the position of the thing in page pixels.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING

import cv2
import numpy as np

from bp.contract import Check
from bp.tools import sheet_doors, sheet_geometry, sheet_rooms, sheet_scan, sheet_text

if TYPE_CHECKING:
    from bp.contract import Calibration
    from bp.tools.ocr import TextLine
    from bp.tools.sheet_text import Label

ROOM_NAME = re.compile(r"[A-Za-z][A-Za-z'&/().,\- ]{3,}(?: ?\d{1,2})?")  # also "STAIR 2"
# Rooms that stall partitions, fixtures or stair flights divide: the fill finds only a part of the floor.
DIVIDED = re.compile(
    r"\b(MEN'?S?|WOMEN'?S?|LATRINES?|TOILETS?|SHOWE?RS?|SHOW|RESTROOMS?|RR|LAV(?:ATORY)?|LOCKERS?|WC|STAIRS?)\b",
    re.IGNORECASE,
)
STRONG_WITNESSES = 5  # dimension lines that agree: from here the scale is as sure as it gets


_PLANS: dict[tuple[str, str], SheetPlan] = {}
KEEP_PLANS = 3


def plan_for(rgb: np.ndarray, lines: list[TextLine], calibration: Calibration | None = None) -> SheetPlan:
    """The plan of this image with this calibration. The agent tools and the facts of one document share it."""
    key = (sheet_text.pixel_key(rgb), calibration.model_dump_json() if calibration else "")
    if key not in _PLANS:
        while len(_PLANS) >= KEEP_PLANS:
            _PLANS.pop(next(iter(_PLANS)))
        _PLANS[key] = SheetPlan(rgb, lines, sheet_text.labels(lines), calibration)
    return _PLANS[key]


def label_id(label: Label) -> str:
    return f"label:{label.at[0]}:{label.at[1]}"


def room_id(label: Label) -> str:
    return f"room:{label.at[0]}:{label.at[1]}"


def door_id(swing: sheet_rooms.Swing) -> str:
    return f"door:{round(swing.centre[0])}:{round(swing.centre[1])}"


@dataclass(frozen=True)
class PlanScale:
    ppm: float  # pixels per metre
    source: str  # "user", "dimension lines", "printed scale and doors"
    detail: str
    check: Check
    measured: sheet_geometry.DimensionScale | None  # the dimension lines of the sheet, also when the user gave a scale


@dataclass(frozen=True)
class PlanRoom:
    label: Label
    room: sheet_rooms.Room | None
    shares_with: tuple[str, ...]  # other room names in the same white region: no wall between them
    why_not: str  # why there is no area, or ""

    @property
    def closed(self) -> bool:
        return self.room is not None and not self.shares_with


@dataclass
class SheetPlan:
    rgb: np.ndarray
    lines: list[TextLine]
    labels: list[Label]
    calibration: Calibration | None = None
    _rooms: dict[str, PlanRoom] | None = field(default=None, repr=False)

    @cached_property
    def gray(self) -> np.ndarray:
        return cv2.cvtColor(np.ascontiguousarray(self.rgb), cv2.COLOR_RGB2GRAY)

    @cached_property
    def scan(self) -> bool:
        """True when the paper is not white: a scan or a photo of a print, not a render of a vector PDF."""
        return sheet_scan.is_scan(self.gray)

    @cached_property
    def measured(self) -> sheet_geometry.DimensionScale | None:
        return sheet_geometry.dimension_scale(self.rgb, self.lines)

    def _doors(self, ppm: float, found: list[sheet_rooms.Swing] | None = None) -> list[sheet_rooms.Swing]:
        """The door leaves at this scale: from the trained detector when it has seen the sheet, else from the arcs."""
        seen = sheet_doors.detected(sheet_text.pixel_key(self.rgb))
        if seen is None:
            return found if found is not None else sheet_rooms.door_swings(self.gray, ppm)
        low, high = sheet_rooms.LEAF_M  # a locker or a cabinet has a swing too, with a shorter leaf
        return [s for s in seen if low <= s.radius_px / ppm <= high]

    @cached_property
    def _scale_and_swings(self) -> tuple[PlanScale | None, list[sheet_rooms.Swing]]:
        given = self.calibration
        if given and given.points and given.real_length_m and given.real_length_m > 0:
            (ax, ay), (bx, by) = given.points
            pixels = math.hypot(bx - ax, by - ay)
            if pixels >= 2:
                ppm = pixels / given.real_length_m
                detail = f"{given.real_length_m:g} m between two points that the user marked"
                check = Check(id="scale", label="Scale from the user", state="pass", detail=detail, factor=0.95)
                return PlanScale(ppm, "user", detail, check, None), self._doors(ppm)
        user_ratio = round(given.scale_ratio) if given and given.scale_ratio else None
        # One length that is drawn many times (a bed module in a detail) can be from another drawing on the sheet:
        # the dimension lines count only when two different lengths agree.
        varied = self.measured is not None and len({round(w.metres, 2) for w in self.measured.witnesses}) >= 2
        if user_ratio is None and self.measured is not None and varied:
            found = self.measured
            strong = found.agreeing >= STRONG_WITNESSES
            detail = f"{found.agreeing} of {found.read} dimension lines agree within {100 * found.spread:.1f}%"
            check = Check(id="scale", label="Scale from dimension lines", state="pass" if strong else "warn",
                          detail=detail, factor=0.97 if strong else 0.9)  # fmt: skip
            swings = sheet_rooms.door_swings(self.gray, found.ppm)
            seen = sheet_doors.detected(sheet_text.pixel_key(self.rgb))
            # On a scan the arc finder sees no doors, so the size check would pass without a witness: the leaves of
            # the trained detector are the witness there. Their size in pixels does not depend on the scale.
            witness = seen if len(swings) < sheet_rooms.MIN_DOORS and seen is not None else swings
            if strong or sheet_rooms.doors_fit(witness, found.ppm):
                return PlanScale(found.ppm, "dimension lines", detail, check, found), self._doors(found.ppm, swings)
            # few dimension lines, and the door leaves do not have the size of a door at this scale: the dimension
            # lines were read wrong. Many lines that agree are stronger than the door sizes: a dormitory has many
            # narrow doors. No scale then: the printed ratio is often that of a key plan or a detail (a dormitory
            # sheet prints 1:360 for its key plan): on 4 val sheets it gave a scale 2 to 5 times off the dimension lines.
            return None, []
        ratios = {user_ratio} if user_ratio else {s.ratio for s in sheet_text.printed_scales(self.lines)}
        if len(ratios) == 1:
            ratio = ratios.pop()
            seen = sheet_doors.detected(sheet_text.pixel_key(self.rgb))
            confirmed = None
            if self.scan and seen is not None:
                # A scan: the arc finder sees few doors there, and noise can give it a few arcs of a wrong size.
                # The detector reads scans.
                confirmed = sheet_rooms.scale_from_detected(seen, ratio)
            if confirmed is None:
                confirmed = sheet_rooms.scale_from_doors(self.gray, ratio)
            if confirmed is None and seen is not None:
                confirmed = sheet_rooms.scale_from_detected(seen, ratio)
            if confirmed is not None:
                ppm, swings = confirmed
                whose = "from the user" if user_ratio else "printed on the sheet"
                detail = f"1:{ratio} {whose}; {len(swings)} doors have the size of a common door at this resolution"
                check = Check(id="scale", label="Scale ratio, confirmed by door sizes", state="warn", detail=detail,
                              factor=0.9)  # fmt: skip
                source = "user" if user_ratio else "printed scale and doors"
                return PlanScale(ppm, source, detail, check, None), self._doors(ppm, swings)
        return None, []

    @property
    def scale(self) -> PlanScale | None:
        return self._scale_and_swings[0]

    @property
    def swings(self) -> list[sheet_rooms.Swing]:
        return self._scale_and_swings[1]

    @cached_property
    def second_swings(self) -> list[sheet_rooms.Swing] | None:
        """The door leaves of the second detector at the scale of the plan, or None when it has not seen the sheet."""
        scale = self.scale
        seen = sheet_doors.detected(sheet_text.pixel_key(self.rgb), cache=sheet_doors.SECOND)
        if scale is None or seen is None:
            return None
        low, high = sheet_rooms.LEAF_M
        return [s for s in seen if low <= s.radius_px / scale.ppm <= high]

    @cached_property
    def arc_swings(self) -> list[sheet_rooms.Swing]:
        """The swings from the arcs of the drawing, for the room fill.

        The fill closes its door openings with these: the points of the detector are a few pixels off, and one room
        on the dev sheets got a wrong area with them.
        """
        scale = self.scale
        if scale is None:
            return []
        if sheet_doors.detected(sheet_text.pixel_key(self.rgb)) is None:
            return self.swings
        return sheet_rooms.door_swings(self.gray, scale.ppm)

    @cached_property
    def walls(self) -> np.ndarray:
        scale = self.scale
        assert scale is not None
        if self.scan:  # only the solid ink of a wall: blur makes thick bands of thin double lines
            ink = sheet_rooms.room_barriers(sheet_scan.levelled(self.gray), self.arc_swings,
                                            round(sheet_scan.WALL_SHARE * 255))  # fmt: skip
        else:
            ink = sheet_rooms.room_barriers(self.gray, self.arc_swings)
        return sheet_rooms.wall_barriers(ink, scale.ppm)

    def room_labels(self) -> list[Label]:
        return [lb for lb in self.labels if ROOM_NAME.fullmatch(lb.text.strip())]

    def rooms(self) -> dict[str, PlanRoom]:
        """Each label that reads as a name, with the room around it. Keyed by the room id."""
        if self._rooms is not None:
            return self._rooms
        scale = self.scale
        if scale is None:
            return {}
        names = self.room_labels()
        boxes = [(round(lb.bbox[0]), round(lb.bbox[1]), round(lb.bbox[2]), round(lb.bbox[3])) for lb in names]
        found = sheet_rooms.rooms_at(self.walls, boxes, scale.ppm)
        by_region: dict[int, list[Label]] = {}
        for label, (_, region) in zip(names, found, strict=True):
            by_region.setdefault(region, []).append(label)
        out: dict[str, PlanRoom] = {}
        for label, (room, region) in zip(names, found, strict=True):
            others = tuple(
                o.text for o in by_region[region] if o is not label and o.height >= 0.8 * label.height
            )  # smaller text in a room is a note or an equipment name, not the next room
            why = ""
            if room is None:
                why = "the walls around this label are not closed"
            elif others:
                why = f"no wall between this label and {list(others[:5])}"
            out[room_id(label)] = PlanRoom(label, room, others, why)
        self._rooms = out
        return out

    def room_of(self, label: Label) -> PlanRoom | None:
        """The room around one label. A label that does not read as a name ("TR", "JAN") is filled on request."""
        known = self.rooms().get(room_id(label))
        scale = self.scale
        if known is not None or scale is None:
            return known
        box = (round(label.bbox[0]), round(label.bbox[1]), round(label.bbox[2]), round(label.bbox[3]))
        room, _ = sheet_rooms.rooms_at(self.walls, [box], scale.ppm)[0]
        if room is None:
            return PlanRoom(label, None, (), "the walls around this label are not closed")
        others = tuple(
            o.label.text
            for o in self.rooms().values()
            if o.label.height >= 0.8 * label.height and room.holds(o.label.at[0], o.label.at[1])
        )
        return PlanRoom(label, room, others, f"no wall between this label and {list(others[:5])}" if others else "")
