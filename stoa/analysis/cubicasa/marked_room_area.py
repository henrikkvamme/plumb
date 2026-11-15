"""How exact is the box of a room that the symbol detector marks, against the CubiCasa5K room polygon?

A small raster plan with a scale from the user and no room numbers has only these boxes as room shapes. For each
plan: the detector, its marked rooms (`raster_tools.detected_rooms`), and the SVG room polygon that holds the box
centre. The ratio is box area to polygon area. Writes out/marked_room_area.json.

Run: uv run python analysis/cubicasa/marked_room_area.py [plans]
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

ROOT = Path(__file__).resolve().parents[2]
PNG = ROOT / "data/junction-dataset/data/cubicasa5k"
SVG = ROOT / "data/external/cubicasa5k/svg"
OUT = Path(__file__).parent / "out/marked_room_area.json"
LIMITS = (0.05, 0.10, 0.15, 0.20, 0.30, 0.50)


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    names = sorted(p.stem for p in PNG.glob("*.png"))
    random.Random(7).shuffle(names)
    ratios: list[float] = []
    plans = 0
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
        rows = raster_tools.detected_rooms(raster_tools.detector_for(PNG / f"{name}.png"), [])
        plan = cubicasa.parse_svg(svg, name)
        plans += 1
        for row in rows:
            x0, y0, x1, y1 = row["box_px"]
            centre = Point((x0 + x1) / 2 / fx, (y0 + y1) / 2 / fy)
            inside = [r for r in plan.rooms if r.poly.contains(centre) and r.poly.area > 0]
            if len(inside) == 1:
                ratios.append((x1 - x0) * (y1 - y0) / (inside[0].poly.area * fx * fy))
        print(name, len(ratios), flush=True)
    errors = sorted(abs(r - 1) for r in ratios)
    out = {
        "plans": plans, "rooms": len(ratios), "median_ratio": round(statistics.median(ratios), 4),
        "within": {f"{x:g}": round(sum(1 for e in errors if e <= x) / len(errors), 4) for x in LIMITS},
        "error_at_90_percent": round(errors[int(0.9 * len(errors))], 4),
    }  # fmt: skip
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out))


main()
