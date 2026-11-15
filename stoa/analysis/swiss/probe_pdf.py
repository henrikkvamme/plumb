# /// script
# requires-python = ">=3.11"
# dependencies = ["pymupdf", "shapely"]
# ///
"""Probe: answer swiss_dwellings questions from the PDF alone (pymupdf vector paths and text, no DXF).

Scale comes from the title block text ("1:100 (A3)"), checked against the scale bar.
Rooms: filled paths with a grey (0.54) 0.37 pt stroke. Labels: the span centred above a room number.
Apartments: "Whg. X" / "App. X" tags and the red dash-dot unit outline. Doors: grey (0.27) quads.
Fixtures and windows: white boxes with a black 0.51 pt stroke, classified by what is drawn inside them.
Writes pdf_features.json and probe_pdf.json.
Usage: uv run probe_pdf.py [n_floors]   (needs templates.py output rows.json)
"""
import sys, re, json, pathlib, collections, math
import pymupdf
from shapely.geometry import Polygon, Point

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from qparse import parse, OUTDOOR

ROOT = pathlib.Path(__file__).resolve().parents[2]
D = ROOT / "data/junction-dataset/data/swiss_dwellings"
OUT = ROOT / "data/external/swiss-derived"
NUM = re.compile(r"^(U\d+\.)?\d+\.\d+$|^U\d+\.\d+$")
UNIT = re.compile(r"^(Whg\.|App\.)\s*([A-Z]+)$")



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

def near(c, ref, tol=0.02):
    return c is not None and all(abs(a - b) < tol for a, b in zip(c, ref))


def path_points(d):
    pts = []
    for it in d["items"]:
        if it[0] == "l":
            pts += [it[1], it[2]]
        elif it[0] == "re":
            r = it[1]
            pts += [r.tl, r.tr, r.br, r.bl]
        elif it[0] == "qu":
            q = it[1]
            pts += [q.ul, q.ur, q.lr, q.ll]
        elif it[0] == "c":
            pts += [it[1], it[4]]
    out = []
    for p in pts:
        if not out or abs(p.x - out[-1][0]) > 1e-6 or abs(p.y - out[-1][1]) > 1e-6:
            out.append((p.x, p.y))
    return out


def floor_features(path):
    pg = pymupdf.open(path)[0]
    spans = []
    for b in pg.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                x0, y0, x1, y1 = s["bbox"]
                spans.append((s["text"].strip(), (x0 + x1) / 2, (y0 + y1) / 2, s["size"], y0))
    f = {"page": [round(pg.rect.width), round(pg.rect.height)]}
    # the title block band starts about 45 pt above the span that holds the scale ("1:100 (A3)")
    ys = [s[4] for s in spans if re.search(r"1:\d+ \(A\d\)", s[0])]
    cut = (ys[0] - 45) if ys else pg.rect.height * 0.82
    f["title_cut_pt"] = round(cut, 1)
    # scale from the title block, verified with the scale bar ticks "0" and "5"
    sc = [int(m.group(1)) for t, *_ in spans for m in [re.search(r"1:(\d+)", t)] if m]
    scale = sc[0] if sc else None
    f["scale_text"] = scale
    zero = [s for s in spans if s[0] == "0" and s[4] > cut]
    five = [s for s in spans if s[0] in ("5", "10") and s[4] > cut]
    f["scalebar_pt_per_m"] = round((five[0][1] - zero[0][1]) / float(five[0][0]), 3) if zero and five else None
    mpp = 0.0254 / 72 * scale if scale else None
    f["m_per_pt"] = mpp
    plan = [s for s in spans if s[4] < cut]
    nums = [s for s in plan if NUM.match(s[0])]
    units = [s for s in plan if UNIT.match(s[0])]
    others = [s for s in plan if not NUM.match(s[0]) and not UNIT.match(s[0])]
    drs = pg.get_drawings()
    rooms_poly, unit_polys, boxes, inner, doors = [], [], [], [], 0
    boxpts, linepts = {}, {}
    room_fill = []
    for d in drs:
        if d["rect"].y0 > cut:
            continue
        col, fill, w = d.get("color"), d.get("fill"), d.get("width") or 0
        kinds = collections.Counter(it[0] for it in d["items"])
        if near(col, (0.54, 0.54, 0.54), 0.01) and abs(w - 0.3685) < 0.01 and fill is not None:
            p = path_points(d)
            if len(p) >= 3:
                rooms_poly.append(Polygon(p).buffer(0))
                room_fill.append(round(fill[0], 2))
        elif near(col, (0.69, 0.23, 0.18), 0.01):
            p = path_points(d)
            if len(p) >= 3:
                unit_polys.append(Polygon(p).buffer(0))
        elif near(col, (0.27, 0.27, 0.27), 0.01) and kinds.get("qu"):
            doors += 1
        elif near(fill, (1, 1, 1)) and near(col, (0, 0, 0)) and abs(w - 0.51) < 0.01 and (kinds.get("re") or kinds.get("l") == 4):
            boxes.append(d["rect"])
            boxpts[len(boxes) - 1] = path_points(d)
        elif fill is None and near(col, (0, 0, 0)):
            if kinds.get("c") == 8:
                r = d["rect"].width / 2 * (mpp or 0.0352778)
                inner.append((f"C{r:.3f}", d["rect"]))
            elif kinds.get("qu"):
                inner.append(("Q", d["rect"]))
            elif kinds.get("l"):
                inner.append((f"L{kinds['l']}w{w:.2f}", d["rect"]))
                if kinds["l"] == 1:
                    seg = [it for it in d["items"] if it[0] == "l"][0]
                    linepts[len(inner) - 1] = ((seg[1].x, seg[1].y), (seg[2].x, seg[2].y))
    f["doors_quads"] = doors
    rooms_poly = net_holes(rooms_poly)
    # fixture and window boxes
    groups = []
    mult = collections.Counter(tuple(round(v, 1) for v in b) for b in boxes)
    seen = set()
    for bi, b in enumerate(boxes):
        k = tuple(round(v, 1) for v in b)
        if k in seen:
            continue
        seen.add(k)
        inr = [(i, t, r) for i, (t, r) in enumerate(inner) if r.x0 >= b.x0 - 0.3 and r.y0 >= b.y0 - 0.3 and r.x1 <= b.x1 + 0.3 and r.y1 <= b.y1 + 0.3]
        ins = [t for i, t, r in inr]
        # window glass lines: thin lines parallel to the long side of the (possibly rotated) box, spanning it
        bp = boxpts.get(bi, [])
        glass = 0
        if len(bp) >= 4:
            e1 = (bp[1][0] - bp[0][0], bp[1][1] - bp[0][1])
            e2 = (bp[2][0] - bp[1][0], bp[2][1] - bp[1][1])
            ax = e1 if math.hypot(*e1) >= math.hypot(*e2) else e2
            L = math.hypot(*ax)
            for i, t, r in inr:
                if t != "L1w0.37" or i not in linepts or L == 0:
                    continue
                (x0, y0), (x1, y1) = linepts[i]
                v = (x1 - x0, y1 - y0)
                lv = math.hypot(*v)
                if lv > 0.9 * L and abs(v[0] * ax[1] - v[1] * ax[0]) / (lv * L) < 0.02:
                    glass += 1
        groups.append({"sig": "+".join(sorted(ins)), "mult": mult[k], "glass": glass, "w": round(max(b.width, b.height) * (mpp or 0), 2), "h": round(min(b.width, b.height) * (mpp or 0), 2)})
    f["fixtures"] = groups
    # rooms
    rooms = []
    for n in nums:
        cand = [o for o in others if abs(o[1] - n[1]) < 1.0 and 0 < n[2] - o[2] < 2.5 * n[3]]
        label = min(cand, key=lambda o: n[2] - o[2])[0] if cand else None
        pt = Point(n[1], n[2])
        cp = [p for p in rooms_poly if p.contains(pt)]
        poly = min(cp, key=lambda p: p.area) if cp else None
        fillv = room_fill[rooms_poly.index(poly)] if poly is not None else None
        ui = [i for i, u in enumerate(unit_polys) if u.contains(pt)]
        rooms.append({"num": n[0], "label": label, "area": round(poly.area * mpp * mpp, 4) if poly is not None and mpp else None, "fill": fillv, "unit_idx": ui[0] if ui else None})
    ut = {}
    for u in units:
        ui = [i for i, p in enumerate(unit_polys) if p.contains(Point(u[1], u[2]))]
        if ui:
            ut[ui[0]] = UNIT.match(u[0]).group(2)
    for r in rooms:
        r["unit"] = ut.get(r.pop("unit_idx"))
    f["rooms"] = rooms
    f["unit_texts"] = [u[0] for u in units]
    f["n_unit_polys"] = len(unit_polys)
    f["printed_m2"] = [s[0] for s in plan if s[0].endswith("m²")]
    return f


def fx(f, pred):
    return sum(1 for g in f["fixtures"] if pred(g["sig"]))


def drain(s):
    return any(t.startswith("C") and float(t[1:]) < 0.06 for t in s.split("+"))


def outdoor(r):
    # outdoor rooms are filled darker grey (0.89); small balconies often carry no name on the sheet
    return r["label"] in OUTDOOR or r.get("fill") == 0.89


def tot(f):
    return round(sum(r["area"] for r in f["rooms"] if r["area"] and not outdoor(r)), 2)


def apt(f, letter):
    a = [r["area"] for r in f["rooms"] if r["unit"] == letter and not outdoor(r) and r["area"]]
    return round(sum(a), 2) if a else None


PRED = {
    "count_label": lambda f, p: sum(1 for r in f["rooms"] if r["label"] == p),
    "apartments": lambda f, p: len(f["unit_texts"]),
    "doors": lambda f, p: f["doors_quads"],
    # a window is a white box holding only two thin lines; the generator stacks a second copy of a window
    # that two units share, so a box drawn m times holds 2m lines and counts m times
    "windows": lambda f, p: sum(g["mult"] for g in f["fixtures"] if g["glass"] >= 2 * g["mult"]),
    "toilets": lambda f, p: fx(f, lambda s: "L47w0.51" in s and "L1w0.51" in s and not drain(s)),
    "washbasins": lambda f, p: fx(f, lambda s: "L47w0.51" in s and drain(s)),
    "bathtubs": lambda f, p: fx(f, lambda s: "L68w0.51" in s),
    "showers": lambda f, p: fx(f, lambda s: "Q" in s and drain(s)),
    "area_room": lambda f, p: next((r["area"] for r in f["rooms"] if r["num"] == p), None),
    "area_label": lambda f, p: round(sum(r["area"] for r in f["rooms"] if r["label"] == p and r["area"]), 2),
    "area_total": lambda f, p: tot(f),
    "area_apartment": lambda f, p: apt(f, p),
}


def ok(pred, ans, typ):
    if pred is None:
        return False
    if typ == "count":
        return int(round(pred)) == int(ans)
    return abs(pred - ans) <= 0.02 * abs(ans) + 1e-9


def main():
    rows = json.load(open(OUT / "rows.json"))
    floors = sorted({pathlib.Path(r["path"]).stem for r in rows})
    if len(sys.argv) > 1:
        floors = floors[: int(sys.argv[1])]
    feats = {}
    for fl in floors:
        try:
            feats[fl] = floor_features(D / f"{fl}.pdf")
        except Exception as ex:
            feats[fl] = {"error": repr(ex)}
    json.dump(feats, open(OUT / "pdf_features.json", "w"), ensure_ascii=False)
    res = collections.defaultdict(lambda: [0, 0])
    fails = collections.defaultdict(list)
    for r in rows:
        fl = pathlib.Path(r["path"]).stem
        if fl not in feats or "error" in feats[fl]:
            continue
        fam, p, lang = parse(r["question"])
        try:
            pred = PRED[fam](feats[fl], p)
        except Exception:
            pred = None
        g = ok(pred, r["answer"], r["type"])
        res[fam][0] += g
        res[fam][1] += 1
        if not g and len(fails[fam]) < 8:
            fails[fam].append({"floor": fl, "q": r["question"][:80], "ref": r["answer"], "pred": pred})
    a = sum(v[0] for v in res.values())
    n = sum(v[1] for v in res.values())
    sig = collections.Counter(g["sig"] for f in feats.values() for g in f.get("fixtures", []))
    scales = collections.Counter((f.get("scale_text"), f.get("scalebar_pt_per_m")) for f in feats.values())
    out = {"floors": len(feats), "errors": sum("error" in f for f in feats.values()), "overall": round(a / n, 4), "n": n,
           "families": {k: {"agree": v[0], "n": v[1], "rate": round(v[0] / v[1], 4)} for k, v in res.items()},
           "fixture_signatures": sig.most_common(30), "scales": [[str(k), v] for k, v in scales.most_common()],
           "floors_with_printed_m2": sum(1 for f in feats.values() if f.get("printed_m2")),
           "disagreements": fails}
    json.dump(out, open(OUT / "probe_pdf.json", "w"), indent=1, ensure_ascii=False)
    print("floors", out["floors"], "errors", out["errors"], "overall", out["overall"], "n", n)
    for k, v in out["families"].items():
        print(k, v["rate"], v["n"])
    print("scales", out["scales"][:5])


if __name__ == "__main__":
    main()
