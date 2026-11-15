# /// script
# requires-python = ">=3.11"
# dependencies = ["lxml", "shapely", "numpy"]
# ///
"""Test geometric rules for the sauna template: which room holds each sauna stove?

Candidate rules:
  stoves            number of SaunaStove elements
  stove_rooms       number of distinct Space polygons that contain a stove centre
  stove_rooms_or_space_sauna   |stove rooms  UNION  Space Sauna polygons|
Writes out/sauna_geometry.json with agreement per rule and the disagreements of the best rule.
"""
import json
import pathlib
import re
import numpy as np
from lxml import etree
from shapely.geometry import Point, Polygon

ROOT = pathlib.Path(__file__).resolve().parents[2]
SVG = ROOT / "data/external/cubicasa5k/svg"
OUT = pathlib.Path(__file__).parent / "out"
P = {k.split("/")[-1]: v for k, v in json.load(open(OUT / "presence.json")).items()}
F = json.load(open(OUT / "svg_features.json"))


def cls(e):
    return " ".join((e.get("class") or "").split())


def mat(e):
    t = e.get("transform") or ""
    m = re.search(r"matrix\(([^)]*)\)", t)
    if not m:
        return np.eye(3)
    a, b, c, d, e_, f = [float(x) for x in re.split(r"[ ,]+", m.group(1).strip())]
    return np.array([[a, c, e_], [b, d, f], [0, 0, 1]])


def full(e):
    m = np.eye(3)
    chain = []
    while e is not None:
        chain.append(e)
        e = e.getparent()
    for x in reversed(chain):
        m = m @ mat(x)
    return m


def pts(s):
    v = [float(x) for x in re.split(r"[ ,]+", s.strip()) if x]
    return list(zip(v[0::2], v[1::2]))


def rules(path):
    root = etree.parse(str(path)).getroot()
    spaces = []
    for e in root.iter():
        c = cls(e)
        if c.startswith("Space "):
            poly = e.find("{http://www.w3.org/2000/svg}polygon")
            if poly is not None:
                m = full(e)
                p = [tuple((m @ np.array([x, y, 1]))[:2]) for x, y in pts(poly.get("points"))]
                if len(p) >= 3:
                    spaces.append((c, Polygon(p).buffer(0)))
    stoves = []
    for e in root.iter():
        c = cls(e)
        if "SaunaStove" in c:
            bp = None
            for x in e.iter():
                if cls(x) == "BoundaryPolygon":
                    bp = x.find("{http://www.w3.org/2000/svg}polygon")
                    break
            if bp is None:
                continue
            q = np.array(pts(bp.get("points")))
            cx, cy = q.mean(axis=0)
            m = full(e)
            stoves.append(Point(*(m @ np.array([cx, cy, 1]))[:2]))
    rooms = set()
    unplaced = 0
    for s in stoves:
        hit = [i for i, (c, poly) in enumerate(spaces) if poly.contains(s)]
        if hit:
            rooms.add(min(hit, key=lambda i: spaces[i][1].area))
        else:
            unplaced += 1
    sauna_spaces = {i for i, (c, _) in enumerate(spaces) if c == "Space Sauna"}
    return {
        "stoves": len(stoves),
        "stove_rooms": len(rooms) + unplaced,
        "stove_rooms_or_space_sauna": len(rooms | sauna_spaces) + unplaced,
        "room_classes": sorted(spaces[i][0] for i in rooms),
    }


def main():
    keys = [k for k in F if "saunas" in P[k]]
    agg = {}
    dis = {}
    room_cls = {}
    for k in keys:
        g, i = k[:-4].rsplit("-", 1)
        r = rules(SVG / g / i / "model.svg")
        for c in r["room_classes"]:
            room_cls[c] = room_cls.get(c, 0) + 1
        for name in ("stoves", "stove_rooms", "stove_rooms_or_space_sauna"):
            ok = r[name] == P[k]["saunas"]
            agg[name] = agg.get(name, 0) + ok
            if not ok:
                dis.setdefault(name, []).append({"file": k, "rule": r[name], "ref": P[k]["saunas"]})
    res = {"n": len(keys), "agree": {k: round(v / len(keys), 4) for k, v in agg.items()},
           "n_disagree": {k: len(v) for k, v in dis.items()},
           "disagreements": {k: v[:12] for k, v in dis.items()}, "stove_room_classes": room_cls}
    json.dump(res, open(OUT / "sauna_geometry.json", "w"), indent=1)
    print(res["agree"], res["n_disagree"])


if __name__ == "__main__":
    main()
