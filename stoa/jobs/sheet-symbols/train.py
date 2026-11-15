"""Train the symbol detector (YOLO detect: toilet, urinal, sink, window) on the views of `prepare.py`.

    python jobs/sheet-symbols/train.py --data /root/symbols/data/data.yaml --out /root/symbols/run --epochs 40
"""

from __future__ import annotations

import argparse

from ultralytics import YOLO

parser = argparse.ArgumentParser()
parser.add_argument("--data", required=True)
parser.add_argument("--out", required=True)
parser.add_argument("--model", default="yolo26m.pt")
parser.add_argument("--epochs", type=int, default=40)
parser.add_argument("--batch", type=int, default=24)
parser.add_argument("--workers", type=int, default=12)
args = parser.parse_args()
model = YOLO(args.model)
# The settings of the door detector: a drawing has no colour and no perspective, and a sheet can lie on its side.
model.train(
    data=args.data, epochs=args.epochs, imgsz=1024, batch=args.batch, project=args.out, name="train", exist_ok=True,
    hsv_h=0.0, hsv_s=0.0, hsv_v=0.2, degrees=4.0, scale=0.35, translate=0.1, fliplr=0.5, flipud=0.5, mosaic=0.5,
    close_mosaic=10, workers=args.workers, patience=25, cache=False,
)  # fmt: skip
