# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Join every drawn room (DXF) to its public source area by polygon area, to read the label convention.

Outputs label_map.json: drawn label -> source entity_subtype counts, the language of each floor (from its
labels), and the subtypes of numbered rooms that the floor-total reference leaves out.
Usage: uv run label_map.py   (needs dxf_features.py and probe_source.py outputs)
"""
import json, pathlib, collections, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from qparse import parse, OUTDOOR

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "data/external/swiss-derived"
F = json.load(open(OUT / "dxf_features.json"))
S = json.load(open(OUT / "source_floor.json"))
rows = json.load(open(OUT / "rows.json"))

lab2sub = collections.defaultdict(collections.Counter)
unmatched = 0
matched = 0
room_sub = {}
for fl, f in F.items():
    fid = fl.split("floor")[1]
    src = S[fid]["areas"]
    pool = collections.defaultdict(list)
    for sub, a, u, uu in src:
        pool[round(a, 2)].append(sub)
    for r in f["rooms"]:
        if r["area"] is None:
            continue
        k = round(r["area"], 2)
        subs = pool.get(k) or pool.get(round(k + 0.01, 2)) or pool.get(round(k - 0.01, 2))
        if subs:
            matched += 1
            lab2sub[r["label"]][subs[0]] += 1
            room_sub[(fl, r["num"])] = subs[0]
        else:
            unmatched += 1

# floor-total: which numbered drawn rooms does the reference leave out?
ref_total = {pathlib.Path(r["path"]).stem: r["answer"] for r in rows if parse(r["question"])[0] == "area_total"}
excluded_sub = collections.Counter()
explained = 0
miss = 0
for fl, ans in ref_total.items():
    f = F[fl]
    pred = sum(r["area"] for r in f["rooms"] if r["area"] and r["label"] not in OUTDOOR)
    if abs(pred - ans) <= 0.02 * ans:
        continue
    miss += 1
    subs = collections.Counter(room_sub.get((fl, r["num"])) for r in f["rooms"] if r["area"] and r["label"] not in OUTDOOR)
    excluded_sub.update(s for s in subs if s in {"SHAFT", "VOID", "NOT_DEFINED", "LIGHTWELL", "ELEVATOR"})
    pred2 = sum(r["area"] for r in f["rooms"] if r["area"] and r["label"] not in OUTDOOR and room_sub.get((fl, r["num"])) not in {"SHAFT", "VOID", "LIGHTWELL", "OUTDOOR_VOID"})
    explained += abs(pred2 - ans) <= 0.02 * ans
out = {
    "rooms_matched_to_source": matched,
    "rooms_unmatched": unmatched,
    "label_to_subtype": {str(k): v.most_common(6) for k, v in sorted(lab2sub.items(), key=lambda kv: -sum(kv[1].values()))},
    "area_total_misses": miss,
    "area_total_misses_explained_by_numbered_shaft_or_void": explained,
    "subtypes_in_missed_floors": excluded_sub.most_common(),
}
json.dump(out, open(OUT / "label_map.json", "w"), indent=1, ensure_ascii=False)
print({k: v for k, v in out.items() if k != "label_to_subtype"})
for k, v in list(out["label_to_subtype"].items())[:45]:
    print(k, v)
