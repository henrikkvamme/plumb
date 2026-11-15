# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow", "numpy"]
# ///
"""Measure a length on a raster drawing against its scale bar, to set ground truth for the length probes.

For a clip region (fractions 0-1) it prints the extent of dark pixels (gray < thr) in source pixels. Run it once
on the scale-bar line (a thin band that holds the bar but not its labels) and once on the building outline.
metres = building_px / bar_px * bar_m.

uv run measure_scale.py <image> --bar x0,y0,x1,y1 --bar-m 5 --obj x0,y0,x1,y1 [--thr 128] [--axis x|y]
"""
import argparse
import json
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ap = argparse.ArgumentParser()
ap.add_argument("img")
ap.add_argument("--bar", required=True)
ap.add_argument("--bar-m", type=float, required=True)
ap.add_argument("--obj", required=True)
ap.add_argument("--axis", default="x", choices=["x", "y"])
ap.add_argument("--thr", type=int, default=128)
a = ap.parse_args()
g = np.asarray(Image.open(a.img).convert("L")).astype(int)
H, W = g.shape


def extent(clip, axis):
    x0, y0, x1, y1 = map(float, clip.split(","))
    X0, Y0, X1, Y1 = int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)
    m = g[Y0:Y1, X0:X1] < a.thr
    if axis == "x":
        idx = np.where(m.any(0))[0]
        return int(idx.min() + X0), int(idx.max() + X0)
    idx = np.where(m.any(1))[0]
    return int(idx.min() + Y0), int(idx.max() + Y0)


b0, b1 = extent(a.bar, "x")
o0, o1 = extent(a.obj, a.axis)
bar_px = b1 - b0
obj_px = o1 - o0
res = {"img": a.img.split("/")[-1], "size": [W, H], "bar_px": [b0, b1, bar_px], "bar_m": a.bar_m,
       "px_per_m": round(bar_px / a.bar_m, 2), "obj_axis": a.axis, "obj_px": [o0, o1, obj_px],
       "obj_m": round(obj_px / bar_px * a.bar_m, 2)}
print(json.dumps(res))
