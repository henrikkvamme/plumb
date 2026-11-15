"""The count head's question rules, image preparation and the solver's abstentions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest
import torch
from PIL import Image

from bp.contract import MissingReason, Question
from bp.solvers.cubicasa_count import CubicasaCountSolver
from bp.tools.count_head import DEFAULT_ARTIFACT, STORE_SIDE, dihedral, family_of, letterbox, load_image

if TYPE_CHECKING:
    from pathlib import Path

# Public question texts of the 12 CubiCasa families, both languages.
QUESTIONS: dict[str, tuple[str, str]] = {
    "floors": (
        "How many floors (storeys) does this floor plan show?",
        "Kuinka monta kerrosta pohjapiirustuksessa on esitetty?",
    ),
    "windows": ("How many windows are shown on this floor plan?", "Kuinka monta ikkunaa pohjapiirustuksessa on?"),
    "toilets": (
        "How many toilet bowls (WC seats) are drawn on this floor plan?",
        "Kuinka monta WC-istuinta pohjapiirustukseen on piirretty?",
    ),
    "sinks": (
        "How many sinks and wash basins (kitchen and bathroom combined; a double-bowl sink counts as one) are drawn"
        " on this floor plan?",
        "Kuinka monta pesu- ja tiskiallasta (keittiö ja kylpytilat yhteensä; kaksoisallas lasketaan yhdeksi)"
        " pohjapiirustukseen on piirretty?",
    ),
    "showers_tubs": (
        "How many showers and bathtubs are drawn on this floor plan in total?",
        "Kuinka monta suihkua ja kylpyammetta pohjapiirustukseen on piirretty yhteensä?",
    ),
    "doors": (
        "How many doors are shown on this floor plan? Count doorways fitted with a door; open doorways without a"
        " door leaf do not count.",
        "Kuinka monta ovea pohjapiirustuksessa on? Laske oviaukot, joissa on ovi; pelkkiä oviaukkoja ilman"
        " ovilehteä ei lasketa.",
    ),
    "saunas": ("How many saunas are on this floor plan?", "Kuinka monta saunaa pohjapiirustuksessa on?"),
    "kitchens": (
        "How many kitchens (including kitchenettes, open kitchens and utility kitchens) are on this floor plan?",
        "Kuinka monta keittiötä (myös keittokomerot, avo- ja tupakeittiöt sekä apukeittiöt) pohjapiirustuksessa on?",
    ),
    "bedrooms": (
        "How many bedrooms (makuuhuone, usually marked MH) are on this floor plan?",
        "Kuinka monta makuuhuonetta (MH) pohjapiirustuksessa on?",
    ),
    "bathrooms": (
        "How many bathrooms or washrooms (e.g. KH, KPH, PH, PESUH, SH) are on this floor plan, not counting"
        " separate WC rooms?",
        "Kuinka monta kylpy- tai pesuhuonetta (esim. KH, KPH, PH, PESUH, SH) pohjapiirustuksessa on, erillisiä"
        " WC-tiloja lukuun ottamatta?",
    ),
    "wc_rooms": (
        "How many separate WC rooms (toilet rooms marked WC) are on this floor plan?",
        "Kuinka monta erillistä WC-tilaa pohjapiirustuksessa on?",
    ),
    "balconies": (
        "How many balconies (parveke, including glazed balconies) are on this floor plan?",
        "Kuinka monta parveketta (myös lasitetut parvekkeet) pohjapiirustuksessa on?",
    ),
}


@pytest.mark.parametrize("family", sorted(QUESTIONS))
def test_family_of_public_texts(family: str) -> None:
    english, finnish = QUESTIONS[family]
    assert family_of(english) == family
    assert family_of(finnish) == family


@pytest.mark.parametrize(
    ("text", "family"),
    [
        ("Count the windows on this plan.", "windows"),
        ("What is the number of doors in this drawing?", "doors"),
        ("Montako saunaa asunnossa on?", "saunas"),
        ("How many bedrooms does the apartment have?", "bedrooms"),
    ],
)
def test_family_of_paraphrases(text: str, family: str) -> None:
    assert family_of(text) == family


@pytest.mark.parametrize(
    "text",
    [
        "How many showers are drawn on this floor plan?",  # showers alone: not the showers + bathtubs family
        "How many washbasins are drawn on this floor plan?",  # basins alone: the CubiCasa count adds kitchen sinks
        "How many rooms labelled 'Küche' are there on this floor?",
        "What is the area of the kitchen in m2?",
        "On sheet A-801, how many doors are in the door schedule?",
        "Which room is the largest?",
        "How many apartments are shown on this floor plan?",
    ],
)
def test_family_of_refuses(text: str) -> None:
    assert family_of(text) is None


def test_dihedral_gives_eight_distinct_views() -> None:
    x = torch.arange(12, dtype=torch.float32).reshape(1, 3, 4)
    square = torch.arange(16, dtype=torch.float32).reshape(1, 4, 4)
    views = {tuple(dihedral(square, k).flatten().tolist()) for k in range(8)}
    assert len(views) == 8
    assert dihedral(x, 0).equal(x)
    assert sorted(dihedral(x, 5).flatten().tolist()) == sorted(x.flatten().tolist())


def test_letterbox_shape_and_white_padding() -> None:
    image = Image.new("RGB", (200, 100), (0, 0, 0))
    array = letterbox(image, 64)
    assert array.shape == (3, 64, 64)
    assert array.dtype == np.float32
    white = (1.0 - 0.485) / 0.229
    assert array[0, 0, 0] == pytest.approx(white, rel=1e-5)  # the top band is padding
    assert array[0, 32, 32] == pytest.approx(-0.485 / 0.229, rel=1e-5)  # the middle is the black plan


def test_load_image_caps_size_and_flattens_alpha(tmp_path: Path) -> None:
    path = tmp_path / "plan.png"
    Image.new("RGBA", (3000, 1500), (0, 0, 0, 0)).save(path)
    image = load_image(path)
    assert image.mode == "RGB"
    assert max(image.size) == STORE_SIDE
    assert image.getpixel((10, 10)) == (255, 255, 255)


def test_solver_abstains_on_pdf_without_loading_a_model(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    path.write_bytes(b"%PDF-1.4\n")
    solver = CubicasaCountSolver()
    assert solver.ingest(str(path)).ok
    record = solver.ask(Question(qid="q", text="How many windows are shown on this floor plan?"))
    assert record.status == "abstained"
    assert record.abstain is not None
    assert record.abstain.reason is MissingReason.UNSUPPORTED


def test_solver_abstains_on_unknown_question(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    path.write_bytes(b"%PDF-1.4\n")
    solver = CubicasaCountSolver()
    solver.ingest(str(path))
    record = solver.ask(Question(qid="q", text="What colour are the walls?"))
    assert record.status == "abstained"


@pytest.mark.skipif(not (DEFAULT_ARTIFACT / CubicasaCountSolver.spec).exists(), reason="no trained weights here")
def test_solver_answers_or_abstains_on_a_plan(tmp_path: Path) -> None:
    path = tmp_path / "doc.png"
    Image.new("RGB", (800, 600), (255, 255, 255)).save(path)
    solver = CubicasaCountSolver()
    assert solver.ingest(str(path)).ok
    record = solver.ask(Question(qid="q", text="How many windows are shown on this floor plan?"))
    assert record.status in {"answered", "abstained"}
    assert record.steps
    assert record.steps[0].tool == "count_head"
