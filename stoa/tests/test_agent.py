"""The agent loop with a scripted model. The provenance rule must stop an invented number."""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from bp.agent import core
from bp.agent.calc import CalcError, evaluate
from bp.agent.core import Event, ToolOutput, ToolSpec, run_agent
from bp.llm import ChatResult, ToolCall

ROOMS = [{"name": "Bad", "area_m2": 4.52}, {"name": "WC", "area_m2": 1.8}, {"name": "Zimmer", "area_m2": 14.07}]


def rooms_tool() -> ToolSpec:
    return ToolSpec(
        name="list_rooms",
        description="rooms",
        parameters={"type": "object", "properties": {}},
        run=lambda _: ToolOutput(data={"rooms": ROOMS}),
    )


def script(*turns: list[tuple[str, dict[str, Any]]]):
    queue = list(turns)
    seen: list[list[dict[str, Any]]] = []

    def chat(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ChatResult:
        assert {t["function"]["name"] for t in tools} >= {"calc", "submit_answer", "abstain"}
        seen.append(list(messages))
        calls = tuple(
            ToolCall(call_id=f"c{len(seen)}{i}", name=n, arguments=a) for i, (n, a) in enumerate(queue.pop(0))
        )
        return ChatResult(content="", tool_calls=calls, message={"role": "assistant", "content": ""})

    return chat, seen


def submit(value: float | str, unit: str | None = "m2") -> tuple[str, dict[str, Any]]:
    return ("submit_answer", {"value": value, "unit": unit, "confidence": 0.9, "convention": "rooms Bad and WC"})


def test_composed_answer_is_accepted() -> None:
    chat, _ = script(
        [("list_rooms", {})],
        [("calc", {"expression": "sum([4.52, 1.8]) * 1.10"})],
        [submit(6.95)],
    )
    result = run_agent("How many m2 of tiles for the bathrooms with 10% waste?", [rooms_tool()], chat)
    assert result.record.status == "answered"
    assert result.record.value == 6.95
    assert result.events == [
        Event.BEGIN,
        Event.CALL,
        Event.OBSERVE,
        Event.CALL,
        Event.OBSERVE,
        Event.SUBMIT,
        Event.ACCEPT,
    ]
    assert [s.tool for s in result.record.steps] == ["list_rooms", "calc"]


def test_invented_number_is_refused_then_abstains() -> None:
    chat, seen = script([("list_rooms", {})], [submit(6.4)], [submit(6.5)], [submit(6.6)])
    result = run_agent("Total bathroom area?", [rooms_tool()], chat)
    assert result.record.status == "abstained"
    assert result.rejections == 3
    assert "REFUSED" in seen[2][-1]["content"]
    assert result.events[-1] is Event.EXHAUST


def test_calc_refuses_a_number_from_nowhere() -> None:
    chat, seen = script(
        [("list_rooms", {})],
        [("calc", {"expression": "4.52 + 1.9"})],
        [("abstain", {"reason": "unreadable", "detail": "d", "request": "r"})],
    )
    result = run_agent("Total bathroom area?", [rooms_tool()], chat)
    assert "REFUSED" in seen[2][-1]["content"]
    assert result.record.status == "abstained"
    assert result.record.abstain is not None
    assert result.record.abstain.reason == "unreadable"


def test_answer_in_the_same_turn_as_the_tool_call_is_not_taken() -> None:
    chat, _ = script([("list_rooms", {}), submit(4.52)], [submit(4.52)])
    result = run_agent("Area of Bad?", [rooms_tool()], chat)
    assert result.record.value == 4.52
    assert result.events.count(Event.SUBMIT) == 1


def test_text_answer_must_come_from_a_tool() -> None:
    chat, _ = script([("list_rooms", {})], [submit("Zimmer", None)])
    assert run_agent("Largest room?", [rooms_tool()], chat).record.value == "Zimmer"
    chat, _ = script([("list_rooms", {})], [submit("Kitchen", None)], [submit("Küche", None)], [submit("x", None)])
    assert run_agent("Largest room?", [rooms_tool()], chat).record.status == "abstained"


def test_step_limit_and_tool_failure() -> None:
    def broken(_: dict[str, Any]) -> ToolOutput:
        raise RuntimeError("no file")

    tool = ToolSpec(name="list_rooms", description="", parameters={"type": "object", "properties": {}}, run=broken)
    chat, seen = script(*[[("list_rooms", {})] for _ in range(3)])
    result = run_agent("q", [tool], chat, max_turns=3)
    assert result.record.status == "abstained"
    assert "no file" in seen[1][-1]["content"]


def test_calc() -> None:
    assert evaluate("sum([1.5, 2.5]) * 2")[0] == 8.0
    assert evaluate("count([3, 4, 5])")[0] == 3.0
    assert evaluate("round(10 * FT2_PER_M2, 2)")[0] == 107.64
    assert sorted(evaluate("max(1.5, 2) - 0.25")[1]) == [0.25, 1.5, 2.0]
    for bad in ("__import__('os')", "a.b", "[1,2]", "1 if 2 else 3", "x", "1/0", "'a'", "sum(1, k=2)", "(lambda: 1)()"):
        with pytest.raises(CalcError):
            evaluate(bad)


@given(a=st.floats(-1e6, 1e6), b=st.floats(-1e6, 1e6))
def test_calc_matches_python(a: float, b: float) -> None:
    value, literals = evaluate(f"({a!r}) + ({b!r}) * 2")
    assert value == pytest.approx(a + b * 2)
    assert sorted(literals) == sorted([abs(a), abs(b), 2.0])


def test_identifier_given_as_number_with_text_unit_becomes_a_string() -> None:
    ledger = core.Ledger(question_numbers=[])
    ledger.add({"name": "302", "long_name": "KORIDOR"})
    record, why = core._check({"value": 302.0, "unit": "text", "confidence": 0.9}, ledger)
    assert why == ""
    assert record is not None
    assert record.value == "302"
    assert record.unit is None


def test_room_number_with_an_area_unit_is_refused() -> None:
    def run(_: dict[str, Any]) -> ToolOutput:
        return ToolOutput(data={"rooms": [{"number": "2.30", "label": "Reduit", "area_m2": 31.05}]})

    tool = ToolSpec("list_rooms", "Rooms with number, label and area.", {"type": "object", "properties": {}}, run)
    chat, seen = script([("list_rooms", {})], [submit(2.3)], [submit(31.05)])
    result = run_agent("Which room is the largest, and how large is it?", [tool], chat)
    assert "room number or a tag" in seen[2][-1]["content"]
    assert (result.record.status, result.record.value, result.record.unit) == ("answered", 31.05, "m2")
    # The same number as a which-answer with no measure unit is fine.
    chat, _ = script([("list_rooms", {})], [submit("2.30", None)])
    assert run_agent("Which room is the largest?", [tool], chat).record.value == "2.30"
