"""Build the training set for the CubiCasa detector. Two steps, so only small files cross the slow uplink.

    uv run python jobs/cubicasa-detect/prepare.py labels [--limit N]       # on the Mac: labels.json, plans.json
    python prepare.py views --zip /root/cache/cubicasa5k.zip               # on the VM: data/coco from the public zip

- Plans: Stoa DEV partition only. 15 % of DEV groups are held out (`hold`) for model selection and thresholds.
  VAL and LOCK plans are never read here.
- Labels: `bp.toolbench.cubicasa_detect.plan_labels` (SVG rules that reproduce Stoa's counts). Plans whose
  label counts disagree with Stoa's key are excluded.
- Images: the Stoa PNG `<group>-<id>.png` is byte-identical to `<group>/<id>/F1_original.png` in the public
  CubiCasa5K zip, so the VM reads the zip it downloads itself.
- Views: `symbol_detector.plan_views` (vendored copy of `bp.tools.symbol_detector`), the same global view and
  tiles that inference uses. A small object goes into a tile when at least half of it is visible; a room only
  when 90 % of it is visible.
- Output: data/coco/{train,valid}/ with `_annotations.coco.json` (category ids 0..14, flat supercategories).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import zipfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
# `gpu run` syncs this folder with --delete, so on the VM the views and outputs live outside it (CDET_ROOT).
COCO = Path(os.environ.get("CDET_ROOT", str(HERE))) / "data" / "coco"
HOLD_FRACTION = 0.15
SMALL_VISIBLE = 0.5
LARGE_VISIBLE = 0.9
MIN_BOX = 2.0


def held_out(group: str) -> bool:
    digest = hashlib.sha256(f"cubicasa-detect:{group}".encode()).digest()
    return digest[0] / 256 < HOLD_FRACTION


# ----------------------------------------------------------------------------- step 1, on the Mac


def labels(limit: int) -> None:
    from bp.suites import read_items  # noqa: PLC0415
    from bp.toolbench.cubicasa_detect import plan_labels, plans_by_partition, verify  # noqa: PLC0415
    from bp.tools import symbol_detector  # noqa: PLC0415

    items = read_items("stoa")
    dev = plans_by_partition(items)["dev"]
    stems = sorted(dev)[: limit or None]
    report = verify(items, stems)
    bad = set(report.pop("bad_plans"))
    print(json.dumps({k: report[k] for k in ("plans", "questions", "agreement", "plans_with_disagreement")}))
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir()
    out = {}
    for stem in stems:
        if stem in bad:
            continue
        lab = plan_labels(stem)
        out[stem] = {
            "split": "valid" if held_out(dev[stem][0].group) else "train",
            "width": lab.width, "height": lab.height,
            "boxes": [[label, *(round(v, 2) for v in box)] for label, box in lab.boxes],
        }  # fmt: skip
    (DATA / "labels.json").write_text(json.dumps(out))
    plans = {
        "train": sorted(s for s, v in out.items() if v["split"] == "train"),
        "hold": sorted(s for s, v in out.items() if v["split"] == "valid"),
        "excluded": sorted(bad),
        "label_check": report,
    }
    (DATA / "plans.json").write_text(json.dumps(plans, indent=1))
    vendor = HERE / "_vendor"
    vendor.mkdir(exist_ok=True)
    shutil.copyfile(symbol_detector.__file__, vendor / "symbol_detector.py")
    print(json.dumps({"train_plans": len(plans["train"]), "hold_plans": len(plans["hold"])}))


# ----------------------------------------------------------------------------- step 2, on the VM

_ZIP: zipfile.ZipFile | None = None


def _image(stem: str, source: str):  # noqa: ANN202 - PIL is imported in the worker
    global _ZIP  # noqa: PLW0603 - one zip handle per worker process
    sys.path.insert(0, str(HERE / "_vendor"))
    import symbol_detector as sd  # noqa: PLC0415

    if source.endswith(".zip"):
        if _ZIP is None:
            _ZIP = zipfile.ZipFile(source)
        group, ident = stem.rsplit("-", 1)
        return sd.load_rgb(io.BytesIO(_ZIP.read(f"cubicasa5k/{group}/{ident}/F1_original.png")))
    return sd.load_rgb(Path(source) / f"{stem}.png")


def build(stem: str, plan: dict, source: str) -> list[dict]:
    sys.path.insert(0, str(HERE / "_vendor"))
    import symbol_detector as sd  # noqa: PLC0415

    image = _image(stem, source)
    if image.size != (plan["width"], plan["height"]):
        raise ValueError(f"{stem}: image {image.size} is not the labelled size")
    split = plan["split"]
    out = []
    for index, view in enumerate(sd.plan_views(image.width, image.height)):
        anns = []
        for label, *box in plan["boxes"]:
            x0, y0, x1, y1 = view.to_view(box)
            area = max(1e-6, (x1 - x0) * (y1 - y0))
            cx0, cy0 = max(0.0, x0), max(0.0, y0)
            cx1, cy1 = min(float(view.size), x1), min(float(view.size), y1)
            if cx1 - cx0 < MIN_BOX or cy1 - cy0 < MIN_BOX:
                continue
            visible = (cx1 - cx0) * (cy1 - cy0) / area
            if view.kind == "tile" and visible < (SMALL_VISIBLE if label in sd.SMALL else LARGE_VISIBLE):
                continue
            if label == "floorplan" and (box[2] - box[0]) < 8:
                continue  # a floor group with no geometry: counted in the key, but nothing to see
            anns.append({"label": label, "bbox": [cx0, cy0, cx1 - cx0, cy1 - cy0]})
        if view.kind == "tile" and not anns:
            continue  # an empty tile teaches little; the global view already shows the blank areas
        name = f"{stem}__{index}.png"
        sd.render_view(image, view).save(COCO / split / name, compress_level=1)
        out.append({"file": name, "kind": view.kind, "anns": anns})
    return out


def views(source: str, workers: int, extra: list[str]) -> None:
    sys.path.insert(0, str(HERE / "_vendor"))
    import symbol_detector as sd  # noqa: PLC0415

    plans = json.loads((DATA / "labels.json").read_text())
    sources = dict.fromkeys(plans, source)
    for item in extra:  # "folder" or "folder=labels file": other drawings, labels in the same format, DEV only
        folder, _, file = item.partition("=")
        more = json.loads(Path(file or Path(folder) / "labels.json").read_text())
        more = {k: v for k, v in more.items() if v.get("partition", "dev") == "dev"}
        plans.update(more)
        sources.update(dict.fromkeys(more, folder))
    if COCO.exists():
        shutil.rmtree(COCO)
    for split in ("train", "valid"):
        (COCO / split).mkdir(parents=True)
    stems = sorted(plans)
    with ProcessPoolExecutor(workers) as pool:
        results = list(pool.map(build, stems, [plans[s] for s in stems], [sources[s] for s in stems], chunksize=8))
    categories = [{"id": i, "name": name, "supercategory": name} for i, name in enumerate(sd.CLASSES)]
    stats: Counter[str] = Counter()
    for split in ("train", "valid"):
        images, annotations = [], []
        for stem, rendered in zip(stems, results, strict=True):
            if plans[stem]["split"] != split:
                continue
            for view in rendered:
                image_id = len(images)
                images.append({"id": image_id, "file_name": view["file"], "width": 1024, "height": 1024})
                stats[f"{split}/{view['kind']}"] += 1
                for ann in view["anns"]:
                    x, y, w, h = ann["bbox"]
                    annotations.append({
                        "id": len(annotations), "image_id": image_id, "category_id": sd.CLASSES.index(ann["label"]),
                        "bbox": [round(x, 2), round(y, 2), round(w, 2), round(h, 2)], "area": round(w * h, 2),
                        "iscrowd": 0,
                    })  # fmt: skip
                    stats[f"{split}/{ann['label']}"] += 1
        coco = {"images": images, "annotations": annotations, "categories": categories}
        (COCO / split / "_annotations.coco.json").write_text(json.dumps(coco))
    (COCO / "view_stats.json").write_text(json.dumps(dict(sorted(stats.items())), indent=1))
    print(json.dumps(dict(sorted(stats.items()))), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["labels", "views"])
    parser.add_argument("--limit", type=int, default=0, help="labels: keep this many DEV plans (a smoke test).")
    parser.add_argument("--zip", default="/root/cache/cubicasa5k.zip", help="views: the public zip or a PNG folder.")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--extra", action="append", default=[], help="views: more PNG folders with labels.")
    args = parser.parse_args()
    if args.step == "labels":
        labels(args.limit)
    else:
        views(args.zip, args.workers, args.extra)


if __name__ == "__main__":
    main()
