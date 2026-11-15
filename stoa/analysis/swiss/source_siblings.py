# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""How big is the pool the hidden set could come from, and how alike are floors of one building?

Scans the full public Swiss Dwellings v3.0.0 geometries.csv and builds one answer vector per floor
(the generator's conventions: raw door/window rows, TOILET, SINK, BATHTUB, SHOWER, residential units).
Reports: floors, buildings and sites in the source; sibling floors of our 1,040 floors; how often a sibling
floor of the same building has the identical answer for each family. Writes source_siblings.json.
Usage: uv run source_siblings.py
"""
import csv, sys, json, pathlib, collections, re, itertools, random

csv.field_size_limit(sys.maxsize)
ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "data/external/swiss-dwellings-v3/swiss-dwellings-v3.0.0/geometries.csv"
D = ROOT / "data/junction-dataset/data/swiss_dwellings"
OUT = ROOT / "data/external/swiss-derived"

FAM = {"doors": ("opening", ("DOOR", "ENTRANCE_DOOR")), "windows": ("opening", ("WINDOW",)), "toilets": ("feature", ("TOILET",)),
       "washbasins": ("feature", ("SINK",)), "bathtubs": ("feature", ("BATHTUB",)), "showers": ("feature", ("SHOWER",))}
vec = collections.defaultdict(collections.Counter)
units = collections.defaultdict(set)
meta = {}
for r in csv.DictReader(open(SRC, newline="")):
    fl = r["floor_id"]
    meta[fl] = (r["site_id"], r["building_id"])
    if r["unit_usage"] == "RESIDENTIAL" and r["unit_id"]:
        units[fl].add(r["unit_id"])
    for k, (et, st) in FAM.items():
        if r["entity_type"] == et and r["entity_subtype"] in st:
            vec[fl][k] += 1
for fl in meta:
    vec[fl]["apartments"] = len(units[fl])

ours = {re.search(r"floor(\d+)", p.stem).group(1) for p in D.glob("*.pdf")}
by_b = collections.defaultdict(list)
by_s = collections.defaultdict(set)
for fl, (s, b) in meta.items():
    by_b[b].append(fl)
    by_s[s].add(b)
fams = list(FAM) + ["apartments"]
same = {k: [0, 0] for k in fams}
whole = [0, 0]
for fl in ours:
    sib = [x for x in by_b[meta[fl][1]] if x != fl]
    for x in sib:
        whole[1] += 1
        whole[0] += all(vec[fl][k] == vec[x][k] for k in fams)
        for k in fams:
            same[k][1] += 1
            same[k][0] += vec[fl][k] == vec[x][k]
# baseline: random floor of another building
rnd = {k: [0, 0] for k in fams}
allf = list(meta)
random.seed(0)
for fl in ours:
    for x in random.sample(allf, 5):
        if meta[x][1] == meta[fl][1]:
            continue
        for k in fams:
            rnd[k][1] += 1
            rnd[k][0] += vec[fl][k] == vec[x][k]
our_b = {meta[f][1] for f in ours}
our_s = {meta[f][0] for f in ours}
out = {
    "source_floors": len(meta), "source_buildings": len(by_b), "source_sites": len(by_s),
    "our_floors": len(ours), "our_buildings": len(our_b), "our_sites": len(our_s),
    "unused_floors_in_our_buildings": sum(len(by_b[b]) for b in our_b) - len(ours),
    "unused_floors_in_other_buildings": len(meta) - sum(len(by_b[b]) for b in our_b),
    "floors_in_unused_sites": sum(1 for f, (s, b) in meta.items() if s not in our_s),
    "our_floors_with_a_sibling_floor": sum(1 for f in ours if len(by_b[meta[f][1]]) > 1),
    "sibling_pairs": whole[1],
    "sibling_identical_all_counts": round(whole[0] / max(1, whole[1]), 4),
    "sibling_identical_per_family": {k: round(a / max(1, n), 3) for k, (a, n) in same.items()},
    "random_other_building_identical_per_family": {k: round(a / max(1, n), 3) for k, (a, n) in rnd.items()},
}
json.dump(out, open(OUT / "source_siblings.json", "w"), indent=1)
print(json.dumps(out))
