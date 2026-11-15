# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Summarise out/probe_rows.jsonl from 05_probe_models.py.

Per family: share of questions where each candidate rule agrees, share where ANY rule agrees,
the best single rule, agreement per model for the best rule, and example disagreements.
Writes out/probe_summary.json and prints a compact table.
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "probe_rows.jsonl"
    rows = [json.loads(l) for l in open(OUT / src)]
    fams = collections.defaultdict(list)
    for r in rows:
        fams[r["family"]].append(r)
    summary = {}
    for fam, rs in sorted(fams.items()):
        n = len(rs)
        cand_hits = collections.Counter()
        for r in rs:
            for a in r["agrees"]:
                cand_hits[a] += 1
        any_hit = sum(1 for r in rs if r["agrees"])
        best = cand_hits.most_common(1)[0][0] if cand_hits else None
        per_model = collections.defaultdict(lambda: [0, 0])
        for r in rs:
            per_model[r["model"]][1] += 1
            per_model[r["model"]][0] += best in r["agrees"]
        # best rule per model (the generator may switch rules by what the model holds)
        best_by_model = {}
        for m in per_model:
            c = collections.Counter(a for r in rs if r["model"] == m for a in r["agrees"])
            mr = [r for r in rs if r["model"] == m]
            best_by_model[m] = {"n": len(mr), "best": c.most_common(3), "any": sum(1 for r in mr if r["agrees"])}
        dis = [
            {"model": r["model"][:40], "path": r["path"], "q": r["q"], "ref": r["ref"],
             "cands": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r["cands"].items()}, "info": r["info"]}
            for r in rs if not r["agrees"]
        ]
        summary[fam] = {
            "n": n, "any_rule": any_hit, "any_rule_pct": round(100 * any_hit / n, 1),
            "rules": {k: [v, round(100 * v / n, 1)] for k, v in cand_hits.most_common()},
            "best_rule": best, "per_model_best_rule": {m: v for m, v in sorted(per_model.items())},
            "best_by_model": best_by_model, "n_disagree": len(dis), "disagreements": dis[:25],
        }
    tot = len(rows)
    any_all = sum(1 for r in rows if r["agrees"])
    summary["_total"] = {"n": tot, "any_rule": any_all, "pct": round(100 * any_all / tot, 1)}
    json.dump(summary, open(OUT / src.replace("rows", "summary").replace(".jsonl", ".json"), "w"), indent=1, ensure_ascii=False)
    for fam, v in summary.items():
        if fam.startswith("_"):
            print(fam, v)
            continue
        print(f"{fam}: n={v['n']} any={v['any_rule_pct']}% rules={dict(list(v['rules'].items())[:5])}")


if __name__ == "__main__":
    main()
