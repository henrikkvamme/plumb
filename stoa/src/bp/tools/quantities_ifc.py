"""Contractor quantities from an IFC model: wall lengths, door and window widths, space perimeters and baseboards.

Rules, the same as the public ifc_bench answers where they give one:
- Wall length: the Qto_WallBaseQuantities Length of each wall, summed. A wall with no Qto length takes the length
  of its Axis representation (a marked fallback). Exterior and interior come from Pset_WallCommon.IsExternal; a
  model without it can name the side in a layer property ("Ebene: Außenwände" in ArchiCAD), a marked fallback.
- Door and window width: the OverallWidth attribute, else the Qto Width. A second field, nominal_width_m, is the
  nominal size that a type name states ("DL - 1000 x 2000" is 1.00 m). Some keys use that one (digital_hub).
- Space perimeter: the Qto NetPerimeter (else GrossPerimeter), else the edge length of the plan footprint of the
  space body. Baseboard: the perimeter minus the width of each door that bounds the space (IfcRelSpaceBoundary),
  else of each door whose position lies within half a metre of the space footprint.
Entity ids are those of `bp.tools.ifc_model`: `door:<GlobalId>`, `window:<GlobalId>`, `element:<GlobalId>` for a
wall, `space:<name>` for a space.
"""

from __future__ import annotations

import contextlib
import itertools
import math
import re
from typing import TYPE_CHECKING, Literal

import ifcopenshell.geom
import ifcopenshell.util.element as ue
import ifcopenshell.util.placement as up
import numpy as np
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from bp.contract import Frozen
from bp.tools import ifc_model as im

if TYPE_CHECKING:
    from ifcopenshell import entity_instance
    from shapely.geometry.base import BaseGeometry

DOOR_NEAR_M = 0.5  # a door belongs to a space when its position lies this close to the footprint (no boundaries)
_THREADS = 4


class OpeningRow(Frozen):
    entity_id: str
    name: str
    type_name: str
    storey: str | None
    width_m: float | None
    height_m: float | None
    source: Literal["attribute", "qto", "none"]
    nominal_width_m: float | None  # from a "W x H" size in mm in the type or element name


class WallRow(Frozen):
    entity_id: str
    name: str
    type_name: str
    storey: str | None
    external: bool | None
    side_source: Literal["IsExternal", "layer", "none"]
    length_m: float | None
    source: Literal["qto", "axis", "none"]


class WallTotals(Frozen):
    storey: str | None
    walls: int
    with_length: int
    total_m: float | None
    exterior_m: float | None
    interior_m: float | None
    unknown_side_m: float | None  # walls with no IsExternal value
    from_axis: int  # walls whose length is the Axis fallback


class SpaceRow(Frozen):
    entity_id: str
    name: str
    long_name: str
    storey: str | None
    area_m2: float | None
    perimeter_m: float | None
    perimeter_source: Literal["qto", "geometry", "none"]
    door_ids: tuple[str, ...]
    door_widths_m: tuple[float | None, ...]
    doors_by: Literal["space boundaries", "geometry", "none"]
    baseboard_m: float | None


def _in_storey(model: im.IfcModel, elements: list[entity_instance], storey: str | None) -> list[entity_instance]:
    if storey is None:
        return elements
    wanted = im.match_storeys(model, storey)
    return [e for e in elements if (s := im.storey_of(model, e)) is not None and any(s == w for w in wanted)]


def _storey_name(model: im.IfcModel, element: entity_instance) -> str | None:
    found = im.storey_of(model, element)
    return str(found.Name or "") if found is not None else None


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 else None


NOMINAL = re.compile(r"(?<![0-9.])([0-9]{3,4})\s*[x×]\s*([0-9]{3,4})(?![0-9])")  # noqa: RUF001 - type names use the multiplication sign


def nominal_width(*names: str) -> float | None:
    """The width of a "1000 x 2000" size (mm) in a type or element name, in metres."""
    for name in names:
        if found := NOMINAL.search(name or ""):
            return int(found.group(1)) / 1000.0
    return None


def opening_rows(model: im.IfcModel, kind: Literal["door", "window"], storey: str | None = None) -> list[OpeningRow]:
    elements = _in_storey(model, im.by_type(model, "IfcDoor" if kind == "door" else "IfcWindow"), storey)
    out = []
    for e in elements:
        width, height = _number(getattr(e, "OverallWidth", None)), _number(getattr(e, "OverallHeight", None))
        source: Literal["attribute", "qto", "none"] = "attribute" if width is not None else "none"
        if width is None:
            width = im.qto_value(e, ("Width",))
            source = "qto" if width is not None else "none"
        if height is None:
            height = im.qto_value(e, ("Height",))
        scale, name, type_name = model.length_scale, str(e.Name or ""), im.type_name(e)
        out.append(OpeningRow(entity_id=im.element_id(e), name=name, type_name=type_name,
                              storey=_storey_name(model, e), width_m=round(width * scale, 4) if width else None,
                              height_m=round(height * scale, 4) if height else None, source=source,
                              nominal_width_m=nominal_width(type_name, name)))  # fmt: skip
    return out


def _curve_length(item: entity_instance) -> float | None:  # noqa: PLR0911 - one return per curve kind
    """The plan length of an axis curve: a polyline, a trimmed line, or a composite of those."""
    if item.is_a("IfcPolyline"):
        pts = [tuple(p.Coordinates[:2]) for p in item.Points]
        return sum(math.dist(a, b) for a, b in itertools.pairwise(pts))
    if item.is_a("IfcIndexedPolyCurve"):
        pts = [tuple(p[:2]) for p in item.Points.CoordList]
        return sum(math.dist(a, b) for a, b in itertools.pairwise(pts))
    if item.is_a("IfcTrimmedCurve"):
        trims = [t for t in item.Trim1 if hasattr(t, "is_a") and t.is_a("IfcCartesianPoint")]
        trims2 = [t for t in item.Trim2 if hasattr(t, "is_a") and t.is_a("IfcCartesianPoint")]
        if trims and trims2:
            return math.dist(trims[0].Coordinates[:2], trims2[0].Coordinates[:2])
        params = [float(t.wrappedValue) for t in (*item.Trim1, *item.Trim2) if hasattr(t, "wrappedValue")]
        if len(params) == 2 and item.BasisCurve.is_a("IfcLine"):
            magnitude = float(item.BasisCurve.Dir.Magnitude)
            return abs(params[1] - params[0]) * magnitude
        if len(params) == 2 and item.BasisCurve.is_a("IfcCircle"):
            return abs(math.radians(params[1] - params[0])) * float(item.BasisCurve.Radius)
    if item.is_a("IfcCompositeCurve"):
        parts = [_curve_length(seg.ParentCurve) for seg in item.Segments]
        return sum(p for p in parts if p is not None) if all(p is not None for p in parts) else None
    return None


def axis_length(element: entity_instance) -> float | None:
    """The length of the Axis representation of a wall, in project units, or None when it has none."""
    shape = getattr(element, "Representation", None)
    for rep in getattr(shape, "Representations", None) or ():
        if str(rep.RepresentationIdentifier or "") != "Axis":
            continue
        lengths = [_curve_length(item) for item in rep.Items]
        known = [x for x in lengths if x is not None]
        if known:
            return sum(known)
    return None


LAYER_PROPS = ("Ebene", "Layer", "LayerName", "Layer Name")
EXTERIOR_WORDS = ("außenwand", "außenwände", "aussenwand", "aussenwände", "exterior wall", "external wall")
INTERIOR_WORDS = ("innenwand", "innenwände", "interior wall", "internal wall", "partition")


def wall_side(element: entity_instance) -> tuple[bool | None, Literal["IsExternal", "layer", "none"]]:
    """Whether a wall is exterior: Pset_WallCommon.IsExternal, else a layer property that names the side."""
    value = im.common_property(element, "IsExternal")
    if isinstance(value, bool):
        return value, "IsExternal"
    with contextlib.suppress(Exception):
        for props in ue.get_psets(element, psets_only=True).values():
            for key in LAYER_PROPS:
                text = str(props.get(key) or "").casefold()
                if any(w in text for w in EXTERIOR_WORDS):
                    return True, "layer"
                if any(w in text for w in INTERIOR_WORDS):
                    return False, "layer"
    return None, "none"


def wall_rows(model: im.IfcModel, storey: str | None = None) -> list[WallRow]:
    elements, _ = im.category_elements(model, "wall")
    out = []
    for e in _in_storey(model, elements, storey):
        length = im.qto_value(e, ("Length",))
        source: Literal["qto", "axis", "none"] = "qto"
        if length is None:
            with contextlib.suppress(Exception):
                length = axis_length(e)
            source = "axis" if length is not None else "none"
        external, side = wall_side(e)
        out.append(WallRow(entity_id=im.element_id(e), name=str(e.Name or ""), type_name=im.type_name(e),
                           storey=_storey_name(model, e), external=external, side_source=side,
                           length_m=round(length * model.length_scale, 4) if length else None, source=source))  # fmt: skip
    return out


def wall_totals(rows: list[WallRow], storey: str | None) -> WallTotals:
    def total(items: list[WallRow]) -> float | None:
        known = [r.length_m for r in items if r.length_m is not None]
        return round(math.fsum(known), 3) if known else None

    return WallTotals(
        storey=storey,
        walls=len(rows),
        with_length=sum(1 for r in rows if r.length_m is not None),
        total_m=total(rows),
        exterior_m=total([r for r in rows if r.external is True]),
        interior_m=total([r for r in rows if r.external is False]),
        unknown_side_m=total([r for r in rows if r.external is None]),
        from_axis=sum(1 for r in rows if r.source == "axis"),
    )


# ----------------------------------------------------------------------------- spaces


def _footprints(model: im.IfcModel, spaces: list[entity_instance]) -> dict[str, BaseGeometry]:
    out: dict[str, BaseGeometry] = {}
    if not spaces:
        return out
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    iterator = ifcopenshell.geom.iterator(settings, model.file, _THREADS, include=spaces)
    if not iterator.initialize():
        return out
    while True:
        shape = iterator.get()
        with contextlib.suppress(Exception):
            geometry = getattr(shape, "geometry")  # noqa: B009 - no stub for the iterator result
            verts = np.array(geometry.verts).reshape(-1, 3)
            faces = np.array(geometry.faces).reshape(-1, 3)
            tris = [Polygon(t) for t in verts[faces][:, :, :2]]
            plan = unary_union([t for t in tris if t.area > 1e-9])
            if not plan.is_empty:
                out[str(getattr(shape, "guid"))] = plan  # noqa: B009
        if not iterator.next():
            break
    return out


def _door_position(model: im.IfcModel, door: entity_instance) -> Point | None:
    with contextlib.suppress(Exception):
        matrix = up.get_local_placement(door.ObjectPlacement)
        return Point(float(matrix[0][3]) * model.length_scale, float(matrix[1][3]) * model.length_scale)
    return None


def space_rows(model: im.IfcModel, storey: str | None = None) -> list[SpaceRow]:
    spaces = _in_storey(model, im.by_type(model, "IfcSpace"), storey)
    ids = im.space_ids(model)
    doors = {d.entity_id: d for d in opening_rows(model, "door")}
    door_elements = {im.element_id(d): d for d in im.by_type(model, "IfcDoor")}
    need_geometry = [s for s in spaces if im.qto_value(s, ("NetPerimeter", "GrossPerimeter")) is None]
    any_boundaries = any(getattr(s, "BoundedBy", None) for s in spaces)
    shapes = _footprints(model, spaces if not any_boundaries else need_geometry)
    positions = (
        {}
        if any_boundaries
        else {k: p for k, d in door_elements.items() if (p := _door_position(model, d)) is not None}
    )
    out = []
    for s in spaces:
        info = im.space_info(model, s, geometry=False)
        qto = im.qto_value(s, ("NetPerimeter", "GrossPerimeter"))
        source: Literal["qto", "geometry", "none"] = "none"
        perimeter = None
        if qto is not None:
            perimeter, source = qto * model.length_scale, "qto"
        elif s.GlobalId in shapes:
            perimeter, source = shapes[s.GlobalId].length, "geometry"  # the geometry engine gives metres
        found: list[str] = []
        by: Literal["space boundaries", "geometry", "none"] = "none"
        bounds = getattr(s, "BoundedBy", None) or ()
        if bounds:
            by = "space boundaries"
            for rel in bounds:
                element = getattr(rel, "RelatedBuildingElement", None)
                if element is not None and element.is_a("IfcDoor"):
                    key = im.element_id(element)
                    if key not in found:
                        found.append(key)
        elif s.GlobalId in shapes and positions:
            by = "geometry"
            shape = shapes[s.GlobalId]
            found = [k for k, p in positions.items() if shape.distance(p) <= DOOR_NEAR_M]
        widths = tuple(doors[k].width_m if k in doors else None for k in found)
        known = [w for w in widths if w is not None]
        baseboard = None
        if perimeter is not None and len(known) == len(widths):
            baseboard = round(max(0.0, perimeter - sum(known)), 3)
        out.append(SpaceRow(entity_id=ids.get(s.GlobalId, f"space:{s.GlobalId}"), name=info.name,
                            long_name=info.long_name, storey=info.storey, area_m2=info.net_floor_area_m2,
                            perimeter_m=round(perimeter, 3) if perimeter is not None else None,
                            perimeter_source=source, door_ids=tuple(found), door_widths_m=widths, doors_by=by,
                            baseboard_m=baseboard))  # fmt: skip
    return out
