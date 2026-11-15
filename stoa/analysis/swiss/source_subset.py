# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Leakage map: find each swiss_dwellings floor in the public Swiss Dwellings v3.0.0 geometries.csv.

Needs data/external/swiss-dwellings-v3/swiss-dwellings-v3.0.0/geometries.csv (Zenodo 7788422, CC BY 4.0).
Writes out/source_rows.csv (all source rows of our floors) and out/leakage_map.json (id match stats).
Usage: uv run source_subset.py
"""
import csv, json, pathlib, re, collections, sys

csv.field_size_limit(sys.maxsize)
ROOT = pathlib.Path(__file__).resolve().parents[2]
D = ROOT / "data/junction-dataset/data/swiss_dwellings"
SRC = ROOT / "data/external/swiss-dwellings-v3/swiss-dwellings-v3.0.0/geometries.csv"
OUT = ROOT / "data/external/swiss-derived"  # git-ignored; derived from licensed data

ours = {}
for p in D.glob("*.pdf"):
    m = re.match(r"site(\d+)_bldg(\d+)_floor(\d+)", p.stem)
    ours[m.group(3)] = (m.group(1), m.group(2), p.stem)

found = collections.defaultdict(set)
all_floors = set()
all_sites = set()
n = 0
with open(SRC, newline="") as fin, open(OUT / "source_rows.csv", "w", newline="") as fout:
    r = csv.DictReader(fin)
    w = csv.DictWriter(fout, fieldnames=r.fieldnames)
    w.writeheader()
    for row in r:
        n += 1
        all_floors.add(row["floor_id"])
        all_sites.add(row["site_id"])
        if row["floor_id"] in ours:
            w.writerow(row)
            found[row["floor_id"]].add((row["site_id"], row["building_id"]))

match = sum(1 for f, (s, b, _) in ours.items() if (s, b) in found.get(f, set()))
res = {
    "source_rows": n,
    "source_floors": len(all_floors),
    "source_sites": len(all_sites),
    "our_floors": len(ours),
    "our_floors_found_by_floor_id": sum(1 for f in ours if f in found),
    "our_floors_site_and_building_also_match": match,
    "missing": [ours[f][2] for f in ours if f not in found][:20],
}
json.dump(res, open(OUT / "leakage_map.json", "w"), indent=1)
print(json.dumps(res))
