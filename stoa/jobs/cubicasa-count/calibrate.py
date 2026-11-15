"""Fit the calibration of one model or an ensemble on the DEV hold fold, and install it for the solver.

    cd stoa && uv run python jobs/cubicasa-count/calibrate.py --spec e1-cnx-dino-1024 --members cnx-dino-1024 --tta 1

It reads out/<member>/hold.npz (written by train.py on the GPU), copies each member's model.pt, meta.json and
ood.npz to artifacts/cubicasa-count/members/<member>/, and writes artifacts/cubicasa-count/<spec>.json:
per family a temperature (least hold NLL) and a probability threshold (best hold score, +1 right, -1 wrong,
0 abstained). It prints the hold table: exact accuracy, answered share, score, and the prior (train-fold mode).
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np

from bp.paths import ARTIFACTS
from bp.tools.count_head import FAMILIES, Calib, EnsembleSpec, ModelMeta

JOB = Path(__file__).resolve().parent
TARGET = ARTIFACTS / "cubicasa-count"
TEMPERATURES = np.round(np.arange(0.5, 3.01, 0.05), 2)
THRESHOLDS = np.round(np.arange(0.5, 0.995, 0.01), 2)


def softmax(x: np.ndarray, temperature: float) -> np.ndarray:
    z = x / temperature
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


def prior_modes() -> dict[str, int]:
    rows = [json.loads(line) for line in (JOB / "data" / "labels.jsonl").read_text().splitlines() if line.strip()]
    modes = {}
    for family in FAMILIES:
        values = [r["counts"][family] for r in rows if r["fold"] == "train" and family in r["counts"]]
        modes[family] = int(np.bincount(values).argmax())
    return modes


def fit_family(logits: np.ndarray, labels: np.ndarray, cap: int, keep: np.ndarray) -> tuple[Calib, dict[str, float]]:
    """`logits` [n, classes] (already averaged), `labels` [n] clamped to cap, `keep` [n] in distribution."""
    nll = [float(-np.log(softmax(logits, t)[np.arange(len(labels)), labels] + 1e-12).mean()) for t in TEMPERATURES]
    temperature = float(TEMPERATURES[int(np.argmin(nll))])
    p = softmax(logits, temperature)
    pred = p.argmax(axis=-1)
    conf = p.max(axis=-1)
    right = (pred == labels) & (pred < cap)
    usable = keep & (pred < cap)
    best_t, best = 1.01, 0.0
    for t in THRESHOLDS:
        answered = usable & (conf >= t)
        score = float(np.where(right, 1, -1)[answered].sum())
        if score > best or (score == best and best_t <= 1.0):
            best_t, best = float(t), score
    answered = usable & (conf >= best_t)
    n = len(labels)
    calib = Calib(
        temperature=temperature,
        threshold=best_t,
        hold_n=n,
        hold_accuracy=round(float((pred == labels).mean()), 4),
        hold_score=round(best / n, 4),
    )
    extra = {
        "answered": round(float(answered.mean()), 4),
        "precision": round(float(right[answered].mean()), 4) if answered.any() else 0.0,
    }
    return calib, extra


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--members", nargs="+", required=True)
    parser.add_argument("--tta", type=int, default=1)
    parser.add_argument("--ood-scale", type=float, default=1.0)
    args = parser.parse_args()

    metas, holds = [], []
    for member in args.members:
        source = JOB / "out" / member
        metas.append(ModelMeta.model_validate_json((source / "meta.json").read_text()))
        holds.append(np.load(source / "hold.npz"))
        target = TARGET / "members" / member
        target.mkdir(parents=True, exist_ok=True)
        for name in ("model.pt", "meta.json", "ood.npz"):
            shutil.copyfile(source / name, target / name)
    caps = metas[0].caps
    if any(m.caps != caps for m in metas):
        msg = "members must share caps"
        raise SystemExit(msg)
    if any(not np.array_equal(h["images"], holds[0]["images"]) for h in holds):
        msg = "members must share the hold fold"
        raise SystemExit(msg)
    labels = holds[0]["labels"]
    ratio = np.max([h["dist"] / m.ood_threshold for h, m in zip(holds, metas, strict=True)], axis=0)
    keep = ratio <= args.ood_scale
    modes = prior_modes()
    calib: dict[str, Calib] = {}
    table = []
    for i, family in enumerate(FAMILIES):
        mask = labels[:, i] >= 0
        logits = np.mean([h[f"logits_{family}"][:, : args.tta].mean(axis=1) for h in holds], axis=0)[mask]
        y = np.minimum(labels[mask, i], caps[family])
        calib[family], extra = fit_family(logits, y, caps[family], keep[mask])
        prior = float((labels[mask, i] == modes[family]).mean())
        table.append({"family": family, **calib[family].model_dump(), **extra, "prior_accuracy": round(prior, 4)})
    spec = EnsembleSpec(
        name=args.spec,
        members=tuple(f"members/{m}" for m in args.members),
        tta=args.tta,
        ood_scale=args.ood_scale,
        calib=calib,
    )
    TARGET.mkdir(parents=True, exist_ok=True)
    (TARGET / f"{args.spec}.json").write_text(spec.model_dump_json(indent=2))
    total = sum(r["hold_n"] for r in table)
    summary = {
        "spec": args.spec,
        "hold_items": total,
        "ood_rejected": round(float((~keep).mean()), 4),
        "accuracy": round(sum(r["hold_accuracy"] * r["hold_n"] for r in table) / total, 4),
        "score": round(sum(r["hold_score"] * r["hold_n"] for r in table) / total, 4),
        "answered": round(sum(r["answered"] * r["hold_n"] for r in table) / total, 4),
        "prior_accuracy": round(sum(r["prior_accuracy"] * r["hold_n"] for r in table) / total, 4),
    }
    out = JOB / "out" / f"calib-{args.spec}.json"
    out.write_text(json.dumps({"summary": summary, "families": table}, indent=2))
    print(f"{'family':14} {'n':>5} {'acc':>6} {'prior':>6} {'T':>5} {'thr':>5} {'ans':>6} {'prec':>6} {'score':>6}")
    for r in table:
        print(
            f"{r['family']:14} {r['hold_n']:5d} {r['hold_accuracy']:6.3f} {r['prior_accuracy']:6.3f} {r['temperature']:5.2f}"
            f" {r['threshold']:5.2f} {r['answered']:6.3f} {r['precision']:6.3f} {r['hold_score']:6.3f}"
        )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
