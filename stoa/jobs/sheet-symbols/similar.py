"""Propose names for unnamed catalog keys: the named key whose thumbnail looks most alike, in any of 8 turns.

    uv run python jobs/sheet-symbols/similar.py --cat <catalog dir> --out <dir> [--viewed 400]

Thumbnails are drawn at one scale in inches (`catalog.THUMB_IN`), so a toilet of one set looks like a toilet of
another set at the same size. The keys of the first `--viewed` catalog ranks that have no name were looked at and
are not symbols: they are the negatives. For each class, a contact sheet of candidate keys sorted by likeness lets a
person accept them into `classes.json`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
CLASSES = ("toilet", "urinal", "sink", "window", "shower")


def feature(thumb: np.ndarray) -> np.ndarray:
    """Eight unit vectors (the turns and mirrors) of the centre of a thumbnail."""
    ink = 1 - thumb.astype(np.float32) / 255
    c = ink.shape[0] // 2
    ink = ink[c - 32 : c + 32, c - 32 : c + 32]
    ink = cv2.GaussianBlur(ink, (0, 0), 1.5)
    small = cv2.resize(ink, (32, 32), interpolation=cv2.INTER_AREA)
    out = []
    for flip in (False, True):
        a = small[:, ::-1] if flip else small
        for k in range(4):
            v = np.rot90(a, k).ravel()
            out.append(v / (np.linalg.norm(v) + 1e-6))
    return np.stack(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cat", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--viewed", type=int, default=400)
    parser.add_argument("--per-sheet", type=int, default=64)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    data = np.load(Path(args.cat) / "thumbs.npz")
    keys, counts, thumbs = list(data["keys"]), data["counts"], data["thumbs"]
    names = json.loads((HERE / "classes.json").read_text())
    by_key = {k: c for c, ks in names.items() if not c.startswith("_") for k in ks}
    ranked = [e["key"] for e in json.loads((Path(args.cat) / "catalog.json").read_text())][: args.viewed]
    negative = {k for k in ranked if k not in by_key}
    feats = np.stack([feature(t) for t in thumbs])  # keys x 8 x 1024
    index = {k: i for i, k in enumerate(keys)}
    refs = {c: [index[k] for k, v in by_key.items() if v == c and k in index] for c in (*CLASSES, "mask")}
    neg = [index[k] for k in negative if k in index]
    base = feats[:, 0, :]  # one turn of each key against all turns of the references

    def best(ids: list[int]) -> tuple[np.ndarray, np.ndarray]:
        if not ids:
            return np.zeros(len(keys)), np.zeros(len(keys), int)
        sims = np.einsum("nd,mtd->nmt", base, feats[ids]).max(axis=2)  # n x m
        return sims.max(axis=1), np.array(ids)[sims.argmax(axis=1)]

    neg_sim, neg_ref = best(neg)
    rows = []
    for c in CLASSES:
        sim, ref = best(refs[c])
        for i, k in enumerate(keys):
            if k in by_key or k in negative:
                continue
            if sim[i] > 0.55 and sim[i] > neg_sim[i]:
                rows.append({"class": c, "key": k, "sim": round(float(sim[i]), 3), "neg": round(float(neg_sim[i]), 3),
                             "ref": keys[ref[i]], "count": int(counts[i])})  # fmt: skip
    # one class per key: the most alike
    keep: dict[str, dict] = {}
    for r in rows:
        if r["key"] not in keep or r["sim"] > keep[r["key"]]["sim"]:
            keep[r["key"]] = r
    rows = sorted(keep.values(), key=lambda r: (r["class"], -r["sim"]))
    (out / "candidates.json").write_text(json.dumps(rows, indent=1))
    for c in CLASSES:
        mine = [r for r in rows if r["class"] == c]
        for s in range(0, len(mine), args.per_sheet):
            tiles = []
            for n, r in enumerate(mine[s : s + args.per_sheet], start=s):
                t = cv2.cvtColor(cv2.resize(thumbs[index[r["key"]]], (192, 192), interpolation=cv2.INTER_NEAREST),
                                 cv2.COLOR_GRAY2BGR)  # fmt: skip
                cv2.rectangle(t, (64, 64), (128, 128), (220, 220, 255), 1)
                cv2.putText(t, f"{n} {r['key']}", (2, 11), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 0, 255), 1)
                cv2.putText(t, f"{r['sim']:.2f}/{r['neg']:.2f} x{r['count']}", (2, 188), cv2.FONT_HERSHEY_SIMPLEX, 0.36,
                            (200, 0, 0), 1)  # fmt: skip
                tiles.append(t)
            while len(tiles) % 8:
                tiles.append(np.full((192, 192, 3), 255, np.uint8))
            sheet = np.vstack([np.hstack(tiles[i : i + 8]) for i in range(0, len(tiles), 8)])
            cv2.imwrite(str(out / f"{c}_{s // args.per_sheet:02d}.png"), sheet)
        print(c, "candidates:", len(mine), "named:", len(refs[c]))


if __name__ == "__main__":
    main()
