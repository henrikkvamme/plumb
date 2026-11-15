"""The fallback: Ultralytics YOLO26-M on the same views (data/coco from prepare.py), then a TorchScript export.

    python train_yolo.py --epochs 40 --out out/yolo26m
    python train_yolo.py --export-only --out out/yolo26m

The views are 1024 px squares with symbols at native scale, so imgsz is 1024 (the tiling already does what a
larger input would do). Writes <out>/export/model.ts and meta.json for bp.tools.symbol_detector (backend yolo).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CDET_ROOT", str(HERE)))  # views and outputs; outside the synced folder on the VM
sys.path.insert(0, str(HERE / "_vendor"))

import symbol_detector as sd  # noqa: E402


def to_yolo(coco_dir: Path, yolo_dir: Path) -> Path:
    """YOLO layout with hard links to the COCO images: images/{train,val} and labels/{train,val}."""
    for split, name in (("train", "train"), ("valid", "val")):
        coco = json.loads((coco_dir / split / "_annotations.coco.json").read_text())
        images = yolo_dir / "images" / name
        labels = yolo_dir / "labels" / name
        images.mkdir(parents=True, exist_ok=True)
        labels.mkdir(parents=True, exist_ok=True)
        rows: dict[int, list[str]] = {im["id"]: [] for im in coco["images"]}
        for a in coco["annotations"]:
            x, y, w, h = a["bbox"]
            rows[a["image_id"]].append(
                f"{a['category_id']} {(x + w / 2) / 1024:.6f} {(y + h / 2) / 1024:.6f} {w / 1024:.6f} {h / 1024:.6f}"
            )
        for im in coco["images"]:
            target = images / im["file_name"]
            if not target.exists():
                os.link(coco_dir / split / im["file_name"], target)
            (labels / im["file_name"]).with_suffix(".txt").write_text("\n".join(rows[im["id"]]))
    yaml = yolo_dir / "data.yaml"
    names = "\n".join(f"  {i}: {n}" for i, n in enumerate(sd.CLASSES))
    yaml.write_text(f"path: {yolo_dir}\ntrain: images/train\nval: images/val\nnames:\n{names}\n")
    return yaml


def export(out: Path, weights: Path) -> None:
    import numpy as np  # noqa: PLC0415
    import torch  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    from ultralytics import YOLO  # noqa: PLC0415

    model = YOLO(str(weights))
    # The default exports the raw head [1, 4 + C, anchors]; symbol_detector.decode_yolo does the NMS in torch.
    # nms=True bakes NMS in, but with torchvision ops the sandbox lacks. nms=False exports the one-to-one head,
    # which gave fewer and different boxes than Ultralytics predict on best.pt.
    path = Path(model.export(format="torchscript", imgsz=1024, batch=1, device="cpu"))
    target = out / "export"
    target.mkdir(exist_ok=True)
    (target / "model.ts").write_bytes(path.read_bytes())
    meta = {
        "backend": "yolo",
        "resolution": 1024,
        "classes": list(sd.CLASSES),
        "floor": 0.05,
        "checkpoint": weights.name,
        "model": "yolo26m",
    }
    (target / "meta.json").write_text(json.dumps(meta, indent=1))
    valid = ROOT / "data" / "coco" / "valid"
    coco = json.loads((valid / "_annotations.coco.json").read_text())
    loaded = torch.jit.load(str(target / "model.ts"))
    view = sd.View("global", 0.0, 0.0, 1.0, 1024)
    for image in coco["images"][:5]:
        pil = Image.open(valid / image["file_name"]).convert("RGB")
        ref = model.predict(pil, imgsz=1024, conf=0.3, verbose=False)[0]
        tensor = torch.from_numpy(np.asarray(pil, dtype=np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0)
        with torch.no_grad():
            raw = loaded(tensor)
        shape = tuple(raw[0].shape) if isinstance(raw, (tuple, list)) else tuple(raw.shape)
        mine = sd.decode_yolo(raw, view, sd.CLASSES, 0.3)
        truth = sum(1 for a in coco["annotations"] if a["image_id"] == image["id"])
        print(
            f"{image['file_name']}: raw shape {shape} ultralytics {len(ref.boxes)} traced {len(mine)} truth {truth}",
            flush=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="yolo26m.pt")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--hours", type=float, default=0.0, help="Ultralytics time limit; overrides epochs.")
    parser.add_argument("--fraction", type=float, default=1.0)
    parser.add_argument("--out", default="out/yolo26m")
    parser.add_argument("--export-only", action="store_true")
    parser.add_argument("--device", default="", help="such as 0,1 for two GPUs; empty for the default.")
    args = parser.parse_args()
    out = ROOT / args.out
    if not args.export_only:
        from ultralytics import YOLO  # noqa: PLC0415

        yaml = to_yolo(ROOT / "data" / "coco", ROOT / "data" / "yolo")
        started = time.time()
        model = YOLO(args.model)
        extra = {"time": args.hours} if args.hours else {}
        if args.device:
            extra["device"] = [int(v) for v in args.device.split(",")]
        model.train(
            data=str(yaml), imgsz=1024, epochs=args.epochs, batch=args.batch, project=str(out.parent),
            name=out.name, exist_ok=True, fliplr=0.5, flipud=0.5, degrees=0.0, mosaic=1.0, close_mosaic=5,
            save_period=1, patience=10, workers=8, fraction=args.fraction, plots=False, **extra,
        )  # fmt: skip
        (out / "train_meta.json").write_text(json.dumps({"seconds": time.time() - started, "model": args.model}))
    export(out, out / "weights" / "best.pt")


if __name__ == "__main__":
    main()
