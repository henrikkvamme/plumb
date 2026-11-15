"""How a detector does on drawing styles: the Stoa PNGs of the Swiss VAL floors and the synthetic test images.

    uv run python jobs/cubicasa-detect/eval_styles.py <model dir> [--limit N] [--out file.json]

For each style family it reports, for doors and windows:
- recall and precision of the boxes (a detection matches a label when IoU >= 0.3),
- the share of images with the exact count,
- the share of rooms with the exact count, when each box goes to the rooms it touches (`rooms_of`). The rooms are
  the true polygons here, so this number isolates the detector and the touch rule from the room finder.
`rule` is the same room count from the true boxes: the ceiling that the touch rule allows.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from shapely.geometry import Polygon, box

from bp.tools.symbol_detector import Detector, load_rgb

HERE = Path(__file__).resolve().parent
STOA = HERE.parents[1]
SWISS = STOA / "data" / "junction-dataset" / "data" / "swiss_dwellings"
TEST = STOA / "data" / "styles-test"
IOU = 0.3
REACH_M = 0.10  # a box touches a room when the box, grown by this, overlaps the room
MIN_OVERLAP_M2 = 0.02


def iou(a: list[float], b: list[float]) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    inter = w * h
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def match(found: list[list[float]], truth: list[list[float]]) -> int:
    used: set[int] = set()
    hits = 0
    for f in found:
        best = max(((iou(f, t), i) for i, t in enumerate(truth) if i not in used), default=(0.0, -1))
        if best[0] >= IOU:
            used.add(best[1])
            hits += 1
    return hits


def rooms_of(boxes: list[list[float]], rooms: list[Polygon], ppm: float) -> list[int]:
    """For each room: how many boxes touch it."""
    reach, least = REACH_M * ppm, MIN_OVERLAP_M2 * ppm * ppm
    grown = [box(b[0] - reach, b[1] - reach, b[2] + reach, b[3] + reach) for b in boxes]
    return [sum(1 for g in grown if g.intersects(r) and g.intersection(r).area >= least) for r in rooms]


def one(detector: Detector, path: Path, lab: dict, thresholds: dict[str, float]) -> dict:
    found = detector.detect(load_rgb(path))
    rooms = [Polygon(r["polygon"]).buffer(0) for r in lab["rooms"]]
    row: dict = {"family": lab["family"], "door_style": lab.get("door_style", "arc_leaf")}
    for cls, key, ids in (("door", "door_boxes", "door_ids"), ("window", "window_boxes", "window_ids")):
        truth = lab[key]
        got = [list(d.box) for d in found if d.label == cls and d.score >= thresholds[cls]]
        per_room = rooms_of(got, rooms, lab["ppm"])
        rule = rooms_of(truth, rooms, lab["ppm"])
        want = [len(r[ids]) for r in lab["rooms"]]
        row[cls] = {
            "truth": len(truth), "found": len(got), "hits": match(got, truth), "exact": len(got) == len(truth),
            "rooms": len(rooms), "rooms_exact": sum(1 for a, b in zip(per_room, want, strict=True) if a == b),
            "rule_exact": sum(1 for a, b in zip(rule, want, strict=True) if a == b),
        }  # fmt: skip
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    detector = Detector.get(Path(args.model))
    calib = detector.meta.get("calibration", {})
    thresholds = {"door": float(calib.get("doors", {}).get("threshold", 0.5)),
                  "window": float(calib.get("windows", {}).get("threshold", 0.5))}  # fmt: skip
    jobs: list[tuple[Path, dict]] = []
    real = json.loads((HERE / "data" / "real-labels.json").read_text())
    jobs += [(SWISS / f"{k}.png", v) for k, v in sorted(real.items()) if v["partition"] == "val"][: args.limit or None]
    syn = json.loads((TEST / "labels.json").read_text())
    jobs += [(TEST / f"{k}.png", v) for k, v in sorted(syn.items())][: 3 * args.limit or None]
    with ThreadPoolExecutor(4) as pool:
        rows = list(pool.map(lambda j: one(detector, j[0], j[1], thresholds), jobs))
    table: dict[str, dict] = {}
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["door_style"] == "gap":  # a gap with no leaf is not a door; it would count against the detector
            continue
        groups[r["family"]].append(r)
        groups["held-out styles" if r["family"] in ("blueprint", "sketch") else
               "stoa" if r["family"] == "stoa" else "known styles"].append(r)  # fmt: skip
    for family, items in sorted(groups.items()):
        out: dict = {"images": len(items)}
        for cls in ("door", "window"):
            t = {k: sum(i[cls][k] for i in items) for k in ("truth", "found", "hits", "rooms", "rooms_exact", "rule_exact")}
            out[cls] = {
                "recall": round(t["hits"] / max(1, t["truth"]), 3), "precision": round(t["hits"] / max(1, t["found"]), 3),
                "count_exact": round(sum(i[cls]["exact"] for i in items) / len(items), 3),
                "rooms_exact": round(t["rooms_exact"] / max(1, t["rooms"]), 3),
                "rule": round(t["rule_exact"] / max(1, t["rooms"]), 3),
            }  # fmt: skip
        table[family] = out
        print(family, json.dumps(out), flush=True)
    if args.out:
        Path(args.out).write_text(json.dumps({"model": args.model, "thresholds": thresholds, "families": table}, indent=1))


if __name__ == "__main__":
    main()
