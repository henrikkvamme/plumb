"""The text functions for large drawing sheets, on hand-made OCR lines."""

from __future__ import annotations

import numpy as np

from bp.solvers import drawing_sheet
from bp.tools import sheet_geometry, sheet_text
from bp.tools.ocr import TextLine


def line(text: str, x: float, y: float, height: float = 30.0) -> TextLine:
    width = 0.6 * height * len(text)
    box = ((x - width / 2, y), (x + width / 2, y), (x + width / 2, y + height), (x - width / 2, y + height))
    return TextLine(text=text, box=box, score=0.99)


LINES = [
    line("645 SF", 1000, 960),
    line("MECHANICAL", 1000, 1000),
    line("ROOM", 1000, 1034),
    line("Store", 3000, 1000),
    line("Secure Store", 3000, 2000),
    line("Store", 5000, 1000),
    line("Stair", 7000, 1000, 40),
    line("(Upper)", 7000, 1036, 50),
    line("OFFICE/", 8000, 1000),
    line("CLOSET", 8000, 1034),
    line("PS-1 AND PS-2", 4000, 4000),
    line("PS-2", 4500, 4500),
    line('SCALE: 1/4" = 1\'-0"', 6000, 6000),
]


def test_stacked_lines_are_one_label_and_a_quantity_stays_apart() -> None:
    texts = {lb.text for lb in sheet_text.labels(LINES)}
    assert "MECHANICAL ROOM" in texts
    assert "645 SF" in texts
    assert "Stair (Upper)" in texts
    assert len(sheet_text.find(sheet_text.labels(LINES), "office/closet", "exact")) == 1


def test_exact_match_does_not_count_a_longer_label() -> None:
    labels = sheet_text.labels(LINES)
    assert len(sheet_text.find(labels, "store", "exact")) == 2
    assert len(sheet_text.find(labels, "store", "contains")) == 3
    assert len(sheet_text.find(labels, r"^secure", "regex")) == 1


def test_the_printed_area_is_near_its_room_name() -> None:
    labels = sheet_text.labels(LINES)
    room = sheet_text.find(labels, "mechanical room", "exact")[0]
    assert sheet_text.near(labels, room)[0].text == "645 SF"


def test_tags_count_once() -> None:
    assert sorted(sheet_text.tags(LINES, "PS")) == ["PS-1", "PS-2"]
    assert sheet_text.tags(LINES, "ps-")["PS-2"] == [(4000, 4015), (4500, 4515)]


def test_scales_imperial_and_metric() -> None:
    assert [s.ratio for s in sheet_text.printed_scales(LINES)] == [48]
    more = [
        line('1" = 40\'-0"', 0, 0),
        line("Scale 1:200 @ A0", 0, 100),
        line("1:200", 0, 200),
        line("MIX 1:2:4", 0, 300),
        line("SCALE:1:50", 0, 400),
    ]
    assert [(s.ratio, s.count) for s in sheet_text.printed_scales(more)] == [(200, 2), (50, 1), (480, 1)]


def test_feet_and_inches() -> None:
    assert sheet_text.feet_inches_m("12'-6\"") == 3.81
    assert round(sheet_text.feet_inches_m("8'-10 1/2\"") or 0, 4) == 2.7051
    assert sheet_text.feet_inches_m("645 SF") is None


def test_the_agent_tools_answer_from_the_lines() -> None:
    context, tools = drawing_sheet.sheet_tools(np.zeros((7000, 10000, 3), np.uint8), LINES)
    by_name = {t.name: t for t in tools}
    assert "10000 x 7000" in context
    found = by_name["find_text"].run({"query": "Mechanical Room", "match": "exact"}).data
    assert found["count"] == 1
    assert found["matches"][0]["near"][0] == {
        "entity_id": "label:1000:975", "text": "645 SF", "at_px": [1000, 975], "value": 645.0, "side": "above", "gap": 0.3,
    }  # fmt: skip
    assert by_name["list_tags"].run({"prefix": "PS"}).data["different_tags"] == 2
    assert by_name["read_scales"].run({}).data["scales"][0]["scale"] == "1:48"
    region = by_name["read_region"].run({"x0": 0, "y0": 900, "x1": 2000, "y1": 1100}).data
    assert [t["text"] for t in region["texts"]] == ["645 SF", "MECHANICAL ROOM"]
    assert by_name["length_to_m"].run({"text": "40'-0\""}).data["metres"] == 12.192


def _plan() -> tuple[np.ndarray, list[TextLine]]:
    """A 6000 x 4000 sheet at 50 px per metre: a green zone of 40 x 20 m, its legend swatch, three dimensions."""
    rgb = np.full((4000, 6000, 3), 255, np.uint8)
    rgb[1000:2000, 1000:3000] = (156, 185, 151)
    rgb[1000:2000, 1996:2000] = 0  # a partition inside the zone
    rgb[300:400, 300:450] = (156, 185, 151)  # the legend swatch
    lines = [line("DORMITORY", 700, 335)]
    for x0, x1, y, text in ((1000, 3000, 800, "40000"), (1000, 2000, 600, "20000"), (2000, 3000, 600, "20000")):
        rgb[y : y + 3, x0:x1] = 0
        rgb[y - 25 : y + 28, x0 : x0 + 3] = 0
        rgb[y - 25 : y + 28, x1 - 3 : x1] = 0
        lines.append(line(text, (x0 + x1) // 2, y - 40))
    return rgb, lines


def test_scale_from_dimension_lines_and_zone_area() -> None:
    rgb, lines = _plan()
    scale = sheet_geometry.dimension_scale(rgb, lines)
    assert scale is not None
    assert scale.agreeing == 3
    assert abs(scale.ppm - 50) < 0.5
    zones = sheet_geometry.colour_zones(rgb, sheet_text.labels(lines), scale.ppm)
    assert [(z.colour, z.legend) for z in zones] == [("green", "DORMITORY")]
    assert abs(zones[0].area_px / scale.ppm**2 - 800) < 12


def test_two_dimensions_are_not_a_scale() -> None:
    rgb, lines = _plan()
    assert sheet_geometry.dimension_scale(rgb, lines[:3]) is None


def test_a_scale_bar_and_one_dimension_are_a_scale() -> None:
    rgb, lines = _plan()
    bar = [
        line(text, 4000 + 50 * 0.3048 * feet, 3500) for text, feet in (("0", 0), ("15'", 15), ("30'", 30), ("60'", 60))
    ]
    assert abs(sheet_geometry.scale_bars(bar)[0].ppm - 50) < 0.5
    scale = sheet_geometry.dimension_scale(rgb, [*lines[:2], *bar])
    assert scale is not None
    assert abs(scale.ppm - 50) < 0.5
    assert sheet_geometry.dimension_scale(rgb, bar) is None  # a bar alone is not enough
    assert sheet_geometry.scale_bars([line("0", 0, 0), line("15'", 300, 0), line("30'", 400, 0)]) == []


def test_feet_dimension_text() -> None:
    assert round(sheet_geometry.printed_length_m("130' - 0\"") or 0, 3) == 39.624
    assert sheet_geometry.printed_length_m("3600") == 3.6
    assert sheet_geometry.printed_length_m("A6") is None
