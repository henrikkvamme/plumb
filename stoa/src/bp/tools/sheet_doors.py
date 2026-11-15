"""Door leaves of a large sheet from the trained detector (`jobs/sheet-doors`).

The detector finds each swing door leaf with three points: the hinge, the end of the open leaf and the end of the
closed leaf. It needs no scale. The detections of a sheet are stored by the pixel hash of the sheet, like the OCR.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from bp.tools.sheet_rooms import Swing

CACHE = Path(__file__).resolve().parents[3] / "experiments" / "cache" / "sheet-doors"
# A second detector of another kind (RF-DETR keypoints, `jobs/sheet-doors/predict_rfdetr.py`): the witness of the
# first one. Its rows have the same form.
SECOND = CACHE.parent / "sheet-doors-rfdetr"
MIN_SCORE = 0.5  # set on the dev sheets
SAME_DOOR = 0.45  # boxes that overlap this much (IoU) are one door, seen in two tiles


def cache_path(key: str) -> Path:
    return CACHE / f"{key}.json"


def _iou(a: list[float], b: list[float]) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    inter = w * h
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def merge(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per door: the tiles overlap, so a door can be found twice."""
    kept: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: -r["score"]):
        if all(_iou(row["box"], other["box"]) < SAME_DOOR for other in kept):
            kept.append(row)
    return kept


def swing_of(row: dict[str, Any]) -> Swing:
    (hx, hy), (lx, ly), (cx, cy) = row["hinge"], row["leaf"], row["closed"]
    radius = (math.hypot(lx - hx, ly - hy) + math.hypot(cx - hx, cy - hy)) / 2
    leaf = math.degrees(math.atan2(ly - hy, lx - hx)) % 360
    closed = math.degrees(math.atan2(cy - hy, cx - hx)) % 360
    sweep = abs((leaf - closed + 180) % 360 - 180)
    # `ends` go the positive way from the first to the last, as the arc is drawn
    first, last = (closed, leaf) if (leaf - closed) % 360 <= 180 else (leaf, closed)
    return Swing((float(hx), float(hy)), radius, sweep, (first, last), 1 if last == leaf else 0)


def detected(key: str, min_score: float = MIN_SCORE, cache: Path = CACHE) -> list[Swing] | None:
    """The door leaves of the sheet with this pixel hash, or None when the detector has not seen the sheet."""
    path = cache / f"{key}.json"
    if not path.exists():
        return None
    rows = json.loads(path.read_text())["doors"]
    return [swing_of(r) for r in rows if r["score"] >= min_score and math.dist(r["hinge"], r["leaf"]) > 4]
