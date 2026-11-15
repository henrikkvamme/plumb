# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Do SVG canvas size and F1_original.png size agree? Compared for Stoa plans and the 213 left-out plans.

Writes out/svg_png_alignment.json.
"""
import collections
import io
import json
import pathlib
import re
import zipfile
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
EXT = ROOT / "data/external/cubicasa5k"
OUT = pathlib.Path(__file__).parent / "out"


def main():
    ids = json.load(open(OUT / "public_ids.json"))
    z = zipfile.ZipFile(EXT / "cubicasa5k.zip")
    res = collections.defaultdict(collections.Counter)
    ex = collections.defaultdict(list)
    for key, meta in ids.items():
        g, i = key.rsplit("-", 1)
        head = (EXT / "svg" / g / i / "model.svg").read_text(errors="ignore")[:600]
        w = float(re.search(r'width="([\d.]+)"', head).group(1))
        h = float(re.search(r'height="([\d.]+)"', head).group(1))
        im = Image.open(io.BytesIO(z.read(f"cubicasa5k/{g}/{i}/F1_original.png")))
        rw, rh = w / im.width, h / im.height
        tag = "equal" if abs(rw - 1) < 0.01 and abs(rh - 1) < 0.01 else ("same_ratio" if abs(rw - rh) < 0.02 else "different_aspect")
        res[str(meta["in_stoa"])][tag] += 1
        if tag != "equal" and len(ex[str(meta["in_stoa"]) + tag]) < 5:
            ex[str(meta["in_stoa"]) + tag].append([key, round(rw, 3), round(rh, 3)])
    json.dump({"counts": res, "examples": ex}, open(OUT / "svg_png_alignment.json", "w"), indent=1)
    print(json.dumps(res))


if __name__ == "__main__":
    main()
