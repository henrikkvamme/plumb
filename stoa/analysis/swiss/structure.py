# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Split structure, language assignment, contradictions and question-presence leaks for swiss_dwellings.

1. Contradictions: the English and local-language twin of one question on one floor with different answers.
2. Language: is the label language constant per building and per site?
3. Near copies: how often do two floors of one building (or site) give the same answer to the same
   template? A random floor split leaks these; a fair split groups by site.
4. Question presence: are bathtub and shower questions asked only when the answer is at least 1?
5. Baselines: per-template mode, and "copy the answer from another floor of the same building".
Writes structure.json.
Usage: uv run structure.py
"""
import json, pathlib, collections, re, sys, random, statistics

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from qparse import parse

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "data/external/swiss-derived"
rows = json.load(open(OUT / "rows.json"))


def ids(path):
    m = re.search(r"site(\d+)_bldg(\d+)_floor(\d+)", path)
    return m.group(1), m.group(2), m.group(3)


# 1 contradictions
twins = collections.defaultdict(set)
for r in rows:
    fam, p, lang = parse(r["question"])
    twins[(r["path"], fam, p)].add((lang, r["answer"]))
contra = [(k, v) for k, v in twins.items() if len({a for _, a in v}) > 1]
multi = sum(1 for v in twins.values() if len(v) > 1 or True)

# 2 language
floor_lang = {}
for r in rows:
    fam, p, lang = parse(r["question"])
    if lang != "en":
        floor_lang[r["path"]] = lang
by_b = collections.defaultdict(set)
by_s = collections.defaultdict(set)
floors_b = collections.defaultdict(set)
floors_s = collections.defaultdict(set)
for path, l in floor_lang.items():
    s, b, f = ids(path)
    by_b[b].add(l)
    by_s[s].add(l)
    floors_b[b].add(path)
    floors_s[s].add(path)

# 3 near copies: same template key (family + param) answered on several floors of one group
key_ans = collections.defaultdict(list)
for r in rows:
    fam, p, lang = parse(r["question"])
    if lang != "en":
        continue
    s, b, f = ids(r["path"])
    key_ans[(fam, p)].append((s, b, r["path"], r["answer"]))


def copy_baseline(group_idx):
    """Predict each answer by copying the same question's answer on another floor of the same group."""
    hit = tot = covered = 0
    grp = collections.defaultdict(list)
    for (fam, p), lst in key_ans.items():
        for s, b, path, a in lst:
            grp[(fam, p, (s, b)[group_idx])].append((path, a))
    fam_stats = collections.defaultdict(lambda: [0, 0, 0])
    for (fam, p, g), lst in grp.items():
        for i, (path, a) in enumerate(lst):
            tot += 1
            fam_stats[fam][1] += 1
            others = [x for j, (pp, x) in enumerate(lst) if j != i]
            if not others:
                continue
            covered += 1
            fam_stats[fam][2] += 1
            pred = collections.Counter(others).most_common(1)[0][0]
            ok = (pred == a) if isinstance(a, int) else abs(pred - a) <= 0.02 * abs(a)
            hit += ok
            fam_stats[fam][0] += ok
    return {"accuracy_all": round(hit / tot, 4), "coverage": round(covered / tot, 4), "accuracy_when_covered": round(hit / max(1, covered), 4),
            "per_family": {k: {"acc_all": round(v[0] / v[1], 3), "covered": round(v[2] / v[1], 3)} for k, v in fam_stats.items()}}


# 4 presence leak
pres = collections.defaultdict(collections.Counter)
asked = collections.defaultdict(set)
for r in rows:
    fam, p, lang = parse(r["question"])
    if lang == "en":
        pres[fam][r["answer"]] += 1
        asked[fam].add(r["path"])
nfloors = len({r["path"] for r in rows})

# 5 mode baseline per template (family + param), English only
mode_hit = mode_tot = 0
fam_mode = collections.defaultdict(lambda: [0, 0])
for (fam, p), lst in key_ans.items():
    c = collections.Counter(a for *_, a in lst)
    m = c.most_common(1)[0][0]
    for *_, a in lst:
        ok = (m == a) if isinstance(a, int) else abs(m - a) <= 0.02 * abs(a)
        mode_hit += ok
        mode_tot += 1
        fam_mode[fam][0] += ok
        fam_mode[fam][1] += 1

out = {
    "twin_groups": len(twins),
    "contradictions": len(contra),
    "contradiction_examples": [[list(k), sorted(v)] for k, v in contra[:10]],
    "language_floors": dict(collections.Counter(floor_lang.values())),
    "buildings": len(by_b), "sites": len(by_s),
    "buildings_with_mixed_language": sum(1 for v in by_b.values() if len(v) > 1),
    "sites_with_mixed_language": sum(1 for v in by_s.values() if len(v) > 1),
    "floors_per_building": dict(collections.Counter(len(v) for v in floors_b.values())),
    "floors_per_site": dict(collections.Counter(len(v) for v in floors_s.values())),
    "copy_within_building": copy_baseline(1),
    "copy_within_site": copy_baseline(0),
    "answer_dist": {k: sorted(v.items())[:15] for k, v in pres.items() if k in ("bathtubs", "showers", "toilets", "washbasins", "apartments", "doors", "windows")},
    "floors_asked": {k: len(v) for k, v in asked.items()},
    "n_floors": nfloors,
    "mode_baseline_en": round(mode_hit / mode_tot, 4),
    "mode_baseline_per_family": {k: round(a / n, 3) for k, (a, n) in fam_mode.items()},
}
json.dump(out, open(OUT / "structure.json", "w"), indent=1, ensure_ascii=False)
for k, v in out.items():
    if k not in ("contradiction_examples",):
        print(k, json.dumps(v, ensure_ascii=False)[:400])
