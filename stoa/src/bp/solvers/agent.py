"""The agent solver: a model composes trusted tools. One tool set for each kind of document.

The model is `BP_AGENT_MODEL` (default claude-haiku-5.5) through the Hostinger AI Router. A document with no
tool (a raster image today) gives an abstention without a model call.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shapely.geometry import Point, Polygon, box

from bp.agent.core import ToolOutput, ToolSpec, run_agent
from bp.contract import Abstain, AnswerRecord, Calibration, Evidence, IngestReport, MissingReason, Question
from bp.llm import ChatResult, chat
from bp.solvers.mep_tools import mep_tools
from bp.tools import dxf_plan, ifc_model, ifc_sheet, pdf_text, swiss_plan

if TYPE_CHECKING:
    from collections.abc import Callable

    from bp.contract import Step
    from bp.facts import DocumentFacts
    from bp.tools import count_head

RASTER_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"})

NO_ARGS: dict[str, Any] = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}


def _args(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _openings(plan: swiss_plan.SwissPlan) -> dict[str, tuple[int, int]]:
    """For each room number: the windows and the distinct door openings within 6 cm of the room polygon."""
    if plan.scale is None:
        return {}
    touch = dxf_plan.TOUCH_M / plan.scale.metres_per_point
    windows = [box(*f.bbox) for f in plan.fixtures if f.kind == "window"]
    doors = [box(*key) for key in {tuple(round(v, 1) for p in e.points for v in p) for e in plan.doors.evidence}]
    out: dict[str, tuple[int, int]] = {}
    for r in plan.rooms:
        if len(r.polygon) < 3:
            continue
        shape = Polygon(r.polygon)
        shape = shape if shape.is_valid else shape.buffer(0)
        near_windows = sum(1 for w in windows if w.distance(shape) <= touch)
        out[r.number] = (near_windows, sum(1 for d in doors if d.distance(shape) <= touch))
    return out


def swiss_tools(plan: swiss_plan.SwissPlan) -> tuple[str, list[ToolSpec]]:
    openings = _openings(plan)

    def rooms(_: dict[str, Any]) -> ToolOutput:
        data = [
            {
                "windows": openings.get(r.number, (None, None))[0],
                "doors": openings.get(r.number, (None, None))[1],
                "number": r.number,
                "label": r.label,
                "area_m2": r.area_m2,
                "printed_area_m2": r.printed_area_m2,
                "apartment": r.apartment,
                "outdoor": r.outdoor,
                "shared_circulation": r.fill == swiss_plan.SHARED_FILL,
                "entity_id": swiss_plan.room_id(r.number),
            }
            for r in plan.rooms
        ]
        evidence = tuple(e for r in plan.rooms for e in r.evidence()[:1])
        return ToolOutput(data={"rooms": data}, evidence=evidence)

    def fixtures(arguments: dict[str, Any]) -> ToolOutput:
        kind = _text(arguments.get("kind"))
        if kind == "door":
            fact = swiss_plan.door_count(plan)
            data = {
                "kind": kind,
                "count": fact.value,
                "distinct_places": plan.doors.distinct,
                "note": fact.note,
                "which_to_use": "Answer 'how many doors are drawn' with `count`: the drawing holds one door symbol per "
                "side of a shared wall and the source counts each. Use `distinct_places` only when the question asks "
                "for distinct door openings.",
            }
            return ToolOutput(data=data, evidence=fact.evidence[:40])
        if kind not in {"toilet", "washbasin", "bathtub", "shower", "kitchen", "window"}:
            return ToolOutput(ok=False, error=f"unknown kind {kind}")
        fact = swiss_plan.fixture_count(plan, kind)
        return ToolOutput(
            data={"kind": kind, "count": fact.value, "warnings": fact.warnings}, evidence=fact.evidence[:40]
        )

    def apartments(_: dict[str, Any]) -> ToolOutput:
        data = []
        for a in plan.apartments:
            fact = swiss_plan.apartment_area(plan, a.letter)
            members = [r.number for r in plan.rooms if r.apartment == a.letter]
            data.append({"letter": a.letter, "living_area_m2": fact.value, "rooms": members, "warnings": fact.warnings,
                         "entity_id": swiss_plan.apartment_id(a.letter)})  # fmt: skip
        return ToolOutput(data={"apartments": data})

    scale = plan.scale

    def read_scale(_: dict[str, Any]) -> ToolOutput:
        if scale is None:
            return ToolOutput(data={"scale": None, "note": "no scale text found in the title block"})
        data = {"scale": f"1:{scale.ratio}", "ratio": scale.ratio, "paper": scale.paper,
                "confirmed_by_scale_bar": scale.agrees, "entity_id": "scale",
                "note": "from the scale text of the title block; confirmed_by_scale_bar is null when the sheet has "
                "no scale bar"}  # fmt: skip
        return ToolOutput(data=data, evidence=(scale.evidence,))

    context = (
        "Document: a vector PDF floor plan of one storey (residential). Scale: "
        + (f"1:{scale.ratio}, confirmed by the scale bar: {scale.agrees}" if scale else "not found")
        + f". It has {len(plan.rooms)} numbered rooms and {len(plan.apartments)} apartment tags. Room areas are net "
        "polygon areas at the sheet scale. For each room, `windows` and `doors` count the openings that touch the room "
        "(a door between two rooms counts for both). The plan shows no heights and no materials."
    )
    return context, [
        ToolSpec("list_rooms", "Every numbered room: number, label, net area in m2, apartment letter, outdoor flag (balcony, loggia, terrace), shared circulation flag, windows and doors that touch the room.", NO_ARGS, rooms),
        ToolSpec("count_symbols", "Count drawn symbols of one kind on the whole sheet.", _args({"kind": {"type": "string", "enum": ["door", "window", "toilet", "washbasin", "bathtub", "shower", "kitchen"]}}, ["kind"]), fixtures),
        ToolSpec("list_apartments", "Every apartment: letter, living area in m2 (indoor rooms inside its outline, no balconies), room numbers.", NO_ARGS, apartments),
        ToolSpec("read_scale", "The scale of the drawing (such as '1:200') from the title block, and whether the scale bar confirms it. Use it for a question about the scale.", NO_ARGS, read_scale),
    ]  # fmt: skip


def sheet_tools(sheet: ifc_sheet.SheetFacts) -> tuple[str, list[ToolSpec]]:
    shapes = [Polygon(r.points) for r in sheet.rooms]

    def rooms(_: dict[str, Any]) -> ToolOutput:
        data = []
        for region, shape in zip(sheet.rooms, shapes, strict=True):
            inside = [line.text for line in sheet.lines if shape.contains(Point(line.x, line.y))]
            nested = sum(1 for other in shapes if other is not shape and shape.contains(other.representative_point()))
            data.append(
                {
                    "region": region.index,
                    "area_m2": round(region.area_m2, 2),
                    "texts_inside": inside[:12],
                    "regions_nested_inside": nested,
                }
            )
        evidence = tuple(Evidence(kind="polygon", points=r.points[:40], ref=str(r.index)) for r in sheet.rooms[:40])
        return ToolOutput(data={"room_regions": data}, evidence=evidence)

    def find(arguments: dict[str, Any]) -> ToolOutput:
        found = ifc_sheet.room_area(sheet, _text(arguments.get("label")))
        return ToolOutput(data=found.model_dump(mode="json", exclude={"tag_xy", "region"}))

    context = (
        f"Document: a vector PDF sheet exported from a BIM model. Title: {sheet.title!r}. Storey: {sheet.storey!r}. "
        f"Sheet kind: {sheet.kind}. Scale 1:{sheet.scale_ratio}, confirmed by two witnesses: {sheet.scale_confirmed}. "
        "The sheet shows ONE storey. It prints no areas: a room area is the room polygon at the sheet scale. It cannot "
        "give counts for the whole model, volumes, heights or wall lengths. Doors and windows are drawn but no tool counts them. "
        "Room names repeat on a sheet. For a which-room question, answer with the room tag or number (the identifier text "
        "inside the region) as a string, or 'name (tag)'. Never answer with the bare name."
    )
    return context, [
        ToolSpec("list_room_regions", "Every room polygon on the sheet with its area in m2 and the texts inside it (room name and number).", NO_ARGS, rooms),
        ToolSpec("find_room", "The area of one room by its tag, for example 'Living Room (A102)'. Status found, no_label, ambiguous or no_scale.", _args({"label": {"type": "string"}}, ["label"]), find),
    ]  # fmt: skip


def model_tools(model: ifc_model.IfcModel) -> tuple[str, list[ToolSpec]]:
    info = ifc_model.project_info(model)
    ids = ifc_model.space_ids(model)

    def spaces(arguments: dict[str, Any]) -> ToolOutput:
        storey = _text(arguments.get("storey")) or None
        found = ifc_model.spaces(model, storey)
        data = [s.model_dump(mode="json", exclude={"global_id"}) | {"entity_id": ids[s.global_id]} for s in found]
        evidence = tuple(Evidence(kind="ifc_element", ref=s.global_id, note=s.name) for s in found[:60])
        return ToolOutput(data={"spaces": data}, evidence=evidence)

    def count(arguments: dict[str, Any]) -> ToolOutput:
        storey = _text(arguments.get("storey")) or None
        target = _text(arguments.get("what"))
        if target in ifc_model.CATEGORY_CLASSES:
            got = ifc_model.count_elements(model, target, storey)
        else:
            got = ifc_model.count_class(model, target, storey)
        evidence = tuple(Evidence(kind="ifc_element", ref=g) for g in got.global_ids[:60])
        return ToolOutput(data=got.model_dump(mode="json", exclude={"global_ids"}), evidence=evidence)

    def quantity(arguments: dict[str, Any]) -> ToolOutput:
        storey = _text(arguments.get("storey")) or None
        got = ifc_model.storey_quantity(model, arguments["category"], _text(arguments.get("quantity")), storey)
        return ToolOutput(data=got.model_dump(mode="json", exclude={"global_ids"}))

    def project(_: dict[str, Any]) -> ToolOutput:
        return ToolOutput(data=info.model_dump(mode="json"))

    categories = sorted(ifc_model.CATEGORY_CLASSES)
    storey_arg = {"type": "string", "description": "storey name exactly as listed, or empty for the whole model"}
    context = (
        f"Document: an IFC building model ({info.schema_name}), project {info.project_name!r}. Storeys: "
        + ", ".join(repr(s.name) for s in info.storeys)
        + ". Quantities come from the model's quantity sets; a value of null means the model has none. For a which-room "
        "question, answer with the space `name` (the room number) as a string with unit null, or 'long name (name)'. "
        "Never answer with the bare long name: long names repeat."
    )
    tools = [
        ToolSpec("project_info", "Schema, project names, authoring application, organisations, storeys with elevations.", NO_ARGS, project),
        ToolSpec("list_spaces", "Rooms (IfcSpace): name, long name, storey, net floor area m2, gross area, height.", _args({"storey": storey_arg}, ["storey"]), spaces),
        ToolSpec("count_elements", f"Count elements. `what` is a category ({', '.join(categories)}) or an IFC class name such as IfcRailing.", _args({"what": {"type": "string"}, "storey": storey_arg}, ["what", "storey"]), count),
        ToolSpec("sum_quantity", "Sum a quantity over a category: NetVolume, GrossVolume, Length, NetSideArea, NetArea, GrossArea. SI units.", _args({"category": {"type": "string", "enum": categories}, "quantity": {"type": "string"}, "storey": storey_arg}, ["category", "quantity", "storey"]), quantity),
    ]  # fmt: skip
    mep_context, mep_specs = mep_tools(model)  # pipes, ducts, fittings, terminals, systems; none without MEP elements
    return (f"{context} {mep_context}" if mep_context else context), tools + mep_specs


def dxf_tools(plan: dxf_plan.DxfPlan) -> tuple[str, list[ToolSpec]]:
    ids = dxf_plan.room_ids(plan)

    def rooms(_: dict[str, Any]) -> ToolOutput:
        data = [
            r.model_dump(mode="json", exclude={"points"}) | {"apartment": r.unit, "entity_id": ids[i]}
            for i, r in enumerate(plan.rooms)
        ]
        evidence = tuple(Evidence(kind="polygon", points=r.points[:40], ref=r.number or "") for r in plan.rooms[:40])
        return ToolOutput(data={"rooms": data}, evidence=evidence)

    def layers(_: dict[str, Any]) -> ToolOutput:
        return ToolOutput(
            data={"entities_per_layer": plan.layers, "texts_outside_rooms": list(plan.texts_outside_rooms)}
        )

    unit = (
        f"one drawing unit is {plan.unit_m} m" if plan.unit_m else "the drawing unit is unknown, so no area is reliable"
    )
    context = (
        f"Document: a CAD drawing (DXF) of a floor plan; {unit}. It has {len(plan.rooms)} room outlines and "
        f"apartments {list(plan.units)}. Room areas are polygon areas. Entity counts per layer are raw CAD entities, "
        "not counts of doors or windows (one door is several entities). For each room, `windows` and `doors` count the "
        "openings that touch the room (a door between two rooms counts for both). A room with number null is a shaft or "
        "a void, not a numbered room. The drawing has no heights and no materials."
    )
    return context, [
        ToolSpec("list_rooms", "Every room outline: number, label, polygon area in m2, printed area, apartment letter, outdoor flag (balcony, loggia, terrace), windows and doors that touch the room.", NO_ARGS, rooms),
        ToolSpec("list_layers", "Raw entity counts per CAD layer and the texts outside rooms.", NO_ARGS, layers),
    ]  # fmt: skip


COUNT_MEANING = {
    "doors": "doors drawn on the plan, interior and entrance together",
    "windows": "windows drawn on the plan",
    "toilets": "toilet seats",
    "sinks": "sinks, kitchen sinks included",
    "showers_tubs": "showers and bathtubs together",
    "bathrooms": "bathrooms and washrooms",
    "wc_rooms": "separate WC rooms",
    "saunas": "saunas",
    "kitchens": "kitchens",
    "bedrooms": "bedrooms",
    "balconies": "balconies",
    "floors": "floors shown on the sheet",
}


def plan_counts(
    counts: count_head.PlanCounts, detected: dict[str, int] | None = None
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """The whole-plan counts that pass their tool's doubt rule, and the families with no trusted count."""
    detected = detected or {}
    fallback = os.environ.get("BP_COUNT_FALLBACK", "1") != "0"
    trusted: dict[str, dict[str, Any]] = {}
    unsure = []
    for family, head in sorted(counts.counts.items()):
        if family in detected:
            trusted[family] = {"count": detected[family], "by": "symbol detector"}
        elif fallback and head.trusted and not head.overflow:
            trusted[family] = {"count": head.value, "by": "count head", "probability": round(head.probability, 3)}
        else:
            unsure.append(family)
    return trusted, unsure


def raster_count_tools(
    counts: count_head.PlanCounts, detected: dict[str, int] | None = None
) -> tuple[str, list[ToolSpec]]:
    """Whole-plan counts. The symbol detector comes first; the count head fills a family the detector doubts.

    Only a count that passes its tool's own doubt rule is given as a number.
    """

    def whole_plan(_: dict[str, Any]) -> ToolOutput:
        trusted, unsure = plan_counts(counts, detected)
        data = {"counts": trusted, "not_sure": unsure, "meaning": COUNT_MEANING}
        return ToolOutput(ok=True, data=data, evidence=())

    context = (
        "The document is a raster image of a residential floor plan (a scan or a drawing with no vector data). "
        "One tool gives whole-plan counts from a trained model. It cannot say which room an object is in, and it "
        "gives no areas and no lengths. A family under `not_sure` has no trusted count: abstain on it."
    )
    tools = [
        ToolSpec(
            name="count_on_plan",
            description="Whole-plan counts of doors, windows, toilets, sinks, showers and tubs, bathrooms, WC rooms, "
            "saunas, kitchens, bedrooms, balconies and floors. Only counts the model is sure of.",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            run=whole_plan,
            method="model",
        )
    ]
    return context, tools


class AgentSolver:
    name = "agent"

    def __init__(self) -> None:
        self.context = ""
        self.tools: list[ToolSpec] = []
        self.kind = "none"
        self.model = os.environ.get("BP_AGENT_MODEL", "claude-haiku-5.5")
        self.path = ""
        self.calibration: Calibration | None = None
        self.facts: DocumentFacts | None = None
        self.on_step: Callable[[Step], None] | None = None  # called after each tool call, for a live trace

    def ingest(self, path: str) -> IngestReport:
        self.path = path
        with open(path, "rb") as handle:  # noqa: PTH123
            head = handle.read(64)
        if head.startswith(b"ISO-10303-21"):
            self.kind = "ifc"
            model = ifc_model.open_model(path)
            self.context, self.tools = model_tools(model)
            from bp.solvers.quantity_tools import ifc_quantity_tools  # noqa: PLC0415 - contractor quantities

            extra_context, extra_tools = ifc_quantity_tools(model)
            self.context, self.tools = f"{self.context}\n{extra_context}", [*self.tools, *extra_tools]
        elif pdf_text.is_pdf(path):
            plan = swiss_plan.read_plan(path) if pdf_text.page_count(path) == 1 else None
            if plan is not None and plan.detection.is_plan:
                self.kind = "plan_pdf"
                self.context, self.tools = swiss_tools(plan)
            else:
                sheet = ifc_sheet.read_sheet(path)
                if ifc_sheet.is_bim_sheet(sheet):
                    self.kind = "bim_sheet"
                    self.context, self.tools = sheet_tools(sheet)
        elif dxf_plan.is_dxf(path):
            self.kind = "dxf"
            self.context, self.tools = dxf_tools(dxf_plan.read_dxf(path))
        elif Path(path).suffix.lower() in RASTER_SUFFIXES:
            # Lazy imports: torch and the OCR models are slow to load, and only rasters need them.
            from bp.solvers import raster_tools, scan_tools  # noqa: PLC0415
            from bp.tools import count_head, ocr  # noqa: PLC0415

            scan = scan_tools.scan_lines(path)
            if scan is not None:
                # A historic scan: text, title block, scale and look tools; no room model and no detector.
                self.kind = "scan"
                self.context, self.tools = scan_tools.scan_tools(ocr.to_rgb(path), scan, self.calibration)
                self.facts = self._document_facts(path)
                return IngestReport(ok=True, detail=self.kind)

            def detect() -> Any:  # noqa: ANN401 - CubicasaDetectSolver, imported late
                # Run once per image and process: the facts of the same image use the same detections.
                return raster_tools.detector_for(path)

            use = detect if os.environ.get("BP_ROOM_OPENINGS", "1") != "0" else None
            rooms = raster_tools.raster_tools(path, use, self.calibration)
            if rooms is not None:
                self.kind = "raster_rooms"
                self.context, self.tools = rooms
            counts = count_head.count_plan(Path(path), count_head.get_model("e1.json"))
            if counts.in_distribution:
                detector = detect()
                detected = detector.sure_counts() if detector is not None else None
                context, tools = raster_count_tools(counts, detected)
                self.kind = "raster_counts" if rooms is None else "raster_rooms+counts"
                self.context = (self.context + "\n" + context).strip()
                self.tools = [*self.tools, *tools]
        from bp.solvers.quantity_tools import path_quantity_tools  # noqa: PLC0415 - contractor quantities

        if (quantities := path_quantity_tools(self.kind, path)) is not None:
            self.context, self.tools = f"{self.context}\n{quantities[0]}", [*self.tools, *quantities[1]]
        self.facts = self._document_facts(path)
        return IngestReport(ok=True, detail=self.kind)

    def _document_facts(self, path: str) -> DocumentFacts | None:
        """The facts of a Swiss plan or a large sheet, so that the agent knows which of them do not add up."""
        from bp import facts  # noqa: PLC0415 - it loads the readers; only these two kinds need it

        if self.kind == "plan_pdf":
            return facts.document_facts(path)
        if self.kind == "scan":
            return facts.document_facts(path, self.calibration)
        if Path(path).suffix.lower() in RASTER_SUFFIXES and self.tools:
            from bp.tools import ocr, sheet_text  # noqa: PLC0415

            if sheet_text.is_sheet(ocr.to_rgb(path)):
                return facts.document_facts(path, self.calibration)
        return None

    def calibrate(self, calibration: Calibration) -> None:
        """Take a scale from the user. Only a raster sheet uses it now: the tools are made again with it."""
        self.calibration = calibration
        if self.path and Path(self.path).suffix.lower() in RASTER_SUFFIXES:
            self.context, self.tools, self.kind = "", [], "none"
            self.ingest(self.path)

    def ask(self, question: Question) -> AnswerRecord:
        if not self.tools:
            abstain = Abstain(
                reason=MissingReason.UNSUPPORTED,
                detail="no trusted tool reads this kind of document yet",
                request="a vector PDF, a DXF or an IFC file of the same drawing",
            )
            return AnswerRecord(status="abstained", abstain=abstain)

        def call(messages: list[dict[str, Any]], schemas: list[dict[str, Any]]) -> ChatResult:
            return chat(self.model, messages, tools=schemas, max_tokens=1500, tag=f"agent:{self.kind}")

        return run_agent(
            question.text, self.tools, call, context=self.context, on_step=self.on_step, facts=self.facts
        ).record
