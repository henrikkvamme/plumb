"""Facts of a historic scan: its text labels, its scale and witnesses, its drawings, and the title block facts.

The same reading as the agent tools (`scan_reading.read_scan`), in the types of the sheet facts. Each fact says
where it comes from and how sure it is. No benchmark of historic scans with true answers exists yet, so the rates
are rules that say so (`bp.rates.unmeasured`), never invented measurements.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bp import rates
from bp.facts import DocumentFacts, Entity, Fact, Page, rated
from bp.solvers import scan_tools
from bp.tools import scan_reading, sheet_plan

if TYPE_CHECKING:
    from pathlib import Path

    import numpy as np

    from bp.contract import Calibration
    from bp.tools.ocr import TextLine
    from bp.tools.scan_reading import ScanReading

MAX_LABELS = 400
# The title block keys, in the order the summary gives them, from the roles of scan_reading.TitleText.
TITLE_KEYS = {
    "title": "title", "year": "year", "date": "date", "architect": "architect", "drawn by": "drawn_by",
    "measured by": "measured_by", "builder": "builder", "sheet number": "sheet_number",
    "printed scale": "printed_scale", "kind": "drawing_kind",
}  # fmt: skip
TITLE_SOURCE = "OCR of the title block and captions"


def _scale_entities(reading: ScanReading) -> tuple[list[Entity], list[Fact]]:
    """The scale entity (when proven) and one entity per witness: each scale bar and each dimension line."""
    out: list[Entity] = []
    scale = reading.scale
    if scale is not None:
        rate = scan_tools.scale_rate(scale)
        fact = Fact(key="px_per_metre", value=scale.ppm, unit="px/m", status="known", confidence=rate.confidence,
                    source=scale.source, note=scale.detail, checks=(scan_tools.scale_check(scale),),
                    basis=rate.basis, margin=round(scale.ppm * scale.error, 3), margin_share=None,
                    margin_basis="the spread of the scale witnesses and the placing of their marks")  # fmt: skip
        given = reading.calibration.points if reading.calibration and scale.source == "user" else None
        points = given or ((0.0, 0.0), (scale.ppm, 0.0))
        out.append(Entity(id="scale", kind="scale", label=f"Scale ({scale.source})", geometry="line", points=points,
                          facts=(fact,)))  # fmt: skip
        summary = fact
    else:
        summary = rated("px_per_metre", None, rates.NOT_GIVEN, unit="px/m", note=scan_tools.no_scale_reason(reading))
    for index, bar in enumerate(reading.bars):
        if bar.ppm:
            fact = rated("px_per_metre", bar.ppm, scan_tools.SCAN_SCALE_ONE, unit="px/m", source="scale bar",
                         note=f"{bar.px_per_unit:g} px per {bar.unit}, labels {', '.join(bar.texts)}")  # fmt: skip
        else:
            unit = bar.unit or "unknown unit"
            fact = rated("px_per_unit", bar.px_per_unit, scan_tools.SCAN_SCALE_ONE, unit=f"px/{unit}",
                         source="scale bar", note="the unit has no value in metres or is not readable")  # fmt: skip
        out.append(Entity(id=f"scale:bar:{index}", kind="scale", label=" ".join(bar.texts)[:80], geometry="line",
                          points=((bar.xs_px[0], bar.row_y), (bar.xs_px[-1], bar.row_y)), facts=(fact,)))  # fmt: skip
    if reading.dimensions is not None:
        for index, witness in enumerate(reading.dimensions.witnesses):
            fact = rated("px_per_metre", round(witness.pixels / witness.metres, 3), scan_tools.SCAN_TEXT,
                         unit="px/m", source="dimension line", note=f"{witness.pixels:.0f} px for {witness.metres:g} m")  # fmt: skip
            out.append(Entity(id=f"scale:witness:{index}", kind="scale", label=witness.text, geometry="line",
                              points=tuple(witness.line), facts=(fact,)))  # fmt: skip
    return out, [summary]


def _drawing_entities(reading: ScanReading) -> list[Entity]:
    scale = reading.scale
    out = []
    for d in reading.drawings:
        x0, y0, x1, y1 = d.bbox
        facts = [rated("caption", d.caption, scan_tools.SCAN_TEXT, source="OCR, the text nearest above or below")]
        if scale is not None:
            for key, pixels in (("width", x1 - x0 + 1), ("height", y1 - y0 + 1)):
                metres, margin = scan_tools.length_m(scale, pixels)
                rate = scan_tools.SCAN_DRAWING_BOX.lowered(scan_tools.scale_rate(scale).confidence, "and the scale")
                fact = rated(key, round(metres, 3), rate, unit="m", status="estimated", source="box of the line work",
                             checks=(scan_tools.scale_check(scale),))  # fmt: skip
                facts.append(fact.model_copy(update={"margin": round(margin, 3), "margin_basis": "the scale error "
                                                     "and 2 px at each end; not measured on a benchmark"}))  # fmt: skip
        out.append(Entity(id=f"drawing:{d.index}", kind="element", group="drawing", label=d.caption or
                          f"Drawing {d.index + 1}", geometry="box", points=((x0, y0), (x1, y1)), facts=tuple(facts)))  # fmt: skip
    return out


def _label_entities(reading: ScanReading) -> list[Entity]:
    """One entity per text label, with the title block facts that the label gives."""
    roles: dict[str, list[Fact]] = {}
    for item in reading.title:
        key = TITLE_KEYS.get(item.role, item.role.replace(" ", "_"))
        fact = rated(key, item.value, scan_tools.SCAN_TITLE, source=TITLE_SOURCE, note=item.text[:120])
        roles.setdefault(sheet_plan.label_id(item.label), []).append(fact)
    out = []
    for label in reading.labels[:MAX_LABELS]:
        entity_id = sheet_plan.label_id(label)
        text = rated("text", label.text, scan_tools.SCAN_TEXT, source="OCR")
        box = ((label.bbox[0], label.bbox[1]), (label.bbox[2], label.bbox[3]))
        out.append(Entity(id=entity_id, kind="label", label=label.text[:80], geometry="box", points=box,
                          facts=(text, *roles.get(entity_id, ()))))  # fmt: skip
    return out


def _title_summary(reading: ScanReading) -> list[Fact]:
    """The first value of each title block key, with the label it comes from in the note."""
    first: dict[str, Fact] = {}
    for item in reading.title:
        key = TITLE_KEYS.get(item.role, item.role.replace(" ", "_"))
        if key not in first:
            note = f"from {sheet_plan.label_id(item.label)}: {item.text[:100]}"
            first[key] = rated(key, item.value, scan_tools.SCAN_TITLE, source=TITLE_SOURCE, note=note)
    return [first[key] for key in TITLE_KEYS.values() if key in first]


def scan_facts(
    path: str | Path, rgb: np.ndarray, calibration: Calibration | None = None, lines: list[TextLine] | None = None
) -> DocumentFacts | None:
    """The facts of a historic scan, or None when the raster is not one (see `scan_tools.scan_lines`)."""
    raw = lines if lines is not None else scan_tools.scan_lines(path, rgb)
    if raw is None:
        return None
    reading = scan_reading.read_scan(rgb, calibration, raw)
    height, width = rgb.shape[:2]
    scale_entities, scale_summary = _scale_entities(reading)
    labels = _label_entities(reading)
    drawings = _drawing_entities(reading)
    unknown = [
        "A historic scan: no room model and no door or window detector reads it. Counts need the look tool of "
        "the agent, which gives a model reading.",
        "OCR reads printed text well and handwriting badly: handwritten names, dates and notes can be missing.",
    ]
    if reading.scale is None:
        unknown.append(f"No proven scale: {scan_tools.no_scale_reason(reading)}.")
    summary = [
        *scale_summary,
        *_title_summary(reading),
        rated("text_labels", len(reading.labels), scan_tools.SCAN_TEXT, source="OCR"),
        rated("drawings", len(drawings), scan_tools.SCAN_DRAWING_BOX, status="estimated",
              source="connected line work, the largest 6"),
    ]  # fmt: skip
    return DocumentFacts(kind="scan", pages=(Page(index=0, width=float(width), height=float(height)),),
                         entities=(*scale_entities, *drawings, *labels), unknown=tuple(unknown),
                         summary=tuple(summary))  # fmt: skip
