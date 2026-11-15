"""The `styles` suite: questions on the synthetic test images (VAL floors in known and in held-out styles).

    uv run python jobs/cubicasa-detect/build_suite.py [--floors 40]

It tests whether the raster tools hold on a drawing style they did not see: the keys come from the vector floor,
so they are exact in each style. `Item.condition` is the style family. A question is only asked when the image
shows what it needs (a room number is asked only when the numbers are drawn).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from bp.contract import CountKey, Item, LookupKey, MeasureKey
from bp.suites import write_items

HERE = Path(__file__).resolve().parent
TEST = HERE.parents[1] / "data" / "styles-test"
OUTDOOR = {"BALCONY", "LOGGIA", "TERRACE"}
NAMES = {"KITCHEN": "kitchen", "BATHROOM": "bathroom", "BEDROOM": "bedroom"}


def pick(seq: list, salt: str) -> object:
    return min(seq, key=lambda v: hashlib.sha256(f"{salt}:{v}".encode()).hexdigest())


def questions(name: str, lab: dict) -> list[tuple[str, str, object, str]]:  # noqa: C901, PLR0912
    """(family, question, key, cell) for one image."""
    out: list[tuple[str, str, object, str]] = []
    rooms = lab["rooms"]
    numbers, labels = lab["text"] in ("all", "number"), lab["text"] in ("all", "label")
    doors = lab["door_style"] != "gap"
    indoor = [r for r in rooms if r["subtype"] not in OUTDOOR]
    if doors:
        out.append(("count_doors", "How many doors are drawn on this plan? Count each door opening once.",
                    CountKey(value=len(lab["door_boxes"])), "count/raster"))  # fmt: skip
    out.append(("count_windows", "How many windows are drawn on this plan?",
                CountKey(value=len(lab["window_boxes"])), "count/raster"))  # fmt: skip
    toilets = sum(1 for b in lab["boxes"] if b[0] == "toilet")
    if toilets:
        out.append(("count_toilets", "How many toilets are drawn on this plan?", CountKey(value=toilets),
                    "count/raster"))  # fmt: skip
    if numbers and doors:
        r = pick(rooms, name + "d")
        out.append(("doors_to_room", f"How many doors open into room {r['number']}? Count each door opening once.",
                    CountKey(value=len(r["door_ids"])), "count/raster"))  # fmt: skip
    if numbers:
        r = pick(indoor or rooms, name + "w")
        out.append(("windows_of_room", f"How many windows does room {r['number']} have?",
                    CountKey(value=len(r["window_ids"])), "count/raster"))  # fmt: skip
    if labels:
        for subtype, word in NAMES.items():
            mine = [r for r in rooms if r["subtype"] == subtype]
            if not mine:
                continue
            if subtype == "BEDROOM":
                out.append(("bedrooms_with_window", "How many bedrooms on this plan have at least one window?",
                            CountKey(value=sum(1 for r in mine if r["window_ids"])), "count/raster"))  # fmt: skip
            if subtype == "BATHROOM":
                out.append(("bathrooms_without_window", "How many bathrooms on this plan have no window?",
                            CountKey(value=sum(1 for r in mine if not r["window_ids"])), "count/raster"))  # fmt: skip
            if len(mine) == 1 and doors and subtype == "KITCHEN":
                out.append(("doors_to_named_room", f"How many doors lead into the {word} on this plan? Count each "
                            "door opening once.", CountKey(value=len(mine[0]["door_ids"])), "count/raster"))  # fmt: skip
    if lab["text"] == "all":
        r = pick(rooms, name + "a")
        out.append(("printed_area", f"What is the floor area of room {r['number']} in square metres?",
                    MeasureKey(value=round(r["area_m2"], 2), unit="m2", tolerance=0.02, decimals=1), "measure/raster"))  # fmt: skip
        big = sorted(indoor, key=lambda r: -r["area_m2"])
        if len(big) > 1 and big[0]["area_m2"] > 1.1 * big[1]["area_m2"]:
            out.append(("largest_room", "Which room on this plan has the largest floor area? Give its room number. "
                        "Do not count balconies, loggias or terraces.", LookupKey(accepted=(big[0]["number"],)),
                        "lookup/raster"))  # fmt: skip
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--floors", type=int, default=40)
    args = parser.parse_args()
    labels = json.loads((TEST / "labels.json").read_text())
    stems = sorted({v["stem"] for v in labels.values()}, key=lambda s: hashlib.sha256(s.encode()).hexdigest())
    chosen = set(stems[: args.floors])
    items = []
    for name, lab in sorted(labels.items()):
        if lab["stem"] not in chosen:
            continue
        for family, text, key, cell in questions(name, lab):
            ident = hashlib.sha256(f"styles:{name}:{family}".encode()).hexdigest()[:14]
            items.append(Item(
                item_id=f"s-{ident}", doc=f"../styles-test/{name}.png", question=text, key=key,
                source="synthetic_styles", family=family, group=f"swiss:{lab['stem'].split('_')[0]}", cell=cell,
                suite="styles", condition=lab["family"], partition="val", origin="synthetic",
            ))  # fmt: skip
    path = write_items("styles", items)
    print(path, len(items), "items", len({i.doc for i in items}), "images")
    print(dict(Counter(i.family for i in items)))
    print(dict(Counter(i.condition for i in items)))


if __name__ == "__main__":
    main()
