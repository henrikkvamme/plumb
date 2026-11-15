"""Benchmark of the contractor quantities (`bp.tools.quantities`) on Swiss floors: PDF, DXF and source geometry.

Three readings of one floor:
1. the vector PDF (what the agent reads),
2. the DXF twin (a second rendering of the same floor, with its own layers),
3. the Swiss Dwellings v3 source rows (`geometries.csv`): the room areas, the wall separators and the door and
   window openings that both drawings were made from. Rows that two units share are listed once per unit; the
   bench keeps each geometry once.
The truth of a room is the same rule applied to the source geometry; this tests that the drawing gives the
source geometry back, at the sheet scale, with the openings in the right rooms. Rooms are matched by area and
perimeter (the source has no room numbers). The wall centre line is compared to the centre line of the union of
the source wall rectangles, and the per-element sum of the source walls is reported next to it.

Only floors of the dev and val partitions are read; lock floors stay unseen. Writes
experiments/tools/quantities.json. Run: uv run python -m bp.toolbench.quantities [dev|val ...] [--limit N]
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from typing import TYPE_CHECKING

from pydantic import Field
from shapely import wkt
from shapely.geometry import Polygon

from bp.contract import Frozen
from bp.paths import DATA, DATASET, EXPERIMENTS
from bp.suites import read_items
from bp.tools import dxf_plan
from bp.tools import quantities as q
from bp.tools import swiss_plan as sp
from bp.tools.pdf_text import read_page

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

OUT = EXPERIMENTS / "tools" / "quantities.json"
GEOMETRIES = DATA / "external" / "swiss-dwellings-v3" / "swiss-dwellings-v3.0.0" / "geometries.csv"
SOURCE = DATA / "external" / "swiss-derived" / "quantities_source.json"
TOLERANCE = 0.02  # the default tolerance of a measure key
NOT_ROOMS = frozenset({"SHAFT", "VOID", "LIGHTWELL"})  # unnumbered on the sheets
MATCH_AREA = 0.002  # a PDF room and a source area match when the areas differ by at most 0.2%
SHARES = (0.005, 0.01, 0.02, 0.05)

csv.field_size_limit(1 << 30)


# ----------------------------------------------------------------------------- source rows


def extract(floor_ids: set[str]) -> dict[str, dict[str, list[list[str]]]]:
    """One pass over geometries.csv: the areas, walls and openings of the wanted floors, each geometry once."""
    out: dict[str, dict[str, list[list[str]]]] = {}
    seen: set[tuple[str, str, str]] = set()
    with GEOMETRIES.open(newline="") as handle:
        for row in csv.DictReader(handle):
            floor = row["floor_id"]
            if floor not in floor_ids:
                continue
            kind, sub, geometry = row["entity_type"], row["entity_subtype"], row["geometry"]
            if kind not in {"area", "separator", "opening"}:
                continue
            key = (floor, sub, geometry)
            if key in seen:
                continue
            seen.add(key)
            out.setdefault(floor, {}).setdefault(kind, []).append([sub, geometry])
    return out


def _rings(geom: BaseGeometry) -> tuple[tuple[tuple[float, float], ...], ...]:
    parts = [geom] if isinstance(geom, Polygon) else [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]
    if not parts:
        return ()
    main = max(parts, key=lambda p: p.area)
    return (
        tuple((x, y) for x, y, *_ in main.exterior.coords),
        *(tuple((x, y) for x, y, *_ in r.coords) for r in main.interiors),
    )


def source_floor(rows: dict[str, list[list[str]]]) -> tuple[q.FloorIn, list[str], float]:
    """The source floor in metres, the subtype of each room, and the per-element sum of the wall lengths."""
    areas = [(sub, wkt.loads(g)) for sub, g in rows.get("area", [])]
    shapes = [g if g.is_valid else g.buffer(0) for _, g in areas]
    nets = sp.net_holes(shapes)
    rooms, subtypes = [], []
    for i, ((sub, _), net) in enumerate(zip(areas, nets, strict=True)):
        if sub in NOT_ROOMS or net.is_empty:
            continue
        rooms.append(q.RoomIn(entity_id=f"src:{i}", number=None, label=None, apartment=None, outdoor=False,
                              shared=False, area_m2=round(net.area, 4), rings=_rings(net)))  # fmt: skip
        subtypes.append(sub)
    walls = [wkt.loads(g) for sub, g in rows.get("separator", []) if sub == "WALL"]
    element_sum = sum(q.sides(w.exterior.coords)[0] for w in walls if isinstance(w, Polygon))
    doors, windows = [], []
    for n, (sub, g) in enumerate(rows.get("opening", [])):
        shape = wkt.loads(g)
        if not isinstance(shape, Polygon):
            continue
        ring = tuple((x, y) for x, y, *_ in shape.exterior.coords)
        if sub in {"DOOR", "ENTRANCE_DOOR"}:
            doors.append(q.OpeningIn(entity_id=f"src-door:{n}", kind="door", ring=ring))
        elif sub == "WINDOW":
            windows.append(q.OpeningIn(entity_id=f"src-window:{n}", kind="window", ring=ring))
    floor = q.FloorIn(unit_m=1.0, rooms=tuple(rooms), doors=tuple(doors), windows=tuple(windows),
                      walls=tuple(_rings(w) for w in walls if isinstance(w, Polygon)))  # fmt: skip
    return floor, subtypes, element_sum


# ----------------------------------------------------------------------------- one floor


class RoomPair(Frozen):
    number: str
    kind: str | None
    subtype: str | None  # the source subtype of the matched area
    apartment: str | None
    outdoor: bool
    pdf: dict[str, float] = Field(default_factory=dict)
    dxf: dict[str, float] = Field(default_factory=dict)
    src: dict[str, float] = Field(default_factory=dict)


class FloorResult(Frozen):
    doc: str
    partition: str
    error: str = ""
    rooms: tuple[RoomPair, ...] = ()
    unmatched: int = 0
    walls: dict[str, float] = Field(default_factory=dict)
    door_widths: dict[str, list[float]] = Field(default_factory=dict)
    seconds_pdf: float = 0.0


def _values(r: q.RoomQ) -> dict[str, float]:
    return {
        "perimeter_m": r.perimeter_m,
        "baseboard_m": r.baseboard_m,
        "baseboard_walls_only_m": r.baseboard_walls_only_m,
        "open_edge_m": r.open_edge_m,
        "doors": len(r.door_ids),
        "windows": len(r.window_ids),
        "door_width_sum_m": round(sum(r.door_widths_m), 3),
        "area_m2": r.area_m2 or 0.0,
    }


def _match(pdf: list[q.RoomQ], src: list[q.RoomQ]) -> dict[str, int]:
    """Each PDF room number to the index of the source room with the same area and the nearest perimeter."""
    out: dict[str, int] = {}
    free = set(range(len(src)))
    for r in sorted(pdf, key=lambda r: -(r.area_m2 or 0.0)):
        if not r.area_m2 or r.number is None:
            continue
        area = r.area_m2
        cands = [i for i in free if abs((src[i].area_m2 or 0.0) - area) <= MATCH_AREA * area + 0.005]
        if not cands:
            continue
        best = min(cands, key=lambda i: abs(src[i].perimeter_m - r.perimeter_m))
        out[r.number] = best
        free.discard(best)
    return out


def bench_floor(job: tuple[str, str, dict[str, list[list[str]]]]) -> FloorResult:
    import time  # noqa: PLC0415

    doc, partition, rows = job
    pdf_path = DATASET / doc
    try:
        start = time.perf_counter()
        page = read_page(pdf_path)
        plan = sp.compile_plan(page)
        pdf_in = q.swiss_floor(page, plan)
        if pdf_in is None:
            return FloorResult(doc=doc, partition=partition, error="no scale")
        pdf_q = q.measure(pdf_in)
        seconds = time.perf_counter() - start
        dxf_file = pdf_path.with_suffix(".dxf")
        dxf_in = q.dxf_floor(dxf_file, dxf_plan.read_dxf(dxf_file))
        dxf_q = q.measure(dxf_in) if dxf_in else None
        src_in, subtypes, element_sum = source_floor(rows)
        src_q = q.measure(src_in)
    except Exception as exc:  # one broken floor must not stop the benchmark
        return FloorResult(doc=doc, partition=partition, error=f"{type(exc).__name__}: {exc}"[:300])
    dxf_rooms = {r.number: r for r in dxf_q.rooms} if dxf_q else {}
    match = _match(list(pdf_q.rooms), list(src_q.rooms))
    pairs = []
    for r in pdf_q.rooms:
        if r.number is None:
            continue
        s = match.get(r.number)
        d = dxf_rooms.get(r.number)
        pairs.append(RoomPair(number=r.number, kind=r.kind, subtype=subtypes[s] if s is not None else None,
                              apartment=r.apartment, outdoor=r.outdoor, pdf=_values(r),
                              dxf=_values(d) if d else {}, src=_values(src_q.rooms[s]) if s is not None else {}))  # fmt: skip
    walls: dict[str, float] = {}
    for name, got in (("pdf", pdf_q), ("dxf", dxf_q), ("src", src_q)):
        if got is not None and got.walls is not None:
            walls |= {f"{name}_centerline_m": got.walls.centerline_m, f"{name}_exterior_m": got.walls.exterior_m}
    walls["src_element_sum_m"] = round(element_sum, 2)
    widths = {
        "pdf": sorted(o.width_m for o in pdf_q.doors),
        "dxf": sorted(o.width_m for o in dxf_q.doors) if dxf_q else [],
        "src": sorted(o.width_m for o in src_q.doors),
    }
    return FloorResult(doc=doc, partition=partition, rooms=tuple(pairs), unmatched=len(pdf_q.rooms) - len(match),
                       walls=walls, door_widths=widths, seconds_pdf=round(seconds, 3))  # fmt: skip


# ----------------------------------------------------------------------------- aggregate


def quantiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)

    def at(p: float) -> float:
        return round(ordered[min(len(ordered) - 1, int(p * len(ordered)))], 5)

    return {"n": len(ordered), "median": at(0.5), "p90": at(0.9), "p95": at(0.95), "p99": at(0.99),
            "max": round(ordered[-1], 5)}  # fmt: skip


def _score_length(pairs: list[tuple[float | None, float]], tolerance: float = TOLERANCE) -> dict[str, object]:
    """Right within the tolerance, wrong outside it, abstained when the tool has no value."""
    right = sum(1 for got, want in pairs if got is not None and abs(got - want) <= tolerance * max(abs(want), 1e-9))
    abstained = sum(1 for got, _ in pairs if got is None)
    errors = [abs(got - want) / want for got, want in pairs if got is not None and want > 0]
    return {"items": len(pairs), "right": right, "wrong": len(pairs) - right - abstained, "abstained": abstained,
            "rel_error": quantiles(errors),
            "share_within": {f"{x:g}": round(sum(1 for e in errors if e <= x) / len(errors), 4) for x in SHARES}
            if errors else {}}  # fmt: skip


def _score_count(pairs: list[tuple[float | None, float]]) -> dict[str, object]:
    right = sum(1 for got, want in pairs if got is not None and got == want)
    abstained = sum(1 for got, _ in pairs if got is None)
    return {"items": len(pairs), "right": right, "wrong": len(pairs) - right - abstained, "abstained": abstained}


ROOM_LENGTHS = ("perimeter_m", "baseboard_m", "baseboard_walls_only_m")
ROOM_COUNTS = ("doors", "windows")


def _rooms(results: list[FloorResult], against: str) -> dict[str, object]:
    out: dict[str, object] = {}
    rooms = [p for r in results for p in r.rooms]
    for name in ROOM_LENGTHS:
        pairs = [(p.pdf.get(name), getattr(p, against)[name]) for p in rooms if getattr(p, against)]
        out[name] = _score_length([(g, w) for g, w in pairs if w > 0])
    for name in ROOM_COUNTS:
        pairs = [(p.pdf.get(name), getattr(p, against)[name]) for p in rooms if getattr(p, against)]
        out[name] = _score_count(pairs)
    out["rooms_compared"] = sum(1 for p in rooms if getattr(p, against))
    out["rooms_without_partner"] = sum(1 for p in rooms if not getattr(p, against))
    return out


def _groups(results: list[FloorResult], against: str) -> dict[str, object]:
    """Per apartment (indoor rooms) and per room kind on a floor: sums of baseboard, doors and windows."""
    sums: dict[str, list[tuple[float | None, float]]] = defaultdict(list)
    for r in results:
        groups: dict[tuple[str, str], list[RoomPair]] = defaultdict(list)
        for p in r.rooms:
            if p.apartment and not p.outdoor:
                groups[("apartment", p.apartment)].append(p)
            if p.kind:
                groups[("kind", p.kind)].append(p)
        for (what, _), members in groups.items():
            if any(not getattr(m, against) for m in members):
                for name in ("baseboard_m", "windows", "area_m2"):
                    sums[f"{what}_{name}"].append((None, sum(m.pdf.get(name, 0.0) for m in members)))
                continue
            for name in ("baseboard_m", "windows", "area_m2"):
                got = sum(m.pdf.get(name, 0.0) for m in members)
                want = sum(getattr(m, against)[name] for m in members)
                sums[f"{what}_{name}"].append((got, want))
    return {k: (_score_count(v) if k.endswith("windows") else _score_length(v)) for k, v in sums.items()}


def _kinds_vs_subtypes(results: list[FloorResult]) -> dict[str, object]:
    """How often the room kind from the label is the source subtype (lower case)."""
    pairs = [(p.kind, (p.subtype or "").lower()) for r in results for p in r.rooms if p.kind and p.subtype]
    alias = {"room": "room", "living_room": "living_room", "kitchen_dining": "kitchen"}
    same = sum(1 for k, s in pairs if alias.get(k, k) == s)
    return {"rooms": len(pairs), "kind_is_subtype": same}


def _walls(results: list[FloorResult]) -> dict[str, object]:
    def pairs(a: str, b: str) -> list[tuple[float | None, float]]:
        return [(r.walls.get(a), r.walls[b]) for r in results if r.walls.get(b)]

    ratio = [r.walls["src_element_sum_m"] / r.walls["src_centerline_m"] for r in results
             if r.walls.get("src_centerline_m")]  # fmt: skip
    return {
        "pdf_vs_src_centerline": _score_length(pairs("pdf_centerline_m", "src_centerline_m")),
        "dxf_vs_src_centerline": _score_length(pairs("dxf_centerline_m", "src_centerline_m")),
        "pdf_vs_dxf_centerline": _score_length(pairs("pdf_centerline_m", "dxf_centerline_m")),
        "pdf_vs_src_exterior": _score_length(pairs("pdf_exterior_m", "src_exterior_m")),
        "element_sum_over_centerline": quantiles(ratio),
    }


def _door_widths(results: list[FloorResult]) -> dict[str, object]:
    errors: list[float] = []
    same_count = 0
    for r in results:
        pdf, src = r.door_widths.get("pdf", []), r.door_widths.get("src", [])
        if len(pdf) == len(src):
            same_count += 1
            errors += [abs(a - b) for a, b in zip(pdf, src, strict=True)]
    return {"floors": len(results), "floors_same_door_count": same_count,
            "abs_error_m_sorted_pairs": quantiles(errors),
            "within_1cm": round(sum(1 for e in errors if e <= 0.01) / len(errors), 4) if errors else None}  # fmt: skip


def _jobs(partitions: tuple[str, ...], limit: int | None) -> list[tuple[str, str]]:
    items = [i for i in read_items("stoa") if i.source == "swiss_dwellings" and i.partition in partitions]
    part = {i.doc: i.partition for i in items}
    docs = sorted(part)
    if limit:
        step = max(1, len(docs) // limit)
        docs = docs[::step][:limit]
    return [(d, part[d]) for d in docs]


def floor_id(doc: str) -> str:
    return doc.rsplit("floor", 1)[-1].split(".", maxsplit=1)[0]  # bench only: the file name is a key into the source rows


def bench(partitions: tuple[str, ...], limit: int | None = None, workers: int = 2) -> dict[str, object]:
    docs = _jobs(partitions, limit)
    wanted = {floor_id(d) for d, _ in _jobs(("dev", "val"), None)}  # one pass over the CSV for every bench floor
    cached = json.loads(SOURCE.read_text()) if SOURCE.exists() else {}
    missing = wanted - set(cached)
    if missing:
        cached |= extract(missing)
        SOURCE.write_text(json.dumps(cached))
    jobs = [(d, p, cached.get(floor_id(d), {})) for d, p in docs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(bench_floor, jobs, chunksize=4))
    good = [r for r in results if not r.error]
    report: dict[str, object] = {"partitions": list(partitions), "floors": len(results),
                                 "errors": [{"doc": r.doc, "error": r.error} for r in results if r.error]}  # fmt: skip
    for part in partitions:
        mine = [r for r in good if r.partition == part]
        report[part] = {
            "floors": len(mine),
            "rooms_vs_source": _rooms(mine, "src"),
            "rooms_vs_dxf": _rooms(mine, "dxf"),
            "groups_vs_source": _groups(mine, "src"),
            "groups_vs_dxf": _groups(mine, "dxf"),
            "walls": _walls(mine),
            "door_widths_vs_source": _door_widths(mine),
            "kinds": _kinds_vs_subtypes(mine),
            "unmatched_rooms": sum(r.unmatched for r in mine),
            "seconds_pdf": quantiles([r.seconds_pdf for r in mine]),
        }
    worst = sorted(
        ((abs(p.pdf["baseboard_m"] - p.src["baseboard_m"]) / max(p.src["baseboard_m"], 1e-9), r.doc, p.number)
         for r in good for p in r.rooms if p.src and p.src.get("baseboard_m")),
        reverse=True,
    )[:25]  # fmt: skip
    report["baseboard_worst"] = [{"doc": d.rsplit("/", 1)[-1], "room": n, "rel": round(e, 4)} for e, d, n in worst]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False))
    rows = EXPERIMENTS / "tools" / "quantities_rows.jsonl"
    rows.write_text("".join(r.model_dump_json() + "\n" for r in results))
    return report


def main() -> None:
    args = sys.argv[1:]
    limit = None
    if "--limit" in args:
        i = args.index("--limit")
        limit = int(args[i + 1])
        args = args[:i] + args[i + 2 :]
    partitions = tuple(args) or ("dev", "val")
    if "lock" in partitions:
        msg = "the lock partition stays unseen"
        raise SystemExit(msg)
    report = bench(partitions, limit)
    print(json.dumps({k: v for k, v in report.items() if k != "baseboard_worst"}, ensure_ascii=False)[:6000])


if __name__ == "__main__":
    main()
