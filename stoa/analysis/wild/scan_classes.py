# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Tally the by-eye classification of the 120 sampled historic scans (seed 2026, 30 per source, the same files as
out/scan_sample.json and the contact sheets of scan_sample.py).

Each row was typed by a person (an agent) after looking at the contact sheet and, for some, a zoom. The fields:
kind lang scale dims rooms tblock make damage legibility photo
  kind: plan elev sect detail site map cover mixed axon other notdrawing (mixed = several view kinds on one sheet)
  scale: a scale bar or a ratio is printed. dims: dimension strings are printed. rooms: room or space labels.
  tblock: a title block or an official stamp with a date or a number. make: hand cad print digital.
  damage: none light medium heavy (stains, tears, fading, yellowing). photo: a camera photo of a sheet, not a scan.

Writes analysis/wild/out/scan_classes.json. Run: uv run stoa/analysis/wild/scan_classes.py
"""
import collections
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
F = "kind lang scale dims rooms tblock make damage legib photo".split()

RAW = {
    "habs": """
mixed en y y n y hand none fair n
detail en y y n y hand none good n
mixed en y y n y cad none good n
mixed en y n n y hand none good n
cover en y n n y hand none good n
detail en y n n y cad none good n
map en y n n y cad none good n
sect en y y n y cad none good n
mixed en y y n y cad none good n
elev en y n n y hand none good n
site en y n n y cad none good n
axon en y y n y cad none good n
site en y n n y hand none fair n
site en y n n y cad none good n
plan en y y y y hand none good n
axon en n n n y cad none good n
cover en n n n y hand none good n
plan en y y y y hand none good n
mixed en y y y y hand none good n
plan en y y y y hand none good n
axon en y n n y cad none good n
detail en y y n y hand none good n
site en y n n y hand none good n
mixed en y y y y cad none good n
elev en y n n y cad none good n
elev en y n n y cad none good n
elev en y y n y cad none good n
detail en y y n y hand none good n
site en y n n y hand none good n
plan en y y y y hand none good n
""",
    "finna": """
plan fi y y n n hand light fair n
plan sv y n n n hand light good n
mixed unk n n n y hand heavy poor n
mixed sv y n y n hand medium fair n
plan fi+sv y y n n hand medium fair n
plan fi y y n y hand medium poor n
site fi+sv y n n y hand light good n
detail fi n y n n hand none good n
sect sv y n n n hand light good n
plan fi y n y y hand medium fair n
mixed sv y n y n hand light fair n
mixed sv y n y n hand light good n
site fi y n n n hand medium fair n
mixed sv y n n n hand light good n
mixed sv y n n n hand light fair n
notdrawing fi+sv+pl n n n n print none good n
detail fi n y n y hand medium poor n
plan fi y y n y hand medium poor n
detail fi y y n y hand none good n
mixed sv y n n n hand light good n
plan sv y n y n hand light good n
site fi y n n y hand light good n
elev fi+sv n n n y hand medium fair n
map sv y n n n hand medium fair n
site fi+sv y n n y hand light good n
mixed fi y y y n hand medium poor n
plan sv y n n n hand light good n
site fi+sv y n n n hand light fair n
notdrawing sv n n n n hand light fair n
mixed sv y n y n hand light fair n
""",
    "europeana": """
elev en n n n n print none good n
notdrawing nl n n n n hand light good n
mixed fr y n n n print none good n
mixed en y n n n print light good n
mixed fr y n n n print light good n
other la n n n n hand light good n
detail it n y n n hand medium fair n
elev en y n n n hand heavy fair n
mixed es y n n n print light good n
detail de n n n n hand heavy poor n
mixed la n n y n hand none good n
mixed unk n n n n hand heavy poor n
mixed en n y n n print none good n
detail unk n n n n hand medium fair n
elev fr y n n n print none good n
mixed fr y n y n print light good n
elev hu y n n n hand light good n
mixed en y n y n hand medium fair n
notdrawing nl n n n n hand light good n
plan de n y y y hand light fair n
plan et n n y n hand light good n
site nl y n n y print none good y
elev unk y n n n hand light good y
elev unk n n n n hand medium poor y
mixed hr n n y n hand light good n
plan en y n y n print none fair n
map pt y n n n print medium good n
elev unk n n n n hand medium fair y
mixed de y y n n hand medium fair y
elev pt y n n n hand heavy fair n
""",
    "wikimedia": """
plan hu y n y n digital none good n
plan de n n n n print none good n
mixed unk y n n n hand light fair n
plan en y n y n print none good n
plan sv n n y n hand light fair y
mixed en y n y n print light good n
plan fr n n n n hand medium fair n
mixed fr n n n n hand light good n
plan unk n y n n hand medium poor n
plan unk n n n n print none good n
plan none n n n n digital none good n
plan sv y n y n print none good n
plan fr n n y n print none good n
plan sv y n y n hand light good n
mixed ru n n n n hand medium poor y
plan de y n n n digital none good n
plan de y n y n hand light good n
mixed fr n n n n hand light fair n
plan none n n n n digital none good n
plan no y n n n print light fair n
plan fr n n n n print none good n
mixed ru n n y n hand light fair n
mixed ru y n y n hand light fair n
plan de y n y n digital none good n
elev sv y n n n hand medium fair n
site uk y n y n digital none good n
plan en y n y n print light good n
plan en y n y n print none good n
plan de y n y n print medium fair y
plan none y n n n print none good n
""",
}

sample = json.load(open(OUT / "scan_sample.json"))
rows, table = [], {}
for src, raw in RAW.items():
    lines = [ln.split() for ln in raw.strip().splitlines()]
    assert len(lines) == len(sample[src]) == 30, src
    recs = []
    for i, (name, vals) in enumerate(zip(sample[src], lines)):
        assert len(vals) == len(F), (src, i, vals)
        r = dict(zip(F, vals), source=src, idx=i, file=name)
        recs.append(r)
    rows += recs
    c = lambda f, v="y": sum(1 for r in recs if r[f] == v)  # noqa: E731
    table[src] = {
        "n": len(recs),
        "kind": dict(collections.Counter(r["kind"] for r in recs).most_common()),
        "lang": dict(collections.Counter(r["lang"] for r in recs).most_common()),
        "not_a_building_drawing": sum(1 for r in recs if r["kind"] in ("notdrawing", "other", "map")),
        "plan_or_mixed": sum(1 for r in recs if r["kind"] in ("plan", "mixed")),
        "scale": c("scale"), "dims": c("dims"), "rooms": c("rooms"), "tblock": c("tblock"),
        "make": dict(collections.Counter(r["make"] for r in recs).most_common()),
        "damage_medium_or_heavy": sum(1 for r in recs if r["damage"] in ("medium", "heavy")),
        "damage_heavy": c("damage", "heavy"),
        "legib_poor": c("legib", "poor"), "legib_good": c("legib", "good"),
        "photo": c("photo"),
    }
json.dump({"fields": F, "summary": table, "rows": rows}, open(OUT / "scan_classes.json", "w"), indent=1,
          ensure_ascii=False)
for s, t in table.items():
    print(s, json.dumps({k: v for k, v in t.items()}, ensure_ascii=False))
