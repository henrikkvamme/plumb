# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Reproduce Stoa's cubicasa5k reference answers from the public CubiCasa5K model.svg.

Inputs: out/svg_features.json (svg_features.py) and out/presence.json (templates.py).
For each template, evaluates several candidate rules on EVERY plan that has the template
(not a sample) and reports exact-match agreement, plus up to 8 disagreements for the best rule.
Also tests the presence (filter) rules. Writes out/count_rules.json.
"""
import collections
import json
import pathlib

OUT = pathlib.Path(__file__).parent / "out"
F = json.load(open(OUT / "svg_features.json"))
P = {k.split("/")[-1]: v for k, v in json.load(open(OUT / "presence.json")).items()}


def cnt(counter, names):
    return sum(counter.get(n, 0) for n in names)


def pref(counter, prefix):
    return sum(n for c, n in counter.items() if c == prefix or c.startswith(prefix + " "))


def labels(v, cls):
    return [l.upper() for c, l in v["space_labels"] if c == cls]


SINKS = ["FixedFurniture Sink", "FixedFurniture RoundSink", "FixedFurniture DoubleSink",
         "FixedFurniture DoubleSinkRight", "FixedFurniture SideSink", "FixedFurniture CornerSink"]
SHOWERS = ["FixedFurniture Shower", "FixedFurniture ShowerCab", "FixedFurniture ShowerPlatform"]
TUBS = ["FixedFurniture Bathtub", "FixedFurniture BathtubRound"]
STOVES = ["FixedFurniture ElectricalAppliance SaunaStove", "FixedFurniture ElectricalAppliance SaunaStoveRound",
          "FixedFurniture ElectricalAppliance SaunaStove Round", "FixedFurniture SaunaStove"]

RULES = {
    "floors": {
        "floorplan_groups": lambda v: len(v["floorplans"]),
        "floorplan_groups_no_basement": lambda v: sum(1 for f in v["floorplans"] if "Basement" not in f),
    },
    "windows": {
        "all_window_classes": lambda v: sum(v["windows"].values()),
        "regular_only": lambda v: v["windows"].get("Window Regular", 0),
    },
    "doors": {
        "all_door_classes": lambda v: sum(v["doors"].values()),
        "all_minus_none": lambda v: sum(n for c, n in v["doors"].items() if c != "Door None Beside"),
        "swing_only": lambda v: cnt(v["doors"], ["Door Swing Beside", "Door Swing Opposite"]),
        "panels_total": lambda v: sum(p for c, p in v["door_panels"]),
    },
    "toilets": {
        "toilet": lambda v: v["furniture"].get("FixedFurniture Toilet", 0),
        "toilet_plus_urinal": lambda v: cnt(v["furniture"], ["FixedFurniture Toilet", "FixedFurniture Urinal"]),
    },
    "sinks": {
        "all_sink_classes": lambda v: cnt(v["furniture"], SINKS),
        "sink_round_double": lambda v: cnt(v["furniture"], SINKS[:4]),
        "double_counts_two": lambda v: cnt(v["furniture"], SINKS) + cnt(v["furniture"], SINKS[2:4]),
    },
    "showers_tubs": {
        "shower_cab_platform_tub": lambda v: cnt(v["furniture"], SHOWERS + TUBS),
        "shower_tub": lambda v: cnt(v["furniture"], ["FixedFurniture Shower"] + TUBS),
        "plus_jacuzzi": lambda v: cnt(v["furniture"], SHOWERS + TUBS + ["FixedFurniture Jacuzzi"]),
        "showers_only": lambda v: cnt(v["furniture"], SHOWERS),
    },
    "saunas": {
        "space_sauna": lambda v: v["spaces"].get("Space Sauna", 0),
        "sauna_stoves": lambda v: cnt(v["furniture"], STOVES),
        "stoves_capped_by_benchsets": lambda v: min(cnt(v["furniture"], STOVES), max(1, v["furniture"].get("FixedFurniture SaunaBenchMid", 0))) if cnt(v["furniture"], STOVES) else 0,
    },
    "bedrooms": {
        "space_bedroom": lambda v: pref(v["spaces"], "Space Bedroom"),
        "space_bedroom_exact": lambda v: v["spaces"].get("Space Bedroom", 0),
    },
    "kitchens": {
        "space_kitchen_all": lambda v: pref(v["spaces"], "Space Kitchen"),
        "kitchen_no_scullery": lambda v: pref(v["spaces"], "Space Kitchen") - v["spaces"].get("Space Kitchen Scullery", 0),
    },
    "bathrooms": {
        "bath_nonwc_plus_bathshower": lambda v: sum(1 for l in labels(v, "Space Bath") if l != "WC") + v["spaces"].get("Space Bath Shower", 0),
        "bath_all_plus_shower": lambda v: v["spaces"].get("Space Bath", 0) + v["spaces"].get("Space Bath Shower", 0),
        "bath_nonwc_only": lambda v: sum(1 for l in labels(v, "Space Bath") if l != "WC"),
    },
    "wc_rooms": {
        "bath_labelled_wc": lambda v: sum(1 for l in labels(v, "Space Bath") if l == "WC"),
    },
    "balconies": {
        "balcony_all": lambda v: pref(v["spaces"], "Space Outdoor Balcony"),
        "balcony_exact": lambda v: v["spaces"].get("Space Outdoor Balcony", 0),
        "balcony_plus_terrace": lambda v: pref(v["spaces"], "Space Outdoor Balcony") + pref(v["spaces"], "Space Outdoor Terrace"),
    },
}


def main():
    res = {}
    for t, rules in RULES.items():
        keys = [k for k in F if t in P[k]]
        out = {"n": len(keys), "rules": {}}
        best = None
        for name, fn in rules.items():
            hits = 0
            dis = []
            off = collections.Counter()
            for k in keys:
                pred = fn(F[k])
                ref = P[k][t]
                if pred == ref:
                    hits += 1
                else:
                    off[pred - ref] += 1
                    if len(dis) < 8:
                        dis.append({"file": k, "rule": pred, "ref": ref, "split": F[k]["split"]})
            acc = hits / len(keys)
            out["rules"][name] = {"agree": round(acc, 4), "offsets": dict(off.most_common(6)), "disagreements": dis}
            if best is None or acc > best[1]:
                best = (name, acc)
        out["best"] = best
        res[t] = out
    json.dump(res, open(OUT / "count_rules.json", "w"), indent=1)
    for t, o in res.items():
        print(t, o["n"], o["best"][0], round(o["best"][1], 4))


if __name__ == "__main__":
    main()
