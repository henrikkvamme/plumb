"""Does the sibling DXF reproduce the reference answers? Sample of Swiss floors.
Room area: ROOM_OUTLINE polygon that contains the ROOM_TEXT number. Counts: entities on DOOR / WINDOW layers."""
import json, re, collections, random, sys, math
import ezdxf
from shapely.geometry import Polygon, Point
ROOT = "./stoa/data/junction-dataset"
rows = [json.loads(l) for l in open(f"{ROOT}/questions.jsonl", encoding="utf-8") if l.strip()]
sw = collections.defaultdict(list)
for r in rows:
    if "/swiss_dwellings/" in r["path"]: sw[r["path"]].append(r)
random.seed(7)
paths = random.sample(sorted(sw), int(sys.argv[1]) if len(sys.argv) > 1 else 60)
st = collections.Counter(); relerr = []
for p in paths:
    d = ezdxf.readfile(f"{ROOT}/{p[:-4]}.dxf"); msp = d.modelspace()
    polys = []
    for e in msp.query('LWPOLYLINE[layer=="ROOM_OUTLINE"]'):
        pts = [(x, y) for x, y, *_ in e.get_points()]
        if len(pts) >= 3: polys.append(Polygon(pts).buffer(0))
    texts = [(e.dxf.text.strip(), Point(e.dxf.insert.x, e.dxf.insert.y)) for e in msp.query('TEXT[layer=="ROOM_TEXT"]')]
    num = {}
    for t, pt in texts:
        if re.fullmatch(r"U?\d+\.\d+", t):
            cands = [pl for pl in polys if pl.contains(pt)]
            if not cands: cands = sorted(polys, key=lambda pl: pl.distance(pt))[:1]
            num[t] = min(cands, key=lambda pl: pl.area)
    for r in sw[p]:
        m = re.search(r"(?:room|Raum|pièce|locale) (U?\d+\.\d+) ", r["question"])
        if m and r["type"] == "area":
            st["room_q"] += 1
            pl = num.get(m.group(1))
            if pl is None: st["room_nomatch"] += 1; continue
            e = abs(pl.area - r["answer"]) / r["answer"]; relerr.append(e)
            st["room_within_2pct"] += e <= 0.02; st["room_within_0.5pct"] += e <= 0.005
            st["room_equal_after_round2"] += round(pl.area, 2) == r["answer"]
        if re.match(r"How many windows", r["question"]):
            st["win_q"] += 1; st["win_eq_layer_polylines"] += len(msp.query('LWPOLYLINE[layer=="WINDOW"]')) == r["answer"]
            st["win_eq_third"] += len(msp.query('LWPOLYLINE[layer=="WINDOW"]')) == 3 * r["answer"]
        if re.match(r"How many doors", r["question"]):
            st["door_q"] += 1; st["door_eq_arcs"] += len(msp.query('ARC[layer=="DOOR"]')) == r["answer"]
            st["door_arcs_ge"] += len(msp.query('ARC[layer=="DOOR"]')) >= r["answer"]
        if re.match(r"How many apartments", r["question"]):
            st["apt_q"] += 1; st["apt_eq_unit_outlines"] += len(msp.query('LWPOLYLINE[layer=="UNIT_OUTLINE"]')) == r["answer"]
print("floors", len(paths), dict(st))
relerr.sort()
if relerr: print("room relerr med", round(relerr[len(relerr)//2], 5), "p95", round(relerr[int(.95*len(relerr))], 5), "max", round(relerr[-1], 4))
