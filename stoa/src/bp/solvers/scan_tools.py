"""Agent tools for a historic scan: a small raster of an old drawing, a title page or a print, not a modern flat plan.

A scan is read with OCR (scan_reading). The text tools are those of a large sheet, built on the joined phrases of
the scan. Other tools read the title block and the captions, the scale (a scale bar with its unit, dimension lines,
or the user's two points), the size of each drawing, and a length between two points. A length is given only at a
proven scale, with an error margin; else the tool fails with the reason, and the agent abstains with no_scale.
The look tool asks two vision models; its result is a model reading, not a measurement.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bp import rates
from bp.agent.core import ToolOutput, ToolSpec
from bp.contract import Check, Evidence
from bp.solvers import drawing_sheet
from bp.tools import scan_look, scan_reading, sheet_plan

if TYPE_CHECKING:
    import numpy as np

    from bp.contract import Calibration
    from bp.tools.ocr import TextLine
    from bp.tools.scan_reading import ScanReading, ScanScale
    from bp.tools.sheet_text import Label

NO_ARGS = drawing_sheet.NO_ARGS
TEXT_TOOLS = ("find_text", "list_tags", "read_region", "length_to_m")
POINT_PX = 2.0  # a point that the agent gives from a text or a drawing box is placed to about this many pixels
MAX_ROWS = 40

# Rates of scan facts. No benchmark of historic scans with true answers exists yet, so each is a rule that says so.
SCAN_TEXT = rates.unmeasured("OCR of historic scans (it reads print well and handwriting badly)")
SCAN_TITLE = rates.unmeasured("title block facts read from historic scans", confidence=0.4)
SCAN_SCALE_ONE = rates.unmeasured("a scale from one scale bar or one set of dimension lines on a historic scan")
SCAN_SCALE_TWO = rates.unmeasured("a scale from two agreeing witnesses on a historic scan", confidence=0.7)
SCAN_SCALE_USER = rates.unmeasured("a scale from two points that the user marked", confidence=0.9)
SCAN_DRAWING_BOX = rates.unmeasured("the box of a drawing on a historic scan (a dimension chain can widen it)", 0.4)

CONTEXT = (
    "Document: a scan of a historic drawing, a title page or a print ({width} x {height} px). It is not a modern "
    "floor plan: there is no room model and no door detector for it. It was read with OCR, and the text tools give "
    "each printed text with its position in pixels (x to the right, y down). OCR reads printed text well and "
    "handwriting badly: a handwritten name, date or note can be missing or misread. Then use look, and say that it "
    "is a model reading. read_title_block gives the title, dates, years, names, sheet number, printed scale and the "
    "kind of drawing that the texts give. read_scale gives the pixels per metre only from a scale bar with a unit, "
    "from dimension lines, or from two points that the user marked. A printed ratio such as 1:100 gives no pixels "
    "per metre on a scan, because the print size of the scan is not known. A bar in an old unit (Ellen, alnar, "
    "pieds, Fuss, fot) is read, never converted. measure_length and drawing_size fail when the scale is not proven: "
    "then abstain with reason no_scale. look asks two vision models about the image or a region of it. Give a "
    "count from look only when both models agree and are sure; else abstain with reason ambiguous and give the "
    "readings as best_estimate. When the question asks for something that the scan does not show, abstain with "
    "reason not_on_document."
)


def _span(label: Label) -> Evidence:
    box = label.bbox
    return Evidence(kind="text_span", points=((box[0], box[1]), (box[2], box[3])), ref=label.text[:80])


def _label_row(label: Label) -> dict[str, Any]:
    return {"entity_id": sheet_plan.label_id(label), "text": label.text, "at_px": list(label.at)}


def scale_check(scale: ScanScale) -> Check:
    """The check that a scan scale puts on a measured value."""
    rate = scale_rate(scale)
    state = "pass" if scale.confirmed or scale.source == "user" else "warn"
    return Check(id="scale", label="Scale of the scan", state=state, factor=rate.confidence,
                 detail=f"{scale.ppm:g} px per metre {scale.detail}, error {100 * scale.error:.1f}%")  # fmt: skip


def scale_rate(scale: ScanScale) -> rates.Rate:
    if scale.source == "user":
        return SCAN_SCALE_USER
    return SCAN_SCALE_TWO if scale.confirmed else SCAN_SCALE_ONE


def no_scale_reason(reading: ScanReading) -> str:
    """Why the scan has no proven scale, in one sentence for the agent and the user."""
    bars = reading.bars
    if any(b.ppm for b in bars):
        return "the scale bars and dimension lines of this scan disagree by more than 2%, so none is trusted"
    old = [b for b in bars if b.unit and b.metres_per_unit is None]
    if old:
        return (f"the scale bar is in an old unit ({old[0].unit}) with no single value in metres; give the scale "
                "with two points and their real distance")  # fmt: skip
    if bars:
        return ("a scale bar was found, but its unit is not readable or two units are printed next to it; give the "
                "scale with two points and their real distance")  # fmt: skip
    ratios = scan_reading.printed_ratios(reading.labels)
    if ratios:
        return (f"the scan prints the scale {ratios[0][0]}, but the print size of the scan is not known, so a ratio "
                "gives no pixels per metre; give the scale with two points and their real distance")  # fmt: skip
    return "the scan has no readable scale bar, no dimension lines and no user scale"


def length_m(scale: ScanScale, pixels: float) -> tuple[float, float]:
    """A length in metres and its margin: the scale error and the placing of both ends."""
    metres = pixels / scale.ppm
    margin = metres * scale.error + 2 * POINT_PX / scale.ppm
    return metres, margin


def _bar_row(bar: scan_reading.BarScale) -> dict[str, Any]:
    row: dict[str, Any] = {
        "values": list(bar.values), "unit": bar.unit, "px_per_unit": bar.px_per_unit, "at_px": [bar.xs_px[0],
        bar.row_y, bar.xs_px[-1], bar.row_y], "placed_on": "tick marks" if bar.on_ticks else "label centres",
        "error_share": bar.error, "as_printed": list(bar.texts),
    }  # fmt: skip
    if bar.ppm:
        row["px_per_m"] = bar.ppm
    elif bar.unit:
        row["note"] = f"{bar.unit} is an old unit with no single value in metres: not converted"
    else:
        row["note"] = "no unit is readable next to this bar, or words of two units are near it"
    return row


def scan_tools(  # noqa: C901, PLR0915 - one closure per tool
    rgb: np.ndarray, lines: list[TextLine] | None = None, calibration: Calibration | None = None
) -> tuple[str, list[ToolSpec]]:
    """The context and the tools of one scan. `lines` are the raw OCR lines when the caller has read them."""
    height, width = rgb.shape[:2]
    reading = scan_reading.read_scan(rgb, calibration, lines)
    _, sheet = drawing_sheet.sheet_tools(rgb, reading.lines, calibration)
    text_tools = [t for t in sheet if t.name in TEXT_TOOLS]

    def read_title_block(_: dict[str, Any]) -> ToolOutput:
        found = reading.title
        rows: dict[str, list[dict[str, Any]]] = {}
        for item in found:
            rows.setdefault(item.role, []).append({"value": item.value, **_label_row(item.label)})
        data = {
            "facts": rows,
            "note": "each value with the text it was read from. title: the texts in the largest letters. year and "
            "date: every year or date printed anywhere (a survey year, a building year or a stamp; read the text "
            "to tell which). OCR misses most handwriting: when the question asks for a handwritten name or date "
            "and it is not here, use look",
        }
        evidence = tuple(dict.fromkeys(_span(item.label) for item in found))[:MAX_ROWS]
        return ToolOutput(data=data, evidence=evidence)

    def read_scale(_: dict[str, Any]) -> ToolOutput:
        scale = reading.scale
        data: dict[str, Any] = {
            "scale_bars": [_bar_row(b) for b in reading.bars],
            "printed_ratios": [{"scale": text, **_label_row(lb)} for text, lb in
                               scan_reading.printed_ratios(reading.labels)],
        }  # fmt: skip
        if reading.dimensions is not None:
            dims = reading.dimensions
            data["dimension_lines"] = {"px_per_m": round(dims.ppm, 3), "agreeing": dims.agreeing,
                                       "spread_share": round(dims.spread, 4)}  # fmt: skip
        evidence: tuple[Evidence, ...] = tuple(
            Evidence(kind="scale", points=((b.xs_px[0], b.row_y), (b.xs_px[-1], b.row_y)), ref=" ".join(b.texts))
            for b in reading.bars
        )
        if scale is None:
            data["px_per_m"] = None
            data["reason"] = no_scale_reason(reading)
            return ToolOutput(data=data, evidence=evidence)
        data.update(px_per_m=scale.ppm, source=scale.source, error_share=scale.error, confirmed=scale.confirmed,
                    detail=scale.detail)  # fmt: skip
        return ToolOutput(data=data, evidence=evidence, checks=(scale_check(scale),))

    def measure_length(arguments: dict[str, Any]) -> ToolOutput:
        try:
            x0, y0, x1, y1 = (float(arguments[k]) for k in ("x0", "y0", "x1", "y1"))
        except (KeyError, TypeError, ValueError):
            return ToolOutput(ok=False, error="give x0, y0, x1, y1 in pixels")
        scale = reading.scale
        if scale is None:
            return ToolOutput(ok=False, error=f"no_scale: {no_scale_reason(reading)}")
        pixels = math.hypot(x1 - x0, y1 - y0)
        metres, margin = length_m(scale, pixels)
        data = {
            "metres": round(metres, 3), "margin_m": round(margin, 3), "pixels": round(pixels, 1),
            "px_per_m": scale.ppm, "scale_source": scale.source,
            "note": "the straight distance between the two points. The margin holds the scale error and 2 px at "
            "each end; it does not hold an error in where the points were put",
        }  # fmt: skip
        evidence = (
            Evidence(kind="mark", points=((x0, y0), (x1, y1)), note="the two ends"),
            Evidence(kind="scale", ref=scale.detail),
        )
        return ToolOutput(data=data, evidence=evidence, checks=(scale_check(scale),))

    def drawing_size(_: dict[str, Any]) -> ToolOutput:
        scale = reading.scale
        rows = []
        for d in reading.drawings:
            x0, y0, x1, y1 = d.bbox
            row: dict[str, Any] = {"entity_id": f"drawing:{d.index}", "box_px": [x0, y0, x1, y1],
                                   "width_px": x1 - x0 + 1, "height_px": y1 - y0 + 1, "caption": d.caption}  # fmt: skip
            if scale is not None:
                for side, pixels in (("width", x1 - x0 + 1), ("height", y1 - y0 + 1)):
                    metres, margin = length_m(scale, pixels)
                    row[f"{side}_m"], row[f"{side}_margin_m"] = round(metres, 2), round(margin, 2)
            rows.append(row)
        data: dict[str, Any] = {
            "drawings": rows,
            "note": "each drawing is a connected piece of line work, largest first, with the caption nearest above "
            "or below it. The box runs to the outer face of the lines: a dimension chain or a ground line drawn "
            "past the building makes it larger than the building. Check the caption before you use a size",
        }
        if scale is None:
            data["sizes_in_metres"] = f"no_scale: {no_scale_reason(reading)}"
            return ToolOutput(data=data)
        evidence = tuple(
            Evidence(kind="polygon", points=((d.bbox[0], d.bbox[1]), (d.bbox[2], d.bbox[1]), (d.bbox[2], d.bbox[3]),
                                             (d.bbox[0], d.bbox[3])), ref=f"drawing:{d.index}")
            for d in reading.drawings
        )  # fmt: skip
        box = Check(id="error_band", label="Box of the line work", state="warn", factor=SCAN_DRAWING_BOX.confidence,
                    detail="the box can include dimension chains and ground lines")  # fmt: skip
        return ToolOutput(data=data, evidence=evidence, checks=(scale_check(scale), box))

    def look(arguments: dict[str, Any]) -> ToolOutput:
        question = str(arguments.get("question", "")).strip()
        if not question:
            return ToolOutput(ok=False, error="give the question to look for")
        region: tuple[int, int, int, int] | None = None
        if all(k in arguments for k in ("x0", "y0", "x1", "y1")):
            try:
                x0, y0, x1, y1 = (round(float(arguments[k])) for k in ("x0", "y0", "x1", "y1"))
            except (TypeError, ValueError):
                return ToolOutput(ok=False, error="x0, y0, x1, y1 must be numbers in pixels")
            region = (x0, y0, x1, y1)
        seen = scan_look.look(rgb, question, region)
        return look_output(seen)

    region_args = {k: {"type": "number"} for k in ("x0", "y0", "x1", "y1")}
    tools = [
        *text_tools,
        ToolSpec(
            "read_title_block",
            "The title block and caption facts that OCR reads: title, years, dates, architect, drawn by, measured "
            "by, builder, sheet number, printed scale and the kind of drawing (floor plan, elevation, section, site "
            "plan, detail), each with the text it comes from.",
            NO_ARGS,
            read_title_block,
        ),
        ToolSpec(
            "read_scale",
            "The scale of the scan in pixels per metre, with its witnesses (scale bars with their unit, dimension "
            "lines, the user's two points), and the printed ratios. When no scale is proven it gives the reason.",
            NO_ARGS,
            read_scale,
        ),
        ToolSpec(
            "measure_length",
            "The straight distance in metres between two points in pixels, with its margin. Fails with no_scale when "
            "the scale of the scan is not proven.",
            drawing_sheet._args(region_args, ["x0", "y0", "x1", "y1"]),  # noqa: SLF001 - the shared schema helper
            measure_length,
        ),
        ToolSpec(
            "drawing_size",
            "The drawings on the scan (connected line work, largest first) with their box in pixels and caption, and "
            "their width and height in metres with a margin when the scale is proven.",
            NO_ARGS,
            drawing_size,
        ),
        ToolSpec(
            "look",
            "Ask two vision models a question about the scan, or about a region of it (x0, y0, x1, y1 in pixels). "
            "For what OCR cannot read: handwriting, symbols, counts of windows, columns or drawings, the kind of "
            "drawing. A model reading, not a measurement: give a count only when both models agree and are sure.",
            {"type": "object", "properties": {"question": {"type": "string"}, **region_args}, "required": ["question"],
             "additionalProperties": False},
            look,
            method="model",
        ),
    ]  # fmt: skip
    return CONTEXT.format(width=width, height=height), tools


def look_output(seen: scan_look.Look) -> ToolOutput:
    """The tool result of a look: the readings, what they agree on, and how sure that is."""
    if not seen.available:
        errors = "; ".join(f"{r.model}: {r.error}" for r in seen.readings)[:400]
        return ToolOutput(ok=False, cost_usd=seen.cost_usd,
                          error=f"vision model not available ({errors}): abstain with reason unsupported, and say "
                          "that the question needs a vision model")  # fmt: skip
    readings = [
        {"model": r.model, "answer": r.answer, "count": r.count, "sure": r.sure, "seen": r.seen, "error": r.error}
        for r in seen.readings
    ]
    rate = scan_look.LOOK_AGREED if seen.agreed_answer is not None else scan_look.LOOK_SINGLE
    data: dict[str, Any] = {"readings": readings, "agreed_answer": seen.agreed_answer, "agreed_count":
                            seen.agreed_count, "method": "vision model reading, not a measurement"}  # fmt: skip
    if seen.agreed_answer is None:
        data["note"] = ("the two models do not agree, or one is not sure: abstain with reason ambiguous and give "
                        "the readings as best_estimate")  # fmt: skip
    else:
        data["note"] = "both models agree and are sure. It is still a model reading: say so in the answer"
    check = Check(id="cross_check", label="Two vision models", state="pass" if seen.agreed_answer else "warn",
                  factor=rate.confidence, detail=rate.basis)  # fmt: skip
    evidence = ()
    if seen.region is not None:
        x0, y0, x1, y1 = seen.region
        evidence = (Evidence(kind="polygon", points=((x0, y0), (x1, y0), (x1, y1), (x0, y1)), note="looked here"),)
    return ToolOutput(data=data, evidence=evidence, cost_usd=seen.cost_usd, confidence=rate.confidence,
                      checks=(check,))  # fmt: skip


def scan_lines(path: str | Path, rgb: np.ndarray | None = None) -> list[TextLine] | None:
    """The raw OCR lines of a raster when it is a historic scan, else None.

    A large sheet is not a scan (the sheet tools read it). A raster that the count model knows (a CubiCasa or a
    Swiss style plan), or one where OCR reads room numbers or printed areas, is not a scan either. The count model
    is fast (0.1 s); OCR runs only for a raster that the model doubts, and its lines are cached on disk.
    """
    from bp.tools import count_head, ocr, sheet_text  # noqa: PLC0415 - torch and OCR load only for rasters

    rgb = ocr.to_rgb(path) if rgb is None else rgb
    if sheet_text.is_sheet(rgb):
        return None
    counts = count_head.count_plan(Path(path), count_head.get_model("e1.json"))
    if not scan_reading.looks_unlike_flat_plan(counts):
        return None
    lines = scan_reading.read_lines(rgb)
    return lines if scan_reading.flat_plan_signs(lines) < scan_reading.FLAT_PLAN_NUMBERS else None
