# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Topic 4: consistency checks as a label-noise detector.

Hard checks (a violation means at least one answer is wrong, or the question is ill-posed):
  - translation pairs with different answers
  - the same (path, question) twice; the same question text on two files of one model with two answers
  - parts larger than wholes (room area > label total, apartment sum > floor total, ...)
  - impossible values (count 0 where the question presupposes the item, negative, non-integer counts)
Soft checks (a violation is unusual but can be real): WC rooms > toilet bowls, kitchens > sinks, ...

Writes analysis/questions/out/consistency.json with counts and up to 8 examples per check.
Run: uv run consistency.py
"""

from __future__ import annotations

from collections import Counter, defaultdict

from qcommon import FULL, OUT_DIR, annotate, answer_key, families, load, write_json

TOL = 0.02  # the README tolerance for measures


class Checks:
    def __init__(self):
        self.res = {}

    def add(self, name, checked, violations, kind, note=""):
        self.res[name] = {
            "kind": kind,
            "checked": checked,
            "violations": len(violations),
            "rate": round(len(violations) / checked, 5) if checked else None,
            "note": note,
            "examples": violations[:8],
        }


def main() -> None:
    rows = annotate(load(FULL))
    fam = families(rows)
    for r in rows:
        r["_fam"] = fam[(r["_src"], r["_tpl"])]
    C = Checks()

    # ---------------- translation pairs
    groups = defaultdict(list)
    for r in rows:
        if r["_src"] in ("cubicasa5k", "swiss_dwellings", "ifc_models"):
            groups[(r["path"], r["_fam"], r["_sk"])].append(r)
    multi = [g for g in groups.values() if len(g) > 1]
    bad = [
        {"path": g[0]["path"], "answers": {x["_lang"]: x["answer"] for x in g}, "q": g[0]["question"]}
        for g in multi
        if len({answer_key(x) for x in g}) > 1
    ]
    C.add("translation_pair_disagree", len(multi), bad, "hard")
    unpaired = Counter(g[0]["_src"] for g in groups.values() if len(g) == 1)
    C.res["translation_pair_disagree"]["unpaired_items_per_source"] = dict(unpaired)
    C.res["translation_pair_disagree"]["group_sizes"] = dict(Counter(len(g) for g in groups.values()))

    # ---------------- duplicates
    dup = Counter((r["path"], r["question"]) for r in rows)
    d2 = [k for k, v in dup.items() if v > 1]
    C.add("duplicate_path_question", len(dup), [list(k) for k in d2], "hard")

    # Same question text on several files of one ifc model: one answer expected.
    byq = defaultdict(list)
    for r in rows:
        if r["_src"] == "ifc_models":
            model = r["path"].split("/")[-1].split("_plan-")[0].rsplit(".", 1)[0]
            byq[(model, r["question"])].append(r)
    multiq = [v for v in byq.values() if len(v) > 1]
    badq = [
        {"q": v[0]["question"], "answers": sorted({str(x["answer"]) for x in v}), "paths": sorted({x["path"] for x in v})[:3]}
        for v in multiq
        if len({answer_key(x) for x in v}) > 1
    ]
    C.add("ifc_same_question_two_answers", len(multiq), badq, "hard")
    C.res["ifc_same_question_two_answers"]["files_per_repeated_question"] = dict(
        Counter(len(v) for v in multiq)
    )

    # ---------------- value checks
    neg = [r for r in rows if not isinstance(r["answer"], str) and r["answer"] < 0]
    C.add("negative_value", len(rows), [[r["path"], r["question"], r["answer"]] for r in neg], "hard")
    nonint = [r for r in rows if r["type"] == "count" and not isinstance(r["answer"], int)]
    C.add("count_not_integer", sum(r["type"] == "count" for r in rows), [[r["path"], r["answer"]] for r in nonint], "hard")
    zero_meas = [r for r in rows if r["type"] in ("area", "volume", "length") and float(r["answer"]) == 0]
    C.add(
        "measure_zero",
        sum(r["type"] in ("area", "volume", "length") for r in rows),
        [[r["path"], r["question"], r["answer"]] for r in zero_meas],
        "hard",
    )
    lab0 = [
        r
        for r in rows
        if r["_src"] == "swiss_dwellings" and r["type"] == "count" and any(k == "label" for k, _ in r["_slots"])
    ]
    C.add(
        "swiss_label_count_zero",
        len(lab0),
        [[r["path"], r["question"]] for r in lab0 if r["answer"] == 0],
        "hard",
        "The question names a label, so the label exists on the floor; 0 would contradict it.",
    )
    # Zero counts per family (information: questions that presuppose nothing can be 0).
    zc = Counter()
    zn = Counter()
    for r in rows:
        if r["type"] == "count" and r["_lang"] == "en":
            zn[r["_fam"]] += 1
            zc[r["_fam"]] += r["answer"] == 0
    C.res["zero_share_per_family"] = {f: round(zc[f] / zn[f], 4) for f in sorted(zn) if zc[f]}

    # ---------------- per-drawing logic
    per = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["_lang"] == "en" or r["_src"] == "opening_design":
            per[r["path"]][r["_fam"]].append(r)

    def one(d, fam_id):
        v = d.get(fam_id)
        return v[0]["answer"] if v and len(v) == 1 else None

    # cubicasa5k families (ids from templates.json)
    F_FLOORS, F_WIN, F_TOIL, F_SINK, F_SHOW, F_DOOR, F_SAUNA, F_KITCH, F_BED, F_BATH, F_WCROOM, F_BALC = (
        "F:cubicasa5k/T000", "F:cubicasa5k/T001", "F:cubicasa5k/T004", "F:cubicasa5k/T006",
        "F:cubicasa5k/T008", "F:cubicasa5k/T010", "F:cubicasa5k/T012", "F:cubicasa5k/T014",
        "F:cubicasa5k/T016", "F:cubicasa5k/T018", "F:cubicasa5k/T020", "F:cubicasa5k/T022",
    )
    cc = {p: d for p, d in per.items() if p.split("/")[1] == "cubicasa5k"}

    def rel(name, a, b, op, kind, note=""):
        checked, viol = 0, []
        for p, d in cc.items():
            x, y = one(d, a), one(d, b)
            if x is None or y is None:
                continue
            checked += 1
            if op(x, y):
                viol.append([p, x, y])
        C.add(name, checked, viol, kind, note)

    rel("cubicasa_wcrooms_gt_toilets", F_WCROOM, F_TOIL, lambda x, y: x > y, "hard",
        "Each separate WC room holds a toilet bowl.")
    rel("cubicasa_toilets0_but_wcroom", F_TOIL, F_WCROOM, lambda x, y: x == 0 and y > 0, "hard")
    rel("cubicasa_bathrooms_gt_showers_tubs", F_BATH, F_SHOW, lambda x, y: x > y, "soft",
        "A bathroom without a shower or tub is rare.")
    rel("cubicasa_kitchens_gt_sinks", F_KITCH, F_SINK, lambda x, y: x > y, "soft",
        "A kitchen without a sink is rare.")
    floors0 = [[p, one(d, F_FLOORS)] for p, d in cc.items() if one(d, F_FLOORS) == 0]
    C.add("cubicasa_floors_zero", sum(one(d, F_FLOORS) is not None for d in cc.values()), floors0, "hard")
    win0 = [[p] for p, d in cc.items() if one(d, F_WIN) == 0]
    C.add("cubicasa_windows_zero", sum(one(d, F_WIN) is not None for d in cc.values()), win0, "soft")
    # toilets vs wc rooms + bathrooms: more bowls than WC rooms + bathrooms + 1 is odd
    chk, viol = 0, []
    for p, d in cc.items():
        t, w, b = one(d, F_TOIL), one(d, F_WCROOM), one(d, F_BATH)
        if None in (t, w, b):
            continue
        chk += 1
        if t > w + b + 1:
            viol.append([p, t, w, b])
    C.add("cubicasa_toilets_gt_wcrooms_plus_bathrooms_plus1", chk, viol, "soft")
    # Which cubicasa questions are skipped, by plan: presence pattern.
    present = Counter(frozenset(f for f in d) for d in cc.values())
    # Presence rate of each family per cubicasa sub-collection: the generator skips questions.
    coll = lambda p: p.split("/")[-1].rsplit("-", 1)[0]
    n_coll = Counter(coll(p) for p in cc)
    pres = defaultdict(Counter)
    for p, d in cc.items():
        for f in d:
            pres[f][coll(p)] += 1
    C.res["cubicasa_presence_rate_by_collection"] = {
        "plans": dict(n_coll),
        "rate": {f: {c: round(v[c] / n_coll[c], 3) for c in n_coll} for f, v in sorted(pres.items())},
    }
    C.res["cubicasa_family_presence_patterns"] = len(present)

    # swiss_dwellings
    S_LCOUNT, S_ROOMA, S_APTA, S_APTS, S_TOTAL, S_LAREA = (
        "F:swiss_dwellings/T000", "F:swiss_dwellings/T002", "F:swiss_dwellings/T003",
        "F:swiss_dwellings/T007", "F:swiss_dwellings/T012", "F:swiss_dwellings/T013",
    )
    sw = {p: d for p, d in per.items() if p.split("/")[1] == "swiss_dwellings"}

    def label(r):
        return next(v for k, v in r["_slots"] if k == "label")

    chk_a, va, chk_b, vb, chk_c, vc, chk_d, vd, chk_e, ve, chk_f, vf = 0, [], 0, [], 0, [], 0, [], 0, [], 0, []
    for p, d in sw.items():
        lcount = {label(r): r["answer"] for r in d.get(S_LCOUNT, [])}
        larea = {label(r): float(r["answer"]) for r in d.get(S_LAREA, [])}
        rooms = defaultdict(list)
        for r in d.get(S_ROOMA, []):
            rooms[label(r)].append(float(r["answer"]))
        # (a) a single room larger than its label total
        for lab, areas in rooms.items():
            if lab in larea:
                chk_a += 1
                if max(areas) > larea[lab] * (1 + TOL):
                    va.append([p, lab, max(areas), larea[lab]])
                # (b) the asked rooms of a label sum to more than the label total
                chk_b += 1
                if sum(areas) > larea[lab] * (1 + TOL):
                    vb.append([p, lab, round(sum(areas), 2), larea[lab], len(areas), lcount.get(lab)])
                # (c) all rooms of the label asked: the sum must match the total
                if lab in lcount and len(areas) == lcount[lab]:
                    chk_c += 1
                    if abs(sum(areas) - larea[lab]) > larea[lab] * TOL:
                        vc.append([p, lab, round(sum(areas), 2), larea[lab], lcount[lab]])
            # (d) more rooms asked with this label than the label count
            if lab in lcount:
                chk_d += 1
                if len(set(areas)) > lcount[lab] and len(areas) > lcount[lab]:
                    vd.append([p, lab, len(areas), lcount[lab]])
        total = one(d, S_TOTAL)
        apts = {next(v for k, v in r["_slots"] if k == "apt_id"): float(r["answer"]) for r in d.get(S_APTA, [])}
        napts = one(d, S_APTS)
        if total is not None and apts:
            chk_e += 1
            if sum(apts.values()) > float(total) * (1 + TOL):
                ve.append([p, round(sum(apts.values()), 2), total, len(apts), napts])
        if napts is not None and apts:
            chk_f += 1
            if len(apts) > napts:
                vf.append([p, sorted(apts), napts])
        # room or label total larger than the floor total
    C.add("swiss_room_gt_label_total", chk_a, va, "hard")
    C.add("swiss_rooms_sum_gt_label_total", chk_b, vb, "hard")
    C.add("swiss_all_rooms_asked_sum_ne_label_total", chk_c, vc, "hard")
    C.add("swiss_more_rooms_asked_than_label_count", chk_d, vd, "hard")
    C.add("swiss_apartments_sum_gt_floor_total", chk_e, ve, "hard",
          "Floor total: numbered indoor rooms without outdoor, shafts, voids. Apartment: rooms without outdoor.")
    C.add("swiss_more_apartment_ids_than_apartment_count", chk_f, vf, "hard")
    # Share of floor total covered by apartments, to see what the floor total includes.
    cover = []
    for p, d in sw.items():
        total = one(d, S_TOTAL)
        apts = [float(r["answer"]) for r in d.get(S_APTA, [])]
        napts = one(d, S_APTS)
        if total and apts and napts == len(apts):
            cover.append(sum(apts) / float(total))
    cover.sort()
    if cover:
        C.res["swiss_apartments_over_floor_total_when_all_asked"] = {
            "n": len(cover),
            "p05": round(cover[len(cover) // 20], 4),
            "median": round(cover[len(cover) // 2], 4),
            "p95": round(cover[len(cover) * 19 // 20], 4),
            "share_gt_1.02": round(sum(c > 1.02 for c in cover) / len(cover), 4),
        }
    # Soft: toilets vs washbasins, apartments vs bathtubs+showers
    S_WC, S_WB, S_TUB, S_SHOWER = (
        "F:swiss_dwellings/T009", "F:swiss_dwellings/T010", "F:swiss_dwellings/T014", "F:swiss_dwellings/T026",
    )
    chk, viol = 0, []
    for p, d in sw.items():
        a, wc = one(d, S_APTS), one(d, S_WC)
        if a is None or wc is None:
            continue
        chk += 1
        if wc < a:
            viol.append([p, a, wc])
    C.add("swiss_fewer_toilets_than_apartments", chk, viol, "soft", "An apartment without a toilet is rare.")
    chk, viol = 0, []
    for p, d in sw.items():
        a = one(d, S_APTS)
        if a is None:
            continue
        chk += 1
        if a == 0:
            viol.append([p])
    C.add("swiss_apartments_zero", chk, viol, "hard")

    # ifc_models: rooms vs storey total; storey counts vs model counts
    im = defaultdict(lambda: defaultdict(list))  # (model, storey) -> family -> rows
    for r in rows:
        if r["_src"] != "ifc_models" or r["_lang"] != "en":
            continue
        model = r["path"].split("/")[-1].split("_plan-")[0].rsplit(".", 1)[0]
        storey = next((v for k, v in r["_slots"] if k == "storey"), None)
        im[(model, storey)][r["_fam"]].append(r)
    chk, viol = 0, []
    for (model, storey), d in im.items():
        tot = d.get("F:ifc_models/T008")
        rooms = d.get("F:ifc_models/T000", [])
        if tot and rooms:
            chk += 1
            s = sum(float(r["answer"]) for r in rooms)
            if s > float(tot[0]["answer"]) * (1 + TOL):
                viol.append([model, storey, round(s, 2), tot[0]["answer"], len(rooms)])
    C.add("ifc_rooms_sum_gt_storey_total", chk, viol, "hard")
    # room count on plan vs number of distinct rooms asked
    chk, viol = 0, []
    for (model, storey), d in im.items():
        cnt = d.get("F:ifc_models/T006")
        rooms = {next(v for k, v in r["_slots"] if k == "room") for r in d.get("F:ifc_models/T000", [])}
        if cnt and rooms:
            chk += 1
            if len(rooms) > cnt[0]["answer"]:
                viol.append([model, storey, len(rooms), cnt[0]["answer"]])
    C.add("ifc_more_rooms_asked_than_room_count", chk, viol, "hard")
    # Sum of per-storey counts vs model-wide count (same element class).
    pairs = {
        "doors": ("F:ifc_models/T007", "F:ifc_models/T025"),
        "windows": ("F:ifc_models/T017", "F:ifc_models/T024"),
        "rooms": ("F:ifc_models/T006", "F:ifc_models/T016"),
        "walls": ("F:ifc_models/T014", "F:ifc_models/T018"),
        "stairs": ("F:ifc_models/T010", "F:ifc_models/T029"),
        "columns": ("F:ifc_models/T015", "F:ifc_models/T030"),
    }
    out = {}
    for name, (fs, fm) in pairs.items():
        models = defaultdict(lambda: {"storeys": {}, "model": None})
        for (model, storey), d in im.items():
            if d.get(fs):
                models[model]["storeys"][storey] = d[fs][0]["answer"]
            if d.get(fm):
                models[model]["model"] = d[fm][0]["answer"]
        cmp = []
        for model, v in models.items():
            if v["model"] is not None and v["storeys"]:
                cmp.append([model, sum(v["storeys"].values()), v["model"], len(v["storeys"])])
        out[name] = cmp
    C.res["ifc_storey_sum_vs_model_count"] = {
        "kind": "info",
        "note": "Storeys with a question may be a subset of all storeys, so sum < model is not a violation; sum > model is.",
        "rows": out,
        "sum_gt_model": sum(1 for v in out.values() for m in v if m[1] > m[2]),
        "sum_eq_model": sum(1 for v in out.values() for m in v if m[1] == m[2]),
        "compared": sum(len(v) for v in out.values()),
    }

    # Per-source summary of hard violations.
    write_json(OUT_DIR / "consistency.json", C.res)
    for k, v in C.res.items():
        if isinstance(v, dict) and "violations" in v:
            print(f"{k}: {v['violations']}/{v['checked']} ({v['kind']})")


if __name__ == "__main__":
    main()
