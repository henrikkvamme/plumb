"""Build the compact training set for the CubiCasa count model. Run on the laptop, before the GPU job.

    cd stoa && uv run python jobs/cubicasa-count/prepare.py

It reads the DEV partition only (labels from suites/stoa.jsonl). VAL is for the sealed report and LOCK is never
read. Output, all git-ignored:
    data/images/<n>.png   the plan, RGB on white, longest side at most 1280 (count_head.load_image)
    data/labels.jsonl     one row per plan: image, group, style, fold (train | hold), counts per family
    data/count_head.py    a copy of src/bp/tools/count_head.py, so the job uses the same code
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from bp.contract import CountKey
from bp.paths import DATASET
from bp.suites import read_items
from bp.tools import count_head
from bp.tools.count_head import FAMILY_CODES, load_image

JOB = Path(__file__).resolve().parent
OUT = JOB / "data"
HOLD_SHARE = 5  # one group in five goes to the hold fold (threshold and model selection)


def fold_of(group: str) -> str:
    return "hold" if int(hashlib.sha1(group.encode()).hexdigest(), 16) % HOLD_SHARE == 0 else "train"  # noqa: S324 - a split, not security


def _convert(job: tuple[str, str]) -> tuple[str, int, int]:
    source, target = job
    image = load_image(DATASET / source)
    image.save(OUT / target, optimize=False, compress_level=6)
    return target, image.width, image.height


def main() -> None:
    plans: dict[str, dict[str, object]] = {}
    counts: dict[str, dict[str, int]] = defaultdict(dict)
    for item in read_items("stoa"):
        if item.source != "cubicasa5k" or item.partition != "dev":
            continue
        if not isinstance(item.key, CountKey):
            continue
        family = FAMILY_CODES.get(item.family.rsplit("/", 1)[-1])
        if family is None:
            continue
        counts[item.doc][family] = item.key.value
        if item.doc not in plans:
            stem = Path(item.doc).stem
            plans[item.doc] = {"group": item.group, "style": stem.rsplit("-", 1)[0], "fold": fold_of(item.group)}
    (OUT / "images").mkdir(parents=True, exist_ok=True)
    jobs = []
    for index, doc in enumerate(sorted(plans)):
        target = f"images/{index:05d}.png"
        plans[doc]["image"] = target
        jobs.append((doc, target))
    with ProcessPoolExecutor() as pool:
        sizes = {t: (w, h) for t, w, h in pool.map(_convert, jobs, chunksize=16)}
    with (OUT / "labels.jsonl").open("w") as handle:
        for doc in sorted(plans):
            row = dict(plans[doc])
            row["size"] = sizes[str(row["image"])]
            row["counts"] = counts[doc]
            handle.write(json.dumps(row) + "\n")
    shutil.copyfile(count_head.__file__, OUT / "count_head.py")
    folds = defaultdict(int)
    for row in plans.values():
        folds[str(row["fold"])] += 1
    total = sum(f.stat().st_size for f in (OUT / "images").iterdir())
    print(json.dumps({"plans": len(plans), "folds": folds, "bytes": total}))


if __name__ == "__main__":
    main()
