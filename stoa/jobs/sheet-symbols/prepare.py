"""Training views for the symbol detector (toilet, urinal, sink, window), from the vector PDFs of the USACE sets.

    python jobs/sheet-symbols/prepare.py --out /root/symbols/data --variants 4 [--processes 32]

The labels come from `labels.py` (runs of paths whose signature `classes.json` names). Each page is rendered
several times as a scan could look, with the same changes as the door views (`jobs/sheet-doors/prepare.py`:
resolution, skew or a right-angle turn, line weight, grey ink, blur, noise, JPEG), and cut into 1024 px tiles in
the YOLO detect layout. Runs that a person could not name for sure (`mask` in `classes.json`) are painted white.

The held-out facility types (`usace.LOCK`) are never read. The kinds `cof` and `sprc` (as for the doors) and
`ssa` are the validation part. Site plans (more than 16 ft per inch) are left out: their symbols are too small.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import pymupdf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "sheets"))
import labels  # noqa: E402
import usace  # noqa: E402

_spec = importlib.util.spec_from_file_location("door_prepare", HERE.parent / "sheet-doors" / "prepare.py")
_doors = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_doors)
degrade = _doors.degrade  # the scan look of the door views (that file is only read)

STOA = HERE.parents[1]
SRC = STOA / "data/external/sheets/usace"
VAL = {"cof", "sprc", "ssa"}  # held out; cdcsa trains: it holds toilet and urinal families no other kind has
TILE, STRIDE = 1024, 704
LONG_SIDES = (5200, 6800, 8400, 10200, 12000)
MAX_FT = 16.0
EMPTY_SHARE = 0.12


def pages() -> list[tuple[str, int, float, str]]:
    """(pdf, page index, feet per inch, split) of each dev page with a scale of at most `MAX_FT`."""
    out = []
    for pdf in sorted(SRC.glob("*.pdf")):
        kind = pdf.stem.partition("__")[0]
        if kind in usace.SKIP:
            continue
        doc = pymupdf.open(pdf)
        for i, page in enumerate(doc):
            if kind in usace.LOCK and not (kind == "ortc" and i + 1 < usace.ORTC_LOCK_FROM):
                continue  # held out
            if max(page.rect.width, page.rect.height) / 72 < usace.MIN_SIDE_IN:
                continue
            page.remove_rotation()
            scale = usace.feet_per_inch(page)
            if scale and scale[1] <= MAX_FT:
                out.append((str(pdf), i, scale[1], "val" if kind in VAL else "train"))
    return out


def page_labels(job: tuple[str, int, float, str]) -> tuple[list, list]:
    pdf, index, ft, _ = job
    page = pymupdf.open(pdf)[index]
    page.remove_rotation()
    return labels.labels(page, ft)


def render(pdf: str, index: int, rows: list, masks: list, variant: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(gray sheet, boxes in pixels as x0 y0 x1 y1, class ids) of one view. Variant 0 is the clean render."""
    rng = random.Random(f"{pdf}:{index}:{variant}:symbols")
    page = pymupdf.open(pdf)[index]
    page.remove_rotation()
    zoom = rng.choice(LONG_SIDES) * rng.uniform(0.9, 1.1) / max(page.rect.width, page.rect.height)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY, alpha=False)
    gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width).copy()
    for m in masks:
        x0, y0, x1, y1 = (int(round(v * zoom)) for v in m)
        gray[max(y0 - 2, 0) : y1 + 3, max(x0 - 2, 0) : x1 + 3] = 255
    boxes = np.array([b for _, b in rows], float).reshape(-1, 4) * zoom
    ids = np.array([labels.CLASSES.index(c) for c, _ in rows], int)
    if variant and rng.random() < 0.5:
        angle = rng.choice([90.0, 180.0, 270.0]) if rng.random() < 0.25 else rng.uniform(-2.5, 2.5)
        h, w = gray.shape
        mat = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        cos, sin = abs(mat[0, 0]), abs(mat[0, 1])
        nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
        mat[0, 2] += nw / 2 - w / 2
        mat[1, 2] += nh / 2 - h / 2
        gray = cv2.warpAffine(gray, mat, (nw, nh), flags=cv2.INTER_LINEAR, borderValue=255)
        if len(boxes):
            corners = np.stack([boxes[:, [0, 1]], boxes[:, [2, 1]], boxes[:, [2, 3]], boxes[:, [0, 3]]], axis=1)
            xy = np.c_[corners.reshape(-1, 2), np.ones(len(corners) * 4)] @ mat.T
            xy = xy.reshape(-1, 4, 2)
            boxes = np.c_[xy[:, :, 0].min(1), xy[:, :, 1].min(1), xy[:, :, 0].max(1), xy[:, :, 1].max(1)]
    if variant:
        gray = degrade(gray, rng)
    return gray, boxes, ids


def one(job: tuple[str, int, list, list, int, str, str]) -> int:
    pdf, index, rows, masks, variant, split, out = job
    rng = random.Random(f"{pdf}:{index}:{variant}:tiles")
    gray, boxes, ids = render(pdf, index, rows, masks, variant)
    centre = (boxes[:, :2] + boxes[:, 2:]) / 2 if len(boxes) else np.zeros((0, 2))
    stem = f"{Path(pdf).stem[:40].replace(' ', '_')}_p{index + 1:03d}_v{variant}"
    made = 0
    for y in range(0, max(gray.shape[0] - TILE // 2, 1), STRIDE):
        for x in range(0, max(gray.shape[1] - TILE // 2, 1), STRIDE):
            inside = (centre[:, 0] >= x) & (centre[:, 0] < x + TILE) & (centre[:, 1] >= y) & (centre[:, 1] < y + TILE)
            if not inside.any() and rng.random() > EMPTY_SHARE:
                continue
            part = gray[y : y + TILE, x : x + TILE]
            if part.mean() > 254:
                continue
            tile = np.full((TILE, TILE), 255, np.uint8)
            tile[: part.shape[0], : part.shape[1]] = part
            text = []
            for i in np.nonzero(inside)[0]:
                x0, y0, x1, y1 = np.clip(boxes[i] - [x, y, x, y], 0, TILE)
                if x1 - x0 < 2 or y1 - y0 < 2:
                    continue
                text.append(f"{ids[i]} {(x0 + x1) / 2 / TILE:.6f} {(y0 + y1) / 2 / TILE:.6f} "
                            f"{(x1 - x0) / TILE:.6f} {(y1 - y0) / TILE:.6f}")  # fmt: skip
            name = f"{stem}_{y:05d}_{x:05d}"
            cv2.imwrite(f"{out}/images/{split}/{name}.jpg", tile, [cv2.IMWRITE_JPEG_QUALITY, 92])
            Path(f"{out}/labels/{split}/{name}.txt").write_text("\n".join(text))
            made += 1
    return made


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--variants", type=int, default=4)
    parser.add_argument("--processes", type=int, default=16)
    args = parser.parse_args()
    for split in ("train", "val"):
        for kind in ("images", "labels"):
            Path(args.out, kind, split).mkdir(parents=True, exist_ok=True)
    found = pages()
    with ProcessPoolExecutor(args.processes) as pool:
        labelled = list(pool.map(page_labels, found, chunksize=1))
    jobs, manifest = [], []
    counts = {s: {c: 0 for c in labels.CLASSES} | {"pages": 0} for s in ("train", "val")}
    for (pdf, index, ft, split), (rows, masks) in zip(found, labelled, strict=True):
        if not rows:
            continue
        counts[split]["pages"] += 1
        for c, _ in rows:
            counts[split][c] += 1
        manifest.append({"pdf": Path(pdf).name, "index": index, "ft": ft, "split": split, "rows": rows, "masks": masks})
        variants = range(args.variants) if split == "train" else range(2)
        jobs.extend((pdf, index, rows, masks, v, split, args.out) for v in variants)
    print("labels:", json.dumps(counts), "jobs:", len(jobs), flush=True)
    Path(args.out, "manifest.json").write_text(json.dumps(manifest))
    with ProcessPoolExecutor(args.processes) as pool:
        tiles = sum(pool.map(one, jobs, chunksize=1))
    names = "".join(f"  {i}: {c}\n" for i, c in enumerate(labels.CLASSES))
    Path(args.out, "data.yaml").write_text(f"path: {args.out}\ntrain: images/train\nval: images/val\nnames:\n{names}")
    print("tiles:", tiles)


if __name__ == "__main__":
    main()
