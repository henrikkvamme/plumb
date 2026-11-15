"""Score the symbol detector on whole validation sheets: counts, matches, and the size of false positives.

    # on the GPU VM, from the stoa directory (PDFs at data/external/sheets/usace, manifest from prepare.py):
    python jobs/sheet-symbols/evaluate.py run --weights best.pt --manifest /root/symbols/data/manifest.json --out det.json
    # anywhere:
    python jobs/sheet-symbols/evaluate.py score det.json

`run` renders each validation page as a whole sheet the way `prepare.py` does (variant 0: clean; variant 1: the
scan look), finds the symbols with the tiled inference of `detect.py`, and stores every detection above 0.05 with
the labels of the sheet and the inches of building per pixel.

`score` matches detections to labels of the same class (highest score first; IoU >= 0.3, or the centre of one box
inside the other, as a window box is thin) and reports per class and score threshold: precision, recall, and the
share of sheets whose count is within max(1, 3 %) of the label count. Sheets with no label of a class count too
(their right count is 0).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detect  # noqa: E402

THRESHOLDS = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8)


def run(args: argparse.Namespace) -> None:
    import prepare  # noqa: PLC0415
    from ultralytics import YOLO  # noqa: PLC0415

    model = YOLO(args.weights)
    sheets = []
    for entry in json.loads(Path(args.manifest).read_text()):
        if entry["split"] != "val":
            continue
        pdf = str(prepare.SRC / entry["pdf"])
        for variant in (0, 1):
            gray, boxes, ids = prepare.render(pdf, entry["index"], entry["rows"], entry["masks"], variant)
            import pymupdf  # noqa: PLC0415

            page = pymupdf.open(pdf)[entry["index"]]
            page.remove_rotation()
            zoom = gray.shape[1] / page.rect.width if variant == 0 else None
            rows = detect.detect(model, gray)
            turned = detect.detect(model, np.ascontiguousarray(np.rot90(gray)))  # the second opinion: other tiles
            pt_per_inch = 72 / entry["ft"] / 12
            sheets.append({
                "pdf": entry["pdf"], "index": entry["index"], "variant": variant, "ft": entry["ft"],
                "inch_per_px": 1 / (zoom * pt_per_inch) if zoom else None,
                "labels": [{"box": b.tolist(), "class": detect.CLASSES[i]} for b, i in zip(boxes, ids, strict=True)],
                "detections": rows, "turned": turned,
            })  # fmt: skip
            print(entry["pdf"][:40], entry["index"] + 1, variant, len(boxes), "labels",
                  sum(r["score"] >= 0.5 for r in rows), "found", flush=True)  # fmt: skip
    Path(args.out).write_text(json.dumps(sheets))


def same(a: list[float], b: list[float]) -> bool:
    if detect.iou(a, b) >= 0.3:
        return True
    ca, cb = ((a[0] + a[2]) / 2, (a[1] + a[3]) / 2), ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    return (b[0] <= ca[0] <= b[2] and b[1] <= ca[1] <= b[3]) or (a[0] <= cb[0] <= a[2] and a[1] <= cb[1] <= a[3])


def match(labels: list[list[float]], found: list[dict]) -> tuple[int, list[dict]]:
    """(true positives, the false positive detections)."""
    free = list(range(len(labels)))
    wrong = []
    hits = 0
    for d in sorted(found, key=lambda r: -r["score"]):
        j = next((j for j in free if same(d["box"], labels[j])), None)
        if j is None:
            wrong.append(d)
        else:
            free.remove(j)
            hits += 1
    return hits, wrong


def score(args: argparse.Namespace) -> None:
    sheets = [s for f in args.files for s in json.loads(Path(f).read_text())]
    if args.variant is not None:
        sheets = [s for s in sheets if s["variant"] == args.variant]
    print(f"sheets: {len(sheets)} (variants {sorted({s['variant'] for s in sheets})})")
    for cls in detect.CLASSES:
        n = sum(sum(lab["class"] == cls for lab in s["labels"]) for s in sheets)
        with_cls = sum(any(lab["class"] == cls for lab in s["labels"]) for s in sheets)
        print(f"\n{cls}: {n} labels on {with_cls} sheets")
        print("  thr  prec  recall  count ok (all sheets)  count ok (sheets with the class)")
        for t in THRESHOLDS:
            tp = fp = 0
            ok = ok_with = 0
            for s in sheets:
                labels = [lab["box"] for lab in s["labels"] if lab["class"] == cls]
                found = [d for d in s["detections"] if d["class"] == cls and d["score"] >= t]
                hits, wrong = match(labels, found)
                tp += hits
                fp += len(wrong)
                right = abs(len(found) - len(labels)) <= max(1, 0.03 * len(labels))
                ok += right
                if labels:
                    ok_with += right
            prec = tp / max(tp + fp, 1)
            rec = tp / max(n, 1)
            print(f"  {t:.1f}  {prec:.3f}  {rec:.3f}   {ok}/{len(sheets)}                 {ok_with}/{with_cls}")


def hand(args: argparse.Namespace) -> None:
    """Detector counts against the counts by eye of `handcount.json` (a truth that is not the signature rule)."""
    sheets = [s for f in args.files for s in json.loads(Path(f).read_text())]
    truth = json.loads((HERE / "handcount.json").read_text())["sheets"]
    for cls in detect.CLASSES:
        print(f"\n{cls}: sheet, variant, by eye, labels, found at " + " ".join(f"{t:.1f}" for t in THRESHOLDS))
        ok = dict.fromkeys(THRESHOLDS, 0)
        n = 0
        for h in truth:
            for s in sheets:
                if s["pdf"] != h["pdf"] or s["index"] != h["index"]:
                    continue
                n += 1
                labels = sum(lab["class"] == cls for lab in s["labels"])
                found = [sum(d["class"] == cls and d["score"] >= t for d in s["detections"]) for t in THRESHOLDS]
                for t, f in zip(THRESHOLDS, found, strict=True):
                    ok[t] += abs(f - h[cls]) <= max(1, 0.03 * h[cls])
                mark = "~" if cls in h["approx"] else " "
                print(f"  {h['pdf'][:34]:34} p{h['index'] + 1:<3} v{s['variant']}  {mark}{h[cls]:<4} {labels:<5} "
                      + " ".join(f"{f:>3}" for f in found))  # fmt: skip
        print("  count ok (by eye):", " ".join(f"{t:.1f}:{ok[t]}/{n}" for t in THRESHOLDS))


EXACT = False  # `abstain --exact`: a count is right only when it is equal


def close(a: int, b: int) -> bool:
    return a == b if EXACT else abs(a - b) <= max(1, 0.03 * b)


def abstain(args: argparse.Namespace) -> None:
    """Answered right, answered wrong and abstained against `handcount2.json`, per class, threshold and render.

    The tool answers with the count of the normal pass only when the pass on the sheet turned 90 degrees (other
    tiles, other context), or the normal pass of a second model (`--second det.json`), gives the same count (`--slack 0`) or one within max(1, 3 %) (`--slack 1`). The answer is
    right when it is within max(1, 3 %) of the count by eye.
    """
    global EXACT  # noqa: PLW0603
    EXACT = args.exact
    sheets = [s for f in args.files for s in json.loads(Path(f).read_text())]
    truth = json.loads((HERE / "handcount2.json").read_text())["sheets"]
    if args.second:  # the second opinion is another model's normal pass, not the turned pass
        other = {
            (s["pdf"], s["index"], s["variant"]): s["detections"] for s in json.loads(Path(args.second).read_text())
        }
        for s in sheets:
            s["turned"] = other[s["pdf"], s["index"], s["variant"]]
    for cls in ("toilet", "urinal"):
        for variant in sorted({s["variant"] for s in sheets}):
            print(f"\n{cls}, variant {variant}: thr  right  wrong  abstain   (no abstain rule: right/sheets)")
            for t in THRESHOLDS:
                right = wrong = held = plain = n = 0
                for h in truth:
                    s = next((s for s in sheets if (s["pdf"], s["index"], s["variant"]) == (h["pdf"], h["index"], variant)), None)  # fmt: skip
                    if s is None:
                        continue
                    n += 1
                    a = sum(d["class"] == cls and d["score"] >= t for d in s["detections"])
                    b = sum(d["class"] == cls and d["score"] >= t for d in s["turned"])
                    plain += close(a, h[cls])
                    agree = a == b if args.slack == 0 else close(b, a)
                    if not agree:
                        held += 1
                    elif close(a, h[cls]):
                        right += 1
                    else:
                        wrong += 1
                print(f"  {t:.1f}  {right:>5}  {wrong:>5}  {held:>7}   {plain}/{n}")
    if args.list:
        per_sheet(sheets, truth)


def per_sheet(sheets: list[dict], truth: list[dict]) -> None:
    """(normal, second) counts at 0.4, 0.5 and 0.6 for each hand-counted sheet."""
    for h in truth:
        for s in sheets:
            if (s["pdf"], s["index"]) == (h["pdf"], h["index"]):
                found = {c: [(sum(d["class"] == c and d["score"] >= t for d in s["detections"]),
                              sum(d["class"] == c and d["score"] >= t for d in s["turned"])) for t in (0.4, 0.5, 0.6)]
                         for c in ("toilet", "urinal")}  # fmt: skip
                print(h["pdf"][:38], h["index"] + 1, "v", s["variant"], "eye", h["toilet"], h["urinal"], found)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    ab = sub.add_parser("abstain")
    ab.add_argument("files", nargs="+")
    ab.add_argument("--slack", type=int, default=0)
    ab.add_argument("--list", action="store_true")
    ab.add_argument("--second")
    ab.add_argument("--exact", action="store_true")
    hd = sub.add_parser("hand")
    hd.add_argument("files", nargs="+")
    r = sub.add_parser("run")
    r.add_argument("--weights", required=True)
    r.add_argument("--manifest", required=True)
    r.add_argument("--out", required=True)
    s = sub.add_parser("score")
    s.add_argument("files", nargs="+")
    s.add_argument("--variant", type=int)
    args = parser.parse_args()
    {"run": run, "score": score, "hand": hand, "abstain": abstain}[args.cmd](args)


if __name__ == "__main__":
    np.set_printoptions(precision=3)
    main()
