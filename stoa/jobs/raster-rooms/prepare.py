"""Build the training set of the room U-Net: Swiss PNG sheets of the DEV partition with masks from the DXF.

Run on the laptop (it reads the dataset): uv run python jobs/raster-rooms/prepare.py [n_sheets]
Each sheet is resized to the canonical scale (59.06 px per metre), as the tool does at inference. Output in
jobs/raster-rooms/data/: <stem>.img.png (RGB) and <stem>.mask.png (RGBA = room interior, wall, room boundary,
opening; soft 0..255), plus index.json with the scale factor and the room areas for a sanity check.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

from bp.toolbench import raster as R
from bp.tools.ocr import to_rgb
from bp.tools.raster_rooms import CANON_PPM, canonical

OUT = Path(__file__).resolve().parent / "data"


def one(stem: str) -> dict:
    try:
        labels = R.sheet_labels(stem)
    except Exception as exc:  # a sheet whose map cannot be fitted is left out
        return {"stem": stem, "error": repr(exc)[:200]}
    rgb = to_rgb(R.SWISS_DIR / f"{stem}.png")
    image, factor = canonical(rgb, labels.ppm)
    masks = R.render_masks(labels, factor)
    if masks.shape[:2] != image.shape[:2]:
        masks = np.asarray(Image.fromarray(masks).resize((image.shape[1], image.shape[0]), Image.Resampling.BILINEAR))
    Image.fromarray(image).save(OUT / f"{stem}.img.png", optimize=False, compress_level=6)
    Image.fromarray(masks, mode="RGBA").save(OUT / f"{stem}.mask.png", compress_level=6)
    soft = float(masks[..., 0].astype(np.float64).sum() / 255 / CANON_PPM**2)
    true = sum(r.area_m2 for r in labels.rooms) + sum(s.area / labels.ppm**2 for s in labels.other_shapes)
    return {"stem": stem, "factor": factor, "ppm": labels.ppm, "residual_px": labels.residual_px,
            "rooms": len(labels.rooms), "interior_m2": round(true, 3), "mask_m2": round(soft, 3),
            "shape": list(image.shape[:2])}


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    chosen = R.stems("dev")
    if len(sys.argv) > 1:
        chosen = chosen[: int(sys.argv[1])]
    with ProcessPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(one, chosen, chunksize=2))
    (OUT / "index.json").write_text(json.dumps(rows, indent=0))
    ok = [r for r in rows if "error" not in r]
    errs = [abs(r["mask_m2"] / r["interior_m2"] - 1) for r in ok if r["interior_m2"]]
    print(f"{len(ok)} sheets, {len(rows) - len(ok)} errors, mask vs polygon area: max {max(errs):.4f}, "
          f"mean {sum(errs) / len(errs):.5f}")
