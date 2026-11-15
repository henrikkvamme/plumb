# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Do reference counts follow raw source rows (with duplicate geometry) or distinct objects on the sheet?

For each count family, compare the reference with (a) the raw number of source rows and (b) the number of
distinct geometries. A gap means the drawing shows fewer distinct objects than the answer says
(objects drawn twice on top of each other). Writes duplicates.json.
Usage: uv run duplicates.py   (needs source_subset.py and templates.py outputs)
"""
import csv, sys, json, pathlib, collections

csv.field_size_limit(sys.maxsize)
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "data/external/swiss-derived"
FAM = {
    "doors": ("opening", {"DOOR", "ENTRANCE_DOOR"}, "How many doors"),
    "windows": ("opening", {"WINDOW"}, "How many windows"),
    "toilets": ("feature", {"TOILET"}, "How many toilets"),
    "washbasins": ("feature", {"SINK"}, "How many washbasins"),
    "bathtubs": ("feature", {"BATHTUB"}, "How many bathtubs"),
    "showers": ("feature", {"SHOWER"}, "How many showers"),
}
raw = {k: collections.Counter() for k in FAM}
ded = {k: collections.defaultdict(set) for k in FAM}
for r in csv.DictReader(open(OUT / "source_rows.csv")):
    for k, (et, st, _) in FAM.items():
        if r["entity_type"] == et and r["entity_subtype"] in st:
            raw[k][r["floor_id"]] += 1
            ded[k][r["floor_id"]].add(r["geometry"])
rows = json.load(open(OUT / "rows.json"))
res = {}
for k, (_, _, prefix) in FAM.items():
    ref = {r["path"].split("floor")[1].split(".")[0]: r["answer"] for r in rows if r["question"].startswith(prefix)}
    a = sum(raw[k][f] == v for f, v in ref.items())
    b = sum(len(ded[k][f]) == v for f, v in ref.items())
    gap = [(f, v, len(ded[k][f])) for f, v in ref.items() if len(ded[k][f]) != v]
    res[k] = {"floors": len(ref), "ref_equals_raw_rows": a, "ref_equals_distinct_geometry": b,
              "floors_where_distinct_differs": len(gap), "extra_total": sum(v - d for _, v, d in gap),
              "examples": gap[:5]}
    print(k, {x: y for x, y in res[k].items() if x != "examples"})
json.dump(res, open(OUT / "duplicates.json", "w"), indent=1)
