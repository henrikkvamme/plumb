"""Train the room U-Net on the Swiss sheets made by prepare.py (dev partition only).

Four sigmoid channels: room interior (soft coverage of the DXF room polygons), wall, room boundary, opening.
Strong augmentation so the model does not learn one render style: scale 0.7 to 1.4, rotation by 90 degrees,
flips, line weight (erode or dilate the ink), blur, JPEG, noise, grey and colour shifts.

Run on the GPU VM: python train.py --minutes 15 --encoder resnet34
Writes out/model.pt, out/log.jsonl and out/metrics.json.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import cv2
import numpy as np
import segmentation_models_pytorch as smp
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = HERE / "out"
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
CHANNEL_WEIGHT = torch.tensor([1.0, 0.5, 1.0, 0.5])

cv2.setNumThreads(1)


def load(stem: str) -> tuple[np.ndarray, np.ndarray]:
    image = cv2.cvtColor(cv2.imread(str(DATA / f"{stem}.img.png"), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    mask = cv2.imread(str(DATA / f"{stem}.mask.png"), cv2.IMREAD_UNCHANGED)  # BGRA
    mask = mask[..., [2, 1, 0, 3]]  # back to interior, wall, boundary, opening
    return image, mask


def photometric(img: np.ndarray, rng: random.Random) -> np.ndarray:
    out = img
    if rng.random() < 0.25:  # thicker ink
        k = rng.choice([2, 3])
        out = cv2.erode(out, np.ones((k, k), np.uint8))
    elif rng.random() < 0.15:  # thinner ink
        out = cv2.dilate(out, np.ones((2, 2), np.uint8))
    if rng.random() < 0.3:
        grey = cv2.cvtColor(out, cv2.COLOR_RGB2GRAY)
        out = np.repeat(grey[..., None], 3, axis=2)
    if rng.random() < 0.2:
        out = out[..., rng.sample([0, 1, 2], 3)].copy()
    if rng.random() < 0.4:
        out = cv2.GaussianBlur(out, (0, 0), rng.uniform(0.3, 1.3))
    f = out.astype(np.float32)
    if rng.random() < 0.5:  # contrast and brightness; paper tone
        f = f * rng.uniform(0.75, 1.1) + rng.uniform(-25, 15)
    if rng.random() < 0.3:
        f += np.random.default_rng(rng.randrange(1 << 30)).normal(0, rng.uniform(2, 10), f.shape).astype(np.float32)
    out = np.clip(f, 0, 255).astype(np.uint8)
    if rng.random() < 0.4:
        q = rng.randint(30, 95)
        ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, q])
        if ok:
            out = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    return out


class Crops(Dataset):
    def __init__(self, stems: list[str], crop: int, per_epoch: int, augment: bool, seed: int = 0) -> None:
        self.stems, self.crop, self.per_epoch, self.augment, self.seed = stems, crop, per_epoch, augment, seed

    def __len__(self) -> int:
        return self.per_epoch

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        rng = random.Random(index * 7919 + self.seed if not self.augment else None)
        stem = self.stems[rng.randrange(len(self.stems))]
        img, mask = load(stem)
        h, w = img.shape[:2]
        scale = math.exp(rng.uniform(math.log(0.7), math.log(1.4))) if self.augment else 1.0
        side = min(round(self.crop / scale), h, w)
        if rng.random() < 0.85:  # centre on a room most of the time
            ys, xs = np.nonzero(mask[::16, ::16, 0] > 128)
            if len(ys):
                i = rng.randrange(len(ys))
                cy, cx = ys[i] * 16, xs[i] * 16
            else:
                cy, cx = h // 2, w // 2
        else:
            cy, cx = rng.randrange(h), rng.randrange(w)
        y0 = min(max(0, cy - side // 2), h - side)
        x0 = min(max(0, cx - side // 2), w - side)
        img = img[y0 : y0 + side, x0 : x0 + side]
        mask = mask[y0 : y0 + side, x0 : x0 + side]
        if side != self.crop:
            interp = cv2.INTER_AREA if side > self.crop else cv2.INTER_LINEAR
            img = cv2.resize(img, (self.crop, self.crop), interpolation=interp)
            mask = cv2.resize(mask, (self.crop, self.crop), interpolation=cv2.INTER_LINEAR)
        if self.augment:
            k = rng.randrange(4)
            img, mask = np.rot90(img, k), np.rot90(mask, k)
            if rng.random() < 0.5:
                img, mask = img[:, ::-1], mask[:, ::-1]
            img = photometric(np.ascontiguousarray(img), rng)
        x = (img.astype(np.float32) / 255.0 - MEAN) / STD
        return torch.from_numpy(np.ascontiguousarray(x.transpose(2, 0, 1))), torch.from_numpy(
            np.ascontiguousarray(mask.transpose(2, 0, 1)).astype(np.float32) / 255.0
        )


def loss_fn(logits: torch.Tensor, target: torch.Tensor) -> tuple[torch.Tensor, dict[str, float]]:
    weight = CHANNEL_WEIGHT.to(logits.device).view(1, -1, 1, 1)
    bce = (F.binary_cross_entropy_with_logits(logits, target, reduction="none") * weight).mean()
    prob = torch.sigmoid(logits)
    dims = (2, 3)
    inter = (prob * target).sum(dims)
    dice = 1 - (2 * inter + 1) / (prob.sum(dims) + target.sum(dims) + 1)
    dice = dice[:, [0, 2]].mean()
    # soft area of the interior per crop: the tool measures areas as sums of the probability
    area_t = target[:, 0].sum(dims[0:1]).sum(1)
    area_p = prob[:, 0].sum(dims[0:1]).sum(1)
    area = ((area_p - area_t).abs() / (area_t + 2000.0)).mean()
    total = bce + 0.5 * dice + 0.2 * area
    return total, {"bce": float(bce.detach()), "dice": float(dice.detach()), "area": float(area.detach())}


@torch.no_grad()
def evaluate(model: torch.nn.Module, loader: DataLoader, device: str) -> dict[str, float]:
    model.eval()
    sums: dict[str, float] = {}
    n = 0
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=device == "cuda"):
            logits = model(x)
        _, parts = loss_fn(logits.float(), y)
        prob = torch.sigmoid(logits.float())
        hard = (prob > 0.5).float()
        for c, name in enumerate(["interior", "wall", "boundary", "opening"]):
            inter = (hard[:, c] * (y[:, c] > 0.5)).sum()
            union = ((hard[:, c] + (y[:, c] > 0.5).float()) > 0).sum()
            parts[f"iou_{name}"] = float(inter / union.clamp(min=1))
        for k, v in parts.items():
            sums[k] = sums.get(k, 0.0) + v
        n += 1
    model.train()
    return {k: round(v / max(1, n), 5) for k, v in sums.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=15)
    ap.add_argument("--encoder", default="resnet34")
    ap.add_argument("--crop", type=int, default=768)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=5e-4)
    ap.add_argument("--workers", type=int, default=18)
    ap.add_argument("--eval-every", type=int, default=400)
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    index = [r for r in json.loads((DATA / "index.json").read_text()) if "error" not in r]
    stems = sorted(r["stem"] for r in index)
    held = stems[::20]
    train = [s for s in stems if s not in set(held)]
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device {device}, {len(train)} train sheets, {len(held)} held-out sheets", flush=True)
    model = smp.Unet(args.encoder, encoder_weights="imagenet", in_channels=3, classes=4).to(device)
    model = model.to(memory_format=torch.channels_last)
    enc = [p for n, p in model.named_parameters() if n.startswith("encoder.")]
    dec = [p for n, p in model.named_parameters() if not n.startswith("encoder.")]
    opt = torch.optim.AdamW([{"params": enc, "lr": args.lr / 3}, {"params": dec, "lr": args.lr}], weight_decay=1e-4)
    loader = DataLoader(Crops(train, args.crop, 10**7, augment=True), batch_size=args.batch, num_workers=args.workers,
                        pin_memory=True, persistent_workers=True, prefetch_factor=4)
    held_loader = DataLoader(Crops(held, 1024, 96, augment=False, seed=1), batch_size=8, num_workers=8)
    budget = args.minutes * 60
    start = time.time()
    step, best = 0, float("inf")
    log = (OUT / "log.jsonl").open("w")
    warm = 300
    for x, y in loader:
        elapsed = time.time() - start
        if elapsed > budget:
            break
        frac = min(1.0, elapsed / budget)
        scale = min(1.0, (step + 1) / warm) * (0.02 + 0.98 * 0.5 * (1 + math.cos(math.pi * frac)))
        for g, base in zip(opt.param_groups, (args.lr / 3, args.lr), strict=True):
            g["lr"] = base * scale
        x = x.to(device, non_blocking=True).to(memory_format=torch.channels_last)
        y = y.to(device, non_blocking=True)
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=device == "cuda"):
            logits = model(x)
        loss, parts = loss_fn(logits.float(), y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        step += 1
        if step % 50 == 0:
            print(f"step {step} t {elapsed:.0f}s loss {float(loss):.4f} {parts} lr {opt.param_groups[1]['lr']:.2e} "
                  f"img/s {step * args.batch / elapsed:.1f}", flush=True)
        if step % args.eval_every == 0:
            metrics = evaluate(model, held_loader, device)
            score = metrics["bce"] + 0.5 * metrics["dice"] + 0.2 * metrics["area"]
            row = {"step": step, "t": round(elapsed), **metrics, "score": round(score, 5)}
            log.write(json.dumps(row) + "\n")
            log.flush()
            print("eval", row, flush=True)
            if score < best:
                best = score
                torch.save({"state_dict": {k: v.half() for k, v in model.state_dict().items()},
                            "encoder": args.encoder, "classes": 4, "canon_ppm": 150 / 0.0254 / 100,
                            "step": step, "metrics": row}, OUT / "model.pt")
    metrics = evaluate(model, held_loader, device)
    score = metrics["bce"] + 0.5 * metrics["dice"] + 0.2 * metrics["area"]
    if score < best:
        torch.save({"state_dict": {k: v.half() for k, v in model.state_dict().items()}, "encoder": args.encoder,
                    "classes": 4, "canon_ppm": 150 / 0.0254 / 100, "step": step, "metrics": metrics}, OUT / "model.pt")
    final = {"steps": step, "minutes": round((time.time() - start) / 60, 2), "final": metrics, "best_score": min(best, score),
             "args": vars(args)}
    (OUT / "metrics.json").write_text(json.dumps(final, indent=1))
    print("done", final, flush=True)


if __name__ == "__main__":
    main()
