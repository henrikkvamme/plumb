"""Labels and benchmarks for the raster tools (OCR, scale, room areas) on Swiss Dwellings PNG sheets.

It runs outside the sandbox: it reads the DXF and the PDF sibling of each PNG. Labels come from the DXF; the
PDF gives only the positions of the room numbers, which fix the map from DXF metres to PNG pixels (one scale and
one shift per axis, fitted by least squares; residual about 0.1 px). Only dev and val sheets are read here; lock
sheets stay unseen. `bench()` measures on val sheets and writes experiments/tools/raster.json.

Run: uv run python -m bp.toolbench.raster [ocr|scale|rooms|all] [n_sheets]
"""

from __future__ import annotations

import json
import math
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from functools import cache
from typing import TYPE_CHECKING, Any

import ezdxf
import numpy as np
from ezdxf import entities as dxf_entities
from PIL import Image
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry  # noqa: TC002 - pydantic needs it at run time

from bp.contract import Frozen
from bp.hardcases.common import group_key, split_groups
from bp.hardcases.swiss_facts import CACHE as FACTS_CACHE
from bp.hardcases.swiss_facts import NUM, SWISS_DIR, net_holes
from bp.paths import DATASET, EXPERIMENTS
from bp.tools.pdf_text import read_page

if TYPE_CHECKING:
    from pathlib import Path

OUT = EXPERIMENTS / "tools" / "raster.json"
CUBICASA_DIR = DATASET / "data" / "cubicasa5k"
TRUE_PPM_100 = 150.0 / 0.0254 / 100.0  # 59.0551 px per metre at 1:100 on a 150 dpi render


# ----------------------------------------------------------------------------- labels


class LabelText(Frozen):
    text: str
    x: float  # px
    y: float
    h: float  # text height in px


class LabelRoom(Frozen):
    number: str
    label: str | None
    area_m2: float  # DXF polygon area, holes subtracted
    apartment: str | None
    outdoor: bool
    printed_m2: float | None
    x: float  # the number position in px
    y: float


class SheetLabels(Frozen):
    model_config = Frozen.model_config | {"arbitrary_types_allowed": True}
    stem: str
    partition: str
    width: int
    height: int
    ppm: float  # px per metre of the map (the true scale of the sheet)
    map: tuple[float, float, float, float]  # x_px = a*x + b, y_px = c*y + d
    residual_px: float
    texts: tuple[LabelText, ...]
    rooms: tuple[LabelRoom, ...]
    room_shapes: tuple[BaseGeometry, ...]  # px, same order as rooms
    other_shapes: tuple[BaseGeometry, ...]  # numbered nowhere (shafts are holes already)
    walls: tuple[BaseGeometry, ...]
    openings: tuple[BaseGeometry, ...]
    units: tuple[BaseGeometry, ...]
    separators: tuple[tuple[tuple[float, float], tuple[float, float]], ...]  # 2-point ROOM_OUTLINE lines


@cache
def partitions() -> dict[str, str]:
    """Partition of each Swiss stem: dev, val or test (the lock partition)."""
    keyer, groups = group_key(), split_groups()
    out: dict[str, str] = {}
    for png in SWISS_DIR.glob("*.png"):
        out[png.stem] = groups.get(keyer(f"data/swiss_dwellings/{png.name}"), "")
    return out


def stems(partition: str) -> list[str]:
    if partition == "test":
        msg = "the lock partition is never read here"
        raise ValueError(msg)
    return sorted(s for s, p in partitions().items() if p == partition)


@cache
def _facts() -> dict[str, dict[str, Any]]:
    data = json.loads(FACTS_CACHE.read_text())
    return {f["stem"]: f for f in data}


def _points(entity: dxf_entities.LWPolyline) -> list[tuple[float, float]]:
    return [(float(p[0]), float(p[1])) for p in entity.get_points()]


def _text_anchor(entity: dxf_entities.Text) -> tuple[float, float]:
    halign, valign = int(entity.dxf.get("halign", 0)), int(entity.dxf.get("valign", 0))
    point = entity.dxf.get("align_point") if (halign or valign) else None
    point = point if point is not None else entity.dxf.insert
    return float(point[0]), float(point[1])


def fit_map(pairs: list[tuple[float, float, float, float]]) -> tuple[tuple[float, float, float, float], float]:
    """One scale for both axes (y flipped) and a shift per axis, by least squares."""
    a = np.asarray(pairs, dtype=float)
    mx, my = a[:, 0] - a[:, 0].mean(), a[:, 1] - a[:, 1].mean()
    px, py = a[:, 2] - a[:, 2].mean(), a[:, 3] - a[:, 3].mean()
    scale = float((mx @ px - my @ py) / (mx @ mx + my @ my))
    bx = float(a[:, 2].mean() - scale * a[:, 0].mean())
    by = float(a[:, 3].mean() + scale * a[:, 1].mean())
    res = np.hypot(a[:, 2] - (scale * a[:, 0] + bx), a[:, 3] - (-scale * a[:, 1] + by))
    return (scale, bx, -scale, by), float(res.max())


def _move(shape: BaseGeometry, m: tuple[float, float, float, float]) -> BaseGeometry:
    from shapely import affinity  # noqa: PLC0415

    return affinity.affine_transform(shape, [m[0], 0.0, 0.0, m[2], m[1], m[3]])


def sheet_labels(stem: str) -> SheetLabels:  # noqa: C901, PLR0912, PLR0915 - one pass over one DXF
    part = partitions().get(stem, "")
    if part == "test":
        msg = "lock sheet"
        raise ValueError(msg)
    doc = ezdxf.readfile(SWISS_DIR / f"{stem}.dxf")
    space = doc.modelspace()
    raw_texts: list[tuple[str, float, float, float]] = []
    rooms_m: list[Polygon] = []
    walls_m: list[BaseGeometry] = []
    open_m: list[BaseGeometry] = []
    units_m: list[BaseGeometry] = []
    seps_m: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for e in space:
        layer = e.dxf.layer
        if isinstance(e, dxf_entities.Text) and layer == "ROOM_TEXT":
            x, y = _text_anchor(e)
            raw_texts.append((str(e.dxf.text), x, y, float(e.dxf.height)))
            continue
        if not isinstance(e, dxf_entities.LWPolyline):
            continue
        pts = _points(e)
        if layer == "ROOM_OUTLINE":
            if len(pts) >= 3:
                rooms_m.append(Polygon(pts).buffer(0))
            elif len(pts) == 2:
                seps_m.append((pts[0], pts[1]))
        elif layer == "WALL" and len(pts) >= 3 and e.closed:
            walls_m.append(Polygon(pts).buffer(0))
        elif layer == "DOOR" and len(pts) == 5:
            open_m.append(Polygon(pts[:4]).buffer(0))
        elif layer == "WINDOW" and len(pts) == 4 and e.closed:
            open_m.append(Polygon(pts).buffer(0))
        elif layer == "UNIT_OUTLINE" and len(pts) >= 3:
            units_m.append(Polygon(pts).buffer(0))
    page = read_page(SWISS_DIR / f"{stem}.pdf")
    with Image.open(SWISS_DIR / f"{stem}.png") as im:
        width, height = im.size
    k = width / page.width
    runs = {s.text: s for s in page.runs if NUM.match(s.text)}
    pairs = [(x, y, runs[t].cx * k, runs[t].cy * k) for t, x, y, _ in raw_texts if NUM.match(t) and t in runs]
    if len(pairs) < 2:
        msg = f"{stem}: too few numbers to fit the map"
        raise ValueError(msg)
    m, residual = fit_map(pairs)
    scale = m[0]
    texts = tuple(LabelText(text=t, x=m[0] * x + m[1], y=m[2] * y + m[3], h=h * scale) for t, x, y, h in raw_texts)
    nets = net_holes(rooms_m)
    facts = {r["num"]: r for r in _facts().get(stem, {}).get("rooms", [])}
    rooms: list[LabelRoom] = []
    shapes: list[BaseGeometry] = []
    used: set[int] = set()
    for t, x, y, _ in raw_texts:
        if not NUM.match(t):
            continue
        pt = ShapelyPoint(x, y)
        hits = [i for i, p in enumerate(nets) if p.contains(pt)]
        if not hits:
            continue
        best = min(hits, key=lambda i: nets[i].area)
        used.add(best)
        f = facts.get(t, {})
        rooms.append(
            LabelRoom(
                number=t,
                label=f.get("label"),
                area_m2=round(nets[best].area, 4),
                apartment=f.get("unit"),
                outdoor=bool(f.get("outdoor", False)),
                printed_m2=f.get("printed"),
                x=m[0] * x + m[1],
                y=m[2] * y + m[3],
            )
        )
        shapes.append(_move(nets[best], m))
    return SheetLabels(
        stem=stem,
        partition=part,
        width=width,
        height=height,
        ppm=scale,
        map=m,
        residual_px=round(residual, 4),
        texts=texts,
        rooms=tuple(rooms),
        room_shapes=tuple(shapes),
        other_shapes=tuple(_move(p, m) for i, p in enumerate(nets) if i not in used),
        walls=tuple(_move(w, m) for w in walls_m),
        openings=tuple(_move(o, m) for o in open_m),
        units=tuple(_move(u, m) for u in units_m),
        separators=tuple(
            ((m[0] * a[0] + m[1], m[2] * a[1] + m[3]), (m[0] * b[0] + m[1], m[2] * b[1] + m[3])) for a, b in seps_m
        ),
    )


# ----------------------------------------------------------------------------- OCR benchmark

OCR_CACHE = EXPERIMENTS / "cache" / "raster-ocr"


def cached_lines(png: Path, upscale: float = 2.0) -> tuple[list[Any], float]:
    """OCR lines of one image, cached (the cache is git-ignored). It returns the lines and the OCR seconds."""
    from bp.tools import ocr  # noqa: PLC0415

    path = OCR_CACHE / f"{png.parent.name}-{png.stem}-u{upscale:g}.json"
    if path.exists():
        data = json.loads(path.read_text())
        return [ocr.TextLine.model_validate(x) for x in data["lines"]], float(data["seconds"])
    start = time.perf_counter()
    lines = ocr.read_lines(png, upscale=upscale)
    seconds = time.perf_counter() - start
    OCR_CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"seconds": seconds, "lines": [x.model_dump() for x in lines]}))
    return lines, seconds


def _kind(text: str) -> str:
    from bp.tools import ocr  # noqa: PLC0415

    if NUM.match(text):
        return "number"
    if ocr.area_value(text) is not None:
        return "area"
    if text.startswith(("Whg.", "App.")):
        return "tag"
    return "label"


def ocr_sheet(stem: str, upscale: float = 2.0) -> dict[str, Any]:
    """Match each DXF room text to the OCR line at its place. It returns per-kind counts and position errors."""
    from bp.tools import ocr  # noqa: PLC0415

    labels = sheet_labels(stem)
    lines, seconds = cached_lines(SWISS_DIR / f"{stem}.png", upscale)
    out: dict[str, Any] = {"stem": stem, "seconds": round(seconds, 3), "kinds": {}, "errors_px": [], "misses": []}
    for t in labels.texts:
        kind = _kind(t.text)
        pad = max(2.0, 0.3 * t.h)
        near = [
            line
            for line in lines
            if line.bbox[0] - pad <= t.x <= line.bbox[2] + pad and line.bbox[1] - pad <= t.y <= line.bbox[3] + pad
        ]
        line = min(near, key=lambda ln: math.hypot(ln.cx - t.x, ln.cy - t.y)) if near else None
        found = line is not None
        if line is None:
            right = exact = False
        elif kind == "number":
            exact = line.text == t.text
            right = ocr.room_number(line.text) == t.text
        elif kind == "area":
            exact = line.text == t.text
            right = ocr.area_value(line.text) == ocr.area_value(t.text)
        else:
            exact = line.text == t.text
            right = exact
        row = out["kinds"].setdefault(kind, {"n": 0, "found": 0, "right": 0, "exact": 0})
        row["n"] += 1
        row["found"] += found
        row["right"] += right
        row["exact"] += exact
        if line is not None and right:
            out["errors_px"].append(round(math.hypot(line.cx - t.x, line.cy - t.y), 2))
        if not right and len(out["misses"]) < 6:
            out["misses"].append([t.text, line.text if line else None])
    return out


def _sum_kinds(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total: dict[str, Counter[str]] = {}
    for r in rows:
        for kind, c in r["kinds"].items():
            total.setdefault(kind, Counter()).update(c)
    out: dict[str, Any] = {}
    for kind, c in sorted(total.items()):
        n = c["n"]
        out[kind] = {
            "n": n,
            "found": round(c["found"] / n, 4),
            "right": round(c["right"] / n, 4),
            "exact": round(c["exact"] / n, 4),
        }
    errors = [e for r in rows for e in r["errors_px"]]
    out["position_error_px"] = {
        "median": round(statistics.median(errors), 3) if errors else None,
        "p95": round(float(np.percentile(errors, 95)), 3) if errors else None,
    }
    out["seconds_per_sheet"] = round(statistics.mean(r["seconds"] for r in rows), 3) if rows else None
    out["sheets"] = len(rows)
    return out


def bench_ocr(chosen: list[str], upscale: float = 2.0, jobs: int = 4) -> dict[str, Any]:
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        rows = list(pool.map(ocr_sheet, chosen, [upscale] * len(chosen)))
    summary = _sum_kinds(rows)
    summary["upscale"] = upscale
    summary["examples_of_misses"] = [m for r in rows for m in r["misses"]][:30]
    return summary


# ----------------------------------------------------------------------------- masks for training

SUPER = 4  # supersampling factor of the soft masks
BOUNDARY_PX = 2.0  # width of the room boundary band at the canonical scale


def _rings(shape: BaseGeometry) -> list[tuple[np.ndarray, list[np.ndarray]]]:
    polys = [shape] if isinstance(shape, Polygon) else list(getattr(shape, "geoms", []))
    out = []
    for p in polys:
        if not isinstance(p, Polygon) or p.is_empty:
            continue
        out.append((np.asarray(p.exterior.coords), [np.asarray(r.coords) for r in p.interiors]))
    return out


def soft_fill(canvas: np.ndarray, shape: BaseGeometry, factor: float) -> None:
    """Paint the coverage (0..255) of `shape`, scaled by `factor`, into `canvas` (max composite)."""
    import cv2  # noqa: PLC0415

    if shape.is_empty:
        return
    # fillPoly paints every sample that the outline touches; half a sample inwards removes that bias
    shape = shape.buffer(-0.5 / SUPER / factor, join_style="mitre")
    if shape.is_empty:
        return
    x0, y0, x1, y1 = (v * factor for v in shape.bounds)
    ix0, iy0 = max(0, math.floor(x0) - 1), max(0, math.floor(y0) - 1)
    ix1, iy1 = min(canvas.shape[1], math.ceil(x1) + 1), min(canvas.shape[0], math.ceil(y1) + 1)
    if ix1 <= ix0 or iy1 <= iy0:
        return
    big = np.zeros(((iy1 - iy0) * SUPER, (ix1 - ix0) * SUPER), np.uint8)
    for exterior, holes in _rings(shape):
        ext = np.round(((exterior * factor) - (ix0, iy0)) * SUPER * 16).astype(np.int32)
        cv2.fillPoly(big, [ext], 255, lineType=cv2.LINE_8, shift=4)
        for hole in holes:
            h = np.round(((hole * factor) - (ix0, iy0)) * SUPER * 16).astype(np.int32)
            cv2.fillPoly(big, [h], 0, lineType=cv2.LINE_8, shift=4)
    small = cv2.resize(big, (ix1 - ix0, iy1 - iy0), interpolation=cv2.INTER_AREA)
    view = canvas[iy0:iy1, ix0:ix1]
    np.maximum(view, small, out=view)


def render_masks(labels: SheetLabels, factor: float) -> np.ndarray:
    """Four soft masks at `factor` times the PNG size: room interior, wall, room boundary, opening."""
    import cv2  # noqa: PLC0415

    h, w = round(labels.height * factor), round(labels.width * factor)
    out = np.zeros((h, w, 4), np.uint8)
    interior, wall, boundary, opening = (np.zeros((h, w), np.uint8) for _ in range(4))
    for shape in (*labels.room_shapes, *labels.other_shapes):
        soft_fill(interior, shape, factor)
    for shape in labels.walls:
        soft_fill(wall, shape, factor)
    for shape in labels.openings:
        soft_fill(opening, shape, factor)
    thick = max(1, round(BOUNDARY_PX))
    for shape in (*labels.room_shapes, *labels.other_shapes):
        for exterior, holes in _rings(shape):
            for ring in (exterior, *holes):
                pts = np.round(ring * factor * 16).astype(np.int32)
                cv2.polylines(boundary, [pts], isClosed=True, color=255, thickness=thick, lineType=cv2.LINE_AA, shift=4)
    for a, b in labels.separators:
        pa = (round(a[0] * factor * 16), round(a[1] * factor * 16))
        pb = (round(b[0] * factor * 16), round(b[1] * factor * 16))
        cv2.line(boundary, pa, pb, 255, thickness=thick, lineType=cv2.LINE_AA, shift=4)
    out[..., 0], out[..., 1], out[..., 2], out[..., 3] = interior, wall, boundary, opening
    return out


# ----------------------------------------------------------------------------- scale benchmark


def scale_sheet(png: Path) -> dict[str, Any]:
    from bp.tools.ocr import to_rgb  # noqa: PLC0415
    from bp.tools.raster_scale import measure_scale  # noqa: PLC0415

    lines, _ = cached_lines(png)
    gray = to_rgb(png).mean(axis=2)
    got = measure_scale(gray, lines)
    row: dict[str, Any] = {"doc": png.name, "found": got is not None}
    if got is None:
        return row
    row |= {
        "ppm": got.ppm,
        "source": got.source,
        "agree": got.agree,
        "bar_ppm": got.bar.ppm if got.bar else None,
        "text_ppm": got.text.ppm if got.text else None,
        "ratio": got.ratio,
    }
    return row


def bench_scale(chosen: list[str], cubicasa: list[Path], jobs: int = 6) -> dict[str, Any]:
    """Error of the measured scale against the true scale on Swiss sheets, and None on CubiCasa plans."""
    pngs = [SWISS_DIR / f"{s}.png" for s in chosen]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        rows = list(pool.map(scale_sheet, pngs, chunksize=2))
        cubi = list(pool.map(scale_sheet, cubicasa, chunksize=2))
    errors, bar_err, text_err, true_err = [], [], [], []
    for stem, row in zip(chosen, rows, strict=True):
        if not row["found"]:
            continue
        ratio = row["ratio"] or 100
        truth = TRUE_PPM_100 * 100 / ratio
        try:
            fitted = sheet_labels(stem).ppm  # the scale that maps the DXF onto this PNG
        except ValueError:
            fitted = truth
        row["fitted_ppm"] = fitted
        errors.append(abs(row["ppm"] / fitted - 1))
        true_err.append(abs(row["ppm"] / truth - 1))
        if row["bar_ppm"]:
            bar_err.append(abs(row["bar_ppm"] / fitted - 1))
        if row["text_ppm"]:
            text_err.append(abs(row["text_ppm"] / fitted - 1))

    def dist(x: list[float]) -> dict[str, Any]:
        if not x:
            return {"n": 0}
        return {"n": len(x), "median": round(statistics.median(x), 6), "max": round(max(x), 6),
                "within_1pct": round(sum(e < 0.01 for e in x) / len(x), 4)}  # fmt: skip

    found = [r for r in rows if r["found"]]
    return {
        "sheets": len(rows),
        "found": len(found),
        "both_witnesses": sum(r.get("source") == "both" for r in found),
        "agree": sum(bool(r.get("agree")) for r in found),
        "error_vs_dxf_fit": dist(errors),
        "error_vs_59_0551": dist(true_err),
        "bar_error": dist(bar_err),
        "text_error": dist(text_err),
        "missing": [r["doc"] for r in rows if not r["found"]][:20],
        "disagree": [r for r in found if r.get("agree") is False][:10],
        "cubicasa": {
            "plans": len(cubi),
            "scale_found": sum(r["found"] for r in cubi),
            "found_on": [r for r in cubi if r["found"]][:10],
        },
    }


# ----------------------------------------------------------------------------- rooms benchmark


def rooms_sheet(stem: str, use_model: bool = True) -> dict[str, Any]:
    """Each labelled room with the baseline, model and final area, and the apartment and outdoor flags."""
    from bp.tools import raster_rooms  # noqa: PLC0415

    png = SWISS_DIR / f"{stem}.png"
    labels = sheet_labels(stem)
    lines, _ = cached_lines(png)
    start = time.perf_counter()
    plan = raster_rooms.read_plan(str(png), lines, use_model=use_model)
    seconds = time.perf_counter() - start
    got = {r.number: r for r in plan.rooms}
    rows = []
    for truth in labels.rooms:
        r = got.get(truth.number)
        rows.append({
            "number": truth.number, "true": truth.area_m2, "outdoor_true": truth.outdoor,
            "apartment_true": truth.apartment, "label_true": truth.label, "printed_true": truth.printed_m2,
            "found": r is not None,
            "label": r.label if r else None, "area": r.area_m2 if r else None,
            "source": r.area_source if r else None, "confidence": r.area_confidence if r else None,
            "model": r.model_area_m2 if r else None, "baseline": r.baseline_area_m2 if r else None,
            "printed": r.printed_area_m2 if r else None, "apartment": r.apartment if r else None,
            "outdoor": r.outdoor if r else None,
        })  # fmt: skip
    extra = [r.number for r in plan.rooms if r.number not in {t.number for t in labels.rooms}]
    return {"stem": stem, "seconds": round(seconds, 2), "rows": rows, "extra_numbers": extra,
            "scale_ppm": plan.scale.ppm if plan.scale else None, "true_ppm": labels.ppm,
            "apartments_true": sorted({t.apartment for t in labels.rooms if t.apartment}),
            "apartments": sorted({a.letter for a in plan.apartments})}  # fmt: skip


def _within(rows: list[dict[str, Any]], field: str, tol: float) -> float:
    ok = [r for r in rows if r[field] and abs(r[field] / r["true"] - 1) <= tol]
    return round(len(ok) / max(1, len(rows)), 4)


def summarise_rooms(sheets: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [r for s in sheets for r in s["rows"]]
    found = [r for r in rows if r["found"]]
    out: dict[str, Any] = {
        "sheets": len(sheets),
        "rooms": len(rows),
        "found_by_ocr": round(len(found) / max(1, len(rows)), 4),
    }
    for field in ("baseline", "model", "area"):
        out[field] = {"within_2pct": _within(rows, field, 0.02), "within_5pct": _within(rows, field, 0.05)}
    no_print = [r for r in rows if r["printed_true"] is None]
    out["no_printed_area"] = {
        "rooms": len(no_print),
        **{field: {"within_2pct": _within(no_print, field, 0.02), "within_5pct": _within(no_print, field, 0.05)}
           for field in ("baseline", "model", "area")},
    }  # fmt: skip
    by_conf: dict[str, Any] = {}
    for level in ("high", "medium", "low", "none"):
        part = [r for r in found if r["confidence"] == level]
        by_conf[level] = {"rooms": len(part), "within_2pct": _within(part, "area", 0.02),
                          "within_5pct": _within(part, "area", 0.05)}  # fmt: skip
    out["by_confidence"] = by_conf
    out["by_source"] = dict(Counter(r["source"] for r in found))
    totals = []
    for s in sheets:
        indoor = [r for r in s["rows"] if not r["outdoor_true"]]
        true = sum(r["true"] for r in indoor)
        got = sum(r["area"] or 0.0 for r in indoor)
        if true:
            totals.append(abs(got / true - 1))
    out["floor_total_error"] = {
        "median": round(statistics.median(totals), 4) if totals else None,
        "within_2pct": round(sum(e <= 0.02 for e in totals) / max(1, len(totals)), 4),
    }
    labelled = [r for r in found if r["label_true"]]
    out["label_exact"] = round(sum(r["label"] == r["label_true"] for r in labelled) / max(1, len(labelled)), 4)
    with_unit = [r for r in found if r["apartment_true"]]
    out["apartment_right"] = round(
        sum(r["apartment"] == r["apartment_true"] for r in with_unit) / max(1, len(with_unit)), 4
    )
    no_unit = [r for r in found if not r["apartment_true"]]
    out["no_apartment_right"] = round(sum(r["apartment"] is None for r in no_unit) / max(1, len(no_unit)), 4)
    out["outdoor_right"] = round(sum(r["outdoor"] == r["outdoor_true"] for r in found) / max(1, len(found)), 4)
    out["apartment_sets_exact"] = round(
        sum(s["apartments"] == s["apartments_true"] for s in sheets) / max(1, len(sheets)), 4
    )
    out["extra_numbers_per_sheet"] = round(sum(len(s["extra_numbers"]) for s in sheets) / max(1, len(sheets)), 3)
    out["seconds_per_sheet"] = round(statistics.mean(s["seconds"] for s in sheets), 2) if sheets else None
    return out


def bench_rooms(
    chosen: list[str], use_model: bool = True, jobs: int = 4
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        sheets = list(pool.map(rooms_sheet, chosen, [use_model] * len(chosen)))
    return summarise_rooms(sheets), sheets


# ----------------------------------------------------------------------------- all


def _model_info() -> dict[str, Any] | None:
    from bp.tools import raster_rooms  # noqa: PLC0415 - torch is slow to import

    if not raster_rooms.MODEL_PATH.exists():
        return None
    import torch  # noqa: PLC0415

    blob = torch.load(raster_rooms.MODEL_PATH, map_location="cpu", weights_only=False)
    return {"encoder": blob.get("encoder"), "step": blob.get("step"), "held_out": blob.get("metrics"),
            "bytes": raster_rooms.MODEL_PATH.stat().st_size}  # fmt: skip


def bench(jobs: int = 4) -> dict[str, Any]:
    """OCR, scale and room areas on every val sheet; scale on 60 CubiCasa plans. Writes OUT."""
    import random  # noqa: PLC0415

    val = stems("val")
    cubicasa = sorted(CUBICASA_DIR.glob("*.png"))
    random.Random(5).shuffle(cubicasa)  # noqa: S311 - a fixed sample, not security
    start = time.time()
    out: dict[str, Any] = {"partition": "val", "sheets": len(val), "model": _model_info()}
    out["ocr"] = bench_ocr(val, jobs=jobs)
    out["scale"] = bench_scale(val, cubicasa[:60], jobs=jobs)
    out["rooms_baseline"], _ = bench_rooms(val, use_model=False, jobs=jobs)
    out["rooms"], sheets = bench_rooms(val, use_model=True, jobs=jobs)
    out["worst_sheets"] = sorted(
        ({"stem": s["stem"], "rooms": len(s["rows"]),
          "off_5pct": sum(1 for r in s["rows"] if not (r["area"] and abs(r["area"] / r["true"] - 1) <= 0.05))}
         for s in sheets), key=lambda row: -row["off_5pct"],
    )[:10]  # fmt: skip
    out["minutes"] = round((time.time() - start) / 60, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


if __name__ == "__main__":
    print(json.dumps(bench(int(sys.argv[1]) if len(sys.argv) > 1 else 4), ensure_ascii=False)[:4000])
