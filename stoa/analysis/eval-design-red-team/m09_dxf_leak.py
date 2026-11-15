"""How much does the DXF sibling give away? Trivial layer counts and shoelace areas vs the reference answers.
This measures the size of the sibling-format leak and the noise floor of the reference. It is not a solver."""
import sys, collections, random, re, ezdxf, os
from common import *
it = [x for x in items() if x["source"]=="swiss_dwellings" and x["lang"]=="en"]
byf = collections.defaultdict(list)
for x in it: byf[x["path"]].append(x)
random.seed(11); files = random.sample(sorted(byf), int(sys.argv[1]) if len(sys.argv)>1 else 150)
def area(pl):
    pts = [(p[0],p[1]) for p in pl.get_points()]; a = 0
    for (x1,y1),(x2,y2) in zip(pts, pts[1:]+pts[:1]): a += x1*y2-x2*y1
    return abs(a)/2
stat = collections.defaultdict(lambda: [0,0]); relerr = []
first = True
for f in files:
    d = ezdxf.readfile(ROOT + "/" + f[:-4] + ".dxf"); ms = d.modelspace()
    c = collections.Counter((e.dxf.layer, e.dxftype()) for e in ms)
    rooms = [e for e in ms if e.dxf.layer=="ROOM_OUTLINE" and e.dxftype()=="LWPOLYLINE"]
    units = [e for e in ms if e.dxf.layer=="UNIT_OUTLINE"]
    texts = [(e.dxf.text, e.dxf.insert) for e in ms if e.dxftype()=="TEXT" and e.dxf.layer=="ROOM_TEXT"]
    cand = {"windows": [c[("WINDOW","LWPOLYLINE")], c[("WINDOW","LWPOLYLINE")]/3], "doors": [c[("DOOR","ARC")], c[("DOOR","LWPOLYLINE")], c[("DOOR","LWPOLYLINE")]-c[("DOOR","ARC")]],
            "apartments": [len(units)]}
    for x in byf[f]:
        q = x["family"]
        k = "windows" if "windows" in q else "doors" if "doors" in q else "apartments" if "apartments" in q else None
        if k:
            for j, v in enumerate(cand[k]): stat[(k,j)][0] += (v == x["answer"]); stat[(k,j)][1] += 1
        if q.startswith("How many rooms labelled"):
            lab = re.search(r"labelled '(.*)' are", x["question"]).group(1)
            stat[("rooms_labelled",0)][0] += (sum(1 for t,_ in texts if t==lab) == x["answer"]); stat[("rooms_labelled",0)][1] += 1
        if "all numbered indoor rooms" in q:
            tot = sum(area(r) for r in rooms)
            for j, v in enumerate([tot, tot/2]):
                stat[("floor_area_all_outlines",j)][0] += abs(v-x["answer"])<=0.02*x["answer"]; stat[("floor_area_all_outlines",j)][1] += 1
    if first:
        first = False; print("example", f, dict(c)); print("  rooms", len(rooms), "areas", sorted(round(area(r),2) for r in rooms)[:12])
        for x in byf[f]: print("   ", x["question"][:70], x["answer"])
for k, (h, n) in sorted(stat.items()): print("RESULT_"+k[0]+"_variant"+str(k[1])+"_hits"+str(h)+"_of"+str(n))
