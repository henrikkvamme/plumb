"""Copy a trained room U-Net into the artifacts folder that the tool reads.

Run from stoa/: uv run python jobs/raster-rooms/export.py artifacts/raster-rooms/run-110min/model.pt
It checks the checkpoint (keys, encoder, 4 classes, a forward pass on a blank tile) before it replaces
artifacts/raster-rooms/model.pt, and keeps the old file as model.prev.pt.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import segmentation_models_pytorch as smp
import torch

TARGET = Path(__file__).resolve().parents[2] / "artifacts" / "raster-rooms" / "model.pt"


def check(path: Path) -> dict[str, object]:
    blob = torch.load(path, map_location="cpu", weights_only=False)
    for key in ("state_dict", "encoder", "classes"):
        if key not in blob:
            raise SystemExit(f"{path}: no {key!r} in the checkpoint")
    if blob["classes"] != 4:  # noqa: PLR2004 - interior, wall, boundary, opening
        raise SystemExit(f"{path}: {blob['classes']} classes, not 4")
    net = smp.Unet(blob["encoder"], encoder_weights=None, in_channels=3, classes=4)
    net.load_state_dict({k: v.float() for k, v in blob["state_dict"].items()})
    with torch.no_grad():
        out = net.eval()(torch.zeros(1, 3, 256, 256))
    if tuple(out.shape) != (1, 4, 256, 256):
        raise SystemExit(f"{path}: output shape {tuple(out.shape)}")
    return {"encoder": blob["encoder"], "step": blob.get("step"), "metrics": blob.get("metrics")}


def main() -> None:
    source = Path(sys.argv[1])
    info = check(source)
    if TARGET.exists():
        shutil.copy2(TARGET, TARGET.with_name("model.prev.pt"))
    shutil.copy2(source, TARGET)
    print(json.dumps({"exported": str(TARGET), **info}, default=str))  # noqa: T201


if __name__ == "__main__":
    main()
