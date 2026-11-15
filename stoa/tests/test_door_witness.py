"""The second count of the doors: the second detector when it has seen the sheet, else the arc finder."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from bp.contract import Check
from bp.solvers import drawing_sheet
from bp.tools import sheet_plan
from bp.tools.sheet_rooms import Swing


def _swings(n: int) -> list[Swing]:
    return [Swing((float(i), 0.0), 90.0, 90.0, (0.0, 90.0), 1) for i in range(n)]


def _plan(detector: int, arcs: int, second: int | None) -> sheet_plan.SheetPlan:
    found = _swings(detector)
    return cast("sheet_plan.SheetPlan", SimpleNamespace(
        swings=found, arc_swings=_swings(arcs), second_swings=None if second is None else _swings(second)))


def test_the_second_detector_is_the_witness_when_it_has_seen_the_sheet() -> None:
    plan = _plan(detector=40, arcs=0, second=41)  # a scan: the arc finder sees no doors
    assert drawing_sheet._door_witness(plan) == ("second_detector", 41)
    assert drawing_sheet._doors_agree(plan) is True


def test_the_arc_finder_stays_the_witness_without_the_second_detector() -> None:
    plan = _plan(detector=40, arcs=30, second=None)  # an upload to the live site
    assert drawing_sheet._door_witness(plan) == ("arc_finder", 30)
    assert drawing_sheet._doors_agree(plan) is False


def test_no_witness_without_the_first_detector() -> None:
    arcs = _swings(12)
    plan = cast("sheet_plan.SheetPlan", SimpleNamespace(swings=arcs, arc_swings=arcs, second_swings=_swings(12)))
    assert drawing_sheet._door_witness(plan) is None
    assert drawing_sheet._doors_agree(plan) is None


def test_the_tool_answers_the_lower_count_when_the_two_detectors_agree() -> None:
    plan = _plan(detector=41, arcs=0, second=40)
    scale = Check(id="scale", label="Scale from dimension lines", state="pass", detail="")
    plan.scale = SimpleNamespace(ppm=100.0, source="dimension lines", check=scale)  # ty: ignore[invalid-assignment]
    count = next(t for t in drawing_sheet.plan_tools(plan) if t.name == "count_door_swings")
    out = count.run({})
    assert out.data["door_leaves"] == 40
    assert out.data["methods_agree"] is True
    assert out.data["door_leaves_second_detector"] == 40
