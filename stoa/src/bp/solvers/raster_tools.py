"""Agent tools for a raster floor plan (a PNG with no vector data), and an agent solver that uses them.

The tools read the image with OCR (`bp.tools.ocr`), measure its scale (`bp.tools.raster_scale`) and segment
the rooms (`bp.tools.raster_rooms`). Field names are the same as in the vector tools (`swiss_tools`), so the
agent asks the same way. A raster plan with no scale (CubiCasa) still lists the room texts that OCR reads, with a
relative pixel area that can only compare sizes, and `area_m2` null.

Run: uv run bp run bp.solvers.raster_tools:RasterAgentSolver --suite hard --partition val --cell measure/raster
"""

from __future__ import annotations

import math
import os
import re
import threading
from collections import Counter, OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from bp.agent.core import ToolOutput, ToolSpec, run_agent
from bp.contract import Abstain, AnswerRecord, Calibration, Evidence, IngestReport, MissingReason, Question
from bp.llm import ChatResult, chat
from bp.solvers import drawing_sheet
from bp.solvers.agent import NO_ARGS, RASTER_SUFFIXES, raster_count_tools
from bp.tools import ocr, raster_openings, raster_rooms, sheet_text
from bp.tools.raster_scale import RasterScale

if TYPE_CHECKING:
    from collections.abc import Callable

    from bp.solvers.cubicasa_detect import CubicasaDetectSolver
    from bp.tools.ocr import TextLine
    from bp.tools.raster_rooms import RasterPlan

ROOM_NAME = re.compile(r"^[A-ZÄÖÅÜ][A-ZÄÖÅÜ.\-/ ]{0,15}$")  # plan room names are in capitals: "OH", "KPH", "SAUNA"
UNREAD_WARN_M2 = 1.5  # val sheets: below this, 79 of 89 apartment areas within 2%; above it, 18 of 49
LOW_NOTE = "an area with area_confidence low can be off by more than 5%"
OPENINGS_NOTE = (
    "For each room, `windows` and `doors` count the symbols a detector found that touch the room (a door between two "
    "rooms counts for both). A null count means the detector is not sure for that room: a question that needs that "
    "room's count cannot be answered, so abstain. A question over many rooms (how many rooms have a window) needs "
    "every room it covers to have a count. `windows_at_least` and `doors_at_least` count only the firm symbols: when "
    "`windows` is null and `windows_at_least` is 1 or more, the room has a window for certain, only the exact number "
    "is open. "
)
FINNISH = (
    "Common Finnish room abbreviations: OH olohuone (living room), MH makuuhuone (bedroom), K or KEITTIÖ (kitchen), "
    "KK keittokomero (kitchenette), RT ruokailutila (dining), ET eteinen (hall), KH or KPH kylpyhuone (bathroom), "
    "PH or PESUH pesuhuone (washroom), S or SAUNA (sauna), WC (toilet), VH vaatehuone (walk-in closet), "
    "VAR varasto (storage), TK takkahuone (fireplace room), AK autokatos (carport), PARVEKE or P (balcony), "
    "TERASSI (terrace)."
)


# ----------------------------------------------------------------------------- entity ids
# The facts of a small raster (`bp.facts_models.raster_facts`) use the same ids, so an answer can show its rooms.


def room_ids(plan: RasterPlan) -> list[str]:
    """The entity id of each room, in the order of `plan.rooms`: `room:<number>`, `room:<number>@<x>:<y>` on a repeat."""
    numbers = Counter(r.number for r in plan.rooms)
    return [
        f"room:{r.number}" if numbers[r.number] == 1 else f"room:{r.number}@{round(r.at[0])}:{round(r.at[1])}"
        for r in plan.rooms
    ]


def text_room_id(at_px: list[int] | tuple[int, int]) -> str:
    """A room text with no room number (a plan with no scale), by the place of the text."""
    return f"room:{at_px[0]}:{at_px[1]}"


def marked_room_id(kind: str, box_px: list[int]) -> str:
    """A room that the symbol detector marks by kind, by the centre of its box."""
    return f"room:{kind}:{round((box_px[0] + box_px[2]) / 2)}:{round((box_px[1] + box_px[3]) / 2)}"


def apartment_id(letter: str) -> str:
    return f"apartment:{letter}"


# ----------------------------------------------------------------------------- reading, shared by tools and facts


@dataclass(frozen=True)
class SmallRaster:
    """What the tools of a small raster plan are built from. The facts of the same image read the same object."""

    rgb: np.ndarray
    lines: list[TextLine]
    plan: RasterPlan
    detector: CubicasaDetectSolver | None
    measured: RasterScale | None = None  # with a scale from the user: the scale that the image itself shows


CACHE_SIZE = 4
_cache: OrderedDict[tuple[str, int, bool, float | None], SmallRaster | None] = OrderedDict()
_detectors: OrderedDict[tuple[str, int], CubicasaDetectSolver | None] = OrderedDict()
_lock = threading.Lock()


def _key(path: str | Path) -> tuple[str, int]:
    resolved = Path(path).resolve()
    return str(resolved), resolved.stat().st_mtime_ns


def _remember(cache: OrderedDict[Any, Any], key: object, value: object) -> None:
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > CACHE_SIZE:
        cache.popitem(last=False)


def detector_for(path: str | Path) -> CubicasaDetectSolver | None:
    """The symbol detector run on one image, once per process. None when `BP_COUNT_DETECTOR=0`."""
    if os.environ.get("BP_COUNT_DETECTOR", "1") == "0":
        return None
    key = _key(path)
    with _lock:
        if key in _detectors:
            return _detectors[key]
    from bp.solvers.cubicasa_detect import CubicasaDetectSolver  # noqa: PLC0415 - torch is slow to import

    detector = CubicasaDetectSolver()
    detector.ingest(str(path))
    with _lock:
        _remember(_detectors, key, detector)
    return detector


def user_ppm(calibration: Calibration | None) -> float | None:
    """Pixels per metre from two points and their real distance. None for a ratio alone: an image has no paper size."""
    if calibration is None or calibration.points is None or not calibration.real_length_m:
        return None
    (x0, y0), (x1, y1) = calibration.points
    px = math.hypot(x1 - x0, y1 - y0)
    return px / calibration.real_length_m if px > 0 and calibration.real_length_m > 0 else None


def read_small(
    path: str | Path, rgb: np.ndarray, detect: Callable[[], CubicasaDetectSolver | None] | None,
    ppm: float | None = None,
) -> SmallRaster | None:  # fmt: skip
    """OCR, the room model and the detector on a small raster plan, once per process. None when OCR reads nothing.

    `ppm` is a scale from the user. It replaces the scale of the image, and the rooms are read again at it.
    """
    key = (*_key(path), detect is not None, round(ppm, 4) if ppm else None)
    with _lock:
        if key in _cache:
            return _cache[key]
    if ppm:
        base = read_small(path, rgb, detect)
        scaled: SmallRaster | None = None
        if base is not None:
            plan = raster_rooms.read_plan(rgb, base.lines, _scale(ppm, "user"))
            own = base.plan.scale
            scaled = SmallRaster(rgb=rgb, lines=base.lines, plan=plan, detector=base.detector,
                                 measured=own if own is not None and own.source not in ("doors", "areas") else None)  # fmt: skip
        with _lock:
            _remember(_cache, key, scaled)
        return scaled
    lines = ocr.read_lines(rgb)
    found: SmallRaster | None = None
    if lines:
        plan = raster_rooms.read_plan(rgb, lines)
        # The detector runs after OCR and the room model: the other order ends the process without a message.
        detector = detect() if detect else None
        if plan.scale is None and plan.rooms:
            plan = with_estimated_scale(plan, rgb, lines, detector)
        found = SmallRaster(rgb=rgb, lines=lines, plan=plan, detector=detector)
    with _lock:
        _remember(_cache, key, found)
    return found


def _label_texts(lines: list[TextLine]) -> list[TextLine]:
    """OCR lines that can be a room name: one short word or abbreviation in capitals."""
    return [line for line in lines if ROOM_NAME.match(line.text.strip()) and line.score >= 0.7]


def label_areas(rgb: np.ndarray, lines: list[TextLine]) -> list[dict[str, Any]]:
    """For a plan with no scale: each room-name text and the pixel area of the region around it.

    The region is the baseline fill. A region that touches the image border is the outside, not a room: its area
    is null.
    """
    labels = _label_texts(lines)
    if not labels:
        return []
    gray = rgb.mean(axis=2)
    mask = np.zeros(gray.shape, bool)
    for line in lines:
        x0, y0, x1, y1 = (round(v) for v in line.bbox)
        mask[max(0, y0 - 1) : y1 + 2, max(0, x0 - 1) : x1 + 2] = True
    regions = raster_rooms.baseline_regions(gray, [(t.cx, t.cy) for t in labels], mask)
    px = np.bincount(regions.ravel(), minlength=len(labels) + 1)
    border = set(np.unique(np.concatenate([regions[0], regions[-1], regions[:, 0], regions[:, -1]])).tolist())
    good = [i + 1 for i in range(len(labels)) if px[i + 1] and i + 1 not in border]
    total = float(sum(px[i] for i in good)) or 1.0
    return [
        {"label": t.text, "area_px": int(px[i + 1]) if i + 1 in good else None,
         "area_share": round(float(px[i + 1]) / total, 4) if i + 1 in good else None,
         "at_px": [round(t.cx), round(t.cy)]}
        for i, t in enumerate(labels)
    ]  # fmt: skip


def _scale_text(plan: RasterPlan) -> str:
    scale = plan.scale
    if scale is None:
        return "no scale on this image: areas cannot be given"
    if scale.source == "user":
        return (f"{scale.ppm:.2f} px per metre, from two points and their real distance that the user gave. No "
                "benchmark checks a scale from a user: each area in m2 depends on it")  # fmt: skip
    if scale.source == "areas":
        return (f"no scale bar or scale text; {scale.ppm:.2f} px per metre from the printed room areas against the "
                "room shapes (the printed areas agree with each other)")  # fmt: skip
    if scale.source == "doors":
        return ("no scale bar, no scale text and too few printed areas: the scale is only an ESTIMATE from the door "
                "symbols. area_m2 is given only where the area is printed in the room; relative_area compares "
                "room sizes")  # fmt: skip
    ratio = f"1:{scale.ratio}" if scale.ratio else "unknown ratio"
    if scale.source == "both":
        how = f"the scale bar and the scale text agree within {100 * (scale.difference or 0):.2f}% (confirmed)"
    elif scale.agree is False:
        how = f"the scale bar and the scale text DISAGREE by {100 * (scale.difference or 0):.1f}%: the bar is used"
    else:
        how = f"only the {scale.source} witness was found (not confirmed)"
    return f"{ratio}, {scale.ppm:.2f} px per metre measured on the image; {how}"


Openings = dict[str, dict[str, int | None]]


def room_openings(plan: RasterPlan, detector: CubicasaDetectSolver | None) -> Openings:
    """For each room number: the windows and doors whose detector box touches the room shape.

    A count is None when a box near the detector threshold touches the room. Empty with no detector, no scale or a
    detector in doubt.
    """
    if detector is None or detector.detector is None or detector.detections is None or detector.problem is not None:
        return {}
    if plan.scale is None:
        return {}
    calib: dict[str, Any] = detector.detector.meta.get("calibration", {})
    rooms = [r for r in plan.rooms if len(r.polygon) >= 3]
    shapes = [raster_openings.shape_of(r.polygon) for r in rooms]
    out: Openings = {r.number: {} for r in rooms}
    for label, concept in (("window", "windows"), ("door", "doors")):
        c = calib.get(concept, {})
        got = raster_openings.room_openings(
            shapes, detector.detections, label, float(c.get("threshold", 0.5)), float(c.get("band", 0.0)),
            plan.scale.ppm,
        )  # fmt: skip
        for room, g in zip(rooms, got, strict=True):
            out[room.number][concept] = g.count if g.sure else None
            out[room.number][f"{concept}_at_least"] = g.count
    return out


MIN_AREA_WITNESSES = 3
AREA_SPREAD = 0.12  # the printed areas give a scale when the middle half of their ratios lies within this


def _scale(ppm: float, source: str) -> RasterScale:
    return RasterScale(ppm=ppm, source=source, agree=None, difference=None, bar=None, text=None, evidence=())  # ty: ignore[invalid-argument-type]


def with_estimated_scale(
    plan: RasterPlan, rgb: np.ndarray, lines: list[TextLine], detector: CubicasaDetectSolver | None
) -> RasterPlan:
    """A plan with room numbers and no scale bar: get the scale from what the drawing shows.

    1. The door symbols give a first estimate (a door leaf is about 0.85 m), enough to find the room shapes.
    2. When at least 3 rooms print their area and the printed areas agree with the shapes up to one factor, that
       factor gives the scale (source "areas"). Else the scale stays an estimate (source "doors"): shapes and
       relative sizes are usable, areas in m2 are not.
    """
    if detector is None or detector.detections is None or detector.detector is None or detector.problem is not None:
        return plan
    calib: dict[str, Any] = detector.detector.meta.get("calibration", {})
    ppm = raster_openings.door_scale(detector.detections, float(calib.get("doors", {}).get("threshold", 0.5)))
    if ppm is None:
        return plan
    first = raster_rooms.read_plan(rgb, lines, _scale(ppm, "doors"))
    ratios = sorted(r.model_area_m2 / r.printed_area_m2 for r in first.rooms
                    if r.model_area_m2 and r.printed_area_m2 and r.printed_area_m2 > 1.0)  # fmt: skip
    if len(ratios) < MIN_AREA_WITNESSES:
        return first
    low, mid, high = ratios[len(ratios) // 4], ratios[len(ratios) // 2], ratios[(3 * len(ratios)) // 4]
    if high / low - 1 > AREA_SPREAD:
        return first
    return raster_rooms.read_plan(rgb, lines, _scale(ppm * mid**0.5, "areas"))


def raster_tools(
    path: str | Path,
    detect: Callable[[], CubicasaDetectSolver | None] | None = None,
    calibration: Calibration | None = None,
) -> tuple[str, list[ToolSpec]] | None:
    """The tools and context for one raster plan, or None when the file is not a raster image or shows no text."""
    if Path(path).suffix.lower() not in RASTER_SUFFIXES:
        return None
    rgb = ocr.to_rgb(path)
    if sheet_text.is_sheet(rgb):
        # A full sheet at print resolution: the room model is built for small plans and fails here.
        lines = sheet_text.read_lines(rgb)
        return drawing_sheet.sheet_tools(rgb, lines, calibration) if lines else None
    small = read_small(path, rgb, detect, user_ppm(calibration))
    if small is None:
        return None
    plan, lines, detector = small.plan, small.lines, small.detector
    if plan.scale is None:
        return _no_scale_tools(plan, rgb, lines, detector)
    if plan.scale.source == "user" and not plan.rooms:
        # The room model starts from the room numbers. With none, a scale alone gives no room shape.
        context, tools = _no_scale_tools(plan, rgb, lines, detector, plan.scale.ppm)
        now = (f"The user gave a scale ({plan.scale.ppm:.1f} px per metre), but OCR reads no room numbers on this "
               "image, so no room shape is measured. list_rooms_by_kind gives box_area_m2: the box of a marked room "
               "at that scale. It is rough (within 20% of the room area on 80% of 323 test rooms): give it only as "
               "an estimate, with that margin, and never as an exact area.")  # fmt: skip
        return context.replace(NO_SCALE, now), tools
    context, tools = plan_tools(plan, rgb, lines, room_openings(plan, detector))
    if plan.scale.source in ("doors", "areas"):
        # No printed scale: the texts read as room numbers can be noise (a Finnish plan has none). Keep the rooms
        # that the symbol detector marks by kind, so a question about bedrooms or bathrooms still has a tool.
        _, extra = _no_scale_tools(plan, rgb, lines, detector)
        by_kind = [t for t in extra if t.name == "list_rooms_by_kind"]
        if by_kind:
            tools = [*tools, *by_kind]
            context += (
                " A symbol detector also marks rooms by kind with a box (list_rooms_by_kind), with the windows and "
                "doors that touch each one. It does not need a readable label: use it when list_rooms has no room "
                "with the label that the question asks for."
            )
    return context, tools


def plan_tools(
    plan: RasterPlan, rgb: np.ndarray, lines: list[TextLine], openings: Openings | None = None
) -> tuple[str, list[ToolSpec]]:
    openings = openings or {}
    if plan.scale is None:
        return _no_scale_tools(plan, rgb, lines, None)

    estimate = plan.scale is not None and plan.scale.source == "doors"
    whole = sum(r.model_area_m2 or 0.0 for r in plan.rooms) or 1.0

    def shown(r: Any) -> dict[str, Any]:  # noqa: ANN401 - raster_rooms.Room
        if not estimate:
            return {"area_m2": r.area_m2, "area_confidence": r.area_confidence, "area_source": r.area_source}
        return {
            "area_m2": r.printed_area_m2, "area_confidence": "high" if r.printed_area_m2 else "none",
            "area_source": "printed" if r.printed_area_m2 else "none",
            "relative_area": round((r.model_area_m2 or 0.0) / whole, 4) if r.model_area_m2 else None,
        }  # fmt: skip

    ids = room_ids(plan)

    def rooms(_: dict[str, Any]) -> ToolOutput:
        data = [
            {
                "number": r.number,
                "label": r.label,
                **shown(r),
                "printed_area_m2": r.printed_area_m2,
                "apartment": r.apartment,
                "outdoor": r.outdoor,
                **(openings.get(r.number) or {"windows": None, "doors": None} if openings else {}),
                "entity_id": ids[i],
            }
            for i, r in enumerate(plan.rooms)
        ]  # fmt: skip
        evidence = tuple(e for r in plan.rooms for e in r.evidence()[-1:])
        note = LOW_NOTE
        if plan.unread_area_m2:
            note += (
                f"; {plan.unread_area_m2} m2 of room area on the sheet has no number that OCR read, so some rooms are "
                "missing from this list: a total over 'all rooms labelled X' may be too small"
            )
        return ToolOutput(data={"rooms": data, "note": note}, evidence=evidence)

    def apartments(_: dict[str, Any]) -> ToolOutput:
        data = []
        for a in plan.apartments:
            members = [r for r in plan.rooms if r.apartment == a.letter]
            indoor = [r for r in members if not r.outdoor]
            missing = [r.number for r in indoor if r.area_m2 is None]
            area = round(sum(r.area_m2 or 0.0 for r in indoor), 2) if indoor and not missing else None
            warnings = []
            if missing:
                warnings.append(f"no area for rooms {missing}")
            if a.unread_area_m2 is not None and a.unread_area_m2 >= UNREAD_WARN_M2:
                area = None
                warnings.append(
                    f"{a.unread_area_m2} m2 of room area inside the outline has no number that OCR read: a room "
                    "of this apartment is missing, so its living area and room list are not reliable"
                )
            if a.unit is None:
                warnings.append("the apartment outline was not found: rooms come from the tag position only")
            data.append({"letter": a.letter, "living_area_m2": area, "rooms": [r.number for r in members],
                         "warnings": warnings, "entity_id": apartment_id(a.letter)})  # fmt: skip
        return ToolOutput(data={"apartments": data})

    n_low = sum(1 for r in plan.rooms if r.area_confidence == "low")
    context = (
        "Document: a raster image (PNG) of a floor plan of one storey (residential), read with OCR and a room "
        f"segmentation model. Scale: {_scale_text(plan)}. It has {len(plan.rooms)} numbered rooms read by OCR "
        f"({n_low} with a low-confidence area) and {len(plan.apartments)} apartment tags. A room area is the "
        "printed area when it matches the measured one, else the measured net area at the measured scale. "
        "On held-out plans, about 95% of high-confidence areas were within 2% of the true area; a medium or low "
        "area can be off by more than 5%. A room whose number OCR "
        "missed is not listed. Labels are OCR reads with small spelling slips ('Badd' or 'Bed' for 'Bad', "
        "'Zirhmer' for 'Zimmer'): match a label loosely. "
        + (OPENINGS_NOTE if openings else "The tools cannot read which windows or doors belong to a room. ")
        + "The tools cannot read heights or materials."
    )
    if estimate:
        context += (
            " The scale is an estimate: do not compute an area in m2 from it. `relative_area` is the share of a room "
            "in the area of all listed rooms; use it to compare rooms or to find the largest when the printed areas "
            "are missing, and only when the difference is clear (1.2 times or more)."
        )
    tools = [
        ToolSpec("list_rooms", "Every numbered room read on the image: number, label, net area in m2 with area_confidence (high, medium, low), apartment letter, outdoor flag (balcony, loggia, terrace), and when a detector ran: windows and doors that touch the room (null when not sure).", NO_ARGS, rooms, method="model"),
        ToolSpec("list_apartments", "Every apartment tag: letter, living area in m2 (indoor rooms inside its outline, no balconies; null when a room of the apartment was not read: then abstain), room numbers, warnings.", NO_ARGS, apartments, method="model"),
    ]  # fmt: skip
    return context, tools[:1] if estimate else tools


ROOM_KINDS = {"bedroom": "bedrooms", "kitchen": "kitchens", "bathroom": "bathrooms", "wc_room": "wc_rooms",
              "sauna": "saunas", "balcony": "balconies"}  # fmt: skip
ROOM_REACH_M = 0.10


def detected_rooms(detector: CubicasaDetectSolver | None, lines: list[TextLine]) -> list[dict[str, Any]]:
    """Rooms the symbol detector marks by kind, with the windows and doors whose box touches the room box.

    A room box is the bounding box of the room, so a room that is not a rectangle can catch an opening of a
    neighbour: the counts are less exact than on a plan with room shapes. The scale for the touch distance comes
    from the door boxes (one leaf is about 0.85 m), or from the image size when there are too few doors.
    """
    if detector is None or detector.detector is None or detector.detections is None or detector.problem is not None:
        return []
    found = detector.detections
    calib: dict[str, Any] = detector.detector.meta.get("calibration", {})

    def cut(concept: str) -> tuple[float, float]:
        c = calib.get(concept, {})
        return float(c.get("threshold", 0.5)), float(c.get("band", 0.0))

    ppm = raster_openings.door_scale(found, cut("doors")[0]) or max(detector.size) / 100.0
    rooms = [d for d in found if d.label in ROOM_KINDS and d.score >= cut(ROOM_KINDS[d.label])[0]]
    shapes = [raster_openings.shape_of([(d.box[0], d.box[1]), (d.box[2], d.box[1]), (d.box[2], d.box[3]),
                                        (d.box[0], d.box[3])]) for d in rooms]  # fmt: skip
    counts = {
        concept: raster_openings.room_openings(shapes, found, label, *cut(concept), ppm, ROOM_REACH_M)
        for label, concept in (("window", "windows"), ("door", "doors"))
    }
    total = sum(s.area for s in shapes) or 1.0
    out = []
    for i, (d, shape) in enumerate(zip(rooms, shapes, strict=True)):
        x0, y0, x1, y1 = d.box
        texts = [t.text for t in lines if x0 <= t.cx <= x1 and y0 <= t.cy <= y1 and len(t.text.strip()) <= 16]
        row: dict[str, Any] = {
            "kind": d.label, "score": round(d.score, 2), "texts_inside": texts[:6],
            "relative_box_area": round(shape.area / total, 4),
            "box_px": [round(v) for v in d.box],
        }  # fmt: skip
        for concept, got in counts.items():
            row[concept] = got[i].count if got[i].sure else None
            row[f"{concept}_at_least"] = got[i].count
        row["entity_id"] = marked_room_id(d.label, row["box_px"])
        out.append(row)
    return out


NO_SCALE = "There is no scale on this image: areas cannot be given in m2 and no length can be measured."


def _no_scale_tools(
    plan: RasterPlan, rgb: np.ndarray, lines: list[TextLine], detector: CubicasaDetectSolver | None = None,
    ppm: float | None = None,
) -> tuple[str, list[ToolSpec]]:  # fmt: skip
    """The tools of a plan with no measured room shapes. `ppm` is a scale from the user: boxes get a rough area."""
    labelled = label_areas(rgb, lines)
    marked = detected_rooms(detector, lines)
    if ppm:
        for m in marked:
            x0, y0, x1, y1 = m["box_px"]
            m["box_area_m2"] = round((x1 - x0) * (y1 - y0) / ppm**2, 1)

    def by_kind(_: dict[str, Any]) -> ToolOutput:
        evidence = tuple(
            Evidence(kind="mark", points=((m["box_px"][0], m["box_px"][1]), (m["box_px"][2], m["box_px"][3])),
                     ref=m["kind"])
            for m in marked
        )  # fmt: skip
        note = (
            "kinds: bedroom, kitchen, bathroom, wc_room (a toilet room), sauna, balcony. Other rooms (living room, "
            "hall, storage) are not marked: use list_rooms for those. windows and doors count the detector boxes "
            "that touch the room box; null means not sure, and then windows_at_least and doors_at_least give the firm symbols (1 or more: the room has one for certain). relative_box_area compares the bounding boxes of the "
            "marked rooms only; it is rough, so use it only when one room is clearly larger (1.5 times or more)."
        )
        return ToolOutput(data={"rooms": marked, "note": note}, evidence=evidence)

    ids = room_ids(plan)

    def rooms(_: dict[str, Any]) -> ToolOutput:
        data: list[dict[str, Any]] = [
            {"number": r.number, "label": r.label, "area_m2": None, "area_confidence": "none",
             "apartment": r.apartment, "outdoor": r.outdoor, "entity_id": ids[i]}
            for i, r in enumerate(plan.rooms)
        ]  # fmt: skip
        data += [
            {"number": None, "label": t["label"], "area_m2": None, "area_confidence": "none",
             "relative_area_share": t["area_share"], "outdoor": raster_rooms.is_outdoor_label(t["label"]),
             "entity_id": text_room_id(t["at_px"])}
            for t in labelled
        ]  # fmt: skip
        evidence = tuple(Evidence(kind="text_span", points=(tuple(t["at_px"]),), ref=t["label"]) for t in labelled[:40])
        return ToolOutput(
            data={"rooms": data, "note": "no scale: area_m2 is null; relative_area_share only compares sizes "
                  "(the share of the pixel area of all listed texts' regions; rough)"},
            evidence=evidence,
        )  # fmt: skip

    context = (
        f"Document: a raster image of a floor plan, read with OCR. {NO_SCALE} list_rooms gives the room texts that OCR reads (often "
        "abbreviations) with a rough relative pixel area that can only say which room is larger (null when the "
        "region is not closed). OCR misses many small labels. The tools cannot read heights or materials. " + FINNISH
    )
    tools = [
        ToolSpec("list_rooms", "Room texts read on the image: label, area_m2 (null: no scale), relative_area_share to compare sizes, outdoor flag.", NO_ARGS, rooms, method="model"),
    ]  # fmt: skip
    if marked:
        context += (
            " A symbol detector also marks rooms by kind with a box (list_rooms_by_kind), with the windows and doors "
            "that touch each one. It does not need a readable label. When list_rooms_by_kind marks the rooms a "
            "question asks about and their counts are not null, answer from it."
        )
        tools.append(ToolSpec("list_rooms_by_kind", "Rooms a symbol detector marks by kind (bedroom, kitchen, bathroom, wc_room, sauna, balcony): the windows and doors that touch each room (null when not sure), OCR texts inside it, a rough relative box area.", NO_ARGS, by_kind, method="model"))  # fmt: skip
    return context, tools


class RasterAgentSolver:
    """The agent with the raster tools.

    A raster plan also gets the whole-plan count tool when the count head says the image is in its distribution.
    Any other document: abstain (the vector solvers handle it).
    """

    name = "raster-agent"

    def __init__(self) -> None:
        self.context = ""
        self.tools: list[ToolSpec] = []
        self.kind = "none"
        self.model = os.environ.get("BP_AGENT_MODEL", "claude-haiku-5.5")

    def ingest(self, path: str) -> IngestReport:
        got = raster_tools(path)
        if got is not None:
            self.kind = "raster_rooms"
            self.context, self.tools = got
        if Path(path).suffix.lower() in RASTER_SUFFIXES:
            from bp.tools import count_head  # noqa: PLC0415 - torch is slow to import, only rasters need it

            counts = count_head.count_plan(Path(path), count_head.get_model("e1.json"))
            if counts.in_distribution:
                context, tools = raster_count_tools(counts)
                self.context = (self.context + "\n" + context).strip()
                self.tools = [*self.tools, *tools]
                self.kind += "+counts"
        return IngestReport(ok=True, detail=self.kind)

    def calibrate(self, calibration: Calibration) -> None:
        del calibration

    def ask(self, question: Question) -> AnswerRecord:
        if not self.tools:
            abstain = Abstain(
                reason=MissingReason.UNSUPPORTED,
                detail="no trusted tool reads this document",
                request="a vector PDF, a DXF or an IFC file of the same drawing",
            )
            return AnswerRecord(status="abstained", abstain=abstain)

        def call(messages: list[dict[str, Any]], schemas: list[dict[str, Any]]) -> ChatResult:
            return chat(self.model, messages, tools=schemas, max_tokens=1500, tag=f"raster:{self.kind}")

        return run_agent(question.text, self.tools, call, context=self.context).record
