# /// script
# requires-python = ">=3.11"
# dependencies = ["lxml", "shapely", "numpy"]
# ///
"""Explain the template filter with geometry: which room holds each fixture?

For every plan, makes tokens "<fixture class>@<room class>" (the smallest Space polygon that holds the
fixture centre) and "<fixture>@NONE". Also adds tokens for overlapping fixtures (for example a shower
inside a bathtub). Then, for each template, after removing the plans explained by the simple class
filters (presence_rules.py), ranks tokens by how well they predict "template absent".
Writes out/presence_geometry.json and out/fixture_tokens.json.
"""
import collections
import json
import pathlib
import re
import sys
import numpy as np
from lxml import etree
from shapely.geometry import Point, Polygon

ROOT = pathlib.Path(__file__).resolve().parents[2]
SVG = ROOT / "data/external/cubicasa5k/svg"
OUT = pathlib.Path(__file__).parent / "out"
P = {k.split("/")[-1]: v for k, v in json.load(open(OUT / "presence.json")).items()}
F = json.load(open(OUT / "svg_features.json"))
NS = "{http://www.w3.org/2000/svg}"


def cls(e):
    return " ".join((e.get("class") or "").split())


def mat(e):
    m = re.search(r"matrix\(([^)]*)\)", e.get("transform") or "")
    if not m:
        return np.eye(3)
    a, b, c, d, e_, f = [float(x) for x in re.split(r"[ ,]+", m.group(1).strip())]
    return np.array([[a, c, e_], [b, d, f], [0, 0, 1]])


def full(e):
    chain = []
    while e is not None:
        chain.append(e)
        e = e.getparent()
    m = np.eye(3)
    for x in reversed(chain):
        m = m @ mat(x)
    return m


def pts(s):
    v = [float(x) for x in re.split(r"[ ,]+", s.strip()) if x]
    return list(zip(v[0::2], v[1::2]))


def poly_of(e, first_child_only=False):
    if first_child_only:
        p = e.find(NS + "polygon")
    else:
        p = None
        for x in e.iter():
            if cls(x) == "BoundaryPolygon":
                p = x.find(NS + "polygon")
                break
    if p is None:
        return None
    m = full(e) if first_child_only else full(e)
    q = [tuple((m @ np.array([x, y, 1]))[:2]) for x, y in pts(p.get("points"))]
    if len(q) < 3:
        return None
    return Polygon(q).buffer(0)


def tokens(path):
    root = etree.parse(str(path)).getroot()
    spaces, fixtures = [], []
    for e in root.iter():
        c = cls(e)
        if c.startswith("Space "):
            g = poly_of(e, first_child_only=True)
            if g is not None and g.area > 0:
                spaces.append((c, g))
        elif c.startswith("FixedFurniture ") and not c.startswith("FixedFurnitureSet"):
            g = poly_of(e)
            if g is not None:
                fixtures.append((c.replace("FixedFurniture ", ""), g))
    toks = set()
    for c, g in fixtures:
        pt = g.representative_point() if g.area > 0 else g.centroid
        hit = [s for s in spaces if s[1].contains(pt)]
        room = min(hit, key=lambda s: s[1].area)[0] if hit else "NONE"
        toks.add(f"{c}@{room}")
    wet = [(c, g) for c, g in fixtures if any(w in c for w in ("Shower", "Bathtub", "Jacuzzi"))]
    for i, (c1, g1) in enumerate(wet):
        for c2, g2 in wet[i + 1:]:
            if g1.area and g2.area and g1.intersection(g2).area > 0.3 * min(g1.area, g2.area):
                toks.add("OVERLAP:" + "+".join(sorted([c1, c2])))
    return sorted(toks)


SIMPLE = {
    "doors": lambda v: not any(v["doors"].get(c, 0) for c in ("Door None Beside", "Door RollUp Beside", "Door ParallelSlide Beside")),
    "bedrooms": lambda v: not v["spaces"].get("Space UserDefined") and not v["spaces"].get("Space Room"),
    "kitchens": lambda v: not v["spaces"].get("Space UserDefined"),
    "bathrooms": lambda v: not v["spaces"].get("Space UserDefined"),
    "wc_rooms": lambda v: not v["spaces"].get("Space UserDefined"),
    "saunas": lambda v: not v["spaces"].get("Space UserDefined"),
    "balconies": lambda v: not v["spaces"].get("Space UserDefined") and not v["spaces"].get("Space Outdoor"),
    "showers_tubs": lambda v: not v["furniture"].get("FixedFurniture Jacuzzi"),
    "sinks": lambda v: not v["furniture"].get("FixedFurniture WaterTap"),
    "toilets": lambda v: True,
}


def main():
    tok_file = OUT / "fixture_tokens.json"
    if tok_file.exists() and "--recompute" not in sys.argv:
        T = json.load(open(tok_file))
    else:
        T = {}
        for k in F:
            g, i = k[:-4].rsplit("-", 1)
            T[k] = tokens(SVG / g / i / "model.svg")
        json.dump(T, open(tok_file, "w"))
    res = {}
    for t, simple in SIMPLE.items():
        keys = [k for k in F if simple(F[k])]
        absent = {k for k in keys if t not in P[k]}
        wrong_present = sum(1 for k in F if not simple(F[k]) and t in P[k])
        cnt = collections.Counter()
        for k in keys:
            cnt.update(T[k])
        ranked = []
        for tok, n in cnt.items():
            if n < 5:
                continue
            a = sum(1 for k in keys if k in absent and tok in T[k])
            ranked.append({"token": tok, "n_with": n, "absent_with": a, "precision": round(a / n, 3),
                           "recall": round(a / max(1, len(absent)), 3)})
        ranked.sort(key=lambda s: (-s["precision"], -s["recall"]))
        res[t] = {"after_simple_filter": len(keys), "still_absent": len(absent),
                  "simple_filter_violations": wrong_present, "top": ranked[:15]}
    json.dump(res, open(OUT / "presence_geometry.json", "w"), indent=1)


if __name__ == "__main__":
    main()
