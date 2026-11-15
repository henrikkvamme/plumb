"""Agent tools for contractor quantities on vector plans (Swiss PDF and DXF): perimeters, baseboards, walls, doors.

The geometry is in `bp.tools.quantities`; the conventions are stated in its docstring and in each result.
The quantities are measured once, when the first tool runs, and kept for the other calls on the same document.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bp.agent.core import ToolOutput, ToolSpec
from bp.contract import Evidence
from bp.tools import quantities as q
from bp.tools import quantities_ifc as qi

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from bp.tools import dxf_plan, ifc_model, swiss_plan
    from bp.tools.pdf_text import PdfPage

BASEBOARD_RULE = (
    "baseboard_m = perimeter_m minus the width of each door opening in the room edge (a door between two rooms is "
    "taken off in both). baseboard_walls_only_m also takes off open_edge_m, the edge that borders another room with "
    "no wall between. Window openings are not taken off: a baseboard runs under a window."
)
PERIMETER_RULE = "perimeter_m: the whole edge of the net floor polygon, shaft holes included, door openings not cut out."
WALL_RULE = (
    "centerline_m: the centre line of all walls on the floor, door and window openings filled, measured to the free "
    "end of each wall. A BIM model sums one length per wall element; those overlap at corners, so such a sum is "
    "about 13% longer. exterior_m: the walls on the outer edge of the floor; interior_m: the rest."
)
COUNT_RULE = (
    "Doors and windows per room or per group count each opening place once. A door between two rooms of a group "
    "counts once for the group. The sheet-wide door count of count_symbols (one symbol per side of a shared wall) is "
    "a different rule."
)

# Error margins from the held-out bench (bp.toolbench.quantities, val: 210 floors, 5,577 rooms, 9 of 10 values inside).
WALL_MARGIN_SHARE = 0.012
WALL_MARGIN_BASIS = "9 of 10 of 210 held-out floors within 1.2% of the wall centre line of the CAD source"
ROOM_MARGIN_SHARE = 0.001
ROOM_MARGIN_COVER = 0.99
ROOM_MARGIN_BASIS = "99 of 100 of 5,577 held-out rooms: PDF and DXF perimeters and baseboards within 0.1% (largest 0.2%)"

NO_ARGS: dict[str, Any] = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
FILTER_ARGS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "apartment": {"type": "string", "description": "apartment letter, or empty for all rooms"},
        "kind": {"type": "string", "description": "room kind (bedroom, room, bathroom, kitchen, corridor, "
                 "living_dining, living_room, storeroom, staircase, balcony, ...), or empty for all"},
    },
    "required": ["apartment", "kind"],
    "additionalProperties": False,
}  # fmt: skip
GROUP_ARGS: dict[str, Any] = {
    "type": "object",
    "properties": {"by": {"type": "string", "enum": ["kind", "apartment"]}},
    "required": ["by"],
    "additionalProperties": False,
}


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _room_row(r: q.RoomQ) -> dict[str, Any]:
    return {
        "entity_id": r.entity_id,
        "number": r.number,
        "label": r.label,
        "kind": r.kind,
        "apartment": r.apartment,
        "outdoor": r.outdoor,
        "area_m2": r.area_m2,
        "perimeter_m": round(r.perimeter_m, 2),
        "door_openings": len(r.door_ids),
        "door_widths_m": [round(w, 2) for w in r.door_widths_m],
        "baseboard_m": round(r.baseboard_m, 2),
        "open_edge_m": round(r.open_edge_m, 2),
        "baseboard_walls_only_m": round(r.baseboard_walls_only_m, 2),
        "windows": len(r.window_ids),
    }


def _totals(rooms: list[q.RoomQ]) -> dict[str, Any]:
    doors = {d for r in rooms for d in r.door_ids}
    windows = {w for r in rooms for w in r.window_ids}
    return {
        "rooms": len(rooms),
        "room_ids": [r.entity_id for r in rooms],
        "area_m2": round(sum(r.area_m2 or 0.0 for r in rooms), 2),
        "perimeter_m": round(sum(r.perimeter_m for r in rooms), 2),
        "baseboard_m": round(sum(r.baseboard_m for r in rooms), 2),
        "baseboard_walls_only_m": round(sum(r.baseboard_walls_only_m for r in rooms), 2),
        "door_openings": len(doors),
        "windows": len(windows),
    }


def _evidence(rooms: list[q.RoomQ], limit: int = 40) -> tuple[Evidence, ...]:
    return tuple(
        Evidence(kind="polygon", points=r.exterior[:80], ref=r.number or r.entity_id,
                 note=f"perimeter {r.perimeter_m:.2f} m, baseboard {r.baseboard_m:.2f} m")
        for r in rooms[:limit] if len(r.exterior) >= 3
    )  # fmt: skip


def quantity_tools(measured: Callable[[], q.FloorQ | None]) -> tuple[str, list[ToolSpec]]:  # noqa: C901 - one closure per tool
    """The tools on one floor. `measured` gives the quantities (or None when the plan has no scale)."""
    cache: list[q.FloorQ | None] = []

    def floor() -> q.FloorQ | None:
        if not cache:
            cache.append(measured())
        return cache[0]

    def missing() -> ToolOutput:
        return ToolOutput(ok=False, error="the plan has no usable scale or unit, so no length can be measured")

    def rooms(arguments: dict[str, Any]) -> ToolOutput:
        got = floor()
        if got is None:
            return missing()
        apartment, kind = _text(arguments.get("apartment")), _text(arguments.get("kind")).lower()
        chosen = [r for r in got.rooms
                  if (not apartment or (r.apartment or "").upper() == apartment.upper())
                  and (not kind or r.kind == kind)]  # fmt: skip
        totals = _totals(chosen)
        if apartment and not kind:
            indoor = [r for r in chosen if not r.outdoor and not r.shared]
            totals["indoor_only"] = _totals(indoor) | {"entity_id": f"apartment:{apartment.upper()}"}
        data = {"rooms": [_room_row(r) for r in chosen], "totals": totals,
                "rules": [PERIMETER_RULE, BASEBOARD_RULE, COUNT_RULE],
                "margin": f"lengths ±{ROOM_MARGIN_SHARE:.1%}: {ROOM_MARGIN_BASIS}"}  # fmt: skip
        return ToolOutput(data=data, evidence=_evidence(chosen))

    def groups(arguments: dict[str, Any]) -> ToolOutput:
        got = floor()
        if got is None:
            return missing()
        by = _text(arguments.get("by")) or "kind"
        buckets: dict[str, list[q.RoomQ]] = {}
        for r in got.rooms:
            if by == "apartment":
                if r.apartment and not r.outdoor and not r.shared:
                    buckets.setdefault(r.apartment, []).append(r)
            else:
                buckets.setdefault(r.kind or "unlabelled", []).append(r)
        rows = []
        for key, members in sorted(buckets.items()):
            row = {by: key} | _totals(members)
            row["entity_id"] = f"apartment:{key}" if by == "apartment" else f"kind:{key}"
            row["room_numbers"] = [r.number for r in members]
            rows.append(row)
        note = ("Apartment groups hold the indoor rooms of the apartment (no balconies, no shared stair halls)."
                if by == "apartment" else "Kinds come from the room labels; 'room' is a plain room (Zimmer, Pièce, "
                "Stanza), 'bedroom' is a room labelled as a bedroom.")  # fmt: skip
        return ToolOutput(data={"groups": rows, "note": note, "rules": [BASEBOARD_RULE, COUNT_RULE]})

    def walls(_: dict[str, Any]) -> ToolOutput:
        got = floor()
        if got is None:
            return missing()
        wall_row = None
        if got.walls:
            wall_row = got.walls.model_dump(mode="json") | {
                "entity_id": "walls",
                "margin_m": round(WALL_MARGIN_SHARE * got.walls.centerline_m, 2),
                "margin_share": 0.9,
                "margin_basis": WALL_MARGIN_BASIS,
            }
        widths = [d.width_m for d in got.doors]
        doors = [{"entity_id": d.entity_id, "width_m": round(d.width_m, 2), "rooms": list(d.rooms)} for d in got.doors]
        windows = [{"entity_id": w.entity_id, "width_m": round(w.width_m, 2), "rooms": list(w.rooms)}
                   for w in got.windows]  # fmt: skip
        stats = ({"count": len(widths), "min_m": round(min(widths), 2), "max_m": round(max(widths), 2),
                  "mean_m": round(sum(widths) / len(widths), 3)} if widths else {"count": 0})  # fmt: skip
        data = {"walls": wall_row, "door_widths": stats, "doors": doors, "windows": windows,
                "rules": [WALL_RULE, "width_m: the long side of the opening in the wall (the clear opening drawn)."]}
        evidence = tuple(
            Evidence(kind="polygon", points=d.ring, ref=d.entity_id, note=f"{d.width_m:.2f} m")
            for d in got.doors[:60]
        )
        return ToolOutput(data=data, evidence=evidence)

    context = (
        "Contractor quantities: room_quantities gives perimeter, baseboard (skirting) length, door openings with widths "
        "and windows per room, with totals for an apartment or a room kind; group_quantities sums them per kind or per "
        "apartment; wall_quantities gives the wall centre line length and each door and window width. Each result "
        "states its rule; say the rule in the answer when a question could mean more than one."
    )
    return context, [
        ToolSpec("room_quantities", "Per room: perimeter_m, baseboard_m (skirting: perimeter minus door openings), door openings and their widths, windows, area; filtered by apartment letter and/or room kind, with totals.", FILTER_ARGS, rooms),
        ToolSpec("group_quantities", "Sums per room kind or per apartment: room count, floor area, baseboard length, distinct door openings and windows.", GROUP_ARGS, groups),
        ToolSpec("wall_quantities", "Wall centre line length of the floor (total, exterior, interior), wall footprint area, and the width of each door and window opening with the rooms it serves.", NO_ARGS, walls),
    ]  # fmt: skip


def swiss_quantity_tools(page: PdfPage, plan: swiss_plan.SwissPlan) -> tuple[str, list[ToolSpec]]:
    def measured() -> q.FloorQ | None:
        floor = q.swiss_floor(page, plan)
        return q.measure(floor) if floor is not None else None

    return quantity_tools(measured)


def dxf_quantity_tools(path: str | Path, plan: dxf_plan.DxfPlan) -> tuple[str, list[ToolSpec]]:
    def measured() -> q.FloorQ | None:
        floor = q.dxf_floor(path, plan)
        return q.measure(floor) if floor is not None else None

    return quantity_tools(measured)


UNSURE = 0.3  # a value that the model does not state: the agent abstains and gives it as best_estimate
IFC_WALL_RULE = (
    "total_m sums the Qto_WallBaseQuantities Length of each wall (a wall with no Qto length takes its Axis length, "
    "counted in from_axis). exterior_m and interior_m split it by Pset_WallCommon.IsExternal, or by a layer property "
    "that names the side (side_source 'layer'); unknown_side_m has neither. When total_m is None the model has no "
    "wall length: say so and do not guess."
)
IFC_OPENING_RULE = (
    "width_m: the OverallWidth attribute of the door or window, else its Qto Width. nominal_width_m: the nominal size "
    'in the type name ("DL - 1000 x 2000" is 1.00 m), when there is one. Give width_m; when the two differ, also '
    "give the nominal width and say which is which."
)
IFC_SPACE_RULE = (
    "perimeter_m: the space Qto NetPerimeter (else GrossPerimeter), else the edge of its plan footprint. baseboard_m = "
    "perimeter_m minus the width of each door of the space (from IfcRelSpaceBoundary, else doors within 0.5 m of the "
    "footprint). Window openings are not taken off."
)
STOREY_ARGS: dict[str, Any] = {
    "type": "object",
    "properties": {"storey": {"type": "string", "description": "storey name as listed, or empty for the whole model"}},
    "required": ["storey"],
    "additionalProperties": False,
}
OPENING_ARGS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["door", "window"]},
        "storey": {"type": "string", "description": "storey name as listed, or empty for the whole model"},
    },
    "required": ["kind", "storey"],
    "additionalProperties": False,
}


def _stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0}
    return {"count": len(values), "min_m": round(min(values), 3), "max_m": round(max(values), 3),
            "mean_m": round(sum(values) / len(values), 3), "sum_m": round(sum(values), 3)}  # fmt: skip


def ifc_quantity_tools(model: ifc_model.IfcModel) -> tuple[str, list[ToolSpec]]:
    """Wall lengths, door and window widths, and space perimeters and baseboards of an IFC model."""

    def walls(arguments: dict[str, Any]) -> ToolOutput:
        storey = _text(arguments.get("storey")) or None
        rows = qi.wall_rows(model, storey)
        totals = qi.wall_totals(rows, storey)
        sides = sorted({r.side_source for r in rows})
        data = {"totals": totals.model_dump(mode="json") | {"entity_id": "walls", "side_sources": sides},
                "walls": [r.model_dump(mode="json") for r in rows[:150]], "rule": IFC_WALL_RULE}  # fmt: skip
        evidence = tuple(Evidence(kind="ifc_element", ref=r.entity_id.split(":", 1)[-1], note=f"{r.length_m} m")
                         for r in rows[:60])  # fmt: skip
        if totals.from_axis:
            # The Axis curve is not a stated quantity: against the public keys it was wrong on 2 of 2 models.
            data["sure"] = False
            data["why"] = (f"{totals.from_axis} of {totals.walls} wall lengths come from the Axis curve, not from a "
                           "quantity set. Do not submit a wall length: abstain and give it as best_estimate.")  # fmt: skip
            return ToolOutput(data=data, evidence=evidence, confidence=UNSURE)
        return ToolOutput(data=data, evidence=evidence)

    def openings(arguments: dict[str, Any]) -> ToolOutput:
        kind = "window" if _text(arguments.get("kind")) == "window" else "door"
        storey = _text(arguments.get("storey")) or None
        rows = qi.opening_rows(model, kind, storey)
        widths = [r.width_m for r in rows if r.width_m is not None]
        nominal = [r.nominal_width_m for r in rows if r.nominal_width_m is not None]
        data = {"stats": _stats(widths) | {"without_width": len(rows) - len(widths)},
                "nominal_stats": _stats(nominal) | {"without_nominal": len(rows) - len(nominal)},
                "openings": [r.model_dump(mode="json") for r in rows[:200]], "rule": IFC_OPENING_RULE}  # fmt: skip
        evidence = tuple(Evidence(kind="ifc_element", ref=r.entity_id.split(":", 1)[-1], note=f"{r.width_m} m")
                         for r in rows[:60])  # fmt: skip
        return ToolOutput(data=data, evidence=evidence)

    def spaces(arguments: dict[str, Any]) -> ToolOutput:
        storey = _text(arguments.get("storey")) or None
        rows = qi.space_rows(model, storey)
        known = [r for r in rows if r.baseboard_m is not None]
        totals = {"spaces": len(rows), "with_baseboard": len(known),
                  "perimeter_m": round(sum(r.perimeter_m or 0.0 for r in rows), 3),
                  "baseboard_m": round(sum(r.baseboard_m or 0.0 for r in known), 3)}  # fmt: skip
        data = {"spaces": [r.model_dump(mode="json") for r in rows[:150]], "totals": totals, "rule": IFC_SPACE_RULE}
        measured = sum(1 for r in rows if r.perimeter_source != "qto")
        if measured:
            # A perimeter from the footprint is not in the model: the one public skirting key says "not in the model".
            data["sure"] = False
            data["why"] = (f"{measured} of {len(rows)} perimeters are measured from the space footprint, not stated "
                           "in a quantity set. Do not submit a perimeter or baseboard length: abstain, say that the "
                           "model does not state it, and give the value as best_estimate.")  # fmt: skip
            return ToolOutput(data=data, confidence=UNSURE)
        return ToolOutput(data=data)

    context = (
        "Contractor quantities: wall_lengths gives the wall length (total, exterior, interior) with its source; "
        "opening_widths gives each door or window width with min, max and mean; space_quantities gives each space "
        "perimeter and baseboard (skirting) length. Each result states its rule."
    )
    return context, [
        ToolSpec("wall_lengths", "Wall length of the model or a storey: total, exterior and interior metres, per wall rows with entity_id and the source of each value.", STOREY_ARGS, walls),
        ToolSpec("opening_widths", "Width of each door or window (entity_id, width_m, storey) with count, min, max, mean and sum.", OPENING_ARGS, openings),
        ToolSpec("space_quantities", "Per space: perimeter_m and baseboard_m (skirting: perimeter minus door widths), the doors of the space and the source of each value.", STOREY_ARGS, spaces),
    ]  # fmt: skip


def path_quantity_tools(kind: str, path: str) -> tuple[str, list[ToolSpec]] | None:
    """The quantity tools of a Swiss plan PDF or a DXF, read from the file at the first call (None for other kinds)."""
    from bp.tools import dxf_plan, pdf_text, swiss_plan  # noqa: PLC0415 - the readers load only when a tool runs

    if kind == "plan_pdf":

        def swiss() -> q.FloorQ | None:
            page = pdf_text.read_page(path)
            floor = q.swiss_floor(page, swiss_plan.compile_plan(page))
            return q.measure(floor) if floor is not None else None

        return quantity_tools(swiss)
    if kind == "dxf":

        def dxf() -> q.FloorQ | None:
            floor = q.dxf_floor(path, dxf_plan.read_dxf(path))
            return q.measure(floor) if floor is not None else None

        return quantity_tools(dxf)
    return None
