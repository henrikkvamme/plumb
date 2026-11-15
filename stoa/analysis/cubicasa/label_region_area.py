"""How exact is the pixel area of the region around a room-name text, against the CubiCasa5K room polygon?

A small raster plan with a scale from the user gives room areas from these regions (`raster_tools.label_areas`).
For each plan: OCR, the region of each room-name text, and the SVG room polygon that holds the text point. A room
counts when exactly one text lies in it. The SVG canvas maps to the PNG by the width ratio (plans with another
aspect are left out). Writes out/label_region_area.json.

Run: uv run python analysis/cubicasa/label_region_area.py [plans]
"""

import json
import random
import statistics
import sys
from pathlib import Path

from PIL import Image
from shapely.geometry import Point

from bp.hardcases import cubicasa
from bp.solvers import raster_tools
from bp.tools import ocr, sheet_text

ROOT = Path(__file__).resolve().parents[2]
PNG = ROOT / "data/junction-dataset/data/cubicasa5k"
SVG = ROOT / "data/external/cubicasa5k/svg"
OUT = Path(__file__).parent / "out/label_region_area.json"
LIMITS = (0.05, 0.10, 0.15, 0.20, 0.30, 0.50)


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    names = sorted(p.stem for p in PNG.glob("*.png"))
    random.Random(7).shuffle(names)
    ratios: list[float] = []
    plans = no_region = 0
    for name in names:
        if plans >= count:
            break
        group, number = name.rsplit("-", 1)
        svg = SVG / group / number / "model.svg"
        if not svg.exists():
            continue
        head = svg.read_text(errors="ignore")[:600]
        width = float(head.split('width="')[1].split('"')[0])
        height = float(head.split('height="')[1].split('"')[0])
        image = Image.open(PNG / f"{name}.png")
        fx, fy = image.width / width, image.height / height
        if abs(fx / fy - 1) > 0.02:
            continue
        rgb = ocr.to_rgb(PNG / f"{name}.png")
        if sheet_text.is_sheet(rgb):
            continue
        lines = ocr.read_lines(rgb)
        if not lines:
            continue
        plan = cubicasa.parse_svg(svg, name)
        rows = raster_tools.label_areas(rgb, lines)
        plans += 1
        for room in plan.rooms:
            inside = [r for r in rows if room.poly.contains(Point(r["at_px"][0] / fx, r["at_px"][1] / fy))]
            if len(inside) != 1 or room.poly.area <= 0:
                continue
            if inside[0]["area_px"] is None:
                no_region += 1
                continue
            ratios.append(inside[0]["area_px"] / (room.poly.area * fx * fy))
        print(name, len(ratios), flush=True)
    errors = sorted(abs(r - 1) for r in ratios)
    out = {
        "plans": plans, "rooms": len(ratios), "rooms_with_no_closed_region": no_region,
        "median_ratio": round(statistics.median(ratios), 4),
        "within": {f"{x:g}": round(sum(1 for e in errors if e <= x) / len(errors), 4) for x in LIMITS},
        "error_at_90_percent": round(errors[int(0.9 * len(errors))], 4),
    }  # fmt: skip
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out))


main()
