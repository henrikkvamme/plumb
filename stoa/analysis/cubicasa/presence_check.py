# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Score explicit presence (filter) rules per template against which questions Stoa asked.

Inputs: out/svg_features.json, out/presence.json, out/fixture_tokens.json (presence_geometry.py).
Writes out/presence_check.json: agreement of each rule over all 4,787 plans.
"""
import collections
import json
import pathlib

OUT = pathlib.Path(__file__).parent / "out"
F = json.load(open(OUT / "svg_features.json"))
P = {k.split("/")[-1]: v for k, v in json.load(open(OUT / "presence.json")).items()}
T = {k: set(v) for k, v in json.load(open(OUT / "fixture_tokens.json")).items()}


def ud(v):
    return v["spaces"].get("Space UserDefined", 0) > 0


def in_rooms(k, fixture, ok_prefixes):
    """True when every token of this fixture sits in a room whose class starts with one of ok_prefixes."""
    toks = [t for t in T[k] if t.split("@")[0] == fixture]
    return all(any(t.split("@")[1].startswith(p) for p in ok_prefixes) for t in toks)


RULES = {
    "doors": lambda k, v: not any(v["doors"].get(c, 0) for c in ("Door None Beside", "Door RollUp Beside", "Door ParallelSlide Beside")),
    "bedrooms": lambda k, v: not ud(v) and not v["spaces"].get("Space Room"),
    "kitchens": lambda k, v: not ud(v) and in_rooms(k, "ElectricalAppliance IntegratedStove", ["Space Kitchen"]),
    "bathrooms": lambda k, v: not ud(v) and in_rooms(k, "Shower", ["Space Bath"]) and in_rooms(k, "Bathtub", ["Space Bath"]),
    "bathrooms+no_generic_saunabench": lambda k, v: not ud(v) and in_rooms(k, "Shower", ["Space Bath"]) and in_rooms(k, "Bathtub", ["Space Bath"]) and not v["furniture"].get("FixedFurniture SaunaBench"),
    "wc_rooms": lambda k, v: not ud(v) and in_rooms(k, "Toilet", ["Space Bath"]),
    "wc_rooms+no_generic_saunabench": lambda k, v: not ud(v) and in_rooms(k, "Toilet", ["Space Bath"]) and not v["furniture"].get("FixedFurniture SaunaBench"),
    "saunas": lambda k, v: not ud(v) and not v["furniture"].get("FixedFurniture ElectricalAppliance SaunaStove Round")
    and all(in_rooms(k, b, ["Space Undefined", "Space Sauna"]) for b in ("SaunaBench", "SaunaBenchMid", "SaunaBenchHigh", "SaunaBenchLow")),
    "balconies": lambda k, v: not ud(v) and not v["spaces"].get("Space Outdoor"),
    "showers_tubs": lambda k, v: not v["furniture"].get("FixedFurniture Jacuzzi") and "OVERLAP:Bathtub+Shower" not in T[k],
    "sinks": lambda k, v: not v["furniture"].get("FixedFurniture WaterTap"),
}


def main():
    res = {}
    for t, rule in RULES.items():
        c = collections.Counter()
        ex = collections.defaultdict(list)
        for k, v in F.items():
            pred, act = rule(k, v), t.split("+")[0] in P[k]
            c[(pred, act)] += 1
            if pred != act and len(ex[f"pred={pred}"]) < 5:
                ex[f"pred={pred}"].append(k)
        res[t] = {"agree": round((c[(True, True)] + c[(False, False)]) / len(F), 4),
                  "pred_ask_actual_skip": c[(True, False)], "pred_skip_actual_ask": c[(False, True)],
                  "examples": ex}
    json.dump(res, open(OUT / "presence_check.json", "w"), indent=1)
    for t, r in res.items():
        print(t, r["agree"], r["pred_ask_actual_skip"], r["pred_skip_actual_ask"])


if __name__ == "__main__":
    main()
