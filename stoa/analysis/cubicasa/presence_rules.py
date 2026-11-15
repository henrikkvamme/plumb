# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Find the rule that decides which templates Stoa asked for each plan.

Inputs: out/svg_features.json (svg_features.py) and out/presence.json (templates.py).
Step 1: for each template, rank SVG classes by how well "class present" predicts "template absent".
Step 2: test explicit candidate rules and report the confusion table.
Writes out/presence_rules.json.
"""
import collections
import json
import pathlib

OUT = pathlib.Path(__file__).parent / "out"
F = json.load(open(OUT / "svg_features.json"))
P = {k.split("/")[-1]: v for k, v in json.load(open(OUT / "presence.json")).items()}
TEMPLATES = ["doors", "bedrooms", "kitchens", "bathrooms", "wc_rooms", "saunas", "balconies",
             "showers_tubs", "sinks", "toilets"]


def all_classes(v):
    s = set()
    for k in ("spaces", "furniture", "doors", "windows"):
        s |= {c for c, n in v[k].items() if n}
    return s


def rank(template, base_filter):
    keys = [k for k in F if base_filter(F[k])]
    absent = {k for k in keys if template not in P[k]}
    stats = []
    classes = collections.Counter()
    for k in keys:
        classes.update(all_classes(F[k]))
    for c, n in classes.items():
        if n < 15:
            continue
        with_c = [k for k in keys if c in all_classes(F[k])]
        a = sum(1 for k in with_c if k in absent)
        # precision: share of plans with class c that lack the template; recall: share of absences covered
        stats.append({"class": c, "n_with": len(with_c), "absent_with": a,
                      "precision": round(a / len(with_c), 3), "recall": round(a / max(1, len(absent)), 3)})
    stats.sort(key=lambda s: (-s["precision"], -s["recall"]))
    return {"n": len(keys), "absent": len(absent), "top": stats[:12]}


def confusion(template, rule):
    c = collections.Counter()
    miss = []
    for k, v in F.items():
        pred = rule(v)
        act = template in P[k]
        c[f"pred={pred},actual={act}"] += 1
        if pred != act and len(miss) < 8:
            miss.append(k)
    agree = sum(n for key, n in c.items() if key in ("pred=True,actual=True", "pred=False,actual=False"))
    return {"agree": round(agree / len(F), 4), "table": dict(c), "misses": miss}


def main():
    no_ud = lambda v: v["spaces"].get("Space UserDefined", 0) == 0  # noqa: E731
    res = {"rank_all": {t: rank(t, lambda v: True) for t in TEMPLATES},
           "rank_no_userdefined": {t: rank(t, no_ud) for t in TEMPLATES}}
    json.dump(res, open(OUT / "presence_rules.json", "w"), indent=1)


if __name__ == "__main__":
    main()
