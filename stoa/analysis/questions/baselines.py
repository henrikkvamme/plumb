# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Topic 3: how a public score misleads. Priors that never look at the drawing.

Predictors (none reads a drawing):
  P0 family constant      best constant per template family (all languages pooled)
  P1 template constant    best constant per template (= family x language)
  P2 slot constant        best constant per (template, slot value), e.g. per room label;
                          falls back to P1 when the slot value was not seen
  P3 conditional          answer of the target family given the gold answer of the single best
                          other family on the same drawing (counts only); falls back to P0
Each is scored in sample (fit and score on all rows) and with grouped 2-fold cross-validation
(fold = hash of group_key, so a building never sits on both sides).
Scoring follows the dataset README: counts exact, area/length/volume within 2%, text exact.

Writes analysis/questions/out/baselines.json.
Run: uv run baselines.py
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict

from qcommon import (
    FULL,
    OUT_DIR,
    annotate,
    answer_key,
    best_constant,
    correct,
    families,
    group_key,
    load,
    write_json,
)

NUMERIC = ("count", "area", "volume", "length")


def fold(r: dict) -> int:
    return int(hashlib.sha256(group_key(r["path"]).encode()).hexdigest(), 16) % 2


def slot_value(r: dict) -> str | None:
    for kind, v in r["_slots"]:
        if kind == "label":
            return v
        if kind == "room":
            return re.sub(r"\s*\(.*\)\s*$", "", v)  # room name without its id
    return None


def fit_const(rows, keyf):
    groups = defaultdict(list)
    for r in rows:
        if r["type"] in NUMERIC:
            groups[keyf(r)].append(r)
    return {k: best_constant(v)[0] for k, v in groups.items()}


def score(rows, predf) -> list[bool]:
    return [correct(predf(r), r) for r in rows]


def summarize(rows, hits) -> dict:
    by_src = defaultdict(list)
    by_fam = defaultdict(list)
    for r, h in zip(rows, hits):
        by_src[r["_src"]].append(h)
        by_fam[(r["_src"], r["_fam"])].append(h)
    src_acc = {s: round(sum(v) / len(v), 4) for s, v in sorted(by_src.items())}
    fam_acc = {f"{s}|{f}": round(sum(v) / len(v), 4) for (s, f), v in sorted(by_fam.items())}
    # Macro over families within each source, then over sources.
    src_fam_macro = {}
    for s in by_src:
        vals = [sum(v) / len(v) for (s2, _), v in by_fam.items() if s2 == s]
        src_fam_macro[s] = round(sum(vals) / len(vals), 4)
    return {
        "micro": round(sum(hits) / len(hits), 4),
        "macro_sources": round(sum(src_acc.values()) / len(src_acc), 4),
        "macro_families": round(sum(sum(v) / len(v) for v in by_fam.values()) / len(by_fam), 4),
        "macro_sources_of_family_macro": round(sum(src_fam_macro.values()) / len(src_fam_macro), 4),
        "per_source": src_acc,
        "per_source_family_macro": src_fam_macro,
        "per_family": fam_acc,
    }


def build_predictors(train):
    fam_c = fit_const(train, lambda r: r["_fam"])
    tpl_c = fit_const(train, lambda r: (r["_src"], r["_tpl"]))
    slot_c = fit_const(train, lambda r: (r["_src"], r["_tpl"], slot_value(r)))

    def p0(r):
        return fam_c.get(r["_fam"])

    def p1(r):
        return tpl_c.get((r["_src"], r["_tpl"]), p0(r))

    def p2(r):
        k = (r["_src"], r["_tpl"], slot_value(r))
        return slot_c[k] if slot_value(r) is not None and k in slot_c else p1(r)

    return p0, p1, p2


def conditional(train, test):
    """P3: per target family, the best single other family on the same drawing as a predictor."""
    def per_drawing(rows):
        d = defaultdict(dict)
        for r in rows:
            if r["type"] == "count" and not r["_slots"] and r["_lang"] == "en":
                d[r["path"]][r["_fam"]] = int(r["answer"])
        return d

    dtr, dte = per_drawing(train), per_drawing(test)
    fams = sorted({f for v in dtr.values() for f in v})
    out = {}
    for t in fams:
        src = t.split("/")[0]
        base = Counter(v[t] for v in dtr.values() if t in v)
        if not base:
            continue
        mode = base.most_common(1)[0][0]
        best = (None, -1.0, {})
        for b in fams:
            if b == t or b.split("/")[0] != src:
                continue
            tab = defaultdict(Counter)
            for v in dtr.values():
                if t in v and b in v:
                    tab[v[b]][v[t]] += 1
            m = {k: c.most_common(1)[0][0] for k, c in tab.items()}
            pairs = [(v[t], m.get(v[b], mode) if b in v else mode) for v in dtr.values() if t in v]
            acc = sum(a == p for a, p in pairs) / len(pairs)
            if acc > best[1]:
                best = (b, acc, m)
        b, _, m = best
        te = [(v[t], (m.get(v[b], mode) if b in v else mode)) for v in dte.values() if t in v]
        te_mode = [v[t] == mode for v in dte.values() if t in v]
        if not te:
            continue
        out[t] = {
            "best_predictor_family": b,
            "test_rows": len(te),
            "mode_acc": round(sum(te_mode) / len(te), 4),
            "conditional_acc": round(sum(a == p for a, p in te) / len(te), 4),
        }
    return out


def main() -> None:
    rows = annotate(load(FULL))
    fam = families(rows)
    for r in rows:
        r["_fam"] = fam[(r["_src"], r["_tpl"])]

    res = {"rows": len(rows)}
    res["share_by_source"] = {
        s: round(n / len(rows), 4) for s, n in Counter(r["_src"] for r in rows).most_common()
    }
    # Independent items: a translation pair asks the same thing about the same drawing.
    res["independent_items"] = len({(r["path"], r["_fam"], r["_sk"]) for r in rows})

    # In sample.
    p0, p1, p2 = build_predictors(rows)
    res["in_sample"] = {
        name: summarize(rows, score(rows, p)) for name, p in (("P0_family", p0), ("P1_template", p1), ("P2_slot", p2))
    }

    # Grouped 2-fold cross-validation.
    cv = {"P0_family": [], "P1_template": [], "P2_slot": []}
    order = []
    p3 = {}
    for k in (0, 1):
        train = [r for r in rows if fold(r) != k]
        test = [r for r in rows if fold(r) == k]
        q0, q1, q2 = build_predictors(train)
        for name, p in (("P0_family", q0), ("P1_template", q1), ("P2_slot", q2)):
            cv[name].extend(score(test, p))
        order.extend(test)
        p3[f"fold{k}"] = conditional(train, test)
    res["cv_grouped_2fold"] = {name: summarize(order, hits) for name, hits in cv.items()}

    # The same P2 slot prior under weaker splits: by row and by drawing (path) instead of group.
    # The gap to the grouped split is what a leaky split would add to a public score.
    weak = {}
    for split_name, keyf in (
        ("row", lambda r: str(r["_i"])),
        ("drawing", lambda r: r["path"]),
        ("group", lambda r: group_key(r["path"])),
    ):
        hits, order2 = [], []
        for k in (0, 1):
            train = [r for r in rows if int(hashlib.sha256(keyf(r).encode()).hexdigest(), 16) % 2 != k]
            test = [r for r in rows if int(hashlib.sha256(keyf(r).encode()).hexdigest(), 16) % 2 == k]
            _, _, q2 = build_predictors(train)
            hits.extend(score(test, q2))
            order2.extend(test)
        sm = summarize(order2, hits)
        weak[split_name] = {"micro": sm["micro"], "per_source": sm["per_source"]}
    res["P2_slot_by_split_unit"] = weak

    # Average P3 over both folds, per target family.
    p3avg = {}
    for t in p3["fold0"]:
        a, b = p3["fold0"][t], p3["fold1"].get(t)
        if not b:
            continue
        n = a["test_rows"] + b["test_rows"]
        p3avg[t] = {
            "best_predictor_family": [a["best_predictor_family"], b["best_predictor_family"]],
            "rows": n,
            "mode_acc": round((a["mode_acc"] * a["test_rows"] + b["mode_acc"] * b["test_rows"]) / n, 4),
            "conditional_acc": round(
                (a["conditional_acc"] * a["test_rows"] + b["conditional_acc"] * b["test_rows"]) / n, 4
            ),
        }
    res["P3_conditional_cv"] = p3avg
    write_json(OUT_DIR / "baselines.json", res)
    for name in cv:
        s = res["cv_grouped_2fold"][name]
        print(name, "micro", s["micro"], "macro_src", s["macro_sources"], s["per_source"])


if __name__ == "__main__":
    main()
