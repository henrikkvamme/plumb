# /// script
# requires-python = ">=3.11"
# dependencies = ["langdetect==1.0.9"]
# ///
"""Topic 1: template inventory and languages.

Clusters every question into a template with slots, finds the paired template in the other
language, and writes stoa/docs/research/data/templates.json.

Run: uv run templates.py
"""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict

from qcommon import (
    FULL,
    OUT_DIR,
    STOA,
    annotate,
    answer_key,
    best_constant,
    entropy_bits,
    families,
    load,
    pair_templates,
    template_ids,
    write_json,
)

OUT = STOA / "docs" / "research" / "data" / "templates.json"


def main() -> None:
    rows = annotate(load(FULL))
    ids = template_ids(rows)
    pairs = pair_templates(rows)
    fam = families(rows)

    by_t: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        by_t[(r["_src"], r["_tpl"])].append(r)

    # English templates: the partner list is the reverse of the pairing.
    rev: dict[tuple, list] = defaultdict(list)
    for a, p in pairs.items():
        if p["partner"]:
            rev[p["partner"]].append(a)

    table = []
    for k, rs in sorted(by_t.items(), key=lambda kv: ids[kv[0]]):
        s, t = k
        types = Counter(r["type"] for r in rs)
        units = Counter(str(r["unit"]) for r in rs)
        typ = types.most_common(1)[0][0]
        ans = [answer_key(r) for r in rs]
        entry = {
            "id": ids[k],
            "source": s,
            "language": rs[0]["_lang"],
            "type": typ,
            "types": dict(types),
            "units": dict(units),
            "family": fam[k],
            "count": len(rs),
            "drawings": len({r["path"] for r in rs}),
            "slot_kinds": sorted({kd for r in rs for kd, _ in r["_slots"]}),
            "distinct_slot_values": len({r["_sk"] for r in rs}) if rs[0]["_slots"] else 0,
            "template": t,
            "example": rs[0]["question"],
        }
        if typ == "text":
            entry["answer"] = {
                "distinct": len(set(ans)),
                "mode_share": round(Counter(ans).most_common(1)[0][1] / len(ans), 4),
                "median_chars": statistics.median(len(a) for a in ans),
            }
        else:
            c = Counter(ans)
            mode, mode_n = c.most_common(1)[0]
            bc, bc_n = best_constant(rs)
            vals = [float(a) for a in ans]
            entry["answer"] = {
                "distinct": len(c),
                "entropy_bits": round(entropy_bits(ans), 3),
                "mode": mode,
                "mode_share": round(mode_n / len(ans), 4),
                "best_constant": round(bc, 3) if isinstance(bc, float) else bc,
                "best_constant_share": round(bc_n / len(ans), 4),
                "min": min(vals),
                "median": statistics.median(vals),
                "max": max(vals),
                "top5": [[a, n] for a, n in c.most_common(5)],
            }
        if k in pairs and pairs[k]["partner"]:
            p = pairs[k]
            entry["paired_with"] = ids[p["partner"]]
            entry["pair_overlap"] = p["both"]
            entry["pair_agreement"] = round(p["agree"] / p["both"], 4) if p["both"] else None
        elif k in rev:
            entry["paired_with"] = sorted(ids[a] for a in rev[k])
        else:
            entry["paired_with"] = None
        table.append(entry)

    # Language counts per question and per source.
    lang_q = Counter(r["_lang"] for r in rows)
    lang_src = defaultdict(Counter)
    for r in rows:
        lang_src[r["_src"]][r["_lang"]] += 1

    # Cross-check of the stopword detector with langdetect on the template text (slots removed).
    from langdetect import DetectorFactory, detect

    DetectorFactory.seed = 0
    agree = 0
    checked = 0
    disagreements = []
    for e in table:
        if e["source"] in ("ifc_bench",):
            continue
        text = re.sub(r"\{[A-Z_]+\}", " ", e["template"])
        try:
            d = detect(text)
        except Exception:
            d = "und"
        checked += 1
        if d == e["language"]:
            agree += 1
        else:
            disagreements.append([e["id"], e["language"], d, e["template"][:90]])

    summary = {
        "templates_total": len(table),
        "templates_per_source": dict(Counter(e["source"] for e in table)),
        "families_per_source": {
            s: len({e["family"] for e in table if e["source"] == s})
            for s in sorted({e["source"] for e in table})
        },
        "questions_per_language": dict(lang_q.most_common()),
        "questions_per_source_language": {s: dict(c.most_common()) for s, c in lang_src.items()},
        "templates_per_language": dict(Counter(e["language"] for e in table).most_common()),
        "langdetect_crosscheck": {
            "checked_templates": checked,
            "agree": agree,
            "disagreements": disagreements[:40],
        },
        "ifc_bench_question_reuse": dict(
            Counter(e["count"] for e in table if e["source"] == "ifc_bench")
        ),
    }
    doc = {
        "generated_by": "stoa/analysis/questions/templates.py",
        "input": str(FULL.relative_to(STOA)),
        "rows": len(rows),
        "summary": summary,
        "templates": table,
    }
    write_json(OUT, doc)
    write_json(OUT_DIR / "templates_summary.json", summary)
    print("templates", len(table), "->", OUT)


if __name__ == "__main__":
    main()
