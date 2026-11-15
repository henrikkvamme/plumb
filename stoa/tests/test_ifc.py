"""Tests of the IFC tools and solver on small files made here (no dataset)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ifcopenshell
import ifcopenshell.api
import pymupdf
import pytest

from bp.contract import MissingReason, Question
from bp.solvers.ifc import IfcSolver, parse_question, plan_text
from bp.tools import ifc_model as im
from bp.tools import ifc_sheet as sh

if TYPE_CHECKING:
    from pathlib import Path

# ----------------------------------------------------------------------------- fixtures


def _qto(model: ifcopenshell.file, product: object, name: str, values: dict[str, float]) -> None:
    qto = ifcopenshell.api.run("pset.add_qto", model, product=product, name=name)
    ifcopenshell.api.run("pset.edit_qto", model, qto=qto, properties=values)


@pytest.fixture(scope="module")
def ifc_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    model = ifcopenshell.api.run("project.create_file", version="IFC4")
    project = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject", name="Test House")
    ifcopenshell.api.run("unit.assign_unit", model)
    site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    building = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding", name="House")
    ground = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Ground Floor")
    upper = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Upper Floor")
    ifcopenshell.api.run("aggregate.assign_object", model, products=[site], relating_object=project)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[building], relating_object=site)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[ground, upper], relating_object=building)
    kitchen = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSpace", name="0.01")
    kitchen.LongName = "Kitchen"
    hall = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSpace", name="1.01")
    hall.LongName = "Hall"
    ifcopenshell.api.run("aggregate.assign_object", model, products=[kitchen], relating_object=ground)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[hall], relating_object=upper)
    _qto(model, kitchen, "Qto_SpaceBaseQuantities", {"NetFloorArea": 12.5})
    _qto(model, hall, "Qto_SpaceBaseQuantities", {"NetFloorArea": 7.25})
    walls = [ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcWall", name=f"W{i}") for i in range(3)]
    ifcopenshell.api.run("spatial.assign_container", model, products=walls[:2], relating_structure=ground)
    ifcopenshell.api.run("spatial.assign_container", model, products=walls[2:], relating_structure=upper)
    for wall, (length, volume) in zip(walls, [(4000.0, 1.2), (5000.0, 1.5), (3000.0, 0.9)], strict=True):  # lengths in mm, the default unit
        _qto(model, wall, "Qto_WallBaseQuantities", {"Length": length, "NetVolume": volume})
    door = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcDoor", name="D1")
    ifcopenshell.api.run("spatial.assign_container", model, products=[door], relating_structure=ground)
    stair = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcStair", name="S1")
    part = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcStair", name="S1 part")
    ifcopenshell.api.run("spatial.assign_container", model, products=[stair], relating_structure=ground)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[part], relating_object=stair)
    path = tmp_path_factory.mktemp("ifc") / "model.ifc"
    model.write(str(path))
    return path


BLUE = (0.89, 0.93, 0.97)


@pytest.fixture(scope="module")
def pdf_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A sheet at 1:100 with a scale bar: 72 pt is 25.4 mm on paper, so 2.54 m in the building."""
    document = pymupdf.open()
    page = document.new_page(width=600, height=400)
    page.draw_rect(pymupdf.Rect(100, 100, 172, 136), color=None, fill=BLUE)  # 2.54 m x 1.27 m
    page.draw_rect(pymupdf.Rect(200, 100, 236, 136), color=None, fill=BLUE)  # 1.27 m x 1.27 m
    page.insert_text((120, 115), "Kitchen", fontsize=5)
    page.insert_text((125, 122), "0.01", fontsize=5)
    page.insert_text((205, 115), "Store", fontsize=5)
    page.insert_text((207, 122), "0.02", fontsize=5)
    page.insert_text((20, 340), "Test House - Floor plan: Ground Floor", fontsize=11)  # base-14 fonts lack the em dash
    page.insert_text((20, 360), "Scale 1:100", fontsize=7)
    x0 = 400.0
    x5 = x0 + 5.0 / (0.0254 / 72 * 100)  # 5 m at 1:100
    zero, five, unit = (pymupdf.get_text_length(t, fontsize=6) for t in ("0", "5", "m"))
    gap = 2.0
    start = x5 - (five + gap + unit) / 2  # the centre of "5 m" sits on the 5 m tick
    page.insert_text((x0 - zero / 2, 320), "0", fontsize=6)
    page.insert_text((start, 320), "5", fontsize=6)
    page.insert_text((start + five + gap, 320), "m", fontsize=6)
    path = tmp_path_factory.mktemp("pdf") / "sheet.pdf"
    document.save(str(path))
    return path


# ----------------------------------------------------------------------------- the question parser


@pytest.mark.parametrize(
    ("text", "family", "category"),
    [
        ("What is the net floor area of the room 'Kitchen (0.01)' on 'Ground Floor', in m²?", "area_room", "space"),
        ("Wie viele Türen sind im Grundriss „EG“ dargestellt?", "count_storey", "door"),
        ("¿Cuál es el número de locales en el plano de la planta «P0»?", "count_storey", "space"),
        ("Mitu treppi on mudelis „Maja“?", "count_model", "stair"),
        ("Hvad er det samlede nettovolumen af alle dæk og plader på '1. Sal' i m³?", "volume_slabs", "slab"),
        ("What is the total length of all walls on 'OG1', in metres?", "length_walls", "wall"),
        ("Wat is de totale netto zijoppervlakte van alle wanden op '0', in m²?", "area_wall_side", "wall"),
        ("What is the total net floor area of all rooms (spaces) on 'Level 2', in m²?", "area_total_storey", "space"),
        ("How many sanitary fixtures are there in the model 'X'?", "count_model", "sanitary"),
    ],
)
def test_parse_question(text: str, family: str, category: str) -> None:
    q = parse_question(text)
    assert q is not None
    assert (q.family, q.category) == (family, category)


def test_parse_free_text_is_none() -> None:
    assert parse_question("Which software was used to create this model?") is None
    plan = plan_text("Which software was used to create this model?")
    assert plan is not None
    assert plan.kind == "metadata"
    door_plan = plan_text("Which door types are installed, with their quantities?")
    assert door_plan is not None
    assert (door_plan.kind, door_plan.classes) == ("types", ("IfcDoor",))


# ----------------------------------------------------------------------------- ifc_model


def test_model_queries(ifc_path: Path) -> None:
    model = im.open_model(str(ifc_path))
    info = im.project_info(model)
    assert info.project_name == "Test House"
    assert [s.name for s in info.storeys] == ["Ground Floor", "Upper Floor"]
    assert im.count_elements(model, "wall").count == 3
    assert im.count_elements(model, "wall", "Ground Floor").count == 2
    assert im.count_elements(model, "stair").count == 1  # the stair part does not count
    kitchen = im.find_spaces(model, "Kitchen (0.01)", "Ground Floor")
    assert len(kitchen) == 1
    assert kitchen[0].net_floor_area_m2 == pytest.approx(12.5)
    assert kitchen[0].area_source == "qto"
    assert im.storey_space_area(model, "Upper Floor").value == pytest.approx(7.25)
    length = im.storey_quantity(model, "wall", "Length", "Ground Floor")
    assert length.value == pytest.approx(9.0)
    assert length.n_with_value == 2


def test_solver_on_ifc(ifc_path: Path) -> None:
    solver = IfcSolver()
    assert solver.ingest(str(ifc_path)).ok
    record = solver.ask(Question(qid="a", text="How many doors are shown on the floor plan of 'Ground Floor'?"))
    assert (record.status, record.value) == ("answered", 1)
    assert record.evidence
    assert record.evidence[0].kind == "ifc_element"
    missing = solver.ask(Question(qid="b", text="How many doors are shown on the floor plan of 'Roof'?"))
    assert missing.status == "abstained"
    assert missing.abstain is not None
    assert missing.abstain.reason is MissingReason.NOT_IN_MODEL
    area = solver.ask(Question(qid="c", text="What is the net floor area of the room 'Hall (1.01)' on 'Upper Floor', in m²?"))
    assert area.value == pytest.approx(7.25)


# ----------------------------------------------------------------------------- ifc_sheet


def test_sheet_facts(pdf_path: Path) -> None:
    sheet = sh.read_sheet(str(pdf_path))
    assert sheet.storey == "Ground Floor"
    assert sheet.project == "Test House"
    assert sheet.scale_ratio == 100
    assert sheet.scale_confirmed
    assert len(sheet.rooms) == 2
    found = sh.room_area(sheet, "Kitchen (0.01)")
    assert found.status == "found"
    assert found.area_m2 == pytest.approx(2.54 * 1.27, rel=0.02)
    assert sh.room_area(sheet, "Bath (0.09)").status == "no_label"


def test_solver_on_sheet(pdf_path: Path) -> None:
    solver = IfcSolver()
    solver.ingest(str(pdf_path))
    area = solver.ask(Question(qid="a", text="What is the net floor area of the room 'Store (0.02)' on 'Ground Floor', in m²?"))
    assert area.status == "answered"
    assert area.value == pytest.approx(1.27 * 1.27, rel=0.02)
    rooms = solver.ask(Question(qid="b", text="How many rooms (spaces) are shown on the floor plan of 'Ground Floor'?"))
    assert rooms.value == 2
    model_wide = solver.ask(Question(qid="c", text="How many doors are there in the model 'Test House'?"))
    assert model_wide.abstain is not None
    assert model_wide.abstain.reason is MissingReason.NOT_ON_DOCUMENT
    volume = solver.ask(Question(qid="d", text="What is the total net volume of all walls on 'Ground Floor', in m³?"))
    assert volume.abstain is not None
    assert volume.abstain.reason is MissingReason.NOT_ON_DOCUMENT
    other = solver.ask(Question(qid="e", text="What is the net floor area of the room 'Store (0.02)' on 'Attic', in m²?"))
    assert other.status == "abstained"


def test_solver_abstains_on_other_documents(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    path.write_text("not a drawing")
    solver = IfcSolver()
    solver.ingest(str(path))
    record = solver.ask(Question(qid="a", text="How many doors are there in the model 'X'?"))
    assert record.status == "abstained"
    assert record.abstain is not None
    assert record.abstain.reason is MissingReason.UNSUPPORTED
