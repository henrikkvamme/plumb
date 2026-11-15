"""Tests of the contractor quantities: wall centre lines, room perimeters and baseboards, the tools, the IFC rules."""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.api
import pytest
from shapely.geometry import Polygon, box

from bp import facts_quantities
from bp.solvers.quantity_tools import quantity_tools
from bp.tools import quantities as q
from bp.tools import quantities_ifc as qi

XY = tuple[float, float]


def _ring(minx: float, miny: float, maxx: float, maxy: float) -> tuple[XY, ...]:
    return ((minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy))


def _room(entity_id: str, number: str, label: str, ring: tuple[XY, ...]) -> q.RoomIn:
    return q.RoomIn(entity_id=entity_id, number=number, label=label, apartment="A", outdoor=False, shared=False,
                    area_m2=Polygon(ring).area, rings=(ring,))  # fmt: skip


def _floor() -> q.FloorIn:
    """Two 4 x 3 m rooms, a 0.2 m wall around them and between them, a 0.9 m door between, a 1.2 m window in A."""
    frame = (_ring(-0.2, -0.2, 8.4, 3.2), _ring(0, 0, 8.2, 3))
    return q.FloorIn(
        unit_m=1.0,
        rooms=(_room("room:1", "1", "Zimmer", _ring(0, 0, 4, 3)), _room("room:2", "2", "Bad", _ring(4.2, 0, 8.2, 3))),
        doors=(q.OpeningIn(entity_id="door:1", kind="door", ring=_ring(4.0, 1.0, 4.2, 1.9)),),
        windows=(q.OpeningIn(entity_id="window:1", kind="window", ring=_ring(1.0, -0.2, 2.2, 0)),),
        walls=(frame, (_ring(4.0, 0, 4.2, 1.0),), (_ring(4.0, 1.9, 4.2, 3.0),)),
    )


def test_centerline_of_a_straight_wall_runs_to_its_ends() -> None:
    line = q.centerline(box(0, 0, 10, 0.2), 0.02)
    assert line.length == pytest.approx(10.0, rel=0.01)
    assert line.free_ends == 2


def test_centerline_of_a_rotated_wall_has_no_staircase() -> None:
    wall = Polygon([(0, 0), (8.66, 5.0), (8.56, 5.17), (-0.1, 0.17)])
    assert q.centerline(wall, 0.02).length == pytest.approx(10.0, rel=0.015)


def test_rooms_have_perimeter_baseboard_doors_and_windows() -> None:
    got = q.measure(_floor())
    a, b = got.rooms
    assert a.perimeter_m == pytest.approx(14.0)
    assert a.door_ids == ("door:1",)
    assert a.door_widths_m == (pytest.approx(0.9),)
    assert a.baseboard_m == pytest.approx(13.1)
    assert a.window_ids == ("window:1",)
    assert (a.kind, b.kind) == ("room", "bathroom")
    assert b.window_ids == ()
    assert b.baseboard_m == pytest.approx(13.1)
    assert got.doors[0].rooms == ("room:1", "room:2")
    assert got.windows[0].width_m == pytest.approx(1.2)


def test_walls_have_centre_line_with_exterior_and_interior() -> None:
    walls = q.measure(_floor()).walls
    assert walls is not None
    assert walls.centerline_m == pytest.approx(26.4, rel=0.02)
    assert walls.exterior_m == pytest.approx(23.2, rel=0.02)
    assert walls.interior_m == pytest.approx(3.2, rel=0.1)


def test_tools_give_rows_with_entity_ids_and_count_a_shared_door_once() -> None:
    _, tools = quantity_tools(lambda: q.measure(_floor()))
    by_name = {t.name: t for t in tools}
    rooms = by_name["room_quantities"].run({"apartment": "A", "kind": ""})
    assert rooms.ok
    assert [r["entity_id"] for r in rooms.data["rooms"]] == ["room:1", "room:2"]
    assert rooms.data["totals"]["baseboard_m"] == pytest.approx(26.2)
    assert rooms.data["totals"]["door_openings"] == 1
    assert rooms.data["totals"]["indoor_only"]["entity_id"] == "apartment:A"
    groups = by_name["group_quantities"].run({"by": "kind"})
    assert {g["entity_id"] for g in groups.data["groups"]} == {"kind:room", "kind:bathroom"}
    walls = by_name["wall_quantities"].run({})
    assert walls.data["walls"]["entity_id"] == "walls"
    assert walls.data["doors"][0]["entity_id"] == "door:1"


def test_tools_say_when_the_plan_has_no_scale() -> None:
    _, tools = quantity_tools(lambda: None)
    got = tools[0].run({"apartment": "", "kind": ""})
    assert not got.ok
    assert "scale" in (got.error or "")


def test_nominal_width_reads_the_size_in_a_type_name() -> None:
    assert qi.nominal_width("TU DF 1 - Rahmenstock:DL - 1000 x 2000") == pytest.approx(1.0)
    assert qi.nominal_width("Door 25", "M_Single 0915x2134mm") == pytest.approx(0.915)
    assert qi.nominal_width("Window 25") is None


def _wall(model: ifcopenshell.file, pset: str, props: dict[str, object]) -> ifcopenshell.entity_instance:
    wall = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcWall")
    p = ifcopenshell.api.run("pset.add_pset", model, product=wall, name=pset)
    ifcopenshell.api.run("pset.edit_pset", model, pset=p, properties=props)
    return wall


def test_wall_side_uses_is_external_then_a_layer_property() -> None:
    model = ifcopenshell.api.run("project.create_file", version="IFC4")
    ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject")
    assert qi.wall_side(_wall(model, "Pset_WallCommon", {"IsExternal": True})) == (True, "IsExternal")
    assert qi.wall_side(_wall(model, "ArchiCADProperties", {"Ebene": "Außenwände"})) == (True, "layer")
    assert qi.wall_side(_wall(model, "ArchiCADProperties", {"Ebene": "Innenwände"})) == (False, "layer")
    assert qi.wall_side(_wall(model, "Other", {"Note": "x"})) == (None, "none")


def test_facts_carry_the_margins_of_the_bench() -> None:
    rooms, summary, entities = facts_quantities.floor_facts(q.measure(_floor()))
    baseboard = next(f for f in rooms["room:1"] if f.key == "baseboard")
    assert baseboard.value == pytest.approx(13.1)
    assert baseboard.margin == pytest.approx(0.0131)
    assert [f.key for f in summary] == ["wall_centerline", "wall_exterior"]
    assert entities[0].id == "walls"
    assert entities[0].facts[0].margin == pytest.approx(0.012 * 26.4, rel=0.03)
