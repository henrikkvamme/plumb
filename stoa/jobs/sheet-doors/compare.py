"""Compare door detectors on whole validation sheets: door counts, matches and keypoint error per sheet.

    # on a GPU VM, from the stoa directory (the PDFs must be at data/external/sheets/usace):
    python jobs/sheet-doors/compare.py run --weights best.pt --out /root/research/cmp/y26m.json
    python jobs/sheet-doors/compare.py run --kind rfdetr --weights checkpoint_best_total.pth --out .../rf.json
    # anywhere, with the JSON files:
    python jobs/sheet-doors/compare.py score /root/research/cmp/*.json

`run` renders each validation page (`prepare.VAL`) as a whole sheet, the same way `prepare.py` renders it (same
seed, same scale, skew and scan look), with variants 0 to 3. Variants 0 and 1 are the sheets the validation tiles
come from. It finds the doors with the tiled inference of `predict.py` (1024 px tiles, stride 704, cut boxes
dropped, overlapping boxes merged) and stores every detection above 0.05 with the labels of the sheet.

`score` matches detections to labels (box IoU >= 0.5, highest score first) at several score thresholds and reports
per-sheet count accuracy (share of sheets within 1 door or 3 % of the label count), precision, recall, F1 and the
keypoint error of matched doors as a share of the door radius. The locked kinds are never rendered.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
TILE = 1024
SAME_DOOR = 0.45
THRESHOLDS = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7)


# ---------- rendering (a copy of the first half of `prepare.one`, so the same seed gives the same sheet) ----------


def render(pdf: str, index: int, swings: list, variant: int) -> tuple[np.ndarray, np.ndarray, float]:
    """The sheet as `prepare.py` renders it, its door swings in pixels, and the metres of building per pixel."""
    import cv2
    import pymupdf

    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(HERE.parent / "sheets"))
    import prepare
    import usace

    rng = random.Random(f"{pdf}:{index}:{variant}")
    page = pymupdf.open(pdf)[index]
    page.remove_rotation()
    scale = usace.feet_per_inch(page)
    m_per_px = scale[1] * 0.3048 / 72 if scale else 0.0  # per point; divided by the zoom below
    long_pt = max(page.rect.width, page.rect.height)
    zoom = rng.choice(prepare.LONG_SIDES) * rng.uniform(0.9, 1.1) / long_pt
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY, alpha=False)
    gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width).copy()
    pts = np.array(swings, float)
    pts[:, :7] *= zoom
    if variant and rng.random() < 0.5:
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
        gray = prepare.degrade(gray, rng)
    return gray, pts, m_per_px / zoom


def labels_of(pts: np.ndarray) -> list[dict]:
    sys.path.insert(0, str(HERE))
    import prepare

    out = []
    for row, box in zip(pts, prepare.boxes(pts), strict=True):
        leaf = int(row[7])
        ends = [(row[3], row[4]), (row[5], row[6])]
        out.append({
            "box": [round(float(v), 1) for v in box], "radius": round(float(row[2]), 1),
            "hinge": [round(float(row[0]), 1), round(float(row[1]), 1)],
            "leaf": [round(float(v), 1) for v in ends[leaf]], "closed": [round(float(v), 1) for v in ends[1 - leaf]],
        })  # fmt: skip
    return out


def prepare_src() -> Path:
    sys.path.insert(0, str(HERE))
    import prepare

    return prepare.SRC


def val_jobs(variants: int) -> list[tuple[str, int, list, int]]:
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(HERE.parent / "sheets"))
    import prepare
    import usace

    jobs = []
    for pdf in sorted(prepare.SRC.glob("*.pdf")):
        kind = pdf.stem.partition("__")[0]
        if kind not in prepare.VAL or kind in usace.LOCK:
            continue
        for index, swings in prepare.pages(pdf):
            jobs.extend((str(pdf), index, swings, v) for v in range(variants))
    return jobs


# ---------- detectors: each returns, per tile, a list of (box xyxy, score, [hinge, leaf, closed]) ----------


class Ultralytics:
    def __init__(self, weights: str, imgsz: int, half: bool, device: str) -> None:
        from ultralytics import YOLO

        self.model, self.imgsz, self.half, self.device = YOLO(weights, task="pose"), imgsz, half, device

    def __call__(self, tiles: list[np.ndarray]) -> list[list[tuple]]:
        extra = {"half": True} if self.half else {}
        results = self.model.predict(tiles, imgsz=self.imgsz, conf=0.05, verbose=False, device=self.device, **extra)
        out = []
        for r in results:
            if r.boxes is None or r.keypoints is None:
                out.append([])
                continue
            out.append(list(zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist(), r.keypoints.xy.tolist(), strict=True)))
        return out


class RFDETR:
    def __init__(self, weights: str, resolution: int) -> None:
        from rfdetr import RFDETRKeypointPreview

        model = RFDETRKeypointPreview.from_checkpoint(weights, resolution=resolution)
        try:  # the optimized predictor, as the rfdetr warning advises
            self.predictor = model.inference(compile=False)
        except Exception as error:
            print("rfdetr: no optimized predictor:", error, flush=True)
            self.predictor = model

    def __call__(self, tiles: list[np.ndarray]) -> list[list[tuple]]:
        # the tiles are grey in 3 channels, so the channel order does not matter
        found = self.predictor.predict(tiles, threshold=0.05)
        found = found if isinstance(found, list) else [found]
        out = []
        for k in found:
            boxes = k.data.get("xyxy", np.zeros((0, 4)))
            out.append([(list(map(float, b)), float(c), xy[:3].tolist())
                        for b, c, xy in zip(boxes, k.detection_confidence, k.xy, strict=True)])  # fmt: skip
        return out


# ---------- tiled inference (as `predict.py`) ----------


def iou(a: list[float], b: list[float]) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    inter = w * h
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def merge(rows: list[dict]) -> list[dict]:
    kept: list[dict] = []
    for row in sorted(rows, key=lambda r: -r["score"]):
        if all(iou(row["box"], other["box"]) < SAME_DOOR for other in kept):
            kept.append(row)
    return kept


def unflip(det: tuple, flip: str) -> tuple:
    (x0, y0, x1, y1), score, keys = det
    if "h" in flip:
        x0, x1 = TILE - x1, TILE - x0
        keys = [[TILE - kx, ky] for kx, ky in keys]
    if "v" in flip:
        y0, y1 = TILE - y1, TILE - y0
        keys = [[kx, TILE - ky] for kx, ky in keys]
    return (x0, y0, x1, y1), score, keys


def find(gray: np.ndarray, detect, stride: int, flips: tuple[str, ...], batch: int) -> list[dict]:
    height, width = gray.shape
    tiles, origins = [], []
    for y in range(0, max(height - TILE // 2, 1), stride):
        for x in range(0, max(width - TILE // 2, 1), stride):
            part = gray[y : y + TILE, x : x + TILE]
            if part.mean() > 254:
                continue
            tile = np.full((TILE, TILE), 255, np.uint8)
            tile[: part.shape[0], : part.shape[1]] = part
            tiles.append(tile)
            origins.append((x, y))
    views = []
    for flip in flips:
        rows = []
        for start in range(0, len(tiles), batch):
            chunk = tiles[start : start + batch]
            if "h" in flip:
                chunk = [t[:, ::-1] for t in chunk]
            if "v" in flip:
                chunk = [t[::-1, :] for t in chunk]
            chunk = [np.ascontiguousarray(np.stack([t] * 3, axis=2)) for t in chunk]
            for (ox, oy), dets in zip(origins[start : start + batch], detect(chunk), strict=True):
                for det in dets:
                    (x0, y0, x1, y1), score, keys = unflip(det, flip)
                    cut = min(x0, y0) < 4 or max(x1, y1) > TILE - 4
                    edge = (ox == 0 and x0 < 4) or (oy == 0 and y0 < 4) or ox + x1 > width - 4 or oy + y1 > height - 4
                    if cut and not edge:
                        continue
                    rows.append({
                        "box": [round(x0 + ox, 1), round(y0 + oy, 1), round(x1 + ox, 1), round(y1 + oy, 1)],
                        "score": round(score, 4),
                        "hinge": [round(keys[0][0] + ox, 1), round(keys[0][1] + oy, 1)],
                        "leaf": [round(keys[1][0] + ox, 1), round(keys[1][1] + oy, 1)],
                        "closed": [round(keys[2][0] + ox, 1), round(keys[2][1] + oy, 1)],
                    })  # fmt: skip
        views.append(merge(rows))
    if len(views) == 1:
        return views[0]
    # several views: one cluster per door, its score the mean over the views (a view that missed it gives 0)
    clusters: list[list[dict]] = []
    for row in sorted((r for v in views for r in v), key=lambda r: -r["score"]):
        for c in clusters:
            if iou(row["box"], c[0]["box"]) >= SAME_DOOR:
                c.append(row)
                break
        else:
            clusters.append([row])
    out = []
    for c in clusters:
        best = dict(c[0])
        best["score"] = round(sum(r["score"] for r in c[: len(views)]) / len(views), 4)
        out.append(best)
    return out


def run(args: argparse.Namespace) -> None:
    if args.kind == "ultralytics":
        detect = Ultralytics(args.weights, args.imgsz, args.half, args.device)
    else:
        detect = RFDETR(args.weights, args.imgsz)
    flips = ("",) + (("h", "v", "hv") if args.tta else ())
    jobs = val_jobs(args.variants)
    if args.limit:
        jobs = jobs[: args.limit]
    sheets = []
    for pdf, index, swings, variant in jobs:
        gray, pts, m_per_px = render(pdf, index, swings, variant)
        start = time.perf_counter()
        doors = find(gray, detect, args.stride, flips, args.batch)
        took = time.perf_counter() - start
        sheets.append({
            "pdf": Path(pdf).name, "page": index + 1, "variant": variant, "size": [gray.shape[1], gray.shape[0]],
            "m_per_px": m_per_px, "seconds": round(took, 3), "labels": labels_of(pts), "doors": doors,
        })  # fmt: skip
        print(f"{Path(pdf).name[:30]} p{index + 1} v{variant} {gray.shape[1]}x{gray.shape[0]} labels {len(pts)} "
              f"found@0.5 {sum(d['score'] >= 0.5 for d in doors)} {took:.2f}s", flush=True)  # fmt: skip
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    meta = {k: v for k, v in vars(args).items() if k != "func"}
    Path(args.out).write_text(json.dumps({"meta": meta, "sheets": sheets}))


# ---------- the same metrics for every model on the validation tiles ----------


def tile_labels(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().split("\n") if path.exists() else []:
        v = [float(x) * TILE for x in line.split()[1:]]
        if len(v) < 13:
            continue
        cx, cy, w, h = v[:4]
        hinge, leaf, closed = v[4:6], v[7:9], v[10:12]
        rows.append({"box": [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], "hinge": hinge, "leaf": leaf,
                     "closed": closed, "seen": [v[6] > 0, v[9] > 0, v[12] > 0],
                     "radius": (math.dist(hinge, leaf) + math.dist(hinge, closed)) / 2})  # fmt: skip
    return rows


def average_precision(hits: list[tuple[float, bool]], total: int) -> float:
    """COCO-style AP (101 recall points) from (score, true positive) of all detections."""
    hits = sorted(hits, key=lambda h: -h[0])
    tp = np.cumsum([h[1] for h in hits])
    fp = np.cumsum([not h[1] for h in hits])
    recall = tp / max(total, 1)
    precision = tp / np.maximum(tp + fp, 1)
    precision = np.maximum.accumulate(precision[::-1])[::-1] if len(precision) else precision
    out = 0.0
    for r in np.linspace(0, 1, 101):
        i = np.searchsorted(recall, r, side="left")
        out += precision[i] if i < len(precision) else 0.0
    return out / 101


def tiles(args: argparse.Namespace) -> None:
    import cv2

    detect = Ultralytics(args.weights, args.imgsz, args.half, args.device) if args.kind == "ultralytics" else (
        RFDETR(args.weights, args.imgsz))  # fmt: skip
    images = sorted(Path(args.data, "images", "val").glob("*.jpg"))
    found, truth = [], []
    start = time.perf_counter()
    for i in range(0, len(images), args.batch):
        chunk = [cv2.imread(str(p)) for p in images[i : i + args.batch]]
        for p, dets in zip(images[i : i + args.batch], detect(chunk), strict=True):
            found.append([{"box": list(b), "score": sc, "hinge": k[0], "leaf": k[1], "closed": k[2]} for b, sc, k in dets])
            truth.append(tile_labels(Path(args.data, "labels", "val", p.stem + ".txt")))
    took = time.perf_counter() - start
    total = sum(len(t) for t in truth)
    aps = []
    for t in np.arange(0.5, 0.96, 0.05):
        hits = []
        for dets, labs in zip(found, truth, strict=True):
            used = [False] * len(labs)
            for d in sorted(dets, key=lambda r: -r["score"]):
                best, best_iou = -1, t
                for j, lab in enumerate(labs):
                    if not used[j] and (v := iou(d["box"], lab["box"])) >= best_iou:
                        best, best_iou = j, v
                if best >= 0:
                    used[best] = True
                hits.append((d["score"], best >= 0))
        aps.append(average_precision(hits, total))
    # precision and recall at the score with the best F1 (as ultralytics reports them), and keypoints of the matches
    best = {"F1": -1.0}
    for thr in np.arange(0.05, 0.96, 0.05):
        tp = fp = 0
        kp_ok = []
        for dets, labs in zip(found, truth, strict=True):
            doors = [d for d in dets if d["score"] >= thr]
            n, pairs = match(doors, labs)
            tp, fp = tp + n, fp + len(doors) - n
            for d, lab in pairs:
                errs = [math.dist(d[k], lab[k]) / max(lab["radius"], 1)
                        for k, seen in zip(("hinge", "leaf", "closed"), lab["seen"], strict=True) if seen]  # fmt: skip
                kp_ok.append(max(errs, default=0) <= 0.15)
        p, r = tp / max(tp + fp, 1), tp / max(total, 1)
        f1 = 2 * p * r / max(p + r, 1e-9)
        if f1 > best["F1"]:
            best = {"thr": round(float(thr), 2), "P": round(p, 3), "R": round(r, 3), "F1": round(f1, 3),
                    "kp_ok15": round(sum(kp_ok) / max(len(kp_ok), 1), 3)}  # fmt: skip
    out = {"weights": args.weights, "tiles": len(images), "doors": total, "mAP50": round(aps[0], 3),
           "mAP50_95": round(float(np.mean(aps)), 3), **best, "ms_per_tile": round(1000 * took / len(images), 1)}  # fmt: skip
    print(json.dumps(out))
    if args.out:
        Path(args.out).write_text(json.dumps(out))


# ---------- scoring ----------


def match(doors: list[dict], labels: list[dict]) -> tuple[int, list[tuple[dict, dict]]]:
    used = [False] * len(labels)
    pairs = []
    for d in sorted(doors, key=lambda r: -r["score"]):
        best, best_iou = -1, 0.5
        for i, lab in enumerate(labels):
            if not used[i]:
                v = iou(d["box"], lab["box"])
                if v >= best_iou:
                    best, best_iou = i, v
        if best >= 0:
            used[best] = True
            pairs.append((d, labels[best]))
    return len(pairs), pairs


LEAF_M = (0.58, 1.40)  # the app keeps a door when its leaf (hinge to open end) is this long, on a sheet with a scale


def sized(doors: list[dict], m_per_px: float) -> list[dict]:
    return [d for d in doors if LEAF_M[0] <= math.dist(d["hinge"], d["leaf"]) * m_per_px <= LEAF_M[1]]


def score_file(path: str, group: str = "", size_filter: bool = False) -> dict:
    data = json.loads(Path(path).read_text())
    sheets = [s for s in data["sheets"] if s["pdf"].startswith(group)]
    if size_filter:
        sheets = [dict(s, doors=sized(s["doors"], s["m_per_px"])) for s in sheets]
    out = {"file": Path(path).name + (f" {group}" if group else "") + (" sized" if size_filter else ""), "sheets": len(sheets), "doors": sum(len(s["labels"]) for s in sheets),
           "s_per_sheet": round(statistics.mean(s["seconds"] for s in sheets), 2), "at": {}}  # fmt: skip
    for t in THRESHOLDS:
        tp = fp = fn = within = 0
        errs = {"hinge": [], "leaf": [], "closed": []}
        either = []  # all 3 points within 15 % of the radius, with the open and the closed end in either order
        for s in sheets:
            doors = [d for d in s["doors"] if d["score"] >= t]
            n, pairs = match(doors, s["labels"])
            tp, fp, fn = tp + n, fp + len(doors) - n, fn + len(s["labels"]) - n
            within += abs(len(doors) - len(s["labels"])) <= max(1, 0.03 * len(s["labels"]))
            for d, lab in pairs:
                r = max(lab["radius"], 1)
                for k in errs:
                    errs[k].append(math.dist(d[k], lab[k]) / r)
                swapped = max(math.dist(d["leaf"], lab["closed"]), math.dist(d["closed"], lab["leaf"])) / r
                same = max(math.dist(d["leaf"], lab["leaf"]), math.dist(d["closed"], lab["closed"])) / r
                either.append(max(math.dist(d["hinge"], lab["hinge"]) / r, min(same, swapped)) <= 0.15)
        p, r = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
        keys_ok = [max(a, b, c) <= 0.15 for a, b, c in zip(errs["hinge"], errs["leaf"], errs["closed"], strict=True)]
        out["at"][t] = {
            "count_ok": round(within / len(sheets), 3), "P": round(p, 3), "R": round(r, 3),
            "F1": round(2 * p * r / max(p + r, 1e-9), 3),
            "kp_med": {k: round(statistics.median(v), 3) if v else None for k, v in errs.items()},
            "kp_ok15": round(sum(keys_ok) / max(len(keys_ok), 1), 3),
            "kp_any15": round(sum(either) / max(len(either), 1), 3),
        }  # fmt: skip
    return out


def close(a: int, b: int) -> bool:
    """The app's agreement rule: two counts within max(1, 3 %)."""
    return abs(a - b) <= max(1, 0.03 * max(a, b))


def counts(path: str, thr: float, size_filter: bool) -> dict[tuple, tuple[int, int]]:
    """(pdf, page, variant) -> (detected doors, label doors) at a score threshold."""
    out = {}
    for s in json.loads(Path(path).read_text())["sheets"]:
        doors = [d for d in s["doors"] if d["score"] >= thr]
        if size_filter:
            doors = sized(doors, s["m_per_px"])
        out[(s["pdf"], s["page"], s["variant"])] = (len(doors), len(s["labels"]))
    return out


def pairs(args: argparse.Namespace) -> None:
    """For each pair of runs: the share of sheets where the two counts agree, and how often an agreed count is right."""
    print(f"{'model a':30} {'model b':30} {'group':5} {'thr':>4} {'sheets':>6} {'agree':>6} {'right':>6} "
          f"{'a ok':>5} {'b ok':>5}")  # fmt: skip
    # `run.json@0.4` fixes the threshold of that run; the others take each of --thr
    files = [(f.rpartition("@")[0], float(f.rpartition("@")[2])) if "@" in f else (f, None) for f in args.files]
    names = [Path(f).stem + (f"@{t}" if t is not None else "") for f, t in files]
    for i in range(len(files)):
        for j in range(i + 1, len(files)):
            for thr in args.thr:
                a = counts(files[i][0], files[i][1] or thr, not args.no_size)
                b = counts(files[j][0], files[j][1] or thr, not args.no_size)
                for group in args.groups:
                    keys = [k for k in a if k in b and k[0].startswith(group)]
                    agree = [k for k in keys if close(a[k][0], b[k][0])]
                    right = [k for k in agree if close(round((a[k][0] + b[k][0]) / 2), a[k][1])]
                    a_ok = sum(close(a[k][0], a[k][1]) for k in keys) / max(len(keys), 1)
                    b_ok = sum(close(b[k][0], b[k][1]) for k in keys) / max(len(keys), 1)
                    print(f"{names[i][:30]:30} {names[j][:30]:30} {group or 'all':5} {thr:>4} {len(keys):>6} "
                          f"{len(agree) / max(len(keys), 1):>6.2f} {len(right) / max(len(agree), 1):>6.2f} "
                          f"{a_ok:>5.2f} {b_ok:>5.2f}")  # fmt: skip


def score(args: argparse.Namespace) -> None:
    rows = [score_file(p, g, f) for p in args.files for g in args.groups for f in ((False, True) if args.sized else (False,))]
    if args.json:
        print(json.dumps(rows, indent=1))
        return
    print(f"{'file':44} {'thr':>4} {'count_ok':>8} {'P':>6} {'R':>6} {'F1':>6} {'kp_ok15':>7} {'any15':>6} "
          f"{'hinge':>6} {'leaf':>6} {'closed':>6} {'s/sheet':>7}")  # fmt: skip
    for row in rows:
        for t, m in row["at"].items():
            if args.thr and float(t) not in args.thr:
                continue
            k = m["kp_med"]
            print(f"{row['file'][:44]:44} {t:>4} {m['count_ok']:>8} {m['P']:>6} {m['R']:>6} {m['F1']:>6} "
                  f"{m['kp_ok15']:>7} {m['kp_any15']:>6} {k['hinge']!s:>6} {k['leaf']!s:>6} {k['closed']!s:>6} {row['s_per_sheet']:>7}")  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(required=True)
    r = sub.add_parser("run")
    r.add_argument("--weights", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--kind", choices=("ultralytics", "rfdetr"), default="ultralytics")
    r.add_argument("--imgsz", type=int, default=1024, help="model input size (RF-DETR: its resolution)")
    r.add_argument("--stride", type=int, default=704)
    r.add_argument("--tta", action="store_true", help="also run on flipped tiles and average the scores")
    r.add_argument("--variants", type=int, default=4)
    r.add_argument("--batch", type=int, default=32)
    r.add_argument("--half", action="store_true")
    r.add_argument("--device", default="0")
    r.add_argument("--limit", type=int, default=0)
    r.set_defaults(func=run)
    t = sub.add_parser("tiles", help="box AP and keypoints on the validation tiles, the same code for every model")
    t.add_argument("--weights", required=True)
    t.add_argument("--data", default="/root/doors")
    t.add_argument("--out", default="")
    t.add_argument("--kind", choices=("ultralytics", "rfdetr"), default="ultralytics")
    t.add_argument("--imgsz", type=int, default=1024)
    t.add_argument("--batch", type=int, default=32)
    t.add_argument("--half", action="store_true")
    t.add_argument("--device", default="0")
    t.set_defaults(func=tiles)
    q = sub.add_parser("pairs", help="agreement of the per-sheet counts of each pair of runs")
    q.add_argument("files", nargs="+")
    q.add_argument("--thr", type=float, nargs="*", default=[0.5])
    q.add_argument("--groups", nargs="*", default=["", "cof", "sprc"])
    q.add_argument("--no-size", action="store_true", help="count without the leaf size filter")
    q.set_defaults(func=pairs)
    s = sub.add_parser("score")
    s.add_argument("files", nargs="+")
    s.add_argument("--thr", type=float, nargs="*")
    s.add_argument("--json", action="store_true")
    s.add_argument("--groups", nargs="*", default=[""], help="score sheets whose PDF name starts with each, apart")
    s.add_argument("--sized", action="store_true", help="also score with the leaf size filter (LEAF_M)")
    s.set_defaults(func=score)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
