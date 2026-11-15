# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Topic 6: split design. Grouping keys, group sizes, a frozen grouped split and shift suites.

The split assigns whole groups (building, model project, drawing set) to dev, val or test, so no
building or model crosses a split. Within each stratum it balances template families: each group
goes to the split whose family composition it helps most, in a fixed hash order.

Strata: cubicasa5k, swiss_dwellings, ifc (ifc_models and ifc_bench together: they share buildings,
eight files are byte-identical), opening_design. Drawings with no questions get a split too, so an
unlabelled shift suite can use them.

Writes analysis/questions/split_v0.json and analysis/questions/out/split_stats.json.
Run: uv run split.py
"""

from __future__ import annotations

import hashlib
import os
import re
from collections import Counter, defaultdict

from qcommon import (
    FULL,
    OUT_DIR,
    STOA,
    annotate,
    families,
    group_key,
    load,
    sha256_json,
    stem,
    write_json,
)

SEED = "stoa-split-v0-2026-11-13"
TARGET = {"dev": 0.6, "val": 0.2, "test": 0.2}
SPLITS = list(TARGET)
DATA = STOA / "data" / "junction-dataset" / "data"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "split_v0.json")

TASKS = [
    ("area_room", r"net floor area of (the )?room"),
    ("area_apartment", r"apartment .* in m²|net floor area of apartment"),
    ("area_aggregate", r"total net (floor |side )?area"),
    ("volume", r"volume"),
    ("length", r"length"),
    ("count_model", r"in the model"),
    ("count_rooms_by_label", r"rooms labelled"),
    ("count_room_type", r"bedrooms|bathrooms|WC rooms|kitchens|saunas|balconies|rooms \(spaces\)|apartments"),
    ("count_fixtures", r"toilet|sinks|washbasins|showers|bathtubs|sanitary|light fixtures"),
    ("count_openings", r"doors|windows"),
    ("count_structure", r"walls|columns|stairs|beams|floors \(storeys\)"),
]


def task_of(src: str, en_template: str, typ: str) -> str:
    if src == "ifc_bench":
        return "free_text_model"
    if src == "opening_design":
        return "schedule_" + typ
    for name, rx in TASKS:
        if re.search(rx, en_template):
            return name
    return "other"


def stratum(src: str) -> str:
    return "ifc" if src in ("ifc_models", "ifc_bench") else src


def h(x: str) -> int:
    return int(hashlib.sha256((SEED + ":" + x).encode()).hexdigest(), 16)


def assign(groups: dict[str, Counter]) -> dict[str, str]:
    """groups: group -> Counter(family -> rows). Greedy family-balanced assignment in hash order."""
    total = Counter()
    for c in groups.values():
        total.update(c)
    cur = {s: Counter() for s in SPLITS}
    out = {}
    order = sorted(groups, key=lambda g: (-sum(groups[g].values()) if len(groups) < 40 else 0, h(g)))
    for g in order:
        c = groups[g]
        best, best_score = None, None
        for s in SPLITS:
            # Deficit of split s for the families of this group, weighted by the group's rows.
            score = sum(max(0.0, TARGET[s] * total[f] - cur[s][f]) * n for f, n in c.items())
            # Tie-break toward the split furthest below its overall target.
            under = TARGET[s] * sum(total.values()) - sum(cur[s].values())
            key = (score, under)
            if best_score is None or key > best_score:
                best, best_score = s, key
        out[g] = best
        cur[best].update(c)
    return out


def main() -> None:
    rows = annotate(load(FULL))
    fam = families(rows)
    en_tpl = {}
    for r in rows:
        f = fam[(r["_src"], r["_tpl"])]
        r["_fam"] = f
        if r["_lang"] == "en":
            en_tpl.setdefault(f, r["_tpl"])
    for r in rows:
        r["_task"] = task_of(r["_src"], en_tpl.get(r["_fam"], r["_tpl"]), r["type"])
        r["_grp"] = group_key(r["path"])

    stats = {}
    # Group sizes per source.
    gs = defaultdict(Counter)
    gd = defaultdict(lambda: defaultdict(set))
    for r in rows:
        gs[r["_src"]][r["_grp"]] += 1
        gd[r["_src"]][r["_grp"]].add(stem(r["path"]))
    stats["groups"] = {
        s: {
            "groups": len(c),
            "rows_per_group_min_median_max": [
                min(c.values()),
                sorted(c.values())[len(c) // 2],
                max(c.values()),
            ],
            "drawings_per_group_max": max(len(v) for v in gd[s].values()),
            "largest_groups": c.most_common(5),
        }
        for s, c in gs.items()
    }
    cross = defaultdict(set)
    for r in rows:
        cross[r["_grp"]].add(r["_src"])
    stats["groups_spanning_two_sources"] = sorted(g for g, v in cross.items() if len(v) > 1)

    # Drawings on disk and with questions, per source.
    on_disk = defaultdict(set)
    files_on_disk = defaultdict(set)
    for dp, _, fns in os.walk(DATA):
        for fn in fns:
            if fn == "LICENSE.md":
                continue
            rel = os.path.relpath(os.path.join(dp, fn), DATA.parent)
            on_disk[rel.split("/")[1]].add(stem(rel))
            files_on_disk[rel.split("/")[1]].add(rel)
    with_q = defaultdict(set)
    for r in rows:
        with_q[r["_src"]].add(stem(r["path"]))
    stats["drawings_on_disk_vs_with_questions"] = {
        s: {"stems_on_disk": len(v), "stems_with_questions": len(with_q.get(s, set()) & v)}
        for s, v in sorted(on_disk.items())
    }
    groups_on_disk = defaultdict(set)
    for s, v in files_on_disk.items():
        for rel in v:
            groups_on_disk[s].add(group_key(rel))
    stats["groups_on_disk_vs_with_questions"] = {
        s: {"groups_on_disk": len(v), "groups_with_questions": len({g for g in v if g in cross})}
        for s, v in sorted(groups_on_disk.items())
    }

    # Assignment per stratum.
    per_stratum = defaultdict(lambda: defaultdict(Counter))
    for r in rows:
        per_stratum[stratum(r["_src"])][r["_grp"]][r["_fam"]] += 1
        # Balance languages too: in the ifc stratum one model carries one local language.
        per_stratum[stratum(r["_src"])][r["_grp"]]["lang:" + r["_lang"]] += 1
    assignment = {}
    for st, groups in per_stratum.items():
        if len(groups) < 3:
            # Too few groups to split three ways: the largest goes to test, the next to dev.
            order = sorted(groups, key=lambda g: (-sum(groups[g].values()), h(g)))
            for g, s in zip(order, ["test", "dev", "val"]):
                assignment[g] = s
        else:
            assignment.update(assign(groups))
    # Drawings without questions: by hash of group, same targets.
    unlabelled = {}
    for s, gset in groups_on_disk.items():
        for g in sorted(gset):
            if g in assignment:
                continue
            x = (h(g) % 1000) / 1000
            unlabelled[g] = "dev" if x < 0.6 else ("val" if x < 0.8 else "test")

    # Statistics of the split.
    sp = Counter()
    sp_src = defaultdict(Counter)
    sp_task = defaultdict(Counter)
    sp_lang = defaultdict(Counter)
    sp_groups = defaultdict(Counter)
    lang_groups = defaultdict(lambda: defaultdict(set))
    fam_cover = defaultdict(lambda: defaultdict(int))
    for r in rows:
        s = assignment[r["_grp"]]
        sp[s] += 1
        sp_src[r["_src"]][s] += 1
        sp_task[r["_task"]][s] += 1
        sp_lang[r["_lang"]][s] += 1
        fam_cover[r["_fam"]][s] += 1
        lang_groups[r["_lang"]][s].add(r["_grp"])
    for g, s in assignment.items():
        sp_groups[g.split(":")[0]][s] += 1
    stats["split_rows"] = dict(sp)
    stats["split_rows_by_source"] = {k: dict(v) for k, v in sp_src.items()}
    stats["split_rows_by_task"] = {k: dict(v) for k, v in sp_task.items()}
    stats["split_rows_by_language"] = {k: dict(v) for k, v in sp_lang.items()}
    stats["split_groups_by_prefix"] = {k: dict(v) for k, v in sp_groups.items()}
    stats["split_groups_by_language"] = {l: {s: len(g) for s, g in v.items()} for l, v in lang_groups.items()}
    stats["families_missing_from_test"] = sorted(f for f, v in fam_cover.items() if not v.get("test"))
    stats["families_missing_from_dev"] = sorted(f for f, v in fam_cover.items() if not v.get("dev"))
    # Prior to beat on the locked test: template constant fit on dev only.
    from qcommon import best_constant, correct

    dev = defaultdict(list)
    for r in rows:
        if assignment[r["_grp"]] == "dev" and r["type"] != "text":
            dev[(r["_src"], r["_tpl"])].append(r)
            dev[("fam", r["_fam"])].append(r)
    const = {k: best_constant(v)[0] for k, v in dev.items()}
    hits_src, hits_task = defaultdict(list), defaultdict(list)
    for r in rows:
        if assignment[r["_grp"]] != "test":
            continue
        pred = const.get((r["_src"], r["_tpl"]), const.get(("fam", r["_fam"])))
        ok = correct(pred, r) if r["type"] != "text" else False
        hits_src[r["_src"]].append(ok)
        hits_task[(r["_src"], r["_task"])].append(ok)
    allh = [x for v in hits_src.values() for x in v]
    stats["test_prior_template_constant_fit_on_dev"] = {
        "micro": round(sum(allh) / len(allh), 4),
        "macro_sources": round(sum(sum(v) / len(v) for v in hits_src.values()) / len(hits_src), 4),
        "macro_source_task": round(sum(sum(v) / len(v) for v in hits_task.values()) / len(hits_task), 4),
        "per_source": {k: round(sum(v) / len(v), 4) for k, v in hits_src.items()},
        "per_source_task": {f"{a}|{b}": [round(sum(v) / len(v), 4), len(v)] for (a, b), v in sorted(hits_task.items())},
    }
    stats["unlabelled_groups_by_split"] = dict(Counter(unlabelled.values()))
    stats["task_rows"] = dict(Counter(r["_task"] for r in rows))

    # Shift suites: definitions as filters, with sizes.
    langs = Counter(r["_lang"] for r in rows)
    tasks = Counter(r["_task"] for r in rows)
    srcs = Counter(r["_src"] for r in rows)
    fams = Counter(r["_fam"] for r in rows)
    shift = {
        "leave_one_source_out": {s: n for s, n in srcs.items()},
        "leave_one_language_out": {
            l: {"rows": n, "note": "hold out every question in this language; tune prompts and rules only on the rest"}
            for l, n in langs.items()
            if l != "en"
        },
        "leave_one_task_out": dict(tasks),
        "leave_one_family_out": {f: n for f, n in fams.most_common() if not f.startswith("ifc_bench/")},
        "unlabelled_sources": {
            s: stats["drawings_on_disk_vs_with_questions"][s]["stems_on_disk"]
            for s in ("habs", "finna", "europeana", "wikimedia")
        },
        "modality_swap": "the same question on the .ifc file and on its plan PDF (ifc_models), and on PDF, DXF and PNG copies (swiss_dwellings); the answer must not change",
    }

    manifest_core = {
        "version": "split_v0",
        "seed": SEED,
        "targets": TARGET,
        "group_key": "qcommon.group_key: cubicasa plan id, swiss site, ifc project (ifc_models + ifc_bench merged), opening_design project folder, habs survey id, finna record, europeana record prefix, wikimedia file",
        "algorithm": "per stratum, groups in sha256(seed:group) order (largest first when < 40 groups), each to the split with the largest family deficit; strata with < 3 groups: largest to test",
        "groups": dict(sorted(assignment.items())),
        "unlabelled_groups": dict(sorted(unlabelled.items())),
    }
    manifest = dict(manifest_core)
    manifest["sha256"] = sha256_json(manifest_core)
    manifest["rows"] = stats["split_rows"]
    manifest["shift_suites"] = shift
    manifest["generated_by"] = "stoa/analysis/questions/split.py"
    write_json(OUT_DIR / "split_stats.json", stats)
    import json

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=0)
    print("split", dict(sp), "sha256", manifest["sha256"][:16])


if __name__ == "__main__":
    main()
