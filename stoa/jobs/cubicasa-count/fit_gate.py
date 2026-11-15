"""Fit the style gate of one member: is this raster a CubiCasa-style plan? Runs on the laptop, outside the sandbox.

    cd stoa && uv run python jobs/cubicasa-count/fit_gate.py --member cnx-dino-768

The count head learned CubiCasa plans only. On a plan of another style it can be sure and wrong (measured: Swiss
plans rendered to PNG). The gate is a logistic regression on the member's pooled embedding (view 0):
positives are the CubiCasa DEV train fold, negatives are raster drawings of other sources (Swiss and IFC plan
PNGs, historic scans). Negatives split by a hash of the file into fit (70%) and test (30%). The threshold keeps
99% of the CubiCasa hold fold. It writes artifacts/cubicasa-count/members/<member>/gate.npz and prints the pass
rates on held-out data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

import numpy as np
import torch

from bp.paths import ARTIFACTS, DATASET
from bp.tools.count_head import _Member, letterbox, load_image, pick_device

JOB = Path(__file__).resolve().parent
NEGATIVE_SOURCES = {
    "swiss_dwellings": 500,
    "ifc_models": 300,
    "habs": 300,
    "finna": 300,
    "europeana": 300,
    "wikimedia": 500,
}
KEEP = 0.99


def is_test(path: Path) -> bool:
    return int(hashlib.sha1(path.name.encode()).hexdigest(), 16) % 10 < 3  # noqa: S324 - a split, not security


def embed(member: _Member, device: torch.device, paths: list[Path]) -> np.ndarray:
    out = []
    with torch.inference_mode():
        for path in paths:
            x = torch.from_numpy(letterbox(load_image(path), member.meta.side)).unsqueeze(0).to(device)
            embedding, _ = member.net(x)
            out.append(embedding[0].float().cpu().numpy())
    return np.stack(out)


def fit_logistic(x: np.ndarray, y: np.ndarray, weight_decay: float = 1e-3) -> tuple[np.ndarray, float]:
    xt = torch.from_numpy(x).double()
    yt = torch.from_numpy(y).double()
    w = torch.zeros(x.shape[1], dtype=torch.float64, requires_grad=True)
    b = torch.zeros((), dtype=torch.float64, requires_grad=True)
    pos = float(y.mean())
    sample_weight = torch.where(yt > 0, 0.5 / pos, 0.5 / (1 - pos))
    optimizer = torch.optim.LBFGS([w, b], max_iter=500, line_search_fn="strong_wolfe")

    def closure() -> torch.Tensor:
        optimizer.zero_grad()
        logits = xt @ w + b
        loss = (
            torch.nn.functional.binary_cross_entropy_with_logits(logits, yt, reduction="none") * sample_weight
        ).mean()
        loss = loss + weight_decay * (w * w).sum()
        loss.backward()
        return loss

    optimizer.step(closure)
    return w.detach().numpy(), float(b.detach())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--member", required=True)
    args = parser.parse_args()
    device = pick_device()
    folder = ARTIFACTS / "cubicasa-count" / "members" / args.member
    member = _Member(folder, device)

    rows = [json.loads(line) for line in (JOB / "data" / "labels.jsonl").read_text().splitlines() if line.strip()]
    pos_fit = [JOB / "data" / r["image"] for r in rows if r["fold"] == "train"]
    pos_hold = [JOB / "data" / r["image"] for r in rows if r["fold"] == "hold"]
    neg_fit: list[Path] = []
    neg_test: dict[str, list[Path]] = {}
    rng = random.Random(0)  # noqa: S311 - a sample, not security
    for source, count in NEGATIVE_SOURCES.items():
        files = sorted(
            p for p in (DATASET / "data" / source).iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"}
        )
        rng.shuffle(files)
        files = files[:count]
        neg_fit += [p for p in files if not is_test(p)]
        neg_test[source] = [p for p in files if is_test(p)]

    e_pos_fit = embed(member, device, pos_fit)
    e_pos_hold = embed(member, device, pos_hold)
    e_neg_fit = embed(member, device, neg_fit)
    e_neg_test = {s: embed(member, device, ps) for s, ps in neg_test.items()}

    x = np.concatenate([e_pos_fit, e_neg_fit])
    mean, scale = x.mean(axis=0), x.std(axis=0) + 1e-6
    y = np.concatenate([np.ones(len(e_pos_fit)), np.zeros(len(e_neg_fit))])
    w, b = fit_logistic((x - mean) / scale, y)

    def score(e: np.ndarray) -> np.ndarray:
        return ((e - mean) / scale) @ w + b

    threshold = float(np.quantile(score(e_pos_hold), 1 - KEEP))
    np.savez_compressed(
        folder / "gate.npz",
        mean=mean.astype(np.float32),
        scale=scale.astype(np.float32),
        w=w.astype(np.float32),
        b=np.float32(b),
        threshold=np.float32(threshold),
    )
    report = {
        "member": args.member,
        "fit": {"positives": len(e_pos_fit), "negatives": len(e_neg_fit)},
        "cubicasa_hold_pass": round(float((score(e_pos_hold) >= threshold).mean()), 4),
        "negatives_test_pass": {
            s: [len(e), round(float((score(e) >= threshold).mean()), 4)] for s, e in e_neg_test.items()
        },
    }
    (JOB / "out" / f"gate-{args.member}.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
