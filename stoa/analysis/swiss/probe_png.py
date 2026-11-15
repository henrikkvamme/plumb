# /// script
# requires-python = ">=3.11"
# dependencies = ["pymupdf", "pillow", "numpy", "scipy"]
# ///
"""Raster-only area probe: how accurate is a room area measured on the 150 dpi PNG?

Simulates a PNG-only solver with perfect OCR: the room-number position and the text boxes come from the
PDF (only to place the seed and erase the text), the area comes from the raster alone.
Method: threshold light pixels, erase the room's own text, take the connected light region under the room
number, fill its holes (fixtures), optionally dilate 1 px (the room outline is drawn as a grey line), and
convert pixels to m² with the printed scale (1:100 or 1:200 on A3 at 150 dpi).
Scores area_room questions on a seeded sample of floors. Writes probe_png.json.
Usage: uv run probe_png.py [n_floors]
"""
import sys, re, json, pathlib, random, collections
import numpy as np
import pymupdf
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from qparse import parse

ROOT = pathlib.Path(__file__).resolve().parents[2]
D = ROOT / "data/junction-dataset/data/swiss_dwellings"
OUT = ROOT / "data/external/swiss-derived"
NUM = re.compile(r"^(U\d+\.)?\d+\.\d+$|^U\d+\.\d+$")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
rows = json.load(open(OUT / "rows.json"))
q = collections.defaultdict(list)
for r in rows:
    fam, p, lang = parse(r["question"])
    if fam == "area_room" and lang == "en":
        q[pathlib.Path(r["path"]).stem].append((p, r["answer"]))
random.seed(7)
floors = random.sample(sorted(q), N)
VARIANTS = [("t200", 200, 0), ("t200_dil1", 200, 1), ("t240", 240, 0), ("t240_dil1", 240, 1)]
res = {v[0]: [0, 0] for v in VARIANTS}
by_scale = collections.defaultdict(lambda: [0, 0])
errs = collections.defaultdict(list)
ex = []
for fl in floors:
    pg = pymupdf.open(D / f"{fl}.pdf")[0]
    im = np.asarray(Image.open(D / f"{fl}.png").convert("L"), dtype=np.uint8)
    k = im.shape[1] / pg.rect.width  # px per pt
    spans = []
    for b in pg.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                spans.append((s["text"].strip(), s["bbox"]))
    scale = next(int(m.group(1)) for t, _ in spans for m in [re.search(r"1:(\d+) \(A", t)] if m)
    px_per_m = k * 72 / 0.0254 / scale
    for num, ans in q[fl]:
        sp = [bb for t, bb in spans if t == num]
        if not sp:
            continue
        x0, y0, x1, y1 = sp[0]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        # erase the room's own text: spans whose centre is within 3 text heights above or below the number
        h = y1 - y0
        own = [bb for t, bb in spans if abs((bb[0] + bb[2]) / 2 - cx) < 2 and abs((bb[1] + bb[3]) / 2 - cy) < 3.2 * h]
        for name, thr, dil in VARIANTS:
            free = im > thr
            for bx in own:
                free[int(bx[1] * k) - 1:int(bx[3] * k) + 2, int(bx[0] * k) - 1:int(bx[2] * k) + 2] = True
            lab, _ = ndimage.label(free)
            seed = lab[int(cy * k), int(cx * k)]
            if seed == 0:
                continue
            reg = ndimage.binary_fill_holes(lab == seed)
            if dil:
                reg = ndimage.binary_dilation(reg, iterations=dil)
            area = float(reg.sum() / px_per_m ** 2)
            good = bool(abs(area - ans) <= 0.02 * ans)
            res[name][0] += good
            res[name][1] += 1
            errs[name].append((area - ans) / ans)
            if name == "t200_dil1":
                by_scale[scale][0] += good
                by_scale[scale][1] += 1
                if not good and len(ex) < 8:
                    ex.append({"floor": fl, "room": num, "ref": ans, "png": round(area, 2)})


def q50(x):
    x = sorted(abs(v) for v in x)
    return round(x[len(x) // 2], 4) if x else None


out = {"floors": N, "variants": {k: {"agree": a, "n": n, "rate": round(a / max(1, n), 4), "median_abs_rel_err": q50(errs[k])} for k, (a, n) in res.items()},
       "t200_dil1_by_scale": {str(k): {"agree": a, "n": n, "rate": round(a / n, 4)} for k, (a, n) in by_scale.items()}, "disagreements": ex}
json.dump(out, open(OUT / "probe_png.json", "w"), indent=1)
print(json.dumps(out)[:1200])
