"""Export a trained RF-DETR checkpoint to TorchScript for the Mac, and check that the export matches rfdetr.

    python export.py --run out/rfdetr-l [--checkpoint checkpoint_best_total.pth]

Writes <run>/export/model.ts and meta.json (backend, resolution, classes). The check runs rfdetr's own
predict and the traced model (decoded with the vendored bp.tools.symbol_detector) on a few held-out views
and prints the largest score and box difference.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("CDET_ROOT", str(HERE)))  # views and outputs; outside the synced folder on the VM
sys.path.insert(0, str(HERE / "_vendor"))

import symbol_detector as sd  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="out/rfdetr-l")
    parser.add_argument("--checkpoint", default="")
    parser.add_argument("--model", default="large")
    parser.add_argument("--resolution", type=int, default=1024)
    args = parser.parse_args()

    import torch  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    from rfdetr import RFDETRBase, RFDETRLarge, RFDETRMedium, RFDETRSmall  # noqa: PLC0415

    run = ROOT / args.run
    names = (
        [args.checkpoint]
        if args.checkpoint
        else ["checkpoint_best_total.pth", "checkpoint_best_ema.pth", "checkpoint_best_regular.pth", "checkpoint.pth"]
    )
    checkpoint = next((run / n for n in names if (run / n).exists()), None)
    if checkpoint is None:
        raise SystemExit(f"no checkpoint in {run}: {sorted(p.name for p in run.iterdir())}")
    print("checkpoint", checkpoint, flush=True)
    variants = {"large": RFDETRLarge, "medium": RFDETRMedium, "small": RFDETRSmall, "base": RFDETRBase}
    model = variants[args.model](
        pretrain_weights=str(checkpoint), resolution=args.resolution, num_classes=len(sd.CLASSES)
    )
    names_seen = list(getattr(model, "class_names", []) or [])
    print("rfdetr class names", names_seen, flush=True)
    net = copy.deepcopy(model.model.model).to("cpu").eval()
    net.export()
    example = torch.randn(1, 3, args.resolution, args.resolution)
    with torch.no_grad():
        traced = torch.jit.trace(net, example)
    target = run / "export"
    target.mkdir(exist_ok=True)
    traced.save(str(target / "model.ts"))
    meta = {
        "backend": "rfdetr",
        "resolution": args.resolution,
        "classes": list(sd.CLASSES),
        "floor": 0.05,
        "checkpoint": checkpoint.name,
        "rfdetr_class_names": names_seen,
        "model": f"rfdetr-{args.model}",
    }
    (target / "meta.json").write_text(json.dumps(meta, indent=1))

    # Parity: rfdetr predict against the traced model on held-out views.
    valid = ROOT / "data" / "coco" / "valid"
    coco = json.loads((valid / "_annotations.coco.json").read_text())
    loaded = torch.jit.load(str(target / "model.ts"))
    view = sd.View("global", 0.0, 0.0, 1.0, args.resolution)
    worst = 0.0
    for image in coco["images"][:5]:
        pil = Image.open(valid / image["file_name"]).convert("RGB")
        ref = model.predict(pil, threshold=0.3)
        with torch.no_grad():
            out = loaded(sd.to_tensor(pil))
        mine = list(sd.decode_rfdetr(out, view, sd.CLASSES, 0.3))
        truth = [a for a in coco["annotations"] if a["image_id"] == image["id"]]
        ref_scores = sorted(np.asarray(ref.confidence).tolist(), reverse=True)
        my_scores = sorted((d.score for d in mine), reverse=True)
        k = min(len(ref_scores), len(my_scores))
        diff = max((abs(a - b) for a, b in zip(ref_scores[:k], my_scores[:k], strict=False)), default=0.0)
        worst = max(worst, diff)
        ref_labels = sorted(np.asarray(ref.class_id).tolist())
        my_labels = sorted(sd.CLASSES.index(d.label) for d in mine)
        true_labels = sorted(a["category_id"] for a in truth)
        print(
            f"{image['file_name']}: rfdetr {len(ref_scores)} traced {len(my_scores)} truth {len(truth)} "
            f"max score diff {diff:.4f}\n  rfdetr ids {ref_labels[:40]}\n  traced ids {my_labels[:40]}\n"
            f"  truth ids  {true_labels[:40]}",
            flush=True,
        )
    print(f"parity worst score diff {worst:.4f}", flush=True)


if __name__ == "__main__":
    main()
