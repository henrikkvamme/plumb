# /// script
# requires-python = ">=3.11"
# dependencies = ["shapely"]
# ///
"""Leakage probe: answer swiss_dwellings questions from the PUBLIC Swiss Dwellings v3.0.0 geometry alone.

No drawing is opened. The floor id in the file name selects the source rows (source_subset.py writes them).
This shows how far a lookup in public data goes, and which convention the generator used.
Room-level questions need the synthetic room number, so this probe covers counts, the floor total and
apartment count only. Writes source_floor.json and probe_source.json.
Usage: uv run probe_source.py
"""
import csv, json, pathlib, collections, sys
from shapely import wkt

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from qparse import parse

csv.field_size_limit(sys.maxsize)
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "data/external/swiss-derived"
rows = json.load(open(OUT / "rows.json"))

OUTDOOR = {"BALCONY", "LOGGIA", "TERRACE", "GARDEN", "PATIO", "OUTDOOR_VOID", "ARCADE"}
NONROOM = {"SHAFT", "VOID", "LIGHTWELL"}

fl = collections.defaultdict(lambda: {"feat": collections.Counter(), "open": collections.Counter(), "areas": [], "units": set(), "seen": set()})
for r in csv.DictReader(open(OUT / "source_rows.csv")):
    key = (r["entity_type"], r["entity_subtype"], r["geometry"][:200])
    f = fl[r["floor_id"]]
    if key in f["seen"]:  # the CSV repeats public areas for each apartment
        continue
    f["seen"].add(key)
    if r["unit_id"]:
        f["units"].add((r["unit_id"], r["unit_usage"]))
    if r["entity_type"] == "feature":
        f["feat"][r["entity_subtype"]] += 1
    elif r["entity_type"] == "opening":
        f["open"][r["entity_subtype"]] += 1
    elif r["entity_type"] == "area":
        g = wkt.loads(r["geometry"])
        f["areas"].append((r["entity_subtype"], round(g.area, 4), r["unit_id"], r["unit_usage"]))

floor_out = {}
for k, f in fl.items():
    floor_out[k] = {"feat": dict(f["feat"]), "open": dict(f["open"]), "areas": f["areas"], "units": sorted(f["units"])}
json.dump(floor_out, open(OUT / "source_floor.json", "w"))


def tot(f, excl):
    return round(sum(a for s, a, u, uu in f["areas"] if s not in excl), 2)


V = {
    "apartments": {
        "residential_units": lambda f: sum(1 for u, uu in f["units"] if uu == "RESIDENTIAL"),
        "all_units": lambda f: len(f["units"]),
    },
    "doors": {"DOOR+ENTRANCE_DOOR": lambda f: f["open"].get("DOOR", 0) + f["open"].get("ENTRANCE_DOOR", 0)},
    "windows": {"WINDOW": lambda f: f["open"].get("WINDOW", 0)},
    "toilets": {"TOILET": lambda f: f["feat"].get("TOILET", 0)},
    "washbasins": {"SINK": lambda f: f["feat"].get("SINK", 0)},
    "bathtubs": {"BATHTUB": lambda f: f["feat"].get("BATHTUB", 0)},
    "showers": {"SHOWER": lambda f: f["feat"].get("SHOWER", 0)},
    "area_total": {
        "minus_outdoor_shaft_void": lambda f: tot(f, OUTDOOR | NONROOM),
        "minus_outdoor_only": lambda f: tot(f, OUTDOOR),
        "all": lambda f: tot(f, set()),
    },
}


def ok(pred, ans, typ):
    if pred is None:
        return False
    if typ == "count":
        return int(round(pred)) == int(ans)
    return abs(pred - ans) <= 0.02 * abs(ans) + 1e-9


res = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
fails = collections.defaultdict(list)
for r in rows:
    fam, p, lang = parse(r["question"])
    if fam not in V or lang != "en":  # local-language duplicates give the same answer; checked in contradictions.py
        continue
    fid = r["path"].split("floor")[1].split(".")[0]
    f = floor_out[fid]
    for i, (vn, fn) in enumerate(V[fam].items()):
        pred = fn(f)
        g = ok(pred, r["answer"], r["type"])
        res[fam][vn][0] += g
        res[fam][vn][1] += 1
        if i == 0 and not g and len(fails[fam]) < 8:
            fails[fam].append({"floor": r["path"].split("/")[-1], "ref": r["answer"], "pred": pred})
out = {fam: {vn: {"agree": a, "n": n, "rate": round(a / n, 4)} for vn, (a, n) in v.items()} for fam, v in res.items()}
json.dump({"families": out, "disagreements": fails}, open(OUT / "probe_source.json", "w"), indent=1)
for fam, v in out.items():
    print(fam, {k: x["rate"] for k, x in v.items()})
