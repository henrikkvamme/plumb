"""Scanned twins of the test sheets: the same sheet as an office scanner or a phone camera gives it.

    python jobs/sheet-scans/make.py --partition dev                      # data/sheets-scan/, suites/sheets-scan.jsonl
    python jobs/sheet-scans/make.py --partition val --condition rot90    # data/sheets-scan-rot90-val/ and its suite

Conditions:

- scan: a small skew (up to 1.2 degrees), grey paper, softer ink, blur, sensor noise and JPEG marks. The size stays,
  as for a scan at the print resolution. This is the first recipe: its pixels must not change.
- skew: as scan, with a skew of 1.5 to 3 degrees.
- rot90: as scan, and the page is turned by 90 or 270 degrees (a sheet fed sideways).
- lowres: as scan, at half the resolution (a scan at 150 dpi of a 300 dpi print).
- photo: a phone photo of the print: a perspective of up to 4% of the page side, light that falls off to one side,
  more blur and noise.
- bleed: as scan, with the drawing on the back of the paper showing through (the sheet mirrored, faint).

The questions and keys are those of the clean sheet (door counts and room areas do not depend on the pixels), with
the condition in the item. The recipe of a sheet comes from its name and the condition, so a second build on the
same machine gives the same pixels. JPEG and blur can differ by a grey level between machines (macOS and Linux
builds of OpenCV), and the OCR and door caches are keyed by the pixels: build the twins once and copy them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

STOA = Path(__file__).resolve().parents[2]
CONDITIONS = ("scan", "skew", "rot90", "lowres", "photo", "bleed")


def scan(gray: np.ndarray, rng: random.Random, skew: tuple[float, float] = (-1.2, 1.2)) -> np.ndarray:
    height, width = gray.shape
    turn = cv2.getRotationMatrix2D((width / 2, height / 2), rng.uniform(*skew), 1.0)
    gray = cv2.warpAffine(gray, turn, (width, height), flags=cv2.INTER_LINEAR, borderValue=255)
    ink, paper = rng.uniform(25, 70), rng.uniform(222, 245)
    gray = (ink + gray.astype(np.float32) * (paper - ink) / 255).astype(np.uint8)
    gray = cv2.GaussianBlur(gray, (0, 0), rng.uniform(0.8, 1.4))
    noise = np.random.default_rng(rng.randrange(1 << 30)).normal(0, rng.uniform(5, 10), gray.shape)
    gray = np.clip(gray.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    _, data = cv2.imencode(".jpg", gray, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(40, 65)])
    return cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)


def photo(gray: np.ndarray, rng: random.Random) -> np.ndarray:
    """A phone photo of the print: perspective, uneven light, blur, noise and JPEG."""
    height, width = gray.shape
    side = 0.04 * min(width, height)
    corners = np.float32([[0, 0], [width, 0], [width, height], [0, height]])
    moved = corners + np.float32([[rng.uniform(-side, side), rng.uniform(-side, side)] for _ in range(4)])
    warp = cv2.getPerspectiveTransform(corners, moved)
    gray = cv2.warpPerspective(gray, warp, (width, height), flags=cv2.INTER_LINEAR, borderValue=200)
    ink, paper = rng.uniform(35, 80), rng.uniform(200, 235)
    light = np.linspace(1.0, rng.uniform(0.75, 0.9), width, dtype=np.float32)[None, :]
    if rng.random() < 0.5:
        light = light[:, ::-1]
    gray = (ink + gray.astype(np.float32) * (paper - ink) / 255) * light
    gray = cv2.GaussianBlur(gray, (0, 0), rng.uniform(1.0, 1.8))
    noise = np.random.default_rng(rng.randrange(1 << 30)).normal(0, rng.uniform(6, 12), gray.shape)
    gray = np.clip(gray + noise, 0, 255).astype(np.uint8)
    _, data = cv2.imencode(".jpg", gray, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(50, 75)])
    return cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)


def twin(gray: np.ndarray, condition: str, rng: random.Random) -> np.ndarray:
    if condition == "scan":
        return scan(gray, rng)
    if condition == "skew":
        sign = rng.choice((-1, 1))
        return scan(gray, rng, (1.5 * sign, 3.0 * sign) if sign > 0 else (3.0 * sign, 1.5 * sign))
    if condition == "rot90":
        turned = cv2.rotate(gray, rng.choice((cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE)))
        return scan(turned, rng)
    if condition == "lowres":
        half = cv2.resize(gray, (gray.shape[1] // 2, gray.shape[0] // 2), interpolation=cv2.INTER_AREA)
        return scan(half, rng, (-1.2, 1.2))
    if condition == "photo":
        return photo(gray, rng)
    if condition == "bleed":
        back = cv2.flip(gray, 1).astype(np.float32)
        share = rng.uniform(0.12, 0.25)
        mixed = 255 - (255 - gray.astype(np.float32)) - share * (255 - back)
        return scan(np.clip(mixed, 0, 255).astype(np.uint8), rng)
    raise ValueError(condition)


def make(args: tuple[str, str, Path]) -> str:
    name, condition, target = args
    if not target.exists():
        salt = name if condition == "scan" else f"{name}:{condition}"
        seed = int(hashlib.sha256(salt.encode()).hexdigest()[:8], 16)
        gray = cv2.imread(str(STOA / "data" / "sheets-test" / name), cv2.IMREAD_GRAYSCALE)
        cv2.imwrite(str(target), twin(gray, condition, random.Random(seed)))  # noqa: S311 - a recipe, not a secret
    return name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--partition", action="append", required=True)
    parser.add_argument("--condition", default="scan", choices=CONDITIONS)
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()
    if "lock" in args.partition:
        raise SystemExit("the lock partition is held out: no twins of it")
    # The first suite keeps its names: data/sheets-scan and suites/sheets-scan.jsonl hold the dev scans.
    suffix = "" if args.condition == "scan" and args.partition == ["dev"] else (
        f"-{args.condition}-{'-'.join(args.partition)}" if args.condition != "scan" else f"-{'-'.join(args.partition)}")
    suite = f"sheets-scan{suffix}"
    out = STOA / "data" / suite
    out.mkdir(parents=True, exist_ok=True)
    rows, jobs = [], {}
    with (STOA / "suites" / "sheets.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            if item["partition"] not in args.partition:
                continue
            name = Path(item["doc"]).name
            jobs[name] = (name, args.condition, out / name)
            item.update(item_id=f"{item['item_id']}-{args.condition}", doc=f"../{suite}/{name}", suite=suite,
                        condition=args.condition)  # fmt: skip
            rows.append(json.dumps(item, ensure_ascii=False))
    with ProcessPoolExecutor(args.jobs) as pool:
        list(pool.map(make, jobs.values()))
    (STOA / "suites" / f"{suite}.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(suite, len(jobs), "sheets", len(rows), "items")


if __name__ == "__main__":
    main()
