# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow", "numpy"]
# ///
"""Which public CubiCasa5K image is each Stoa PNG? And what are the 213 public plans Stoa left out?

For every Stoa PNG, compares its size and pixels with F1_original.png and F1_scaled.png in the public zip.
Writes out/image_identity.json.
"""
import collections
import hashlib
import io
import json
import pathlib
import zipfile
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
ZIP = ROOT / "data/external/cubicasa5k/cubicasa5k.zip"
DS = ROOT / "data/junction-dataset/data/cubicasa5k"
OUT = pathlib.Path(__file__).parent / "out"


def main():
    z = zipfile.ZipFile(ZIP)
    names = set(z.namelist())
    res = collections.Counter()
    examples = collections.defaultdict(list)
    per = {}
    for p in sorted(DS.glob("*.png")):
        g, i = p.stem.rsplit("-", 1)
        base = f"cubicasa5k/{g}/{i}/"
        a = Image.open(p)
        sa = a.size
        stoa_bytes = p.read_bytes()
        verdict = "none"
        for kind in ("F1_original.png", "F1_scaled.png"):
            raw = z.read(base + kind)
            if hashlib.md5(raw).digest() == hashlib.md5(stoa_bytes).digest():
                verdict = kind + ":bytes_equal"
                break
            b = Image.open(io.BytesIO(raw))
            if b.size == sa:
                x = np.asarray(a.convert("RGB"), dtype=np.int16)
                y = np.asarray(b.convert("RGB"), dtype=np.int16)
                diff = float(np.abs(x - y).mean())
                verdict = f"{kind}:same_size_meandiff={'0' if diff == 0 else ('<1' if diff < 1 else '>=1')}"
                break
        nfloors_png = sum(1 for k in range(1, 6) if base + f"F{k}_original.png" in names)
        per[p.name] = {"verdict": verdict, "f_pngs": nfloors_png}
        res[verdict] += 1
        if len(examples[verdict]) < 3:
            examples[verdict].append(p.name)
    json.dump({"counts": res, "examples": examples, "per": per}, open(OUT / "image_identity.json", "w"), indent=1)
    print(dict(res))


if __name__ == "__main__":
    main()
