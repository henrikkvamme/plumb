"""Train the door detector (YOLO pose: a box and 3 keypoints for each swing door leaf).

    python jobs/sheet-doors/train.py --data /root/doors/data.yaml --out /root/doors/run --epochs 60
"""

from __future__ import annotations

import argparse

from ultralytics import YOLO

parser = argparse.ArgumentParser()
parser.add_argument("--data", required=True)
parser.add_argument("--out", required=True)
parser.add_argument("--model", default="yolo26m-pose.pt")
parser.add_argument("--epochs", type=int, default=60)
parser.add_argument("--batch", type=int, default=24)
args = parser.parse_args()
model = YOLO(args.model)
# A drawing has no colour and no perspective. A sheet can lie on its side, so the views turn by any right angle.
model.train(
    data=args.data, epochs=args.epochs, imgsz=1024, batch=args.batch, project=args.out, name="train", exist_ok=True,
    hsv_h=0.0, hsv_s=0.0, hsv_v=0.2, degrees=4.0, scale=0.35, translate=0.1, fliplr=0.5, flipud=0.5, mosaic=0.5,
    close_mosaic=10, workers=12, patience=25, cache=False,
)  # fmt: skip
