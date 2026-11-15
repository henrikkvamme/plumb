# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Crop a raster drawing to a region (fractions 0-1) and save it at a readable size, to verify probe answers
by eye. Prints the source size and the crop box in source pixels.

uv run img_peek.py <image> <out.png> [--clip x0,y0,x1,y1] [--max 1600]
"""
import argparse
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ap = argparse.ArgumentParser()
ap.add_argument("img")
ap.add_argument("out")
ap.add_argument("--clip", default="0,0,1,1")
ap.add_argument("--max", type=int, default=1600)
a = ap.parse_args()
im = Image.open(a.img).convert("RGB")
W, H = im.size
x0, y0, x1, y1 = map(float, a.clip.split(","))
box = (int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H))
c = im.crop(box)
c.thumbnail((a.max, a.max))
c.save(a.out)
print("src", W, H, "box", box, "out", c.size)
