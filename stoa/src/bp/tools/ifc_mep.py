"""Typed queries on the building services (MEP) of an IFC model: pipes, ducts, fittings, valves, terminals, systems.

The rules:
- An element is a distribution element (`IfcDistributionElement` and its subtypes). Its kind comes from its IFC4
  class (`IfcPipeSegment`), else from its type object (IFC2X3: an `IfcFlowSegment` typed by `IfcPipeSegmentType`).
- A segment length comes from a quantity set (`Qto_*BaseQuantities`, `BaseQuantities`), else from a property of
  the element (Revit writes `Length` or `Länge`), else from the geometry (the depth of an extrusion, the length of
  an axis curve, or the long extent of the faceted body). Each value says which source it came from.
- Units come from the project units of the file. Nothing is guessed: a value in the project length unit is
  multiplied by the unit scale of the file.
- `length_check` compares the property or quantity length with the geometry length on a sample of segments. When
  they do not agree, every length result says so and the agent must not give the length as sure.
- An element belongs to a system through `IfcRelAssignsToGroup` (an `IfcSystem` that is not a zone). A model with
  no `IfcSystem` (older Revit exports) names the system in a property such as `System Name`; the result says so.
All functions are pure on a model that `ifc_model.open_model` returned. Nothing here reads a label or a key.
"""

from __future__ import annotations

import contextlib
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import ifcopenshell.util.placement as up
import ifcopenshell.util.unit as uu
import numpy as np

from bp.tools import ifc_model

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ifcopenshell import entity_instance
    from shapely.geometry.base import BaseGeometry

    from bp.tools.ifc_model import IfcModel

# ----------------------------------------------------------------------------- kinds

# kind -> (entity id prefix, plain plural label, IFC4 element classes, IFC2X3 and IFC4 type classes)
KINDS: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "pipe": ("pipe segments", ("IfcPipeSegment",), ("IfcPipeSegmentType",)),
    "pipe_fitting": ("pipe fittings", ("IfcPipeFitting",), ("IfcPipeFittingType",)),
    "duct": ("duct segments", ("IfcDuctSegment",), ("IfcDuctSegmentType",)),
    "duct_fitting": ("duct fittings", ("IfcDuctFitting",), ("IfcDuctFittingType",)),
    "cable_carrier": ("cable carrier segments (trays, conduits)", ("IfcCableCarrierSegment",), ("IfcCableCarrierSegmentType",)),
    "cable_carrier_fitting": ("cable carrier fittings", ("IfcCableCarrierFitting",), ("IfcCableCarrierFittingType",)),
    "cable": ("cable segments", ("IfcCableSegment",), ("IfcCableSegmentType",)),
    "cable_fitting": ("cable fittings", ("IfcCableFitting",), ("IfcCableFittingType",)),
    "junction_box": ("junction boxes", ("IfcJunctionBox",), ("IfcJunctionBoxType",)),
    "valve": ("valves", ("IfcValve",), ("IfcValveType",)),
    "damper": ("dampers", ("IfcDamper",), ("IfcDamperType",)),
    "air_terminal_box": ("air terminal boxes", ("IfcAirTerminalBox",), ("IfcAirTerminalBoxType",)),
    "flow_meter": ("flow meters", ("IfcFlowMeter",), ("IfcFlowMeterType",)),
    "flow_controller": ("flow controllers with no type", ("IfcFlowController",), ()),
    "switching_device": ("switches", ("IfcSwitchingDevice",), ("IfcSwitchingDeviceType",)),
    "protective_device": ("protective devices", ("IfcProtectiveDevice",), ("IfcProtectiveDeviceType",)),
    "electric_time_control": ("electric time controls", ("IfcElectricTimeControl",), ("IfcElectricTimeControlType",)),
    "pump": ("pumps", ("IfcPump",), ("IfcPumpType",)),
    "fan": ("fans", ("IfcFan",), ("IfcFanType",)),
    "compressor": ("compressors", ("IfcCompressor",), ("IfcCompressorType",)),
    "tank": ("tanks", ("IfcTank",), ("IfcTankType",)),
    "filter": ("filters", ("IfcFilter",), ("IfcFilterType",)),
    "duct_silencer": ("duct silencers", ("IfcDuctSilencer",), ("IfcDuctSilencerType",)),
    "interceptor": ("interceptors", ("IfcInterceptor",), ("IfcInterceptorType",)),
    "sanitary_terminal": ("sanitary terminals", ("IfcSanitaryTerminal",), ("IfcSanitaryTerminalType",)),
    "air_terminal": ("air terminals", ("IfcAirTerminal",), ("IfcAirTerminalType",)),
    "waste_terminal": ("waste terminals", ("IfcWasteTerminal",), ("IfcWasteTerminalType",)),
    "stack_terminal": ("stack terminals", ("IfcStackTerminal",), ("IfcStackTerminalType",)),
    "fire_suppression_terminal": ("fire suppression terminals", ("IfcFireSuppressionTerminal",), ("IfcFireSuppressionTerminalType",)),
    "space_heater": ("space heaters (radiators)", ("IfcSpaceHeater",), ("IfcSpaceHeaterType",)),
    "light_fixture": ("light fixtures", ("IfcLightFixture",), ("IfcLightFixtureType",)),
    "lamp": ("lamps", ("IfcLamp",), ("IfcLampType",)),
    "outlet": ("outlets", ("IfcOutlet",), ("IfcOutletType",)),
    "electric_appliance": ("electric appliances", ("IfcElectricAppliance",), ("IfcElectricApplianceType",)),
    "audio_visual": ("audio visual appliances", ("IfcAudioVisualAppliance",), ("IfcAudioVisualApplianceType",)),
    "communications": ("communications appliances", ("IfcCommunicationsAppliance",), ("IfcCommunicationsApplianceType",)),
    "medical_device": ("medical devices", ("IfcMedicalDevice",), ("IfcMedicalDeviceType",)),
    "distribution_board": ("distribution boards", ("IfcElectricDistributionBoard", "IfcElectricDistributionPoint"), ("IfcElectricDistributionBoardType",)),
    "boiler": ("boilers", ("IfcBoiler",), ("IfcBoilerType",)),
    "chiller": ("chillers", ("IfcChiller",), ("IfcChillerType",)),
    "coil": ("coils", ("IfcCoil",), ("IfcCoilType",)),
    "heat_exchanger": ("heat exchangers", ("IfcHeatExchanger",), ("IfcHeatExchangerType",)),
    "heat_recovery": ("air-to-air heat recovery units", ("IfcAirToAirHeatRecovery",), ("IfcAirToAirHeatRecoveryType",)),
    "unitary_equipment": ("unitary equipment", ("IfcUnitaryEquipment",), ("IfcUnitaryEquipmentType",)),
    "cooling_tower": ("cooling towers", ("IfcCoolingTower",), ("IfcCoolingTowerType",)),
    "humidifier": ("humidifiers", ("IfcHumidifier",), ("IfcHumidifierType",)),
    "evaporative_cooler": ("evaporative coolers", ("IfcEvaporativeCooler",), ("IfcEvaporativeCoolerType",)),
    "burner": ("burners", ("IfcBurner",), ("IfcBurnerType",)),
    "transformer": ("transformers", ("IfcTransformer",), ("IfcTransformerType",)),
    "electric_motor": ("electric motors", ("IfcElectricMotor",), ("IfcElectricMotorType",)),
    "electric_generator": ("electric generators", ("IfcElectricGenerator",), ("IfcElectricGeneratorType",)),
    "motor_connection": ("motor connections", ("IfcMotorConnection",), ("IfcMotorConnectionType",)),
    "electric_storage": ("electric storage devices", ("IfcElectricFlowStorageDevice",), ("IfcElectricFlowStorageDeviceType",)),
    "solar_device": ("solar devices", ("IfcSolarDevice",), ("IfcSolarDeviceType",)),
    "sensor": ("sensors", ("IfcSensor",), ("IfcSensorType",)),
    "actuator": ("actuators", ("IfcActuator",), ("IfcActuatorType",)),
    "alarm": ("alarms", ("IfcAlarm",), ("IfcAlarmType",)),
    "controller": ("controllers", ("IfcController",), ("IfcControllerType",)),
    "flow_instrument": ("flow instruments", ("IfcFlowInstrument",), ("IfcFlowInstrumentType",)),
    "unitary_control": ("unitary control elements", ("IfcUnitaryControlElement",), ("IfcUnitaryControlElementType",)),
}  # fmt: skip
SEGMENT_KINDS = frozenset({"pipe", "duct", "cable_carrier", "cable", "flow_segment"})

_CLASS_KIND = {cls: kind for kind, (_, classes, _) in KINDS.items() for cls in classes}
_TYPE_KIND = {cls: kind for kind, (_, _, types) in KINDS.items() for cls in types}

# Property names in the languages of the public models (English, German, Dutch, French, Italian, Spanish, Nordic).
LENGTH_NAMES = ("Length", "Länge", "Lengte", "Longueur", "Lunghezza", "Longitud", "Pituus", "Längd", "Lengde", "Længde")
SIZE_NAMES = ("Size", "Größe", "Grootte", "Taille", "Dimensione", "Tamaño", "Koko", "Storlek", "Størrelse", "Overall Size")
SYSTEM_NAME_NAMES = ("System Name", "Systemname", "Systeemnaam", "Nom du système", "Nome sistema", "Nombre de sistema")
SYSTEM_TYPE_NAMES = ("System Type", "Systemtyp", "Systeemtype", "Type de système", "Tipo di sistema", "Tipo de sistema")
SYSTEM_CLASS_NAMES = ("System Classification", "Systemklassifizierung", "Systeemclassificatie", "Classification du système")
DIAMETER_NAMES = ("NominalDiameter",)
_WANTED = frozenset((*LENGTH_NAMES, *SIZE_NAMES, *SYSTEM_NAME_NAMES, *SYSTEM_TYPE_NAMES, *SYSTEM_CLASS_NAMES, *DIAMETER_NAMES))

LengthSource = Literal["qto", "property", "geometry", "none"]
GroupBy = Literal["none", "type", "family", "storey", "system", "system_type", "size", "material", "predefined_type", "class"]
GROUPS: tuple[str, ...] = ("none", "type", "family", "storey", "system", "system_type", "size", "material",
                           "predefined_type", "class")  # fmt: skip
NONE_LABEL = "(not stated)"
AGREE_REL = 0.02  # a property length agrees with the geometry within 2%
AGREE_ABS_M = 0.01  # or within 1 cm, for very short pieces


def kind_of(element: entity_instance, type_object: entity_instance | None) -> str:
    """The plain kind of a distribution element: its IFC4 class, else its type class, else its own class."""
    cls = element.is_a()
    if cls in _CLASS_KIND and cls != "IfcFlowController":
        return _CLASS_KIND[cls]
    if type_object is not None and type_object.is_a() in _TYPE_KIND:
        return _TYPE_KIND[type_object.is_a()]
    if cls in _CLASS_KIND:
        return _CLASS_KIND[cls]
    # IfcFlowSegment -> flow_segment, IfcDistributionControlElement -> distribution_control_element
    return re.sub(r"(?<!^)(?=[A-Z])", "_", cls.removeprefix("Ifc")).lower()


def kind_label(kind: str) -> str:
    return KINDS[kind][0] if kind in KINDS else kind.replace("_", " ")


def entity_id(kind: str, global_id: str) -> str:
    """`pipe:<GlobalId>`, `valve:<GlobalId>`, ... the kind is the prefix."""
    return f"{kind}:{global_id}"


# ----------------------------------------------------------------------------- the index


@dataclass
class MepElement:
    global_id: str
    step_id: int
    ifc_class: str
    kind: str
    name: str
    type_name: str  # the type object name, else ObjectType, else the name (as ifc_model.type_name)
    family: str  # the part before ':' of a Revit 'Family:Type' name
    predefined_type: str
    storey: str
    systems: tuple[str, ...]
    system_types: tuple[str, ...]
    system_source: Literal["IfcSystem", "property", "none"]
    size: str
    material: str
    length_raw: float | None = None  # in the project length unit
    length_m: float | None = None
    length_source: LengthSource = "none"
    length_detail: str = ""  # the quantity or property name, or the geometry method


@dataclass
class SystemInfo:
    key: str  # the entity id: system:<GlobalId>, or system:<name> for a property system
    name: str
    ifc_class: str
    system_type: str  # ObjectType, or PredefinedType of an IfcDistributionSystem
    predefined_type: str
    source: Literal["IfcSystem", "property"]
    members: list[int] = field(default_factory=list)  # step ids of the distribution elements
    serves: tuple[str, ...] = ()  # buildings or sites named by IfcRelServicesBuildings
    parents: tuple[str, ...] = ()  # systems that group this one


@dataclass
class LengthCheck:
    compared: int
    agree: int
    median_ratio: float | None  # property length / geometry length
    status: Literal["confirmed", "disagree", "unchecked", "geometry_only", "none"]
    note: str


@dataclass
class MepIndex:
    model: IfcModel
    unit_name: str  # the project length unit, such as MILLIMETRE
    elements: list[MepElement]
    systems: list[SystemInfo]
    by_step: dict[int, MepElement]
    ports: int
    connected_ports: int
    _check: LengthCheck | None = None
    port_hosts: dict[int, list[entity_instance]] = field(default_factory=dict)  # element step id -> its ports


def length_unit_name(model: IfcModel) -> str:
    """The project length unit as the file writes it, such as 'MILLIMETRE' or 'FOOT'."""
    unit = None
    with contextlib.suppress(Exception):
        unit = uu.get_project_unit(model.file, "LENGTHUNIT")
    if unit is None:
        return "unknown"
    if unit.is_a("IfcSIUnit"):
        return f"{unit.Prefix or ''}{unit.Name}"
    return str(getattr(unit, "Name", "") or unit.is_a()).upper()


def _value(prop: entity_instance) -> object:
    nominal = getattr(prop, "NominalValue", None)
    return getattr(nominal, "wrappedValue", None) if nominal is not None else None


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _read_set(definition: entity_instance, props: dict[str, object], qtos: dict[str, float]) -> None:
    """Copy the wanted single values of a property set, and the length quantities of a quantity set."""
    if definition.is_a("IfcPropertySet"):
        for prop in definition.HasProperties or ():
            if prop.is_a("IfcPropertySingleValue") and prop.Name in _WANTED and prop.Name not in props:
                value = _value(prop)
                if value not in (None, "") and value != prop.Name:
                    props[prop.Name] = value
    elif definition.is_a("IfcElementQuantity"):
        for quantity in definition.Quantities or ():
            if quantity.is_a("IfcQuantityLength") and quantity.Name in LENGTH_NAMES and quantity.Name not in qtos:
                number = _number(quantity.LengthValue)
                if number is not None:
                    qtos[quantity.Name] = number


def _material_names(material: entity_instance | None) -> list[str]:  # noqa: PLR0911 - one return per material kind
    if material is None:
        return []
    if material.is_a("IfcMaterial"):
        return [str(material.Name)] if material.Name else []
    if material.is_a("IfcMaterialList"):
        return [n for m in material.Materials or () for n in _material_names(m)]
    if material.is_a("IfcMaterialLayerSetUsage"):
        return _material_names(material.ForLayerSet)
    if material.is_a("IfcMaterialLayerSet"):
        return [n for layer in material.MaterialLayers or () for n in _material_names(layer.Material)]
    if material.is_a("IfcMaterialProfileSetUsage"):
        return _material_names(material.ForProfileSet)
    if material.is_a("IfcMaterialProfileSet"):
        return [n for p in material.MaterialProfiles or () for n in _material_names(p.Material)]
    if material.is_a("IfcMaterialConstituentSet"):
        return [n for c in material.MaterialConstituents or () for n in _material_names(c.Material)]
    if material.is_a("IfcMaterialLayer") or material.is_a("IfcMaterialProfile") or material.is_a("IfcMaterialConstituent"):
        return _material_names(material.Material)
    return []


def _type_of(element: entity_instance) -> entity_instance | None:
    """The type object (IFC4 IsTypedBy, IFC2X3 IsDefinedBy with IfcRelDefinesByType)."""
    for rel in getattr(element, "IsTypedBy", None) or ():
        return rel.RelatingType
    for rel in getattr(element, "IsDefinedBy", None) or ():
        if rel.is_a("IfcRelDefinesByType"):
            return rel.RelatingType
    return None


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _first(props: dict[str, object], names: tuple[str, ...]) -> object:
    for name in names:
        if name in props:
            return props[name]
    return None


def build_index(model: IfcModel) -> MepIndex:  # noqa: C901, PLR0912, PLR0915 - one pass per relation kind
    """Read every distribution element of the model once, with its type, storey, systems, size and length."""
    elements = ifc_model.by_type(model, "IfcDistributionElement")
    wanted = {int(e.id()) for e in elements}

    props: dict[int, dict[str, object]] = defaultdict(dict)
    qtos: dict[int, dict[str, float]] = defaultdict(dict)
    for rel in ifc_model.by_type(model, "IfcRelDefinesByProperties"):
        targets = [int(o.id()) for o in rel.RelatedObjects or () if int(o.id()) in wanted]
        if not targets:
            continue
        definition = rel.RelatingPropertyDefinition
        got_props: dict[str, object] = {}
        got_qtos: dict[str, float] = {}
        with contextlib.suppress(Exception):
            _read_set(definition, got_props, got_qtos)
        for target in targets:
            for k, v in got_props.items():
                props[target].setdefault(k, v)
            for k, v in got_qtos.items():
                qtos[target].setdefault(k, v)

    materials: dict[int, list[str]] = {}
    for rel in ifc_model.by_type(model, "IfcRelAssociatesMaterial"):
        names = list(dict.fromkeys(_material_names(rel.RelatingMaterial)))
        if names:
            for obj in rel.RelatedObjects or ():
                materials.setdefault(int(obj.id()), names)

    systems: list[SystemInfo] = []
    member_systems: dict[int, list[SystemInfo]] = defaultdict(list)
    system_of_group: dict[int, SystemInfo] = {}
    for system in ifc_model.by_type(model, "IfcSystem"):
        if system.is_a("IfcZone") or system.is_a("IfcStructuralAnalysisModel"):
            continue
        predefined = _text(getattr(system, "PredefinedType", None))
        info = SystemInfo(
            key=f"system:{system.GlobalId}",
            name=_text(system.Name) or system.is_a(),
            ifc_class=system.is_a(),
            system_type=_text(system.ObjectType) or (predefined if predefined not in ("", "NOTDEFINED", "USERDEFINED") else ""),
            predefined_type=predefined,
            source="IfcSystem",
        )
        serves: list[str] = []
        for rel in getattr(system, "ServicesBuildings", None) or ():
            serves += [_text(b.Name) or b.is_a() for b in rel.RelatedBuildings or ()]
        info.serves = tuple(dict.fromkeys(serves))
        systems.append(info)
        system_of_group[int(system.id())] = info
    for rel in ifc_model.by_type(model, "IfcRelAssignsToGroup"):
        info = system_of_group.get(int(rel.RelatingGroup.id()))
        if info is None:
            continue
        for obj in rel.RelatedObjects or ():
            key = int(obj.id())
            if key in wanted:
                member_systems[key].append(info)
                info.members.append(key)
            elif key in system_of_group:
                child = system_of_group[key]
                child.parents = (*child.parents, info.name)
    with contextlib.suppress(Exception):
        for rel in ifc_model.by_type(model, "IfcRelAggregates"):  # IFC4: a system made of subsystems
            info = system_of_group.get(int(rel.RelatingObject.id()))
            if info is not None:
                for obj in rel.RelatedObjects or ():
                    child = system_of_group.get(int(obj.id()))
                    if child is not None:
                        child.parents = (*child.parents, info.name)

    port_hosts = _port_hosts(model)
    property_systems: dict[str, SystemInfo] = {}
    out: list[MepElement] = []
    for element in elements:
        key = int(element.id())
        kind_type = _type_of(element)
        own = props.get(key, {})
        type_props: dict[str, object] = {}
        type_qtos: dict[str, float] = {}
        if kind_type is not None:
            for definition in getattr(kind_type, "HasPropertySets", None) or ():
                with contextlib.suppress(Exception):
                    _read_set(definition, type_props, type_qtos)
        merged = {**type_props, **own}
        type_name = ifc_model.type_name(element)
        object_type = _text(getattr(element, "ObjectType", None))
        own_name = _text(element.Name)
        family_source = next((t for t in (object_type, own_name) if ":" in t), type_name)
        family = family_source.split(":")[0].strip() or type_name
        predefined = _text(getattr(element, "PredefinedType", None))
        if predefined in ("", "NOTDEFINED") and kind_type is not None:
            predefined = _text(getattr(kind_type, "PredefinedType", None)) or predefined
        storey = ifc_model.storey_of(model, element)
        found = list(member_systems.get(key, []))
        system_source: Literal["IfcSystem", "property", "none"] = "IfcSystem" if found else "none"
        if not found:
            name = _text(_first(own, SYSTEM_NAME_NAMES))
            kind_text = _text(_first(own, SYSTEM_TYPE_NAMES)) or _text(_first(own, SYSTEM_CLASS_NAMES))
            # Revit writes 'A,B' when an element joins two systems: one label each.
            labels = [x.strip() for x in (name or kind_text).split(",") if x.strip()]
            kinds = [x.strip() for x in kind_text.split(",") if x.strip()]
            for i, label in enumerate(labels):
                info = property_systems.get(label)
                if info is None:
                    one_kind = kinds[i] if len(kinds) == len(labels) else (kinds[0] if len(kinds) == 1 else "")
                    info = SystemInfo(key=f"system:{label}", name=label, ifc_class="(property)",
                                      system_type=one_kind, predefined_type="", source="property")  # fmt: skip
                    property_systems[label] = info
                info.members.append(key)
                found.append(info)
            system_source = "property" if found else "none"
        size = _text(_first(own, SIZE_NAMES)) or _text(_first(type_props, SIZE_NAMES))
        if not size:
            diameter = _number(_first(merged, DIAMETER_NAMES))
            if diameter is not None:
                size = f"DN{round(diameter * model.length_scale * 1000)}"
        names = materials.get(key) or (materials.get(int(kind_type.id())) if kind_type is not None else None) or []
        out.append(
            MepElement(
                global_id=element.GlobalId,
                step_id=key,
                ifc_class=element.is_a(),
                kind=kind_of(element, kind_type),
                name=_text(element.Name),
                type_name=type_name,
                family=family,
                predefined_type=predefined,
                storey=_text(storey.Name) if storey is not None else "",
                systems=tuple(dict.fromkeys(s.name for s in found)),
                system_types=tuple(dict.fromkeys(s.system_type for s in found if s.system_type)),
                system_source=system_source,
                size=size,
                material=", ".join(names),
            )
        )
        record = out[-1]
        if record.kind in SEGMENT_KINDS:
            _set_length(model, record, element, qtos.get(key, {}) or type_qtos, own, port_hosts.get(key, []))
    systems.extend(property_systems.values())

    ports = ifc_model.by_type(model, "IfcDistributionPort")
    connected: set[int] = set()
    for rel in ifc_model.by_type(model, "IfcRelConnectsPorts"):
        connected.update((int(rel.RelatingPort.id()), int(rel.RelatedPort.id())))
    return MepIndex(model=model, unit_name=length_unit_name(model), elements=out, systems=systems,
                    by_step={e.step_id: e for e in out}, ports=len(ports), connected_ports=len(connected),
                    port_hosts=port_hosts)  # fmt: skip


def _port_hosts(model: IfcModel) -> dict[int, list[entity_instance]]:
    """The ports of each element: IfcRelNests in IFC4, IfcRelConnectsPortToElement in IFC2X3."""
    out: dict[int, list[entity_instance]] = defaultdict(list)
    for rel in ifc_model.by_type(model, "IfcRelConnectsPortToElement"):
        with contextlib.suppress(Exception):
            out[int(rel.RelatedElement.id())].append(rel.RelatingPort)
    for rel in ifc_model.by_type(model, "IfcRelNests"):
        with contextlib.suppress(Exception):
            ports = [o for o in rel.RelatedObjects or () if o.is_a("IfcDistributionPort")]
            if ports:
                out[int(rel.RelatingObject.id())].extend(ports)
    return out


def port_length(ports: list[entity_instance]) -> tuple[float, str] | None:
    """The distance between the two ports of a straight segment, in the project length unit."""
    unique = list({int(p.id()): p for p in ports}.values())
    if len(unique) != 2:
        return None
    points = []
    for port in unique:
        placement = getattr(port, "ObjectPlacement", None)
        if placement is None:
            return None
        points.append(np.asarray(up.get_local_placement(placement), dtype=float)[:3, 3])
    distance = float(np.linalg.norm(points[0] - points[1]))
    return (distance, "geometry: distance between the two ports") if distance > 0 else None


def _set_length(
    model: IfcModel,
    record: MepElement,
    element: entity_instance,
    qto: dict[str, float],
    own: dict[str, object],
    ports: list[entity_instance],
) -> None:
    for name in LENGTH_NAMES:
        if name in qto:
            record.length_raw, record.length_source, record.length_detail = qto[name], "qto", f"quantity {name}"
            break
    else:
        for name in LENGTH_NAMES:
            number = _number(own.get(name))
            if number is not None:
                record.length_raw, record.length_source, record.length_detail = number, "property", f"property {name}"
                break
        else:
            got = None
            with contextlib.suppress(Exception):
                got = port_length(ports)
            got = got or geometry_length(element)
            if got is not None:
                record.length_raw, record.length_source, record.length_detail = got[0], "geometry", got[1]
    if record.length_raw is not None:
        record.length_m = record.length_raw * model.length_scale


# ----------------------------------------------------------------------------- geometry lengths
# Read from the representation itself, with no geometry kernel: fast, and independent of the property values.


def _points(item: entity_instance) -> list[tuple[float, ...]]:
    """The vertices of a faceted body, a face set or a tessellation, in the coordinates of the representation."""
    out: list[tuple[float, ...]] = []
    if item.is_a("IfcFacetedBrep") or item.is_a("IfcFacetedBrepWithVoids"):
        shells = [item.Outer]
    elif item.is_a("IfcFaceBasedSurfaceModel"):
        shells = list(item.FbsmFaces or ())
    elif item.is_a("IfcShellBasedSurfaceModel"):
        shells = list(item.SbsmBoundary or ())
    elif item.is_a("IfcTriangulatedFaceSet") or item.is_a("IfcPolygonalFaceSet"):
        return [tuple(float(v) for v in p) for p in item.Coordinates.CoordList]
    else:
        return out
    for shell in shells:
        for face in getattr(shell, "CfsFaces", None) or ():
            for bound in face.Bounds or ():
                loop = bound.Bound
                if loop.is_a("IfcPolyLoop"):
                    out.extend(tuple(float(v) for v in p.Coordinates) for p in loop.Polygon)
    return out


def _curve_length(curve: entity_instance) -> float | None:
    if curve.is_a("IfcPolyline"):
        pts = np.array([p.Coordinates for p in curve.Points], dtype=float)
        return float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum()) if len(pts) > 1 else None
    if curve.is_a("IfcIndexedPolyCurve") and curve.Segments is None:
        pts = np.array(curve.Points.CoordList, dtype=float)
        return float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum()) if len(pts) > 1 else None
    if curve.is_a("IfcTrimmedCurve") and curve.BasisCurve.is_a("IfcLine"):
        a, b = curve.Trim1, curve.Trim2
        pa = next((x for x in a if hasattr(x, "Coordinates")), None)
        pb = next((x for x in b if hasattr(x, "Coordinates")), None)
        if pa is not None and pb is not None:
            return float(np.linalg.norm(np.array(pa.Coordinates, dtype=float) - np.array(pb.Coordinates, dtype=float)))
    return None


def _profile_extents(profile: entity_instance) -> tuple[float, float, bool] | None:
    """The two extents of a profile and whether it is round; None for a shape this reader does not know."""
    if profile.is_a("IfcCircleProfileDef"):  # also IfcCircleHollowProfileDef
        return 2 * float(profile.Radius), 2 * float(profile.Radius), True
    if profile.is_a("IfcRectangleProfileDef"):  # also the hollow and rounded rectangles
        return float(profile.XDim), float(profile.YDim), False
    if profile.is_a("IfcArbitraryClosedProfileDef"):
        curve = profile.OuterCurve
        if curve.is_a("IfcPolyline"):
            pts = np.array([p.Coordinates[:2] for p in curve.Points], dtype=float)
        elif curve.is_a("IfcIndexedPolyCurve"):
            pts = np.array([p[:2] for p in curve.Points.CoordList], dtype=float)
        else:
            return None
        if len(pts) < 3:
            return None
        centred = pts - pts.mean(axis=0)
        _, _, vectors = np.linalg.svd(centred, full_matrices=False)
        spans = np.ptp(centred @ vectors.T, axis=0)
        return float(spans[0]), float(spans[1]), False
    return None


def _extrusion_length(item: entity_instance, scale: float) -> tuple[float, str] | None:
    """The length of an extruded segment.

    A round profile is extruded along the axis, so the depth is the length. A rectangular duct is often drawn as its
    plan (length by width) extruded by its height, so the length is the longest of the three extents, and only when
    it is clearly the longest.
    """
    depth = float(item.Depth)
    extents = _profile_extents(item.SweptArea)
    if extents is None:
        return None
    a, b, round_profile = extents
    if round_profile:
        return depth * scale, "geometry: extrusion depth of a round profile"
    ordered = sorted((a, b, depth))
    if ordered[2] < 1.25 * ordered[1]:
        return None  # no clear long axis: a short piece
    method = "geometry: extrusion depth" if ordered[2] == depth else "geometry: long side of the extruded profile"
    return ordered[2] * scale, method


def _item_length(item: entity_instance, scale: float = 1.0) -> tuple[float, str] | None:  # noqa: PLR0911 - one per item kind
    """The length of one representation item, with the method."""
    if item.is_a("IfcMappedItem"):
        target = item.MappingTarget
        factor = float(getattr(target, "Scale", None) or 1.0)
        for inner in item.MappingSource.MappedRepresentation.Items:
            got = _item_length(inner, scale * factor)
            if got is not None:
                return got
        return None
    if item.is_a("IfcExtrudedAreaSolid"):
        return _extrusion_length(item, scale)
    if item.is_a("IfcBooleanResult"):
        return _item_length(item.FirstOperand, scale)
    if item.is_a("IfcSweptDiskSolid"):
        got = _curve_length(item.Directrix)
        return (got * scale, "geometry: swept disk directrix") if got is not None else None
    if item.is_a("IfcCurve"):
        got = _curve_length(item)
        return (got * scale, "geometry: axis curve") if got is not None else None
    pts = _points(item)
    if len(pts) >= 4:
        arr = np.array([p[:3] for p in pts if len(p) >= 3], dtype=float)
        if len(arr) >= 4:
            centred = arr - arr.mean(axis=0)
            _, values, vectors = np.linalg.svd(centred, full_matrices=False)
            spans = np.ptp(centred @ vectors.T, axis=0)
            if spans[0] > 0 and (len(spans) < 2 or spans[1] < 0.8 * spans[0]):
                return float(spans[0]) * scale, "geometry: long extent of the body"
            del values
    return None


def geometry_length(element: entity_instance) -> tuple[float, str] | None:
    """The length of a segment from its Axis representation, else its Body, in the project length unit.

    None when the body is not a straight extrusion or a faceted solid with one clear long axis (a short piece whose
    length is close to its width has no clear axis).
    """
    shape = getattr(element, "Representation", None)
    if shape is None:
        return None
    reps = sorted(shape.Representations or (), key=lambda r: r.RepresentationIdentifier != "Axis")
    for rep in reps:
        if rep.RepresentationIdentifier not in ("Axis", "Body", None):
            continue
        for item in rep.Items or ():
            got = None
            with contextlib.suppress(Exception):
                got = _item_length(item)
            if got is not None:
                return got
    return None


def length_check(index: MepIndex, sample: int = 300) -> LengthCheck:
    """Compare the quantity or property length with the geometry length on a spread sample of segments."""
    if index._check is not None:  # noqa: SLF001 - the cache of this module
        return index._check  # noqa: SLF001
    segs = [e for e in index.elements if e.kind in SEGMENT_KINDS]
    stated = [e for e in segs if e.length_source in ("qto", "property")]
    if not segs:
        check = LengthCheck(0, 0, None, "none", "the model has no segments")
    elif not stated:
        n = sum(1 for e in segs if e.length_source == "geometry")
        check = LengthCheck(0, 0, None, "geometry_only" if n else "none",
                            f"no quantity or property length; {n} of {len(segs)} segments measured from geometry")  # fmt: skip
    else:
        step = max(1, len(stated) // sample)
        ratios: list[float] = []
        agree = 0
        for record in stated[::step][:sample]:
            got = None
            with contextlib.suppress(Exception):
                got = port_length(index.port_hosts.get(record.step_id, []))
            got = got or geometry_length(index.model.file.by_id(record.step_id))
            if got is None or record.length_raw is None or got[0] <= 0:
                continue
            geo_m = got[0] * index.model.length_scale
            ratios.append(record.length_raw / got[0])
            if abs((record.length_m or 0.0) - geo_m) <= max(AGREE_REL * geo_m, AGREE_ABS_M):
                agree += 1
        median = float(np.median(ratios)) if ratios else None
        if len(ratios) < 5:
            check = LengthCheck(len(ratios), agree, median, "unchecked",
                                "too few segments have a geometry length to check the stated lengths")  # fmt: skip
        elif agree >= 0.9 * len(ratios):
            check = LengthCheck(len(ratios), agree, median, "confirmed",
                                f"the stated length agrees with the geometry on {agree} of {len(ratios)} sampled segments")  # fmt: skip
        else:
            check = LengthCheck(len(ratios), agree, median, "disagree",
                                f"the stated length agrees with the geometry on only {agree} of {len(ratios)} sampled "
                                f"segments (median ratio {median:.3f}); the lengths are not sure")  # fmt: skip
    index._check = check  # noqa: SLF001
    return check


# ----------------------------------------------------------------------------- queries


def _match(text: str, wanted: str) -> bool:
    return ifc_model.norm(wanted) in ifc_model.norm(text)


def select(
    index: MepIndex,
    kind: str = "all",
    storey: str | None = None,
    system: str | None = None,
    name: str | None = None,
) -> list[MepElement]:
    """The elements of a kind ('all', a kind, or 'segment' for every segment kind), filtered.

    `storey` matches the storey name exactly or loosely. `system` matches a system name or system type, and `name`
    a type, family or element name: an exact match when there is one, else a part of the text.
    """
    found = index.elements
    if kind == "segment":
        found = [e for e in found if e.kind in SEGMENT_KINDS]
    elif kind != "all":
        found = [e for e in found if e.kind == kind]
    if storey:
        exact = [e for e in found if e.storey == storey]
        found = exact or [e for e in found if ifc_model.norm(e.storey) == ifc_model.norm(storey)]
    if system:
        key = ifc_model.norm(system)
        exact = [e for e in found if any(ifc_model.norm(s) == key for s in (*e.systems, *e.system_types))]
        found = exact or [e for e in found if any(_match(s, system) for s in (*e.systems, *e.system_types))]
    if name:
        key = ifc_model.norm(name)
        exact = [e for e in found if any(ifc_model.norm(s) == key for s in (e.type_name, e.family, e.name))]
        found = exact or [e for e in found if any(_match(s, name) for s in (e.type_name, e.family, e.name))]
    return found


def group_key(element: MepElement, group_by: str) -> list[str]:  # noqa: PLR0911 - one return per group
    """The group labels of an element. A member of two systems counts in both."""
    if group_by == "type":
        return [element.type_name or NONE_LABEL]
    if group_by == "family":
        return [element.family or NONE_LABEL]
    if group_by == "storey":
        return [element.storey or "(no storey)"]
    if group_by == "system":
        return list(element.systems) or ["(no system)"]
    if group_by == "system_type":
        return list(element.system_types) or [NONE_LABEL]
    if group_by == "size":
        return [element.size or NONE_LABEL]
    if group_by == "material":
        return [element.material or NONE_LABEL]
    if group_by == "predefined_type":
        return [element.predefined_type or NONE_LABEL]
    if group_by == "class":
        return [kind_label(element.kind)]
    return ["all"]


@dataclass
class Group:
    key: str
    count: int
    length_m: float | None
    with_length: int
    sources: dict[str, int]
    members: list[MepElement]


def grouped(elements: Iterable[MepElement], group_by: str) -> list[Group]:
    """Groups with counts and length sums, largest count first."""
    buckets: dict[str, list[MepElement]] = defaultdict(list)
    for e in elements:
        for key in group_key(e, group_by):
            buckets[key].append(e)
    out = []
    for key, members in buckets.items():
        lengths = [m.length_m for m in members if m.length_m is not None]
        sources = Counter(m.length_source for m in members if m.length_m is not None)
        out.append(Group(key=key, count=len(members), length_m=math.fsum(lengths) if lengths else None,
                         with_length=len(lengths), sources=dict(sources), members=members))  # fmt: skip
    out.sort(key=lambda g: (-g.count, g.key))
    return out


def kind_counts(index: MepIndex) -> list[tuple[str, int]]:
    counter = Counter(e.kind for e in index.elements)
    return counter.most_common()


# ----------------------------------------------------------------------------- formatting


def fmt_count(n: int) -> str:
    """An integer as a report writes it: 10,957 (thousands with a comma), as the IFC-Bench answers do."""
    return f"{n:,}"


def pct(part: float, whole: float) -> str:
    return f"{100.0 * part / whole:.1f}%" if whole else "-"


def fmt_length(value_m: float | None) -> str:
    return "-" if value_m is None else f"{value_m:.2f} m"


def unit_suffix(unit_name: str) -> str:
    return {"MILLIMETRE": "mm", "CENTIMETRE": "cm", "METRE": "m", "FOOT": "ft", "INCH": "in"}.get(unit_name, unit_name)


# ----------------------------------------------------------------------------- location in spaces


@dataclass
class SpaceShape:
    global_id: str
    name: str
    long_name: str
    storey: str
    footprint: BaseGeometry  # in metres, world coordinates
    z_min: float
    z_max: float


def space_shapes(model: IfcModel) -> list[SpaceShape]:
    """The world footprint and height band of every space with a body, in metres."""
    import ifcopenshell.geom  # noqa: PLC0415 - the geometry kernel loads only for a location question
    from shapely.geometry import Polygon  # noqa: PLC0415
    from shapely.ops import unary_union  # noqa: PLC0415

    found = ifc_model.by_type(model, "IfcSpace")
    if not found:
        return []
    by_guid = {s.GlobalId: s for s in found}
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    out: list[SpaceShape] = []
    iterator = ifcopenshell.geom.iterator(settings, model.file, 4, include=found)
    if not iterator.initialize():
        return out
    while True:
        shape = iterator.get()
        with contextlib.suppress(Exception):
            geometry = getattr(shape, "geometry")  # noqa: B009 - the iterator result type has no stub
            verts = np.array(geometry.verts, dtype=float).reshape(-1, 3)
            faces = np.array(geometry.faces, dtype=int).reshape(-1, 3)
            polys = [Polygon(t) for t in verts[faces][:, :, :2]]
            polys = [p for p in polys if p.area > 1e-9]
            space = by_guid.get(str(getattr(shape, "guid")))  # noqa: B009
            if polys and space is not None:
                storey = ifc_model.storey_of(model, space)
                out.append(SpaceShape(global_id=space.GlobalId, name=_text(space.Name), long_name=_text(space.LongName),
                                      storey=_text(storey.Name) if storey is not None else "",
                                      footprint=unary_union(polys).buffer(0), z_min=float(verts[:, 2].min()),
                                      z_max=float(verts[:, 2].max())))  # fmt: skip
        if not iterator.next():
            break
    return out


@dataclass
class Location:
    space: str  # the space Name, or '' when none was found
    space_long_name: str
    space_global_id: str
    method: str  # "containment", "placement point inside the space", "placement point 0.12 m from the space"


def element_point_m(model: IfcModel, element: entity_instance) -> tuple[float, float, float] | None:
    """The world position of the placement of an element, in metres."""
    import ifcopenshell.util.placement as up  # noqa: PLC0415

    placement = getattr(element, "ObjectPlacement", None)
    if placement is None:
        return None
    with contextlib.suppress(Exception):
        matrix = up.get_local_placement(placement)
        x, y, z = (float(v) * model.length_scale for v in matrix[:3, 3])
        return (x, y, z)
    return None


NEAR_M = 0.35  # a wall-hung terminal sits up to a wall thickness outside the room outline


def locate(model: IfcModel, elements: list[entity_instance], shapes: list[SpaceShape] | None = None) -> list[Location]:
    """The space of each element: by spatial containment in an IfcSpace, else the space around its placement point."""
    from shapely.geometry import Point  # noqa: PLC0415

    shapes = space_shapes(model) if shapes is None else shapes
    out: list[Location] = []
    for element in elements:
        container = None
        with contextlib.suppress(Exception):
            import ifcopenshell.util.element as ue  # noqa: PLC0415

            container = ue.get_container(element)
        if container is not None and container.is_a("IfcSpace"):
            out.append(Location(_text(container.Name), _text(container.LongName), container.GlobalId, "containment"))
            continue
        point = element_point_m(model, element)
        if point is None or not shapes:
            out.append(Location("", "", "", "no placement or no space geometry"))
            continue
        flat = Point(point[0], point[1])
        band = [s for s in shapes if s.z_min - 0.5 <= point[2] <= s.z_max + 0.1]
        best: tuple[float, SpaceShape] | None = None
        for s in band:
            d = float(s.footprint.distance(flat))
            if best is None or d < best[0]:
                best = (d, s)
        if best is None or best[0] > NEAR_M:
            out.append(Location("", "", "", "the placement point is in no space"))
            continue
        d, s = best
        method = "placement point inside the space" if d == 0 else f"placement point {d:.2f} m from the space"
        out.append(Location(s.name, s.long_name, s.global_id, method))
    return out
