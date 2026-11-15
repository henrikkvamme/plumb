"""Draw labels (green) and detections (red, score >= --thr) of one sheet from a `compare.py run` file.

python jobs/sheet-doors/overlay.py cmp/y26m.json --sheet 1 --thr 0.5 --out sheet.jpg [--crop x0 y0 x1 y1]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compare

parser = argparse.ArgumentParser()
parser.add_argument("file")
parser.add_argument("--sheet", type=int, default=0)
parser.add_argument("--thr", type=float, default=0.5)
parser.add_argument("--out", required=True)
parser.add_argument("--crop", type=int, nargs=4)
parser.add_argument("--scale", type=float, default=0.25)
args = parser.parse_args()
s = json.loads(Path(args.file).read_text())["sheets"][args.sheet]
pdf = compare.prepare_src() / s["pdf"]
jobs = [j for j in compare.val_jobs(4) if Path(j[0]).name == s["pdf"] and j[1] == s["page"] - 1 and j[3] == s["variant"]]
gray, _, _ = compare.render(*jobs[0])
img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
for lab in s["labels"]:
    x0, y0, x1, y1 = map(int, lab["box"])
    cv2.rectangle(img, (x0, y0), (x1, y1), (0, 200, 0), 4)
for d in s["doors"]:
    if d["score"] >= args.thr:
        x0, y0, x1, y1 = map(int, d["box"])
        cv2.rectangle(img, (x0 + 3, y0 + 3), (x1 - 3, y1 - 3), (0, 0, 255), 3)
        cv2.circle(img, tuple(map(int, d["hinge"])), 6, (255, 0, 0), -1)
if args.crop:
    x0, y0, x1, y1 = args.crop
    img = img[y0:y1, x0:x1]
else:
    img = cv2.resize(img, None, fx=args.scale, fy=args.scale, interpolation=cv2.INTER_AREA)
cv2.imwrite(args.out, img, [cv2.IMWRITE_JPEG_QUALITY, 85])
print(args.out, img.shape)
