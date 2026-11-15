"""Tests of the Swiss Dwellings PDF tools and the thin solver, on small PDFs made here."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pymupdf
import pytest

from bp.contract import MissingReason, Question
from bp.solvers.swiss import SwissSolver, parse_question, quoted_label
from bp.tools import swiss_plan as sp
from bp.tools.pdf_text import is_pdf, page_count, read_page

if TYPE_CHECKING:
    from pathlib import Path

GREY = (0.54, 0.54, 0.54)
M_PER_PT = 0.0254 / 72 * 100  # 1:100


def _room(page: pymupdf.Page, rect: pymupdf.Rect, fill: tuple[float, float, float] = (1, 1, 1)) -> None:
    shape = page.new_shape()
    shape.draw_rect(rect)
    shape.finish(color=GREY, fill=fill, width=0.3685)
    shape.commit()


def _centred(page: pymupdf.Page, x: float, y: float, text: str) -> None:
    width = pymupdf.get_text_length(text, fontname="helv", fontsize=6)
    page.insert_text((x - width / 2, y), text, fontsize=6, fontname="helv")


def _sheet(path: Path, *, hole: bool = False, printed: bool = False) -> Path:
    """A one-room sheet in the style of the generator, at 1:100."""
    doc = pymupdf.open()
    page = doc.new_page(width=1190.55, height=841.89)
    room = pymupdf.Rect(100, 100, 300, 200)  # 200 x 100 pt
    if hole:  # one path: the room ring and a reversed inner ring, filled and stroked (operator B)
        h = page.rect.height
        stream = (
            f"q 0.54 G 1 g 0.3685 w 100 {h - 100} m 300 {h - 100} l 300 {h - 200} l 100 {h - 200} l h "
            f"150 {h - 130} m 150 {h - 150} l 170 {h - 150} l 170 {h - 130} l h B Q"
        ).encode()
        xref = doc.get_new_xref()
        doc.update_object(xref, "<<>>")
        doc.update_stream(xref, stream)
        refs = " ".join(f"{x} 0 R" for x in page.get_contents())
        doc.xref_set_key(page.xref, "Contents", f"[{refs} {xref} 0 R]")
    else:
        _room(page, room)
    _room(page, pymupdf.Rect(300, 100, 400, 200), fill=(0.89, 0.89, 0.89))  # an outdoor room without a label
    _centred(page, 200, 160, "Bad")  # the label sits centred above the number
    _centred(page, 200, 170, "1.01")
    _centred(page, 350, 170, "1.02")
    if printed:
        _centred(page, 200, 178, "24.89 m²")
    unit = page.new_shape()
    unit.draw_rect(pymupdf.Rect(95, 95, 405, 205))
    unit.finish(color=(0.69, 0.23, 0.18), width=1.276)
    unit.commit()
    page.insert_text((120, 120), "Whg. A", fontsize=6)
    door = page.new_shape()
    door.draw_quad(pymupdf.Rect(250, 198, 260, 202).quad)
    door.finish(color=(0.27, 0.27, 0.27), width=0.3685)
    door.commit()
    page.insert_text((900, 760), "1:100 (A3)", fontsize=7)
    path = path / "sheet.pdf"
    doc.save(path)
    return path


def test_parser_reads_every_family_in_four_languages() -> None:
    cases = {
        "How many rooms labelled 'Cage d'escalier' are there on this floor?": ("count_label", "Cage d'escalier"),
        "Combien de pièces portant la désignation « Cage d'escalier » y a-t-il à cet étage ?": (
            "count_label", "Cage d'escalier"),
        "Wie viele Wohnungen sind auf diesem Grundriss dargestellt?": ("apartments", None),
        "Combien de portes (portes intérieures et portes d'entrée confondues) sont dessinées sur ce plan ?": (
            "doors", None),
        "Quante finestre sono disegnate in questa pianta?": ("windows", None),
        "Wie viele WCs sind auf diesem Grundriss eingezeichnet?": ("toilets", None),
        "How many washbasins are drawn on this floor plan?": ("washbasins", None),
        "Quante vasche da bagno sono disegnate in questa pianta?": ("bathtubs", None),
        "Combien de douches sont dessinées sur ce plan ?": ("showers", None),
        "Quelle est la surface nette de la pièce U2.07 (« Couloir ») en m² ?": ("area_room", "Couloir"),
        "Qual è la superficie netta totale in m² di tutti i locali denominati «Vano scala» in questo piano?": (
            "area_label", "Vano scala"),
        "Wie gross ist die gesamte Nettogeschossfläche in m² aller nummerierten Innenräume dieses Geschosses?": (
            "area_total", None),
        "Quelle est la surface nette de l'appartement C en m² (somme de toutes ses pièces) ?": (
            "area_apartment", None),
    }  # fmt: skip
    for text, (intent, label) in cases.items():
        parsed = parse_question(text)
        assert not isinstance(parsed, str), text
        assert parsed.intent == intent, text
        assert parsed.label == label, text
    room = parse_question("Quelle est la surface nette de la pièce U2.07 (« Couloir ») en m² ?")
    assert not isinstance(room, str)
    assert room.room == "U2.07"
    apartment = parse_question("Quelle est la surface nette de l'appartement C en m² ?")
    assert not isinstance(apartment, str)
    assert apartment.apartment == "C"


def test_parser_refuses_what_it_cannot_place() -> None:
    assert isinstance(parse_question("What is the ceiling height?"), str)
    assert isinstance(parse_question("How many rooms are there?"), str)
    assert quoted_label("Wie viele Räume mit der Bezeichnung «Zimmer» gibt es?") == "Zimmer"


def test_tool_reads_rooms_scale_units_and_doors(tmp_path: Path) -> None:
    path = _sheet(tmp_path, printed=True)
    page = read_page(path)
    assert sp.detect(page).is_plan
    plan = sp.compile_plan(page)
    assert plan.scale is not None
    assert plan.scale.ratio == 100
    room = sp.room(plan, "1.01")
    assert room is not None
    assert room.label == "Bad"
    assert room.area_m2 == pytest.approx(200 * 100 * M_PER_PT**2, rel=1e-3)
    assert room.printed_area_m2 == pytest.approx(24.89)
    assert not room.print_mismatch
    assert room.apartment == "A"
    outdoor = sp.room(plan, "1.02")
    assert outdoor is not None
    assert outdoor.outdoor
    total = sp.total_area(plan)
    assert total.value == pytest.approx(room.area_m2, abs=0.01)
    assert not total.warnings
    assert sp.door_count(plan).value == 1
    assert sp.apartment_count(plan).value == 1


def test_a_reversed_inner_ring_is_a_hole(tmp_path: Path) -> None:
    plan = sp.compile_plan(read_page(_sheet(tmp_path, hole=True)))
    room = sp.room(plan, "1.01")
    assert room is not None
    assert room.area_m2 == pytest.approx((200 * 100 - 20 * 20) * M_PER_PT**2, rel=1e-3)


def test_fixture_classes() -> None:
    assert sp.classify_fixture("L1w0.51+L47w0.51", 1, 0) == "toilet"
    assert sp.classify_fixture("C0.030+L47w0.51", 1, 0) == "washbasin"
    assert sp.classify_fixture("C0.025+C0.032+L47w0.51+L68w0.51", 1, 0) == "bathtub"
    assert sp.classify_fixture("C0.025", 1, 0) == "bathtub"
    assert sp.classify_fixture("C0.045+Q", 1, 0) == "shower"
    assert sp.classify_fixture("C0.035+C0.080+C0.080+C0.080+C0.080+L47w0.51", 1, 0) == "kitchen"
    assert sp.classify_fixture("L1w0.37+L1w0.37", 1, 2) == "window"


def test_solver_answers_on_a_sheet(tmp_path: Path) -> None:
    solver = SwissSolver()
    assert solver.ingest(str(_sheet(tmp_path))).ok
    record = solver.ask(Question(qid="q", text="What is the net floor area of room 1.01 ('Bad') in m²?"))
    assert record.status == "answered"
    assert record.value == pytest.approx(200 * 100 * M_PER_PT**2, rel=1e-3)
    wrong_label = solver.ask(Question(qid="q", text="What is the net floor area of room 1.01 ('Reduit') in m²?"))
    assert wrong_label.status == "abstained"
    missing = solver.ask(Question(qid="q", text="What is the net floor area of room 9.99 ('Bad') in m²?"))
    assert missing.status == "abstained"
    absent = solver.ask(Question(qid="q", text="How many rooms labelled 'Sauna' are there on this floor?"))
    assert absent.status == "abstained"


def test_solver_abstains_on_other_documents(tmp_path: Path) -> None:
    text = tmp_path / "notes.pdf"
    text.write_text("not a pdf at all")
    assert not is_pdf(text)
    assert page_count(text) == 0
    plain = tmp_path / "plain.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Room 1.01 is 20 m2. Scale 1:50", fontsize=11)
    doc.save(plain)
    for path in (text, plain, tmp_path / "missing.ifc"):
        solver = SwissSolver()
        report = solver.ingest(str(path))
        assert report.ok  # a failed ingest would turn every question into an error
        record = solver.ask(Question(qid="q", text="How many doors are drawn on this floor plan?"))
        assert record.status == "abstained"
        assert record.abstain is not None
        assert record.abstain.reason is MissingReason.UNSUPPORTED
