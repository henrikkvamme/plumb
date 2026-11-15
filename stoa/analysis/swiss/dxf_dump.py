# /// script
# requires-python = ">=3.11"
# dependencies = ["ezdxf", "shapely"]
# ///
"""Dump DXF entities of one floor with geometry summaries (for reading the generator's conventions).
Usage: uv run dxf_dump.py <floor> [layer ...]"""
import sys, pathlib, ezdxf
from shapely.geometry import Polygon

ROOT = pathlib.Path(__file__).resolve().parents[2]
D = ROOT / "data/junction-dataset/data/swiss_dwellings"
f = sys.argv[1]
layers = set(sys.argv[2:])
dx = ezdxf.readfile(D / f"{f}.dxf")
for e in dx.modelspace():
    if layers and e.dxf.layer not in layers:
        continue
    t = e.dxftype()
    s = f"{e.dxf.layer:13s} {t:10s} color={e.dxf.get('color')} lt={e.dxf.get('linetype')} h={e.dxf.handle}"
    if t == "LWPOLYLINE":
        pts = [(p[0], p[1]) for p in e.get_points()]
        s += f" n={len(pts)} closed={e.closed} cw={e.dxf.get('const_width')}"
        if len(pts) >= 3:
            p = Polygon(pts)
            b = p.bounds
            s += f" area={p.area:.3f} bbox=({b[0]:.2f},{b[1]:.2f},{b[2]:.2f},{b[3]:.2f})"
    elif t == "CIRCLE":
        s += f" c=({e.dxf.center.x:.2f},{e.dxf.center.y:.2f}) r={e.dxf.radius:.3f}"
    elif t == "ARC":
        s += f" c=({e.dxf.center.x:.2f},{e.dxf.center.y:.2f}) r={e.dxf.radius:.3f} a={e.dxf.start_angle:.0f}-{e.dxf.end_angle:.0f}"
    elif t == "TEXT":
        s += f" '{e.dxf.text}' at=({e.dxf.insert.x:.2f},{e.dxf.insert.y:.2f}) h={e.dxf.height:.3f}"
    elif t == "HATCH":
        s += f" pattern={e.dxf.pattern_name} paths={len(e.paths)}"
    print(s)
