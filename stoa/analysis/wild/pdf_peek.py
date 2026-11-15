# /// script
# requires-python = ">=3.11"
# dependencies = ["pymupdf"]
# ///
"""Render a PDF page (or a crop) to PNG and dump its text, to verify probe answers by eye.

uv run pdf_peek.py <pdf> <outdir> [--page N] [--dpi D] [--clip x0,y0,x1,y1 (fractions 0-1)] [--text]
"""
import argparse, sys
from pathlib import Path
import pymupdf as fitz

ap = argparse.ArgumentParser()
ap.add_argument("pdf")
ap.add_argument("outdir")
ap.add_argument("--page", type=int, default=0)
ap.add_argument("--dpi", type=int, default=60)
ap.add_argument("--clip", default=None)
ap.add_argument("--text", action="store_true")
ap.add_argument("--tag", default="p")
a = ap.parse_args()
d = fitz.open(a.pdf)
pg = d[a.page]
r = pg.rect
clip = None
if a.clip:
    x0, y0, x1, y1 = map(float, a.clip.split(","))
    clip = fitz.Rect(r.x0 + x0 * r.width, r.y0 + y0 * r.height, r.x0 + x1 * r.width, r.y0 + y1 * r.height)
out = Path(a.outdir)
out.mkdir(parents=True, exist_ok=True)
pix = pg.get_pixmap(dpi=a.dpi, clip=clip)
fn = out / f"{a.tag}.png"
pix.save(fn)
print(fn, pix.width, pix.height, "pages", d.page_count)
if a.text:
    # words mapped to the visible (rotated) frame, grouped into lines by y, left to right
    m = pg.rotation_matrix
    vis = pg.rect * m if pg.rotation else pg.rect
    vr = fitz.Rect(0, 0, abs(vis.width), abs(vis.height))
    vclip = None
    if a.clip:
        x0, y0, x1, y1 = map(float, a.clip.split(","))
        vclip = fitz.Rect(x0 * vr.width, y0 * vr.height, x1 * vr.width, y1 * vr.height)
    items = []
    for w in pg.get_text("words"):
        r = fitz.Rect(w[:4]) * m
        r.normalize()
        if vclip and not vclip.intersects(r):
            continue
        items.append(((r.y0 + r.y1) / 2, r.x0, w[4]))
    items.sort()
    lines, cur, cy = [], [], None
    for y, x, w in items:
        if cy is not None and abs(y - cy) > 2.5:
            lines.append(cur)
            cur = []
        if not cur:
            cy = y
        cur.append((x, w))
    if cur:
        lines.append(cur)
    t = "\n".join(" ".join(w for _, w in sorted(l)) for l in lines)
    (out / f"{a.tag}.txt").write_text(t)
    print("text lines", len(lines), "->", out / f"{a.tag}.txt")
