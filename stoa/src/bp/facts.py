"""The facts of one document, for a person to inspect: each thing on the drawing with its place and what is known.

`document_facts(path)` is the one entry point. An entity is one thing (a room, a door, a text label, the scale)
with a geometry in the coordinate system of its page: source pixels for a raster image. Each fact says how it is
known: `known` (read from the document), `estimated` (measured, with an error band) or `unknown` (the document
does not give it, with the reason in `note`). The ids are the same ids that the agent tools put in their rows
(`entity_id`) and in their evidence (`ref`), so an answer can be linked to the things it used.

Each fact has a confidence with its `basis` (a measured benchmark result, or a statement that none covers it), and a
measured length or area has an error `margin` with the share of test items inside it (see `bp.rates`). The facts that
do not add up are in `DocumentFacts.conflicts` (see `bp.conflicts`).

It covers large raster sheets and Swiss vector plans (`bp.facts_swiss`). For another kind of document the result
has the kind and no entities.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from bp import conflicts, rates
from bp.contract import Check, Conflict, Frozen
from bp.rates import NOT_GIVEN, Margin, Rate
from bp.tools import ocr, sheet_plan, sheet_text
from bp.tools.sheet_text import SQFT_M2

if TYPE_CHECKING:
    from bp.contract import Calibration
    from bp.tools.sheet_rooms import Swing

RASTER_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"})
OCR_CONFIDENCE = 0.9  # of a text that OCR read on a clean sheet
ROOM_FACTOR = 0.9
PERIMETER_FACTOR = 0.8
DOOR_FACTOR = 0.8  # one swing is a door; the weak point of the door finder is the count, not one door
MAX_LABELS = 3000

Status = Literal["known", "estimated", "unknown"]


class Fact(Frozen):
    key: str  # "area", "perimeter", "doors", "text", "leaf_width", "px_per_metre"
    value: float | int | str | None
    unit: str = ""
    status: Status = "known"
    confidence: float = 1.0
    source: str = ""  # the tool or the reading that gives it
    note: str = ""
    checks: tuple[Check, ...] = ()  # the reasons for the confidence
    basis: str = ""  # one plain sentence: why this confidence, from a benchmark, or that no benchmark covers it
    # Error margin of a measured length or area: plus or minus `margin` in `unit`; `margin_share` of the test items
    # of the benchmark were inside it. None: not a measured value, or no benchmark measures its error.
    margin: float | None = None
    margin_share: float | None = None
    margin_basis: str = ""


def rated(key: str, value: float | str | None, rate: Rate, margin: Margin | None = None, **fields: Any) -> Fact:  # noqa: ANN401
    """A fact with the confidence and the basis of `rate`, and the margin when one is measured.

    A fact with no value gets `NOT_GIVEN`: confidence 0 and the status `unknown`.
    """
    if value is None:
        fields.setdefault("status", "unknown")
        rate, margin = NOT_GIVEN, None
    extra: dict[str, Any] = {}
    if margin is not None:
        extra = {"margin": margin.value, "margin_share": margin.share, "margin_basis": margin.basis}
    return Fact(key=key, value=value, confidence=rate.confidence, basis=rate.basis, **extra, **fields)


EntityKind = Literal["room", "door", "label", "scale", "zone", "apartment", "fixture", "window", "storey", "element"]


class Entity(Frozen):
    id: str
    kind: EntityKind
    label: str
    page: int = 0
    geometry: Literal["point", "box", "line", "polygon"]
    points: tuple[tuple[float, float], ...]
    facts: tuple[Fact, ...] = ()
    members: tuple[str, ...] = ()  # the ids of the entities that a group holds
    group: str = ""  # a finer kind for the legend, such as "toilet" for a fixture


class Page(Frozen):
    index: int
    width: float
    height: float
    unit: Literal["px", "pt", "m"] = "px"


class DocumentFacts(Frozen):
    kind: str  # "sheet", "plan_pdf", "raster", "unsupported"
    pages: tuple[Page, ...] = ()
    entities: tuple[Entity, ...] = ()
    unknown: tuple[str, ...] = ()  # what the document does not give, in plain sentences
    ocr_pending: bool = False  # the text of this sheet is not read yet: call again with read_text=True
    summary: tuple[Fact, ...] = ()  # counts and totals of the whole document
    conflicts: tuple[Conflict, ...] = ()  # facts that do not add up; see `bp.conflicts`


SCALE_RATE_BASIS = (
    "the factor of the scale check is a rule; on the 12 dev USACE sheets with a scale, rooms measured at it had a "
    "median error of 1.3% against their printed areas, so no scale there was wrong"
)  # analysis/sheets/room_margin.py


def _scale_entities(plan: sheet_plan.SheetPlan) -> tuple[list[Entity], list[str]]:
    scale, measured = plan.scale, plan.measured
    out: list[Entity] = []
    unknown: list[str] = []
    if scale is not None:
        basis = SCALE_RATE_BASIS if scale.source != "user" else "the scale is from the user; no benchmark measures it"
        fact = Fact(key="px_per_metre", value=round(scale.ppm, 3), unit="px/m", status="known",
                    confidence=scale.check.factor, source=scale.source, note=scale.detail, checks=(scale.check,),
                    basis=basis)  # fmt: skip
        given = plan.calibration.points if plan.calibration and scale.source == "user" else None
        points = given or ((0.0, 0.0), (scale.ppm, 0.0))
        out.append(Entity(id="scale", kind="scale", label=f"Scale ({scale.source})", geometry="line", points=points,
                          facts=(fact,)))  # fmt: skip
    else:
        unknown.append("The scale of this image is not proven: no dimension lines agree, and the doors do not "
                       "confirm a printed scale. Give two points and their real distance.")  # fmt: skip
    if measured is not None:
        for index, witness in enumerate(measured.witnesses):
            note = f"{witness.pixels:.0f} px for {witness.metres:g} m"
            fact = rated("px_per_metre", round(witness.pixels / witness.metres, 3), rates.SHEET_WITNESS, unit="px/m",
                         source="dimension line", note=note)  # fmt: skip
            out.append(Entity(id=f"scale:witness:{index}", kind="scale", label=witness.text, geometry="line",
                              points=tuple(witness.line), facts=(fact,)))  # fmt: skip
        if scale is not None and scale.source == "user" and abs(measured.ppm / scale.ppm - 1) > 0.02:
            unknown.append(f"The scale from the user ({scale.ppm:.1f} px/m) and the dimension lines of the sheet "
                           f"({measured.ppm:.1f} px/m) differ by {100 * abs(measured.ppm / scale.ppm - 1):.0f}%.")  # fmt: skip
    return out, unknown


def _door(swing: Swing, ppm: float, scale_check: Check) -> Entity:
    checks = (scale_check, Check(id="error_band", label="Door finder", state="pass", factor=DOOR_FACTOR,
                                 detail="a leaf line with a swing arc of a door size"))  # fmt: skip
    width = rated("leaf_width", round(swing.radius_px / ppm, 2), rates.SHEET_LEAF_WIDTH, unit="m",
                  status="estimated", source="count_door_swings", checks=checks)  # fmt: skip
    kind = rated("kind", "swing door leaf", rates.SHEET_DOOR, source="count_door_swings")
    return Entity(id=sheet_plan.door_id(swing), kind="door", label="Door leaf", geometry="point",
                  points=((swing.centre[0], swing.centre[1]),), facts=(kind, width))  # fmt: skip


PRINTED_SQFT = re.compile(r"(?:^|\s)([\d,]{2,7})\s*(?:SF|S\.F\.|SQ\.? ?FT\.?)$", re.IGNORECASE)
PRINTED_M2 = re.compile(r"(?:^|\s)(\d{1,5}(?:[.,]\d{1,2})?)\s*m[²2]$", re.IGNORECASE)


def printed_area_m2(text: str) -> tuple[float, str] | None:
    """The area that a text prints, in m2, and the text of it: "220 SF" or "12.5 m2"."""
    found = PRINTED_SQFT.search(text.strip())
    if found:
        value = int(found.group(1).replace(",", ""))
        return (round(value * SQFT_M2, 2), f"{value} SF") if value > 0 else None
    found = PRINTED_M2.search(text.strip())
    if found:
        value = float(found.group(1).replace(",", "."))
        return (value, f"{value:g} m2") if value > 0 else None
    return None


def _printed(found: sheet_plan.PlanRoom, plan: sheet_plan.SheetPlan) -> tuple[float, str, str] | None:
    """(m2, text, label id) of the one printed area in the room: in its name label, or one area label inside it."""
    own = printed_area_m2(found.label.text)
    if own is not None:
        return (*own, sheet_plan.label_id(found.label))
    room = found.room
    if room is None or not found.closed:
        return None  # an open region holds the areas of other rooms too
    inside = [(lb, area) for lb in plan.labels if (area := printed_area_m2(lb.text)) and room.holds(*lb.at)]
    if len(inside) != 1:
        return None
    label, (m2, text) = inside[0]
    return m2, text, sheet_plan.label_id(label)


def _room(found: sheet_plan.PlanRoom, plan: sheet_plan.SheetPlan, scale: sheet_plan.PlanScale) -> Entity:
    label = found.label
    name = rated("text", label.text, rates.SHEET_TEXT, source="OCR")
    box = ((label.bbox[0], label.bbox[1]), (label.bbox[2], label.bbox[3]))
    printed = _printed(found, plan)
    printed_fact = () if printed is None else (
        rated("printed_area", printed[0], rates.SHEET_PRINTED, unit="m2", source="text on the sheet (OCR)",
              note=f"{printed[1]}, label {printed[2]}"),
    )  # fmt: skip
    if not found.closed or found.room is None:
        area = Fact(key="area", value=None, unit="m2", status="unknown", confidence=0.0, source="room_area",
                    note=found.why_not, basis=rates.NOT_GIVEN.basis)  # fmt: skip
        return Entity(id=sheet_plan.room_id(label), kind="room", label=label.text, geometry="box", points=box,
                      facts=(name, area, *printed_fact))  # fmt: skip
    room = found.room
    closed = Check(id="closed", label="Room is closed", state="pass",
                   detail="the walls and the closed door openings bound one region with one room name")  # fmt: skip
    area_checks = (scale.check, closed, Check(id="error_band", label="Area from the wall lines", state="pass",
                                              factor=ROOM_FACTOR, detail="1 to 3% error on a closed room"))  # fmt: skip
    wall_checks = (scale.check, Check(id="error_band", label="Wall length from the outline", state="warn",
                                      factor=PERIMETER_FACTOR, detail="3 to 6% error"))  # fmt: skip
    m2 = room.area_px / scale.ppm**2
    doors = room.doors_on_edge(plan.swings)
    perimeter = room.perimeter_px() / scale.ppm
    measured = scale.measured
    area_rate, area_margin = rates.sheet_room(
        m2, divided=bool(sheet_plan.DIVIDED.search(label.text)), scale_source=scale.source,
        agreeing=measured.agreeing if measured else None, spread=measured.spread if measured else None,
        scan=plan.scan,
    )  # fmt: skip
    facts = (
        name,
        rated("area", round(m2, 2), area_rate, area_margin, unit="m2", status="estimated", source="room_area",
              note=f"{round(m2 / SQFT_M2)} sq ft", checks=area_checks),
        *printed_fact,
        rated("perimeter", round(perimeter, 2), rates.SHEET_PERIMETER, unit="m", status="estimated",
              source="room_perimeter", checks=wall_checks),
        rated("doors", len(doors), rates.SHEET_DOOR_COUNT, status="estimated", source="count_door_swings",
              note="swing doors with the hinge on the outline of the room"),
    )  # fmt: skip
    outline = tuple((float(x), float(y)) for x, y in room.outline())
    return Entity(id=sheet_plan.room_id(label), kind="room", label=label.text, geometry="polygon", points=outline,
                  facts=facts, members=tuple(sheet_plan.door_id(s) for s in doors))  # fmt: skip


NEAR_DOORS_M = 15.0
NEAR_DOORS = 4  # a name with fewer door leaves this near is in the title block, a legend or the notes
SENTENCE = re.compile(r"[,.] |\b(THE|IS|ARE|DOES|NOT|SHALL|ETC|ALL)\b")
NAME_WORDS = 5
VOID = re.compile(r"\b(OPEN TO (BELOW|ABOVE)|VOID|OPEN ABOVE|OPEN BELOW)\b")  # a hole in the floor has no floor area


def _in_plan(found: sheet_plan.PlanRoom, plan: sheet_plan.SheetPlan, ppm: float) -> bool:
    """True for a name in the drawing. A cell of the title block is a closed box too, and a note is a line of words."""
    text = found.label.text.upper()
    if VOID.search(text):
        return False
    if found.room is not None and found.room.doors_on_edge(plan.swings):
        return True
    if len(text.split()) > NAME_WORDS or SENTENCE.search(text):
        return False
    x, y = found.label.at
    reach = NEAR_DOORS_M * ppm
    return sum(math.hypot(s.centre[0] - x, s.centre[1] - y) <= reach for s in plan.swings) >= NEAR_DOORS


def _sheet_summary(entities: list[Entity], scale: sheet_plan.PlanScale | None) -> tuple[Fact, ...]:
    kinds = [e.kind for e in entities]
    outlined = sum(1 for e in entities if e.kind == "room" and e.geometry == "polygon")
    scale_fact = (
        Fact(key="px_per_metre", value=round(scale.ppm, 3), unit="px/m", confidence=scale.check.factor,
             source=scale.source, note=scale.detail, basis=SCALE_RATE_BASIS if scale.source != "user" else
             "the scale is from the user; no benchmark measures it")
        if scale is not None else rated("px_per_metre", None, rates.NOT_GIVEN, unit="px/m", note="no scale found")
    )  # fmt: skip
    return (
        scale_fact,
        rated("room_names", kinds.count("room"), rates.SHEET_TEXT, source="text on the sheet (OCR)"),
        rated("rooms_with_outline", outlined, rates.unmeasured("the share of rooms whose walls close"),
              status="estimated", source="closed wall lines around a room name"),
        rated("door_leaves", kinds.count("door"), rates.SHEET_DOOR_COUNT, status="estimated",
              source="leaf line with a swing arc"),
        rated("text_labels", kinds.count("label"), rates.SHEET_TEXT, source="OCR"),
    )  # fmt: skip


def sheet_facts(plan: sheet_plan.SheetPlan) -> DocumentFacts:
    """The scale, the rooms, the doors and the text labels of one large sheet, and the facts that do not add up."""
    height, width = plan.rgb.shape[:2]
    entities, unknown = _scale_entities(plan)
    scale = plan.scale
    rooms = plan.rooms() if scale is not None else {}
    if scale is not None:
        rooms = {key: found for key, found in rooms.items() if _in_plan(found, plan, scale.ppm)}
    if scale is not None:
        entities.extend(_room(found, plan, scale) for found in rooms.values())
        entities.extend(_door(swing, scale.ppm, scale.check) for swing in plan.swings)
        open_rooms = sum(1 for found in rooms.values() if not found.closed)
        if open_rooms:
            unknown.append(f"{open_rooms} name labels have no closed room around them: no area for those.")
    room_labels = {sheet_plan.label_id(found.label) for found in rooms.values()}
    for label in plan.labels[:MAX_LABELS]:
        if sheet_plan.label_id(label) in room_labels:
            continue
        box = ((label.bbox[0], label.bbox[1]), (label.bbox[2], label.bbox[3]))
        text = rated("text", label.text, rates.SHEET_TEXT, source="OCR")
        entities.append(Entity(id=sheet_plan.label_id(label), kind="label", label=label.text[:80], geometry="box",
                               points=box, facts=(text,)))  # fmt: skip
    page = Page(index=0, width=float(width), height=float(height))
    found = DocumentFacts(kind="sheet", pages=(page,), entities=tuple(entities), unknown=tuple(unknown),
                          summary=_sheet_summary(entities, scale))  # fmt: skip
    return found.model_copy(update={"conflicts": (*conflicts.sheet_scale(plan), *conflicts.find(found))})


def document_facts(
    path: str | Path, calibration: Calibration | None = None, *, read_text: bool = False
) -> DocumentFacts:
    """The facts of the document at `path`. It is fast: it reads text only from the cache unless `read_text`.

    A Swiss vector plan (PDF), an IFC model, a DXF plan, a small raster plan and a large raster sheet have facts. With a calibration, the scale entity of a sheet
    has the source `user`, and the dimension lines of the sheet stay in the result as witnesses, so a conflict
    between the two is visible.
    """
    suffix = Path(path).suffix.lower()
    from bp import facts_models  # noqa: PLC0415 - the IFC, DXF and raster readers load only when needed

    for build in (facts_models.model_facts, facts_models.dxf_facts):
        found = build(path)
        if found is not None:
            return found.model_copy(update={"conflicts": conflicts.find(found)})
    if suffix == ".pdf":
        from bp import facts_swiss  # noqa: PLC0415 - the PDF readers load only for a PDF

        found = facts_swiss.swiss_facts(path)
        if found is not None:
            return found.model_copy(update={"conflicts": conflicts.find(found)})
        return DocumentFacts(kind="unsupported", unknown=("document_facts reads Swiss plan PDFs and raster sheets.",))
    if suffix not in RASTER_SUFFIXES:
        return DocumentFacts(kind="unsupported", unknown=("document_facts reads Swiss plan PDFs and raster sheets.",))
    return _raster_facts(path, calibration, read_text=read_text)


def _raster_facts(path: str | Path, calibration: Calibration | None, *, read_text: bool) -> DocumentFacts:
    """The facts of a raster: a small plan through the raster tools, a large sheet through its plan."""
    from bp import facts_models  # noqa: PLC0415 - the raster readers load only when needed

    rgb = ocr.to_rgb(path)
    height, width = rgb.shape[:2]
    page = Page(index=0, width=float(width), height=float(height))
    if not sheet_text.is_sheet(rgb):
        from bp import facts_scan  # noqa: PLC0415 - a historic scan: OCR facts, no room model

        found = facts_scan.scan_facts(path, rgb, calibration) or facts_models.raster_facts(path, rgb, calibration)
        if found is not None:
            return found.model_copy(update={"conflicts": conflicts.find(found)})
        return DocumentFacts(kind="raster", pages=(page,), unknown=("A small raster plan: ask the agent tools.",))
    lines = sheet_text.read_lines(rgb) if read_text else sheet_text.cached_lines(rgb)
    if lines is None:
        return DocumentFacts(kind="sheet", pages=(page,), ocr_pending=True,
                             unknown=("The text of this sheet is not read yet.",))  # fmt: skip
    return sheet_facts(sheet_plan.plan_for(rgb, lines, calibration))
