"""Training views for the door detector, from the vector PDFs of the USACE sets.

    python jobs/sheet-doors/prepare.py --out /root/doors --variants 4

The door swings of a vector sheet are exact (`jobs/sheets/usace.py: door_swings`). Each page is rendered several
times as a scan could look: another resolution, grey or thin ink, blur, noise, a small skew, JPEG marks. The views
are 1024 px tiles in the YOLO pose layout: one class (a swing door leaf) with 3 keypoints, the hinge, the end of the
open leaf and the end of the closed leaf.

The held-out facility types (`usace.LOCK`) are never read. Two dev types are the validation part.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sheets"))
import usace  # noqa: E402

STOA = Path(__file__).resolve().parents[2]
SRC = STOA / "data/external/sheets/usace"
VAL = {"cof", "sprc"}
TILE, STRIDE = 1024, 704
LONG_SIDES = (5200, 6800, 8400, 10200, 12000)  # px of the long side of a sheet: a door leaf is 35 to 220 px
MIN_SWINGS = 3
EMPTY_SHARE = 0.12  # tiles with no door that are kept: title blocks, notes, furniture


def pages(pdf: Path) -> list[tuple[int, list[usace.Swing]]]:
    """(page index, swings) for each large sheet of the file with a scale and doors."""
    out = []
    doc = pymupdf.open(pdf)
    for i, page in enumerate(doc):
        if max(page.rect.width, page.rect.height) / 72 < usace.MIN_SIDE_IN:
            continue
        page.remove_rotation()
        scale = usace.feet_per_inch(page)
        if not scale:
            continue
        swings = usace.door_swings(page, scale[1])
        if len(swings) >= MIN_SWINGS:
            out.append((i, swings))
    return out


def degrade(gray: np.ndarray, rng: random.Random) -> np.ndarray:
    """One look of a scan or of another plotter."""
    if rng.random() < 0.35:  # thin or thick lines
        kernel = np.ones((2, 2) if rng.random() < 0.6 else (3, 3), np.uint8)
        gray = cv2.erode(gray, kernel) if rng.random() < 0.6 else cv2.dilate(gray, kernel)
    if rng.random() < 0.4:  # grey ink, grey paper
        ink, paper = rng.uniform(0, 110), rng.uniform(215, 255)
        gray = (ink + gray.astype(np.float32) * (paper - ink) / 255).astype(np.uint8)
    if rng.random() < 0.4:
        sigma = rng.uniform(0.5, 1.6)
        gray = cv2.GaussianBlur(gray, (0, 0), sigma)
    if rng.random() < 0.35:
        noise = np.random.default_rng(rng.randrange(1 << 30)).normal(0, rng.uniform(4, 14), gray.shape)
        gray = np.clip(gray.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    if rng.random() < 0.3:
        _, data = cv2.imencode(".jpg", gray, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(25, 70)])
        gray = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    return gray


def boxes(swings: np.ndarray) -> np.ndarray:
    """(x0, y0, x1, y1) around the hinge and the arc of each swing. `swings` is in pixels."""
    out = []
    for cx, cy, r, ax, ay, bx, by, _ in swings:
        a0, a1 = math.atan2(ay - cy, ax - cx), math.atan2(by - cy, bx - cx)
        sweep = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi  # the short way from end 0 to end 1
        angles = a0 + sweep * np.linspace(0, 1, 12)
        xs = np.r_[cx, cx + r * np.cos(angles)]
        ys = np.r_[cy, cy + r * np.sin(angles)]
        out.append((xs.min(), ys.min(), xs.max(), ys.max()))
    return np.array(out).reshape(-1, 4)


def one(job: tuple[str, int, list, int, str, str]) -> int:
    pdf, index, swings, variant, split, out = job
    rng = random.Random(f"{pdf}:{index}:{variant}")
    page = pymupdf.open(pdf)[index]
    page.remove_rotation()
    long_pt = max(page.rect.width, page.rect.height)
    zoom = rng.choice(LONG_SIDES) * rng.uniform(0.9, 1.1) / long_pt
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY, alpha=False)
    gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width).copy()
    pts = np.array(swings, float)
    pts[:, :7] *= zoom
    if variant and rng.random() < 0.5:  # a small skew, or a sheet that was scanned on its side
        angle = rng.choice([90.0, 180.0, 270.0]) if rng.random() < 0.25 else rng.uniform(-2.5, 2.5)
        h, w = gray.shape
        m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        cos, sin = abs(m[0, 0]), abs(m[0, 1])
        nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
        m[0, 2] += nw / 2 - w / 2
        m[1, 2] += nh / 2 - h / 2
        gray = cv2.warpAffine(gray, m, (nw, nh), flags=cv2.INTER_LINEAR, borderValue=255)
        for a in (0, 3, 5):
            xy = np.c_[pts[:, a], pts[:, a + 1], np.ones(len(pts))] @ m.T
            pts[:, a], pts[:, a + 1] = xy[:, 0], xy[:, 1]
    if variant:
        gray = degrade(gray, rng)
    box = boxes(pts)
    centre = (box[:, :2] + box[:, 2:]) / 2
    stem = f"{Path(pdf).stem[:40].replace(' ', '_')}_p{index + 1:03d}_v{variant}"
    made = 0
    for y in range(0, max(gray.shape[0] - TILE // 2, 1), STRIDE):
        for x in range(0, max(gray.shape[1] - TILE // 2, 1), STRIDE):
            inside = (centre[:, 0] >= x) & (centre[:, 0] < x + TILE) & (centre[:, 1] >= y) & (centre[:, 1] < y + TILE)
            if not inside.any() and rng.random() > EMPTY_SHARE:
                continue
            tile = np.full((TILE, TILE), 255, np.uint8)
            part = gray[y : y + TILE, x : x + TILE]
            if part.mean() > 254:
                continue
            tile[: part.shape[0], : part.shape[1]] = part
            rows = []
            for i in np.nonzero(inside)[0]:
                x0, y0, x1, y1 = np.clip(box[i] - [x, y, x, y], 0, TILE)
                leaf = int(pts[i, 7])
                ends = [(pts[i, 3], pts[i, 4]), (pts[i, 5], pts[i, 6])]
                keys = [(pts[i, 0], pts[i, 1]), ends[leaf], ends[1 - leaf]]
                text = f"0 {(x0 + x1) / 2 / TILE:.6f} {(y0 + y1) / 2 / TILE:.6f} {(x1 - x0) / TILE:.6f} {(y1 - y0) / TILE:.6f}"
                for kx, ky in keys:
                    seen = 0 <= kx - x < TILE and 0 <= ky - y < TILE
                    text += f" {min(max((kx - x) / TILE, 0), 1):.6f} {min(max((ky - y) / TILE, 0), 1):.6f} {2 if seen else 0}"
                rows.append(text)
            name = f"{stem}_{y:05d}_{x:05d}"
            cv2.imwrite(f"{out}/images/{split}/{name}.jpg", tile, [cv2.IMWRITE_JPEG_QUALITY, 92])
            Path(f"{out}/labels/{split}/{name}.txt").write_text("\n".join(rows))
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
    jobs = []
    counts = {"train": [0, 0], "val": [0, 0]}
    for pdf in sorted(SRC.glob("*.pdf")):
        kind = pdf.stem.partition("__")[0]
        if kind in usace.SKIP:
            continue
        for index, swings in pages(pdf):
            if kind in usace.LOCK and not (kind == "ortc" and index + 1 < usace.ORTC_LOCK_FROM):
                continue  # held out
            split = "val" if kind in VAL else "train"
            counts[split][0] += 1
            counts[split][1] += len(swings)
            variants = range(args.variants) if split == "train" else range(2)
            jobs.extend((str(pdf), index, swings, v, split, args.out) for v in variants)
    print("pages and swings:", counts, "jobs:", len(jobs), flush=True)
    with ProcessPoolExecutor(args.processes) as pool:
        tiles = sum(pool.map(one, jobs, chunksize=2))
    Path(args.out, "data.yaml").write_text(
        f"path: {args.out}\ntrain: images/train\nval: images/val\nkpt_shape: [3, 3]\nflip_idx: [0, 1, 2]\n"
        "names:\n  0: door_leaf\n"
    )
    print("tiles:", tiles)


if __name__ == "__main__":
    main()
