"""MEP tools on a small IFC4 model made here (no dataset): kinds, storeys, systems, lengths and the sure flag."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import ifcopenshell
import ifcopenshell.api
import pytest

from bp.solvers.mep_tools import length_status, mep_tools
from bp.toolbench import mep_truth
from bp.tools import ifc_mep, ifc_model

if TYPE_CHECKING:
    from pathlib import Path


def _run(api: str, model: ifcopenshell.file | None = None, **kwargs: Any) -> Any:
    return ifcopenshell.api.run(api, model, **kwargs)


def _placement(model: ifcopenshell.file, x: float, y: float = 0.0, z: float = 0.0) -> Any:
    point = model.createIfcCartesianPoint((float(x), float(y), float(z)))
    return model.createIfcLocalPlacement(None, model.createIfcAxis2Placement3D(point, None, None))


def _ports(model: ifcopenshell.file, element: Any, xs: tuple[float, float]) -> None:
    ports = []
    for x in xs:
        port = _run("root.create_entity", model, ifc_class="IfcDistributionPort", name="Port")
        port.ObjectPlacement = _placement(model, x)
        ports.append(port)
    model.createIfcRelNests(ifcopenshell.guid.new(), None, None, None, element, ports)


@pytest.fixture(scope="module")
def ifc_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One storey in millimetres: a 2 m pipe with no stated length, a 3 m pipe with a quantity, a fitting, a valve."""
    model = _run("project.create_file", version="IFC4")
    project = _run("root.create_entity", model, ifc_class="IfcProject", name="Test")
    _run("unit.assign_unit", model)  # millimetres
    building = _run("root.create_entity", model, ifc_class="IfcBuilding", name="House")
    ground = _run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Ground")
    _run("aggregate.assign_object", model, products=[building], relating_object=project)
    _run("aggregate.assign_object", model, products=[ground], relating_object=building)
    short = _run("root.create_entity", model, ifc_class="IfcPipeSegment", name="Pipe A")
    long = _run("root.create_entity", model, ifc_class="IfcPipeSegment", name="Pipe B")
    fitting = _run("root.create_entity", model, ifc_class="IfcPipeFitting", name="Elbow")
    valve = _run("root.create_entity", model, ifc_class="IfcValve", name="Ball valve")
    _ports(model, short, (0.0, 2000.0))
    _ports(model, long, (2000.0, 5000.0))
    qto = _run("pset.add_qto", model, product=long, name="Qto_PipeSegmentBaseQuantities")
    _run("pset.edit_qto", model, qto=qto, properties={"Length": 3000.0})
    elements = [short, long, fitting, valve]
    _run("spatial.assign_container", model, products=elements, relating_structure=ground)
    system = _run("system.add_system", model, ifc_class="IfcDistributionSystem")
    system.Name = "Heating supply"
    _run("system.assign_system", model, products=elements, system=system)
    path = tmp_path_factory.mktemp("mep") / "mep.ifc"
    model.write(str(path))
    return path


def test_index_reads_kinds_storeys_systems_and_lengths(ifc_path: Path) -> None:
    index = ifc_mep.build_index(ifc_model.open_model(str(ifc_path)))
    assert index.unit_name == "MILLIMETRE"
    by_name = {e.name: e for e in index.elements}
    assert {e.kind for e in index.elements} == {"pipe", "pipe_fitting", "valve"}
    assert all(e.storey == "Ground" and e.systems == ("Heating supply",) for e in index.elements)
    assert by_name["Pipe A"].length_source == "geometry"
    assert by_name["Pipe A"].length_m == pytest.approx(2.0)  # the distance between the two ports
    assert by_name["Pipe B"].length_source == "qto"
    assert by_name["Pipe B"].length_m == pytest.approx(3.0)  # the quantity, in mm, scaled by the project unit
    assert ifc_mep.entity_id("valve", by_name["Ball valve"].global_id).startswith("valve:")


def test_a_mixed_or_unchecked_length_is_not_sure(ifc_path: Path) -> None:
    index = ifc_mep.build_index(ifc_model.open_model(str(ifc_path)))
    pipes = ifc_mep.select(index, "pipe")
    sure, why, check = length_status(index, pipes)
    assert not sure  # one stated length cannot be checked against the geometry on a sample of one
    assert check.status == "unchecked"
    assert why
    only_geometry = ifc_mep.select(index, "pipe", name="Pipe A")
    assert length_status(index, only_geometry)[0]


def test_tools_report_counts_and_lengths(ifc_path: Path) -> None:
    context, specs = mep_tools(ifc_model.open_model(str(ifc_path)))
    tools = {s.name: s for s in specs}
    assert set(tools) == {"mep_overview", "mep_count", "mep_length", "mep_systems", "mep_elements"}
    assert "mep_" in context
    empty = {"group_by": None, "then_by": None, "storey": None, "system": None, "name": None}
    counted = tools["mep_count"].run({**empty, "kind": "valve"})
    assert counted.ok
    assert counted.data["groups"][0]["count"] == 1
    assert counted.data["groups"][0]["entity_ids"][0].startswith("valve:")
    length = tools["mep_length"].run({**empty, "kind": "pipe"})
    assert length.ok
    assert length.data["total_m"] == pytest.approx(5.0)
    assert length.data["sure"] is False
    assert (length.confidence or 1.0) < 0.5
    systems = tools["mep_systems"].run({"system": None})
    assert systems.data["systems"][0]["name"] == "Heating supply"


def test_truth_reader_agrees_on_the_synthetic_model(ifc_path: Path) -> None:
    truth = mep_truth.read_truth(ifc_path)
    assert sorted(truth.kinds.values()) == ["pipe", "pipe", "pipe_fitting", "valve"]
    assert truth.unit_m == pytest.approx(0.001)
    assert sorted(round(v, 3) for v in truth.port_length_m.values()) == [2.0, 3.0]
    assert set(truth.storey.values()) == {"Ground"}
