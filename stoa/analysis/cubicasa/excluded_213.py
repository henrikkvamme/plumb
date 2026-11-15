# /// script
# requires-python = ">=3.11"
# dependencies = ["lxml", "pillow"]
# ///
"""Why are 213 public CubiCasa5K plans not in Stoa's set? Compare them with the 4,787 included plans.

Reads the public zip and SVGs. Writes out/excluded_213.json with per-plan facts and group comparisons.
"""
import collections
import io
import json
import pathlib
import sys
import zipfile
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from svg_features import features  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EXT = ROOT / "data/external/cubicasa5k"
OUT = pathlib.Path(__file__).parent / "out"


def main():
    ids = json.load(open(OUT / "public_ids.json"))
    z = zipfile.ZipFile(EXT / "cubicasa5k.zip")
    names = set(z.namelist())
    rows = {}
    for key, meta in ids.items():
        g, i = key.rsplit("-", 1)
        base = f"cubicasa5k/{g}/{i}/"
        svg = EXT / "svg" / g / i / "model.svg"
        r = {"in_stoa": meta["in_stoa"], "split": meta["split"],
             "f_pngs": sum(1 for k in range(1, 6) if base + f"F{k}_original.png" in names)}
        try:
            f = features(svg)
            r.update(floorplans=len(f["floorplans"]), n_doors=sum(f["doors"].values()),
                     n_windows=sum(f["windows"].values()), n_spaces=sum(f["spaces"].values()),
                     n_furniture=sum(f["furniture"].values()), error=None)
        except Exception as ex:  # noqa: BLE001
            r.update(error=repr(ex)[:200])
        if not meta["in_stoa"]:
            im = Image.open(io.BytesIO(z.read(base + "F1_original.png")))
            r.update(size=im.size, mode=im.mode)
        rows[key] = r
    summ = {}
    for flag in (True, False):
        sel = [r for r in rows.values() if r["in_stoa"] is flag]
        summ[str(flag)] = {
            "n": len(sel),
            "errors": sum(1 for r in sel if r.get("error")),
            "floorplans_eq_fpngs": sum(1 for r in sel if r.get("floorplans") == r["f_pngs"]),
            "floorplans_dist": dict(collections.Counter(r.get("floorplans") for r in sel)),
            "fpngs_dist": dict(collections.Counter(r["f_pngs"] for r in sel)),
            "zero_doors": sum(1 for r in sel if r.get("n_doors") == 0),
            "zero_windows": sum(1 for r in sel if r.get("n_windows") == 0),
            "zero_spaces": sum(1 for r in sel if r.get("n_spaces") == 0),
            "zero_furniture": sum(1 for r in sel if r.get("n_furniture") == 0),
        }
    json.dump({"summary": summ, "excluded": {k: r for k, r in rows.items() if not r["in_stoa"]}},
              open(OUT / "excluded_213.json", "w"), indent=1)
    print(json.dumps(summ))


if __name__ == "__main__":
    main()
