"""Draw the labels of USACE pages on renders, to check them by eye.

    uv run python jobs/sheet-symbols/overlay.py --out <dir> <pdf>:<page number> ...
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import pymupdf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "sheets"))
import labels  # noqa: E402
import usace  # noqa: E402

COLOURS = {"toilet": (0, 0, 230), "urinal": (200, 0, 200), "sink": (230, 120, 0), "window": (0, 170, 0)}

parser = argparse.ArgumentParser()
parser.add_argument("--out", required=True)
parser.add_argument("--long", type=int, default=7000)
parser.add_argument("pages", nargs="+")
args = parser.parse_args()
Path(args.out).mkdir(parents=True, exist_ok=True)
for spec in args.pages:
    pdf, _, number = spec.rpartition(":")
    page = pymupdf.open(pdf)[int(number) - 1]
    page.remove_rotation()
    ft = usace.feet_per_inch(page)[1]
    rows, masks = labels.labels(page, ft)
    zoom = args.long / max(page.rect.width, page.rect.height)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csRGB)
    im = cv2.cvtColor(np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3), cv2.COLOR_RGB2BGR).copy()
    for cls, box in rows:
        x0, y0, x1, y1 = (int(v * zoom) for v in box)
        cv2.rectangle(im, (x0 - 3, y0 - 3), (x1 + 3, y1 + 3), COLOURS[cls], 3)
    for box in masks:
        x0, y0, x1, y1 = (int(v * zoom) for v in box)
        cv2.rectangle(im, (x0 - 3, y0 - 3), (x1 + 3, y1 + 3), (0, 200, 230), 2)
    name = f"{Path(pdf).stem[:30]}_p{number}"
    cv2.imwrite(f"{args.out}/{name}.png", im)
    counts = {c: sum(r[0] == c for r in rows) for c in labels.CLASSES}
    print(name, counts, "masked", len(masks), flush=True)
