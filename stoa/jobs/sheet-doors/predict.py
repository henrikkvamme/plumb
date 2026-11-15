"""Find the door leaves of whole sheets with the trained detector and store them for `bp.tools.sheet_doors`.

    python jobs/sheet-doors/predict.py --weights /root/doors/run/train/weights/best.pt data/sheets-test/*.png

One JSON per sheet in experiments/cache/sheet-doors/, with the pixel hash of the sheet as its name: the same key as
the OCR cache. Each door: hinge, end of the open leaf, end of the closed leaf, the box and the score.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from ultralytics import YOLO

from bp.tools import ocr, sheet_doors, sheet_text

TILE, STRIDE = 1024, 704

parser = argparse.ArgumentParser()
parser.add_argument("--weights", required=True)
parser.add_argument("--conf", type=float, default=0.05)
parser.add_argument("sheets", nargs="+")
args = parser.parse_args()
model = YOLO(args.weights)
sheet_doors.CACHE.mkdir(parents=True, exist_ok=True)
for path in args.sheets:
    rgb = ocr.to_rgb(path)
    target = sheet_doors.cache_path(sheet_text.pixel_key(rgb))
    gray = rgb.mean(axis=2).astype(np.uint8) if rgb.ndim == 3 else rgb
    height, width = gray.shape
    tiles, origins = [], []
    for y in range(0, max(height - TILE // 2, 1), STRIDE):
        for x in range(0, max(width - TILE // 2, 1), STRIDE):
            part = gray[y : y + TILE, x : x + TILE]
            if part.mean() > 254:
                continue
            tile = np.full((TILE, TILE), 255, np.uint8)
            tile[: part.shape[0], : part.shape[1]] = part
            tiles.append(np.stack([tile] * 3, axis=2))
            origins.append((x, y))
    rows = []
    for start in range(0, len(tiles), 32):
        results = model.predict(tiles[start : start + 32], imgsz=TILE, conf=args.conf, verbose=False)
        for (ox, oy), result in zip(origins[start : start + 32], results, strict=True):
            if result.boxes is None or result.keypoints is None:
                continue
            for box, score, keys in zip(result.boxes.xyxy.tolist(), result.boxes.conf.tolist(),
                                        result.keypoints.xy.tolist(), strict=True):  # fmt: skip
                x0, y0, x1, y1 = box
                # a door on the edge of a tile is cut: the next tile has it whole
                cut = min(x0, y0) < 4 or max(x1, y1) > TILE - 4
                edge = (ox == 0 and x0 < 4) or (oy == 0 and y0 < 4) or ox + x1 > width - 4 or oy + y1 > height - 4
                if cut and not edge:
                    continue
                rows.append({
                    "box": [round(x0 + ox, 1), round(y0 + oy, 1), round(x1 + ox, 1), round(y1 + oy, 1)],
                    "score": round(score, 4),
                    "hinge": [round(keys[0][0] + ox, 1), round(keys[0][1] + oy, 1)],
                    "leaf": [round(keys[1][0] + ox, 1), round(keys[1][1] + oy, 1)],
                    "closed": [round(keys[2][0] + ox, 1), round(keys[2][1] + oy, 1)],
                })  # fmt: skip
    doors = sheet_doors.merge(rows)
    target.write_text(json.dumps({"size": [width, height], "doors": doors}))
    print(Path(path).name, len(doors), "doors at 0.5:", sum(d["score"] >= 0.5 for d in doors), flush=True)
