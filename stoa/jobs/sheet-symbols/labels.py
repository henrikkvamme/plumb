"""Symbol labels of one USACE page: the runs of `instances.groups` whose catalog key `classes.json` names.

A window run is often only its glass lines (a box with no depth), and a wide window can be cut into one run per
pane. So a window box gets at least the depth of a wall, and window boxes on one line with a small gap join.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import catalog  # noqa: E402
import instances  # noqa: E402

CLASSES = ("toilet", "urinal", "sink", "window")
NAMES = json.loads((HERE / "classes.json").read_text())
BY_KEY = {k: c for c, keys in NAMES.items() if not c.startswith("_") for k in keys}
# A key two families share, told apart by the count of items: the mop sink of cdcsa has 20 to 32, the round
# lavatory of gpw, fs and ortc 60 to 79. Below the count the run is no label (mop sinks are background).
MIN_ITEMS_BY_KEY = {"20x20L128": 45}
WALL_IN = 8  # depth given to a window box, inches
JOIN_IN = 10  # window boxes on one line with a gap below this join


def _join_windows(boxes: list[list[float]], inch: float) -> list[list[float]]:
    boxes = [b[:] for b in boxes]
    changed = True
    while changed:
        changed = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                horizontal = (a[2] - a[0]) >= (a[3] - a[1]) and (b[2] - b[0]) >= (b[3] - b[1])
                vertical = (a[3] - a[1]) > (a[2] - a[0]) and (b[3] - b[1]) > (b[2] - b[0])
                if horizontal:
                    same = abs((a[1] + a[3]) / 2 - (b[1] + b[3]) / 2) < 2 * inch
                    gap = max(a[0], b[0]) - min(a[2], b[2])
                elif vertical:
                    same = abs((a[0] + a[2]) / 2 - (b[0] + b[2]) / 2) < 2 * inch
                    gap = max(a[1], b[1]) - min(a[3], b[3])
                else:
                    continue
                if same and gap < JOIN_IN * inch:
                    boxes[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                    del boxes[j]
                    changed = True
                    break
            if changed:
                break
    return boxes


def labels(page: pymupdf.Page, ft_per_in: float) -> tuple[list[tuple[str, list[float]]], list[list[float]]]:
    """([(class, box in page points)], [masked boxes]) of the page."""
    pt_ft = 72 / ft_per_in
    inch = pt_ft / 12
    found: dict[str, list[list[float]]] = {c: [] for c in (*CLASSES, "mask")}
    for g in instances.groups(page, ft_per_in):
        sig = g.signature(pt_ft)
        if g.items < catalog.MIN_ITEMS or not catalog.SIDE_IN[0] <= sig[3] <= catalog.SIDE_IN[1]:
            continue
        k = catalog.key(sig)
        cls = BY_KEY.get(k)
        if cls and g.items >= MIN_ITEMS_BY_KEY.get(k, 0):
            found[cls].append([g.rect.x0, g.rect.y0, g.rect.x1, g.rect.y1])
    windows = []
    for x0, y0, x1, y1 in found["window"]:
        if x1 - x0 >= y1 - y0:
            cy, half = (y0 + y1) / 2, max((y1 - y0) / 2, WALL_IN * inch / 2)
            windows.append([x0, cy - half, x1, cy + half])
        else:
            cx, half = (x0 + x1) / 2, max((x1 - x0) / 2, WALL_IN * inch / 2)
            windows.append([cx - half, y0, cx + half, y1])
    found["window"] = _join_windows(windows, inch)

    def holds(m: list[float], b: list[float]) -> bool:
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        return m[0] <= cx <= m[2] and m[1] <= cy <= m[3]

    def area(b: list[float]) -> float:
        return (b[2] - b[0]) * (b[3] - b[1])

    for c in ("toilet", "urinal", "sink"):  # a seat run inside the run of the whole fixture is one fixture
        boxes = sorted(found[c], key=area, reverse=True)
        found[c] = [b for i, b in enumerate(boxes) if not any(holds(o, b) for o in boxes[:i])]
    rows = [(c, b) for c in CLASSES for b in found[c]]

    masks = [m for m in found["mask"] if not any(holds(m, b) for _, b in rows)]  # never paint over a label
    return rows, masks
