"""Render one PDF page to PNG: render.py <pdf> <out.png> [page] [max_px]"""
import sys, fitz
pdf, out = sys.argv[1], sys.argv[2]; page = int(sys.argv[3]) if len(sys.argv)>3 else 0; mx = int(sys.argv[4]) if len(sys.argv)>4 else 1800
d = fitz.open(pdf); p = d[page]; r = p.rect; z = mx/max(r.width, r.height)
p.get_pixmap(matrix=fitz.Matrix(z,z)).save(out)
print("pages", len(d), "size_pt", round(r.width), round(r.height), "text_chars", len(p.get_text()), "drawings", len(p.get_drawings()), "images", len(p.get_images()))
