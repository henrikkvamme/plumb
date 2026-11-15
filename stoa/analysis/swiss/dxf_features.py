# /// script
# requires-python = ">=3.11"
# dependencies = ["ezdxf", "shapely"]
# ///
"""Extract candidate features from every swiss_dwellings DXF (the vector sibling of the PDF).

Per floor: rooms (label, number, polygon area, apartment), unit outlines, door and window entity
counts, fixture groups with a shape signature. Writes out/dxf_features.json.
Usage: uv run dxf_features.py [limit]
"""
import sys, re, json, pathlib, collections
import ezdxf
from shapely.geometry import Polygon, Point, box

ROOT = pathlib.Path(__file__).resolve().parents[2]
D = ROOT / "data/junction-dataset/data/swiss_dwellings"
OUT = ROOT / "data/external/swiss-derived"  # git-ignored; derived from licensed data
NUM = re.compile(r"^(U\d+\.)?\d+\.\d+$|^U\d+\.\d+$")
UNIT = re.compile(r"^(Whg\.|App\.|Appt\.|Apt\.|Wohnung|Appartement|Appartamento)\s*([A-Z]+)$")



def net_holes(polys):
    """The generator draws a room with a hole (a shaft or lift inside a stair hall) as an outer ring plus a
    separate inner polygon. Subtract every polygon that lies inside a larger one, as the source area does."""
    out = []
    for i, p in enumerate(polys):
        inner = [q for j, q in enumerate(polys) if j != i and q.area < p.area and p.buffer(1e-6).contains(q)]
        for q in inner:
            p = p.difference(q)
        out.append(p)
    return out

def pts(e):
    return [(p[0], p[1]) for p in e.get_points()]


def floor_features(path):
    dx = ezdxf.readfile(path)
    msp = dx.modelspace()
    ents = collections.defaultdict(list)
    for e in msp:
        ents[e.dxf.layer].append(e)
    f = {"layers": sorted(ents), "insunits": dx.header.get("$INSUNITS")}
    # texts
    texts = [(e.dxf.text, e.dxf.insert.x, e.dxf.insert.y, e.dxf.height) for e in ents["ROOM_TEXT"] if e.dxftype() == "TEXT"]
    nums = [t for t in texts if NUM.match(t[0])]
    units_t = [t for t in texts if UNIT.match(t[0])]
    other = [t for t in texts if not NUM.match(t[0]) and not UNIT.match(t[0])]
    f["unit_texts"] = [t[0] for t in units_t]
    f["other_texts_unpaired"] = []
    # room polygons
    polys = []
    for e in ents["ROOM_OUTLINE"]:
        if e.dxftype() == "LWPOLYLINE":
            p = pts(e)
            if len(p) >= 3:
                polys.append(Polygon(p).buffer(0))
    f["n_room_polys"] = len(polys)
    polys = net_holes(polys)
    # pair each number with the closest label text above it (same x, slightly higher y)
    rooms = []
    used = set()
    for n in nums:
        best, bd = None, 1e9
        for i, o in enumerate(other):
            dy = o[2] - n[2]
            dxx = abs(o[1] - n[1])
            # the generator centres the label exactly above the number (same x, about 1.7 text heights up)
            if 0 < dy < 2.5 * n[3] and dxx < 0.02:
                d = dy + dxx
                if d < bd:
                    best, bd = i, d
        label = other[best][0] if best is not None else None
        if best is not None:
            used.add(best)
        pt = Point(n[1], n[2])
        cand = [p for p in polys if p.contains(pt)]
        if not cand:
            cand = sorted(polys, key=lambda p: p.distance(pt))[:1]
        poly = min(cand, key=lambda p: p.area) if cand else None
        rooms.append({"num": n[0], "label": label, "area": round(poly.area, 4) if poly else None, "x": n[1], "y": n[2], "_poly": poly})
    f["other_texts_unpaired"] = [o[0] for i, o in enumerate(other) if i not in used]
    # unlabelled polygons (no number inside)
    numbered = {id(r["_poly"]) for r in rooms}
    f["unnumbered_poly_areas"] = sorted(round(p.area, 3) for p in polys if id(p) not in numbered)
    # units
    unit_polys = []
    for e in ents["UNIT_OUTLINE"]:
        if e.dxftype() == "LWPOLYLINE":
            p = pts(e)
            if len(p) >= 3:
                unit_polys.append(Polygon(p).buffer(0))
    f["n_unit_polys"] = len(unit_polys)
    ut = []
    for t in units_t:
        pt = Point(t[1], t[2])
        cand = [i for i, p in enumerate(unit_polys) if p.contains(pt)]
        ut.append((UNIT.match(t[0]).group(2), cand[0] if cand else None))
    for r in rooms:
        pt = Point(r["x"], r["y"])
        idx = [i for i, p in enumerate(unit_polys) if p.contains(pt)]
        if not idx and r["_poly"] is not None:
            # fall back to the unit with the largest overlap
            ov = [(p.intersection(r["_poly"]).area, i) for i, p in enumerate(unit_polys)]
            ov = [o for o in ov if o[0] > 0.5 * r["_poly"].area]
            idx = [max(ov)[1]] if ov else []
        letters = [u[0] for u in ut if u[1] in idx]
        r["unit"] = letters[0] if letters else None
        r["unit_idx"] = idx[0] if idx else None
        del r["_poly"]
    f["rooms"] = rooms
    f["unit_labels"] = ut
    f["unit_poly_areas"] = [round(p.area, 3) for p in unit_polys]
    # doors and windows
    def sig_counts(layer):
        return dict(collections.Counter(
            f"{e.dxftype()}{len(pts(e)) if e.dxftype() == 'LWPOLYLINE' else ''}{'c' if e.dxftype() == 'LWPOLYLINE' and e.closed else ''}" for e in ents[layer]))
    f["door_sig"] = sig_counts("DOOR")
    f["window_sig"] = sig_counts("WINDOW")
    arcs = {(round(e.dxf.center.x, 3), round(e.dxf.center.y, 3), round(e.dxf.radius, 3)) for e in ents["DOOR"] if e.dxftype() == "ARC"}
    f["door_unique_arcs"] = len(arcs)
    # fixtures: outer boxes = closed 4-pt polylines not inside another closed 4-pt polyline
    fx = []
    for e in ents["FIXTURE"]:
        t = e.dxftype()
        if t == "LWPOLYLINE":
            p = pts(e)
            xs, ys = [q[0] for q in p], [q[1] for q in p]
            fx.append({"t": f"P{len(p)}", "closed": bool(e.closed), "bb": (min(xs), min(ys), max(xs), max(ys)), "pts": p})
        elif t == "CIRCLE":
            c, r = e.dxf.center, e.dxf.radius
            fx.append({"t": f"C{round(r, 2)}", "closed": True, "bb": (c.x - r, c.y - r, c.x + r, c.y + r)})
        else:
            fx.append({"t": t, "closed": False, "bb": None})
    rects = [i for i, e in enumerate(fx) if e["t"] == "P4"]
    def inside(a, b, tol=0.02):
        return a[0] >= b[0] - tol and a[1] >= b[1] - tol and a[2] <= b[2] + tol and a[3] <= b[3] + tol
    outer = [i for i in rects if not any(j != i and inside(fx[i]["bb"], fx[j]["bb"], 0.0) and fx[j]["bb"] != fx[i]["bb"] for j in rects)]
    # dedupe identical outer boxes
    seen, outer2 = set(), []
    for i in outer:
        k = tuple(round(v, 3) for v in fx[i]["bb"])
        if k not in seen:
            seen.add(k)
            outer2.append(i)
    groups = []
    for i in outer2:
        bb = fx[i]["bb"]
        inner = [fx[j]["t"] for j in range(len(fx)) if j != i and fx[j]["bb"] and inside(fx[j]["bb"], bb) and tuple(round(v, 3) for v in fx[j]["bb"]) != tuple(round(v, 3) for v in bb)]
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        groups.append({"sig": "+".join(sorted(inner)), "w": round(max(w, h), 2), "h": round(min(w, h), 2), "cx": round((bb[0] + bb[2]) / 2, 2), "cy": round((bb[1] + bb[3]) / 2, 2)})
    f["fixtures"] = groups
    f["fixture_entity_types"] = dict(collections.Counter(e["t"] for e in fx))
    return f


def main():
    files = sorted(D.glob("*.dxf"))
    if len(sys.argv) > 1:
        files = files[: int(sys.argv[1])]
    res = {}
    for p in files:
        try:
            res[p.stem] = floor_features(p)
        except Exception as ex:  # keep going, record the error
            res[p.stem] = {"error": repr(ex)}
    json.dump(res, open(OUT / "dxf_features.json", "w"), ensure_ascii=False)
    print("floors", len(res), "errors", sum("error" in v for v in res.values()))


if __name__ == "__main__":
    main()
