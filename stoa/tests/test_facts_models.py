"""Facts of IFC and DXF files made here (no dataset), and the ids that the agent tool rows share with them."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import ezdxf
import ifcopenshell
import ifcopenshell.api
import numpy as np
import pytest

from bp import facts_models
from bp.contract import Calibration
from bp.solvers import raster_tools
from bp.solvers.agent import dxf_tools, model_tools
from bp.tools import dxf_plan, ifc_model
from bp.tools.raster_rooms import RasterPlan

if TYPE_CHECKING:
    from pathlib import Path

    from bp.facts import DocumentFacts, Entity, Fact


def _run(api: str, model: ifcopenshell.file | None = None, **kwargs: Any) -> Any:
    return ifcopenshell.api.run(api, model, **kwargs)


@pytest.fixture(scope="module")
def ifc_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Two storeys; two spaces share the name "Bath", and one has only a LongName."""
    model = _run("project.create_file", version="IFC4")
    project = _run("root.create_entity", model, ifc_class="IfcProject", name="Test")
    _run("unit.assign_unit", model)
    building = _run("root.create_entity", model, ifc_class="IfcBuilding", name="House")
    ground = _run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Ground")
    upper = _run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Upper")
    _run("aggregate.assign_object", model, products=[building], relating_object=project)
    _run("aggregate.assign_object", model, products=[ground, upper], relating_object=building)
    spaces = []
    for name, long_name, storey, area in [("0.01", "Kitchen", ground, 12.5), ("Bath", "", ground, 4.0),
                                          ("Bath", "", upper, 4.5), ("", "Hall", upper, None)]:  # fmt: skip
        space = _run("root.create_entity", model, ifc_class="IfcSpace", name=name or None)
        space.LongName = long_name or None
        _run("aggregate.assign_object", model, products=[space], relating_object=storey)
        if area is not None:
            qto = _run("pset.add_qto", model, product=space, name="Qto_SpaceBaseQuantities")
            _run("pset.edit_qto", model, qto=qto, properties={"NetFloorArea": area, "Height": 2500.0})
        spaces.append(space)
    door = _run("root.create_entity", model, ifc_class="IfcDoor", name="D1")
    window = _run("root.create_entity", model, ifc_class="IfcWindow", name="W1")
    _run("spatial.assign_container", model, products=[door, window], relating_structure=ground)
    path = tmp_path_factory.mktemp("ifc") / "model.ifc"
    model.write(str(path))
    return path


def _by_id(found: DocumentFacts) -> dict[str, Entity]:
    return {e.id: e for e in found.entities}


def _fact(entity: Entity, key: str) -> Fact:
    return next(f for f in entity.facts if f.key == key)


def test_ifc_space_ids_follow_the_name(ifc_path: Path) -> None:
    model = ifc_model.open_model(str(ifc_path))
    ids = sorted(ifc_model.space_ids(model).values())
    assert ids[0] == "space:0.01"
    assert sum(1 for i in ids if i.startswith("space:Bath@")) == 2  # a repeated name gets the GlobalId
    assert "space:Hall" in ids  # the LongName when the Name is empty


def test_ifc_facts(ifc_path: Path) -> None:
    found = facts_models.model_facts(ifc_path)
    assert found is not None
    assert found.kind == "ifc"
    entities = _by_id(found)
    kitchen = entities["space:0.01"]
    assert kitchen.kind == "room"
    assert kitchen.group == "space"
    assert kitchen.label == "0.01"
    area = _fact(kitchen, "area")
    assert area.value == 12.5
    assert area.unit == "m2"
    assert area.confidence == facts_models.IFC_AREA.confidence
    assert area.basis
    assert _fact(kitchen, "long_name").value == "Kitchen"
    assert _fact(kitchen, "storey").value == "Ground"
    assert _fact(kitchen, "height").confidence == 0.5  # no benchmark covers heights
    hall = entities["space:Hall"]
    assert _fact(hall, "area").status == "unknown"
    assert _fact(hall, "area").confidence == 0.0
    ground = entities["storey:Ground"]
    assert ground.kind == "storey"
    ground_spaces = {e.id for e in found.entities if e.kind == "room" and _fact(e, "storey").value == "Ground"}
    assert set(ground.members) == ground_spaces
    assert len(ground_spaces) == 2
    assert _fact(ground, "doors").value == 1
    assert any(i.startswith("door:") for i in entities)
    assert any(i.startswith("window:") for i in entities)
    summary = {f.key: f.value for f in found.summary}
    assert summary["doors"] == 1
    assert summary["spaces"] == 4
    assert summary["net_floor_area"] == 21.0
    assert found.unknown == ("1 spaces have no area in the model.",)


def test_ifc_rows_link_to_the_facts(ifc_path: Path) -> None:
    model = ifc_model.open_model(str(ifc_path))
    _, tools = model_tools(model)
    rows = next(t for t in tools if t.name == "list_spaces").run({"storey": ""}).data["spaces"]
    found = facts_models.model_facts(ifc_path)
    assert found is not None
    assert {r["entity_id"] for r in rows} <= set(_by_id(found))
    assert len({r["entity_id"] for r in rows}) == 4


@pytest.fixture(scope="module")
def dxf_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Two rooms in metres inside apartment A, one door between them, a window and a title text."""
    document = ezdxf.new()
    document.header["$INSUNITS"] = 6
    space = document.modelspace()
    for layer, points in [
        ("ROOM_OUTLINE", [(0, 0), (4, 0), (4, 3), (0, 3)]),
        ("ROOM_OUTLINE", [(4, 0), (6, 0), (6, 3), (4, 3)]),
        ("UNIT_OUTLINE", [(-0.1, -0.1), (6.1, -0.1), (6.1, 3.1), (-0.1, 3.1)]),
        ("DOOR", [(3.98, 1), (4.02, 1), (4.02, 1.9), (3.98, 1.9)]),
        ("WINDOW", [(1, -0.02), (2, -0.02), (2, 0.02), (1, 0.02)]),
    ]:
        space.add_lwpolyline(points, close=True, dxfattribs={"layer": layer})
    for text, at in [("1.01", (1, 1.5)), ("Zimmer", (1, 2)), ("12.00 m2", (1, 1)), ("1.02", (5, 1.5)),
                     ("Bad", (5, 2)), ("Whg. A", (3, 2.5)), ("Plan 1", (0, 5))]:  # fmt: skip
        space.add_text(text, dxfattribs={"insert": at, "layer": "TEXT"})
    path = tmp_path_factory.mktemp("dxf") / "plan.dxf"
    document.saveas(path)
    return path


def test_dxf_room_ids() -> None:
    room = dxf_plan.DxfRoom(number="1.01", label=None, printed_area_m2=None, area_m2=1.0, unit=None, outdoor=False,
                            windows=0, doors=0, points=())  # fmt: skip
    plan = dxf_plan.DxfPlan(unit_m=1.0, layers={}, rooms=(room, room, room.model_copy(update={"number": None})),
                            units=(), texts_outside_rooms=())  # fmt: skip
    assert dxf_plan.room_ids(plan) == ["room:outline:0", "room:outline:1", "room:outline:2"]


def test_dxf_facts(dxf_path: Path) -> None:
    found = facts_models.dxf_facts(dxf_path)
    assert found is not None
    assert found.kind == "dxf"
    entities = _by_id(found)
    room = entities["room:1.01"]
    assert room.label == "Zimmer 1.01"
    assert room.geometry == "polygon"
    assert _fact(room, "area").value == 12.0
    assert _fact(room, "printed_area").value == 12.0
    assert _fact(room, "apartment").value == "A"
    assert _fact(room, "doors").value == 1
    assert _fact(room, "windows").value == 1
    # metres from the top left corner, Y down: the drawing spans x -0.1 (the apartment) and y 5 (the title text)
    assert (0.1, 5.0) in room.points
    assert entities["apartment:A"].members == ("room:1.01", "room:1.02")
    assert "door:1" in entities
    assert "window:1" in entities
    labels = [e for e in found.entities if e.kind == "label"]
    assert [e.label for e in labels] == ["Plan 1"]
    assert labels[0].id == "label:0.1:0"
    summary = {f.key: f.value for f in found.summary}
    assert summary == {"rooms": 2, "apartments": 1, "doors": 1, "windows": 1, "net_floor_area": 18.0,
                       "outdoor_area": 0.0}  # fmt: skip
    assert found.pages[0].unit == "m"


def test_dxf_rows_link_to_the_facts(dxf_path: Path) -> None:
    _, tools = dxf_tools(dxf_plan.read_dxf(dxf_path))
    rows = next(t for t in tools if t.name == "list_rooms").run({}).data["rooms"]
    found = facts_models.dxf_facts(dxf_path)
    assert found is not None
    assert [r["entity_id"] for r in rows] == ["room:1.01", "room:1.02"]
    assert {r["entity_id"] for r in rows} <= set(_by_id(found))


def test_other_files_are_not_mine(dxf_path: Path, ifc_path: Path) -> None:
    assert facts_models.model_facts(dxf_path) is None
    assert facts_models.dxf_facts(ifc_path) is None
    assert facts_models.raster_facts(ifc_path) is None


def test_raster_ids() -> None:
    assert raster_tools.text_room_id([12, 30]) == "room:12:30"
    assert raster_tools.marked_room_id("bedroom", [0, 0, 11, 20]) == "room:bedroom:6:10"
    assert raster_tools.apartment_id("B") == "apartment:B"


def _raster_plan(ppm: float, source: str) -> RasterPlan:
    scale = raster_tools._scale(ppm, source)
    return RasterPlan(width=100, height=100, scale=scale, factor=1.0, rooms=(), apartments=(), texts=0,
                      model_used=False, plan_like=False, reasons=())  # fmt: skip


def test_user_scale_on_a_small_raster() -> None:
    two_points = Calibration(points=((10.0, 10.0), (10.0, 130.0)), real_length_m=2.0)
    assert raster_tools.user_ppm(two_points) == 60.0
    # A ratio alone gives no scale: an image has no paper size.
    assert raster_tools.user_ppm(Calibration(scale_ratio=100.0)) is None
    assert raster_tools.user_ppm(None) is None
    entity = facts_models._scale_entity(_raster_plan(60.0, "user"), two_points)
    assert entity is not None
    assert (entity.id, entity.label, entity.geometry, entity.points) == ("scale", "Scale (user)", "line", two_points.points)
    assert (entity.facts[0].key, entity.facts[0].value, entity.facts[0].source) == ("px_per_metre", 60.0, "user")


def test_user_scale_against_the_scale_of_the_image() -> None:
    rgb = np.zeros((100, 100, 3), np.uint8)
    own = raster_tools._scale(50.0, "bar")

    def small(ppm: float) -> raster_tools.SmallRaster:
        return raster_tools.SmallRaster(rgb=rgb, lines=[], plan=_raster_plan(ppm, "user"), detector=None, measured=own)

    assert facts_models._user_scale_conflict(small(51.0)) == ()
    (conflict,) = facts_models._user_scale_conflict(small(60.0))
    assert conflict.id == "scale:user"
    assert conflict.all_measured
    assert "60.0 px/m" in conflict.text
    assert "50.0 px/m" in conflict.text
