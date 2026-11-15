"""Historic scans: the route rule, the text joins, the title block, the scale bars, the tools and the facts."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from bp import llm
from bp.contract import Calibration
from bp.facts_scan import scan_facts
from bp.solvers import scan_tools
from bp.tools import scan_look, scan_reading, sheet_text
from bp.tools.count_head import PlanCounts
from bp.tools.ocr import TextLine


def line(text: str, x: float, y: float, w: float | None = None, h: float = 20.0) -> TextLine:
    """A text line with its centre at (x, y)."""
    w = w if w is not None else 12.0 * len(text)
    x0, y0, x1, y1 = x - w / 2, y - h / 2, x + w / 2, y + h / 2
    return TextLine(text=text, box=((x0, y0), (x1, y0), (x1, y1), (x0, y1)), score=0.99)


def counts(*, in_distribution: bool, style: float | None) -> PlanCounts:
    return PlanCounts.model_construct(in_distribution=in_distribution, style_margin=style)


def blank(width: int = 1200, height: int = 900) -> np.ndarray:
    return np.full((height, width, 3), 255, dtype=np.uint8)


# ----------------------------------------------------------------------------- route rule


def test_route_keeps_known_plans_and_numbered_plans() -> None:
    plain = [line("SECTION A-A", 300, 300)]
    numbered = [line(text, 100 + 150 * i, 100) for i, text in enumerate(("2.18", "3.04", "3.05", "4.11", "15.6 m2"))]
    assert scan_reading.is_scan(counts(in_distribution=False, style=-4.0), plain)
    assert not scan_reading.is_scan(counts(in_distribution=True, style=-4.0), plain)  # the count model knows it
    assert not scan_reading.is_scan(counts(in_distribution=False, style=3.0), plain)  # CubiCasa style
    assert not scan_reading.is_scan(counts(in_distribution=False, style=-4.0), numbered)  # a modern flat plan
    bar = [line("0", 100, 100), line("5 m", 200, 100), line("10 m", 300, 100), line("15 m", 400, 100)]
    assert scan_reading.is_scan(counts(in_distribution=False, style=-4.0), bar)  # scale bar labels are no areas


# ----------------------------------------------------------------------------- text


def test_phrases_join_words_of_one_row_and_keep_numbers_apart() -> None:
    joined = scan_reading.phrases([line("SECOND", 100, 100, 70), line("FLOOR", 180, 100, 60), line("PLAN", 250, 100, 50),
                                   line("12'-6\"", 330, 100, 60)])  # fmt: skip
    texts = [ln.text for ln in joined]
    assert "SECOND FLOOR PLAN" in texts
    assert "12'-6\"" in texts


def test_title_block_roles() -> None:
    labels = sheet_text.labels([
        line("DRAWN BY: KENNETH L. LAMBERT", 600, 800, 330), line("SHEET 2 OF 3", 1000, 800, 140),
        line("MEASURED JUNE 1934", 300, 800, 220), line("FIRST FLOOR PLAN", 600, 100, 400, 40),
        line("SCALE 1:500", 900, 120, 130),
    ])  # fmt: skip
    found = {(t.role, t.value) for t in scan_reading.title_texts(labels)}
    assert ("drawn by", "KENNETH L. LAMBERT") in found
    assert ("sheet number", "SHEET 2 OF 3") in found
    assert ("year", "1934") in found
    assert ("kind", "floor plan") in found
    assert ("printed scale", "1:500") in found
    assert ("title", "FIRST FLOOR PLAN") in found


def test_a_fraction_is_a_scale_only_when_it_is_common_or_next_to_a_scale_word() -> None:
    alone = sheet_text.labels([line("1/500", 200, 200, 60)])
    odd = sheet_text.labels([line("1/37", 200, 200, 60)])
    worded = sheet_text.labels([line("Skala 1/37", 200, 200, 110)])
    assert [r for r, _ in scan_reading.printed_ratios(alone)] == ["1:500"]
    assert scan_reading.printed_ratios(odd) == []
    assert [r for r, _ in scan_reading.printed_ratios(worded)] == ["1:37"]
    engineer = sheet_text.labels([line("SCALE: I\" = 20'", 200, 200, 160)])
    assert [r for r, _ in scan_reading.printed_ratios(engineer)] == ["1:240 (I\" = 20')"]
    inset = sheet_text.labels([line("SCALE:1:125,000 CONTOUR LINES", 200, 200, 300)])
    assert [r for r, _ in scan_reading.printed_ratios(inset)] == ["1:125000"]


# ----------------------------------------------------------------------------- scale


def bar_lines(unit_words: list[TextLine]) -> list[TextLine]:
    return [line("0", 100, 500, 12), line("5", 200, 500, 12), line("10", 300, 500, 24), line("15", 400, 500, 24),
            *unit_words]  # fmt: skip


def test_scale_bar_in_metres() -> None:
    bars = scan_reading.scale_bars(blank().mean(axis=2), bar_lines([line("METRES", 250, 540, 80)]))
    assert len(bars) == 1
    assert bars[0].unit == "m"
    assert bars[0].ppm == pytest.approx(20.0, rel=0.01)


def test_scale_bar_with_two_units_near_it_has_no_unit() -> None:
    near = [line("SCALE IN METERS", 250, 535, 160), line("SCALE 1/4\" = 1'-0\"", 250, 465, 180)]
    bars = scan_reading.scale_bars(blank().mean(axis=2), bar_lines(near))
    assert bars
    assert bars[0].ppm is None
    assert scan_reading.scan_scale(bars, None) is None


def test_scale_bar_in_an_old_unit_is_never_converted() -> None:
    bars = scan_reading.scale_bars(blank().mean(axis=2), bar_lines([line("Ellen", 460, 500, 50)]))
    assert bars[0].unit == "ellen"
    assert bars[0].ppm is None


def test_two_units_on_one_row_are_two_bars() -> None:
    row = [line("0 m", 100, 500, 36), line("5 m", 200, 500, 36), line("10 m", 300, 500, 48),
           line("0 ft.", 900, 500, 60), line("10 ft.", 961, 500, 72), line("20 ft.", 1022, 500, 72)]  # fmt: skip
    bars = scan_reading.scale_bars(blank(1300).mean(axis=2), row)
    assert {b.unit for b in bars} == {"m", "ft"}


def bar(ppm: float, error: float = 0.02) -> scan_reading.BarScale:
    return scan_reading.BarScale(values=(0.0, 10.0), xs_px=(0.0, 10 * ppm), on_ticks=False, row_y=0.0,
                                 px_per_unit=ppm, unit="m", metres_per_unit=1.0, ppm=ppm, error=error,
                                 texts=("0", "10 m"))  # fmt: skip


def test_witnesses_that_disagree_give_no_scale() -> None:
    assert scan_reading.scan_scale([bar(20.0), bar(22.0)], None) is None
    agreed = scan_reading.scan_scale([bar(20.0), bar(20.2)], None)
    assert agreed is not None
    assert agreed.confirmed
    assert agreed.source == "scale bars"


def test_user_points_give_the_scale() -> None:
    given = Calibration(points=((0.0, 0.0), (300.0, 400.0)), real_length_m=10.0)
    scale = scan_reading.scan_scale([], None, given)
    assert scale is not None
    assert scale.ppm == pytest.approx(50.0)
    assert scale.source == "user"


# ----------------------------------------------------------------------------- tools and facts


def tools_by_name(rgb: np.ndarray, lines: list[TextLine], calibration: Calibration | None = None) -> dict[str, Any]:
    _, tools = scan_tools.scan_tools(rgb, lines, calibration)
    return {t.name: t for t in tools}


def test_measure_length_fails_without_scale_and_names_the_reason() -> None:
    rgb = blank()
    rgb[1, 1] = 0  # a different image key from the other tests
    tools = tools_by_name(rgb, [line("SCALE 1:100", 600, 800, 130)])
    out = tools["measure_length"].run({"x0": 0, "y0": 0, "x1": 100, "y1": 0})
    assert not out.ok
    assert out.error.startswith("no_scale")
    assert "print size" in out.error
    assert {"find_text", "read_region", "read_title_block", "read_scale", "drawing_size", "look"} <= set(tools)
    assert tools["look"].method == "model"


def test_measure_length_at_a_user_scale() -> None:
    rgb = blank()
    rgb[2, 2] = 0
    given = Calibration(points=((0.0, 0.0), (500.0, 0.0)), real_length_m=10.0)
    out = tools_by_name(rgb, [line("PLAN", 600, 800, 60)], given)["measure_length"].run(
        {"x0": 100, "y0": 100, "x1": 100, "y1": 350}
    )
    assert out.ok
    assert out.data["metres"] == pytest.approx(5.0)
    assert 0 < out.data["margin_m"] < 0.5


def test_scan_facts_have_label_scale_and_title_entities() -> None:
    rgb = blank()
    rgb[100:600, 200:205] = 0  # a wall, so there is one drawing
    rgb[100:105, 200:900] = 0
    rgb[3, 3] = 0
    lines = [line("FIRST FLOOR PLAN", 600, 700, 300, 30), line("DRAWN BY: A. AALTO", 600, 800, 220)]
    given = Calibration(points=((0.0, 0.0), (500.0, 0.0)), real_length_m=10.0)
    found = scan_facts("scan.jpg", rgb, given, lines)
    assert found is not None
    assert found.kind == "scan"
    ids = {e.id for e in found.entities}
    assert "scale" in ids
    assert any(i.startswith("label:") for i in ids)
    assert "drawing:0" in ids
    summary = {f.key: f for f in found.summary}
    assert summary["px_per_metre"].value == pytest.approx(50.0)
    assert summary["drawn_by"].value == "A. AALTO"
    assert summary["drawing_kind"].value == "floor plan"
    assert all(f.basis for f in summary.values())


# ----------------------------------------------------------------------------- look


def fake_chat(replies: dict[str, str]) -> Any:
    def chat(model: str, messages: list[dict[str, Any]], **_: Any) -> llm.ChatResult:  # noqa: ARG001
        return llm.ChatResult(content=replies[model], cost_usd=0.001)

    return chat


def test_look_gives_a_count_only_when_both_models_agree_and_are_sure(monkeypatch: pytest.MonkeyPatch) -> None:
    agree = '{"answer": "7", "count": 7, "sure": true, "seen": "the doors of the elevation"}'
    other = '{"answer": "6", "count": 6, "sure": true, "seen": "the doors"}'
    unsure = '{"answer": "7", "count": 7, "sure": false, "seen": "faded"}'
    a, b = "model-a", "model-b"
    monkeypatch.setattr(llm, "chat", fake_chat({a: agree, b: agree}))
    seen = scan_look.look(blank(), "how many doors?", models=(a, b))
    assert seen.agreed_count == 7
    out = scan_tools.look_output(seen)
    assert out.confidence == scan_look.LOOK_AGREED.confidence
    monkeypatch.setattr(llm, "chat", fake_chat({a: agree, b: other}))
    seen = scan_look.look(blank(), "how many doors?", models=(a, b))
    assert seen.agreed_count is None
    assert "abstain" in scan_tools.look_output(seen).data["note"]
    monkeypatch.setattr(llm, "chat", fake_chat({a: agree, b: unsure}))
    assert scan_look.look(blank(), "how many doors?", models=(a, b)).agreed_count is None
    monkeypatch.setattr(llm, "chat", fake_chat({a: agree, b: "no json here"}))
    seen = scan_look.look(blank(), "how many doors?", models=(a, b))
    assert seen.agreed_count is None
    assert seen.readings[1].error


def test_look_says_when_no_vision_model_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*_: Any, **__: Any) -> llm.ChatResult:
        raise RuntimeError("router status 402: Insufficient credits")

    monkeypatch.setattr(llm, "chat", broken)
    monkeypatch.setenv(scan_look.LOOK_MODELS_ENV, "model-x, model-y")
    assert scan_look.look_models() == ("model-x", "model-y")
    out = scan_tools.look_output(scan_look.look(blank(), "how many doors?"))
    assert not out.ok
    assert "vision model not available" in out.error
