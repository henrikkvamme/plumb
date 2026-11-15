"""The agent loop as a state machine, with a provenance rule.

The provenance rule is the reason that the agent can be trusted on a question that nobody has seen before:
every number that it submits must be a number that a tool returned, or the result of a calculator call whose
literal numbers all come from a tool or from the question. A number that the model invents cannot pass.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal

from bp import conflicts
from bp.agent.calc import FREE_LITERALS, CalcError, evaluate
from bp.contract import Abstain, AnswerRecord, Check, Evidence, Frozen, MissingReason, Step, confidence_of
from bp.llm import ChatResult, ToolCall
from bp.machine import Machine, Run
from bp.scoring import normalise_text, numbers

if TYPE_CHECKING:
    from bp.contract import Conflict
    from bp.facts import DocumentFacts


class State(StrEnum):
    START = "start"
    THINKING = "thinking"
    TOOL = "tool"
    CHECK = "check"
    DONE = "done"


class Event(StrEnum):
    BEGIN = "begin"
    CALL = "call"
    OBSERVE = "observe"
    SUBMIT = "submit"
    ACCEPT = "accept"
    REJECT = "reject"
    ABSTAIN = "abstain"
    EXHAUST = "exhaust"


AGENT: Machine[State, Event] = Machine(
    name="agent",
    initial=State.START,
    finals=frozenset({State.DONE}),
    table={
        (State.START, Event.BEGIN): State.THINKING,
        (State.THINKING, Event.CALL): State.TOOL,
        (State.TOOL, Event.OBSERVE): State.THINKING,
        (State.THINKING, Event.SUBMIT): State.CHECK,
        (State.CHECK, Event.ACCEPT): State.DONE,
        (State.CHECK, Event.REJECT): State.THINKING,
        (State.CHECK, Event.EXHAUST): State.DONE,
        (State.THINKING, Event.ABSTAIN): State.DONE,
        (State.THINKING, Event.EXHAUST): State.DONE,
    },
)
AGENT.verify()


class ToolOutput(Frozen):
    ok: bool = True
    data: Any = None  # JSON that the model reads
    evidence: tuple[Evidence, ...] = ()
    cost_usd: float = 0.0
    error: str = ""
    # How sure the tool is of this result, from its evidence (scale witnesses, error band). None: no statement.
    confidence: float | None = None
    checks: tuple[Check, ...] = ()  # the reasons; with checks and no confidence, the confidence is their product


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema of the arguments
    run: Callable[[dict[str, Any]], ToolOutput]
    method: Literal["deterministic", "model"] = "deterministic"

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }


def _object(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


RESULT_CHARS = 6000  # of a tool result in a step: enough for a person to check it

CALC_SCHEMA = {
    "type": "function",
    "function": {
        "name": "calc",
        "description": (
            "Evaluate arithmetic. Use it for EVERY sum, count of a list, difference, ratio, percentage or unit "
            "conversion. Operators + - * / **, functions sum, count, min, max, mean, abs, sqrt, ceil, floor, "
            "round(x, n), lists [a, b], constants FT2_PER_M2, M2_PER_FT2, FT_PER_M, M_PER_FT, PI. Each number "
            "in the expression must be copied from a tool result or from the question."
        ),
        "parameters": _object({"expression": {"type": "string"}}, ["expression"]),
    },
}
SUBMIT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "submit_answer",
        "description": (
            "Give the final answer. A number must be exactly a number from a tool result or a calc result. "
            "A text answer must be text from a tool result."
        ),
        "parameters": _object(
            {
                "value": {
                    "type": ["number", "string"],
                    "description": "a number, or for a which-question the identifier as a string exactly as the tool "
                    "gave it: the room number or tag such as '3.04' or 'Flur (117)', the apartment letter. When the "
                    "question asks which item AND how large it is, the value is the measure with its unit, and the "
                    "item goes in `convention`",
                },
                "unit": {"type": ["string", "null"], "description": "m2, m, m3, ft2, %, count, or null for text"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "convention": {"type": "string", "description": "the counting or measuring rule you applied"},
            },
            ["value", "unit", "confidence", "convention"],
        ),
    },
}
ABSTAIN_SCHEMA = {
    "type": "function",
    "function": {
        "name": "abstain",
        "description": (
            "Use this when the document or the tools cannot give a reliable answer. A wrong answer costs more "
            "than no answer."
        ),
        "parameters": _object(
            {
                "reason": {"type": "string", "enum": [r.value for r in MissingReason]},
                "detail": {"type": "string"},
                "request": {"type": "string", "description": "what the user can supply to make an answer possible"},
                "best_estimate": {"type": ["number", "string", "null"]},
            },
            ["reason", "detail", "request"],
        ),
    },
}

SYSTEM = """You answer one question about one building document (a floor plan, a drawing sheet or a BIM model).
You cannot see the document. You have tools that read it. The tools are tested and you can trust what they return.

Rules:
1. Plan first: which facts do you need, and which tool gives each one.
2. Never write a number from memory or estimate it. Every number in your answer comes from a tool result, or from
   the calc tool with numbers that you copied from tool results or from the question.
3. Use calc for every sum, count, difference, percentage and unit conversion, also the simple ones.
4. Follow the convention that the question states. When the question states none, use the plain reading and say
   which one you used in `convention`.
5. When the tools cannot give the facts (no scale, the item is not on the document, the document is of another
   kind, the question is ambiguous), call abstain with the reason and with what the user can supply.
   A wrong answer costs more than no answer.
6. Finish with exactly one call of submit_answer or abstain."""


def _collect(value: Any, found_numbers: list[float], found_text: list[str]) -> None:  # noqa: ANN401 - JSON
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        if math.isfinite(value):
            found_numbers.append(float(value))
    elif isinstance(value, str):
        found_text.append(value)
        found_numbers.extend(numbers(value))
    elif isinstance(value, dict):
        for item in value.values():
            _collect(item, found_numbers, found_text)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect(item, found_numbers, found_text)


NAME_KEYS = frozenset({"number", "room", "room_number", "tag", "id", "entity_id", "label", "name", "apartment"})


def _split(value: Any, names: list[float], measures: list[float], *, named: bool) -> None:  # noqa: ANN401 - JSON
    """Sort the numbers of a tool result: under a name key (a room number, a tag, an id) or any other key."""
    if isinstance(value, dict):
        for key, item in value.items():
            _split(item, names, measures, named=key in NAME_KEYS)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _split(item, names, measures, named=named)
    else:
        found: list[float] = []
        _collect(value, found, [])
        (names if named else measures).extend(found)


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


@dataclass
class Ledger:
    """Every number and text that the tools produced in this question."""

    question_numbers: list[float]
    numbers: list[float] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    names: list[float] = field(default_factory=list)  # numbers that are a name: a room number, a tag, an id
    measures: list[float] = field(default_factory=list)  # every other number of the tool results

    def add(self, data: Any) -> None:  # noqa: ANN401 - JSON
        _collect(data, self.numbers, self.texts)
        _split(data, self.names, self.measures, named=False)

    def add_measure(self, value: float) -> None:
        """A calc result: a number that is a measure, never a name."""
        self.numbers.append(value)
        self.measures.append(value)

    def only_a_name(self, value: float) -> bool:
        """True when the tools gave this number only as a name, such as room number 2.30."""
        return any(_close(value, n) for n in self.names) and not any(_close(value, n) for n in self.measures)

    def known(self, value: float) -> bool:
        return any(_close(value, n) for n in self.numbers)

    def literal_ok(self, value: float) -> bool:
        magnitude = abs(value)
        return (
            magnitude in FREE_LITERALS
            or any(_close(magnitude, abs(n)) for n in self.numbers)
            or any(_close(magnitude, abs(n)) for n in self.question_numbers)
            or any(_close(magnitude, abs(n) / 100.0) for n in self.question_numbers)  # 10% written as 0.10
            or any(_close(magnitude, 1.0 + abs(n) / 100.0) for n in self.question_numbers)  # and as 1.10
        )

    def text_known(self, value: str) -> bool:
        wanted = normalise_text(value)
        return wanted != "" and any(wanted in normalise_text(text) for text in self.texts)


MEASURE_UNITS = frozenset({"m2", "m²", "m", "m3", "m³", "ft2", "ft²", "ft", "mm", "cm", "sqm", "sq m"})

Chat = Callable[[list[dict[str, Any]], list[dict[str, Any]]], ChatResult]


@dataclass
class AgentResult:
    record: AnswerRecord
    events: list[Event]
    rejections: int


def _abstain(reason: MissingReason, detail: str, request: str, estimate: float | str | None = None) -> AnswerRecord:
    return AnswerRecord(
        status="abstained",
        abstain=Abstain(reason=reason, detail=detail[:400], request=request[:400]),
        best_estimate=estimate,
    )


def _check(arguments: dict[str, Any], ledger: Ledger) -> tuple[AnswerRecord | None, str]:  # noqa: PLR0911 - one return per rule
    """Return the record when the submitted value passes the provenance rule, or the text of the refusal."""
    value, unit = arguments.get("value"), arguments.get("unit")
    confidence = arguments.get("confidence", 0.5)
    confidence = min(1.0, max(0.0, float(confidence))) if isinstance(confidence, (int, float)) else 0.5
    convention = str(arguments.get("convention", ""))[:300]
    as_text = isinstance(unit, str) and unit.strip().lower() in {"text", "string", "name", "id"}
    unit = unit if isinstance(unit, str) and unit not in {"", "count", "none", "null"} and not as_text else None
    if as_text and isinstance(value, (int, float)) and not isinstance(value, bool):
        value = str(int(value)) if float(value).is_integer() else str(value)  # an identifier such as room 302
        if ledger.text_known(value):
            return AnswerRecord(
                status="answered", value=value, unit=None, confidence=confidence, convention=convention
            ), ""
    if isinstance(value, bool) or value is None:
        return None, "submit_answer needs a value. Call abstain when you have none."
    if isinstance(value, (int, float)):
        if not ledger.known(float(value)):
            return None, (
                f"REFUSED: {value} is not a number from a tool result or a calc result. "
                "Get it from a tool, compute it with calc, or abstain."
            )
        if unit is not None and unit.strip().lower() in MEASURE_UNITS and ledger.only_a_name(float(value)):
            return None, (
                f"REFUSED: {value} is a room number or a tag in the tool results, not a measure in {unit}. When the "
                "question asks which item and how large, submit the measure as the value with its unit, and name "
                "the item in `convention`."
            )
        return AnswerRecord(status="answered", value=value, unit=unit, confidence=confidence, convention=convention), ""
    text = str(value)
    as_numbers = numbers(text)
    plain_number = len(as_numbers) == 1 and text.strip().replace(",", ".").lstrip("-").replace(".", "", 1).isdigit()
    if plain_number and (unit is not None or not ledger.text_known(text)):
        return _check({**arguments, "value": as_numbers[0]}, ledger)
    if not ledger.text_known(text):
        return None, f"REFUSED: the text {text[:80]!r} is not in any tool result. Use text from a tool, or abstain."
    return AnswerRecord(status="answered", value=text, unit=unit, confidence=confidence, convention=convention), ""


def _run_calc(arguments: dict[str, Any], ledger: Ledger) -> dict[str, Any]:
    expression = str(arguments.get("expression", ""))
    try:
        value, literals = evaluate(expression)
    except CalcError as exc:
        return {"error": str(exc)}
    unknown = [n for n in literals if not ledger.literal_ok(n)]
    if unknown:
        return {
            "error": f"REFUSED: these numbers are not from a tool result or the question: {unknown[:8]}. "
            "Copy numbers exactly as the tool gave them."
        }
    ledger.add_measure(value)
    rounded = round(value, 2)
    ledger.add_measure(rounded)
    return {"result": value, "rounded_2": rounded}


def _step(tool: str, method: str, arguments: dict[str, Any], output: ToolOutput, took_ms: float) -> Step:
    data = output.data if output.ok else {"error": output.error}
    failed = isinstance(data, dict) and "error" in data
    confidence = output.confidence
    if confidence is None and output.checks:
        confidence = confidence_of(output.checks)
    return Step(
        tool=tool,
        method="model" if method == "model" else "deterministic",
        summary=json.dumps(arguments)[:300],
        arguments=arguments,
        ok=output.ok and not failed,
        error=str(data["error"])[:600] if failed else "",
        checks=output.checks,
        result=json.dumps(data, default=str)[:RESULT_CHARS],
        evidence=output.evidence[:40],
        confidence=confidence if output.ok else None,
        latency_ms=round(took_ms, 1),
    )


# An answer that uses a fact in conflict is less sure. This factor is a rule: no benchmark measures how often an
# answer on a conflicting fact is wrong. It halves the confidence, like the old desk stand-in (desk/trust.py).
CONFLICT_FACTOR = 0.5
CONFLICT_NOTE = (
    "FACTS DO NOT ADD UP on this document: {texts} If your answer depends on a value in doubt, call abstain with the "
    "reason 'ambiguous', say which facts disagree, and give the value as best_estimate. A value that the drawing "
    "prints (a printed area, a printed scale) is not in doubt: use it when the question asks for it."
)
Row = tuple[dict[str, Any], list[str]]


def _rows(data: Any, known: set[str]) -> list[Row]:  # noqa: ANN401 - JSON
    """Every dict in a tool result that links to a fact entity, with the entity ids."""
    out: list[Row] = []
    if isinstance(data, dict):
        ids = conflicts.row_ids(data, known)
        if ids:
            out.append((data, ids))
        for item in data.values():
            out.extend(_rows(item, known))
    elif isinstance(data, (list, tuple)):
        for item in data:
            out.extend(_rows(item, known))
    return out


def _row_numbers(row: dict[str, Any]) -> list[float]:
    return [
        float(v) for v in row.values() if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    ]


def _row_texts(row: dict[str, Any]) -> list[str]:
    return [normalise_text(v) for v in row.values() if isinstance(v, str)]


def _note(hits: list[Conflict]) -> str:
    return CONFLICT_NOTE.format(texts=" ".join(c.text for c in hits[:4]))


@dataclass
class _Trail:
    """What the run read that links to the document facts: tool rows and calc expressions."""

    facts: DocumentFacts
    known: set[str]
    rows: list[Row] = field(default_factory=list)
    calcs: list[tuple[float, list[float], str]] = field(default_factory=list)  # (value, literals, expression)

    def used(self, value: float | str) -> list[Row]:
        """The rows that the answer value comes from: directly, or through the calc that made it."""
        if isinstance(value, str):
            wanted = normalise_text(value)
            return [r for r in self.rows if wanted and any(wanted == t for t in _row_texts(r[0]))]
        wanted = [float(value)]
        for result, literals, _ in self.calcs:
            if _close(result, value) or _close(round(result, 2), value):
                wanted.extend(literals)
                break
        return [r for r in self.rows if any(_close(n, w) for n in _row_numbers(r[0]) for w in wanted)]

    def margin(self, value: float) -> tuple[float, float, str] | None:
        """(margin, share, basis) of a numeric answer, from the margins of the facts it uses.

        Direct: a value that a fact gives (or its unit change). Through calc: a sum or a scaled sum of such values.
        A difference has no margin here: its error can be larger than its value.
        """
        direct = self._value_margin(value)
        if direct is not None:
            return direct
        for result, literals, expression in self.calcs:
            if not (_close(result, value) or _close(round(result, 2), value)) or "-" in expression:
                continue
            parts: list[tuple[float, float, float, str]] = []  # (literal, margin, share, basis)
            for literal in literals:
                found = self._value_margin(literal)
                if found is not None:
                    parts.append((literal, *found))
                elif any(_close(literal, n) for r in self.rows for n in _row_numbers(r[0])):
                    return None  # a tool value with no margin takes part: the margin is not known
            total = sum(abs(p[0]) for p in parts)
            if not parts or total == 0:
                return None
            relative = sum(p[1] for p in parts) / total  # margins added, as in bp.rates.sum_margin
            basis = parts[0][3] if len({p[3] for p in parts}) == 1 else "the margins of the facts it uses"
            return (
                round(relative * abs(value), 4),
                min(p[2] for p in parts),
                f"the margins of {len(parts)} values added: {basis}",
            )
        return None

    def _value_margin(self, value: float) -> tuple[float, float, str] | None:
        for row, ids in self.rows:
            if not any(_close(n, value) for n in _row_numbers(row)):
                continue
            for entity_id in ids:
                found = conflicts.margin_of(self.facts, entity_id, value)
                if found is not None:
                    fact, factor = found
                    if fact.margin is not None and fact.margin_share is not None:
                        return round(fact.margin * factor, 4), fact.margin_share, fact.margin_basis
        return None


def _facts_check(trail: _Trail, record: AnswerRecord) -> dict[str, Any]:
    """The update of an answered record: the facts it used, its margin, and the check "Facts add up"."""
    value = record.value
    if value is None:
        return {}
    used = trail.used(value)
    ids = sorted({i for _, row_ids in used for i in row_ids})
    update: dict[str, Any] = {"entity_ids": tuple(ids)}
    margin = trail.margin(float(value)) if isinstance(value, (int, float)) else None
    if margin is not None:
        update |= {"margin": margin[0], "margin_share": margin[1], "margin_basis": margin[2]}
    if not ids:
        return update
    measured = margin is not None or any(conflicts.is_measured(row) for row, _ in used)
    hits = conflicts.touching(trail.facts, set(ids), measured=measured)
    if hits:
        check = Check(id="agreement", label="Facts add up", state="fail", factor=CONFLICT_FACTOR,
                      detail=" ".join(c.text for c in hits[:3])[:600])  # fmt: skip
    else:
        check = Check(id="agreement", label="Facts add up", state="pass",
                      detail="the facts that this answer uses agree with the other facts of the document")  # fmt: skip
    update["checks"] = (*record.checks, check)
    update["confidence"] = round(record.confidence * check.factor, 3)
    return update


def run_agent(  # noqa: C901, PLR0912, PLR0915 - one loop, kept in one place so the order of steps is visible
    question: str,
    tools: list[ToolSpec],
    chat: Chat,
    *,
    context: str = "",
    max_turns: int = 12,
    max_rejections: int = 2,
    on_step: Callable[[Step], None] | None = None,
    facts: DocumentFacts | None = None,
) -> AgentResult:
    """Run the loop for one question. `chat(messages, tool_schemas)` is the model.

    With the `facts` of the document, a tool result whose rows use a fact in conflict carries a note to the model,
    and the answer gets the facts it used, its error margin and the check "Facts add up".
    """
    trail = _Trail(facts, {e.id for e in facts.entities}) if facts is not None else None
    by_name = {tool.name: tool for tool in tools}
    schemas = [tool.schema() for tool in tools] + [CALC_SCHEMA, SUBMIT_SCHEMA, ABSTAIN_SCHEMA]
    ledger = Ledger(question_numbers=numbers(question))
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": (context + "\n\n" if context else "") + "Question: " + question},
    ]
    run = Run(AGENT)
    run.fire(Event.BEGIN)
    steps: list[Step] = []
    evidence: list[Evidence] = []
    cost = 0.0
    rejections = 0
    final: AnswerRecord | None = None

    for _ in range(max_turns):
        reply = chat(messages, schemas)
        cost += reply.cost_usd
        messages.append(reply.message or {"role": "assistant", "content": reply.content})
        calls: tuple[ToolCall, ...] = reply.tool_calls
        if not calls:
            messages.append({"role": "user", "content": "Call a tool. Finish with submit_answer or abstain."})
            continue
        terminal = next((c for c in calls if c.name in {"submit_answer", "abstain"}), None)
        work = [c for c in calls if c.name not in {"submit_answer", "abstain"}]
        if work:
            run.fire(Event.CALL)
            for call in work:
                note = ""
                if call.name == "calc":
                    data: Any = _run_calc(call.arguments, ledger)
                    if trail is not None and "result" in data:
                        expression = str(call.arguments.get("expression", ""))
                        trail.calcs.append((data["result"], evaluate(expression)[1], expression))
                    steps.append(_step("calc", "deterministic", call.arguments, ToolOutput(data=data), 0.0))
                    if on_step:
                        on_step(steps[-1])
                elif call.name in by_name:
                    spec = by_name[call.name]
                    started = time.perf_counter()
                    try:
                        output = spec.run(call.arguments)
                    except Exception as exc:  # a tool failure is a result that the model must see
                        output = ToolOutput(ok=False, error=f"{type(exc).__name__}: {exc}")
                    took = 1000 * (time.perf_counter() - started)
                    cost += output.cost_usd
                    data = output.data if output.ok else {"error": output.error}
                    if output.ok:
                        ledger.add(output.data)
                        evidence.extend(output.evidence[:40])
                        if trail is not None:
                            rows = _rows(output.data, trail.known)
                            trail.rows.extend(rows)
                            ids = {i for _, row_ids in rows for i in row_ids}
                            hits = conflicts.touching(
                                trail.facts, ids, measured=any(conflicts.is_measured(r) for r, _ in rows)
                            )
                            note = _note(hits) if hits else ""
                    steps.append(_step(spec.name, spec.method, call.arguments, output, took))
                    if on_step:
                        on_step(steps[-1])
                else:
                    data = {"error": f"unknown tool {call.name}"}
                content = json.dumps(data)[:60000]
                messages.append(
                    {"role": "tool", "tool_call_id": call.call_id, "content": content + ("\n" + note if note else "")}
                )
            run.fire(Event.OBSERVE)
            if terminal is not None:  # an answer in the same turn as its facts: ask again after the results
                refusal = "Results are above. Now call submit_answer or abstain as a separate step."
                messages.append({"role": "tool", "tool_call_id": terminal.call_id, "content": refusal})
            continue
        if terminal is None:
            continue
        if terminal.name == "abstain":
            run.fire(Event.ABSTAIN)
            raw = str(terminal.arguments.get("reason", ""))
            reason = MissingReason(raw) if raw in MissingReason._value2member_map_ else MissingReason.UNSUPPORTED
            estimate = terminal.arguments.get("best_estimate")
            final = _abstain(
                reason,
                str(terminal.arguments.get("detail", "")),
                str(terminal.arguments.get("request", "")),
                estimate if isinstance(estimate, (int, float, str)) and not isinstance(estimate, bool) else None,
            )
            break
        run.fire(Event.SUBMIT)
        record, refusal = _check(terminal.arguments, ledger)
        if record is not None:
            run.fire(Event.ACCEPT)
            final = record
            break
        rejections += 1
        if rejections > max_rejections:
            run.fire(Event.EXHAUST)
            final = _abstain(MissingReason.UNSUPPORTED, "the answer had no source in a tool result", "ask again")
            break
        run.fire(Event.REJECT)
        messages.append({"role": "tool", "tool_call_id": terminal.call_id, "content": refusal})

    if final is None:
        run.fire(Event.EXHAUST)
        final = _abstain(MissingReason.UNSUPPORTED, "the step limit was reached", "ask a narrower question")
    update: dict[str, Any] = {"steps": tuple(steps), "evidence": tuple(evidence[:60]), "cost_usd": cost}
    if final.status == "answered":
        update["model_confidence"] = final.confidence
    stated = [s.confidence for s in steps if s.ok and s.confidence is not None]
    if final.status == "answered" and stated:
        # the answer is not more sure than the least sure measurement that the model read
        update["confidence"] = min(final.confidence, *stated)
        update["checks"] = tuple({c.id: c for s in steps if s.ok for c in s.checks}.values())
    final = final.model_copy(update=update)
    if trail is not None and final.status == "answered":
        final = final.model_copy(update=_facts_check(trail, final))
    return AgentResult(record=final, events=run.events(), rejections=rejections)
