"""The raster tools on small drawn images: text normalisers, the scale witnesses, room fills and the agent tools."""

from __future__ import annotations

import numpy as np
import pytest

from bp.solvers import raster_tools
from bp.tools import ocr, raster_rooms, raster_scale
from bp.tools.ocr import TextLine
from bp.tools.raster_rooms import RasterPlan


def line(text: str, x: float, y: float, w: float = 10.0, h: float = 10.0, score: float = 0.99) -> TextLine:
    box = ((x - w / 2, y - h / 2), (x + w / 2, y - h / 2), (x + w / 2, y + h / 2), (x - w / 2, y + h / 2))
    return TextLine(text=text, box=box, score=score)


# ----------------------------------------------------------------------------- OCR text


@pytest.mark.parametrize(
    ("text", "want"),
    [("2.18", "2.18"), ("2,18", "2.18"), ("O.12", "0.12"), ("U1.03", "U1.03"), ("Bad", None), ("12", None)],
)
def test_room_number(text: str, want: str | None) -> None:
    assert ocr.room_number(text) == want


@pytest.mark.parametrize(
    ("text", "want"), [("15.61 m²", 15.61), ("7,59 m2", 7.59), ("3.06 m", 3.06), ("Zimmer", None), ("3.06", None)]
)
def test_area_value(text: str, want: float | None) -> None:
    assert ocr.area_value(text) == want


def test_merge_lines_keeps_one_line_where_tiles_overlap() -> None:
    a = line("Wohnen", 100, 50, w=40)
    b = line("Wohn", 95, 50, w=28, score=0.995)  # the same word, cut by a tile edge
    c = line("Bad", 300, 50)
    kept = ocr.merge_lines([b, a, c])
    assert [k.text for k in kept] == ["Wohnen", "Bad"]


def test_to_rgb_makes_transparent_white() -> None:
    from PIL import Image  # noqa: PLC0415 - only this test

    rgba = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    assert ocr.to_rgb(rgba).min() == 255


# ----------------------------------------------------------------------------- scale


def bar_sheet(s: float = 50.0, x0: float = 100.0) -> tuple[np.ndarray, list[TextLine]]:
    """A scale bar 0-1-2-5 m with s px per metre: filled 0-1, empty 1-2, filled 2-5, a 1 px outline."""
    gray = np.full((200, 500), 255.0)
    top, bottom = 80, 92
    xs = [x0 + s * v for v in (0, 1, 2, 5)]
    gray[top:bottom, round(xs[0]) : round(xs[1])] = 0
    gray[top:bottom, round(xs[2]) : round(xs[3])] = 0
    gray[top, round(xs[0]) : round(xs[3])] = 0
    gray[bottom - 1, round(xs[0]) : round(xs[3])] = 0
    labels = [line(str(v), x0 + s * v, 64) for v in (0, 1, 2, 5)]
    return gray, [*labels, line("m", xs[3] + 20, 64)]


def test_scale_bar_is_measured() -> None:
    gray, lines = bar_sheet(s=50.0)
    got = raster_scale.measure_scale(gray, lines)
    assert got is not None
    assert got.source == "bar"
    assert got.bar is not None
    assert got.bar.ppm == pytest.approx(50.0, rel=0.01)


def test_scale_text_with_paper_size_gives_ppm() -> None:
    lines = [line("1:100 (A3)", 1000, 1700, w=80)]
    got = raster_scale.text_witness(lines, 2480, 1754)
    assert got is not None
    witness, _ = got
    assert witness.ratio == 100
    assert witness.ppm == pytest.approx(2480 / 0.42 / 100)


def test_scale_text_is_refused_when_the_image_is_not_the_whole_sheet() -> None:
    got = raster_scale.text_witness([line("1:100 (A3)", 100, 100, w=80)], 1000, 1000)
    assert got is not None
    assert got[0].ppm is None


def test_both_witnesses_agree() -> None:
    s = 877 / 0.42 / 100  # an A3 sheet at 53 dpi keeps the test small
    gray, lines = bar_sheet(s=s)
    canvas = np.full((620, 877), 255.0)
    canvas[:200, :500] = gray
    got = raster_scale.measure_scale(canvas, [*lines, line("1:100 (A3)", 600, 600, w=80)])
    assert got is not None
    assert got.source == "both"
    assert got.confirmed
    assert got.ppm == pytest.approx(877 / 0.42 / 100)


def test_no_witness_gives_none() -> None:
    assert raster_scale.measure_scale(np.full((100, 100), 255.0), [line("Bad", 50, 50)]) is None


# ----------------------------------------------------------------------------- rooms


def drawn_rooms() -> np.ndarray:
    """Two rooms of 100 x 100 and 100 x 60 px inside 6 px walls, joined by a door gap of 20 px."""
    gray = np.full((140, 240), 255.0)
    gray[10:16, 10:230] = 0
    gray[116:122, 10:230] = 0
    gray[10:122, 10:16] = 0
    gray[10:122, 224:230] = 0
    gray[10:122, 116:122] = 0
    return gray


def test_baseline_fills_each_room_from_its_seed() -> None:
    gray = drawn_rooms()
    labels = raster_rooms.baseline_regions(gray, [(60, 60), (170, 60)], np.zeros(gray.shape, bool))
    areas = np.bincount(labels.ravel(), minlength=3)
    assert areas[1] == pytest.approx(100 * 100, rel=0.02)
    assert areas[2] == pytest.approx(102 * 100, rel=0.02)


def test_model_regions_sum_the_interior_probability() -> None:
    prob = np.zeros((140, 240, 4), np.float32)
    prob[16:116, 16:116, 0] = 1.0
    prob[16:116, 122:224, 0] = 1.0
    prob[16:20, 16:116, 0] = 0.5  # a soft edge band still counts by its probability
    _, areas, shared = raster_rooms.model_regions(prob, [(60, 60), (170, 60)])
    assert areas[0] == pytest.approx(100 * 100 - 4 * 100 * 0.5)
    assert areas[1] == pytest.approx(102 * 100)
    assert shared == [1, 1]


def test_a_shared_core_is_split_by_the_baseline() -> None:
    prob = np.zeros((140, 240, 4), np.float32)
    prob[16:116, 16:224, 0] = 1.0  # one open room for two numbers
    split = np.zeros((140, 240), np.int32)
    split[16:116, 16:100] = 1
    split[16:116, 140:224] = 2
    _, areas, shared = raster_rooms.model_regions(prob, [(60, 60), (170, 60)], split)
    assert shared == [2, 2]
    assert sum(areas) == pytest.approx(208 * 100)
    assert areas[0] == pytest.approx(104 * 100, rel=0.02)


@pytest.mark.parametrize(
    ("args", "want"),
    [
        ((10.0, 10.1, 10.02, 1), (10.02, "printed", "high")),
        ((10.0, 10.1, None, 1), (10.0, "model", "high")),
        ((10.0, 10.1, None, 2), (10.0, "model", "medium")),
        ((10.0, 9.2, None, 1), (10.0, "model", "medium")),
        ((10.0, 5.0, None, 1), (10.0, "model", "low")),
        ((None, 5.0, None, 0), (5.0, "baseline", "low")),
        ((None, None, None, 0), (None, "none", "none")),
    ],
)
def test_confidence_rule(args: tuple, want: tuple) -> None:
    assert raster_rooms._confidence(*args) == want


@pytest.mark.parametrize(
    ("label", "want"), [("Balkon", True), ("Loggia", True), ("Terrasse", True), ("Balcon", True), ("Bad", False)]
)
def test_outdoor_labels(label: str, want: bool) -> None:
    assert raster_rooms.is_outdoor_label(label) is want


# ----------------------------------------------------------------------------- agent tools


def test_raster_tools_skip_other_files(tmp_path: object) -> None:
    assert raster_tools.raster_tools("plan.pdf") is None
    assert raster_tools.raster_tools("model.ifc") is None
    del tmp_path


def test_no_scale_plan_says_areas_cannot_be_given() -> None:
    rgb = np.repeat(drawn_rooms()[..., None], 3, axis=2).astype(np.uint8)
    lines = [line("OH", 60, 60), line("KH", 170, 60)]
    plan = raster_rooms.read_plan(rgb, lines, use_model=False)
    assert plan.scale is None
    context, tools = raster_tools.plan_tools(plan, rgb, lines)
    assert "no scale" in context.lower()
    assert [t.name for t in tools] == ["list_rooms"]
    rooms = tools[0].run({}).data["rooms"]
    assert [r["label"] for r in rooms] == ["OH", "KH"]
    assert all(r["area_m2"] is None for r in rooms)
    assert rooms[0]["relative_area_share"] == pytest.approx(0.5, abs=0.02)


def test_scaled_plan_lists_rooms_and_apartments() -> None:
    scale = raster_scale.RasterScale(
        ppm=raster_rooms.CANON_PPM, source="both", agree=True, difference=0.0005, bar=None, text=None, evidence=()
    )
    room = raster_rooms.Room(
        number="1.01", label="Zimmer", area_m2=12.5, area_source="model", area_confidence="high", model_area_m2=12.5,
        baseline_area_m2=12.4, printed_area_m2=None, apartment="A", outdoor=False, at=(1.0, 1.0), polygon=(),
    )  # fmt: skip
    balcony = room.model_copy(update={"number": "1.02", "label": "Balkon", "area_m2": 4.0, "outdoor": True})
    plan = RasterPlan(
        width=10, height=10, scale=scale, factor=1.0, rooms=(room, balcony),
        apartments=(raster_rooms.Apartment(letter="A", at=(0.0, 0.0), unit=1),), texts=3, model_used=True,
        plan_like=True, reasons=(),
    )  # fmt: skip
    context, tools = raster_tools.plan_tools(plan, np.zeros((10, 10, 3), np.uint8), [])
    assert "confirmed" in context
    by_name = {t.name: t for t in tools}
    assert by_name["list_rooms"].run({}).data["rooms"][0]["area_confidence"] == "high"
    flats = by_name["list_apartments"].run({}).data["apartments"]
    assert flats == [{"letter": "A", "living_area_m2": 12.5, "rooms": ["1.01", "1.02"], "warnings": [],
                     "entity_id": "apartment:A"}]  # fmt: skip
