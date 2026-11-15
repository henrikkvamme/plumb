"""Room areas from the wall lines against the printed areas, on the dev USACE sheets. Source of `bp.rates.ROOM_*`.

Each dev sheet of the `room_area` family has a render with every "NNN SF" text removed. For each room of
`bp.facts` with an outline, the printed area is the one "NNN SF" line of the source PDF inside that outline.
Held-out (lock) sheets are skipped.

    cd stoa && uv run python analysis/sheets/room_margin.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pymupdf
from shapely.geometry import Point, Polygon

STOA = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STOA / "jobs" / "sheets"))

import usace  # noqa: E402

from bp import facts  # noqa: E402
from bp.rates import SMALL_ROOM_M2, STRONG_LINES  # noqa: E402
from bp.tools import ocr, sheet_plan, sheet_text  # noqa: E402
from bp.tools.sheet_text import SQFT_M2  # noqa: E402

OUT = STOA / "analysis" / "sheets" / "out"


def rows() -> list[dict]:
    pdfs = {}
    for pdf in sorted((STOA / "data" / "external" / "sheets" / "usace").glob("*.pdf")):
        kind, _, rest = pdf.stem.partition("__")
        pdfs[(kind, hashlib.sha256(rest.encode()).hexdigest()[:6])] = pdf
    out: list[dict] = []
    for render in sorted((STOA / "data" / "sheets-test").glob("usace_*_noarea.png")):
        _, kind, short, page_s, _ = render.stem.split("_")
        number = int(page_s[1:])
        if kind in usace.LOCK and not (kind == "ortc" and number < usace.ORTC_LOCK_FROM):
            continue
        page = pymupdf.open(pdfs[(kind, short)])[number - 1]
        page.remove_rotation()
        rgb = ocr.to_rgb(render)
        lines = sheet_text.cached_lines(rgb)
        if lines is None:
            print("no OCR cache:", render.name)
            continue
        plan = sheet_plan.plan_for(rgb, lines)
        if plan.scale is None:
            print("no scale:", render.name)
            continue
        k = rgb.shape[1] / page.rect.width
        printed = usace.room_areas(usace.text_lines(page))
        measured = plan.scale.measured
        for entity in facts.sheet_facts(plan).entities:
            if entity.kind != "room" or entity.geometry != "polygon":
                continue
            outline = Polygon(entity.points)
            hits = [v for _, v, ln in printed if outline.contains(Point((ln[0] + ln[2]) / 2 * k, (ln[1] + ln[3]) / 2 * k))]
            if len(hits) != 1:
                continue
            area = next(f for f in entity.facts if f.key == "area")
            assert isinstance(area.value, float)
            out.append({
                "sheet": render.stem, "room": entity.label, "printed_sqft": hits[0], "area_m2": area.value,
                "rel": round(area.value / SQFT_M2 / hits[0] - 1, 4), "source": plan.scale.source,
                "agreeing": measured.agreeing if measured else None, "spread": measured.spread if measured else None,
            })  # fmt: skip
    return out


def main() -> None:
    found = rows()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "room_margin.jsonl").write_text("\n".join(json.dumps(r) for r in found))

    def divided(r: dict) -> bool:
        return bool(sheet_plan.DIVIDED.search(r["room"]))

    def weak(r: dict) -> bool:
        return r["source"] == "dimension lines" and (r["agreeing"] or 0) < STRONG_LINES

    buckets = {
        "normal": [r for r in found if not divided(r) and not weak(r) and r["area_m2"] >= SMALL_ROOM_M2],
        "small": [r for r in found if not divided(r) and not weak(r) and r["area_m2"] < SMALL_ROOM_M2],
        "weak scale": [r for r in found if not divided(r) and weak(r)],
        "divided": [r for r in found if divided(r)],
    }
    print(f"{len(found)} rooms")
    for name, group in buckets.items():
        errors = sorted(abs(r["rel"]) for r in group)
        shares = {t: sum(e <= t for e in errors) for t in (0.02, 0.05, 0.10, 0.25, 0.50)}
        print(f"{name:12s} rooms {len(errors):3d}  inside: " + "  ".join(f"{t:.0%} {n}" for t, n in shares.items()))


if __name__ == "__main__":
    main()
