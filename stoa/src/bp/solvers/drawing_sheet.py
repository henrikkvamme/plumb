"""Agent tools for a large drawing sheet (a raster of a full construction drawing with a title block and notes).

The tools are general: they search and read the printed text with its position, and they know nothing about the
building type or the discipline. The agent composes them: find a room name and read the area printed next to it,
list the tags of a kind, read the scale, read a legend or a table by its region.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from bp import rates
from bp.agent.core import ToolOutput, ToolSpec
from bp.contract import Check, Evidence
from bp.tools import sheet_geometry, sheet_plan, sheet_text
from bp.tools.sheet_text import SQFT_M2

if TYPE_CHECKING:
    import numpy as np

    from bp.contract import Calibration
    from bp.tools.ocr import TextLine
    from bp.tools.sheet_text import Label

MAX_MATCHES = 60
MAX_REGION = 150
NO_SCALE = (
    "the scale of this image is not proven (no agreeing dimension lines, and the doors do not confirm the printed "
    "scale): nothing can be measured"
)
ROOM_NAME = re.compile(r"[A-Za-z][A-Za-z'&/().,\- ]{3,}")
DOOR_FACTOR = 0.5
DOOR_AGREE = 0.03  # the detector and the arc finder count the same doors within this share
DOOR_AGREE_FACTOR = 0.9  # agreed counts right within 3%: 31 of 32 dev sheets (arc finder), 51 of 54 (second detector)
ROOM_FACTOR = 0.9
SAME_ROOMS = 0.03  # rooms with one name count as one answer when their areas agree this well  # a closed room at a proven scale: 1 to 3% error
PERIMETER_FACTOR = 0.8
M_PER_FT = 0.3048
NO_ARGS: dict[str, Any] = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}

CONTEXT = (
    "Document: a raster image of a full drawing sheet ({width} x {height} px), read with OCR. It has one or more "
    "drawings, a title block, notes and often a legend or a schedule. The text tools give each printed text with its "
    "position in pixels (x to the right, y down). OCR reads most texts and can miss or misread a few, so a count of "
    "labels can be 1 short. Units on the sheet can be imperial (SF is square feet, 12'-6\" is feet and inches) or "
    "metric (mm). To answer in another unit, convert with calc (M2_PER_FT2, M_PER_FT) or length_to_m. Prefer a "
    "value that the sheet prints. zone_areas measures the area of each colour-filled zone. room_area measures one room "
    "from its walls, room_perimeter gives its wall length (for baseboards), and count_door_swings counts the swing "
    "doors of the plan. They fail when the scale of the image "
    "is not proven or the room is not closed: then abstain. The tools cannot measure a wall or a pipe run on this "
    "sheet yet: abstain on those too."
)


def _args(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


NUMBER = re.compile(r"(?<![\w.])-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])-?\d+(?:\.\d+)?")


def _number(text: str) -> float | None:
    """The one number that a text prints, such as 820 for "820 SF". None when it prints none or several."""
    found = NUMBER.findall(text)
    return float(found[0].replace(",", "")) if len(found) == 1 else None


def _row(label: Label) -> dict[str, Any]:
    row: dict[str, Any] = {"entity_id": sheet_plan.label_id(label), "text": label.text, "at_px": list(label.at)}
    value = _number(label.text)
    if value is not None:
        row["value"] = value
    return row


def _span(label: Label) -> Evidence:
    box = label.bbox
    return Evidence(kind="text_span", points=((box[0], box[1]), (box[2], box[3])), ref=label.text[:80])


def _room_labels(plan: sheet_plan.SheetPlan, asked: str) -> list[Label]:
    """The labels that a room argument names: an entity id, the exact text, or the first line of a name in two lines."""
    if asked.startswith(("room:", "label:")):
        at = asked.split(":", 1)[1]
        return [lb for lb in plan.labels if f"{lb.at[0]}:{lb.at[1]}" == at]
    hits = sheet_text.find(plan.labels, asked, "exact")
    if hits:
        return hits
    wanted = sheet_text.norm(asked)
    starts = [
        lb for lb in plan.labels if len(sheet_text.norm(lb.text)) >= 4 and wanted.startswith(sheet_text.norm(lb.text))
    ]
    return starts if len(starts) == 1 else []


def _one_room(plan: sheet_plan.SheetPlan, asked: str) -> tuple[sheet_plan.PlanRoom | None, str]:
    """The one closed room that the argument names, or why there is none."""
    hits = _room_labels(plan, asked)
    if not hits:
        return None, "no label has this text: give the text of one room label as find_text shows it"
    if sheet_plan.DIVIDED.search(hits[0].text):
        return None, "stalls, fixtures or stair flights divide this kind of room: the wall lines do not give its area"
    found = [r for r in (plan.room_of(h) for h in hits) if r is not None]
    closed = [r for r in found if r.closed]
    if len(hits) == 1:
        error = "" if closed else f"{found[0].why_not}: the room is not closed, no area"
        return (closed[0] if closed else None), error
    areas = [r.room.area_px for r in closed if r.room is not None]
    if len(closed) == len(hits) and max(areas) <= (1 + SAME_ROOMS) * min(areas):
        return closed[0], ""
    ids = [sheet_plan.room_id(h) for h in hits[:8]]
    return None, f"{len(hits)} labels have this text and their rooms differ: give one entity id of {ids}"


AGREED = {
    "arc_finder": "the trained detector and the arc finder agree within 3%: on the dev sheets 31 of 32 such counts "
    "were right",
    "second_detector": "two trained detectors of different kinds agree within 3%: the lower count was right on 51 of "
    "54 such dev sheets and on 49 of 52 scanned twins (the 3 wrong ones are the same sheets, where the key misses "
    "doors)",
}


def _door_checks(scale: sheet_plan.PlanScale, agree: bool | None, witness: str) -> tuple[Check, ...]:
    if agree:
        band = Check(id="error_band", label="Door count from two methods", state="pass", factor=DOOR_AGREE_FACTOR,
                     detail=f"{AGREED[witness]}; sliding doors are not counted")  # fmt: skip
    else:
        band = Check(id="error_band", label="Door finder", state="warn", factor=DOOR_FACTOR,
                     detail="an estimate: the two door methods differ, or only one has run; sliding doors are "
                            "not counted")  # fmt: skip
    return (scale.check, band)


def _door_note(agree: bool | None) -> str:
    note = (
        "each swing is one door leaf: a leaf line and its arc. A double door is 2 swings. Sliding, folding and "
        "overhead doors have no swing and are not counted. "
    )
    if agree:
        note += (
            "Two independent methods agree on this count within 3%: answer a question that wants the number of "
            "doors with door_leaves"
        )
    else:
        note += (
            "This count is an estimate: the two door methods do not agree on this sheet. For a question that "
            "wants the number of doors, abstain with reason unsupported and give this count as best_estimate. "
            "Answer with it only when the question asks for an estimate or an approximate count"
        )
    return note


def _door_witness(plan: sheet_plan.SheetPlan) -> tuple[str, int] | None:
    """The second count of the doors: the second detector when it has seen the sheet, else the arc finder.

    None when only one method has run (no detector: the swings are the arcs). The second detector reads scans,
    where the arc finder sees no doors. Uploads to the live site have no second detector, so the arc finder stays.
    """
    if plan.arc_swings is plan.swings:
        return None
    second = plan.second_swings
    if second is not None:
        return "second_detector", len(second)
    return "arc_finder", len(plan.arc_swings)


def _doors_agree(plan: sheet_plan.SheetPlan) -> bool | None:
    """True when the detector and its witness count the same doors within 3%. None when only one has run."""
    witness = _door_witness(plan)
    if witness is None:
        return None
    return abs(witness[1] - len(plan.swings)) <= max(1, DOOR_AGREE * len(plan.swings))


def plan_tools(plan: sheet_plan.SheetPlan) -> list[ToolSpec]:
    """The tools that read the walls and the doors of a plan: they need the scale of the image."""

    def count_door_swings(_: dict[str, Any]) -> ToolOutput:
        scale = plan.scale
        if scale is None:
            return ToolOutput(ok=False, error=NO_SCALE)
        swings = plan.swings
        agree = _doors_agree(plan)
        rows = [
            {"entity_id": sheet_plan.door_id(s), "hinge_px": [round(s.centre[0]), round(s.centre[1])],
             "leaf_m": round(s.radius_px / scale.ppm, 2)}
            for s in swings
        ]  # fmt: skip
        note = _door_note(agree)
        evidence = tuple(
            Evidence(kind="mark", points=((s.centre[0], s.centre[1]),), ref=sheet_plan.door_id(s)) for s in swings[:200]
        )
        data = {"door_leaves": len(swings), "px_per_metre": round(scale.ppm, 2), "scale_from": scale.source,
                "swings": rows[:MAX_MATCHES], "note": note}  # fmt: skip
        witness = _door_witness(plan)
        if agree is not None and witness is not None:
            data["methods_agree"] = agree
            data[f"door_leaves_{witness[0]}"] = witness[1]
            if agree and witness[0] == "second_detector":
                # Both detectors count a cabinet or a locker swing now and then: on the dev sheets every count that
                # agreed and was wrong was too high, and the lower count was right more often (51 of 54, not 50).
                data["door_leaves"] = min(len(swings), witness[1])
        checks = _door_checks(scale, agree, witness[0] if witness else "arc_finder")
        return ToolOutput(data=data, evidence=evidence, checks=checks)

    def one_room(arguments: dict[str, Any]) -> tuple[sheet_plan.PlanRoom | None, sheet_plan.PlanScale | None, str]:
        scale = plan.scale
        if scale is None:
            return None, None, NO_SCALE
        found, error = _one_room(plan, str(arguments.get("room", "")).strip())
        return found, scale, error

    def room_checks(scale: sheet_plan.PlanScale) -> tuple[Check, ...]:
        closed = Check(id="closed", label="Room is closed", state="pass", factor=1.0,
                       detail="the walls and the closed door openings bound one region with one room name")  # fmt: skip
        band = Check(id="error_band", label="Area from the wall lines", state="pass", factor=ROOM_FACTOR,
                     detail="1 to 3% error on a closed room")  # fmt: skip
        return (scale.check, closed, band)

    def room_area(arguments: dict[str, Any]) -> ToolOutput:
        found, scale, error = one_room(arguments)
        if found is None or found.room is None or scale is None:
            return ToolOutput(ok=False, error=error)
        room, label = found.room, found.label
        m2 = room.area_px / scale.ppm**2
        data = {
            "entity_id": sheet_plan.room_id(label), "room": label.text, "area_m2": round(m2, 2),
            "area_sqft": round(m2 / SQFT_M2), "bbox_px": list(room.bbox), "px_per_metre": round(scale.ppm, 2),
            "scale_from": scale.source,
            "note": "the floor inside the wall lines around the label, to the face of the walls, with door openings "
            "closed. Expect 1 to 3% error. A value that the sheet prints for the room is better",
        }  # fmt: skip
        if plan.scan and not sheet_plan.DIVIDED.search(label.text) and m2 < rates.SMALL_ROOM_M2:
            # Blur moves each wall face by about a pixel: on the test scans 2 of 4 rooms this small were within 5%.
            return ToolOutput(ok=False, error=(
                f"the sheet is a scan and the room is small: the measure is {round(m2 / SQFT_M2)} sq ft "
                f"({round(m2, 2)} m2), but only 2 of 4 test rooms this small on scans were within 5%. Abstain with "
                "reason unsupported and give it as best_estimate, unless the question asks for an estimate"))  # fmt: skip
        evidence = (Evidence(kind="polygon", points=tuple(room.outline()), ref=sheet_plan.room_id(label)),)
        return ToolOutput(data=data, evidence=evidence, checks=room_checks(scale))

    def room_perimeter(arguments: dict[str, Any]) -> ToolOutput:
        found, scale, error = one_room(arguments)
        if found is None or found.room is None or scale is None:
            return ToolOutput(ok=False, error=error)
        room, label = found.room, found.label
        doors = room.doors_on_edge(plan.swings)
        perimeter = room.perimeter_px() / scale.ppm
        widths = [round(s.radius_px / scale.ppm, 2) for s in doors]
        data = {
            "entity_id": sheet_plan.room_id(label), "room": label.text, "perimeter_m": round(perimeter, 2),
            "perimeter_ft": round(perimeter / M_PER_FT, 1), "door_widths_m": widths,
            "doors": [sheet_plan.door_id(s) for s in doors],
            "perimeter_without_doors_m": round(perimeter - sum(widths), 2),
            "perimeter_without_doors_ft": round((perimeter - sum(widths)) / M_PER_FT, 1),
            "scale_from": scale.source,
            "note": "the length of the walls around the room. A baseboard or a skirting runs along the walls and "
            "stops at each door: use perimeter_without_doors. Columns and built-in furniture are not followed. "
            "Expect 3 to 6% error",
        }  # fmt: skip
        evidence = (Evidence(kind="polygon", points=tuple(room.outline()), ref=sheet_plan.room_id(label)),)
        band = Check(id="error_band", label="Wall length from the outline", state="warn", factor=PERIMETER_FACTOR,
                     detail="3 to 6% error: small steps in a wall are smoothed")  # fmt: skip
        return ToolOutput(data=data, evidence=evidence, checks=(scale.check, band))

    room_arg = _args({"room": {"type": "string", "description": "the room label, as find_text shows it"}}, ["room"])
    return [
        ToolSpec(
            "count_door_swings",
            "Count the swing door leaves that the plan draws (leaf line and arc), with each hinge position.",
            NO_ARGS,
            count_door_swings,
        ),
        ToolSpec(
            "room_area",
            "Measure the floor area of one room from its walls, in m2 and square feet. Use it only when the sheet "
            "does not print the area of the room.",
            room_arg,
            room_area,
        ),
        ToolSpec(
            "room_perimeter",
            "Measure the wall length around one room in metres and feet, with and without the door openings. Use it "
            "for baseboard, skirting or wall finish lengths.",
            room_arg,
            room_perimeter,
        ),
    ]


def geometry_tools(plan: sheet_plan.SheetPlan) -> list[ToolSpec]:
    """The tools that measure on the image. The work is done at the first call, not at ingest.

    A calibration from the user comes first: two marked points with their distance are the scale, and a ratio
    replaces the printed scales.
    """
    rgb, all_labels = plan.rgb, plan.labels
    measured: dict[str, Any] = {}

    def scale_of() -> sheet_geometry.DimensionScale | None:
        if plan.scale is not None and plan.scale.source == "user":
            ppm = plan.scale.ppm
            return sheet_geometry.DimensionScale(ppm=ppm, agreeing=1, read=1, spread=0.0, witnesses=())
        return plan.measured

    def measure_scale(_: dict[str, Any]) -> ToolOutput:
        scale = scale_of()
        if scale is None:
            return ToolOutput(data={"px_per_metre": None, "note": "fewer than 3 dimension lines agree: no length "
                                    "or area can be measured on this sheet"})  # fmt: skip
        data = {
            "px_per_metre": scale.ppm,
            "dimensions_that_agree": scale.agreeing,
            "dimensions_read": scale.read,
            "spread_percent": round(100 * scale.spread, 2),
            "witnesses": [{"printed": d.text, "metres": d.metres, "line_px": d.pixels} for d in scale.witnesses],
            "note": "measured on the dimension lines of the drawing, so it holds for this image. A printed ratio "
            "(read_scales) does not give pixels per metre",
        }
        evidence = tuple(Evidence(kind="scale", points=d.line, ref=d.text) for d in scale.witnesses)
        return ToolOutput(data=data, evidence=evidence)

    def zone_areas(_: dict[str, Any]) -> ToolOutput:
        scale = scale_of()
        if scale is None:
            return ToolOutput(ok=False, error="no measured scale: fewer than 3 dimension lines agree")
        if "zones" not in measured:
            measured["zones"] = sheet_geometry.colour_zones(rgb, all_labels, scale.ppm)
        rows = [
            {"colour": z.colour, "rgb": list(z.rgb), "legend_text": z.legend,
             "area_m2": round(z.area_px / scale.ppm**2, 1), "area_sqft": round(z.area_px / scale.ppm**2 / SQFT_M2),
             "parts": z.parts, "bbox_px": list(z.bbox)}
            for z in measured["zones"]
        ]  # fmt: skip
        note = (
            "the area that each fill colour covers on the drawing, with the thin lines inside it. The legend swatch "
            "is not counted. legend_text is the text next to the swatch of that colour, when the sheet has a legend. "
            "A zone includes all that has the colour, also a void such as 'open to below'. It is the area as drawn: when "
            "a part of the building is cut with a break line, the drawing is smaller than the building. When the "
            "legend prints the area of the zone, give the printed value. Expect 1 to 3% error"
        )
        evidence = tuple(
            Evidence(kind="polygon", points=((z.bbox[0], z.bbox[1]), (z.bbox[2], z.bbox[3])), ref=z.legend or z.colour)
            for z in measured["zones"]
        )
        return ToolOutput(data={"zones": rows, "note": note}, evidence=evidence)

    return [
        *plan_tools(plan),
        ToolSpec(
            "measure_scale",
            "Pixels per metre of this image, measured on the dimension lines of the drawing (several must agree).",
            NO_ARGS,
            measure_scale,
        ),
        ToolSpec(
            "zone_areas",
            "The area of each colour-filled zone of the plan in m2 and square feet, with the legend text of the "
            "colour. Use it for the area of a kind of space that the plan shows by colour (dormitory, circulation, "
            "common area).",
            NO_ARGS,
            zone_areas,
        ),
    ]


def sheet_tools(
    rgb: np.ndarray, lines: list[TextLine], calibration: Calibration | None = None
) -> tuple[str, list[ToolSpec]]:
    height, width = rgb.shape[:2]
    plan = sheet_plan.plan_for(rgb, lines, calibration)
    all_labels = plan.labels

    def find_text(arguments: dict[str, Any]) -> ToolOutput:
        query, mode = str(arguments.get("query", "")), str(arguments.get("match", "exact"))
        try:
            hits = sheet_text.find(all_labels, query, mode)
        except re.error as error:  # a bad pattern from the model
            return ToolOutput(ok=False, error=f"bad pattern: {error}")
        rows = []
        for hit in hits[:MAX_MATCHES]:
            row = _row(hit)
            row["near"] = [
                {**_row(lb), "side": where, "gap": gap}
                for lb in sheet_text.near(all_labels, hit)
                for where, gap in [sheet_text.side(hit, lb)]
            ]
            rows.append(row)
        data = {
            "count": len(hits),
            "matches": rows,
            "note": "near: the texts closest to the match, nearest first, with the side they lie on and the gap in "
            "text heights. A value that belongs to a name is usually right above or below it with a gap under 1. "
            "A larger gap can belong to a neighbour room: then abstain or check with read_region",
        }
        if len(hits) > MAX_MATCHES:
            data["note"] += f"; only the first {MAX_MATCHES} matches are listed"
        return ToolOutput(data=data, evidence=tuple(_span(h) for h in hits[:MAX_MATCHES]))

    def list_tags(arguments: dict[str, Any]) -> ToolOutput:
        found = sheet_text.tags(lines, str(arguments.get("prefix", "")))
        names = sorted(found, key=lambda t: (len(t), t))
        evidence = tuple(Evidence(kind="text_span", points=(found[n][0],), ref=n) for n in names[:MAX_MATCHES])
        return ToolOutput(
            data={
                "different_tags": len(names),
                "tags": [
                    {"tag": n, "printed": len(found[n]), "at_px": [[round(x), round(y)] for x, y in found[n][:20]]}
                    for n in names
                ],
            },
            evidence=evidence,
        )

    def scales(_: dict[str, Any]) -> ToolOutput:
        found = sheet_text.printed_scales(lines)
        data = {
            "scales": [
                {"scale": f"1:{s.ratio}", "as_printed": s.text, "printed": s.count, "at_px": list(s.at)} for s in found
            ],
            "note": "every scale notation on the sheet; a sheet with several drawings can print several scales",
        }
        evidence = tuple(Evidence(kind="scale", points=(s.at,), ref=s.text) for s in found)
        return ToolOutput(data=data, evidence=evidence)

    def read_region(arguments: dict[str, Any]) -> ToolOutput:
        try:
            box = tuple(float(arguments[k]) for k in ("x0", "y0", "x1", "y1"))
        except (KeyError, TypeError, ValueError):
            return ToolOutput(ok=False, error="give x0, y0, x1, y1 in pixels")
        inside = sheet_text.in_region(all_labels, (box[0], box[1], box[2], box[3]))
        data = {"count": len(inside), "texts": [_row(lb) for lb in inside[:MAX_REGION]]}
        if len(inside) > MAX_REGION:
            data["note"] = f"only the first {MAX_REGION} texts are listed: ask for a smaller region"
        return ToolOutput(data=data, evidence=tuple(_span(lb) for lb in inside[:MAX_MATCHES]))

    def length_to_m(arguments: dict[str, Any]) -> ToolOutput:
        text = str(arguments.get("text", ""))
        metres = sheet_text.feet_inches_m(text)
        if metres is None:
            return ToolOutput(ok=False, error="not a length in feet and inches, such as 12'-6\"")
        return ToolOutput(data={"text": text, "metres": round(metres, 4)})

    region = {k: {"type": "number"} for k in ("x0", "y0", "x1", "y1")}
    tools = [
        ToolSpec(
            "find_text",
            "Find printed text on the sheet. match 'exact': the whole label equals the query (use it to count rooms "
            "with one name: 'Store' does not match 'Secure Store'); 'contains': the query is part of the label; "
            "'regex': a pattern. Not case sensitive. A name on two lines is one label. Gives the count, each match "
            "with its position, and the texts printed near it.",
            _args(
                {"query": {"type": "string"}, "match": {"type": "string", "enum": ["exact", "contains", "regex"]}},
                ["query", "match"],
            ),
            find_text,
        ),
        ToolSpec(
            "list_tags",
            "The different tags with one letter prefix, such as PS-1, PS-2 for prefix 'PS': each tag once, with how "
            "often it is printed.",
            _args({"prefix": {"type": "string"}}, ["prefix"]),
            list_tags,
        ),
        ToolSpec(
            "read_scales",
            'Every scale printed on the sheet (1:100, 1/4" = 1\'-0"), each as a ratio 1:N.',
            NO_ARGS,
            scales,
        ),
        ToolSpec(
            "read_region",
            "Every text in a rectangle of the sheet, in reading order. Use it to read a legend, a schedule, a note "
            "block or the title block after find_text gave the position of its heading.",
            _args(region, ["x0", "y0", "x1", "y1"]),
            read_region,
        ),
        ToolSpec(
            "length_to_m",
            "Convert a printed length in feet and inches (12'-6\", 8'-10 1/2\") to metres.",
            _args({"text": {"type": "string"}}, ["text"]),
            length_to_m,
        ),
    ]
    return CONTEXT.format(width=width, height=height), [*tools, *geometry_tools(plan)]
