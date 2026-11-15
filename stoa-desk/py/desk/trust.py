"""How sure each fact is, its error margin, and the facts that do not add up.

Each rate is a measured share from `stoa/docs/RESULTS.md` (tool benchmarks and the sheet runs).
A fact with no measured rate gets no confidence: the desk says so.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from desk.facts import DocumentFacts

Json = dict[str, Any]

SWISS_ROOMS = "all 22,966 rooms on 833 test floors were found with the right name and number"
SWISS_AREA = "22,966 test rooms against the CAD source: the largest area error was 0.05%"
SWISS_COUNT = "the count was exact on all 833 test floors"
SWISS_SCALE = "the scale text and the scale bar agreed on 833 of 833 test floors"
RASTER_TEXT = "text reading was right for 89 of 100 room labels on 210 test sheets"
RASTER_AREA = "5,577 test rooms: 81 of 100 areas were within 2%, 89 of 100 within 5%"
RASTER_SCALE = "the scale was found on 210 of 210 test sheets, with an error under 1%"
SHEET_DOORS = "the door count was within 3% on 31 of 60 test sheets, so it is an estimate"
WARNED = "lowered by the desk because the fact has a warning; this rate is a rule, not a measurement"

# Relative error margin of a measured length or area, per kind of document, with the share of test items inside it.
MARGINS: dict[str, tuple[float, str]] = {
    "plan_pdf": (0.0005, "the largest error on 22,966 test rooms"),
    "raster": (0.05, "89 of 100 test rooms were inside this margin, 81 of 100 inside 2%"),
}
MEASURED_UNITS = {"m²", "m2", "m", "ft2", "ft", "sqft"}
AREA_TOLERANCE = 0.03
AREA_FLOOR = 0.5

SWISS: dict[str, tuple[float, str]] = {
    "Name": (0.999, SWISS_ROOMS),
    "Number": (0.999, SWISS_ROOMS),
    "Area": (0.999, SWISS_AREA),
    "Printed area": (0.999, SWISS_ROOMS),
    "Apartment": (0.999, SWISS_COUNT),
    "Outdoor": (0.999, SWISS_ROOMS),
    "Living area": (0.999, SWISS_AREA),
    "Rooms": (0.999, SWISS_ROOMS),
    "Rooms with a measured area": (0.999, SWISS_ROOMS),
    "Apartments": (0.999, SWISS_COUNT),
    "Door openings": (0.999, SWISS_COUNT),
    "Kind": (0.999, SWISS_COUNT),
    "Scale": (0.999, SWISS_SCALE),
    "Metres per point": (0.999, SWISS_SCALE),
    "Windows": (0.999, "the window count was exact on 99.9% of the test floors"),
}
SHEET: dict[str, tuple[float | None, str]] = {
    "Text": (None, RASTER_TEXT),
    "Room names": (0.894, RASTER_TEXT),
    "Text labels": (0.894, RASTER_TEXT),
    "Area": (None, RASTER_AREA),
    "Wall length": (None, RASTER_AREA),
    "Rooms with an outline": (0.812, RASTER_AREA),
    "Door leaves": (0.52, SHEET_DOORS),
    "Doors": (0.52, SHEET_DOORS),
    "Leaf width": (None, SHEET_DOORS),
    "Pixels per metre": (None, RASTER_SCALE),
    "Scale, px per m": (0.97, RASTER_SCALE),
}


def family(kind: str) -> str:
    return "raster" if kind.startswith("raster") else kind


def _number(value: object) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _digits(value: float) -> str:
    return f"{value:.2f}" if value < 10 else f"{value:.1f}"


def margin(kind: str, value: object, unit: str | None) -> Json | None:
    """The error margin of a measured value: plus or minus, in its unit, and what the margin is measured on."""
    number = _number(value)
    rule = MARGINS.get(family(kind))
    if number is None or rule is None or unit not in MEASURED_UNITS:
        return None
    share, basis = rule
    return {"plus": round(number * share, 3), "percent": round(share * 100, 2), "basis": basis,
            "text": f"± {_digits(max(number * share, 0.01))}"}  # fmt: skip


def _rate_fact(kind: str, fact: Json, table: dict[str, Any], *, summary: bool) -> None:
    if fact["status"] == "unknown" or fact["value"] is None:
        fact["confidence"] = 0.0
        fact["basis"] = "the drawing does not give this value"
        return
    key = fact["key"]
    rule = table.get(key) or (table.get("Kind") if summary and kind == "plan_pdf" else None)
    if rule is not None:
        rate, basis = rule
        if fact.get("confidence") is None and rate is not None:
            fact["confidence"] = rate
        fact.setdefault("basis", basis)
    if fact["status"] == "estimated" and kind == "plan_pdf":
        fact["confidence"] = min(fact.get("confidence", 1.0), 0.8)
        fact["basis"] = WARNED
    found = margin(kind, fact["value"], fact["unit"])
    if found is not None and key != "Printed area" and "margin" not in fact:
        fact["margin"] = f"{found['text']} {fact['unit']}"
        fact["marginBasis"] = found["basis"]


def _area_conflicts(entity: Json) -> list[Json]:
    by_key = {f["key"]: f for f in entity["facts"]}
    measured, printed = by_key.get("Area"), by_key.get("Printed area")
    if measured is None or printed is None:
        return []
    a, b = _number(measured["value"]), _number(printed["value"])
    if a is None or b is None or abs(a - b) <= max(AREA_FLOOR, AREA_TOLERANCE * b):
        return []
    text = (f"{entity['label']}: the outline measures {a:g} m², and the text on the drawing says {b:g} m². "
            f"The difference is {abs(a - b):.1f} m².")  # fmt: skip
    for fact in (measured, printed):
        fact["status"] = "estimated"
        fact["confidence"] = min(fact.get("confidence", 1.0), 0.5)
        fact["basis"] = "lowered: the measured area and the printed area do not agree"
    return [{"id": f"area:{entity['id']}", "entityIds": [entity["id"]], "text": text}]


def _sum_conflicts(entities: list[Json]) -> list[Json]:
    by_id = {e["id"]: e for e in entities}
    out: list[Json] = []
    for entity in entities:
        total = next((f for f in entity["facts"] if f["key"] == "Printed living area"), None)
        if total is None:
            continue
        parts = [_number(f["value"]) for m in entity.get("members", []) for f in by_id.get(m, {}).get("facts", [])
                 if f["key"] == "Area"]  # fmt: skip
        whole = _number(total["value"])
        if whole is None or not parts or None in parts:
            continue
        summed = sum(p for p in parts if p is not None)
        if abs(summed - whole) > max(AREA_FLOOR, AREA_TOLERANCE * whole):
            out.append({"id": f"sum:{entity['id']}", "entityIds": [entity["id"], *entity.get("members", [])],
                        "text": f"{entity['label']}: its rooms add up to {summed:g} m², and the drawing says {whole:g} m²."})  # fmt: skip
    return out


def _scale_conflicts(facts: DocumentFacts) -> list[Json]:
    scale = facts.scale
    if scale is not None and scale.get("agrees") is False:
        return [{"id": "scale", "entityIds": ["scale"],
                 "text": f"The title block says 1:{scale['ratio']}, and the scale bar gives another scale. "
                         "Each measured length and area depends on it."}]  # fmt: skip
    return []


def rate(kind: str, facts: DocumentFacts) -> None:
    """Give each fact its confidence, basis and margin, and list the facts that do not add up."""
    table: dict[str, Any] = SWISS if kind == "plan_pdf" else SHEET if kind.startswith("raster") else {}
    for fact in facts.summary:
        _rate_fact(kind, fact, table, summary=True)
    conflicts = [*facts.conflicts, *_scale_conflicts(facts)]
    seen = {tuple(sorted(c["entityIds"])) for c in conflicts}
    for entity in facts.entities:
        for fact in entity["facts"]:
            _rate_fact(kind, fact, table, summary=False)
        conflicts.extend(c for c in _area_conflicts(entity) if tuple(sorted(c["entityIds"])) not in seen)
    conflicts.extend(_sum_conflicts(facts.entities))
    facts.conflicts = conflicts
    if conflicts and kind == "plan_pdf" and any(c["id"] == "scale" for c in conflicts):
        for fact in facts.summary:
            if fact["key"] == "Scale":
                fact["confidence"] = 0.5
                fact["basis"] = "lowered: the scale text and the scale bar do not agree"


def agreement(facts: DocumentFacts | None, used: list[str]) -> tuple[str, str, float] | None:
    """The check of an answer against the facts that do not add up: (state, detail, factor)."""
    if facts is None or not facts.entities:
        return None
    conflicts = facts.conflicts
    hit = [c for c in conflicts if c["id"] == "scale" or set(c["entityIds"]) & set(used)]
    if hit:
        return "fail", " ".join(c["text"] for c in hit[:3]), 0.5
    if conflicts:
        return ("warn", f"{len(conflicts)} place(s) on this drawing have facts that do not add up; "
                        "this answer uses none of them", 0.97)  # fmt: skip
    return "pass", "the facts that this answer uses agree with each other", 1.0


COUNTED: dict[str, tuple[str, ...]] = {
    "door": ("Door openings", "Doors", "Door leaves"),
    "window": ("Windows",),
    "apartment": ("Apartments",),
    "toilet": ("Toilets",),
    "kitchen": ("Kitchens",),
    "bathtub": ("Bathtubs",),
    "washbasin": ("Washbasins",),
}


def same_as_facts(facts: DocumentFacts | None, question: str, value: object) -> tuple[str, str, float] | None:
    """A count in the answer against the same count in the facts of the drawing: (state, detail, factor)."""
    number = _number(value)
    text = question.lower()
    words = [w for w in COUNTED if w in text]
    if facts is None or number is None or len(words) != 1 or not text.lstrip().startswith("how many"):
        return None
    by_key = {f["key"]: f for f in facts.summary}
    fact = next((by_key[k] for k in COUNTED[words[0]] if k in by_key and _number(by_key[k]["value"]) is not None), None)
    if fact is None:
        return None
    known = _number(fact["value"])
    if known == number:
        return "pass", f"the facts of this drawing give the same count ({fact['key']}: {fact['value']})", 1.0
    return ("warn", f"the answer says {number:g}, and the facts of this drawing say {known:g} ({fact['key']}). "
                    "The two count in different ways, such as each drawn symbol against each distinct opening. "
                    "Check which count the question means.", 0.8)  # fmt: skip
