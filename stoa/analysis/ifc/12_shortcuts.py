# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Shortcut baselines on ifc_models that need no drawing and no model.

  S1 pair copy      : the English and local-language twin of a question share the answer. If a split puts
                      one twin in train and one in test, the test row is free. Measures the share of rows with a twin.
  S2 same-name room : predict a room's area as the mode of the other public answers for rooms with the same
                      base name (the text before " (") in the same model (leave-one-out, twins removed).
  S3 template mode  : predict the mode answer of the family in the same model (leave-one-out, twins removed).
Writes out/shortcuts.json.
"""
import collections
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"


def ok(p, ref, t):
    if p is None:
        return False
    return p == ref if t == "count" else abs(p - ref) <= 0.02 * ref


def main():
    rows = [json.loads(l) for l in open(OUT / "probe_rows.jsonl")]
    # twin = same model, same family, same storey/room/class, same answer, other question text
    def key(r):
        p = r["parsed"]
        return (r["model"], r["family"], p.get("storey"), p.get("room"), p.get("cls"))
    groups = collections.defaultdict(list)
    for i, r in enumerate(rows):
        groups[key(r)].append(i)
    has_twin = sum(1 for g in groups.values() for _ in g if len(g) > 1)
    twins_same_answer = sum(1 for g in groups.values() if len(g) > 1 and len({rows[i]["ref"] for i in g}) == 1)
    # S2
    s2_n = s2_ok = s2_cover = 0
    by_base = collections.defaultdict(list)
    for gk, g in groups.items():
        r = rows[g[0]]
        if r["family"] == "area_room":
            base = re.sub(r"\s*\(.*\)$", "", r["parsed"]["room"]).strip().lower()
            by_base[(r["model"], base)].append(gk)
    for (m, base), gks in by_base.items():
        for gk in gks:
            r = rows[groups[gk][0]]
            others = [rows[groups[o][0]]["ref"] for o in gks if o != gk]
            s2_n += 1
            if others:
                s2_cover += 1
                pred = collections.Counter(others).most_common(1)[0][0]
                s2_ok += ok(pred, r["ref"], r["type"])
    # S3
    s3 = collections.Counter()
    fam_groups = collections.defaultdict(list)
    for gk in groups:
        fam_groups[(gk[0], gk[1])].append(gk)
    for (m, fam), gks in fam_groups.items():
        for gk in gks:
            r = rows[groups[gk][0]]
            others = [rows[groups[o][0]]["ref"] for o in gks if o != gk]
            s3[(fam, "n")] += 1
            if others:
                pred = collections.Counter(others).most_common(1)[0][0]
                s3[(fam, "ok")] += ok(pred, r["ref"], r["type"])
    summ = {
        "rows": len(rows), "distinct_items": len(groups), "rows_with_twin": has_twin,
        "twin_groups_same_answer": twins_same_answer, "twin_groups": sum(1 for g in groups.values() if len(g) > 1),
        "S2_same_name_room": {"items": s2_n, "with_namesake": s2_cover, "correct": s2_ok, "pct_of_items": round(100 * s2_ok / s2_n, 1)},
        "S3_family_mode": {f: {"items": s3[(f, "n")], "correct": s3[(f, "ok")], "pct": round(100 * s3[(f, "ok")] / s3[(f, "n")], 1)} for f in sorted({k[0] for k in s3})},
    }
    json.dump(summ, open(OUT / "shortcuts.json", "w"), indent=1)
    print(json.dumps(summ, indent=0))


if __name__ == "__main__":
    main()
