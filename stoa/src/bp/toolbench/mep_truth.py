"""Ground truth for MEP questions on an IFC file, by a method that shares no code with `bp.tools.ifc_mep`.

The tool reads the file with IfcOpenShell and takes a segment length from a quantity, a property or the
representation. This module reads the STEP text with regular expressions and measures each segment another way:
- counts: the entity class (IFC4) or the class of the type in `IFCRELDEFINESBYTYPE` (IFC2X3);
- storey: `IFCRELCONTAINEDINSPATIALSTRUCTURE` to a storey, or to a space that `IFCRELAGGREGATES` puts in a storey; a
  part of an assembly takes the storey of the assembly;
- system: `IFCRELASSIGNSTOGROUP` to an `IFCSYSTEM`, else the `System Name` property (one label per comma part);
- length: the distance between the two ports of the segment (`IFCDISTRIBUTIONPORT` placements, composed through
  `IFCLOCALPLACEMENT` by this module); when the segment has no two ports, the axis extent of the triangulated body
  from the OCC geometry kernel (`truth_mesh_lengths`), and only when that extent is clear.
The tool also falls back to the port distance when a model states no length. For those segments the bench compares
the tool with the OCC extent as well (`mesh_m`), which shares neither the method nor the code.
The kind table `KINDS` of the tool maps an IFC class to a plain kind: it is data, not a method.
"""

from __future__ import annotations

import contextlib
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from bp.tools.ifc_mep import KINDS, SEGMENT_KINDS

if TYPE_CHECKING:
    from pathlib import Path

_LINE = re.compile(r"^#(\d+)\s*=\s*([A-Z0-9_]+)\s*\((.*)\)\s*;\s*$", re.DOTALL)
_REF = re.compile(r"#(\d+)")
_CLASS_KIND = {cls.upper(): kind for kind, (_, classes, _) in KINDS.items() for cls in classes}
_TYPE_KIND = {cls.upper(): kind for kind, (_, _, types) in KINDS.items() for cls in types}
_GENERIC = {
    "IFCFLOWSEGMENT": "flow_segment", "IFCFLOWFITTING": "flow_fitting", "IFCFLOWTERMINAL": "flow_terminal",
    "IFCFLOWCONTROLLER": "flow_controller", "IFCFLOWMOVINGDEVICE": "flow_moving_device",
    "IFCFLOWSTORAGEDEVICE": "flow_storage_device", "IFCFLOWTREATMENTDEVICE": "flow_treatment_device",
    "IFCENERGYCONVERSIONDEVICE": "energy_conversion_device", "IFCDISTRIBUTIONCONTROLELEMENT": "distribution_control_element",
    "IFCDISTRIBUTIONELEMENT": "distribution_element", "IFCDISTRIBUTIONFLOWELEMENT": "distribution_flow_element",
    "IFCDISTRIBUTIONCHAMBERELEMENT": "distribution_chamber_element",
}  # fmt: skip
_ELEMENT_CLASSES = frozenset({*_CLASS_KIND, *_GENERIC})
SYSTEM_NAME_PROPS = ("System Name", "Systemname", "Systeemnaam")


def split_args(text: str) -> list[str]:
    """The top-level arguments of a STEP entity, as raw strings."""
    out: list[str] = []
    depth = 0
    start = 0
    quoted = False
    i = 0
    while i < len(text):
        ch = text[i]
        if quoted:
            if ch == "'":
                if i + 1 < len(text) and text[i + 1] == "'":
                    i += 1
                else:
                    quoted = False
        elif ch == "'":
            quoted = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            out.append(text[start:i].strip())
            start = i + 1
        i += 1
    out.append(text[start:].strip())
    return out


def _decode(raw: str) -> str:
    """A STEP string: quotes off, doubled quotes to one, and the X2 hex escapes of IFC exports decoded."""
    if not (raw.startswith("'") and raw.endswith("'")):
        return ""
    text = raw[1:-1].replace("''", "'")

    def x2(match: re.Match[str]) -> str:
        hexes = match.group(1)
        return "".join(chr(int(hexes[i : i + 4], 16)) for i in range(0, len(hexes), 4))

    text = re.sub(r"\\X2\\([0-9A-F]+)\\X0\\", x2, text)
    return re.sub(r"\\X\\([0-9A-F]{2})", lambda m: chr(int(m.group(1), 16)), text)


def _refs(raw: str) -> list[int]:
    return [int(x) for x in _REF.findall(raw)]


def _floats(raw: str) -> list[float]:
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?", raw)]


@dataclass
class Truth:
    schema: str
    unit_m: float | None  # project length unit in metres, from the IFCSIUNIT or conversion based unit
    kinds: dict[int, str] = field(default_factory=dict)  # element step id -> kind
    guid: dict[int, str] = field(default_factory=dict)
    type_name: dict[int, str] = field(default_factory=dict)  # the Name of the type entity
    storey: dict[int, str] = field(default_factory=dict)
    systems: dict[int, list[str]] = field(default_factory=dict)
    system_source: str = "none"
    port_length_m: dict[int, float] = field(default_factory=dict)


_KEEP = (
    "IFCRELDEFINESBYTYPE", "IFCRELCONTAINEDINSPATIALSTRUCTURE", "IFCBUILDINGSTOREY", "IFCRELAGGREGATES", "IFCSPACE",
    "IFCRELASSIGNSTOGROUP", "IFCSYSTEM", "IFCDISTRIBUTIONSYSTEM", "IFCDISTRIBUTIONCIRCUIT", "IFCBUILDINGSYSTEM",
    "IFCPROPERTYSINGLEVALUE", "IFCPROPERTYSET", "IFCRELDEFINESBYPROPERTIES", "IFCDISTRIBUTIONPORT",
    "IFCRELCONNECTSPORTTOELEMENT", "IFCRELNESTS", "IFCLOCALPLACEMENT", "IFCAXIS2PLACEMENT3D", "IFCCARTESIANPOINT",
    "IFCDIRECTION", "IFCSIUNIT", "IFCUNITASSIGNMENT", "IFCCONVERSIONBASEDUNIT", "IFCMEASUREWITHUNIT",
)  # fmt: skip


def read_entities(path: Path) -> tuple[str, dict[int, tuple[str, str]]]:
    """The schema and the entities this module needs, as (CLASS, raw arguments)."""
    keep = frozenset(_KEEP) | _ELEMENT_CLASSES | {c.upper() for _, (_, _, t) in KINDS.items() for c in t}
    out: dict[int, tuple[str, str]] = {}
    schema = ""
    buffer = ""
    with path.open("r", encoding="latin-1") as handle:
        for line in handle:
            if not schema and "FILE_SCHEMA" in line:
                found = re.search(r"'([A-Z0-9_]+)'", line)
                schema = found.group(1) if found else ""
            if not buffer and not line.startswith("#"):
                continue
            buffer += line
            if not buffer.rstrip().endswith(";"):
                continue
            match = _LINE.match(buffer.strip())
            buffer = ""
            if match and match.group(2) in keep:
                out[int(match.group(1))] = (match.group(2), match.group(3))
    return schema, out


def _unit_m(entities: dict[int, tuple[str, str]]) -> float | None:
    prefix = {"MILLI": 1e-3, "CENTI": 1e-2, "DECI": 1e-1, "KILO": 1e3, "$": 1.0}
    for cls, raw in entities.values():
        if cls != "IFCUNITASSIGNMENT":
            continue
        for ref in _refs(raw):
            unit = entities.get(ref)
            if unit is None:
                continue
            args = split_args(unit[1])
            if unit[0] == "IFCSIUNIT" and args[1] == ".LENGTHUNIT." and args[3] == ".METRE.":
                return prefix.get(args[2].strip("."), 1.0)
            if unit[0] == "IFCCONVERSIONBASEDUNIT" and args[1] == ".LENGTHUNIT.":
                measure = entities.get(_refs(args[3])[0]) if _refs(args[3]) else None
                if measure is not None:
                    value = _floats(split_args(measure[1])[0])
                    return value[0] if value else None
    return None


class _Placements:
    """World matrices of IFCLOCALPLACEMENT chains, read from the text."""

    def __init__(self, entities: dict[int, tuple[str, str]]) -> None:
        self.e = entities
        self.cache: dict[int, np.ndarray] = {}

    def _point(self, ref: int) -> np.ndarray:
        raw = self.e[ref][1]
        values = _floats(raw)
        return np.array([*values, 0.0, 0.0, 0.0][:3], dtype=float)

    def _direction(self, raw: str, default: tuple[float, float, float]) -> np.ndarray:
        refs = _refs(raw)
        if not refs:
            return np.array(default, dtype=float)
        values = _floats(self.e[refs[0]][1])
        v = np.array([*values, 0.0, 0.0, 0.0][:3], dtype=float)
        n = np.linalg.norm(v)
        return v / n if n > 0 else np.array(default, dtype=float)

    def _axis(self, ref: int) -> np.ndarray:
        args = split_args(self.e[ref][1])
        origin = self._point(_refs(args[0])[0])
        z = self._direction(args[1], (0.0, 0.0, 1.0))
        x = self._direction(args[2], (1.0, 0.0, 0.0))
        x = x - np.dot(x, z) * z
        x = x / (np.linalg.norm(x) or 1.0)
        y = np.cross(z, x)
        m = np.eye(4)
        m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = x, y, z, origin
        return m

    def world(self, ref: int) -> np.ndarray:
        if ref in self.cache:
            return self.cache[ref]
        cls, raw = self.e[ref]
        if cls != "IFCLOCALPLACEMENT":
            msg = f"placement #{ref} is {cls}"
            raise ValueError(msg)
        args = split_args(raw)
        local = self._axis(_refs(args[1])[0])
        parent = _refs(args[0])
        m = self.world(parent[0]) @ local if parent else local
        self.cache[ref] = m
        return m


def read_truth(path: Path) -> Truth:  # noqa: C901, PLR0912, PLR0915 - one pass per relation kind
    schema, e = read_entities(path)
    truth = Truth(schema=schema, unit_m=_unit_m(e))
    type_class: dict[int, str] = {}
    type_name: dict[int, str] = {}
    for sid, (cls, raw) in e.items():
        if cls in _ELEMENT_CLASSES:
            truth.kinds[sid] = _CLASS_KIND.get(cls, _GENERIC.get(cls, cls.lower()))
            truth.guid[sid] = _decode(split_args(raw)[0])
        elif cls.endswith("TYPE") and cls in _TYPE_KIND:
            type_class[sid] = cls
            type_name[sid] = _decode(split_args(raw)[2])
    for cls, raw in e.values():
        if cls != "IFCRELDEFINESBYTYPE":
            continue
        args = split_args(raw)
        kind_ref = _refs(args[5])
        if not kind_ref:
            continue
        for obj in _refs(args[4]):
            if obj not in truth.kinds:
                continue
            truth.type_name[obj] = type_name.get(kind_ref[0], "")
            current = truth.kinds[obj]
            typed = _TYPE_KIND.get(type_class.get(kind_ref[0], ""))
            # an IFC4 class names the kind; an IFC2X3 generic class takes the kind of its type
            if typed and (current in _GENERIC.values() or current == "flow_controller"):
                truth.kinds[obj] = typed
    # IFC4 types: IfcRelDefinesByType as above. Storeys:
    storeys = {sid: _decode(split_args(raw)[2]) for sid, (cls, raw) in e.items() if cls == "IFCBUILDINGSTOREY"}
    parent: dict[int, int] = {}
    for cls, raw in e.values():
        if cls == "IFCRELAGGREGATES":
            args = split_args(raw)
            whole = _refs(args[4])
            for part in _refs(args[5]):
                if whole:
                    parent[part] = whole[0]
    placed: dict[int, str] = {}  # any contained object -> its storey
    for cls, raw in e.values():
        if cls != "IFCRELCONTAINEDINSPATIALSTRUCTURE":
            continue
        args = split_args(raw)
        structure = _refs(args[5])[0]
        while structure not in storeys and structure in parent:
            structure = parent[structure]
        if structure in storeys:
            for obj in _refs(args[4]):
                placed[obj] = storeys[structure]
    for obj in truth.kinds:  # a part of an assembly sits on the storey of the assembly
        node, hops = obj, 0
        while node not in placed and node in parent and hops < 8:
            node, hops = parent[node], hops + 1
        if node in placed:
            truth.storey[obj] = placed[node]
    systems = {sid: _decode(split_args(raw)[2]) for sid, (cls, raw) in e.items()
               if cls in ("IFCSYSTEM", "IFCDISTRIBUTIONSYSTEM", "IFCBUILDINGSYSTEM", "IFCDISTRIBUTIONCIRCUIT")}  # fmt: skip
    for cls, raw in e.values():
        if cls != "IFCRELASSIGNSTOGROUP":
            continue
        args = split_args(raw)
        group = _refs(args[6])
        if group and group[0] in systems:
            for obj in _refs(args[4]):
                if obj in truth.kinds:
                    truth.systems.setdefault(obj, []).append(systems[group[0]])
    if truth.systems:
        truth.system_source = "IfcSystem"
    else:
        names = {}
        for sid, (cls, raw) in e.items():
            if cls == "IFCPROPERTYSINGLEVALUE":
                args = split_args(raw)
                if _decode(args[0]) in SYSTEM_NAME_PROPS:
                    inner = re.match(r"^[A-Z]+\((.*)\)$", args[2])
                    names[sid] = _decode(inner.group(1)) if inner else ""
        pset_name: dict[int, str] = {}
        for sid, (cls, raw) in e.items():
            if cls == "IFCPROPERTYSET":
                hit = [names[r] for r in _refs(split_args(raw)[4]) if r in names]
                if hit and hit[0]:
                    pset_name[sid] = hit[0]
        for cls, raw in e.values():
            if cls == "IFCRELDEFINESBYPROPERTIES":
                args = split_args(raw)
                pset = _refs(args[5])
                if pset and pset[0] in pset_name:
                    labels = [x.strip() for x in pset_name[pset[0]].split(",") if x.strip()]
                    for obj in _refs(args[4]):
                        if obj in truth.kinds and obj not in truth.systems:
                            truth.systems[obj] = labels
        if truth.systems:
            truth.system_source = "property"
    # ports: IFC2X3 IfcRelConnectsPortToElement(port, element); IFC4 IfcRelNests(element, (ports))
    ports_of: dict[int, list[int]] = defaultdict(list)
    port_ids = {sid for sid, (cls, _) in e.items() if cls == "IFCDISTRIBUTIONPORT"}
    for cls, raw in e.values():
        args = split_args(raw)
        if cls == "IFCRELCONNECTSPORTTOELEMENT":
            port, element = _refs(args[4]), _refs(args[5])
            if port and element:
                ports_of[element[0]].append(port[0])
        elif cls == "IFCRELNESTS":
            host = _refs(args[4])
            if host and host[0] in truth.kinds:
                ports_of[host[0]].extend(p for p in _refs(args[5]) if p in port_ids)
    placements = _Placements(e)
    for element, ports in ports_of.items():
        if truth.kinds.get(element) not in SEGMENT_KINDS or len(set(ports)) != 2:
            continue
        with contextlib.suppress(Exception):
            points = []
            for port in dict.fromkeys(ports):
                placement = _refs(split_args(e[port][1])[5])[0]
                points.append(placements.world(placement)[:3, 3])
            if truth.unit_m is not None:
                truth.port_length_m[element] = float(np.linalg.norm(points[0] - points[1])) * truth.unit_m
    return truth


def truth_mesh_lengths(path: Path, guids: set[str], threads: int = 4) -> dict[str, float]:
    """The axis extent (metres) of the triangulated body of each segment, from the OCC kernel, when it is clear."""
    import ifcopenshell  # noqa: PLC0415
    import ifcopenshell.geom  # noqa: PLC0415

    model = ifcopenshell.open(str(path))
    targets = [model.by_guid(g) for g in guids]
    targets = [t for t in targets if t is not None]
    if not targets:
        return {}
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    out: dict[str, float] = {}
    iterator = ifcopenshell.geom.iterator(settings, model, threads, include=targets)
    if not iterator.initialize():
        return out
    while True:
        shape = iterator.get()
        with contextlib.suppress(Exception):
            geometry = getattr(shape, "geometry")  # noqa: B009 - no stub
            verts = np.array(geometry.verts, dtype=float).reshape(-1, 3)  # metres: the kernel converts units
            if len(verts) >= 4:
                centred = verts - verts.mean(axis=0)
                _, _, vectors = np.linalg.svd(centred, full_matrices=False)
                spans = np.ptp(centred @ vectors.T, axis=0)
                guid = str(getattr(shape, "guid"))  # noqa: B009
                if spans[0] > 0 and spans[1] < 0.6 * spans[0]:
                    out[guid] = float(spans[0])  # a long segment: the axis is the long extent
                elif spans[1] > 0.95 * spans[0] and spans[2] < 0.8 * spans[1]:
                    out[guid] = float(spans[2])  # a short round segment: a disc, the axis is the short extent
        if not iterator.next():
            break
    return out


def close(a: float, b: float, rel: float = 0.02) -> bool:
    return math.isclose(a, b, rel_tol=rel, abs_tol=1e-6)
