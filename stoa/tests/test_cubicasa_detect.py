"""The CubiCasa detector path: question rules, views and merging, SVG label parsing, calibration, the solver."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from PIL import Image

from bp.contract import Question
from bp.solvers import cubicasa_detect as solver_module
from bp.solvers.cubicasa_detect import CubicasaDetectSolver, concept_of
from bp.toolbench.cubicasa_detect import boxes_from_svg, parse_transform, path_points, tune
from bp.tools.symbol_detector import (
    CLASSES,
    Detection,
    View,
    decode_yolo,
    dedupe,
    merge_views,
    nms,
    plan_views,
    render_view,
)

if TYPE_CHECKING:
    from pathlib import Path

TEMPLATES = {
    "windows": [
        "How many windows are shown on this floor plan?",
        "Kuinka monta ikkunaa pohjapiirustuksessa on?",
    ],
    "floors": [
        "How many floors (storeys) does this floor plan show?",
        "Kuinka monta kerrosta pohjapiirustuksessa on esitetty?",
    ],
    "toilets": [
        "How many toilet bowls (WC seats) are drawn on this floor plan?",
        "Kuinka monta WC-istuinta pohjapiirustukseen on piirretty?",
    ],
    "sinks": [
        "How many sinks and wash basins (kitchen and bathroom combined; a double-bowl sink counts as one) are drawn"
        " on this floor plan?",
        "Kuinka monta pesu- ja tiskiallasta (keittiö ja kylpytilat yhteensä; kaksoisallas lasketaan yhdeksi)"
        " pohjapiirustukseen on piirretty?",
    ],
    "showers_tubs": [
        "How many showers and bathtubs are drawn on this floor plan in total?",
        "Kuinka monta suihkua ja kylpyammetta pohjapiirustukseen on piirretty yhteensä?",
    ],
    "doors": [
        "How many doors are shown on this floor plan? Count doorways fitted with a door; open doorways without a"
        " door leaf do not count.",
        "Kuinka monta ovea pohjapiirustuksessa on? Laske oviaukot, joissa on ovi; pelkkiä oviaukkoja ilman"
        " ovilehteä ei lasketa.",
    ],
    "saunas": ["How many saunas are on this floor plan?", "Kuinka monta saunaa pohjapiirustuksessa on?"],
    "kitchens": [
        "How many kitchens (including kitchenettes, open kitchens and utility kitchens) are on this floor plan?",
        "Kuinka monta keittiötä (myös keittokomerot, avo- ja tupakeittiöt sekä apukeittiöt) pohjapiirustuksessa on?",
    ],
    "bedrooms": [
        "How many bedrooms (makuuhuone, usually marked MH) are on this floor plan?",
        "Kuinka monta makuuhuonetta (MH) pohjapiirustuksessa on?",
    ],
    "bathrooms": [
        "How many bathrooms or washrooms (e.g. KH, KPH, PH, PESUH, SH) are on this floor plan, not counting"
        " separate WC rooms?",
        "Kuinka monta kylpy- tai pesuhuonetta (esim. KH, KPH, PH, PESUH, SH) pohjapiirustuksessa on, erillisiä"
        " WC-tiloja lukuun ottamatta?",
    ],
    "wc_rooms": [
        "How many separate WC rooms (toilet rooms marked WC) are on this floor plan?",
        "Kuinka monta erillistä WC-tilaa pohjapiirustuksessa on?",
    ],
    "balconies": [
        "How many balconies (parveke, including glazed balconies) are on this floor plan?",
        "Kuinka monta parveketta (myös lasitetut parvekkeet) pohjapiirustuksessa on?",
    ],
}


@pytest.mark.parametrize(("concept", "text"), [(c, t) for c, texts in TEMPLATES.items() for t in texts])
def test_every_public_template_maps_to_its_concept(concept: str, text: str) -> None:
    assert concept_of(text) == concept


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("How many showers are drawn?", "showers"),
        ("Count the bathtubs on the plan", "bathtubs"),
        ("Montako makuuhuonetta asunnossa on?", "bedrooms"),
        ("How many rooms are there?", None),
        ("What is the area of the kitchen?", None),
        ("How many doors and windows are there?", None),
        ("Which scale is the drawing?", None),
    ],
)
def test_unseen_questions(text: str, expected: str | None) -> None:
    assert concept_of(text) == expected


def test_small_plan_has_one_global_view() -> None:
    views = plan_views(800, 600, 1024)
    assert len(views) == 1
    assert views[0].scale == pytest.approx(1024 / 800)


def test_large_plan_tiles_cover_every_point_once() -> None:
    views = plan_views(3000, 1800, 1024)
    tiles = [v for v in views if v.kind == "tile"]
    assert views[0].kind == "global"
    assert len(tiles) == 4 * 3  # ceil((3000 - 1024) / 768) + 1 = 4 columns, ceil((1800 - 1024) / 768) + 1 = 3 rows
    for x, y in [(0, 0), (1500, 900), (2999, 1799), (1023, 1023), (800, 1700)]:
        owners = [t for t in tiles if t.owns((x, y, x, y))]
        assert len(owners) == 1
        t = owners[0]
        assert t.x0 <= x < t.x0 + 1024
        assert t.y0 <= y < t.y0 + 1024


def test_view_round_trip_and_render() -> None:
    view = View("tile", 100.0, 50.0, 0.5, 64)
    box = (120.0, 70.0, 180.0, 130.0)
    assert view.to_original(view.to_view(box)) == pytest.approx(box)
    image = Image.new("RGBA", (300, 200), (0, 0, 0, 0))
    out = render_view(image.convert("RGB"), view)
    assert out.size == (64, 64)


def test_merge_takes_rooms_from_global_and_symbols_from_owning_tiles() -> None:
    g = View("global", 0, 0, 0.5, 1024)
    left = View("tile", 0, 0, 1.0, 1024, core=(-1e9, -1e9, 900, 1e9))
    right = View("tile", 776, 0, 1.0, 1024, core=(900, -1e9, 1e9, 1e9))
    door_left = Detection("door", 0.9, (850, 10, 890, 50))  # centre 870: the left tile owns it
    per_view = [
        (g, [Detection("door", 0.8, (850, 10, 890, 50)), Detection("kitchen", 0.7, (0, 0, 500, 500))]),
        (left, [door_left, Detection("kitchen", 0.9, (0, 0, 400, 400))]),
        (right, [Detection("door", 0.85, (851, 10, 891, 50))]),
    ]
    merged = merge_views(per_view)
    assert sorted(d.label for d in merged) == ["door", "kitchen"]
    assert next(d for d in merged if d.label == "kitchen").score == 0.7


def test_dedupe_keeps_separate_boxes() -> None:
    a = Detection("sink", 0.9, (0, 0, 10, 10))
    b = Detection("sink", 0.8, (1, 1, 9, 9))
    c = Detection("sink", 0.7, (20, 0, 30, 10))
    d = Detection("toilet", 0.6, (0, 0, 10, 10))
    assert dedupe([a, b, c, d]) == [a, c, d]


def test_svg_geometry_helpers() -> None:
    m = parse_transform("translate(10,20) matrix(2,0,0,2,1,1)")
    assert (m @ [1, 1, 1])[:2].tolist() == [13.0, 23.0]
    assert path_points("M10,10 q0,-5 -5,-5 l0,5Z") == [(10, 10), (10, 5), (5, 5), (5, 10)]


SVG = """<svg xmlns="http://www.w3.org/2000/svg"><defs><polygon points="0,0 999,999 0,999"/></defs>
<g class="Floorplan Floor-1">
 <g class="Space Bath"><polygon points="0,0 100,0 100,100 0,100"/>
   <g class="TextLabel NameLabel"><text>WC</text></g></g>
 <g class="Space Bath"><polygon points="100,0 200,0 200,100 100,100"/></g>
 <g class="Space Undefined"><polygon points="200,0 300,0 300,100 200,100"/></g>
 <g class="Wall"><polygon points="0,0 300,0 300,5 0,5"/>
   <g class="Door Swing Beside"><polygon points="10,0 40,0 40,5 10,5"/><path d="M40,0 q0,30 -30,30"/></g>
   <g class="Door None Beside"><polygon points="50,0 80,0 80,5 50,5"/></g>
   <g class="Window Regular"><polygon points="120,0 160,0 160,5 120,5"/></g></g>
 <g class="FixedFurniture Toilet" transform="matrix(1,0,0,1,20,20)"><g class="BoundaryPolygon">
   <polygon points="0,0 10,0 10,20 0,20"/></g></g>
 <g class="FixedFurniture DoubleSink" transform="translate(120,20)"><g class="BoundaryPolygon">
   <polygon points="0,0 30,0 30,10 0,10"/></g></g>
 <g class="FixedFurniture ElectricalAppliance SaunaStove" transform="translate(250,50)"><g class="BoundaryPolygon">
   <polygon points="0,0 10,0 10,10 0,10"/></g></g>
</g></svg>"""


def test_svg_labels_follow_the_count_rules() -> None:
    boxes = boxes_from_svg(SVG)
    labels = sorted(label for label, _ in boxes)
    assert labels == ["bathroom", "door", "doorway", "floorplan", "sauna", "sink", "toilet", "wc_room", "window"]
    box = dict(boxes)
    assert box["toilet"] == (20, 20, 30, 40)
    assert box["door"] == (10, 0, 40, 30)  # the swing arc is part of the door
    assert box["sauna"] == (200, 0, 300, 100)  # the room that holds the stove
    assert box["floorplan"] == (0, 0, 300, 100)  # defs do not stretch it


def test_tune_prefers_abstaining_near_the_threshold() -> None:
    sure = [([0.9, 0.9], None, 2)] * 20
    # Near 0.5 the count is 1 or 2, and either answer is wrong as often as right: abstaining scores more.
    unsure = [([0.9, 0.52], None, 1)] * 2 + [([0.9, 0.52], None, 2)] * 2 + [([0.9, 0.52], None, 5)] * 2
    rule = tune(sure + unsure)
    assert rule is not None
    assert rule["wrong"] == 0
    assert rule["right"] == 20


class _FakeDetector:
    meta: dict = {"calibration": {"doors": {"threshold": 0.5, "band": 0.1}}, "plan_min_score": 0.3}  # noqa: RUF012

    def __init__(self, dets: list[Detection]) -> None:
        self.dets = dets

    def detect(self, image: Image.Image) -> list[Detection]:
        del image
        return self.dets


def _solver(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, dets: list[Detection]) -> CubicasaDetectSolver:
    fake = _FakeDetector(dets)
    monkeypatch.setattr(solver_module.Detector, "get", classmethod(lambda _cls, _directory: fake))
    path = tmp_path / "doc-abc.png"
    Image.new("RGB", (400, 300), "white").save(path)
    solver = CubicasaDetectSolver()
    assert solver.ingest(str(path)).ok
    return solver


DOOR_Q = Question(qid="q1", text="How many doors are shown on this floor plan?")


def test_solver_counts_marks_with_evidence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dets = [Detection("door", 0.95, (0, 0, 10, 10)), Detection("door", 0.9, (20, 0, 30, 10)),
            Detection("door", 0.1, (40, 0, 50, 10)), Detection("window", 0.99, (0, 0, 5, 5))]  # fmt: skip
    record = _solver(monkeypatch, tmp_path, dets).ask(DOOR_Q)
    assert record.status == "answered"
    assert record.value == 2
    assert [e.points[0] for e in record.evidence] == [(5.0, 5.0), (25.0, 5.0)]


def test_solver_abstains_near_threshold(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dets = [Detection("door", 0.95, (0, 0, 10, 10)), Detection("door", 0.55, (20, 0, 30, 10))]
    record = _solver(monkeypatch, tmp_path, dets).ask(DOOR_Q)
    assert record.status == "abstained"
    assert record.best_estimate == 2


def test_solver_abstains_on_unknown_questions_and_blank_pages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    solver = _solver(monkeypatch, tmp_path, [Detection("door", 0.95, (0, 0, 10, 10))])
    assert solver.ask(Question(qid="q", text="What is the scale?")).status == "abstained"
    blank = _solver(monkeypatch, tmp_path, [])
    record = blank.ask(DOOR_Q)
    assert record.status == "abstained"
    assert record.abstain is not None
    assert record.abstain.reason == "not_a_drawing"


def test_solver_abstains_on_a_pdf(tmp_path: Path) -> None:
    path = tmp_path / "doc-x.pdf"
    path.write_bytes(b"%PDF-1.4")
    solver = CubicasaDetectSolver()
    assert solver.ingest(str(path)).ok
    assert solver.ask(DOOR_Q).status == "abstained"


def test_meta_round_trip(tmp_path: Path) -> None:
    meta = {"backend": "rfdetr", "resolution": 1024, "classes": ["door"]}
    (tmp_path / "meta.json").write_text(json.dumps(meta))
    assert json.loads((tmp_path / "meta.json").read_text())["backend"] == "rfdetr"


def test_tune_uses_the_mirror_when_it_flags_wrong_counts() -> None:
    sure = [([0.9], [0.9], 1)] * 20
    unstable = [([0.9, 0.9], [0.9], 1)] * 5  # an extra mark that the mirror does not see: the key agrees with it
    rule = tune(sure + unstable)
    assert rule is not None
    assert rule["mirror"] is True
    assert rule["wrong"] == 0


def test_nms_is_class_aware() -> None:
    import numpy as np  # noqa: PLC0415

    boxes = np.array([[0, 0, 10, 10], [1, 0, 11, 10], [0, 0, 10, 10], [50, 50, 60, 60]], dtype=float)
    scores = np.array([0.9, 0.8, 0.7, 0.6])
    labels = np.array([0, 0, 1, 0])
    assert nms(boxes, scores, labels, 0.5) == [0, 2, 3]


def test_decode_yolo_raw_head_runs_nms() -> None:
    import torch  # noqa: PLC0415

    raw = torch.zeros(1, 4 + len(CLASSES), 3)
    raw[0, :4, 0] = torch.tensor([20.0, 20.0, 10.0, 10.0])
    raw[0, :4, 1] = torch.tensor([21.0, 20.0, 10.0, 10.0])  # the same window, a lower score
    raw[0, :4, 2] = torch.tensor([200.0, 100.0, 20.0, 40.0])
    window, toilet = CLASSES.index("window"), CLASSES.index("toilet")
    raw[0, 4 + window, 0], raw[0, 4 + window, 1], raw[0, 4 + toilet, 2] = 0.9, 0.6, 0.8
    found = decode_yolo(raw, View("global", 0.0, 0.0, 0.5, 1024), CLASSES, 0.05)
    assert [(d.label, round(d.score, 2)) for d in found] == [("window", 0.9), ("toilet", 0.8)]
    assert found[0].box == pytest.approx((30.0, 30.0, 50.0, 50.0))  # view pixels / scale 0.5
