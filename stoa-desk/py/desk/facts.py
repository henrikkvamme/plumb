"""The facts of one document as entities that the desk can draw and list.

An entity is one thing on the drawing: a room, a door, a fixture, the scale. It has a geometry in the coordinate
space of the page and a list of facts. Each fact says how it is known: `known` (read or computed by a tested
deterministic tool), `estimated` (a model or a measurement with an error band) or `unknown` (the document
does not give it).

This module reads with the tools of `bp`. It does not change them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bp.tools import pdf_text, swiss_plan

if TYPE_CHECKING:
    from collections.abc import Callable

from desk import dxfpage

Json = dict[str, Any]


@dataclass
class DocumentFacts:
    pages: list[Json]
    entities: list[Json] = field(default_factory=list)
    summary: list[Json] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    # The entity ids that one row of a tool result is about.
    link: Callable[[Json], list[str]] = lambda _row: []
    conflicts: list[Json] = field(default_factory=list)
    scale: Json | None = None


def fact(key: str, value: object, status: str, source: str, unit: str = "", note: str = "") -> Json:
    if isinstance(value, float) and unit in {"m²", "m", "ft²", "ft"}:
        value = f"{value:.2f}"
    return {"key": key, "value": None if value is None else str(value), "unit": unit, "status": status,
            "source": source, "note": note}  # fmt: skip


def _box(bbox: tuple[float, float, float, float]) -> list[list[float]]:
    return [[bbox[0], bbox[1]], [bbox[2], bbox[3]]]


def _bounds(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def swiss(path: str) -> DocumentFacts:  # noqa: C901, PLR0915 - one reader, one pass over the plan
    page = pdf_text.read_page(path)
    plan = swiss_plan.compile_plan(page)
    scale = plan.scale
    scale_text = f"1:{scale.ratio}" if scale else None
    area_source = f"room polygon at the sheet scale {scale_text}" if scale else "no scale"
    entities: list[Json] = []

    if scale is not None:
        witnesses = [{"what": "title block", "says": scale.evidence.ref, "ok": True}]
        if scale.bar_points_per_metre is not None:
            measured = 1.0 / (scale.bar_points_per_metre * scale.metres_per_point / scale.ratio)
            witnesses.append({"what": "scale bar", "says": f"1:{measured:.1f} measured on the bar",
                              "ok": bool(scale.agrees)})  # fmt: skip
        status = "known" if scale.agrees else "estimated"
        at = scale.evidence.points[0]
        entities.append({
            "id": "scale", "kind": "scale", "group": "scale", "page": 0, "label": f"Scale {scale_text}",
            "geometry": "point", "points": [[at[0], at[1]]],
            "facts": [
                fact("Scale", scale_text, status, "title block" + (", confirmed by the scale bar" if scale.agrees else "")),
                fact("Metres per point", round(scale.metres_per_point, 5), status, "scale ratio and paper size"),
            ],
        })  # fmt: skip

    rooms_of: dict[str, list[str]] = {}
    for r in plan.rooms:
        warnings = swiss_plan.room_area(plan, r.number).warnings
        status = "known" if r.area_m2 is not None and not warnings else "estimated" if r.area_m2 is not None else "unknown"
        name = f"{r.label} {r.number}" if r.label else r.number
        facts = [
            fact("Name", r.label, "known" if r.label else "unknown", "text above the room number"),
            fact("Number", r.number, "known", "text on the sheet"),
            fact("Area", r.area_m2, status, area_source, "m²", "; ".join(warnings)),
        ]
        if r.printed_area_m2 is not None:
            facts.append(fact("Printed area", r.printed_area_m2, "known", "text below the room number", "m²"))
        facts.append(fact("Apartment", r.apartment, "known" if r.apartment else "unknown", "red unit outline that holds the room"))
        facts.append(fact("Outdoor", "yes" if r.outdoor else "no", "known", "fill colour and label"))
        entity: Json = {"id": f"room:{r.number}", "kind": "room", "group": "room", "page": 0, "label": name,
                        "facts": facts, "warnings": list(warnings)}  # fmt: skip
        if len(r.polygon) >= 3:
            entity |= {"geometry": "polygon", "points": [[x, y] for x, y in r.polygon]}
        else:
            entity |= {"geometry": "point", "points": [[r.at[0], r.at[1]]]}
        entities.append(entity)
        if r.apartment:
            rooms_of.setdefault(r.apartment, []).append(r.number)

    for a in plan.apartments:
        area = swiss_plan.apartment_area(plan, a.letter)
        status = "known" if area.value is not None and not area.warnings else "estimated"
        entities.append({
            "id": f"apartment:{a.letter}", "kind": "apartment", "group": "apartment", "page": 0,
            "label": f"Apartment {a.letter}", "geometry": "point", "points": [[a.at[0], a.at[1]]],
            "members": [f"room:{n}" for n in rooms_of.get(a.letter, [])],
            "facts": [
                fact("Living area", area.value, status, "sum of its indoor rooms", "m²", "; ".join(area.warnings)),
                fact("Rooms", len(rooms_of.get(a.letter, [])), "known", "rooms inside the unit outline"),
            ],
            "warnings": list(area.warnings),
        })  # fmt: skip

    seen: set[tuple[float, ...]] = set()
    doors = 0
    for e in plan.doors.evidence:
        key = tuple(round(v, 1) for p in e.points for v in p)
        if key in seen or not e.points:
            continue
        seen.add(key)
        doors += 1
        entities.append({
            "id": f"door:{doors}", "kind": "door", "group": "door", "page": 0, "label": f"Door {doors}",
            "geometry": "box", "points": _box(_bounds(list(e.points))),
            "facts": [fact("Kind", "door opening", "known", "dark grey door symbol in the vector drawing")],
        })  # fmt: skip

    counts: dict[str, int] = {}
    for f in plan.fixtures:
        if f.kind == "other":
            continue
        counts[f.kind] = counts.get(f.kind, 0) + 1
        size = f"{f.edge_long_m:.2f} x {f.edge_short_m:.2f}"
        entities.append({
            "id": f"{f.kind}:{counts[f.kind]}", "kind": "fixture", "group": f.kind, "page": 0,
            "label": f"{f.kind.capitalize()} {counts[f.kind]}", "geometry": "box", "points": _box(f.bbox),
            "facts": [
                fact("Kind", f.kind, "known", "symbol drawn inside the box"),
                fact("Size", size, "known" if scale else "unknown", "box edges at the sheet scale", "m"),
            ],
        })  # fmt: skip

    def link(row: Json) -> list[str]:
        number, letter, kind = row.get("number"), row.get("letter"), row.get("kind")
        if isinstance(number, str):
            return [f"room:{number}"]
        if isinstance(letter, str):
            return [f"apartment:{letter}", *[f"room:{n}" for n in row.get("rooms", []) if isinstance(n, str)]]
        if isinstance(kind, str) and "count" in row:
            return [e["id"] for e in entities if e["group"] == kind]
        return []

    measured = sum(1 for r in plan.rooms if r.area_m2 is not None)
    summary = [
        fact("Scale", scale_text, "known" if scale and scale.agrees else "estimated" if scale else "unknown",
             "title block and scale bar" if scale and scale.agrees else "title block" if scale else "not found"),
        fact("Rooms", len(plan.rooms), "known", "room numbers on the sheet"),
        fact("Rooms with a measured area", measured, "known", area_source),
        fact("Apartments", len(plan.apartments), "known", "unit tags (Whg. or App.)"),
        fact("Door openings", plan.doors.distinct, "known", "door symbols, each place once"),
        *[fact(kind.capitalize() + "s", swiss_plan.fixture_count(plan, kind).value, "known", "fixture symbols")
          for kind in sorted(counts)],
    ]  # fmt: skip
    unknown = ["Room heights", "Wall materials and finishes", "Volumes", "Anything on other storeys"]
    return DocumentFacts(
        pages=[{"index": 0, "width": page.width, "height": page.height, "unit": "pt"}],
        entities=entities,
        summary=summary,
        unknown=unknown,
        link=link,
        scale=None if scale is None else {"ratio": scale.ratio, "agrees": scale.agrees,
                                          "bar": scale.bar_points_per_metre is not None},
    )  # fmt: skip


SHEET_KEYS = {
    "area": "Area", "perimeter": "Wall length", "doors": "Doors", "text": "Text", "leaf_width": "Leaf width",
    "px_per_metre": "Pixels per metre",
}  # fmt: skip
SHEET_UNKNOWN = ["Room heights", "Wall materials and finishes", "Anything on other sheets"]


def _figure(value: object) -> str | None:
    return None if value is None else f"{value:g}" if isinstance(value, float) else str(value)


def _sheet_fact(item: Any) -> Json:
    key = SHEET_KEYS.get(item.key, item.key.replace("_", " ").capitalize())
    unit = {"m2": "m²", "m3": "m³"}.get(item.unit, item.unit)
    out = fact(key, _figure(item.value), item.status, item.source, unit, item.note) | {"confidence": item.confidence}
    if getattr(item, "basis", ""):
        out["basis"] = item.basis
    margin = getattr(item, "margin", None)
    if margin is not None:
        out["margin"] = f"± {margin:.2f} {unit}".strip()
        share = getattr(item, "margin_share", None)
        basis = getattr(item, "margin_basis", "")
        out["marginBasis"] = basis or ("" if share is None else f"{share:.0%} of the test items were inside this margin")
    return out


def sheet(path: str, calibration: Any = None) -> DocumentFacts | None:  # noqa: ANN401 - Calibration of bp
    """The facts that `bp.facts` reads: a large sheet, an IFC model, a DXF plan or a small raster plan."""
    from bp.facts import document_facts  # noqa: PLC0415 - bp.facts loads the readers, only these kinds need them

    found = document_facts(path, calibration)
    if found.kind == "unsupported" or not (found.entities or found.summary):
        return None
    flat = Path(path).suffix.lower() != ".ifc"
    drawn = dxfpage.is_dxf(Path(path))
    pad = dxfpage.PAD_M if drawn else 0.0
    pages = [{"index": p.index, "width": p.width, "height": p.height, "unit": p.unit} for p in found.pages]
    if drawn:
        _, _, width, height, _ = dxfpage.frame(Path(path))
        pages = [{"index": 0, "width": width, "height": height, "unit": "m"}]
    entities: list[Json] = []
    counts: dict[str, int] = {}
    for item in found.entities:
        counts[item.kind] = counts.get(item.kind, 0) + 1
        area = next((f for f in item.facts if f.key == "area"), None)
        entities.append({
            "id": item.id, "kind": item.kind, "group": getattr(item, "group", "") or item.kind, "page": item.page,
            "label": f"Door {counts[item.kind]}" if item.kind == "door" and found.kind == "sheet" else item.label,
            "geometry": item.geometry, "points": [[x + pad, y + pad] for x, y in item.points] if flat and item.points else [[0.0, 0.0]],
            "facts": [_sheet_fact(f) for f in item.facts]
            + ([fact("Area", None, "unknown", "room_area", "m²", "no closed outline around this name")]
               if item.kind == "room" and area is None and found.kind == "sheet" else []),
            "members": list(item.members),
        })  # fmt: skip
    if not flat:
        for entity in entities:
            entity["geometry"] = "point"
    summary = [_sheet_fact(f) for f in getattr(found, "summary", ())]
    if not summary and found.kind == "sheet":
        outlined = sum(1 for e in found.entities if e.kind == "room" and e.geometry == "polygon")
        scale = next((e for e in found.entities if e.id == "scale"), None)
        summary = [
            fact("Room names", counts.get("room", 0), "known", "text on the sheet (OCR)"),
            fact("Rooms with an outline", outlined, "estimated", "closed wall lines around a room name"),
            fact("Door leaves", counts.get("door", 0), "estimated", "leaf line with a swing arc"),
            fact("Text labels", counts.get("label", 0), "known", "OCR"),
        ]
        if scale is not None and scale.facts:
            first = scale.facts[0]
            summary.insert(0, fact("Scale, px per m", f"{first.value:g}", first.status, first.source, "", first.note))
        else:
            summary.insert(0, fact("Scale", None, "unknown", "", "", "no scale found on the sheet"))
    known = {e["id"] for e in entities}
    return DocumentFacts(
        pages=pages if flat else [],
        entities=entities,
        summary=summary,
        unknown=[*found.unknown, *(SHEET_UNKNOWN if found.kind == "sheet" else [])],
        link=lambda row: [row["entity_id"]] if isinstance(row, dict) and row.get("entity_id") in known else [],
        conflicts=[{"id": c.id, "entityIds": list(c.entity_ids), "text": c.text} for c in getattr(found, "conflicts", ())],
    )


def page_only(path: str) -> DocumentFacts | None:
    """A document with no facts reader yet: its pages, so the desk shows the drawing."""
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        import fitz  # noqa: PLC0415

        with fitz.open(path) as document:
            pages = [{"index": i, "width": p.rect.width, "height": p.rect.height, "unit": "pt"} for i, p in enumerate(document)]
    elif suffix in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}:
        from PIL import Image  # noqa: PLC0415

        with Image.open(path) as image:
            pages = [{"index": 0, "width": float(image.width), "height": float(image.height), "unit": "px"}]
    else:
        return None
    return DocumentFacts(pages=pages, unknown=["The desk has no facts reader for this kind of document yet"])


def read(kind: str, path: str, calibration: Any = None) -> DocumentFacts | None:  # noqa: ANN401 - Calibration of bp
    """The facts of a document: the Swiss plan reader, the readers of `bp.facts`, or the pages alone."""
    if kind == "plan_pdf":
        return swiss(path)
    try:
        found = sheet(path, calibration)
    except Exception:  # noqa: BLE001 - a reader that fails must not stop the drawing from opening
        found = None
    return found if found is not None else page_only(path)
