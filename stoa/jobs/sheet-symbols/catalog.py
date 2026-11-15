"""Count the symbol signatures of all dev USACE sheets, and draw a contact sheet of the frequent ones.

    uv run python jobs/sheet-symbols/catalog.py --out <dir> [--processes 2]

Writes `<dir>/catalog.json` (each signature key with its count, pages and up to 4 examples) and
`<dir>/sheet_NN.png` (one crop per key, with its number), so that a person can name the keys in `classes.json`.
The held-out kinds (`usace.LOCK`) are never opened.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import pymupdf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "sheets"))
import instances  # noqa: E402
import usace  # noqa: E402

STOA = HERE.parents[1]
SRC = STOA / "data/external/sheets/usace"
MIN_ITEMS = 6
SIDE_IN = (6, 9 * 12)  # long side of a symbol in inches


def key(sig: tuple) -> str:
    """The loose key of a signature: the box to 2 in and the line length to 8 in. Mirrored copies of one family
    can differ by a drawing or two, so the counts of drawings and items are not in the key."""
    _, _, short, long, length = sig
    return f"{round(short / 2) * 2}x{round(long / 2) * 2}L{round(length / 8) * 8}"


def dev_pages() -> list[tuple[str, int, float]]:
    """(pdf, page index, feet per inch) of each large dev page with one scale."""
    out = []
    for pdf in sorted(SRC.glob("*.pdf")):
        kind = pdf.stem.partition("__")[0]
        if kind in usace.SKIP:
            continue
        doc = pymupdf.open(pdf)
        for i, page in enumerate(doc):
            if kind in usace.LOCK and not (kind == "ortc" and i + 1 < usace.ORTC_LOCK_FROM):
                continue
            if max(page.rect.width, page.rect.height) / 72 < usace.MIN_SIDE_IN:
                continue
            page.remove_rotation()
            scale = usace.feet_per_inch(page)
            if scale:
                out.append((str(pdf), i, scale[1]))
    return out


THUMB_IN = 0.75  # inches of building per pixel of a thumbnail
THUMB = 96  # pixels: a thumbnail shows 6 ft around the centre of a run


def page_groups(job: tuple[str, int, float]) -> list[tuple[str, tuple, list[float], np.ndarray | None]]:
    """(key, signature, box, thumbnail) of each candidate run. The thumbnail is drawn at a fixed scale in inches."""
    pdf, index, ft = job
    page = pymupdf.open(pdf)[index]
    page.remove_rotation()
    pt_ft = 72 / ft
    zoom = 12 / THUMB_IN / pt_ft  # pixels per point
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY, alpha=False)
    gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width)
    out = []
    seen: set[str] = set()
    for g in instances.groups(page, ft):
        sig = g.signature(pt_ft)
        if g.items >= MIN_ITEMS and SIDE_IN[0] <= sig[3] <= SIDE_IN[1]:
            k = key(sig)
            thumb = None
            if k not in seen:
                seen.add(k)
                cx, cy = int((g.rect.x0 + g.rect.x1) / 2 * zoom), int((g.rect.y0 + g.rect.y1) / 2 * zoom)
                thumb = np.full((THUMB, THUMB), 255, np.uint8)
                part = gray[max(cy - THUMB // 2, 0) : cy + THUMB // 2, max(cx - THUMB // 2, 0) : cx + THUMB // 2]
                thumb[: part.shape[0], : part.shape[1]] = part
            out.append((k, sig, [g.rect.x0, g.rect.y0, g.rect.x1, g.rect.y1], thumb))
    return out


def crop(pdf: str, index: int, rect: list[float], size: int = 200) -> np.ndarray:
    page = pymupdf.open(pdf)[index]
    page.remove_rotation()
    r = pymupdf.Rect(rect)
    pad = max(r.width, r.height) * 0.6 + 2
    clip = pymupdf.Rect(r.x0 - pad, r.y0 - pad, r.x1 + pad, r.y1 + pad)
    zoom = size / max(clip.width, clip.height)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, colorspace=pymupdf.csRGB)
    im = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3).copy()
    cv2.rectangle(im, (int((r.x0 - clip.x0) * zoom), int((r.y0 - clip.y0) * zoom)),
                  (int((r.x1 - clip.x0) * zoom), int((r.y1 - clip.y0) * zoom)), (255, 0, 0), 1)  # fmt: skip
    tile = np.full((size, size, 3), 255, np.uint8)
    tile[: im.shape[0], : im.shape[1]] = im[:size, :size]
    return tile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--processes", type=int, default=2)
    parser.add_argument("--top", type=int, default=400)
    parser.add_argument("--max-ft", type=float, default=16.0)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = [j for j in dev_pages() if j[2] <= args.max_ft]  # site plans are too coarse for symbols
    print("pages:", len(jobs), flush=True)
    found: dict[str, dict] = defaultdict(lambda: {"count": 0, "pages": set(), "examples": [], "sigs": defaultdict(int)})
    with ProcessPoolExecutor(args.processes) as pool:
        for job, rows in zip(jobs, pool.map(page_groups, jobs, chunksize=1), strict=True):
            for k, sig, rect, thumb in rows:
                entry = found[k]
                if thumb is not None and "thumb" not in entry:
                    entry["thumb"] = thumb
                entry["count"] += 1
                entry["pages"].add(f"{Path(job[0]).name}:{job[1]}")
                entry["sigs"][str(sig)] += 1
                if len(entry["examples"]) < 4 and all(e[0] != job[0] or e[1] != job[1] for e in entry["examples"]):
                    entry["examples"].append((job[0], job[1], rect))
    ranked = sorted(found.items(), key=lambda kv: (-len(kv[1]["pages"]), -kv[1]["count"]))[: args.top]
    data = [
        {"n": n, "key": k, "count": e["count"], "pages": len(e["pages"]), "examples": e["examples"],
         "sigs": dict(sorted(e["sigs"].items(), key=lambda kv: -kv[1])[:4])}
        for n, (k, e) in enumerate(ranked)
    ]  # fmt: skip
    (out / "catalog.json").write_text(json.dumps(data, indent=1))
    allkeys = sorted(found, key=lambda k: -found[k]["count"])
    np.savez_compressed(out / "thumbs.npz", keys=np.array(allkeys), counts=np.array([found[k]["count"] for k in allkeys]),
                        pages=np.array([len(found[k]["pages"]) for k in allkeys]),
                        thumbs=np.stack([found[k]["thumb"] for k in allkeys]))  # fmt: skip
    (out / "examples.json").write_text(json.dumps({k: found[k]["examples"] for k in allkeys}))
    per = 48
    for s in range(0, len(data), per):
        tiles = []
        for entry in data[s : s + per]:
            pdf, index, rect = entry["examples"][0]
            tile = crop(pdf, index, rect)
            cv2.putText(tile, f"{entry['n']} {entry['key']} x{entry['count']}", (2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38,
                        (0, 0, 255), 1)  # fmt: skip
            tiles.append(tile)
        while len(tiles) % 8:
            tiles.append(np.full_like(tiles[0], 255))
        rows = [np.hstack(tiles[i : i + 8]) for i in range(0, len(tiles), 8)]
        cv2.imwrite(str(out / f"sheet_{s // per:02d}.png"), cv2.cvtColor(np.vstack(rows), cv2.COLOR_RGB2BGR))
    print("keys:", len(found), "written:", len(data))


if __name__ == "__main__":
    main()
