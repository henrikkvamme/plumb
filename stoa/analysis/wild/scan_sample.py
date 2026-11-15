# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow", "numpy"]
# ///
"""Historic scans (habs, finna, europeana, wikimedia): image statistics for every file, and a fixed-seed
random sample per source rendered as numbered contact sheets for classification by eye.

Writes analysis/wild/out/scan_stats.json, scan_sample.json and contact sheets to <outdir>.
Run: uv run stoa/analysis/wild/scan_sample.py <outdir> [--n 30]
"""
import json, random, sys, collections, argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps
import numpy as np

Image.MAX_IMAGE_PIXELS = None
ROOT = Path(__file__).resolve().parents[2] / "data/junction-dataset/data"
OUT = Path(__file__).resolve().parent / "out"
SOURCES = ["habs", "finna", "europeana", "wikimedia"]

ap = argparse.ArgumentParser()
ap.add_argument("outdir")
ap.add_argument("--n", type=int, default=30)
ap.add_argument("--seed", type=int, default=2026)
a = ap.parse_args()
od = Path(a.outdir)
od.mkdir(parents=True, exist_ok=True)


def stats(p):
    im = Image.open(p)
    w, h = im.size
    im.draft("RGB", (400, 400))
    im = im.convert("RGB")
    im.thumbnail((256, 256))
    arr = np.asarray(im).astype(float)
    mx, mn = arr.max(2), arr.min(2)
    sat = ((mx - mn) / np.maximum(mx, 1)).mean()
    gray = arr.mean(2)
    return {"w": w, "h": h, "mp": round(w * h / 1e6, 2), "sat": round(float(sat), 3),
            "mean": round(float(gray.mean()), 1), "dark_frac": round(float((gray < 100).mean()), 3)}


summary, sample = {}, {}
for src in SOURCES:
    files = sorted(p for p in (ROOT / src).iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    st = []
    for p in files:
        try:
            st.append(stats(p))
        except Exception as e:  # noqa: BLE001
            st.append({"error": str(e)[:80]})
    ok = [s for s in st if "w" in s]
    mps = sorted(s["mp"] for s in ok)
    summary[src] = {
        "n_raster": len(files),
        "n_svg": sum(1 for p in (ROOT / src).iterdir() if p.suffix.lower() == ".svg"),
        "errors": len(st) - len(ok),
        "median_mp": mps[len(mps) // 2],
        "p10_mp": mps[len(mps) // 10], "p90_mp": mps[9 * len(mps) // 10],
        "max_side_3000": sum(1 for s in ok if max(s["w"], s["h"]) == 3000),
        "max_side_lt_1000": sum(1 for s in ok if max(s["w"], s["h"]) < 1000),
        "colour_sat_gt_0.15": sum(1 for s in ok if s["sat"] > 0.15),
        "near_bw_sat_lt_0.05": sum(1 for s in ok if s["sat"] < 0.05),
        "dark_background_mean_lt_110": sum(1 for s in ok if s["mean"] < 110),
    }
    rnd = random.Random(a.seed)
    pick = rnd.sample(files, min(a.n, len(files)))
    sample[src] = [p.name for p in pick]
    per = 6
    for si in range(0, len(pick), per):
        tiles = []
        for i, p in enumerate(pick[si:si + per]):
            im = Image.open(p)
            im.draft("RGB", (1100, 1100))
            im = ImageOps.exif_transpose(im.convert("RGB"))
            im.thumbnail((560, 560))
            canvas = Image.new("RGB", (580, 600), "white")
            canvas.paste(im, ((580 - im.width) // 2, 30))
            d = ImageDraw.Draw(canvas)
            d.rectangle([0, 0, 579, 26], fill=(255, 230, 0))
            d.text((6, 6), f"{src} #{si + i}: {p.name[:60]}", fill="black")
            tiles.append(canvas)
        sheet = Image.new("RGB", (580 * 3, 600 * 2), "gray")
        for i, t in enumerate(tiles):
            sheet.paste(t, ((i % 3) * 580, (i // 3) * 600))
        sheet.save(od / f"{src}_{si // per:02d}.jpg", quality=85)

json.dump(summary, open(OUT / "scan_stats.json", "w"), indent=1)
json.dump(sample, open(OUT / "scan_sample.json", "w"), indent=1)
print(json.dumps(summary))
