"""Typed queries on an IFC model. Each result carries the GlobalIds of the elements it used.

The rules follow what the public ifc_models references use (analysis/ifc/05_probe_models.py):
- an element belongs to the storey that contains it, directly or through an aggregate;
- a quantity comes from a Qto set when the model has one, and a geometry value is a marked fallback;
- a stair counts only when it is top level (not a part of another stair);
- IFC2X3 sanitary and light fixtures are `IfcFlowTerminal` elements with a matching type.
All functions are pure on a model that `open_model` returned. Nothing here reads a label or a key.
"""

from __future__ import annotations

import contextlib
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as ue
import ifcopenshell.util.unit as uu
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from bp.contract import Frozen

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ifcopenshell import entity_instance

AreaSource = Literal["qto", "geometry", "none"]
Category = Literal["door", "window", "wall", "space", "column", "beam", "stair", "slab", "sanitary", "light"]

# The IFC classes behind each plain category. `IfcWall` includes `IfcWallStandardCase` through subtypes.
CATEGORY_CLASSES: dict[Category, tuple[str, ...]] = {
    "door": ("IfcDoor",),
    "window": ("IfcWindow",),
    "wall": ("IfcWall",),
    "space": ("IfcSpace",),
    "column": ("IfcColumn",),
    "beam": ("IfcBeam",),
    "stair": ("IfcStair",),
    "slab": ("IfcSlab",),
    "sanitary": ("IfcFlowTerminal",),
    "light": ("IfcFlowTerminal",),
}

_MAX_GEOMETRY_THREADS = 8


# ----------------------------------------------------------------------------- results


class StoreyInfo(Frozen):
    name: str
    elevation_m: float | None
    global_id: str


class ProjectInfo(Frozen):
    schema_name: str
    project_name: str
    project_long_name: str
    project_description: str
    applications: tuple[str, ...]  # "Autodesk Revit 2011 (2011)"
    organizations: tuple[str, ...]
    authors: tuple[str, ...]
    site_name: str
    building_names: tuple[str, ...]
    storeys: tuple[StoreyInfo, ...]
    length_unit_m: float  # one project length unit in metres


class ElementCount(Frozen):
    category: str
    ifc_classes: tuple[str, ...]
    storey: str | None  # None means the whole model
    rule: str
    count: int
    global_ids: tuple[str, ...]


class SpaceInfo(Frozen):
    global_id: str
    name: str
    long_name: str
    storey: str | None
    net_floor_area_m2: float | None
    area_source: AreaSource
    gross_floor_area_m2: float | None
    height_m: float | None


class QuantityTotal(Frozen):
    category: str
    quantity: str  # the Qto name that was summed, or "geometry:<kind>"
    storey: str | None
    value: float | None  # SI units: m, m2 or m3
    unit: str
    n_elements: int
    n_with_value: int
    source: Literal["qto", "geometry", "none"]
    global_ids: tuple[str, ...]


class TypeCount(Frozen):
    type_name: str
    count: int


class TypeBreakdown(Frozen):
    category: str
    storey: str | None
    total: int
    types: tuple[TypeCount, ...]


class MaterialUse(Frozen):
    material: str
    count: int


class MaterialBreakdown(Frozen):
    category: str
    total_elements: int
    materials: tuple[MaterialUse, ...]


class StoreySummary(Frozen):
    storey: StoreyInfo
    counts: tuple[TypeCount, ...]  # elements per IFC class, assigned to this storey


# ----------------------------------------------------------------------------- the model


@dataclass
class IfcModel:
    """An open IFC file with lazy caches. Build it with `open_model`."""

    file: ifcopenshell.file
    length_scale: float
    area_scale: float
    volume_scale: float
    _storey_of: dict[int, entity_instance | None] = field(default_factory=dict)
    _footprints: dict[str, float] | None = None


def open_model(path: str) -> IfcModel:
    model = ifcopenshell.open(path)
    return IfcModel(
        file=model,
        length_scale=float(uu.calculate_unit_scale(model, "LENGTHUNIT")),
        area_scale=float(uu.calculate_unit_scale(model, "AREAUNIT")),
        volume_scale=float(uu.calculate_unit_scale(model, "VOLUMEUNIT")),
    )


def by_type(model: IfcModel, ifc_class: str) -> list[entity_instance]:
    """`by_type` that returns an empty list for a class that the schema does not have."""
    try:
        return list(model.file.by_type(ifc_class))
    except RuntimeError:
        return []


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def norm(text: str) -> str:
    """A key for loose name matching: NFKC, case folded, single spaces."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()


# ----------------------------------------------------------------------------- storeys


def storey_of(model: IfcModel, element: entity_instance) -> entity_instance | None:
    """The storey of an element: its container, walking up aggregates, or its aggregate chain."""
    key = int(element.id())
    if key in model._storey_of:  # noqa: SLF001 - the cache of this module
        return model._storey_of[key]  # noqa: SLF001
    found: entity_instance | None = None
    container = ue.get_container(element)
    if container is None:
        parent = ue.get_aggregate(element)
        while parent is not None and not parent.is_a("IfcBuildingStorey"):
            above = ue.get_container(parent)
            parent = above if above is not None else ue.get_aggregate(parent)
        found = parent
    else:
        while container is not None and not container.is_a("IfcBuildingStorey"):
            container = ue.get_aggregate(container)
        found = container
    model._storey_of[key] = found  # noqa: SLF001
    return found


def _elevation_m(model: IfcModel, storey: entity_instance) -> float | None:
    value = getattr(storey, "Elevation", None)
    return float(value) * model.length_scale if isinstance(value, (int, float)) else None


def storeys(model: IfcModel) -> tuple[StoreyInfo, ...]:
    out = [
        StoreyInfo(name=_text(s.Name), elevation_m=_elevation_m(model, s), global_id=s.GlobalId)
        for s in by_type(model, "IfcBuildingStorey")
    ]
    out.sort(key=lambda s: (s.elevation_m is None, s.elevation_m or 0.0))
    return tuple(out)


def match_storeys(model: IfcModel, name: str) -> list[entity_instance]:
    """Storeys with this name: exact first, then a loose match."""
    every = by_type(model, "IfcBuildingStorey")
    exact = [s for s in every if _text(s.Name) == name]
    if exact:
        return exact
    key = norm(name)
    return [s for s in every if norm(_text(s.Name)) == key]


def _in_storey(model: IfcModel, element: entity_instance, wanted: list[entity_instance]) -> bool:
    found = storey_of(model, element)
    return found is not None and any(found == s for s in wanted)


# ----------------------------------------------------------------------------- project


def project_info(model: IfcModel) -> ProjectInfo:
    projects = by_type(model, "IfcProject")
    project = projects[0] if projects else None
    apps = []
    for app in by_type(model, "IfcApplication"):
        full = _text(app.ApplicationFullName)
        version = _text(app.Version)
        apps.append(f"{full} ({version})" if version and version not in full else full)
    orgs = sorted({_text(o.Name) for o in by_type(model, "IfcOrganization") if _text(o.Name)})
    people = set()
    for person in by_type(model, "IfcPerson"):
        parts = [_text(getattr(person, a, None)) for a in ("GivenName", "FamilyName")]
        name = " ".join(p for p in parts if p) or _text(getattr(person, "Identification", None))
        if name:
            people.add(name)
    sites = by_type(model, "IfcSite")
    return ProjectInfo(
        schema_name=str(model.file.schema),
        project_name=_text(project.Name) if project else "",
        project_long_name=_text(project.LongName) if project else "",
        project_description=_text(project.Description) if project else "",
        applications=tuple(dict.fromkeys(a for a in apps if a)),
        organizations=tuple(orgs),
        authors=tuple(sorted(people)),
        site_name=_text(sites[0].Name) if sites else "",
        building_names=tuple(_text(b.Name) for b in by_type(model, "IfcBuilding")),
        storeys=storeys(model),
        length_unit_m=model.length_scale,
    )


# ----------------------------------------------------------------------------- elements and counts


def _type_label(element: entity_instance) -> str:
    kind = ue.get_type(element)
    if kind is None:
        return ""
    return f"{kind.is_a()} {_text(kind.Name)}".lower()


def _is_top_level(element: entity_instance) -> bool:
    parent = ue.get_aggregate(element)
    return parent is None or parent.is_a("IfcSpatialStructureElement") or parent.is_a("IfcSpatialElement")


def category_elements(model: IfcModel, category: Category) -> tuple[list[entity_instance], str]:
    """Every element of a category in the model, and the rule that selected them."""
    if category == "sanitary":
        found = [e for e in by_type(model, "IfcFlowTerminal") if "sanit" in _type_label(e)]
        return found, "IfcFlowTerminal whose type mentions 'sanit'"
    if category == "light":
        found = [e for e in by_type(model, "IfcFlowTerminal") if "lightfixturetype" in _type_label(e)]
        return found, "IfcFlowTerminal whose type is an IfcLightFixtureType"
    classes = CATEGORY_CLASSES[category]
    found = [e for c in classes for e in by_type(model, c)]
    if category == "stair":
        return [e for e in found if _is_top_level(e)], "IfcStair, top level only (stair parts do not count)"
    return found, f"by_type {', '.join(classes)}"


def count_elements(model: IfcModel, category: Category, storey: str | None = None) -> ElementCount:
    """Elements of a category in the model, or assigned to one storey (containment or aggregation)."""
    found, rule = category_elements(model, category)
    if storey is not None:
        wanted = match_storeys(model, storey)
        found = [e for e in found if _in_storey(model, e, wanted)] if wanted else []
        rule += "; assigned to the storey by containment or aggregation"
    return ElementCount(
        category=category,
        ifc_classes=CATEGORY_CLASSES[category],
        storey=storey,
        rule=rule,
        count=len(found),
        global_ids=tuple(e.GlobalId for e in found),
    )


def count_class(model: IfcModel, ifc_class: str, storey: str | None = None) -> ElementCount:
    """Elements of any IFC class (with subtypes), optionally on one storey."""
    found = by_type(model, ifc_class)
    if storey is not None:
        wanted = match_storeys(model, storey)
        found = [e for e in found if _in_storey(model, e, wanted)] if wanted else []
    return ElementCount(
        category=ifc_class,
        ifc_classes=(ifc_class,),
        storey=storey,
        rule=f"by_type {ifc_class}",
        count=len(found),
        global_ids=tuple(e.GlobalId for e in found),
    )


def class_histogram(model: IfcModel, root: str = "IfcProduct") -> tuple[TypeCount, ...]:
    """Counts per exact IFC class for all products in the model."""
    counter = Counter(e.is_a() for e in by_type(model, root))
    return tuple(TypeCount(type_name=k, count=v) for k, v in counter.most_common())


def type_name(element: entity_instance) -> str:
    """The type name a person reads: the type object name, else ObjectType, else the element name."""
    kind = ue.get_type(element)
    if kind is not None and _text(kind.Name):
        return _text(kind.Name)
    return _text(getattr(element, "ObjectType", None)) or _text(element.Name) or "(no type)"


def type_breakdown(elements: Iterable[entity_instance], category: str, storey: str | None = None) -> TypeBreakdown:
    counter = Counter(type_name(e) for e in elements)
    types = tuple(TypeCount(type_name=k, count=v) for k, v in counter.most_common())
    return TypeBreakdown(category=category, storey=storey, total=sum(counter.values()), types=types)


def storey_summaries(model: IfcModel) -> tuple[StoreySummary, ...]:
    per: dict[str, Counter[str]] = defaultdict(Counter)
    for element in by_type(model, "IfcElement"):
        found = storey_of(model, element)
        if found is not None:
            per[found.GlobalId][element.is_a()] += 1
    return tuple(
        StoreySummary(
            storey=s, counts=tuple(TypeCount(type_name=k, count=v) for k, v in per[s.global_id].most_common())
        )
        for s in storeys(model)
    )


# ----------------------------------------------------------------------------- materials


def material_names(element: entity_instance) -> tuple[str, ...]:
    """Material names of an element (layers, constituents, profiles or a single material), with its type."""
    names: list[str] = []
    with contextlib.suppress(Exception):
        materials = ue.get_materials(element, should_inherit=True)
        names = [_text(m.Name) for m in materials if _text(getattr(m, "Name", None))]
    return tuple(dict.fromkeys(names))


def material_breakdown(elements: Iterable[entity_instance], category: str) -> MaterialBreakdown:
    counter: Counter[str] = Counter()
    total = 0
    for element in elements:
        total += 1
        for name in material_names(element):
            counter[name] += 1
    return MaterialBreakdown(
        category=category,
        total_elements=total,
        materials=tuple(MaterialUse(material=k, count=v) for k, v in counter.most_common()),
    )


# ----------------------------------------------------------------------------- quantities


def qto_value(element: entity_instance, names: tuple[str, ...]) -> float | None:
    """The first numeric value of a Qto set entry with one of `names`, in the project unit."""
    sets = ue.get_psets(element, qtos_only=True)
    for name in names:
        for props in sets.values():
            value = props.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    return None


def _footprint(verts: np.ndarray, faces: np.ndarray) -> float | None:
    tris = verts[faces][:, :, :2]
    polys = [Polygon(t) for t in tris]
    polys = [p for p in polys if p.area > 1e-9]
    if not polys:
        return None
    return float(unary_union(polys).area)


def space_footprints(model: IfcModel) -> dict[str, float]:
    """The plan footprint area (m2) of every space with a body, from world-coordinate geometry."""
    if model._footprints is not None:  # noqa: SLF001
        return model._footprints  # noqa: SLF001
    out: dict[str, float] = {}
    spaces = by_type(model, "IfcSpace")
    if spaces:
        settings = ifcopenshell.geom.settings()
        settings.set("use-world-coords", True)
        iterator = ifcopenshell.geom.iterator(settings, model.file, _MAX_GEOMETRY_THREADS, include=spaces)
        if iterator.initialize():
            while True:
                shape = iterator.get()
                with contextlib.suppress(Exception):
                    geometry = getattr(shape, "geometry")  # noqa: B009 - the iterator result type has no stub
                    verts = np.array(geometry.verts).reshape(-1, 3)
                    faces = np.array(geometry.faces).reshape(-1, 3)
                    if len(faces):
                        area = _footprint(verts, faces)
                        if area is not None:
                            out[str(getattr(shape, "guid"))] = area  # noqa: B009
                if not iterator.next():
                    break
    model._footprints = out  # noqa: SLF001
    return out


def space_info(model: IfcModel, space: entity_instance, *, geometry: bool = True) -> SpaceInfo:
    net = qto_value(space, ("NetFloorArea",))
    gross = qto_value(space, ("GrossFloorArea",))
    height = qto_value(space, ("Height", "FinishCeilingHeight", "NetHeight"))
    source: AreaSource = "none"
    area: float | None = None
    if net is not None:
        area, source = net * model.area_scale, "qto"
    elif geometry:
        fp = space_footprints(model).get(space.GlobalId)
        if fp is not None:
            area, source = fp, "geometry"
    found = storey_of(model, space)
    return SpaceInfo(
        global_id=space.GlobalId,
        name=_text(space.Name),
        long_name=_text(space.LongName),
        storey=_text(found.Name) if found is not None else None,
        net_floor_area_m2=area,
        area_source=source,
        gross_floor_area_m2=gross * model.area_scale if gross is not None else None,
        height_m=height * model.length_scale if height is not None else None,
    )


def spaces(model: IfcModel, storey: str | None = None, *, geometry: bool = True) -> tuple[SpaceInfo, ...]:
    found = by_type(model, "IfcSpace")
    if storey is not None:
        wanted = match_storeys(model, storey)
        found = [s for s in found if _in_storey(model, s, wanted)] if wanted else []
    return tuple(space_info(model, s, geometry=geometry) for s in found)


def space_labels(space: entity_instance) -> set[str]:
    name, long_name = _text(space.Name), _text(space.LongName)
    labels = {name, long_name, f"{long_name} ({name})", f"{name} ({long_name})"}
    return {norm(x) for x in labels if x.strip()}


def find_spaces(model: IfcModel, label: str, storey: str | None = None) -> tuple[SpaceInfo, ...]:
    """Spaces whose name, long name or 'long name (name)' equals `label`, on the storey when there are several."""
    key = norm(label)
    hits = [s for s in by_type(model, "IfcSpace") if key in space_labels(s)]
    if len(hits) > 1 and storey is not None:
        wanted = match_storeys(model, storey)
        on_storey = [s for s in hits if _in_storey(model, s, wanted)]
        hits = on_storey or hits
    return tuple(space_info(model, s) for s in hits)


def storey_space_area(model: IfcModel, storey: str) -> QuantityTotal:
    """The sum of the net floor areas of all spaces on a storey (Qto first, geometry per space as fallback)."""
    infos = spaces(model, storey)
    values = [s.net_floor_area_m2 for s in infos]
    known = [v for v in values if v is not None]
    sources = {s.area_source for s in infos if s.net_floor_area_m2 is not None}
    return QuantityTotal(
        category="space",
        quantity="NetFloorArea",
        storey=storey,
        value=math.fsum(known) if known else None,
        unit="m2",
        n_elements=len(infos),
        n_with_value=len(known),
        source="qto" if sources == {"qto"} else ("geometry" if known else "none"),
        global_ids=tuple(s.global_id for s in infos),
    )


_QTO_KIND: dict[str, Literal["length", "area", "volume"]] = {
    "NetVolume": "volume",
    "GrossVolume": "volume",
    "Length": "length",
    "NetSideArea": "area",
    "GrossSideArea": "area",
    "NetArea": "area",
    "GrossArea": "area",
    "Width": "length",
    "Height": "length",
    "Depth": "length",
}
_UNIT_NAME = {"length": "m", "area": "m2", "volume": "m3"}


def storey_quantity(model: IfcModel, category: Category, quantity: str, storey: str | None) -> QuantityTotal:
    """The sum of a Qto entry over the elements of a category on a storey (or the whole model)."""
    found, _ = category_elements(model, category)
    if storey is not None:
        wanted = match_storeys(model, storey)
        found = [e for e in found if _in_storey(model, e, wanted)] if wanted else []
    kind = _QTO_KIND.get(quantity, "length")
    scale = {"length": model.length_scale, "area": model.area_scale, "volume": model.volume_scale}[kind]
    values = [qto_value(e, (quantity,)) for e in found]
    known = [v * scale for v in values if v is not None]
    return QuantityTotal(
        category=category,
        quantity=quantity,
        storey=storey,
        value=math.fsum(known) if known else None,
        unit=_UNIT_NAME[kind],
        n_elements=len(found),
        n_with_value=len(known),
        source="qto" if known else "none",
        global_ids=tuple(e.GlobalId for e in found),
    )


def element_ref(element: entity_instance) -> str:
    return f"{element.is_a()} {element.GlobalId} {_text(element.Name)}".strip()


# ----------------------------------------------------------------------------- entity ids
# The ids that the facts of a model and the rows of the agent tools share, so an answer can show what it used.

ELEMENT_KINDS: dict[str, str] = {"IfcDoor": "door", "IfcWindow": "window"}


def space_name(space: entity_instance) -> str:
    """The name that finds a space in the 3D view: its Name, or its LongName when the Name is empty."""
    return _text(space.Name).strip() or _text(space.LongName).strip()


def space_ids(model: IfcModel) -> dict[str, str]:
    """The entity id of each space by GlobalId: `space:<name>`, and `space:<name>@<GlobalId>` when the name repeats."""
    found = by_type(model, "IfcSpace")
    names = [space_name(s) for s in found]
    seen = Counter(names)
    return {
        s.GlobalId: f"space:{name}" if name and seen[name] == 1 else f"space:{name}@{s.GlobalId}"
        for s, name in zip(found, names, strict=True)
    }


def element_id(element: entity_instance) -> str:
    """`door:<GlobalId>`, `window:<GlobalId>`, or `element:<GlobalId>` for any other element."""
    kind = next((k for cls, k in ELEMENT_KINDS.items() if element.is_a(cls)), "element")
    return f"{kind}:{element.GlobalId}"


def storey_id(name: str) -> str:
    return f"storey:{name}"


# ----------------------------------------------------------------------------- header, site, properties


class HeaderInfo(Frozen):
    schema_name: str
    view_definitions: tuple[str, ...]  # FILE_DESCRIPTION entries
    originating_system: str
    preprocessor: str
    authors: tuple[str, ...]
    organizations: tuple[str, ...]
    timestamp: str


class SiteLocation(Frozen):
    site_name: str
    latitude_dms: tuple[int, ...] | None  # degrees, minutes, seconds, millionths
    longitude_dms: tuple[int, ...] | None
    elevation_m: float | None
    address: str


def _strings(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, (tuple, list)):
        return tuple(str(v) for v in value if isinstance(v, str) and v)
    return ()


def header_info(model: IfcModel) -> HeaderInfo:
    header = model.file.header
    name = header.file_name
    return HeaderInfo(
        schema_name=str(model.file.schema),
        view_definitions=_strings(header.file_description.description),
        originating_system=_text(name.originating_system),
        preprocessor=_text(name.preprocessor_version),
        authors=_strings(name.author),
        organizations=_strings(name.organization),
        timestamp=_text(name.time_stamp),
    )


def _dms(value: object) -> tuple[int, ...] | None:
    if isinstance(value, (tuple, list)) and value and all(isinstance(v, int) for v in value):
        return tuple(int(v) for v in value)
    return None


def site_location(model: IfcModel) -> SiteLocation:
    sites = by_type(model, "IfcSite")
    if not sites:
        return SiteLocation(site_name="", latitude_dms=None, longitude_dms=None, elevation_m=None, address="")
    site = sites[0]
    address = ""
    postal = getattr(site, "SiteAddress", None)
    if postal is not None:
        parts = [*_strings(getattr(postal, "AddressLines", None))]
        parts += [_text(getattr(postal, a, None)) for a in ("PostalCode", "Town", "Region", "Country")]
        address = ", ".join(p for p in parts if p)
    elevation = getattr(site, "RefElevation", None)
    return SiteLocation(
        site_name=_text(site.Name),
        latitude_dms=_dms(getattr(site, "RefLatitude", None)),
        longitude_dms=_dms(getattr(site, "RefLongitude", None)),
        elevation_m=float(elevation) * model.length_scale if isinstance(elevation, (int, float)) else None,
        address=address,
    )


def common_property(element: entity_instance, prop: str) -> object:
    """A value from the element's Pset_*Common set (with the type's), such as IsExternal or FireRating."""
    for name, props in ue.get_psets(element, psets_only=True).items():
        if name.startswith("Pset_") and name.endswith("Common") and prop in props:
            return props[prop]
    return None


def classes_elements(model: IfcModel, classes: tuple[str, ...]) -> list[entity_instance]:
    """Elements of the IFC classes. When a class is absent (IFC2X3 MEP), the elements typed by `<class>Type`."""
    out: list[entity_instance] = []
    for ifc_class in classes:
        found = by_type(model, ifc_class)
        if not found:
            for kind in by_type(model, ifc_class + "Type"):
                found.extend(ue.get_types(kind))
        out.extend(found)
    return list({int(e.id()): e for e in out}.values())


def thickness_m(model: IfcModel, element: entity_instance) -> float | None:
    """The thickness of a wall or slab: the material layer set total, else the Qto Width or Depth."""
    with contextlib.suppress(Exception):
        material = ue.get_material(element, should_inherit=True)
        layer_set = None
        if material is not None and material.is_a("IfcMaterialLayerSetUsage"):
            layer_set = material.ForLayerSet
        elif material is not None and material.is_a("IfcMaterialLayerSet"):
            layer_set = material
        if layer_set is not None:
            total = sum(float(layer.LayerThickness) for layer in layer_set.MaterialLayers)
            if total > 0:
                return total * model.length_scale
    value = qto_value(element, ("Width", "Depth", "Thickness"))
    return value * model.length_scale if value is not None else None


def systems(model: IfcModel) -> tuple[TypeCount, ...]:
    """Distribution systems (IfcSystem and subtypes) by name, with the number of elements in each."""
    out: list[TypeCount] = []
    for system in by_type(model, "IfcSystem"):
        if system.is_a("IfcZone") or system.is_a("IfcStructuralAnalysisModel"):
            continue
        members = sum(len(rel.RelatedObjects) for rel in getattr(system, "IsGroupedBy", ()) or ())
        out.append(TypeCount(type_name=_text(system.Name) or system.is_a(), count=members))
    return tuple(out)
