"""Train an RF-DETR keypoint door detector (Apache 2.0) on the YOLO pose tiles of `prepare.py`.

    python jobs/sheet-doors/train_rfdetr.py --data /root/research/doors --out /root/research/runs/rfdetr \
        --resolution 1008 --epochs 24 --batch 8 --accum 2

`--data` is the directory with `data.yaml` (`kpt_shape: [3, 3]`), `images/{train,val}` and `labels/{train,val}`.
The resolution must be a multiple of 24 (patch 12, 2 windows): 1008 keeps the 1024 px tiles almost at full size, so
the thin lines stay. The augmentation follows `train.py`: flips both ways, a small rotation, scale and shift. A flip
keeps the meaning of the 3 keypoints (hinge, open end, closed end), so the flip pairs are empty but flips stay on.
"""

from __future__ import annotations

import argparse

from rfdetr import RFDETRKeypointPreview

parser = argparse.ArgumentParser()
parser.add_argument("--data", required=True)
parser.add_argument("--out", required=True)
parser.add_argument("--resolution", type=int, default=1008)
parser.add_argument("--epochs", type=int, default=24)
parser.add_argument("--batch", type=int, default=8)
parser.add_argument("--accum", type=int, default=2)
parser.add_argument("--lr", type=float, default=1e-4)
parser.add_argument("--workers", type=int, default=10)
args = parser.parse_args()

model = RFDETRKeypointPreview()
model.train(
    dataset_dir=args.data, dataset_file="yolo", output_dir=args.out, resolution=args.resolution, epochs=args.epochs,
    batch_size=args.batch, grad_accum_steps=args.accum, lr=args.lr, lr_encoder=args.lr * 1.5,
    num_workers=args.workers, multi_scale=False, expanded_scales=False, keypoint_flip_pairs=[0, 0],
    aug_config={
        "HorizontalFlip": {"p": 0.5},
        "VerticalFlip": {"p": 0.5},
        "Affine": {"scale": (0.7, 1.35), "translate_percent": (-0.1, 0.1), "rotate": (-4, 4), "fill": 255, "p": 0.7},
    },
    progress_bar="tqdm", tensorboard=False, checkpoint_interval=4,
)  # fmt: skip
