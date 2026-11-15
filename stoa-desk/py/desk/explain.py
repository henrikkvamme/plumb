"""Turn a recorded run into what the desk shows: steps, the derivation of the answer and its confidence.

The confidence is not the number that the model claims. It comes from the evidence: the measured track record
of this kind of answer, the scale witnesses, the method of each tool, the warnings of the facts that were used
and what the provenance check did.
"""

from __future__ import annotations

import json
import math
import re
from typing import TYPE_CHECKING, Any

from bp.agent.calc import CalcError, evaluate
from desk import trust

if TYPE_CHECKING:
    from bp.agent.core import ToolSpec
    from bp.contract import AnswerRecord, Evidence
    from desk.facts import DocumentFacts

Json = dict[str, Any]

# Share of answered questions that were right, on held-out documents. Source: stoa/docs/RESULTS.md.
TRACK_RECORD: dict[str, tuple[float, int, str]] = {
    "plan_pdf": (0.998, 420, "vector floor plans, 25 held-out sheets"),
    "ifc": (0.986, 308, "IFC models, 25 held-out documents"),
    "bim_sheet": (0.986, 308, "IFC models and their sheets, 25 held-out documents"),
    "raster_counts": (0.879, 737, "raster floor plans, 80 held-out plans"),
}
TITLES = {
    "list_rooms": "Read every room",
    "list_apartments": "Read every apartment",
    "count_symbols": "Count symbols",
    "calc": "Calculate",
    "submit_answer": "Check the answer against its sources",
    "abstain": "Decline to answer",
    "find_text": "Find text",
    "read_region": "Read a region",
    "read_scales": "Read the printed scales",
    "measure_scale": "Measure the scale",
    "zone_areas": "Measure colour zones",
    "room_area": "Measure a room",
    "count_door_swings": "Count door swings",
    "list_tags": "List tags",
    "length_to_m": "Convert a length",
    "list_spaces": "Read the spaces of the model",
    "count_elements": "Count model elements",
    "sum_quantity": "Sum a quantity",
    "project_info": "Read the project data",
    "list_room_regions": "Read every room region",
    "find_room": "Find a room",
    "count_on_plan": "Count on the plan",
}
# One plain sentence per tool, for a person who does not know the tools. `{n}` is the number of rows found.
PLAIN: dict[str, tuple[str, str]] = {
    "list_rooms": ("Read every room on the drawing", "found {n} rooms"),
    "list_rooms_by_kind": ("Sorted the rooms by what they are used for", "{n} kinds"),
    "list_apartments": ("Grouped the rooms into apartments", "found {n} apartments"),
    "count_symbols": ("Counted the symbols on the drawing", ""),
    "find_text": ("Looked for text on the drawing", "found {n} places"),
    "read_region": ("Read the text in one part of the drawing", ""),
    "read_scales": ("Read the scales printed on the drawing", "found {n}"),
    "measure_scale": ("Measured the scale from a known length", ""),
    "zone_areas": ("Measured the coloured zones", "found {n} zones"),
    "room_area": ("Measured the floor area of a room", ""),
    "room_perimeter": ("Measured the outline of a room", ""),
    "count_door_swings": ("Counted the door swings on the drawing", ""),
    "list_tags": ("Read the tags on the drawing", "found {n} tags"),
    "length_to_m": ("Converted a length to metres", ""),
    "list_spaces": ("Read every room of the building model", "found {n} rooms"),
    "count_elements": ("Counted parts of the building model", ""),
    "sum_quantity": ("Added up a quantity of the building model", ""),
    "project_info": ("Read the project data of the building model", ""),
    "list_room_regions": ("Read every room on the sheet", "found {n} rooms"),
    "find_room": ("Looked for a room on the sheet", ""),
    "count_on_plan": ("Counted on the plan", ""),
}
SUBJECT_KEYS = ("kind", "query", "text", "room", "label", "name", "element", "quantity", "what", "tag")
COUNT_KEYS = ("count", "total", "n", "value", "area_m2", "length_m", "metres", "height_m")


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}".rstrip("0").rstrip(".")


def _subject(arguments: Json) -> str:
    for key in SUBJECT_KEYS:
        value = arguments.get(key)
        if isinstance(value, str) and 0 < len(value) <= 40:
            return value.replace("_", " ")
    return ""


def _found(result: object, template: str) -> str:
    if not isinstance(result, dict):
        return ""
    for key in COUNT_KEYS:
        value = result.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            unit = {"area_m2": " m²", "length_m": " m", "metres": " m", "height_m": " m"}.get(key, "")
            return f"{_number(value)}{unit}"
    rows = next((v for v in result.values() if isinstance(v, list)), None)
    if rows is not None and template:
        return template.format(n=len(rows))
    return ""


def _calc_sentence(arguments: Json, result: object) -> str:
    expression = str(arguments.get("expression", ""))
    numbers = re.findall(r"\d+(?:\.\d+)?", expression)
    value = result.get("rounded_2", result.get("result")) if isinstance(result, dict) else None
    total = f": {_number(value)}" if isinstance(value, (int, float)) else ""
    if len(numbers) > 1 and set(re.sub(r"[\d.\s()]", "", expression)) <= {"+"}:
        return f"Added {len(numbers)} numbers{total}"
    return f"Calculated {expression[:80]}{total.replace(': ', ' = ')}"


def sentence(name: str, kind: str, arguments: Json, result: object, state: str) -> str:
    """What a step did, in words for a person who does not know the tools."""
    if state == "error":
        return "This step did not work. The agent tried another way"
    if kind == "calc":
        return _calc_sentence(arguments, result)
    if name == "abstain":
        return "Decided not to answer: the drawing does not give this"
    if kind == "final":
        if state == "refused":
            return "Stopped an answer that had a number with no source on the drawing"
        if state == "waited":
            return "Looked at the results once more before the answer"
        return "Checked that each number in the answer comes from the drawing"
    lead, template = PLAIN.get(name, (TITLES.get(name, name.replace("_", " ").capitalize()), ""))
    subject = _subject(arguments)
    found = _found(result, template)
    return f"{lead}{f' ({subject})' if subject else ''}{f': {found}' if found else ''}"


LABEL_KEYS = ("label", "name", "long_name", "room", "text", "tag", "legend_text", "kind", "colour")
ID_KEYS = ("number", "letter", "region", "tag")
MAX_MARKS = 200
MAX_ENTITIES = 400
MAX_DATA = 200_000


def _mark(evidence: Evidence, index: int, step_id: str) -> Json:
    points = [[float(x), float(y)] for x, y in evidence.points]
    kind = evidence.kind
    if len(points) == 1:
        geometry = "point"
    elif len(points) == 2:
        geometry = "line" if kind == "scale" else "box"
    else:
        geometry = "polygon"
    return {"id": f"{step_id}:e{index}", "kind": kind, "geometry": geometry, "page": evidence.page, "points": points,
            "ref": evidence.ref, "note": evidence.note}  # fmt: skip


def _rows(data: object) -> list[Json]:
    """Every object in a JSON value, outer first."""
    out: list[Json] = []
    if isinstance(data, dict):
        out.append(data)
        for value in data.values():
            out.extend(_rows(value))
    elif isinstance(data, list):
        for value in data:
            out.extend(_rows(value))
    return out


def _paths(data: object, path: str = "") -> list[tuple[str, Json]]:
    """Every object in a JSON value with its path, such as `rooms[3]`."""
    out: list[tuple[str, Json]] = []
    if isinstance(data, dict):
        out.append((path, data))
        for key, value in data.items():
            out.extend(_paths(value, f"{path}.{key}" if path else str(key)))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            out.extend(_paths(value, f"{path}[{index}]"))
    return out


def _row_links(data: object, facts: DocumentFacts | None) -> list[Json]:
    if facts is None:
        return []
    out = []
    for path, row in _paths(data):
        entities = facts.link(row)
        if entities and path:
            out.append({"path": path, "entityIds": entities[:MAX_ENTITIES]})
    return out[:MAX_ENTITIES]


def _linked(data: object, facts: DocumentFacts | None) -> list[str]:
    if facts is None:
        return []
    seen: dict[str, None] = {}
    for row in _rows(data):
        for entity in facts.link(row):
            seen.setdefault(entity)
    return list(seen)[:MAX_ENTITIES]


def build_steps(raw: list[Json], tools: dict[str, ToolSpec], facts: DocumentFacts | None) -> list[Json]:
    steps: list[Json] = []
    for index, item in enumerate(raw):
        step_id = f"s{index + 1}"
        name = item["tool"]
        run = item["run"]
        result = item["result"]
        error = ""
        if run is not None and run.error:
            error = run.error
        elif isinstance(result, dict) and isinstance(result.get("error"), str):
            error = result["error"]
        if name == "calc":
            kind, method = "calc", "deterministic"
        elif name in {"submit_answer", "abstain"}:
            kind, method = "final", "deterministic"
        else:
            kind, method = "tool", tools[name].method if name in tools else "deterministic"
        refused = kind == "final" and isinstance(result, str) and result.startswith("REFUSED")
        waited = kind == "final" and isinstance(result, str) and not refused
        evidence = run.output.evidence[:MAX_MARKS] if run is not None and run.output is not None else ()
        steps.append({
            "id": step_id,
            "kind": kind,
            "tool": name,
            "title": TITLES.get(name, name.replace("_", " ").capitalize()),
            "sentence": sentence(name, kind, item["arguments"] if isinstance(item["arguments"], dict) else {}, result,
                                 "error" if error else "refused" if refused else "waited" if waited else "ok"),
            "method": method,
            "thought": item["thought"][:600],
            "argumentsJson": json.dumps(item["arguments"], ensure_ascii=False)[:4000],
            "done": bool(item["done"]),
            "ok": not error and not refused,
            "error": error or (str(result) if refused else ""),
            "skipped": waited,
            "data": None if kind == "final" else result,
            "dataJson": "" if kind == "final" or result is None else json.dumps(result, ensure_ascii=False)[:MAX_DATA],
            "marks": [_mark(e, i, step_id) for i, e in enumerate(evidence)],
            "entityIds": [] if error else _linked(result, facts),
            "rowLinks": [] if error else _row_links(result, facts),
            "ms": round(run.ms, 1) if run is not None else None,
        })  # fmt: skip
    return steps


# ----------------------------------------------------------------------------- where a number comes from


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def _find(data: object, value: float, path: str = "") -> list[tuple[str, Json | None, str]]:
    """Each place where `value` stands in a JSON value: (path, the object that holds it, the key)."""
    out: list[tuple[str, Json | None, str]] = []
    if isinstance(data, dict):
        for key, item in data.items():
            here = f"{path}.{key}" if path else str(key)
            if isinstance(item, (int, float)) and not isinstance(item, bool) and _close(float(item), value):
                out.append((here, data, str(key)))
            else:
                out.extend(_find(item, value, here))
    elif isinstance(data, list):
        for index, item in enumerate(data):
            here = f"{path}[{index}]"
            if isinstance(item, (int, float)) and not isinstance(item, bool) and _close(float(item), value):
                out.append((here, None, ""))
            else:
                out.extend(_find(item, value, here))
    return out


def _row_label(row: Json | None) -> str:
    if row is None:
        return ""
    name = next((str(row[k]) for k in LABEL_KEYS if isinstance(row.get(k), str) and row.get(k)), "")
    ident = next((str(row[k]) for k in ID_KEYS if isinstance(row.get(k), (str, int)) and row.get(k) != ""), "")
    return " ".join(part for part in (name, ident) if part)


def _source(  # noqa: PLR0913 - one lookup with its filters
    value: float, steps: list[Json], before: int, facts: DocumentFacts | None, hint: str = "",
    taken: set[tuple[str, str]] | None = None,
) -> Json:  # fmt: skip
    """The latest step before `before` that returned `value`. A calc step gives its own operands."""
    for step in reversed(steps[:before]):
        if not step["ok"] or step["data"] is None:
            continue
        hits = _find(step["data"], value)
        if not hits:
            continue
        if step["kind"] == "calc":
            return _calc(step, steps, facts)
        wanted = [h for h in hits if hint and hint in h[0]] or hits
        if taken is not None:
            wanted = [h for h in wanted if (step["id"], h[0]) not in taken] or wanted
            taken.add((step["id"], wanted[0][0]))
        path, row, key = wanted[0]
        entities = facts.link(row) if facts is not None and row is not None else []
        if not entities and "[" not in path:
            # A field of the whole result, such as a count: every entity of the step is its source.
            entities = step["entityIds"]
        return {
            "value": value, "stepId": step["id"], "tool": step["tool"], "path": path, "key": key,
            "label": _row_label(row) or key.replace("_", " "), "entityIds": entities,
            "warnings": [str(w) for w in (row or {}).get("warnings", []) or []] if isinstance(row, dict) else [],
            "places": len(hits), "operands": [],
        }  # fmt: skip
    return {"value": value, "stepId": None, "tool": "", "path": "", "key": "", "label": "no tool result holds this number",
            "entityIds": [], "warnings": [], "places": 0, "operands": []}  # fmt: skip


def _calc(step: Json, steps: list[Json], facts: DocumentFacts | None) -> Json:
    expression = str(json.loads(step["argumentsJson"]).get("expression", ""))
    try:
        value, literals = evaluate(expression)
    except CalcError:
        value, literals = float("nan"), []
    index = steps.index(step)
    taken: set[tuple[str, str]] = set()
    operands = [_source(float(n), steps, index, facts, taken=taken) | {"operands": []} for n in literals]
    return {
        "value": value, "stepId": step["id"], "tool": "calc", "path": "", "key": "", "label": expression,
        "entityIds": [e for op in operands for e in op["entityIds"]], "warnings": [w for op in operands for w in op["warnings"]],
        "places": 1, "operands": operands,
    }  # fmt: skip


def derivation(record: AnswerRecord, steps: list[Json], facts: DocumentFacts | None) -> Json | None:
    """Where the answer comes from. For an abstention: where its best estimate comes from, or None."""
    estimate = record.status == "abstained"
    value = record.best_estimate if estimate else record.value
    if record.status not in {"answered", "abstained"} or value is None:
        return None
    if isinstance(value, str):
        numbers = re.fullmatch(r"-?\d+(?:\.\d+)?", value.strip())
        if not numbers:
            for step in reversed(steps):
                if step["ok"] and step["kind"] == "tool" and value.lower() in str(step["data"]).lower():
                    rows = [r for r in _rows(step["data"]) if value in {str(v) for v in r.values()}]
                    row = rows[0] if rows else None
                    return {"value": value, "stepId": step["id"], "tool": step["tool"], "path": "", "key": "",
                            "label": _row_label(row), "warnings": [], "places": 1, "operands": [],
                            "entityIds": facts.link(row) if facts is not None and row is not None else []}  # fmt: skip
            return None
        value = float(value)
    source = _source(float(value), steps, len(steps), facts)
    return None if estimate and source["stepId"] is None else source


def _second_route(source: Json, steps: list[Json]) -> Json | None:
    """A tool step that returned the value of the answer and is not on the path that produced it."""
    value = source["value"]
    if not isinstance(value, (int, float)) or source["stepId"] is None:
        return None
    on_path = {source["stepId"]} | ({op["stepId"] for op in source["operands"]} if source["tool"] == "calc" else set())
    for step in steps:
        if step["kind"] != "tool" or not step["ok"] or step["id"] in on_path or step["data"] is None:
            continue
        if _find(step["data"], float(value)) or _find(step["data"], round(float(value), 2)):
            return step
    return None


# ----------------------------------------------------------------------------- confidence


def at_least(rate: float, items: int) -> float:
    """The Wilson 95% lower bound of a measured share: what the test proves, not the share it happened to show."""
    z = 1.96
    centre = rate + z * z / (2 * items)
    spread = z * math.sqrt(rate * (1 - rate) / items + z * z / (4 * items * items))
    return (centre - spread) / (1 + z * z / items)


def _check(ident: str, label: str, state: str, detail: str, factor: float = 1.0, step: str | None = None) -> Json:
    return {"id": ident, "label": label, "state": state, "detail": detail, "factor": factor, "stepId": step}


def _claim(steps: list[Json], record: AnswerRecord) -> float | None:
    """The confidence that the model wrote in its answer call. The desk shows it and does not use it."""
    for step in reversed(steps):
        if step["kind"] == "final" and not step["skipped"]:
            try:
                claim = json.loads(step["argumentsJson"] or "{}").get("confidence")
            except ValueError:
                claim = None
            if isinstance(claim, int | float):
                return float(claim)
    return record.confidence


def confidence(  # noqa: C901, PLR0912, PLR0915 - one rule per check, in the order that the desk shows them
    record: AnswerRecord, steps: list[Json], kind: str, facts: DocumentFacts | None, source: Json | None, rejections: int,
    question: str = "",
) -> Json:  # fmt: skip
    checks: list[Json] = []
    used = [s for s in steps if s["kind"] == "tool" and s["ok"]]
    if record.status != "answered":
        return {"score": None, "level": "none", "basis": "", "checks": [], "modelClaim": None}

    if source is None or source["stepId"] is None:
        checks.append(_check("provenance", "Source of the value", "fail",
                             "no reading of the drawing holds this value, so it can be wrong; read the note under the answer", 0.4))  # fmt: skip
    elif rejections:
        checks.append(_check("provenance", "Source of the value", "warn",
                             f"the value is read from the drawing, after {rejections} stopped attempt(s) with a value that had no source",
                             0.9, source["stepId"]))  # fmt: skip
    else:
        how = "calculated from numbers read on the drawing" if source["tool"] == "calc" else "read from the drawing"
        checks.append(_check("provenance", "Source of the value", "pass", f"the value is {how}; the AI model wrote no number itself", 1.0, source["stepId"]))

    models = [s["tool"] for s in used if s["method"] == "model"]
    if models:
        checks.append(_check("method", "Method", "warn", "a trained recognition model gave a fact; it has an error rate", 1.0))
    elif used:
        checks.append(_check("method", "Method", "pass", "every fact is measured from the drawing with fixed rules; a second run gives the same result"))

    measured = record.unit in {"m2", "m", "m3", "ft2", "ft", "sqft"}
    if measured and facts is not None and kind == "plan_pdf":
        scale = facts.scale
        if scale is None:
            checks.append(_check("scale", "Scale", "fail", "no scale was found, so a measured value has no base", 0.3))
        elif scale["agrees"]:
            checks.append(_check("scale", "Scale", "pass", f"1:{scale['ratio']} in the title block, and the scale bar agrees: 2 witnesses"))
        elif scale["agrees"] is None:
            checks.append(_check("scale", "Scale", "warn", f"1:{scale['ratio']} in the title block only: 1 witness, no scale bar to check it", 0.9))
        else:
            checks.append(_check("scale", "Scale", "fail", f"the title block says 1:{scale['ratio']} and the scale bar disagrees", 0.5))

    warnings = list(dict.fromkeys(source["warnings"])) if source else []
    if warnings:
        checks.append(_check("warnings", "Warnings", "warn", "; ".join(warnings)[:300], 0.7))
    elif source is not None and source["stepId"] is not None:
        checks.append(_check("warnings", "Warnings", "pass", "no warning on the facts that the answer uses"))

    agree = trust.agreement(facts, list(source["entityIds"]) if source else [])
    if agree is not None:
        checks.append(_check("agree", "Facts add up", agree[0], agree[1], agree[2]))

    same = trust.same_as_facts(facts, question, record.value)
    if same is not None:
        checks.append(_check("facts", "Same as the facts", same[0], same[1], same[2]))

    second = _second_route(source, steps) if source is not None else None
    if second is not None:
        checks.append(_check("cross", "Second reading", "pass", "a second, independent reading gives the same value", 1.0, second["id"]))

    measured_by_tools = [_check(c.id, c.label, c.state, c.detail, c.factor) for c in getattr(record, "checks", ())]
    checks.extend(measured_by_tools)

    record_of = TRACK_RECORD.get(kind)
    if measured_by_tools:
        base = 1.0
        record_of = None
    elif record_of is not None:
        rate, items, what = record_of
        floor = at_least(rate, items)
        checks.append(_check("track", "Track record", "pass" if floor >= 0.95 else "warn",
                             f"at least {floor:.1%} right: {rate:.1%} of the answers were right on {items} test questions "
                             f"({what}); the score uses the 95% lower bound for a test of this size", floor))  # fmt: skip
        base = floor
    else:
        checks.append(_check("track", "Track record", "warn", "this kind of document has no measured track record yet", 0.7))
        base = 1.0
    score = base
    for check in checks:
        if check["id"] != "track" or record_of is None:
            score *= check["factor"]
    if measured_by_tools and record.confidence > 0:
        score = min(score, record.confidence)
    score = round(min(score, 0.999), 3)
    failed = [c for c in checks if c["state"] == "fail"]
    level = "low" if failed or score < 0.7 else "medium" if score < 0.9 else "high"
    return {"score": score, "level": level, "checks": checks, "modelClaim": _claim(steps, record),
            "basis": "track record of this kind of answer, lowered for each check that does not pass"}  # fmt: skip
