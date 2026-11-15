"""Train one count model on the DEV train fold, and score it on the DEV hold fold. Runs on the GPU VM.

    python train.py --backbone convnext_tiny.dinov3_lvd1689m --side 1024 --name cnt-dino-1024

Writes out/<name>/: model.pt (fp16 state dict), meta.json, ood.npz (embedding mean and precision),
hold.npz (hold logits for all 8 dihedral views, labels), history.json.
"""

# ruff: noqa: S311, PLR0915, PLW2901, NPY002 - a training script: random augmentation, one long main
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset

JOB = Path(__file__).resolve().parent
DATA = JOB / "data"
sys.path.insert(0, str(DATA))
import count_head as ch  # noqa: E402 - the copy that prepare.py wrote

VIEWS = 8
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def read_rows() -> list[dict]:
    return [json.loads(line) for line in (DATA / "labels.jsonl").read_text().splitlines() if line.strip()]


def fit_caps(rows: list[dict]) -> dict[str, int]:
    """Classes 0..cap-1 are exact counts and class `cap` means "cap or more". 99.5% of train values are exact."""
    caps = {}
    for family in ch.FAMILIES:
        values = np.asarray([r["counts"][family] for r in rows if family in r["counts"]])
        caps[family] = max(2, int(np.quantile(values, 0.995)) + 1)
    return caps


class Plans(Dataset):
    def __init__(self, rows: list[dict], caps: dict[str, int], side: int, *, train: bool) -> None:
        self.rows, self.caps, self.side, self.train = rows, caps, side, train

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        row = self.rows[index]
        with Image.open(DATA / row["image"]) as raw:
            image = raw.convert("RGB")
        if self.train:
            if random.random() < 0.3:
                image = image.convert("L").convert("RGB")
            scale = random.uniform(0.8, 1.0)
            offset = (random.random(), random.random())
            x = torch.from_numpy(ch.letterbox(image, self.side, scale, offset))
            x = ch.dihedral(x, random.randrange(VIEWS))
            x = x * random.uniform(0.9, 1.1) + random.uniform(-0.1, 0.1)
        else:
            x = torch.from_numpy(ch.letterbox(image, self.side))
        y = torch.full((len(ch.FAMILIES),), -1, dtype=torch.long)
        for i, family in enumerate(ch.FAMILIES):
            if family in row["counts"]:
                y[i] = min(row["counts"][family], self.caps[family])
        return x, y


def loss_of(logits: dict[str, torch.Tensor], y: torch.Tensor, smoothing: float) -> torch.Tensor:
    total = torch.zeros((), device=y.device)
    for i, family in enumerate(ch.FAMILIES):
        mask = y[:, i] >= 0
        if mask.any():
            total = total + nn.functional.cross_entropy(
                logits[family][mask].float(), y[mask, i], label_smoothing=smoothing
            )
    return total


@torch.inference_mode()
def evaluate(
    model: ch.CountNet, loader: DataLoader, views: int
) -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray]:
    """Logits per family as [n, views, classes], the labels [n, families] and the view-0 embedding [n, dim]."""
    model.eval()
    logits: dict[str, list[np.ndarray]] = {f: [] for f in ch.FAMILIES}
    labels, embeddings = [], []
    for x, y in loader:
        x = x.to(DEVICE, non_blocking=True)
        per_view: dict[str, list[torch.Tensor]] = {f: [] for f in ch.FAMILIES}
        first = None
        for k in range(views):
            with torch.autocast(DEVICE, dtype=torch.bfloat16):
                emb, out = model(ch.dihedral(x, k).contiguous(memory_format=torch.channels_last))
            if first is None:
                first = emb.float()
            for f in ch.FAMILIES:
                per_view[f].append(out[f].float())
        for f in ch.FAMILIES:
            logits[f].append(torch.stack(per_view[f], dim=1).cpu().numpy())
        labels.append(y.numpy())
        embeddings.append(first.cpu().numpy())
    return {f: np.concatenate(v) for f, v in logits.items()}, np.concatenate(labels), np.concatenate(embeddings)


def exact_by_family(logits: dict[str, np.ndarray], labels: np.ndarray) -> dict[str, float]:
    out = {}
    for i, f in enumerate(ch.FAMILIES):
        mask = labels[:, i] >= 0
        pred = logits[f][mask].mean(axis=1).argmax(axis=-1)
        out[f] = round(float((pred == labels[mask, i]).mean()), 4)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backbone", required=True)
    parser.add_argument("--side", type=int, default=1024)
    parser.add_argument("--name", required=True)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--head-lr", type=float, default=2e-3)
    parser.add_argument("--smoothing", type=float, default=0.05)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0, help="smoke test: keep this many rows")
    parser.add_argument("--train-hold", action="store_true", help="also train on the hold fold (no calibration then)")
    args = parser.parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True

    rows = read_rows()
    if args.limit:
        rows = rows[: args.limit]
    train_rows = [r for r in rows if r["fold"] == "train" or args.train_hold]
    hold_rows = [r for r in rows if r["fold"] == "hold"]
    caps = fit_caps([r for r in rows if r["fold"] == "train"])
    print(f"train {len(train_rows)} hold {len(hold_rows)} caps {caps}", flush=True)

    model = (
        ch.CountNet(args.backbone, caps, side=args.side, pretrained=True)
        .to(DEVICE)
        .to(memory_format=torch.channels_last)
    )
    head_params = list(model.heads.parameters())
    optimizer = torch.optim.AdamW(
        [{"params": model.encoder.parameters(), "lr": args.lr}, {"params": head_params, "lr": args.head_lr}],
        weight_decay=0.05,
    )
    train_loader = DataLoader(
        Plans(train_rows, caps, args.side, train=True),
        batch_size=args.batch,
        shuffle=True,
        num_workers=args.workers,
        pin_memory=True,
        drop_last=True,
        persistent_workers=args.workers > 0,
    )
    hold_loader = DataLoader(
        Plans(hold_rows, caps, args.side, train=False), batch_size=args.batch, num_workers=args.workers
    )
    steps = args.epochs * len(train_loader)
    warmup = len(train_loader)
    bases = [g["lr"] for g in optimizer.param_groups]
    history = []
    step = 0
    started = time.time()
    for epoch in range(args.epochs):
        model.train()
        losses = []
        for x, y in train_loader:
            factor = (
                step / warmup if step < warmup else 0.5 * (1 + math.cos(math.pi * (step - warmup) / (steps - warmup)))
            )
            for group, base in zip(optimizer.param_groups, bases, strict=True):
                group["lr"] = base * factor
            x = x.to(DEVICE, non_blocking=True).contiguous(memory_format=torch.channels_last)
            y = y.to(DEVICE, non_blocking=True)
            with torch.autocast(DEVICE, dtype=torch.bfloat16):
                _, logits = model(x)
            loss = loss_of(logits, y, args.smoothing)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            losses.append(loss.item())
            step += 1
        record = {
            "epoch": epoch + 1,
            "loss": round(float(np.mean(losses)), 4),
            "minutes": round((time.time() - started) / 60, 1),
        }
        if (epoch + 1) % 5 == 0 or epoch + 1 == args.epochs:
            hold_logits, hold_labels, _ = evaluate(model, hold_loader, 1)
            exact = exact_by_family(hold_logits, hold_labels)
            record["hold_exact"] = exact
            record["hold_exact_mean"] = round(float(np.mean(list(exact.values()))), 4)
        history.append(record)
        print(json.dumps(record), flush=True)

    out = JOB / "out" / args.name
    out.mkdir(parents=True, exist_ok=True)
    hold_logits, hold_labels, hold_emb = evaluate(model, hold_loader, VIEWS)
    plain_loader = DataLoader(
        Plans(train_rows, caps, args.side, train=False), batch_size=args.batch, num_workers=args.workers
    )
    _, _, train_emb = evaluate(model, plain_loader, 1)
    mean = train_emb.mean(axis=0)
    centred = train_emb - mean
    cov = centred.T @ centred / len(centred)
    shrink = 0.1
    cov = (1 - shrink) * cov + shrink * np.trace(cov) / cov.shape[0] * np.eye(cov.shape[0])
    precision = np.linalg.inv(cov)
    hc = hold_emb - mean
    hold_dist = np.sqrt(np.einsum("bi,ij,bj->b", hc, precision, hc))
    ood_threshold = float(np.quantile(hold_dist, 0.995))
    np.savez_compressed(out / "ood.npz", mean=mean.astype(np.float32), precision=precision.astype(np.float32))
    np.savez_compressed(
        out / "hold.npz",
        labels=hold_labels,
        dist=hold_dist,
        images=np.asarray([r["image"] for r in hold_rows]),
        **{f"logits_{f}": v.astype(np.float32) for f, v in hold_logits.items()},
    )
    torch.save({k: v.half() for k, v in model.state_dict().items()}, out / "model.pt")
    meta = ch.ModelMeta(name=args.name, backbone=args.backbone, side=args.side, caps=caps, ood_threshold=ood_threshold)
    (out / "meta.json").write_text(meta.model_dump_json(indent=2))
    final = {
        "tta1": exact_by_family({f: v[:, :1] for f, v in hold_logits.items()}, hold_labels),
        "tta8": exact_by_family(hold_logits, hold_labels),
    }
    (out / "history.json").write_text(json.dumps({"args": vars(args), "history": history, "final": final}, indent=2))
    print(
        json.dumps({"done": args.name, "final": final, "minutes": round((time.time() - started) / 60, 1)}), flush=True
    )


if __name__ == "__main__":
    main()
