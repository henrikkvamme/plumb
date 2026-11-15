"""Find the toilets, urinals, sinks and windows of whole sheets with the trained detector, and store them.

    python jobs/sheet-symbols/predict.py --weights artifacts/sheet-symbols/best.pt data/sheets-test/*.png

One JSON per sheet in experiments/cache/sheet-symbols/, with the pixel hash of the sheet as its name: the same key
as the OCR cache and the door cache. The shape follows `jobs/sheet-doors/predict.py`:
{"size": [w, h], "symbols": [{"box": [x0, y0, x1, y1], "class": "toilet", "score": 0.93}, ...]}.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from ultralytics import YOLO

from bp.tools import ocr, sheet_text

sys.path.insert(0, str(Path(__file__).resolve().parent))
import detect  # noqa: E402

CACHE = Path(__file__).resolve().parents[2] / "experiments" / "cache" / "sheet-symbols"

parser = argparse.ArgumentParser()
parser.add_argument("--weights", required=True)
parser.add_argument("--conf", type=float, default=0.05)
parser.add_argument("sheets", nargs="+")
args = parser.parse_args()
model = YOLO(args.weights)
CACHE.mkdir(parents=True, exist_ok=True)
for path in args.sheets:
    rgb = ocr.to_rgb(path)
    target = CACHE / f"{sheet_text.pixel_key(rgb)}.json"
    gray = rgb.mean(axis=2).astype(np.uint8) if rgb.ndim == 3 else rgb
    rows = detect.detect(model, gray, args.conf)
    target.write_text(json.dumps({"size": [gray.shape[1], gray.shape[0]], "symbols": rows}))
    print(Path(path).name, dict(Counter(r["class"] for r in rows if r["score"] >= 0.5)), flush=True)
