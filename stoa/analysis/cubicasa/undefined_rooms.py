# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""How many room-type answers are 0 only because the annotator left every room 'Space Undefined'?

A plan is 'untyped' when every indoor Space is Space Undefined (Outdoor spaces ignored).
For each room template, counts asked questions on untyped plans and their answers.
Writes out/undefined_rooms.json.
"""
import collections
import json
import pathlib

OUT = pathlib.Path(__file__).parent / "out"
F = json.load(open(OUT / "svg_features.json"))
P = {k.split("/")[-1]: v for k, v in json.load(open(OUT / "presence.json")).items()}


def indoor(v):
    return {c: n for c, n in v["spaces"].items() if not c.startswith("Space Outdoor")}


def main():
    untyped = [k for k, v in F.items() if indoor(v) and set(indoor(v)) == {"Space Undefined"}]
    share_undef = {k: v["spaces"].get("Space Undefined", 0) / max(1, sum(indoor(v).values())) for k, v in F.items()}
    res = {"untyped_plans": len(untyped), "examples": untyped[:12], "per_template": {}}
    for t in ("bedrooms", "kitchens", "bathrooms", "wc_rooms", "balconies", "saunas"):
        asked = [k for k in untyped if t in P[k]]
        res["per_template"][t] = {"asked_on_untyped": len(asked),
                                  "answers": dict(collections.Counter(P[k][t] for k in asked)),
                                  "zero_answers_total": sum(1 for k in P if P[k].get(t) == 0),
                                  "zero_on_untyped": sum(1 for k in asked if P[k][t] == 0)}
    json.dump(res, open(OUT / "undefined_rooms.json", "w"), indent=1)
    print(json.dumps(res["per_template"]), res["untyped_plans"])


if __name__ == "__main__":
    main()
