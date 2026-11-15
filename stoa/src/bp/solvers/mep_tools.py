"""Agent tools for the building services (MEP) of an IFC model: pipes, ducts, fittings, valves, terminals, systems.

Each tool returns rows with an `entity_id` (`pipe:<GlobalId>`, `valve:<GlobalId>`, `system:<GlobalId>`) and a
`report`: a plain text answer that the agent may submit as it is for a free-text question. A length says where it
came from (quantity set, property or geometry) and whether the geometry confirms it (`sure`).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from bp.agent.core import ToolOutput, ToolSpec
from bp.contract import Check, Evidence
from bp.tools import ifc_mep, ifc_model

if TYPE_CHECKING:
    from bp.tools.ifc_mep import MepElement, MepIndex

MAX_IDS = 40  # entity ids per group row
MAX_ROWS = 60  # groups in one result
MAX_ELEMENTS = 50
SURE = 0.95
UNSURE = 0.3


def _args(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


class Mep:
    """The MEP index of one model, built on the first call (a large model takes seconds)."""

    def __init__(self, model: ifc_model.IfcModel) -> None:
        self.model = model
        self._index: MepIndex | None = None
        self._shapes: list[ifc_mep.SpaceShape] | None = None

    @property
    def index(self) -> MepIndex:
        if self._index is None:
            self._index = ifc_mep.build_index(self.model)
        return self._index

    @property
    def shapes(self) -> list[ifc_mep.SpaceShape]:
        if self._shapes is None:
            self._shapes = ifc_mep.space_shapes(self.model)
        return self._shapes


def _filters(arguments: dict[str, Any]) -> dict[str, str | None]:
    return {k: (_text(arguments.get(k)) or None) for k in ("storey", "system", "name")}


def _filter_text(kind: str, filters: dict[str, str | None]) -> str:
    base = {"all": "all distribution elements", "segment": "all segments"}.get(kind) or ifc_mep.kind_label(kind)
    return base + _suffix(filters)


def _title(kind: str) -> str:
    if kind == "all":
        return "Distribution elements"
    if kind == "segment":
        return "Segments (pipes, ducts, cable carriers)"
    return ifc_mep.kind_label(kind).capitalize()


def _evidence(elements: list[MepElement]) -> tuple[Evidence, ...]:
    return tuple(Evidence(kind="ifc_element", ref=e.global_id, note=e.type_name) for e in elements[:60])


def _ids(elements: list[MepElement]) -> list[str]:
    return [ifc_mep.entity_id(e.kind, e.global_id) for e in elements[:MAX_IDS]]


def length_status(index: MepIndex, elements: list[MepElement]) -> tuple[bool, str, ifc_mep.LengthCheck]:
    """Whether a length sum over these segments is sure, and why."""
    check = ifc_mep.length_check(index)
    missing = sum(1 for e in elements if e.length_m is None)
    if not elements:
        return False, "no segments match", check
    if missing:
        return False, f"{missing} of {len(elements)} segments have no length; the sum is a lower bound", check
    sources = {e.length_source for e in elements}
    if sources == {"geometry"}:
        return True, "every length is measured from the geometry (the model states no length)", check
    if check.status == "confirmed":
        return True, check.note, check
    return False, check.note, check


def mep_tools(model: ifc_model.IfcModel) -> tuple[str, list[ToolSpec]]:  # noqa: C901, PLR0915 - the tools share one index
    """The MEP tools of a model, and one context line. No tools when the model has no distribution element."""
    count = len(ifc_model.by_type(model, "IfcDistributionElement"))
    if not count:
        return "", []
    mep = Mep(model)

    def overview(_arguments: dict[str, Any]) -> ToolOutput:
        index = mep.index
        total = len(index.elements)
        kinds = ifc_mep.kind_counts(index)
        rows: list[dict[str, Any]] = []
        lines = [f"Building services (MEP) components: {ifc_mep.fmt_count(total)} in total"]
        for k, n in kinds:
            label = ifc_mep.kind_label(k)
            rows.append({"kind": k, "label": label, "count": n, "percent": round(100 * n / total, 1)})
            lines.append(f"- {label.capitalize()}: {ifc_mep.fmt_count(n)} ({ifc_mep.pct(n, total)})")
        segments: list[dict[str, Any]] = []
        for kind in sorted({e.kind for e in index.elements if e.kind in ifc_mep.SEGMENT_KINDS}):
            found = ifc_mep.select(index, kind)
            lengths = [e.length_m for e in found if e.length_m is not None]
            sure, why, _check = length_status(index, found)
            length = round(sum(lengths), 2) if lengths else None
            segments.append({"kind": kind, "segments": len(found), "length_m": length, "with_length": len(lengths),
                             "sure": sure, "why": why})  # fmt: skip
            if length is not None:
                lines.append(f"Total length of {ifc_mep.kind_label(kind)}: {length:.2f} m "
                             f"({ifc_mep.fmt_count(len(found))} segments)")  # fmt: skip
        systems = list(index.systems)
        rate = round(100 * index.connected_ports / index.ports, 1) if index.ports else None
        lines.append(f"Systems: {len(systems)}")
        if index.ports:
            lines.append(f"Ports: {ifc_mep.fmt_count(index.ports)}, connected: {ifc_mep.fmt_count(index.connected_ports)} ({rate}%)")
        data = {
            "schema": str(model.file.schema), "length_unit": index.unit_name, "total": total, "kinds": rows,
            "segments": segments, "systems": len(systems),
            "system_source": "IfcSystem" if any(s.source == "IfcSystem" for s in systems) else (
                "property 'System Name' (the model has no IfcSystem)" if systems else "none"),
            "ports": index.ports, "connected_ports": index.connected_ports, "connected_percent": rate,
            "report": "\n".join(lines),
        }  # fmt: skip
        return ToolOutput(data=data)

    def count_tool(arguments: dict[str, Any]) -> ToolOutput:
        index = mep.index
        kind = _text(arguments.get("kind")) or "all"
        group_by = _text(arguments.get("group_by")) or "type"
        then_by = _text(arguments.get("then_by")) or "none"
        if group_by not in ifc_mep.GROUPS or then_by not in ifc_mep.GROUPS:
            return ToolOutput(ok=False, error=f"group_by must be one of {', '.join(ifc_mep.GROUPS)}")
        filters = _filters(arguments)
        found = ifc_mep.select(index, kind, **filters)
        if not found:
            present = ", ".join(k for k, _ in ifc_mep.kind_counts(index))
            return ToolOutput(data={"kind": kind, "total": 0, "groups": [],
                                    "note": f"no element matches; the kinds in this model are: {present}"})  # fmt: skip
        groups = ifc_mep.grouped(found, group_by)
        rows = []
        lines = [f"{_title(kind)}: {ifc_mep.fmt_count(len(found))} in total" + _suffix(filters)]
        for g in groups[:MAX_ROWS]:
            row: dict[str, Any] = {"key": g.key, "count": g.count, "percent": round(100 * g.count / len(found), 1),
                                   "entity_ids": _ids(g.members)}  # fmt: skip
            if group_by != "none":
                lines.append(f"- {g.key}: {ifc_mep.fmt_count(g.count)} ({ifc_mep.pct(g.count, len(found))})")
            if then_by != "none":
                inner = ifc_mep.grouped(g.members, then_by)
                row["by_" + then_by] = [{"key": i.key, "count": i.count} for i in inner[:MAX_ROWS]]
                lines += [f"  - {i.key}: {ifc_mep.fmt_count(i.count)}" for i in inner[:MAX_ROWS]]
            rows.append(row)
        data = {"kind": kind, "filter": _filter_text(kind, filters), "group_by": group_by, "total": len(found),
                "groups": rows, "more_groups": max(0, len(groups) - MAX_ROWS), "report": "\n".join(lines)}  # fmt: skip
        if group_by == "system" and any(e.system_source == "property" for e in found):
            data["note"] = "systems come from the 'System Name' property (the model has no IfcSystem for them)"
        return ToolOutput(data=data, evidence=_evidence(found))

    def length_tool(arguments: dict[str, Any]) -> ToolOutput:
        index = mep.index
        kind = _text(arguments.get("kind")) or "pipe"
        if kind not in (*ifc_mep.SEGMENT_KINDS, "segment"):
            return ToolOutput(ok=False, error="kind must be pipe, duct, cable_carrier, cable, flow_segment or segment")
        group_by = _text(arguments.get("group_by")) or "none"
        if group_by not in ifc_mep.GROUPS:
            return ToolOutput(ok=False, error=f"group_by must be one of {', '.join(ifc_mep.GROUPS)}")
        filters = _filters(arguments)
        found = ifc_mep.select(index, kind, **filters)
        sure, why, check = length_status(index, found)
        lengths = [e.length_m for e in found if e.length_m is not None]
        total = sum(lengths) if lengths else None
        raw = sum(e.length_raw for e in found if e.length_raw is not None) if lengths else None
        sources: dict[str, int] = {}
        for e in found:
            if e.length_m is not None:
                sources[e.length_detail] = sources.get(e.length_detail, 0) + 1
        unit = ifc_mep.unit_suffix(index.unit_name)
        lines = [f"Total length of {_filter_text(kind, filters)}: {ifc_mep.fmt_length(total)}"
                 + (f" ({raw:.2f} {unit} in the model unit)" if raw is not None and unit != "m" else "")
                 + f", {ifc_mep.fmt_count(len(found))} segments"]  # fmt: skip
        rows = []
        if group_by != "none":
            groups = ifc_mep.grouped(found, group_by)
            for g in groups[:MAX_ROWS]:
                share = ifc_mep.pct(g.length_m or 0.0, total or 0.0)
                rows.append({"key": g.key, "segments": g.count, "length_m": round(g.length_m, 2) if g.length_m is not None else None,
                             "percent_of_length": round(100 * (g.length_m or 0.0) / total, 1) if total else None,
                             "with_length": g.with_length, "entity_ids": _ids(g.members)})  # fmt: skip
                lines.append(f"- {g.key}: {ifc_mep.fmt_length(g.length_m)} ({share}), {ifc_mep.fmt_count(g.count)} segments")
        if not sure:
            lines.append(f"Not sure: {why}.")
        data = {
            "kind": kind, "filter": _filter_text(kind, filters), "total_m": round(total, 2) if total is not None else None,
            "total_in_model_unit": round(raw, 2) if raw is not None else None, "model_unit": index.unit_name,
            "segments": len(found), "with_length": len(lengths), "length_sources": sources, "sure": sure,
            "why": why, "geometry_check": {"status": check.status, "compared": check.compared, "agree": check.agree},
            "groups": rows, "report": "\n".join(lines),
        }  # fmt: skip
        if not sure:
            data["advice"] = "the length is not sure: abstain and give total_m as the best estimate"
        state = "pass" if sure else "warn"
        checks = (Check(id="cross_check", label="stated length against geometry", state=state, detail=why,
                        factor=SURE if sure else UNSURE),)  # fmt: skip
        return ToolOutput(data=data, evidence=_evidence(found), confidence=SURE if sure else UNSURE, checks=checks)

    def systems_tool(arguments: dict[str, Any]) -> ToolOutput:
        index = mep.index
        wanted = _text(arguments.get("system"))
        chosen = [s for s in index.systems if not wanted or ifc_mep._match(s.name, wanted)  # noqa: SLF001
                  or ifc_mep._match(s.system_type, wanted)]  # noqa: SLF001  # fmt: skip
        rows = []
        for s in chosen[:MAX_ROWS]:
            members = [index.by_step[m] for m in dict.fromkeys(s.members) if m in index.by_step]
            kinds: dict[str, int] = {}
            for m in members:
                kinds[m.kind] = kinds.get(m.kind, 0) + 1
            segs = [m for m in members if m.kind in ifc_mep.SEGMENT_KINDS and m.length_m is not None]
            rows.append({
                "entity_id": s.key, "name": s.name, "class": s.ifc_class, "system_type": s.system_type,
                "source": s.source, "members": len(members), "by_kind": kinds,
                "segment_length_m": round(sum(m.length_m or 0.0 for m in segs), 2) if segs else None,
                "storeys": sorted({m.storey for m in members if m.storey}), "serves": list(s.serves),
                "part_of": list(s.parents),
            })  # fmt: skip
        categories: dict[str, int] = {}
        for s in chosen:
            label = s.system_type or ifc_mep.NONE_LABEL
            categories[label] = categories.get(label, 0) + 1
        lines = [f"Systems: {ifc_mep.fmt_count(len(chosen))}" + (f" matching {wanted!r}" if wanted else "")]
        lines += ["By system type:"] + [f"- {k}: {ifc_mep.fmt_count(v)} ({ifc_mep.pct(v, len(chosen))})"
                                        for k, v in sorted(categories.items(), key=lambda kv: -kv[1])]  # fmt: skip
        lines += ["Systems:"] + [f"- {r['name']} ({r['system_type'] or '-'}): {r['members']} elements" for r in rows]
        data = {"systems": rows, "total": len(chosen), "by_system_type": categories,
                "more_systems": max(0, len(chosen) - MAX_ROWS), "report": "\n".join(lines)}  # fmt: skip
        if any(s.source == "property" for s in chosen):
            data["note"] = "systems come from the 'System Name' property: the model has no IfcSystem for them"
        return ToolOutput(data=data)

    def elements_tool(arguments: dict[str, Any]) -> ToolOutput:
        index = mep.index
        kind = _text(arguments.get("kind")) or "all"
        filters = _filters(arguments)
        limit = max(1, min(int(arguments.get("limit") or 20), MAX_ELEMENTS))
        found = ifc_mep.select(index, kind, **filters)
        shown = found[:limit]
        entities = [model.file.by_id(e.step_id) for e in shown]
        where = ifc_mep.locate(model, entities, mep.shapes) if arguments.get("rooms") else None
        rows = []
        for i, (e, entity) in enumerate(zip(shown, entities, strict=True)):
            row: dict[str, Any] = {
                "entity_id": ifc_mep.entity_id(e.kind, e.global_id), "kind": e.kind, "name": e.name,
                "type": e.type_name, "family": e.family, "predefined_type": e.predefined_type, "storey": e.storey,
                "systems": list(e.systems), "size": e.size, "material": e.material,
            }  # fmt: skip
            if e.length_m is not None:
                row |= {"length_m": round(e.length_m, 3), "length_source": e.length_detail}
            if where is not None:
                loc = where[i]
                row |= {"space": loc.space, "space_long_name": loc.space_long_name, "space_method": loc.method}
            if limit <= 10:
                row["properties"] = _properties(entity)
            rows.append(row)
        lines = [f"{_title(kind)}: {ifc_mep.fmt_count(len(found))}" + _suffix(filters)]
        for r in rows:
            room = f", space {r['space']}" if r.get("space") else ""
            lines.append(f"- {r['type'] or r['name']} (storey {r['storey'] or '-'}{room})")
        data = {"total": len(found), "shown": len(rows), "elements": rows, "report": "\n".join(lines)}
        if where is not None and not mep.shapes:
            data["note"] = "the model has no space geometry, so no element can be placed in a room"
        return ToolOutput(data=data, evidence=_evidence(shown))

    kinds_hint = "pipe, pipe_fitting, duct, duct_fitting, valve, sanitary_terminal, air_terminal, space_heater, pump, fan, light_fixture, ..."
    kind_arg = {"type": "string", "description": f"an element kind ({kinds_hint}; mep_overview lists the kinds of this model), 'all' or 'segment'"}
    group_arg = {"type": "string", "enum": list(ifc_mep.GROUPS), "description": "type is the full type name, family the Revit family (the part before ':')"}
    storey_arg = {"type": "string", "description": "storey name exactly as listed, or empty"}
    system_arg = {"type": "string", "description": "part of a system name or system type, or empty"}
    name_arg = {"type": "string", "description": "part of a type, family or element name, or empty"}
    context = (
        f"The model has {count} building services (MEP) elements (pipes, ducts, fittings, valves, terminals, equipment). "
        "Use the mep_* tools for them. A free-text question about them can be answered with the `report` of one tool "
        "(submit it as it is). A length with sure=false must not be submitted: abstain and give it as best_estimate."
    )
    return context, [
        ToolSpec("mep_overview", "All MEP component kinds with counts and percentages, total pipe and duct lengths, number of systems, port connectivity.", _args({}, []), overview),
        ToolSpec("mep_count", "Count MEP elements of one kind, grouped (by type, family, storey, system, system_type, size, material, predefined_type, class), optionally a second level `then_by` (such as storey).", _args({"kind": kind_arg, "group_by": group_arg, "then_by": group_arg, "storey": storey_arg, "system": system_arg, "name": name_arg}, ["kind", "group_by", "then_by", "storey", "system", "name"]), count_tool),
        ToolSpec("mep_length", "Total length in metres of pipe, duct, cable carrier or cable segments, optionally grouped (by system, storey, size, material, type). Says where each length comes from and whether it is sure.", _args({"kind": {"type": "string", "enum": ["pipe", "duct", "cable_carrier", "cable", "flow_segment", "segment"]}, "group_by": group_arg, "storey": storey_arg, "system": system_arg, "name": name_arg}, ["kind", "group_by", "storey", "system", "name"]), length_tool),
        ToolSpec("mep_systems", "The distribution systems: name, system type, members by kind, segment length, storeys, what building they serve, parent system.", _args({"system": system_arg}, ["system"]), systems_tool),
        ToolSpec("mep_elements", "List single MEP elements (type, storey, systems, size, length, and with rooms=true the space each one is in). With limit <= 10 each row has its properties (capacity, power, flow).", _args({"kind": kind_arg, "storey": storey_arg, "system": system_arg, "name": name_arg, "rooms": {"type": "boolean"}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_ELEMENTS}}, ["kind", "storey", "system", "name", "rooms", "limit"]), elements_tool),
    ]  # fmt: skip


def _suffix(filters: dict[str, str | None]) -> str:
    parts = [f"{k} {v!r}" for k, v in filters.items() if v]
    return f" ({', '.join(parts)})" if parts else ""


SKIP_VALUES = frozenset({"", "default", "none", "n/a"})


def _properties(entity: Any, limit: int = 40) -> dict[str, Any]:  # noqa: ANN401 - an IFC entity
    """Scalar properties of one element and its type, without placeholders (a value equal to its own name)."""
    import ifcopenshell.util.element as ue  # noqa: PLC0415

    out: dict[str, Any] = {}
    with contextlib.suppress(Exception):
        for pset, values in ue.get_psets(entity).items():
            for name, value in values.items():
                if name == "id" or isinstance(value, (dict, list, tuple)) or value is None:
                    continue
                if isinstance(value, str) and (value.strip().casefold() in SKIP_VALUES or value.strip() == name):
                    continue
                key = name if name not in out else f"{pset}.{name}"
                out[key] = round(value, 4) if isinstance(value, float) else value
                if len(out) >= limit:
                    return out
    return out
