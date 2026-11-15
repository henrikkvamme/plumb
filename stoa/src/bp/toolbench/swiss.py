"""Benchmark of the swiss_plan tool (vector PDF) against two label sources.

It runs outside the sandbox, so it reads the DXF sibling of each sheet, the public source rows and the suite.
Only floors of the dev and val partitions are used; lock floors stay unseen.
1. DXF labels (layers ROOM_OUTLINE, ROOM_TEXT, DOOR, WINDOW, UNIT_OUTLINE): room recall and precision by room
   number, label agreement, the distribution of the area error (PDF polygon against DXF polygon, holes
   subtracted in both), and count agreement for doors (5-point polylines) and windows (closed 4-point
   polylines).
2. Public Swiss Dwellings v3 rows (data/external/swiss-derived/source_floor.json, built from geometries.csv):
   count agreement for doors, windows, toilets, washbasins, bathtubs, showers and residential units.
3. Printed area against polygon area: every room with a printed "m²" value. Where the two differ by more than
   2%, it records the room and which of the two the Stoa key of a room-area question follows.
4. The scale: title text against scale bar.
Writes experiments/tools/swiss.json. Run: uv run python -m bp.toolbench.swiss
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from typing import TYPE_CHECKING

import ezdxf
from ezdxf import entities as dxf_entities
from pydantic import Field
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon

from bp.contract import Frozen, MeasureKey
from bp.paths import DATA, DATASET, EXPERIMENTS
from bp.solvers.swiss import parse_question
from bp.suites import read_items
from bp.tools import swiss_plan as sp

if TYPE_CHECKING:
    from pathlib import Path

OUT = EXPERIMENTS / "tools" / "swiss.json"
SOURCE_FLOOR = DATA / "external" / "swiss-derived" / "source_floor.json"
DXF_LABEL_DX_M = 0.02  # the DXF label sits on the same x as the number
TOLERANCE = 0.02
SHARE_LIMITS = (0.001, 0.005, 0.01, 0.02, 0.05)
COUNT_NAMES = ("doors", "windows", "toilets", "washbasins", "bathtubs", "showers", "apartments")


class RoomPair(Frozen):
    number: str
    pdf_label: str | None
    dxf_label: str | None
    pdf_area: float | None
    dxf_area: float | None
    printed: float | None
    key_area: float | None  # the Stoa key of a room-area question on this room, when there is one


class FloorResult(Frozen):
    doc: str
    partition: str
    error: str = ""
    pdf_numbers: tuple[str, ...] = ()
    dxf_numbers: tuple[str, ...] = ()
    pairs: tuple[RoomPair, ...] = ()
    pdf_counts: dict[str, int] = Field(default_factory=dict)
    dxf_counts: dict[str, int] = Field(default_factory=dict)
    source_counts: dict[str, int] = Field(default_factory=dict)
    scale_ratio: int | None = None
    scale_agrees: bool | None = None


# ----------------------------------------------------------------------------- label readers


def _dxf_polygons(entities: list[dxf_entities.DXFGraphic]) -> list[Polygon]:
    out: list[Polygon] = []
    for e in entities:
        if isinstance(e, dxf_entities.LWPolyline):
            pts = [(float(p[0]), float(p[1])) for p in e.get_points()]
            if len(pts) >= 3:
                shape = Polygon(pts).buffer(0)
                if isinstance(shape, Polygon):
                    out.append(shape)
                else:
                    out += [g for g in getattr(shape, "geoms", []) if isinstance(g, Polygon)]
    return out


def read_dxf(path: Path) -> tuple[dict[str, tuple[str | None, float | None]], dict[str, int]]:
    """Rooms by number (label, net area in m²) and the door and window counts of a DXF sheet."""
    doc = ezdxf.readfile(str(path))
    layers: dict[str, list[dxf_entities.DXFGraphic]] = defaultdict(list)
    for e in doc.modelspace():
        layers[e.dxf.layer].append(e)
    texts = [
        (str(e.dxf.text).strip(), float(e.dxf.insert.x), float(e.dxf.insert.y), float(e.dxf.height))
        for e in layers["ROOM_TEXT"]
        if isinstance(e, dxf_entities.Text)
    ]
    numbers = [t for t in texts if sp.ROOM_NUMBER.match(t[0])]
    others = [t for t in texts if not sp.ROOM_NUMBER.match(t[0]) and not sp.UNIT_TAG.match(t[0])]
    raw = _dxf_polygons(layers["ROOM_OUTLINE"])
    nets = sp.net_holes(list(raw))
    rooms: dict[str, tuple[str | None, float | None]] = {}
    for text, x, y, height in numbers:
        above = [o for o in others if abs(o[1] - x) < DXF_LABEL_DX_M and 0 < o[2] - y < sp.LABEL_DY_SIZES * height]
        label = min(above, key=lambda o: o[2] - y)[0] if above else None
        point = ShapelyPoint(x, y)
        hits = [g for g in nets if g.contains(point)]
        rooms[text] = (label, round(min(hits, key=lambda g: g.area).area, 4) if hits else None)
    doors = sum(1 for e in layers["DOOR"] if isinstance(e, dxf_entities.LWPolyline) and len(e) == 5)
    windows = sum(1 for e in layers["WINDOW"] if isinstance(e, dxf_entities.LWPolyline) and len(e) == 4 and e.closed)
    tags = sum(1 for e in layers["ROOM_TEXT"] if isinstance(e, dxf_entities.Text) and sp.UNIT_TAG.match(e.dxf.text))
    return rooms, {"doors": doors, "windows": windows, "apartments": tags}


def source_counts(floor: dict[str, object]) -> dict[str, int]:
    feat = floor.get("feat") or {}
    opening = floor.get("open") or {}
    units = floor.get("units") or []
    if not isinstance(feat, dict) or not isinstance(opening, dict) or not isinstance(units, list):
        return {}
    return {
        "doors": int(opening.get("DOOR", 0)) + int(opening.get("ENTRANCE_DOOR", 0)),
        "windows": int(opening.get("WINDOW", 0)),
        "toilets": int(feat.get("TOILET", 0)),
        "washbasins": int(feat.get("SINK", 0)),
        "bathtubs": int(feat.get("BATHTUB", 0)),
        "showers": int(feat.get("SHOWER", 0)),
        "apartments": sum(1 for u in units if isinstance(u, list) and len(u) > 1 and u[1] == "RESIDENTIAL"),
    }


def pdf_counts(plan: sp.SwissPlan) -> dict[str, int]:
    def fixtures(kind: sp.FixtureKind) -> int:
        value = sp.fixture_count(plan, kind).value
        return int(value) if value is not None else 0

    return {
        "doors": plan.doors.count,
        "doors_distinct": plan.doors.distinct,
        "windows": fixtures("window"),
        "toilets": fixtures("toilet"),
        "washbasins": fixtures("washbasin"),
        "bathtubs": fixtures("bathtub"),
        "showers": fixtures("shower"),
        "apartments": len(plan.apartments),
    }


# ----------------------------------------------------------------------------- one floor


def bench_floor(job: tuple[str, str, dict[str, float], dict[str, object]]) -> FloorResult:
    doc, partition, room_keys, source = job
    pdf = DATASET / doc
    try:
        plan = sp.read_plan(pdf)
        dxf_rooms, dxf_counts = read_dxf(pdf.with_suffix(".dxf"))
    except Exception as exc:  # one broken floor must not stop the benchmark
        return FloorResult(doc=doc, partition=partition, error=f"{type(exc).__name__}: {exc}"[:300])
    pairs = []
    for room in plan.rooms:
        label, area = dxf_rooms.get(room.number, (None, None))
        pairs.append(
            RoomPair(
                number=room.number,
                pdf_label=room.label,
                dxf_label=label,
                pdf_area=room.area_m2,
                dxf_area=area,
                printed=room.printed_area_m2,
                key_area=room_keys.get(room.number),
            )
        )
    return FloorResult(
        doc=doc,
        partition=partition,
        pdf_numbers=tuple(r.number for r in plan.rooms),
        dxf_numbers=tuple(dxf_rooms),
        pairs=tuple(pairs),
        pdf_counts=pdf_counts(plan),
        dxf_counts=dxf_counts,
        source_counts=source_counts(source),
        scale_ratio=plan.scale.ratio if plan.scale else None,
        scale_agrees=plan.scale.agrees if plan.scale else None,
    )


# ----------------------------------------------------------------------------- aggregate


def _quantiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)

    def q(p: float) -> float:
        return round(ordered[min(len(ordered) - 1, int(p * len(ordered)))], 6)

    return {"median": q(0.5), "p90": q(0.9), "p95": q(0.95), "p99": q(0.99), "max": round(ordered[-1], 6)}


def _rooms(results: list[FloorResult]) -> dict[str, object]:
    pdf_n = sum(len(r.pdf_numbers) for r in results)
    dxf_n = sum(len(r.dxf_numbers) for r in results)
    matched = sum(len(set(r.pdf_numbers) & set(r.dxf_numbers)) for r in results)
    pairs = [p for r in results for p in r.pairs if p.number in set(r.dxf_numbers)]
    labelled = [p for p in pairs if p.dxf_label is not None or p.pdf_label is not None]
    same_label = sum(1 for p in labelled if p.dxf_label == p.pdf_label)
    errors = [
        abs(p.pdf_area - p.dxf_area) / p.dxf_area
        for p in pairs
        if p.pdf_area is not None and p.dxf_area is not None and p.dxf_area > 0
    ]
    worst = sorted(
        (
            (abs(p.pdf_area - p.dxf_area) / p.dxf_area, r.doc, p.number, p.pdf_area, p.dxf_area)
            for r in results
            for p in r.pairs
            if p.pdf_area is not None and p.dxf_area is not None and p.dxf_area > 0
        ),
        reverse=True,
    )[:10]
    return {
        "pdf_rooms": pdf_n,
        "dxf_rooms": dxf_n,
        "matched_by_number": matched,
        "recall": round(matched / dxf_n, 5) if dxf_n else None,
        "precision": round(matched / pdf_n, 5) if pdf_n else None,
        "label_agreement": round(same_label / len(labelled), 5) if labelled else None,
        "label_pairs": len(labelled),
        "rooms_with_both_areas": len(errors),
        "rooms_without_pdf_area": sum(1 for p in pairs if p.pdf_area is None),
        "area_rel_error": _quantiles(errors),
        "area_share_within": {f"{x:g}": round(sum(1 for e in errors if e <= x) / len(errors), 5) for x in SHARE_LIMITS}
        if errors
        else {},
        "dxf_numbers_missing_in_pdf": [
            {"doc": r.doc.rsplit("/", 1)[-1], "room": n}
            for r in results
            for n in r.dxf_numbers
            if n not in r.pdf_numbers
        ][:30],
        "area_worst": [
            {"doc": d.rsplit("/", 1)[-1], "room": n, "pdf": a, "dxf": b, "rel": round(e, 4)} for e, d, n, a, b in worst
        ],
    }


def _counts(results: list[FloorResult], label: str) -> dict[str, object]:
    out: dict[str, object] = {}
    for name in (*COUNT_NAMES, "doors_distinct"):
        ref_name = "doors" if name == "doors_distinct" else name
        pairs = [
            (r.pdf_counts[name], (r.dxf_counts if label == "dxf" else r.source_counts)[ref_name])
            for r in results
            if name in r.pdf_counts and ref_name in (r.dxf_counts if label == "dxf" else r.source_counts)
        ]
        if not pairs:
            continue
        diffs = Counter(a - b for a, b in pairs)
        out[name] = {
            "floors": len(pairs),
            "exact": round(sum(1 for a, b in pairs if a == b) / len(pairs), 5),
            "pdf_total": sum(a for a, _ in pairs),
            "label_total": sum(b for _, b in pairs),
            "difference_histogram": {str(k): v for k, v in sorted(diffs.items())},
        }
    return out


def _printed(results: list[FloorResult]) -> dict[str, object]:
    rooms = [(r.doc, p) for r in results for p in r.pairs if p.printed is not None]
    with_poly = [(d, p) for d, p in rooms if p.pdf_area is not None]
    mismatch = [
        (d, p) for d, p in with_poly if abs((p.printed or 0.0) - (p.pdf_area or 0.0)) > TOLERANCE * (p.printed or 1.0)
    ]
    keyed = [(d, p) for d, p in with_poly if p.key_area is not None]

    def close(a: float | None, b: float | None, tol: float) -> bool:
        return a is not None and b is not None and abs(a - b) <= tol * max(abs(b), 1e-9)

    key_print = sum(1 for _, p in keyed if close(p.printed, p.key_area, 0.0005))
    key_poly = sum(1 for _, p in keyed if close(p.pdf_area, p.key_area, 0.0005))
    return {
        "floors_with_printed_areas": len({d for d, _ in rooms}),
        "rooms_with_printed_area": len(rooms),
        "rooms_with_printed_and_polygon": len(with_poly),
        "mismatch_over_2pct": len(mismatch),
        "mismatches": [
            {
                "doc": d.rsplit("/", 1)[-1],
                "room": p.number,
                "printed": p.printed,
                "polygon": p.pdf_area,
                "dxf": p.dxf_area,
                "key": p.key_area,
            }
            for d, p in mismatch[:50]
        ],
        "room_area_keys_on_printed_rooms": len(keyed),
        "key_equals_printed_0.05pct": key_print,
        "key_equals_polygon_0.05pct": key_poly,
        "printed_rel_error_vs_polygon": _quantiles(
            [abs((p.printed or 0.0) - (p.pdf_area or 0.0)) / (p.pdf_area or 1.0) for _, p in with_poly if p.pdf_area]
        ),
    }


def _median_error(results: list[FloorResult]) -> float:
    errors = [
        abs(p.pdf_area - p.dxf_area) / p.dxf_area
        for r in results
        for p in r.pairs
        if p.pdf_area is not None and p.dxf_area
    ]
    return statistics.median(errors) if errors else 0.0


def _jobs(partitions: tuple[str, ...]) -> list[tuple[str, str, dict[str, float], dict[str, object]]]:
    items = [i for i in read_items("stoa") if i.source == "swiss_dwellings" and i.partition in partitions]
    keys: dict[str, dict[str, float]] = defaultdict(dict)
    part: dict[str, str] = {}
    for item in items:
        part[item.doc] = item.partition
        parsed = parse_question(item.question)
        if (
            not isinstance(parsed, str)
            and parsed.intent == "area_room"
            and parsed.room
            and isinstance(item.key, MeasureKey)
        ):
            keys[item.doc][parsed.room] = item.key.value
    source = json.loads(SOURCE_FLOOR.read_text()) if SOURCE_FLOOR.exists() else {}
    jobs = []
    for doc in sorted(part):
        floor_id = doc.rsplit("floor", 1)[-1].split(".")[0]  # bench only: the file name is a key into the labels
        jobs.append((doc, part[doc], keys.get(doc, {}), source.get(floor_id, {})))
    return jobs


def bench(partitions: tuple[str, ...] = ("dev", "val"), workers: int = 8) -> dict[str, object]:
    jobs = _jobs(partitions)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(bench_floor, jobs, chunksize=8))
    good = [r for r in results if not r.error]
    scales = Counter((r.scale_ratio, r.scale_agrees) for r in good)
    report: dict[str, object] = {
        "partitions": list(partitions),
        "floors": len(results),
        "errors": [{"doc": r.doc, "error": r.error} for r in results if r.error],
        "rooms_vs_dxf": _rooms(good),
        "counts_vs_dxf": _counts(good, "dxf"),
        "counts_vs_source": _counts(good, "source"),
        "printed_vs_polygon": _printed(good),
        "scale": {f"1:{k[0]} bar_agrees={k[1]}": v for k, v in scales.most_common()},
        "by_scale_area_median_error": {
            str(ratio): _median_error([r for r in good if r.scale_ratio == ratio])
            for ratio in sorted({r.scale_ratio for r in good if r.scale_ratio})
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False))
    return report


def main() -> None:
    partitions = tuple(sys.argv[1:]) or ("dev", "val")
    if "lock" in partitions:
        msg = "the lock partition stays unseen"
        raise SystemExit(msg)
    report = bench(partitions)
    rooms = report["rooms_vs_dxf"]
    printed = report["printed_vs_polygon"]
    print(json.dumps({"floors": report["floors"], "rooms": rooms, "printed": printed}, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
