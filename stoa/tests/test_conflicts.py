"""Measured rates and margins, facts that do not add up, and the agent check "Facts add up"."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bp import conflicts, rates
from bp.agent.core import CONFLICT_FACTOR, ToolOutput, ToolSpec, run_agent
from bp.contract import Conflict
from bp.facts import DocumentFacts, Entity, rated
from bp.llm import ChatResult, ToolCall

SWISS_PDF = Path(__file__).resolve().parents[1] / "data/junction-dataset-preview/data/swiss_dwellings"


def room(entity_id: str, area: float, *, printed: float | None = None) -> Entity:
    rate, margin = rates.sheet_room(area, divided=False, scale_source="dimension lines", agreeing=8, spread=0.005)
    facts = [rated("area", area, rate, margin, unit="m2", status="estimated")]
    if printed is not None:
        facts.append(rated("printed_area", printed, rates.SHEET_PRINTED, unit="m2"))
    return Entity(
        id=entity_id, kind="room", label=entity_id, geometry="point", points=((0.0, 0.0),), facts=tuple(facts)
    )


def test_room_margin_follows_its_own_evidence() -> None:
    normal, normal_margin = rates.sheet_room(
        20.0, divided=False, scale_source="dimension lines", agreeing=8, spread=0.005
    )
    assert normal.confidence == round(61 / 65, 3)
    assert normal_margin.value == pytest.approx(1.0)  # 5% of 20 m2
    assert normal_margin.share == round(61 / 65, 3)
    small, small_margin = rates.sheet_room(5.0, divided=False, scale_source="dimension lines", agreeing=8, spread=0.005)
    assert small.confidence < normal.confidence
    assert small_margin.value == pytest.approx(0.5)  # 10%
    _, weak_margin = rates.sheet_room(20.0, divided=False, scale_source="dimension lines", agreeing=3, spread=0.005)
    assert weak_margin.value == pytest.approx(5.0)  # 25%: few dimension lines agree
    divided, divided_margin = rates.sheet_room(
        20.0, divided=True, scale_source="dimension lines", agreeing=8, spread=0.0
    )
    assert divided.confidence < 0.5
    assert divided_margin.value == pytest.approx(10.0)
    _, spread_margin = rates.sheet_room(20.0, divided=False, scale_source="dimension lines", agreeing=8, spread=0.039)
    assert spread_margin.value == pytest.approx(20.0 * (0.05 + 2 * 0.02))  # wider witnesses than the benchmark saw
    user, _ = rates.sheet_room(20.0, divided=False, scale_source="user", agreeing=None, spread=None)
    assert user.confidence < normal.confidence
    assert "user" in user.basis


def test_a_fact_with_no_benchmark_says_so() -> None:
    rate = rates.unmeasured("wall lengths on sheets")
    assert rate.confidence <= 0.5
    assert not rate.measured
    assert "no benchmark" in rate.basis
    fact = rated("area", None, rates.SWISS_AREA, rates.swiss_area_margin(10.0))
    assert (fact.status, fact.confidence, fact.margin) == ("unknown", 0.0, None)


def test_sum_margin_adds_the_parts() -> None:
    parts = [rates.Margin(value=0.5, share=0.9, basis="b"), rates.Margin(value=1.0, share=0.8, basis="b")]
    total = rates.sum_margin(parts)
    assert total is not None
    assert (total.value, total.share) == (1.5, 0.8)
    assert rates.sum_margin([]) is None


def test_measured_against_printed_area() -> None:
    agree = room("room:a", 20.0, printed=20.6)  # inside the margin of 1.0 m2
    disagree = room("room:b", 20.0, printed=25.0)
    found = conflicts.find(DocumentFacts(kind="sheet", entities=(agree, disagree)))
    assert [c.id for c in found] == ["area:room:b"]
    assert found[0].doubtful == ("room:b",)
    assert "25" in found[0].text


def test_sum_of_rooms_against_a_printed_total() -> None:
    parts = (room("room:1", 10.0), room("room:2", 20.0))
    total = rated("printed_area", 40.0, rates.SHEET_PRINTED, unit="m2")
    group = Entity(id="apartment:A", kind="apartment", label="Apartment A", geometry="point", points=((0.0, 0.0),),
                   facts=(total,), members=("room:1", "room:2"))  # fmt: skip
    found = conflicts.find(DocumentFacts(kind="sheet", entities=(*parts, group)))
    assert [c.id for c in found] == ["sum:apartment:A"]
    assert set(found[0].doubtful) == {"room:1", "room:2"}
    close = group.model_copy(update={"facts": (rated("printed_area", 31.0, rates.SHEET_PRINTED, unit="m2"),)})
    assert conflicts.find(DocumentFacts(kind="sheet", entities=(*parts, close))) == ()


def test_two_door_counts() -> None:
    assert conflicts.count_conflict("d", (), "Doors", ("a", 100), ("b", 103)) is None  # within 3%
    assert conflicts.count_conflict("d", (), "Doors", ("a", 10), ("b", 12)) is None  # within 2
    found = conflicts.count_conflict("d", ("door:1",), "Doors", ("a", 40), ("b", 51))
    assert found is not None
    assert "40" in found.text


def test_swiss_scale_against_its_bar() -> None:
    assert conflicts.swiss_scale(100, agrees=True, bar_ratio=100.0) == []
    found = conflicts.swiss_scale(100, agrees=False, bar_ratio=120.0)
    assert found[0].all_measured


def test_row_links() -> None:
    known = {"room:3.04", "apartment:A", "room:1:2"}
    assert conflicts.row_ids({"entity_id": "room:1:2"}, known) == ["room:1:2"]
    assert conflicts.row_ids({"number": "3.04", "area_m2": 1.0}, known) == ["room:3.04"]
    assert conflicts.row_ids({"letter": "A"}, known) == ["apartment:A"]
    assert conflicts.row_ids({"number": "9.99"}, known) == []


# ----------------------------------------------------------------------------- the agent


def facts_with_conflict() -> DocumentFacts:
    rooms = (room("room:a", 10.0, printed=14.0), room("room:b", 20.0))
    return DocumentFacts(
        kind="sheet", entities=rooms, conflicts=conflicts.find(DocumentFacts(kind="sheet", entities=rooms))
    )


def area_tool() -> ToolSpec:
    rows = [{"entity_id": "room:a", "room": "A", "area_m2": 10.0, "area_sqft": 108},
            {"entity_id": "room:b", "room": "B", "area_m2": 20.0, "area_sqft": 215}]  # fmt: skip
    return ToolSpec(name="rooms", description="rooms", parameters={"type": "object", "properties": {}},
                    run=lambda _: ToolOutput(data={"rooms": rows}))  # fmt: skip


def scripted(*turns: list[tuple[str, dict[str, Any]]]):
    queue = list(turns)
    seen: list[list[dict[str, Any]]] = []

    def chat(messages: list[dict[str, Any]], _tools: list[dict[str, Any]]) -> ChatResult:
        seen.append(list(messages))
        calls = tuple(
            ToolCall(call_id=f"c{len(seen)}{i}", name=n, arguments=a) for i, (n, a) in enumerate(queue.pop(0))
        )
        return ChatResult(content="", tool_calls=calls, message={"role": "assistant", "content": ""})

    return chat, seen


def answer(value: float, unit: str = "m2") -> tuple[str, dict[str, Any]]:
    return ("submit_answer", {"value": value, "unit": unit, "confidence": 0.9, "convention": "c"})


def test_the_model_reads_the_conflict_and_the_answer_is_less_sure() -> None:
    chat, seen = scripted([("rooms", {})], [answer(10.0)])
    record = run_agent("Area of A?", [area_tool()], chat, facts=facts_with_conflict()).record
    tool_message = next(m for m in seen[1] if m["role"] == "tool")
    assert "FACTS DO NOT ADD UP" in tool_message["content"]
    check = next(c for c in record.checks if c.id == "agreement")
    assert (check.label, check.state, check.factor) == ("Facts add up", "fail", CONFLICT_FACTOR)
    assert record.confidence == pytest.approx(0.9 * CONFLICT_FACTOR)
    assert record.entity_ids == ("room:a",)
    assert record.margin == pytest.approx(0.5)  # 5% of 10 m2
    assert record.margin_share == round(61 / 65, 3)


def test_an_answer_on_facts_that_agree_passes() -> None:
    chat, _ = scripted([("rooms", {})], [answer(20.0)])
    record = run_agent("Area of B?", [area_tool()], chat, facts=facts_with_conflict()).record
    check = next(c for c in record.checks if c.id == "agreement")
    assert check.state == "pass"
    assert record.confidence == pytest.approx(0.9)


def test_margin_of_a_sum_and_of_a_unit_change() -> None:
    chat, _ = scripted([("rooms", {})], [("calc", {"expression": "10.0 + 20.0"})], [answer(30.0)])
    record = run_agent("Total?", [area_tool()], chat, facts=facts_with_conflict()).record
    assert record.margin == pytest.approx(1.5)  # 0.5 + 1.0
    assert set(record.entity_ids) == {"room:a", "room:b"}
    chat, _ = scripted([("rooms", {})], [answer(215, "ft2")])
    record = run_agent("Area of B in sq ft?", [area_tool()], chat, facts=facts_with_conflict()).record
    assert record.margin == pytest.approx(1.0 / 0.09290304, rel=1e-3)


def test_a_difference_has_no_margin() -> None:
    chat, _ = scripted([("rooms", {})], [("calc", {"expression": "215 - 108"})], [answer(107, "ft2")])
    record = run_agent("Difference?", [area_tool()], chat, facts=facts_with_conflict()).record
    assert record.status == "answered"
    assert record.margin is None


def test_no_facts_changes_nothing() -> None:
    chat, seen = scripted([("rooms", {})], [answer(10.0)])
    record = run_agent("Area of A?", [area_tool()], chat).record
    assert all(c.id != "agreement" for c in record.checks)
    assert record.margin is None
    assert "FACTS DO NOT ADD UP" not in next(m for m in seen[1] if m["role"] == "tool")["content"]


def test_conflict_type_is_frozen() -> None:
    found = Conflict(id="x", entity_ids=("a",), text="t")
    assert found.doubtful == ()
    assert not found.all_measured


@pytest.mark.skipif(not SWISS_PDF.exists(), reason="the dataset preview is not on this machine")
def test_swiss_plan_facts_have_rates_and_margins() -> None:
    from bp.facts import document_facts  # noqa: PLC0415

    found = document_facts(next(iter(sorted(SWISS_PDF.glob("*.pdf")))))
    assert found.kind == "plan_pdf"
    assert found.summary
    areas = [f for e in found.entities if e.kind == "room" for f in e.facts if f.key == "area" and f.value is not None]
    assert areas
    assert all(f.basis and f.margin is not None and f.margin_share == 1.0 for f in areas if f.status == "known")
    living = [f for e in found.entities if e.kind == "apartment" for f in e.facts if f.key == "living_area"]
    assert all(f.margin is not None for f in living if f.status == "known")
