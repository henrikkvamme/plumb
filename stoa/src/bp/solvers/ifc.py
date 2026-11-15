"""The IFC solver: an IFC model, or a PDF sheet exported from one. It composes the ifc_model and ifc_sheet tools.

Route by content, not by extension:
- an IFC file: the templated questions (counts, areas, volumes, lengths) are answered from the model; other
  questions go to the free-text reporter at the end of this module;
- a BIM sheet (PDF): room areas, the room count and the storey room total are answered from the polygons and
  the scale; everything a storey sheet does not hold is an abstention with the reason;
- anything else: an abstention, because this solver does not read it.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from typing import TYPE_CHECKING, Literal

from bp.contract import (
    Abstain,
    AnswerRecord,
    Calibration,
    Evidence,
    Frozen,
    IngestReport,
    MissingReason,
    Question,
    Step,
)
from bp.tools import ifc_model as im
from bp.tools import ifc_sheet as sh

if TYPE_CHECKING:
    from ifcopenshell import entity_instance

Family = Literal[
    "area_room", "area_total_storey", "volume_slabs", "volume_walls", "length_walls", "area_wall_side",
    "count_storey", "count_model",
]  # fmt: skip

MAX_EVIDENCE = 40

_QUOTE = re.compile(r"'([^']*)'|„([^“”\"]*)[“”\"]|«([^»]*)»|\"([^\"]*)\"|“([^”]*)”")

# Words per element category, as whole lower-case tokens, in the languages of the public questions.
_CATEGORY_WORDS: dict[im.Category, frozenset[str]] = {
    "sanitary": frozenset({"sanitary", "sanitaire", "sanitärobjekte", "sanitär"}),
    "light": frozenset({"light", "iluminat", "leuchten", "verlichting", "belysning"}),
    "door": frozenset({"door", "doors", "deuren", "døre", "drzwi", "ust", "türen", "puertas", "porte", "uși"}),
    "window": frozenset({
        "window", "windows", "ramen", "vinduer", "okien", "fenster", "akent", "ventanas", "finestre", "ferestre",
    }),
    "stair": frozenset({"stair", "stairs", "scări", "trapper", "schodów", "treppi", "treppen", "escaleras", "scale"}),
    "column": frozenset({"column", "columns", "stâlpi", "kolommen", "søjler", "posti", "stützen", "pilares", "pilastri"}),
    "beam": frozenset({"beam", "beams", "grinzi", "balken", "bjælker", "belek", "träger", "vigas", "tala", "travi"}),
    "wall": frozenset({"wall", "walls", "wanden", "vægge", "ścian", "seina", "wände", "pereți", "muros", "muri"}),
    "space": frozenset({
        "room", "rooms", "spaces", "ruimtes", "rum", "pomieszczeń", "ruumi", "räume", "locales", "locali", "camere",
    }),
}  # fmt: skip
_COUNT_START = ("how many", "wie viele", "hoeveel", "hvor mange", " ile ", " mitu ", "cuál es el número", "care este numărul",
                "qual è il numero", "combien")  # fmt: skip
_MODEL_WORDS = frozenset({"model", "modell", "modellen", "modelo", "modelul", "mudelis", "modelu", "modello", "modèle"})
_SLAB_WORDS = frozenset({"slabs", "slab", "dæk", "plader", "vloeren", "decken", "bodenplatten", "losas", "solai"})
_WALL_WORDS = _CATEGORY_WORDS["wall"]
_SIDE_MARKS = ("side area", "sideareal", "zijoppervlakte", "seitenfläche")
_TOTAL_MARKS = ("total", "samlede", "łączna", "kokku", "totale", "gesamte", "kõigi")
_LENGTH_MARKS = ("length", "længde", "lengte", "wie lang", "in metres", "in meters", "i meter", "in metern", "długość")


class IfcQuery(Frozen):
    family: Family
    category: im.Category | None = None
    room: str | None = None
    storey: str | None = None
    model_name: str | None = None


def quotes(text: str) -> list[str]:
    return [next((g for g in m if g), "") for m in _QUOTE.findall(text)]


def parse_question(text: str) -> IfcQuery | None:  # noqa: PLR0911 - one branch per template family
    """Map a templated question (any of the public languages) to a query. None when it is not a template."""
    low = " " + text.casefold() + " "
    tokens = set(re.findall(r"\w+", low))
    found = quotes(text)
    first = found[0] if found else None
    if any(s in low for s in _COUNT_START):
        category = next((c for c, words in _CATEGORY_WORDS.items() if tokens & words), None)
        if category is None:
            return None
        if tokens & _MODEL_WORDS:
            return IfcQuery(family="count_model", category=category, model_name=first)
        return IfcQuery(family="count_storey", category=category, storey=first) if first else None
    if "m³" in low or re.search(r"\bm3\b", low):
        if not first:
            return None
        if tokens & _SLAB_WORDS:
            return IfcQuery(family="volume_slabs", category="slab", storey=first)
        if tokens & _WALL_WORDS:
            return IfcQuery(family="volume_walls", category="wall", storey=first)
        return None
    if "m²" in low or re.search(r"\bm2\b", low):
        if any(m in low for m in _SIDE_MARKS):
            return IfcQuery(family="area_wall_side", category="wall", storey=first) if first else None
        if len(found) >= 2:
            return IfcQuery(family="area_room", category="space", room=found[0], storey=found[1])
        if first and any(m in low for m in _TOTAL_MARKS):
            return IfcQuery(family="area_total_storey", category="space", storey=first)
        return None
    if first and any(m in low for m in _LENGTH_MARKS) and tokens & _WALL_WORDS:
        return IfcQuery(family="length_walls", category="wall", storey=first)
    return None


# ----------------------------------------------------------------------------- records


def abstain(
    reason: MissingReason, detail: str, request: str, *, tool: str, estimate: float | None = None
) -> AnswerRecord:
    return AnswerRecord(
        status="abstained",
        abstain=Abstain(reason=reason, detail=detail, request=request),
        best_estimate=estimate,
        steps=(Step(tool=tool, method="deterministic", summary=detail),),
    )


def _ids(global_ids: tuple[str, ...], note: str) -> tuple[Evidence, ...]:
    return tuple(Evidence(kind="ifc_element", ref=g, note=note) for g in global_ids[:MAX_EVIDENCE])


QTO_FOR: dict[Family, str] = {
    "volume_slabs": "NetVolume",
    "volume_walls": "NetVolume",
    "length_walls": "Length",
    "area_wall_side": "NetSideArea",
}


# ----------------------------------------------------------------------------- the IFC route


def answer_model(model: im.IfcModel, q: IfcQuery) -> AnswerRecord:  # noqa: PLR0911 - one exit per family
    tool = "ifc_model"
    if q.family == "count_model" and q.category is not None:
        result = im.count_elements(model, q.category)
        return AnswerRecord(
            status="answered", value=result.count, confidence=0.95, convention=result.rule,
            evidence=_ids(result.global_ids, q.category),
            steps=(Step(tool=f"{tool}.count_elements", method="deterministic", summary=result.rule),),
        )  # fmt: skip
    if q.storey is not None and not im.match_storeys(model, q.storey):
        return abstain(MissingReason.NOT_IN_MODEL, f"no storey named {q.storey!r} in the model",
                       "name a storey of this model", tool=tool)  # fmt: skip
    if q.family == "count_storey" and q.category is not None:
        result = im.count_elements(model, q.category, q.storey)
        return AnswerRecord(
            status="answered", value=result.count, confidence=0.9, convention=result.rule,
            evidence=_ids(result.global_ids, q.category),
            steps=(Step(tool=f"{tool}.count_elements", method="deterministic", summary=result.rule),),
        )  # fmt: skip
    if q.family == "area_room" and q.room is not None:
        return _room_area_model(model, q.room, q.storey)
    if q.family == "area_total_storey" and q.storey is not None:
        total = im.storey_space_area(model, q.storey)
        if total.value is None or total.n_with_value < total.n_elements:
            return abstain(MissingReason.NOT_IN_MODEL, f"{total.n_elements - total.n_with_value} of {total.n_elements} "
                           "spaces have no area", "give the missing room areas", tool=tool, estimate=total.value)  # fmt: skip
        return AnswerRecord(
            status="answered", value=round(total.value, 2), unit="m2", confidence=0.9 if total.source == "qto" else 0.8,
            convention=f"sum of NetFloorArea over {total.n_elements} spaces ({total.source})",
            evidence=_ids(total.global_ids, "space"),
            steps=(Step(tool=f"{tool}.storey_space_area", method="deterministic", summary=total.source),),
        )  # fmt: skip
    if q.family in QTO_FOR and q.category is not None:
        total = im.storey_quantity(model, q.category, QTO_FOR[q.family], q.storey)
        if total.value is None:
            return abstain(MissingReason.NOT_IN_MODEL, f"the {q.category} elements carry no {total.quantity} quantity",
                           "a model exported with base quantities", tool=tool)  # fmt: skip
        return AnswerRecord(
            status="answered", value=round(total.value, 2), unit=total.unit, confidence=0.9,
            convention=f"sum of Qto {total.quantity} over {total.n_with_value} of {total.n_elements} elements",
            evidence=_ids(total.global_ids, q.category),
            steps=(Step(tool=f"{tool}.storey_quantity", method="deterministic", summary=total.quantity),),
        )  # fmt: skip
    return abstain(MissingReason.UNSUPPORTED, "no rule for this question", "-", tool=tool)


def _room_area_model(model: im.IfcModel, room: str, storey: str | None) -> AnswerRecord:
    hits = im.find_spaces(model, room, storey)
    if not hits:
        return abstain(MissingReason.NOT_IN_MODEL, f"no space named {room!r}", "name a space of this model",
                       tool="ifc_model.find_spaces")  # fmt: skip
    areas = [h.net_floor_area_m2 for h in hits if h.net_floor_area_m2 is not None]
    if not areas:
        return abstain(MissingReason.NOT_IN_MODEL, "the space has no quantity and no body geometry",
                       "a model with space quantities", tool="ifc_model.space_info")  # fmt: skip
    if max(areas) > min(areas) * 1.02:
        return abstain(MissingReason.AMBIGUOUS, f"{len(hits)} spaces match {room!r} with different areas",
                       "give the space number", tool="ifc_model.find_spaces", estimate=round(areas[0], 2))  # fmt: skip
    space = hits[0]
    value = space.net_floor_area_m2 or 0.0
    return AnswerRecord(
        status="answered", value=round(value, 2), unit="m2",
        confidence=0.97 if space.area_source == "qto" else 0.9,
        convention="Qto NetFloorArea" if space.area_source == "qto" else "plan footprint of the space body",
        evidence=(Evidence(kind="ifc_element", ref=space.global_id, note=f"{space.long_name} ({space.name})"),),
        steps=(Step(tool="ifc_model.find_spaces", method="deterministic", summary=space.area_source),),
    )  # fmt: skip


# ----------------------------------------------------------------------------- the sheet route

_SHEET_REQUEST = "the IFC model of this project, or a sheet that prints this value"


def _sheet_evidence(sheet: sh.SheetFacts, regions: list[int], note: str) -> tuple[Evidence, ...]:
    return tuple(
        Evidence(kind="polygon", page=0, points=sheet.rooms[i].points, note=note) for i in regions[:MAX_EVIDENCE]
    )


def answer_sheet(sheet: sh.SheetFacts, q: IfcQuery) -> AnswerRecord:  # noqa: PLR0911 - one exit per family
    tool = "ifc_sheet"
    if q.family == "count_model":
        return abstain(MissingReason.NOT_ON_DOCUMENT, "a sheet shows one storey or view, not the whole model",
                       _SHEET_REQUEST, tool=tool)  # fmt: skip
    if q.family in QTO_FOR:
        return abstain(MissingReason.NOT_ON_DOCUMENT, "a plan cut does not hold volumes, wall lengths or side areas "
                       "(they need heights and net quantities)", _SHEET_REQUEST, tool=tool)  # fmt: skip
    if q.storey is not None and not sh.storey_matches(sheet, q.storey):
        return abstain(MissingReason.NOT_ON_DOCUMENT, f"the sheet shows {sheet.storey!r}, not {q.storey!r}",
                       "the sheet of that storey", tool=tool)  # fmt: skip
    if q.family == "count_storey" and q.category != "space":
        return abstain(MissingReason.UNSUPPORTED, f"{q.category} symbols are drawn but not marked in a way this tool "
                       "counts reliably", "the IFC model, or a sheet with tagged symbols", tool=tool)  # fmt: skip
    if not sheet.rooms:
        return abstain(MissingReason.NOT_ON_DOCUMENT, "the sheet draws no room polygons", _SHEET_REQUEST, tool=tool)
    scale = Evidence(kind="scale", note=f"{sheet.m_per_pt} m per pt; 1:{sheet.scale_ratio}; "
                     f"{'bar and text agree' if sheet.scale_confirmed else 'one witness'}")  # fmt: skip
    if q.family == "count_storey":
        regions = list(range(len(sheet.rooms)))
        return AnswerRecord(
            status="answered", value=len(sheet.rooms), confidence=0.9,
            convention="every room polygon drawn on the sheet (a room modelled twice counts twice)",
            evidence=_sheet_evidence(sheet, regions, "room"),
            steps=(Step(tool=f"{tool}.rooms", method="deterministic", summary="room polygons"),),
        )  # fmt: skip
    if sheet.m_per_pt is None:
        return abstain(MissingReason.NO_SCALE, "no scale on the sheet", "give the scale or two points", tool=tool)
    if q.family == "area_total_storey":
        total = sh.total_room_area(sheet) or 0.0
        return AnswerRecord(
            status="answered", value=round(total, 2), unit="m2", confidence=0.8 if sheet.scale_confirmed else 0.6,
            convention="sum of the room polygons times the scale", evidence=(scale,),
            steps=(Step(tool=f"{tool}.total_room_area", method="deterministic", summary="polygon sum"),),
        )  # fmt: skip
    if q.family == "area_room" and q.room is not None:
        found = sh.room_area(sheet, q.room)
        if found.status == "found" and found.area_m2 is not None and found.region is not None:
            return AnswerRecord(
                status="answered", value=round(found.area_m2, 2), unit="m2",
                confidence=0.95 if sheet.scale_confirmed else 0.75,
                convention="the room polygon under the tag, times the scale (net of the drawn boundary)",
                evidence=(*_sheet_evidence(sheet, [found.region], q.room), scale),
                steps=(Step(tool=f"{tool}.room_area", method="deterministic", summary="polygon area"),),
            )  # fmt: skip
        reason = MissingReason.AMBIGUOUS if found.status == "ambiguous" else MissingReason.NOT_ON_DOCUMENT
        estimate = found.candidates[0] if found.candidates else None
        return abstain(reason, found.detail, "point at the room on the sheet", tool=f"{tool}.room_area",
                       estimate=round(estimate, 2) if estimate is not None else None)  # fmt: skip
    return abstain(MissingReason.UNSUPPORTED, "no rule for this question on a sheet", "-", tool=tool)


# ----------------------------------------------------------------------------- the solver


def sniff(path: str) -> Literal["ifc", "pdf", "other"]:
    with open(path, "rb") as handle:  # noqa: PTH123 - one small read
        head = handle.read(64)
    if head.lstrip().startswith(b"ISO-10303-21"):
        return "ifc"
    if head.startswith(b"%PDF"):
        return "pdf"
    return "other"


class IfcSolver:
    """One document: an IFC model or a BIM sheet."""

    name = "ifc"

    def __init__(self) -> None:
        self.kind: Literal["ifc", "pdf", "other"] = "other"
        self.model: im.IfcModel | None = None
        self.sheet: sh.SheetFacts | None = None
        self.detail = ""

    def ingest(self, path: str) -> IngestReport:
        started = time.perf_counter()
        self.kind = sniff(path)
        try:
            if self.kind == "ifc":
                self.model = im.open_model(path)
            elif self.kind == "pdf":
                self.sheet = sh.read_sheet(path)
        except Exception as exc:
            self.detail = f"{type(exc).__name__}: {exc}"[:300]
            self.model = None
            self.sheet = None
        return IngestReport(ok=True, detail=self.detail or self.kind, latency_ms=(time.perf_counter() - started) * 1e3)

    def calibrate(self, calibration: Calibration) -> None:
        del calibration

    def ask(self, question: Question) -> AnswerRecord:
        q = parse_question(question.text)
        if self.kind == "ifc":
            if self.model is None:
                return abstain(MissingReason.UNREADABLE, f"the IFC file did not parse: {self.detail}",
                               "a valid IFC file", tool="ifc_model.open_model")  # fmt: skip
            if q is None:
                return answer_text(self.model, question.text)
            return answer_model(self.model, q)
        if self.kind == "pdf" and self.sheet is not None and sh.is_bim_sheet(self.sheet):
            if q is None:
                return abstain(MissingReason.UNSUPPORTED, "the question is not one that this sheet reader parses",
                               "-", tool="ifc_sheet")  # fmt: skip
            return answer_sheet(self.sheet, q)
        return abstain(MissingReason.UNSUPPORTED, "this document is neither an IFC model nor a BIM sheet export",
                       "use a solver for this kind of document", tool="ifc.sniff")  # fmt: skip


# ----------------------------------------------------------------------------- free text (ifc_bench)

TextKind = Literal[
    "metadata", "location", "materials", "spaces", "largest_room", "space_heights", "levels", "thickness",
    "fire_rating", "load_bearing", "slab_volume", "wall_length", "types", "count", "systems",
]  # fmt: skip

# Bench words for element classes, checked in order (the first hit wins). Class names are IFC4; IFC2X3 MEP
# elements are found through their type class.
_TEXT_CLASSES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("curtain wall",), ("IfcCurtainWall",)),
    (("air terminal",), ("IfcAirTerminal",)),
    (("cable tray", "cable carrier", "cable routing"), ("IfcCableCarrierSegment", "IfcCableCarrierFitting")),
    (("light fixture", "lighting", "luminaire"), ("IfcLightFixture",)),
    (("sanitary", "plumbing fixture"), ("IfcSanitaryTerminal",)),
    (("door",), ("IfcDoor",)),
    (("window",), ("IfcWindow",)),
    (("wall",), ("IfcWall",)),
    (("column",), ("IfcColumn",)),
    (("beam",), ("IfcBeam",)),
    (("slab", "floor slab"), ("IfcSlab",)),
    (("stair",), ("IfcStair",)),
    (("railing",), ("IfcRailing",)),
    (("ceiling", "covering"), ("IfcCovering",)),
    (("furniture", "furnishing"), ("IfcFurniture", "IfcFurnishingElement")),
    (("pile",), ("IfcPile",)),
    (("footing", "foundation"), ("IfcFooting",)),
    (("roof",), ("IfcRoof",)),
    (("duct",), ("IfcDuctSegment",)),
    (("pipe",), ("IfcPipeSegment",)),
    (("fan",), ("IfcFan",)),
    (("filter",), ("IfcFilter",)),
    (("coil",), ("IfcCoil",)),
    (("damper", "controller"), ("IfcFlowController",)),
    (("pump",), ("IfcPump",)),
    (("valve",), ("IfcValve",)),
    (("member",), ("IfcMember",)),
    (("plate",), ("IfcPlate",)),
    (("space", "room"), ("IfcSpace",)),
)


class TextPlan(Frozen):
    kind: TextKind
    classes: tuple[str, ...] = ()
    label: str = ""
    side: Literal["exterior", "interior", "any"] = "any"


def plan_text(text: str) -> TextPlan | None:  # noqa: C901, PLR0911, PLR0912 - one rule per kind
    low = text.casefold()
    side: Literal["exterior", "interior", "any"] = "any"
    if re.search(r"\b(exterior|external|outer|outside|facade)\b", low):
        side = "exterior"
    elif re.search(r"\b(interior|internal|inner|inside)\b", low):
        side = "interior"
    hit = next(((words[0], classes) for words, classes in _TEXT_CLASSES if any(w in low for w in words)), None)
    label, classes = hit or ("", ())
    if re.search(r"software|schema|modell?ing standard|standards were|application", low):
        return TextPlan(kind="metadata")
    if re.search(r"project information|location|latitude|longitude|where is", low):
        return TextPlan(kind="location")
    if "material" in low and classes:
        return TextPlan(kind="materials", classes=classes, label=label, side=side)
    if "fire rating" in low and classes:
        return TextPlan(kind="fire_rating", classes=classes, label=label)
    if "load-bearing" in low or "load bearing" in low:
        return TextPlan(kind="load_bearing", classes=classes or ("IfcWall",), label=label or "wall")
    if "thickness" in low and classes:
        return TextPlan(kind="thickness", classes=classes, label=label, side=side)
    if re.search(r"largest (room|space)|biggest (room|space)|(room|space) .*is the largest", low):
        return TextPlan(kind="largest_room", classes=("IfcSpace",), label="space")
    if re.search(r"ceiling|tallest|lowest", low) and re.search(r"room|space", low):
        return TextPlan(kind="space_heights", classes=("IfcSpace",), label="space")
    if re.search(r"heights? of the (building )?(levels|storeys|floors)|building levels|storey elevations", low):
        return TextPlan(kind="levels")
    if re.search(r"(spaces|rooms) (are )?on|space breakdown|net floor area|spaces .*areas", low):
        return TextPlan(kind="spaces", classes=("IfcSpace",), label="space")
    if re.search(r"volume", low) and label == "slab":
        return TextPlan(kind="slab_volume", classes=classes, label=label)
    if re.search(r"length", low) and label == "wall":
        return TextPlan(kind="wall_length", classes=classes, label=label, side=side)
    if re.search(r"\bsystems?\b", low) and not classes:
        return TextPlan(kind="systems")
    if classes and re.search(
        r"\btypes?\b|breakdown|distribution|quantit|which .* (are|is) (used|installed|present)", low
    ):
        return TextPlan(kind="types", classes=classes, label=label, side=side)
    if classes and re.search(r"how many|number of|count", low):
        return TextPlan(kind="count", classes=classes, label=label, side=side)
    return None


def _side_ok(element: entity_instance, side: str) -> bool:
    if side == "any":
        return True
    flag = im.common_property(element, "IsExternal")
    return flag is (side == "exterior")


def _plan_elements(model: im.IfcModel, plan: TextPlan, text: str) -> list[entity_instance]:
    """The elements a plan is about. Roof slabs count as roof elements; 'floor slab' keeps floor slabs only."""
    elements = im.classes_elements(model, plan.classes)
    low = text.casefold()
    if plan.label == "roof":
        elements += [e for e in im.by_type(model, "IfcSlab") if getattr(e, "PredefinedType", None) == "ROOF"]
    if plan.label == "slab" and "floor slab" in low:
        elements = [e for e in elements if getattr(e, "PredefinedType", None) in {"FLOOR", "BASESLAB"}]
    return elements


def side_known(model: im.IfcModel, plan: TextPlan, text: str) -> bool:
    """True when the question has no exterior or interior filter, or when the model states IsExternal."""
    if plan.side == "any":
        return True
    return any(im.common_property(e, "IsExternal") is not None for e in _plan_elements(model, plan, text))


def _pct(part: int, whole: int) -> str:
    return f"{100.0 * part / whole:.1f}%" if whole else "-"


def _fmt(value: float, places: int = 2) -> str:
    return f"{value:.{places}f}"


def _storey_hint(model: im.IfcModel, text: str) -> im.StoreyInfo | None:
    """The storey that the question names: by its exact name, or 'ground floor' / 'level N' / 'Nth floor'."""
    levels = im.storeys(model)
    low = text.casefold()
    named = [s for s in levels if len(s.name) >= 2 and s.name.casefold() in low]
    if named:
        return max(named, key=lambda s: len(s.name))
    if not levels:
        return None
    ground = min(range(len(levels)), key=lambda i: abs(levels[i].elevation_m or 0.0))
    if re.search(r"ground (floor|level)|level 0\b", low):
        return levels[ground]
    ordinals = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8}
    match = re.search(
        r"level (\d+)\b|(\d+)(?:st|nd|rd|th) (?:floor|level)|(" + "|".join(ordinals) + r") (?:floor|level)", low
    )
    if match is None:
        return None
    number = int(match.group(1) or match.group(2)) if (match.group(1) or match.group(2)) else ordinals[match.group(3)]
    index = ground + number
    return levels[index] if 0 <= index < len(levels) else None


def _report(model: im.IfcModel, plan: TextPlan, text: str) -> tuple[str, tuple[str, ...]]:  # noqa: C901, PLR0911, PLR0912, PLR0915 - one block per kind
    """The answer text and the GlobalIds behind it."""
    if plan.kind == "metadata":
        header, info = im.header_info(model), im.project_info(model)
        lines = [f"IFC schema: {header.schema_name}"]
        lines += [f"View definition: {v}" for v in header.view_definitions]
        lines += [f"Authoring application: {a}" for a in info.applications]
        for app in im.by_type(model, "IfcApplication"):
            developer = getattr(app, "ApplicationDeveloper", None)
            name = getattr(developer, "Name", None) if developer is not None else None
            lines.append(f"Application version: {app.Version}; developer: {name or '-'}")
        lines += [f"Originating system: {header.originating_system}", f"Preprocessor: {header.preprocessor}"]
        lines.append(f"Time stamp: {header.timestamp}")
        lines += [f"Organization: {o}" for o in info.organizations]
        return "\n".join(lines), ()
    if plan.kind == "location":
        info, site = im.project_info(model), im.site_location(model)
        lines = [f"Project name: {info.project_name}", f"Project long name: {info.project_long_name}",
                 f"Site name: {site.site_name}", f"Buildings: {', '.join(info.building_names)}"]  # fmt: skip
        if site.latitude_dms:
            lines.append("Latitude: " + "° ".join(str(abs(v)) for v in site.latitude_dms[:3]))
        if site.longitude_dms:
            lines.append("Longitude: " + "° ".join(str(abs(v)) for v in site.longitude_dms[:3]))
        if site.elevation_m is not None:
            lines.append(f"Reference elevation: {_fmt(site.elevation_m)} m")
        if site.address:
            lines.append(f"Address: {site.address}")
        return "\n".join(lines), ()
    if plan.kind == "levels":
        levels = im.storeys(model)
        lines = [f"{len(levels)} storeys:"]
        for a, b in zip(levels, (*levels[1:], None), strict=True):
            height = ""
            if b is not None and a.elevation_m is not None and b.elevation_m is not None:
                height = f", storey height {_fmt(b.elevation_m - a.elevation_m)} m"
            elevation = _fmt(a.elevation_m) if a.elevation_m is not None else "?"
            lines.append(f"- {a.name}: elevation {elevation} m{height}")
        return "\n".join(lines), tuple(s.global_id for s in levels)
    if plan.kind == "systems":
        found = im.systems(model)
        lines = [f"Total systems: {len(found)}"] + [f"- {s.type_name}: {s.count} elements" for s in found]
        return "\n".join(lines), ()
    if plan.kind in {"spaces", "largest_room", "space_heights"}:
        return _report_spaces(model, plan, text)
    elements = [e for e in _plan_elements(model, plan, text) if _side_ok(e, plan.side)]
    ids = tuple(e.GlobalId for e in elements)
    title = f"{plan.side + ' ' if plan.side != 'any' else ''}{plan.label}s".strip()
    if plan.kind == "materials":
        mats = im.material_breakdown(elements, plan.label)
        lines = [f"Materials of {mats.total_elements} {title}:"]
        lines += [f"- {m.material}: {m.count} elements" for m in mats.materials]
        by_type: dict[str, set[str]] = {}
        for e in elements:
            by_type.setdefault(im.type_name(e), set()).update(im.material_names(e))
        lines += [f"{t}: {', '.join(sorted(ms))}" for t, ms in by_type.items() if ms]
        return "\n".join(lines), ids
    if plan.kind == "thickness":
        per: dict[str, list[float]] = {}
        for e in elements:
            t = im.thickness_m(model, e)
            if t is not None:
                per.setdefault(im.type_name(e), []).append(t)
        lines = [f"Thickness of {title} by type:"]
        lines += [f"- {k}: {round(1000 * sum(v) / len(v))} mm ({len(v)} elements)" for k, v in per.items()]
        return "\n".join(lines), ids
    if plan.kind == "fire_rating":
        per_rating: dict[str, set[str]] = {}
        for e in elements:
            value = im.common_property(e, "FireRating")
            if value not in (None, ""):
                per_rating.setdefault(im.type_name(e), set()).add(str(value))
        if not per_rating:
            return f"No fire rating information is stored for the {len(elements)} {title} in this model.", ids
        lines = [f"{len(per_rating)} {plan.label} types have a fire rating:"]
        lines += [f"- {k}: {', '.join(sorted(v))}" for k, v in per_rating.items()]
        return "\n".join(lines), ids
    if plan.kind == "load_bearing":
        flags = Counter(im.common_property(e, "LoadBearing") for e in elements)
        total = len(elements)
        yes, no = flags.get(True, 0), flags.get(False, 0)
        return (f"Total {title}: {total}\n- Load-bearing: {yes} ({_pct(yes, total)})\n"
                f"- Non-load-bearing: {no} ({_pct(no, total)})\n- Not stated: {total - yes - no}"), ids  # fmt: skip
    if plan.kind == "slab_volume":
        values = [im.qto_value(e, ("NetVolume", "GrossVolume")) for e in elements]
        known = [v * model.volume_scale for v in values if v is not None]
        return f"Total volume of {len(known)} of {len(elements)} slabs: {_fmt(sum(known))} m³", ids
    if plan.kind == "wall_length":
        values = [im.qto_value(e, ("Length",)) for e in elements]
        known = [v * model.length_scale for v in values if v is not None]
        return f"Total length of {len(known)} of {len(elements)} {title}: {_fmt(sum(known))} m", ids
    breakdown = im.type_breakdown(elements, plan.label)
    lines = [f"Total {title}: {breakdown.total}"]
    lines += [f"- {t.type_name}: {t.count} ({_pct(t.count, breakdown.total)})" for t in breakdown.types]
    return "\n".join(lines), ids


def _report_spaces(model: im.IfcModel, plan: TextPlan, text: str) -> tuple[str, tuple[str, ...]]:
    storey = _storey_hint(model, text) if plan.kind == "spaces" else None
    infos = list(im.spaces(model, storey.name if storey else None))
    ids = tuple(s.global_id for s in infos)
    with_area = [s for s in infos if s.net_floor_area_m2 is not None]
    if plan.kind == "largest_room":
        if not with_area:
            return "No space areas are stored in this model.", ids
        top = max(with_area, key=lambda s: s.net_floor_area_m2 or 0.0)
        height = f"\nHeight: {_fmt(top.height_m)} m" if top.height_m is not None else ""
        return (f"Largest room: {top.name} ({top.long_name})\nArea: {_fmt(top.net_floor_area_m2 or 0.0)} m²\n"
                f"Level: {top.storey}{height}"), (top.global_id,)  # fmt: skip
    if plan.kind == "space_heights":
        tall = sorted((s for s in infos if s.height_m is not None), key=lambda s: -(s.height_m or 0.0))
        if "lowest" in text.casefold():
            tall.reverse()
        lines = ["Spaces by height:"] + [f"- {s.name} ({s.long_name}): {_fmt(s.height_m or 0.0)} m" for s in tall[:10]]
        return "\n".join(lines), ids
    total = sum(s.net_floor_area_m2 or 0.0 for s in with_area)
    where = storey.name if storey else "all levels"
    lines = [f"{where}: {len(infos)} spaces, total area {_fmt(total)} m²"]
    lines += [f"- {s.name} ({s.long_name}): {_fmt(s.net_floor_area_m2 or 0.0)} m²" for s in sorted(
        with_area, key=lambda s: -(s.net_floor_area_m2 or 0.0))]  # fmt: skip
    return "\n".join(lines), ids


# The kinds whose dev agreement with the public keys is above one half (toolbench/ifc.py measures it).
# A text of another kind is returned as an abstention with the text as the best estimate.
ANSWER_KINDS: frozenset[TextKind] = frozenset({"metadata"})


def answer_text(model: im.IfcModel, text: str) -> AnswerRecord:
    plan = plan_text(text)
    if plan is None:
        return abstain(MissingReason.UNSUPPORTED, "no report fits this free-text question", "ask about counts, "
                       "types, materials, spaces, levels or the software of the model", tool="ifc_text.plan")  # fmt: skip
    if not side_known(model, plan, text):
        return abstain(MissingReason.NOT_IN_MODEL, f"the model does not state which {plan.label}s are external",
                       "a model with Pset IsExternal", tool="ifc_text.side")  # fmt: skip
    body, ids = _report(model, plan, text)
    step = Step(tool=f"ifc_text.{plan.kind}", method="deterministic", summary=f"{plan.kind} {plan.label} {plan.side}")
    evidence = _ids(ids, plan.label or plan.kind)
    if plan.kind not in ANSWER_KINDS:
        return AnswerRecord(
            status="abstained", best_estimate=body, confidence=0.3, evidence=evidence, steps=(step,),
            abstain=Abstain(reason=MissingReason.UNSUPPORTED, detail=f"a {plan.kind} report is not reliable enough "
                            "on the public keys to give as the answer", request="read the report as an estimate"),
        )  # fmt: skip
    return AnswerRecord(status="answered", value=body, confidence=0.6, evidence=evidence, steps=(step,))
