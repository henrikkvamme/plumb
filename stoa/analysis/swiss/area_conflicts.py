# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Where the drawing-based answer misses the reference, does the public source explain the reference?

For apartment-area and floor-total questions: compare the reference with (a) the DXF probe and (b) sums of
public source areas. "drawing_conflict" = the source reproduces the reference but the drawn rooms do not:
the answer follows the source data, not what the sheet shows. Also lists which source subtypes the
apartment-area reference includes. Writes area_conflicts.json.
Usage: uv run area_conflicts.py
"""
import json, pathlib, collections, sys, itertools

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from qparse import parse, OUTDOOR

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "data/external/swiss-derived"
F = json.load(open(OUT / "dxf_features.json"))
S = json.load(open(OUT / "source_floor.json"))
rows = json.load(open(OUT / "rows.json"))
SRC_OUT = {"BALCONY", "LOGGIA", "TERRACE", "GARDEN", "PATIO", "OUTDOOR_VOID", "ARCADE"}
NONROOM = {"SHAFT", "VOID", "LIGHTWELL"}


def close(a, b):
    return a is not None and abs(a - b) <= 0.02 * abs(b)


res = collections.Counter()
ex = collections.defaultdict(list)
for r in rows:
    fam, p, lang = parse(r["question"])
    if fam not in ("area_apartment", "area_total") or lang != "en":
        continue
    fl = pathlib.Path(r["path"]).stem
    f, s = F[fl], S[fl.split("floor")[1]]
    ans = r["answer"]
    if fam == "area_total":
        dxf = sum(x["area"] for x in f["rooms"] if x["area"] and x["label"] not in OUTDOOR)
        src = [sum(a for sub, a, u, uu in s["areas"] if sub not in SRC_OUT | NONROOM)]
    else:
        rs = [x["area"] for x in f["rooms"] if x["unit"] == p and x["area"] and x["label"] not in OUTDOOR]
        dxf = sum(rs) if rs else None
        units = collections.defaultdict(float)
        units_sh = collections.defaultdict(float)
        for sub, a, u, uu in s["areas"]:
            if u and sub not in SRC_OUT:
                units_sh[u] += a
                if sub not in NONROOM:
                    units[u] += a
        src = list(units.values())
        res["apt_ref_matches_unit_without_shafts"] += any(close(v, ans) for v in units.values())
        res["apt_ref_matches_unit_with_shafts"] += any(close(v, ans) for v in units_sh.values())
    d_ok = close(dxf, ans)
    s_ok = any(close(v, ans) for v in src)
    res[f"{fam}_n"] += 1
    res[f"{fam}_dxf_ok"] += d_ok
    res[f"{fam}_src_ok"] += s_ok
    if not d_ok and s_ok:
        res[f"{fam}_drawing_conflict"] += 1
        if len(ex[fam]) < 5:
            ex[fam].append({"floor": fl, "param": p, "ref": ans, "dxf": round(dxf, 2) if dxf else None})
    if not d_ok and not s_ok:
        res[f"{fam}_neither"] += 1
out = {"counts": dict(res), "examples": ex}
json.dump(out, open(OUT / "area_conflicts.json", "w"), indent=1)
print(json.dumps(out["counts"]))
