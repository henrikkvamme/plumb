"""The facts of a BIM model (IFC), a CAD plan (DXF) and a small raster plan, from the same readers as the agent tools.

Each builder reads the document with the reader that the agent solver uses (`ifc_model`, `dxf_plan`,
`raster_tools.read_small`), so a fact and an answer agree. The entity ids are the ids that the agent tools put in
their rows (`entity_id`):

- IFC: `space:<name>` (`space:<name>@<GlobalId>` when the name repeats or is empty), `storey:<name>`,
  `door:<GlobalId>`, `window:<GlobalId>`. The label of a space is its IFC Name (its LongName when the Name is
  empty), so the 3D view finds it by name.
- DXF: `room:<number>` (`room:outline:<index>` when the number is missing or repeats), `apartment:<letter>`,
  `door:<n>`, `window:<n>` (from 1), `label:<x>:<y>`. Points are in metres from the top left corner of the drawing,
  with Y down: x = (X - min X) * unit, y = (max Y - Y) * unit.
- Small raster: `room:<number>` (`room:<number>@<x>:<y>` on a repeat), `room:<x>:<y>` (a room name with no number
  on a plan with no scale), `room:<kind>:<cx>:<cy>` (a room the symbol detector marks), `apartment:<letter>`,
  `<class>:<cx>:<cy>` for a detector box (door, window, toilet, sink, shower, bathtub) and `scale`. Points are
  source pixels.

Every confidence comes from a benchmark file named at its rate, or from `unmeasured(...)`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bp.contract import Conflict
from bp.facts import RASTER_SUFFIXES, DocumentFacts, Entity, Fact, Page, rated
from bp.rates import Margin, Rate, relative, sum_margin, unmeasured
from bp.tools import dxf_plan, ifc_model

if TYPE_CHECKING:
    import numpy as np

    from bp.contract import Calibration
    from bp.solvers.cubicasa_detect import CubicasaDetectSolver
    from bp.solvers.raster_tools import SmallRaster
    from bp.tools.raster_rooms import RasterPlan

Point = tuple[float, float]

# ----------------------------------------------------------------------------- IFC
# Sources: experiments/tools/ifc.json (dev) and experiments/tools/ifc-val.json (val). Every ifc_model family was
# right on every test question.

# area_room: 691 of 691 (dev, via_pdf), 21 of 21 (val, ifc) and 186 of 186 (val, via_pdf)
IFC_AREA = Rate(confidence=0.999, basis="the space areas of the model answered 898 of 898 test questions right")
# count_model: 16 + 45 (dev) and 14 + 24 (val), all right
IFC_COUNT = Rate(confidence=0.999, basis="element counts of the model answered 99 of 99 test questions right")
# count_storey: 126 (dev, via_pdf), 6 (val, ifc) and 36 (val, via_pdf), all right
IFC_STOREY_COUNT = Rate(confidence=0.999, basis="counts per storey answered 168 of 168 test questions right")
# area_total_storey: 21 (dev), 3 and 11 (val), all right
IFC_STOREY_AREA = Rate(confidence=0.999, basis="storey floor areas answered 35 of 35 test questions right")
# The 898 area questions above find each space by its name, so a wrong name would have failed them.
IFC_NAME = Rate(confidence=0.999, basis="as the model gives it; 898 of 898 test questions found their space by name")
IFC_GEOMETRY_AREA = unmeasured("space areas from the footprint of the geometry (used when the model gives no area)")

PLURAL: dict[str, str] = {
    "door": "doors", "window": "windows", "wall": "walls", "space": "spaces", "column": "columns",
    "beam": "beams", "stair": "stairs", "slab": "slabs", "sanitary": "sanitary_terminals", "light": "lights",
}  # fmt: skip
MAX_ELEMENTS = 5000  # door and window entities of one model


def _is_ifc(path: str | Path) -> bool:
    with Path(path).open("rb") as handle:
        return handle.read(64).startswith(b"ISO-10303-21")


def _space(info: ifc_model.SpaceInfo, entity_id: str, label: str) -> Entity:
    source = "IfcSpace"
    facts = [rated("name", info.name or None, IFC_NAME, source=source)]
    if info.long_name:
        facts.append(rated("long_name", info.long_name, IFC_NAME, source=source))
    facts.append(rated("storey", info.storey, IFC_NAME, source="the storey that contains the space"))
    if info.area_source == "qto":
        facts.append(rated("area", round(info.net_floor_area_m2 or 0.0, 3), IFC_AREA, unit="m2",
                           source="IFC quantity NetFloorArea"))  # fmt: skip
    elif info.area_source == "geometry":
        facts.append(rated("area", round(info.net_floor_area_m2 or 0.0, 3), IFC_GEOMETRY_AREA, unit="m2",
                           status="estimated", source="footprint of the space geometry"))  # fmt: skip
    else:
        facts.append(rated("area", None, IFC_AREA, unit="m2", note="the model gives no area and no geometry"))
    if info.gross_floor_area_m2 is not None:
        facts.append(rated("gross_area", round(info.gross_floor_area_m2, 3), unmeasured("GrossFloorArea quantities"),
                           unit="m2", source="IFC quantity GrossFloorArea"))  # fmt: skip
    height = round(info.height_m, 3) if info.height_m is not None else None
    facts.append(rated("height", height, unmeasured("space heights in IFC models"), unit="m",
                       source="IFC quantity Height", note="" if height is not None else "the model gives no height"))  # fmt: skip
    facts.append(rated("global_id", info.global_id, IFC_NAME, source=source))
    return Entity(id=entity_id, kind="room", group="space", label=label, geometry="point", points=(),
                  facts=tuple(facts))  # fmt: skip


def _element(model: ifc_model.IfcModel, element: Any, kind: str) -> Entity:  # noqa: ANN401 - an IFC entity
    storey = ifc_model.storey_of(model, element)
    name = str(element.Name or "").strip()
    type_name = ifc_model.type_name(element)
    facts = (
        rated("storey", str(storey.Name) if storey is not None else None, IFC_NAME, source="spatial containment"),
        rated("type", type_name or None, IFC_NAME, source="the type of the element"),
        rated("global_id", element.GlobalId, IFC_NAME, source=element.is_a()),
    )
    return Entity(id=ifc_model.element_id(element), kind=kind, group=kind,  # ty: ignore[invalid-argument-type]
                  label=name or type_name or element.is_a(), geometry="point", points=(), facts=facts)  # fmt: skip


def model_facts(path: str | Path) -> DocumentFacts | None:
    """The spaces, storeys, doors and windows of an IFC model, and its element counts. None when not an IFC file."""
    if not _is_ifc(path):
        return None
    model = ifc_model.open_model(str(path))
    ids = ifc_model.space_ids(model)
    names = {s.GlobalId: ifc_model.space_name(s) for s in ifc_model.by_type(model, "IfcSpace")}
    infos = ifc_model.spaces(model)
    entities = [_space(s, ids[s.global_id], names[s.global_id] or s.global_id) for s in infos]
    unknown: list[str] = []
    no_area = sum(1 for s in infos if s.area_source == "none")
    if no_area:
        unknown.append(f"{no_area} spaces have no area in the model.")
    if not infos:
        unknown.append("The model has no IfcSpace: no rooms.")
    seen: set[str] = set()
    for storey in ifc_model.storeys(model):
        if storey.name in seen:
            continue
        seen.add(storey.name)
        facts: list[Fact] = []
        if storey.elevation_m is not None:
            facts.append(rated("elevation", round(storey.elevation_m, 3), unmeasured("storey elevations"), unit="m",
                               source="IfcBuildingStorey"))  # fmt: skip
        for category, plural in PLURAL.items():
            found = ifc_model.count_elements(model, category, storey.name)  # ty: ignore[invalid-argument-type]
            if found.count:
                facts.append(rated(plural, found.count, IFC_STOREY_COUNT, source=found.rule))
        area = ifc_model.storey_space_area(model, storey.name)
        if area.value is not None:
            source = f"NetFloorArea of {area.n_with_value} of {area.n_elements} spaces ({area.source})"
            facts.append(rated("area", round(area.value, 3), IFC_STOREY_AREA, unit="m2", source=source))
        members = tuple(ids[s.global_id] for s in infos if s.storey == storey.name)
        entities.append(Entity(id=ifc_model.storey_id(storey.name), kind="storey", group="storey", label=storey.name,
                               geometry="point", points=(), facts=tuple(facts), members=members))  # fmt: skip
    for category in ("door", "window"):
        elements, _ = ifc_model.category_elements(model, category)
        entities.extend(_element(model, e, category) for e in elements[:MAX_ELEMENTS])
    summary = [
        rated(plural, (found := ifc_model.count_elements(model, category)).count, IFC_COUNT, source=found.rule)  # ty: ignore[invalid-argument-type]
        for category, plural in PLURAL.items()
    ]
    summary.append(rated("storeys", len(seen), unmeasured("the storey count"), source="IfcBuildingStorey"))
    areas = [s.net_floor_area_m2 for s in infos if s.area_source == "qto" and s.net_floor_area_m2 is not None]
    if areas:
        note = f"{len(infos) - len(areas)} spaces with no NetFloorArea are left out" if len(areas) < len(infos) else ""
        summary.append(rated("net_floor_area", round(sum(areas), 3), IFC_STOREY_AREA, unit="m2",
                             source="the NetFloorArea of every space", note=note))  # fmt: skip
    return DocumentFacts(kind="ifc", entities=tuple(entities), unknown=tuple(unknown), summary=tuple(summary))


# ----------------------------------------------------------------------------- DXF
# Source: experiments/tools/swiss.json, 833 test floors (dev and val): the PDF reader against the DXF of the same
# floor (`rooms_vs_dxf`, `counts_vs_dxf`). The DXF is the CAD source, and its reader and the PDF reader agreed.

DXF_ROOMS = Rate(confidence=0.999, basis="the DXF and the PDF of 833 test floors gave the same 22,966 room numbers")
DXF_TEXT = Rate(confidence=0.999, basis="the room labels of the DXF and the PDF agreed on all 21,776 test rooms")
DXF_AREA = Rate(confidence=0.999, basis="outline areas of the DXF and the PDF agreed within 0.05% on 22,966 test rooms")
DXF_APARTMENTS = Rate(confidence=0.999, basis="the apartment count of the DXF and the PDF agreed on 833 of 833 floors")
DXF_WINDOWS = Rate(confidence=0.998, basis="the window count of the DXF and the PDF agreed on 832 of 833 test floors")
DXF_NO_UNIT = unmeasured("areas of a drawing with no unit in its header")


def _bounds(plan: dxf_plan.DxfPlan) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    rings = [r.points for r in plan.rooms] + list(plan.doors) + list(plan.windows) + list(plan.unit_outlines.values())
    for ring in rings:
        xs.extend(x for x, _ in ring)
        ys.extend(y for _, y in ring)
    xs.extend(t.x for t in plan.texts)
    ys.extend(t.y for t in plan.texts)
    if not xs:
        return 0.0, 0.0, 0.0, 0.0
    return min(xs), min(ys), max(xs), max(ys)


def dxf_facts(path: str | Path) -> DocumentFacts | None:
    """The rooms, apartments, doors, windows and loose texts of a DXF floor plan. None when not a DXF file."""
    if not dxf_plan.is_dxf(path):
        return None
    plan = dxf_plan.read_dxf(path)
    unit = plan.unit_m or 1.0
    x0, y0, x1, y1 = _bounds(plan)

    def page(ring: tuple[Point, ...]) -> tuple[Point, ...]:
        return tuple((round((x - x0) * unit, 3), round((y1 - y) * unit, 3)) for x, y in ring)

    area_rate = DXF_AREA if plan.unit_m else DXF_NO_UNIT
    ids = dxf_plan.room_ids(plan)
    entities: list[Entity] = []
    unknown: list[str] = []
    if plan.unit_m is None:
        unknown.append("The drawing gives no unit: points are in drawing units and areas are not reliable.")
    for i, room in enumerate(plan.rooms):
        facts = [rated("area", room.area_m2, area_rate, unit="m2", source="ROOM_OUTLINE polygon")]
        if room.number:
            facts.append(rated("number", room.number, DXF_ROOMS, source="text in the outline"))
        if room.label:
            facts.append(rated("label", room.label, DXF_TEXT, source="text in the outline"))
        if room.printed_area_m2 is not None:
            facts.append(rated("printed_area", room.printed_area_m2, unmeasured("printed areas read from DXF texts"),
                               unit="m2", source="text in the outline"))  # fmt: skip
        if room.unit:
            facts.append(rated("apartment", room.unit, unmeasured("the apartment of one DXF room"),
                               source="UNIT_OUTLINE that holds the room"))  # fmt: skip
        openings = unmeasured("windows and doors per DXF room")
        facts += [
            rated("outdoor", "yes" if room.outdoor else "no", unmeasured("the outdoor flag of DXF rooms"),
                  source="the room label"),
            rated("windows", room.windows, openings, source="WINDOW outlines within 6 cm of the room"),
            rated("doors", room.doors, openings, source="DOOR outlines within 6 cm of the room"),
        ]  # fmt: skip
        name = f"{room.label} {room.number}" if room.label and room.number else room.label or room.number
        entities.append(Entity(id=ids[i], kind="room", group="outdoor" if room.outdoor else "room",
                               label=name or "Room outline", geometry="polygon", points=page(room.points),
                               facts=tuple(facts)))  # fmt: skip
    for letter in plan.units:
        members = tuple(ids[i] for i, r in enumerate(plan.rooms) if r.unit == letter)
        member_areas = [r.area_m2 for r in plan.rooms if r.unit == letter]
        outline = plan.unit_outlines.get(letter)
        facts = (
            rated("rooms", len(members), DXF_ROOMS, source="room outlines inside the apartment outline"),
            rated("area", round(sum(member_areas), 2), area_rate, unit="m2", source="the areas of its rooms added"),
        )
        entities.append(Entity(id=dxf_plan.apartment_id(letter), kind="apartment", group="apartment",
                               label=f"Apartment {letter}", geometry="polygon" if outline else "point",
                               points=page(outline) if outline else (), facts=facts, members=members))  # fmt: skip
    for kind, rings in (("door", plan.doors), ("window", plan.windows)):
        for n, ring in enumerate(rings, start=1):
            entities.append(Entity(id=f"{kind}:{n}", kind=kind, group=kind, label=f"{kind.capitalize()} {n}",
                                   geometry="polygon", points=page(ring)))  # fmt: skip
    for text in plan.texts:
        if text.room is not None or not text.text:
            continue
        (at,) = page(((text.x, text.y),))
        entities.append(Entity(id=f"label:{at[0]:g}:{at[1]:g}", kind="label", group="label", label=text.text[:80],
                               geometry="point", points=(at,),
                               facts=(rated("text", text.text, DXF_TEXT, source="TEXT entity"),)))  # fmt: skip
    outdoor = [r.area_m2 for r in plan.rooms if r.outdoor]
    indoor = [r.area_m2 for r in plan.rooms if not r.outdoor and r.number]
    summary = (
        rated("rooms", sum(1 for r in plan.rooms if r.number), DXF_ROOMS, source="numbered room outlines"),
        rated("apartments", len(plan.units), DXF_APARTMENTS, source="apartment tags in unit outlines"),
        rated("doors", len(plan.doors), unmeasured("the distinct door count of a DXF"),
              source="DOOR outlines, each place once"),
        rated("windows", len(plan.windows), DXF_WINDOWS, source="WINDOW outlines"),
        rated("net_floor_area", round(sum(indoor), 2), area_rate, unit="m2",
              source="numbered indoor room outlines added"),
        rated("outdoor_area", round(sum(outdoor), 2), area_rate, unit="m2", source="balcony and terrace outlines"),
    )  # fmt: skip
    from bp import facts_quantities  # noqa: PLC0415 - perimeter, baseboard and wall length; loads the tool module

    room_extra, wall_facts, _ = facts_quantities.dxf(path, plan)  # no walls entity: DXF points are page metres
    entities = [e.model_copy(update={"facts": (*e.facts, *room_extra[e.id])}) if e.id in room_extra else e
                for e in entities]  # fmt: skip
    summary = (*summary, *wall_facts)
    width, height = round((x1 - x0) * unit, 3), round((y1 - y0) * unit, 3)
    return DocumentFacts(kind="dxf", pages=(Page(index=0, width=width, height=height, unit="m"),),
                         entities=tuple(entities), unknown=tuple(unknown), summary=summary)  # fmt: skip


# ----------------------------------------------------------------------------- small raster plans
# Source of the OCR, scale, room and apartment rates: experiments/tools/raster.json (210 val Swiss raster plans).

RASTER_NUMBER = Rate(confidence=0.925, basis="OCR read 92.5% of 5,577 test room numbers right")
RASTER_LABEL = Rate(confidence=0.894, basis="OCR read 89.4% of 5,285 test room labels right")
RASTER_PRINTED = Rate(confidence=0.893, basis="OCR read 89.3% of 1,770 test printed areas right")
RASTER_TAG = Rate(confidence=0.984, basis="OCR read 98.4% of 641 test apartment tags right")
RASTER_APARTMENT = Rate(confidence=0.972, basis="97.2% of 5,577 test rooms got the right apartment")
RASTER_OUTDOOR = Rate(confidence=0.993, basis="the outdoor flag was right on 99.3% of 5,577 test rooms")
RASTER_SCALE = Rate(confidence=0.999, basis="the scale bar and the scale text were within 1% on 210 of 210 test plans")
RASTER_ESTIMATED_SCALE = unmeasured("a scale from door sizes or printed areas on a plan with no scale bar")
RASTER_USER_SCALE = unmeasured("a scale from the user")
RASTER_RELATIVE = unmeasured("relative room sizes on a plan with no scale")
RASTER_OPENINGS = unmeasured("windows and doors per room on raster plans")
# rooms.by_confidence: share within 5% (the tolerance of the room_area key), and the margin that holds about 9 of 10
RASTER_AREA: dict[str, tuple[Rate, float, float, int]] = {  # rate, relative margin, share inside it, test rooms
    "high": (Rate(confidence=0.995, basis="99.5% of 2,709 test rooms of this confidence were within 5%"), 0.02,
             0.966, 2709),
    "medium": (Rate(confidence=0.945, basis="94.5% of 1,298 test rooms of this confidence were within 5%"), 0.05,
               0.945, 1298),
    "low": (Rate(confidence=0.895, basis="89.5% of 1,186 test rooms of this confidence were within 5%"), 0.05,
            0.895, 1186),
}  # fmt: skip

# Symbol detector (YOLO26-M), experiments/tools/cubicasa-detect.json, 300 val CubiCasa plans.
DETECT_PRECISION: dict[str, float] = {  # share of boxes above the threshold that are a real symbol
    "door": 0.9575, "window": 0.9306, "toilet": 0.95, "sink": 0.9344, "shower": 0.8723, "bathtub": 0.5484,
    "bedroom": 0.918, "kitchen": 0.7961, "bathroom": 0.8898, "wc_room": 0.854, "sauna": 0.9408, "balcony": 0.7925,
}  # fmt: skip
DETECT_EXACT: dict[str, float] = {  # share of plans with the exact count, before the doubt rule
    "door": 0.71, "window": 0.6067, "toilet": 0.9233, "sink": 0.8533, "shower": 0.82, "bathtub": 0.92,
    "sauna": 0.95, "floorplan": 0.9767, "kitchen": 0.8167, "bedroom": 0.87, "bathroom": 0.8567, "wc_room": 0.9233,
    "balcony": 0.9067,
}  # fmt: skip
# Count head e1, experiments/tools/cubicasa_count.json, 957 val plans: accuracy when the head answers.
COUNT_HEAD: dict[str, float] = {
    "balconies": 0.8889, "bathrooms": 0.9442, "bedrooms": 0.7867, "doors": 0.6724, "floors": 0.9778,
    "kitchens": 0.9674, "saunas": 0.9688, "showers_tubs": 0.8638, "sinks": 0.8199, "toilets": 0.8416,
    "wc_rooms": 0.8606, "windows": 0.5176,
}  # fmt: skip
BOX_KINDS = {"door": "door", "window": "window", "toilet": "fixture", "sink": "fixture", "shower": "fixture",
             "bathtub": "fixture"}  # fmt: skip
BOX_CONCEPT = {"door": "doors", "window": "windows", "toilet": "toilets", "sink": "sinks", "shower": "showers",
               "bathtub": "bathtubs"}  # fmt: skip


def _box_rate(cls: str, *, in_distribution: bool = True) -> Rate:
    share = DETECT_PRECISION.get(cls)
    if not in_distribution:
        return unmeasured(f"{cls} boxes on a plan that is not like the CubiCasa test plans")
    if share is None:
        return unmeasured(f"{cls} boxes of the symbol detector")
    return Rate(confidence=share, basis=f"{100 * share:.1f}% of the {cls} boxes on 300 test plans were real symbols")


def _detector_count_rate(classes: tuple[str, ...]) -> Rate:
    known = [(DETECT_EXACT[c], c) for c in classes if c in DETECT_EXACT]
    if not known:
        return unmeasured("this count of the symbol detector")
    share, cls = min(known)
    return Rate(confidence=share, basis=f"the {cls} count of the detector was exact on {100 * share:.0f}% of 300 "
                "test plans")  # fmt: skip


def _count_head_rate(family: str) -> Rate:
    share = COUNT_HEAD.get(family)
    if share is None:
        return unmeasured(f"the {family} count of the count head")
    return Rate(confidence=share, basis=f"the count head was right on {100 * share:.0f}% of the test plans it "
                "answered")  # fmt: skip


def _room_area(room: Any, ppm_source: str) -> Fact:  # noqa: ANN401 - raster_rooms.Room
    if ppm_source == "doors":
        # The tool gives only the printed area when the scale is an estimate.
        if room.printed_area_m2 is None:
            return rated("area", None, RASTER_PRINTED, unit="m2",
                         note="the scale is an estimate from door sizes and the room prints no area")  # fmt: skip
        return rated("area", room.printed_area_m2, RASTER_PRINTED, unit="m2", source="printed area (OCR)")
    bucket = RASTER_AREA.get(room.area_confidence)
    if room.area_m2 is None or bucket is None:
        return rated("area", None, RASTER_PRINTED, unit="m2", note="no closed room shape and no printed area")
    rate, share_of_value, share, rooms = bucket
    margin = relative(room.area_m2, share_of_value, share, f"{100 * share:.1f}% of {rooms} test rooms of this "
                      "confidence were inside it", floor=0.01)  # fmt: skip
    status = "known" if room.area_source == "printed" else "estimated"
    source = "printed area (OCR)" if room.area_source == "printed" else f"room shape ({room.area_source})"
    return rated("area", room.area_m2, rate, margin, unit="m2", status=status, source=source)


def _raster_room(room: Any, entity_id: str, ppm_source: str | None, openings: dict[str, int | None]) -> Entity:  # noqa: ANN401
    facts = [rated("number", room.number, RASTER_NUMBER, source="OCR")]
    if room.label:
        facts.append(rated("label", room.label, RASTER_LABEL, source="OCR"))
    if ppm_source is not None:
        facts.append(_room_area(room, ppm_source))
    else:
        facts.append(rated("area", None, RASTER_PRINTED, unit="m2", note="no scale on this image"))
    if room.printed_area_m2 is not None:
        facts.append(rated("printed_area", room.printed_area_m2, RASTER_PRINTED, unit="m2", source="OCR"))
    if room.apartment:
        facts.append(rated("apartment", room.apartment, RASTER_APARTMENT, source="apartment outline and tag"))
    facts.append(rated("outdoor", "yes" if room.outdoor else "no", RASTER_OUTDOOR, source="the room label"))
    facts += [
        rated(key, openings[key], RASTER_OPENINGS, status="estimated" if openings[key] is not None else "unknown",
              source="detector boxes that touch the room",
              note="" if openings[key] is not None
              else f"the detector is not sure; at least {openings.get(f'{key}_at_least')}")
        for key in ("windows", "doors") if key in openings
    ]  # fmt: skip
    name = f"{room.label} {room.number}" if room.label else room.number
    polygon = len(room.polygon) >= 3
    return Entity(id=entity_id, kind="room", group="outdoor" if room.outdoor else "room", label=name,
                  geometry="polygon" if polygon else "point", points=room.polygon if polygon else (room.at,),
                  facts=tuple(facts))  # fmt: skip


def _scale_entity(plan: RasterPlan, calibration: Calibration | None = None) -> Entity | None:
    scale = plan.scale
    if scale is None:
        return None
    if scale.source == "user":
        fact = rated("px_per_metre", round(scale.ppm, 3), RASTER_USER_SCALE, unit="px/m", source="user",
                     note="two points and their real distance from the user")  # fmt: skip
        points = calibration.points if calibration and calibration.points else ()
        return Entity(id="scale", kind="scale", group="scale", label="Scale (user)",
                      geometry="line" if points else "point", points=points, facts=(fact,))  # fmt: skip
    rate = RASTER_ESTIMATED_SCALE if scale.source in ("doors", "areas") else RASTER_SCALE
    status = "estimated" if scale.source in ("doors", "areas") else "known"
    source = {"both": "scale bar and scale text", "bar": "scale bar", "text": "scale text",
              "areas": "printed room areas against the room shapes", "doors": "door symbol sizes"}[scale.source]  # fmt: skip
    facts = [rated("px_per_metre", round(scale.ppm, 3), rate, unit="px/m", status=status, source=source)]
    if scale.ratio:
        facts.append(rated("ratio", f"1:{scale.ratio}", RASTER_SCALE, source="scale text"))
    return Entity(id="scale", kind="scale", group="scale", label=f"Scale ({source})", geometry="point", points=(),
                  facts=tuple(facts))  # fmt: skip


def _detector_boxes(detector: CubicasaDetectSolver | None, *, in_distribution: bool) -> list[Entity]:
    if detector is None or detector.detector is None or detector.detections is None or detector.problem is not None:
        return []
    calib: dict[str, Any] = detector.detector.meta.get("calibration", {})
    out = []
    for d in detector.detections:
        kind = BOX_KINDS.get(d.label)
        concept = calib.get(BOX_CONCEPT.get(d.label, ""), {})
        if kind is None or not concept or d.score < float(concept.get("threshold", 0.5)):
            continue
        x0, y0, x1, y1 = (round(v) for v in d.box)
        rate = _box_rate(d.label, in_distribution=in_distribution)
        facts = (rated("score", round(d.score, 3), rate, source="symbol detector"),)
        out.append(Entity(id=f"{d.label}:{round((x0 + x1) / 2)}:{round((y0 + y1) / 2)}", kind=kind, group=d.label,  # ty: ignore[invalid-argument-type]
                          label=d.label.replace("_", " ").capitalize(), geometry="box",
                          points=((x0, y0), (x1, y1)), facts=facts))  # fmt: skip
    return out


# analysis/cubicasa/marked_room_area.py: the box of a marked room against the room polygon, 323 rooms on 60 plans
BOX_AREA = Rate(confidence=0.263, basis="the box of a marked room was within 5% of the room area on 26.3% of 323 "
                "test rooms; the median box was 7% too small")  # fmt: skip
BOX_AREA_MARGIN = (0.20, 0.799, "79.9% of 323 test rooms were inside it, at the right scale")


def _marked_rooms(rows: list[dict[str, Any]], *, in_distribution: bool, ppm: float | None = None) -> list[Entity]:
    """The rooms that the detector marks. `ppm` is a scale from the user: with it, the box gives a rough area."""
    out = []
    for row in rows:
        x0, y0, x1, y1 = row["box_px"]
        rate = _box_rate(row["kind"], in_distribution=in_distribution)
        facts = [rated("kind", row["kind"], rate, source="symbol detector")]
        facts += [
            rated(key, row[key], RASTER_OPENINGS, status="estimated" if row[key] is not None else "unknown",
                  source="detector boxes that touch the room box",
                  note="" if row[key] is not None else f"the detector is not sure; at least {row[f'{key}_at_least']}")
            for key in ("windows", "doors")
        ]  # fmt: skip
        facts.append(rated("relative_box_area", row["relative_box_area"], RASTER_RELATIVE, status="estimated",
                           source="room box against the boxes of all marked rooms"))  # fmt: skip
        if ppm:
            area = round((x1 - x0) * (y1 - y0) / ppm**2, 1)
            share_of_value, share, basis = BOX_AREA_MARGIN
            facts.append(rated("area", area, BOX_AREA, relative(area, share_of_value, share, basis), unit="m2",
                               status="estimated", source="the box of the symbol detector at the scale from the user",
                               note="a box, not the room shape: rough"))  # fmt: skip
        out.append(Entity(id=row["entity_id"], kind="room", group=row["kind"],
                          label=row["kind"].replace("_", " ").capitalize(), geometry="box",
                          points=((x0, y0), (x1, y1)), facts=tuple(facts)))  # fmt: skip
    return out


def _counts(path: str | Path, detector: CubicasaDetectSolver | None) -> tuple[list[Fact], list[str], bool]:
    """The whole-plan counts that the agent's count tool gives, when the count head takes the image.

    The last value says whether the image is like the CubiCasa plans that the count models and the detector were
    tested on.
    """
    from bp.solvers.agent import COUNT_MEANING, plan_counts  # noqa: PLC0415 - the agent imports the tools
    from bp.tools import count_head  # noqa: PLC0415 - torch is slow to import
    from bp.tools.symbol_detector import CONCEPTS  # noqa: PLC0415

    counts = count_head.count_plan(Path(path), count_head.get_model("e1.json"))
    if not counts.in_distribution:
        return [], ["The count models do not take this image: no whole-plan counts."], False
    trusted, unsure = plan_counts(counts, detector.sure_counts() if detector is not None else None)
    facts = []
    for family, got in trusted.items():
        by_detector = got["by"] == "symbol detector"
        rate = _detector_count_rate(CONCEPTS.get(family, ())) if by_detector else _count_head_rate(family)
        facts.append(rated(family, got["count"], rate, status="estimated", source=got["by"],
                           note=COUNT_MEANING.get(family, "")))  # fmt: skip
    facts += [
        rated(family, None, NOT_SURE, source="symbol detector and count head", note="neither tool is sure of it")
        for family in unsure
    ]
    return facts, [f"No trusted count of {family}." for family in unsure], True


NOT_SURE = unmeasured("a count that both count tools doubt")


def raster_facts(
    path: str | Path, rgb: np.ndarray | None = None, calibration: Calibration | None = None
) -> DocumentFacts | None:
    """The rooms, apartments, scale, symbols and whole-plan counts of a small raster plan.

    None when the file is not a raster image or is a large sheet (`bp.facts.sheet_facts` reads those). The image
    is read once per process: the agent tools of the same image use the same reading. A calibration with two points
    and their real distance replaces the scale of the image: the rooms are read again at that scale.
    """
    from bp.solvers import raster_tools  # noqa: PLC0415 - torch and OCR are slow to import
    from bp.tools import ocr, sheet_text  # noqa: PLC0415

    if Path(path).suffix.lower() not in RASTER_SUFFIXES:
        return None
    rgb = ocr.to_rgb(path) if rgb is None else rgb
    if sheet_text.is_sheet(rgb):
        return None
    height, width = rgb.shape[:2]
    page = Page(index=0, width=float(width), height=float(height))
    # The same choice as the agent solver: room openings need the detector unless BP_ROOM_OPENINGS=0.
    use = (lambda: raster_tools.detector_for(path)) if os.environ.get("BP_ROOM_OPENINGS", "1") != "0" else None
    small = raster_tools.read_small(path, rgb, use, raster_tools.user_ppm(calibration))
    detector = small.detector if small is not None else raster_tools.detector_for(path)
    counts, no_count, in_distribution = _counts(path, detector)
    entities: list[Entity] = []
    unknown: list[str] = []
    summary: list[Fact] = []
    if small is None:
        unknown.append("OCR reads no text on this image: no rooms.")
    else:
        entities, summary, unknown = _plan_entities(small, calibration, in_distribution=in_distribution)
    if calibration is not None and raster_tools.user_ppm(calibration) is None:
        unknown.append("The scale from the user is not used: a ratio alone gives no scale on an image. Give two "
                       "points and their real distance.")  # fmt: skip
    entities += _detector_boxes(detector, in_distribution=in_distribution)
    return DocumentFacts(kind="raster", pages=(page,), entities=tuple(entities), unknown=tuple(unknown + no_count),
                         summary=tuple(summary + counts), conflicts=_user_scale_conflict(small))  # fmt: skip


USER_SCALE_GAP = 0.05


def _user_scale_conflict(small: SmallRaster | None) -> tuple[Conflict, ...]:
    """The scale from the user against the scale bar or scale text of the image, when they differ."""
    if small is None or small.measured is None or small.plan.scale is None:
        return ()
    given, own = small.plan.scale.ppm, small.measured.ppm
    gap = abs(own / given - 1)
    if gap <= USER_SCALE_GAP:
        return ()
    text = (f"The scale from the user ({given:.1f} px/m) and the scale that the image shows ({own:.1f} px/m) differ "
            f"by {100 * gap:.0f}%. Each area in m2 depends on it.")  # fmt: skip
    return (Conflict(id="scale:user", entity_ids=("scale",), text=text, doubtful=("scale",), all_measured=True),)


def _plan_entities(
    small: SmallRaster, calibration: Calibration | None = None, *, in_distribution: bool
) -> tuple[list[Entity], list[Fact], list[str]]:
    from bp.solvers import raster_tools  # noqa: PLC0415

    plan = small.plan
    scale = plan.scale
    ids = raster_tools.room_ids(plan)
    entities: list[Entity] = []
    unknown: list[str] = []
    openings = raster_tools.room_openings(plan, small.detector)
    for i, room in enumerate(plan.rooms):
        entities.append(_raster_room(room, ids[i], scale.source if scale else None, openings.get(room.number, {})))
    for letter in sorted({a.letter for a in plan.apartments}):
        members = tuple(ids[i] for i, r in enumerate(plan.rooms) if r.apartment == letter)
        at = next(a.at for a in plan.apartments if a.letter == letter)
        facts = (rated("rooms", len(members), RASTER_APARTMENT, source="rooms inside the apartment outline"),)
        entities.append(Entity(id=raster_tools.apartment_id(letter), kind="apartment", group="apartment",
                               label=f"Apartment {letter}", geometry="point", points=(at,), facts=facts,
                               members=members))  # fmt: skip
    found = _scale_entity(plan, calibration)
    if found is not None:
        entities.append(found)
    else:
        unknown.append("No scale on this image: no areas in m2 and no lengths.")
    # A scale from the user with no room numbers: the room model has no rooms, so the plan reads as one with no scale.
    unread = scale is None or (scale.source == "user" and not plan.rooms)
    if unread and scale is not None:
        unknown.append("The scale from the user is taken, but OCR reads no room numbers on this image, so no room "
                       "shape is measured. The rooms that the symbol detector marks have a rough area from their "
                       "box.")  # fmt: skip
    if unread or (scale is not None and scale.source in ("doors", "areas")):
        rows = raster_tools.detected_rooms(small.detector, small.lines)
        entities += _marked_rooms(rows, in_distribution=in_distribution,
                                  ppm=scale.ppm if scale is not None and scale.source == "user" else None)  # fmt: skip
    if unread:
        for t in raster_tools.label_areas(small.rgb, small.lines):
            facts = (
                rated("label", t["label"], RASTER_LABEL, source="OCR"),
                rated("relative_area_share", t["area_share"], RASTER_RELATIVE,
                      status="estimated" if t["area_share"] is not None else "unknown",
                      source="pixel area of the region around the text",
                      note="" if t["area_share"] is not None else "the region around the text is not closed"),
            )  # fmt: skip
            at = (float(t["at_px"][0]), float(t["at_px"][1]))
            entities.append(Entity(id=raster_tools.text_room_id(t["at_px"]), kind="room", group="room",
                                   label=t["label"], geometry="point", points=(at,), facts=facts))  # fmt: skip
    if plan.rooms:
        summary = [rated("rooms", len(plan.rooms), RASTER_NUMBER, source="room numbers that OCR read"),
                   rated("apartments", len({a.letter for a in plan.apartments}), RASTER_TAG, source="apartment tags")]  # fmt: skip
    else:
        # No room number is read: that is not the same as a plan with no rooms.
        summary = [rated("rooms", None, RASTER_NUMBER, source="room numbers that OCR read",
                         note="OCR reads no room numbers on this image, so the rooms are not counted")]  # fmt: skip
    if found is not None:
        summary.insert(0, found.facts[0])
    indoor = [e for e in entities if e.kind == "room" and e.group == "room"]
    area_facts = [f for e in indoor for f in e.facts if f.key == "area" and f.value is not None]
    if area_facts and scale is not None and scale.source != "doors":
        margins = [Margin(value=f.margin, share=f.margin_share or 0.0, basis=f.margin_basis)
                   for f in area_facts if f.margin is not None]  # fmt: skip
        worst = min(area_facts, key=lambda f: f.confidence)
        total = round(sum(float(f.value or 0.0) for f in area_facts), 2)
        missing = len(indoor) - len(area_facts)
        summary.append(rated("net_floor_area", total, Rate(confidence=worst.confidence, basis=f"the lowest room "
                             f"confidence: {worst.basis}"), sum_margin(margins), unit="m2", status="estimated",
                             source="room areas added", note=f"{missing} rooms with no area are left out"
                             if missing else ""))  # fmt: skip
    return entities, summary, unknown
