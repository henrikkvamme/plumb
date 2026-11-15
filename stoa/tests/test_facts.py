"""The facts of a sheet and the answer trace: the API that a UI reads."""

from __future__ import annotations

import cv2
import numpy as np

from bp import facts
from bp.agent.core import ToolOutput, ToolSpec, run_agent
from bp.contract import Calibration, Check, Step
from bp.llm import ChatResult, ToolCall
from bp.solvers import drawing_sheet
from bp.tools import sheet_plan
from bp.tools.ocr import TextLine

PPM = 100.0


def sheet() -> tuple[np.ndarray, list[TextLine]]:
    """A room of 5 m x 4 m with one door, and its name label."""
    gray = np.full((1200, 1600), 255, np.uint8)
    cv2.rectangle(gray, (200, 200), (700, 600), 0, 6)
    cv2.line(gray, (404, 600), (490, 600), 255, 12)
    cv2.line(gray, (400, 600), (400, 510), 0, 3)
    cv2.ellipse(gray, (400, 600), (90, 90), 0, 270, 360, 0, 2)
    line = TextLine(text="OFFICE", box=((420, 380), (500, 380), (500, 400), (420, 400)), score=0.99)
    return np.repeat(gray[:, :, None], 3, axis=2), [line]


def marked() -> Calibration:
    return Calibration(points=((200.0, 200.0), (700.0, 200.0)), real_length_m=5.0)


def test_sheet_facts_give_the_room_with_its_outline_area_and_door() -> None:
    rgb, lines = sheet()

    found = facts.sheet_facts(sheet_plan.plan_for(rgb, lines, marked()))

    room = next(e for e in found.entities if e.kind == "room")
    area = next(f for f in room.facts if f.key == "area")
    assert room.geometry == "polygon"
    assert area.status == "estimated"
    assert abs(float(area.value or 0) - 20.0) < 0.6
    assert 0.0 < area.confidence < 1.0
    assert [c.id for c in area.checks] == ["scale", "closed", "error_band"]
    doors = [e for e in found.entities if e.kind == "door"]
    assert len(doors) == 1
    assert room.members == (doors[0].id,)
    scale = next(e for e in found.entities if e.id == "scale")
    assert scale.facts[0].source == "user"


def test_no_scale_is_an_unknown_and_not_a_guess() -> None:
    rgb, lines = sheet()

    found = facts.sheet_facts(sheet_plan.plan_for(rgb, lines))

    assert not [e for e in found.entities if e.kind in {"room", "door"}]
    assert any("scale" in sentence for sentence in found.unknown)


def test_room_tools_link_rows_and_evidence_to_the_entity() -> None:
    rgb, lines = sheet()
    tools = {t.name: t for t in drawing_sheet.sheet_tools(rgb, lines, marked())[1]}

    area = tools["room_area"].run({"room": "OFFICE"})
    wall = tools["room_perimeter"].run({"room": "OFFICE"})

    assert area.ok
    assert area.data["entity_id"] == area.evidence[0].ref
    assert area.data["entity_id"].startswith("room:")
    assert wall.ok
    assert abs(wall.data["perimeter_m"] - 18.0) < 0.6
    assert len(wall.data["door_widths_m"]) == 1
    assert abs(wall.data["perimeter_without_doors_m"] - 17.1) < 0.6


def test_answer_confidence_is_the_lowest_tool_confidence_and_steps_are_live() -> None:
    weak = Check(id="scale", label="Scale", state="warn", detail="2 lines agree", factor=0.6)
    tool = ToolSpec("measure", "measure", {"type": "object", "properties": {}}, lambda _: ToolOutput(data={"m": 7.5}, checks=(weak,)))
    replies = iter([
        ChatResult(content="", tool_calls=(ToolCall(call_id="1", name="measure", arguments={}),)),
        ChatResult(content="", tool_calls=(ToolCall(call_id="2", name="submit_answer", arguments={
            "value": 7.5, "unit": "m", "confidence": 0.99, "convention": ""}),)),
    ])  # fmt: skip
    seen: list[Step] = []

    record = run_agent("How long?", [tool], lambda _m, _s: next(replies), on_step=seen.append).record

    assert record.status == "answered"
    assert record.confidence == 0.6
    assert record.checks == (weak,)
    assert [s.tool for s in seen] == ["measure"]
    assert seen[0].result == '{"m": 7.5}'
    assert seen[0].confidence == 0.6
