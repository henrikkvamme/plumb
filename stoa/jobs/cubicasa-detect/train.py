"""Train RF-DETR on the CubiCasa views in data/coco (made by prepare.py). Runs on a Verda GPU VM.

    python train.py --model large --resolution 1024 --epochs 20 --out out/rfdetr-l
    python train.py --subset 300 --epochs 2 --out out/smoke        # the 15-minute pipeline proof

Checkpoints go to <out>/ every epoch (rfdetr writes checkpoint*.pth and its log there). After training,
export.py turns the best checkpoint into TorchScript for the Mac.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CDET_ROOT", str(HERE)))  # views and outputs; outside the synced folder on the VM


def subset(source: Path, target: Path, count: int) -> Path:
    """A copy of the COCO folder with the first `count` train images (and a quarter of that for valid)."""
    for split, n in (("train", count), ("valid", max(20, count // 4))):
        coco = json.loads((source / split / "_annotations.coco.json").read_text())
        images = coco["images"][:n]
        keep = {im["id"] for im in images}
        (target / split).mkdir(parents=True, exist_ok=True)
        for im in images:
            dst = target / split / im["file_name"]
            if not dst.exists():
                dst.symlink_to((source / split / im["file_name"]).resolve())
        coco["images"] = images
        coco["annotations"] = [a for a in coco["annotations"] if a["image_id"] in keep]
        (target / split / "_annotations.coco.json").write_text(json.dumps(coco))
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="large", choices=["large", "medium", "small", "base"])
    parser.add_argument("--resolution", type=int, default=1024)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--accum", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--subset", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--patience", type=int, default=6)
    parser.add_argument("--resume", default="")
    parser.add_argument("--out", default="out/rfdetr-l")
    args = parser.parse_args()

    import torch  # noqa: PLC0415
    from rfdetr import RFDETRBase, RFDETRLarge, RFDETRMedium, RFDETRSmall  # noqa: PLC0415

    print(f"torch {torch.__version__} cuda {torch.cuda.is_available()} {torch.cuda.get_device_name(0)}", flush=True)
    data = ROOT / "data" / "coco"
    if args.subset:
        data = subset(data, ROOT / "data" / f"coco-sub{args.subset}", args.subset)
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HERE / "data" / "plans.json", out / "plans.json")
    variants = {"large": RFDETRLarge, "medium": RFDETRMedium, "small": RFDETRSmall, "base": RFDETRBase}
    model = variants[args.model](resolution=args.resolution)
    started = time.time()
    model.train(
        dataset_dir=str(data),
        output_dir=str(out),
        epochs=args.epochs,
        batch_size=args.batch,
        grad_accum_steps=args.accum,
        lr=args.lr,
        num_workers=args.workers,
        multi_scale=False,
        scale_jitter=False,
        checkpoint_interval=1,
        aug_config={
            "SquareSymmetry": {"p": 0.75},  # plans come in any rotation; text runs sideways or upside down
            "ImageCompression": {"p": 0.2},
            "GaussianBlur": {"p": 0.1},
            "ToGray": {"p": 0.2},
        },
        early_stopping=True,
        early_stopping_patience=args.patience,
        early_stopping_use_ema=True,
        log_per_class_metrics=True,
        progress_bar=None,
        tensorboard=False,
        resume=args.resume or None,
    )
    meta = {"model": args.model, "resolution": args.resolution, "epochs": args.epochs, "seconds": time.time() - started}
    (out / "train_meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta), flush=True)


if __name__ == "__main__":
    main()
