"""Facts of one Swiss Dwellings floor, read by two independent paths.

Path 1 reads the DXF of the floor (rooms, numbers, labels, apartments, doors, windows). Path 2 reads the public
Swiss Dwellings source rows (`swiss-derived/source_rows.csv`): room polygons with their type, doors and windows.
The source has its own frame. A rigid motion, fitted on rooms with a unique area, moves it onto the DXF frame.
A third witness for areas is the PDF probe (`swiss-derived/pdf_features.json`), and the area printed on the sheet.

The generator uses a fact only when the paths agree. This module runs outside the sandbox: it reads labels.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from typing import TYPE_CHECKING

import ezdxf
import numpy as np
from shapely import affinity, wkt
from shapely.geometry import Point, Polygon
from shapely.geometry.base import BaseGeometry  # noqa: TC002 - pydantic needs it at runtime

from bp.contract import Frozen
from bp.paths import DATA, DATASET

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

SWISS_DIR = DATASET / "data" / "swiss_dwellings"
DERIVED = DATA / "external" / "swiss-derived"
CACHE = DERIVED / "hardcases_swiss_facts.json"

NUM = re.compile(r"^(U\d+\.)?\d+\.\d+$|^U\d+\.\d+$")
UNIT = re.compile(r"^(Whg\.|App\.|Appt\.|Apt\.|Wohnung|Appartement|Appartamento)\s*([A-Z]+)$")
PRINTED = re.compile(r"^(\d+\.\d+) m²$")
OUTDOOR_FILL = 0.89
TOUCH_M = 0.06  # an opening touches a room when it lies within this distance of the room outline
TOUCH_AREA_M2 = 0.01  # and the band of the room near the opening is at least this large
FIT_RESIDUAL_M = 0.01

OUTDOOR_SUBTYPES = frozenset(
    {"BALCONY", "LOGGIA", "TERRACE", "PATIO", "GARDEN", "WINTERGARTEN", "OUTDOOR_VOID", "ARCADE"}
)


class SwissRoom(Frozen):
    num: str
    label: str | None
    unit: str | None  # apartment letter from the tag inside the red outline
    area_dxf: float
    area_pdf: float | None
    area_src: float | None  # area of the source polygon that matches the room
    printed: float | None  # "12.34 m²" under the number, when the sheet prints it
    outdoor: bool  # grey 0.89 fill on the PDF (balcony, loggia, terrace)
    subtype: str | None  # source entity_subtype of the matching polygon
    windows_dxf: int
    windows_src: int | None
    doors_dxf: int  # distinct door openings that touch the room
    doors_dxf_raw: int  # with the stacked copies of shared doors
    doors_src: int | None
    cx: float
    cy: float


class SwissFloor(Frozen):
    stem: str
    lang: str  # de, fr or it, from the labels
    scale: int  # 100 or 200
    apartments: tuple[str, ...]
    rooms: tuple[SwissRoom, ...]
    source_aligned: bool
    has_printed: bool
    stray_labels: int = 0  # label texts that no room number claims: the floor is then not trusted
    error: str = ""


# ----------------------------------------------------------------------------- geometry helpers

_LANG_WORDS = {
    "de": {"Zimmer", "Bad", "Korridor", "Küche", "Balkon", "Schlafzimmer", "Treppenhaus", "Wohnen", "Reduit"},
    "fr": {"Pièce", "Bain", "Couloir", "Cuisine", "Balcon", "Chambre à coucher", "Séjour", "Réduit"},
    "it": {"Stanza", "Bagno", "Corridoio", "Cucina", "Balcone", "Camera da letto", "Soggiorno", "Ripostiglio"},
}


def floor_language(labels: Iterable[str | None]) -> str:
    votes = dict.fromkeys(_LANG_WORDS, 0)
    for label in labels:
        for lang, words in _LANG_WORDS.items():
            if label in words:
                votes[lang] += 1
    return max(sorted(votes), key=lambda lang: votes[lang])


def net_holes(polys: Sequence[Polygon]) -> list[BaseGeometry]:
    """A room with a hole is an outer ring plus a separate inner polygon. Subtract the inner ones."""
    out: list[BaseGeometry] = []
    for i, p in enumerate(polys):
        shape: BaseGeometry = p
        grown = p.buffer(1e-6)
        for j, q in enumerate(polys):
            if j != i and q.area < p.area and grown.contains(q):
                shape = shape.difference(q)
        out.append(shape)
    return out


def touches(opening: BaseGeometry, room: BaseGeometry) -> bool:
    return opening.distance(room) <= TOUCH_M and opening.buffer(TOUCH_M).intersection(room).area >= TOUCH_AREA_M2


def distinct(shapes: Iterable[BaseGeometry]) -> list[BaseGeometry]:
    """Drop exact copies (the generator stacks a shared opening once per unit)."""
    seen: set[tuple[float, ...]] = set()
    out: list[BaseGeometry] = []
    for s in shapes:
        key = tuple(round(v, 3) for v in s.bounds)
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out


def fit_rigid(src: np.ndarray, dst: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Rotation `r` and shift `t` with dst ~ src @ r.T + t (Kabsch, no reflection). It returns the residual too."""
    ms, md = src.mean(0), dst.mean(0)
    u, _, vt = np.linalg.svd((src - ms).T @ (dst - md))
    r = vt.T @ u.T
    if np.linalg.det(r) < 0:
        vt[-1] *= -1
        r = vt.T @ u.T
    t = md - ms @ r.T
    residual = float(np.abs(src @ r.T + t - dst).max())
    return r, t, residual


def move(shape: BaseGeometry, r: np.ndarray, t: np.ndarray) -> BaseGeometry:
    return affinity.affine_transform(shape, [r[0, 0], r[0, 1], r[1, 0], r[1, 1], t[0], t[1]])


# ----------------------------------------------------------------------------- the DXF path


class _Text(Frozen):
    text: str
    x: float
    y: float
    h: float


class _Dxf(Frozen):
    model_config = Frozen.model_config | {"arbitrary_types_allowed": True}
    texts: tuple[_Text, ...]
    rooms: tuple[BaseGeometry, ...]
    units: tuple[BaseGeometry, ...]
    doors: tuple[BaseGeometry, ...]
    windows: tuple[BaseGeometry, ...]


def _points(entity: object) -> list[tuple[float, float]]:
    return [(float(p[0]), float(p[1])) for p in entity.get_points()]  # ty: ignore[missing-attribute]


def read_dxf(path: Path) -> _Dxf:
    doc = ezdxf.readfile(path)
    texts: list[_Text] = []
    rooms: list[Polygon] = []
    units: list[BaseGeometry] = []
    doors: list[BaseGeometry] = []
    windows: list[BaseGeometry] = []
    for e in doc.modelspace():
        layer, kind = e.dxf.layer, e.dxftype()
        if kind == "TEXT" and layer == "ROOM_TEXT":
            ins = e.dxf.insert
            texts.append(_Text(text=str(e.dxf.text), x=float(ins.x), y=float(ins.y), h=float(e.dxf.height)))
            continue
        if kind != "LWPOLYLINE":
            continue
        pts = _points(e)
        closed = bool(e.closed)  # ty: ignore[missing-attribute]
        if layer == "ROOM_OUTLINE" and len(pts) >= 3:
            rooms.append(Polygon(pts).buffer(0))
        elif layer == "UNIT_OUTLINE" and len(pts) >= 3:
            units.append(Polygon(pts).buffer(0))
        elif layer == "DOOR" and len(pts) == 5:
            doors.append(Polygon(pts[:4]).buffer(0))
        elif layer == "WINDOW" and len(pts) == 4 and closed:
            windows.append(Polygon(pts).buffer(0))
    return _Dxf(
        texts=tuple(texts), rooms=tuple(net_holes(rooms)), units=tuple(units), doors=tuple(doors),
        windows=tuple(windows),
    )  # fmt: skip


def _label_above(num: _Text, others: Sequence[_Text]) -> _Text | None:
    """The generator centres the label exactly above the number."""
    best, gap = None, 1e9
    for o in others:
        dy, dx = o.y - num.y, abs(o.x - num.x)
        if 0 < dy < 2.5 * num.h and dx < 0.02 and dy + dx < gap:
            best, gap = o, dy + dx
    return best


def _printed_below(num: _Text, printed: Sequence[_Text]) -> float | None:
    for o in printed:
        dy, dx = num.y - o.y, abs(o.x - num.x)
        if 0 < dy < 2.5 * num.h and dx < 0.02:
            match = PRINTED.match(o.text)
            return float(match.group(1)) if match else None
    return None


class _SourceFloor(Frozen):
    model_config = Frozen.model_config | {"arbitrary_types_allowed": True}
    areas: tuple[tuple[str, BaseGeometry], ...]  # (subtype, polygon) in the DXF frame
    doors: tuple[BaseGeometry, ...]
    windows: tuple[BaseGeometry, ...]


def align_source(rows: Sequence[dict[str, str]], dxf_rooms: Sequence[BaseGeometry]) -> _SourceFloor | None:
    """Move the source polygons onto the DXF frame. None when no rigid motion fits."""
    areas = [(r["entity_subtype"], wkt.loads(r["geometry"])) for r in rows if r["entity_type"] == "area"]
    by_area: dict[float, list[BaseGeometry]] = defaultdict(list)
    for _, g in areas:
        by_area[round(g.area, 3)].append(g)
    dxf_by_area: dict[float, list[BaseGeometry]] = defaultdict(list)
    for g in dxf_rooms:
        dxf_by_area[round(g.area, 3)].append(g)
    src_pts, dst_pts = [], []
    for key, gs in by_area.items():
        if len(gs) == 1 and key > 1.0 and len(dxf_by_area.get(key, [])) == 1:
            src_pts.append(gs[0].centroid.coords[0])
            dst_pts.append(dxf_by_area[key][0].centroid.coords[0])
    if len(src_pts) < 3:
        return None
    r, t, residual = fit_rigid(np.array(src_pts), np.array(dst_pts))
    if residual > FIT_RESIDUAL_M:
        return None
    openings = [(r_["entity_subtype"], wkt.loads(r_["geometry"])) for r_ in rows if r_["entity_type"] == "opening"]
    return _SourceFloor(
        areas=tuple((s, move(g, r, t)) for s, g in areas),
        doors=tuple(move(g, r, t) for s, g in openings if s in {"DOOR", "ENTRANCE_DOOR"}),
        windows=tuple(move(g, r, t) for s, g in openings if s == "WINDOW"),
    )


def _match_source(room: BaseGeometry, src: _SourceFloor) -> tuple[str, BaseGeometry] | None:
    best, best_iou = None, 0.9
    for subtype, g in src.areas:
        if not g.intersects(room):
            continue
        inter = g.intersection(room).area
        iou = inter / max(1e-9, g.union(room).area)
        if iou > best_iou:
            best, best_iou = (subtype, g), iou
    return best


def _unit_letter(
    pt: Point, poly: BaseGeometry, units: Sequence[BaseGeometry], tags: Sequence[tuple[str, int]]
) -> str | None:
    idx = [i for i, u in enumerate(units) if u.contains(pt)]
    if not idx:
        overlap = [(u.intersection(poly).area, i) for i, u in enumerate(units)]
        overlap = [o for o in overlap if o[0] > 0.5 * poly.area]
        idx = [max(overlap)[1]] if overlap else []
    letters = [letter for letter, i in tags if i in idx]
    return letters[0] if letters else None


def floor_facts(stem: str, source_rows: Sequence[dict[str, str]], pdf: dict[str, object]) -> SwissFloor:
    dxf = read_dxf(SWISS_DIR / f"{stem}.dxf")
    nums = [t for t in dxf.texts if NUM.match(t.text)]
    printed = [t for t in dxf.texts if PRINTED.match(t.text)]
    unit_tags = [t for t in dxf.texts if UNIT.match(t.text)]
    others = [t for t in dxf.texts if not NUM.match(t.text) and not UNIT.match(t.text) and not PRINTED.match(t.text)]
    tags: list[tuple[str, int]] = []
    for t in unit_tags:
        match = UNIT.match(t.text)
        inside = [i for i, u in enumerate(dxf.units) if u.contains(Point(t.x, t.y))]
        if match and inside:
            tags.append((match.group(2), inside[0]))
    pdf_rooms = {str(r["num"]): r for r in pdf.get("rooms", [])}  # ty: ignore[not-iterable]
    src = align_source(source_rows, dxf.rooms)
    doors_distinct = distinct(dxf.doors)
    windows_distinct = distinct(dxf.windows)
    src_doors = distinct(src.doors) if src else []
    src_windows = distinct(src.windows) if src else []
    rooms: list[SwissRoom] = []
    claimed: set[int] = set()
    for n in nums:
        pt = Point(n.x, n.y)
        cands = [p for p in dxf.rooms if p.contains(pt)]
        if not cands:
            continue
        poly = min(cands, key=lambda p: p.area)
        label = _label_above(n, others)
        if label is not None:
            claimed.add(id(label))
        pr = pdf_rooms.get(n.text)
        match = _match_source(poly, src) if src else None
        src_poly = match[1] if match else None
        rooms.append(
            SwissRoom(
                num=n.text,
                label=label.text if label else None,
                unit=_unit_letter(pt, poly, dxf.units, tags),
                area_dxf=round(poly.area, 4),
                area_pdf=float(pr["area"]) if pr and pr.get("area") is not None else None,
                area_src=round(src_poly.area, 4) if src_poly is not None else None,
                printed=_printed_below(n, printed),
                outdoor=bool(pr and pr.get("fill") == OUTDOOR_FILL),
                subtype=match[0] if match else None,
                windows_dxf=sum(touches(w, poly) for w in windows_distinct),
                windows_src=sum(touches(w, src_poly) for w in src_windows) if src_poly is not None else None,
                doors_dxf=sum(touches(d, poly) for d in doors_distinct),
                doors_dxf_raw=sum(touches(d, poly) for d in dxf.doors),
                doors_src=sum(touches(d, src_poly) for d in src_doors) if src_poly is not None else None,
                cx=round(n.x, 3),
                cy=round(n.y, 3),
            )
        )
    scale = int(pdf.get("scale_text") or 0)  # ty: ignore[invalid-argument-type]
    return SwissFloor(
        stem=stem,
        lang=floor_language(r.label for r in rooms),
        scale=scale,
        apartments=tuple(sorted({letter for letter, _ in tags})),
        rooms=tuple(rooms),
        source_aligned=src is not None,
        has_printed=any(r.printed is not None for r in rooms),
        stray_labels=sum(id(o) not in claimed for o in others),
    )


def _one(args: tuple[str, list[dict[str, str]], dict[str, object]]) -> SwissFloor:
    stem, rows, pdf = args
    try:
        return floor_facts(stem, rows, pdf)
    except Exception as exc:  # one broken floor must not stop the build
        return SwissFloor(stem=stem, lang="", scale=0, apartments=(), rooms=(), source_aligned=False,
                          has_printed=False, error=repr(exc)[:300])  # fmt: skip


def build_facts(stems: Sequence[str] | None = None, jobs: int = 8) -> list[SwissFloor]:
    """Read every floor (or `stems`) and cache the facts. Sorted by stem, so the output is deterministic."""
    all_stems = sorted(p.stem for p in SWISS_DIR.glob("*.dxf"))
    chosen = sorted(stems) if stems is not None else all_stems
    by_floor_id = {s.rsplit("floor", 1)[1]: s for s in chosen}
    rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    csv.field_size_limit(1 << 30)
    with (DERIVED / "source_rows.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["floor_id"] in by_floor_id and row["entity_type"] in {"area", "opening"}:
                rows[by_floor_id[row["floor_id"]]].append(row)
    pdf_all: dict[str, dict[str, object]] = json.loads((DERIVED / "pdf_features.json").read_text())
    work = [(s, rows.get(s, []), pdf_all.get(s, {})) for s in chosen]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        floors = list(pool.map(_one, work, chunksize=4))
    return sorted(floors, key=lambda f: f.stem)


def save(floors: Sequence[SwissFloor], path: Path = CACHE) -> None:
    path.write_text(json.dumps([f.model_dump() for f in floors], ensure_ascii=False))


def load(path: Path = CACHE) -> list[SwissFloor]:
    return [SwissFloor.model_validate(f) for f in json.loads(path.read_text())]


if __name__ == "__main__":
    import sys

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    names = sorted(p.stem for p in SWISS_DIR.glob("*.dxf"))
    result = build_facts(names[:limit] if limit else None)
    save(result)
    print(f"{len(result)} floors, {sum(bool(f.error) for f in result)} errors -> {CACHE}")
