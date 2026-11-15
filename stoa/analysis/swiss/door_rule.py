# /// script
# requires-python = ">=3.11"
# dependencies = ["ezdxf", "shapely"]
# ///
"""Can a solver that sees only distinct doors (a raster or a person) recover the reference door count?

The reference counts a door once per unit that lists it (an apartment entrance door counts twice: once
for the apartment, once for the public stair hall). Test drawing-visible rules on the DXF:
  distinct      : distinct door openings (what a person counts)
  unit_crossing : each distinct door counts 1 + the number of apartment outlines (red dash-dot) it crosses
Same for windows. Writes door_rule.json.
Usage: uv run door_rule.py
"""
import json, pathlib, collections
import ezdxf
from shapely.geometry import Polygon

ROOT = pathlib.Path(__file__).resolve().parents[2]
D = ROOT / "data/junction-dataset/data/swiss_dwellings"
OUT = ROOT / "data/external/swiss-derived"
rows = json.load(open(OUT / "rows.json"))
ref = collections.defaultdict(dict)
for r in rows:
    fl = pathlib.Path(r["path"]).stem
    if r["question"].startswith("How many doors"):
        ref[fl]["doors"] = r["answer"]
    if r["question"].startswith("How many windows"):
        ref[fl]["windows"] = r["answer"]

res = {k: collections.Counter() for k in ("doors", "windows")}
ex = collections.defaultdict(list)
for fl, rr in sorted(ref.items()):
    dx = ezdxf.readfile(D / f"{fl}.dxf")
    msp = dx.modelspace()
    units = [Polygon([p[:2] for p in e.get_points()]).buffer(0).boundary for e in msp.query("LWPOLYLINE[layer=='UNIT_OUTLINE']")]
    for fam, layer, npts in (("doors", "DOOR", 5), ("windows", "WINDOW", 4)):
        geoms = {}
        for e in msp.query(f"LWPOLYLINE[layer=='{layer}']"):
            p = [tuple(round(c, 4) for c in q[:2]) for q in e.get_points()]
            if len(p) == npts and (fam == "doors" or e.closed):
                geoms[tuple(sorted(p))] = Polygon(p).buffer(0.02)
        distinct = len(geoms)
        crossing = sum(1 + sum(1 for u in units if g.intersects(u)) for g in geoms.values())
        res[fam]["n"] += 1
        res[fam]["distinct_ok"] += distinct == rr[fam]
        res[fam]["crossing_ok"] += crossing == rr[fam]
        res[fam]["ref_total"] += rr[fam]
        res[fam]["distinct_total"] += distinct
        if crossing != rr[fam] and len(ex[fam]) < 5:
            ex[fam].append((fl, rr[fam], distinct, crossing))
out = {k: dict(v) for k, v in res.items()}
out["examples"] = ex
json.dump(out, open(OUT / "door_rule.json", "w"), indent=1)
print(json.dumps(out))
