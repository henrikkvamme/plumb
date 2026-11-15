# /// script
# requires-python = ">=3.11"
# dependencies = ["lxml"]
# ///
"""Extract per-plan features from the public CubiCasa5K model.svg files.

Input: stoa/data/external/cubicasa5k/svg/<group>/<id>/model.svg (from fetch_public_svgs.py --local).
Output: out/svg_features.json keyed by Stoa file name (<group>-<id>.png), with:
  floors (Floorplan groups), door and window class counts, FixedFurniture class counts,
  Space class counts, Space name labels, and the public split.
Also writes out/public_ids.json: every public plan id with its split and whether Stoa has it.
"""
import collections
import json
import pathlib
from lxml import etree

ROOT = pathlib.Path(__file__).resolve().parents[2]
EXT = ROOT / "data/external/cubicasa5k"
DS = ROOT / "data/junction-dataset/data/cubicasa5k"
OUT = pathlib.Path(__file__).parent / "out"


def cls(e):
    return " ".join((e.get("class") or "").split())


def name_label(space):
    for e in space.iter():
        if cls(e) == "TextLabel NameLabel":
            texts = ["".join(t.itertext()).strip() for t in e.iter("{http://www.w3.org/2000/svg}text")]
            texts = [t for t in texts if t]
            return " ".join(texts)
    return ""


def features(path):
    root = etree.parse(str(path)).getroot()
    f = {"floorplans": [], "doors": collections.Counter(), "windows": collections.Counter(),
         "furniture": collections.Counter(), "spaces": collections.Counter(), "space_labels": [],
         "door_panels": [], "per_floor": []}
    for e in root.iter():
        c = cls(e)
        if not c:
            continue
        first = c.split()[0]
        if first == "Floorplan":
            f["floorplans"].append(c)
            # per-floor counts
            fl = collections.Counter()
            for x in e.iter():
                cx = cls(x)
                if cx.startswith("Door ") or cx.startswith("Window ") or cx.startswith("FixedFurniture ") or cx.startswith("Space "):
                    fl[cx] += 1
            f["per_floor"].append(dict(fl))
        elif first == "Door":
            f["doors"][c] += 1
            panels = [cls(x) for x in e.iter() if cls(x).startswith("Panel")]
            f["door_panels"].append([c, len(panels)])
        elif first == "Window":
            f["windows"][c] += 1
        elif first == "FixedFurniture":
            f["furniture"][c] += 1
        elif first == "Space":
            f["spaces"][c] += 1
            f["space_labels"].append([c, name_label(e)])
    return f


def main():
    splits = {}
    for s in ("train", "val", "test"):
        for line in open(EXT / "splits" / f"{s}.txt"):
            line = line.strip().strip("/")
            if line:
                g, i = line.split("/")[-2:]
                splits[f"{g}-{i}"] = s
    stoa = {p.stem for p in DS.glob("*.png")}
    pub = {}
    for svg in sorted((EXT / "svg").glob("*/*/model.svg")):
        key = f"{svg.parent.parent.name}-{svg.parent.name}"
        pub[key] = svg
    feats = {}
    for key in sorted(stoa & set(pub)):
        try:
            feats[key + ".png"] = features(pub[key]) | {"split": splits.get(key)}
        except Exception as ex:  # noqa: BLE001
            feats[key + ".png"] = {"error": repr(ex), "split": splits.get(key)}
    json.dump(feats, open(OUT / "svg_features.json", "w"))
    ids = {k: {"split": splits.get(k), "in_stoa": k in stoa} for k in pub}
    json.dump(ids, open(OUT / "public_ids.json", "w"))
    print("public", len(pub), "stoa", len(stoa), "matched", len(feats), "stoa_not_public", len(stoa - set(pub)))


if __name__ == "__main__":
    main()
