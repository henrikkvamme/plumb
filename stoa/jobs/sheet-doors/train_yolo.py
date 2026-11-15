"""Train a YOLO pose door detector with another base model or input size (research copy of `train.py`).

    python jobs/sheet-doors/train_yolo.py --data /root/doors/data.yaml --out /root/research/runs --name y26l \
        --model yolo26l-pose.pt --imgsz 1024 --epochs 40 --batch 32

The augmentation is the same as in `train.py`, so only the base model, the input size and the data change.
"""

from __future__ import annotations

import argparse

from ultralytics import YOLO

parser = argparse.ArgumentParser()
parser.add_argument("--data", required=True)
parser.add_argument("--out", required=True)
parser.add_argument("--name", required=True)
parser.add_argument("--model", default="yolo26m-pose.pt")
parser.add_argument("--imgsz", type=int, default=1024)
parser.add_argument("--epochs", type=int, default=40)
parser.add_argument("--batch", type=int, default=32)
parser.add_argument("--workers", type=int, default=12)
args = parser.parse_args()
model = YOLO(args.model)
model.train(
    data=args.data, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch, project=args.out, name=args.name,
    exist_ok=True, hsv_h=0.0, hsv_s=0.0, hsv_v=0.2, degrees=4.0, scale=0.35, translate=0.1, fliplr=0.5, flipud=0.5,
    mosaic=0.5, close_mosaic=10, workers=args.workers, patience=25, cache=False,
)  # fmt: skip
