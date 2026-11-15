# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Probe: answer every swiss_dwellings question from the DXF features alone, and score against the reference.

Needs dxf_features.json (uv run dxf_features.py) and rows.json (uv run templates.py).
Variants per family test which convention the generator used. Writes probe_dxf.json with agreement per
family and variant, plus up to 8 disagreements for the main variant.
Usage: uv run probe_dxf.py
"""
import json, pathlib, collections, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from qparse import parse, OUTDOOR

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "data/external/swiss-derived"
F = json.load(open(OUT / "dxf_features.json"))
rows = json.load(open(OUT / "rows.json"))


def fx_count(f, pred):
    return sum(1 for g in f["fixtures"] if pred(g["sig"], g))


def is_wc(s, g):
    return s == "P2+P48"


def is_basin(s, g):
    return s.startswith("C0.0") and s.endswith("+P48") and not s.startswith("C0.08")


def is_basin_small(s, g):
    return s in ("C0.03+P48", "C0.02+P48")


def is_tub(s, g):
    return "P69" in s


def is_shower(s, g):
    return s.endswith("P5") and "C0.0" in s


def m2(label):
    return label is not None and label.endswith("m²")


def rooms_by(f, pred):
    return [r for r in f["rooms"] if pred(r)]


def area_total(f, excl_outdoor=True, excl_m2=False, excl_lift_stair=False):
    s = 0.0
    for r in f["rooms"]:
        lab = r["label"]
        if r["area"] is None:
            continue
        if excl_outdoor and lab in OUTDOOR:
            continue
        if excl_m2 and m2(lab):
            continue
        if excl_lift_stair and lab in {"Lift", "Ascenseur", "Ascensore", "Treppenhaus", "Cage d'escalier", "Vano scala"}:
            continue
        s += r["area"]
    return round(s, 2)


def area_apartment(f, letter, mode="text"):
    s, n = 0.0, 0
    for r in f["rooms"]:
        if r["unit"] == letter and r["label"] not in OUTDOOR and r["area"] is not None:
            s += r["area"]
            n += 1
    return round(s, 2) if n else None


VARIANTS = {
    "count_label": {
        "exact_label": lambda f, p: sum(1 for r in f["rooms"] if r["label"] == p),
    },
    "apartments": {
        "unit_outline_polys": lambda f, p: f["n_unit_polys"],
        "unit_texts": lambda f, p: len(f["unit_texts"]),
    },
    "doors": {
        "door_polyline5": lambda f, p: f["door_sig"].get("LWPOLYLINE5", 0),
        "door_unique_arcs": lambda f, p: f["door_unique_arcs"],
    },
    "windows": {
        "window_closed_rect": lambda f, p: f["window_sig"].get("LWPOLYLINE4c", 0),
        "window_rect_any": lambda f, p: f["window_sig"].get("LWPOLYLINE4c", 0) + f["window_sig"].get("LWPOLYLINE4", 0),
    },
    "toilets": {"wc_sig": lambda f, p: fx_count(f, is_wc)},
    "washbasins": {
        "basin_any_drain": lambda f, p: fx_count(f, is_basin),
        "basin_small_drain": lambda f, p: fx_count(f, is_basin_small),
    },
    "bathtubs": {"tub_sig": lambda f, p: fx_count(f, is_tub)},
    "showers": {"shower_sig": lambda f, p: fx_count(f, is_shower)},
    "area_room": {
        "poly_containing_number": lambda f, p: next((round(r["area"], 2) for r in f["rooms"] if r["num"] == p and r["area"] is not None), None),
    },
    "area_label": {
        "sum_label": lambda f, p: round(sum(r["area"] for r in f["rooms"] if r["label"] == p and r["area"]), 2),
    },
    "area_total": {
        "numbered_minus_outdoor": lambda f, p: area_total(f),
        "numbered_all": lambda f, p: area_total(f, excl_outdoor=False),
        "minus_outdoor_minus_liftstair": lambda f, p: area_total(f, excl_lift_stair=True),
    },
    "area_apartment": {
        "rooms_in_unit_minus_outdoor": lambda f, p: area_apartment(f, p),
    },
}


def ok(pred, ans, typ):
    if pred is None:
        return False
    if typ == "count":
        return int(round(pred)) == int(ans)
    return abs(pred - ans) <= 0.02 * abs(ans) + 1e-9


res = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
fails = collections.defaultdict(list)
floor_fail = collections.defaultdict(set)
for r in rows:
    fam, p, lang = parse(r["question"])
    floor = pathlib.Path(r["path"]).stem
    f = F[floor]
    for i, (vn, fn) in enumerate(VARIANTS[fam].items()):
        try:
            pred = fn(f, p)
        except Exception as ex:
            pred = None
        good = ok(pred, r["answer"], r["type"])
        res[fam][vn][0] += good
        res[fam][vn][1] += 1
        if i == 0 and not good:
            floor_fail[fam].add(floor)
            if len(fails[fam]) < 8:
                fails[fam].append({"floor": floor, "q": r["question"][:90], "ref": r["answer"], "pred": pred})

summary = {}
for fam, v in res.items():
    summary[fam] = {vn: {"agree": a, "n": n, "rate": round(a / n, 4)} for vn, (a, n) in v.items()}
    summary[fam]["_floors_with_any_miss_main"] = len(floor_fail[fam])
tot = sum(list(v.values())[0][0] for v in res.values())
n = sum(list(v.values())[0][1] for v in res.values())
best = sum(max(x[0] for x in v.values()) for v in res.values())
out = {"overall_main_variant": round(tot / n, 4), "overall_best_variant": round(best / n, 4), "n": n, "families": summary, "disagreements": fails}
json.dump(out, open(OUT / "probe_dxf.json", "w"), indent=1, ensure_ascii=False)
print("overall main", out["overall_main_variant"], "best", out["overall_best_variant"], "n", n)
for fam, v in summary.items():
    print(fam, {k: (x["rate"] if isinstance(x, dict) else x) for k, x in v.items()})
