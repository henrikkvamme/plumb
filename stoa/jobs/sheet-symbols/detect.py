"""Tiled inference of the symbol detector on a whole sheet (no `bp` import, so it runs on a bare GPU VM)."""

from __future__ import annotations

from typing import Any

import numpy as np

TILE, STRIDE = 1024, 704
CLASSES = ("toilet", "urinal", "sink", "window")
SAME = 0.45  # boxes of one class that overlap this much (IoU) are one symbol, seen in two tiles


def iou(a: list[float], b: list[float]) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    inter = w * h
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def merge(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: -r["score"]):
        if all(row["class"] != o["class"] or iou(row["box"], o["box"]) < SAME for o in kept):
            kept.append(row)
    return kept


def detect(model: Any, gray: np.ndarray, conf: float = 0.05, batch: int = 32) -> list[dict[str, Any]]:  # noqa: ANN401
    """Every symbol of the sheet above `conf`: box (x0, y0, x1, y1 in sheet pixels), class and score."""
    height, width = gray.shape
    tiles, origins = [], []
    for y in range(0, max(height - TILE // 2, 1), STRIDE):
        for x in range(0, max(width - TILE // 2, 1), STRIDE):
            part = gray[y : y + TILE, x : x + TILE]
            if part.mean() > 254:
                continue
            tile = np.full((TILE, TILE), 255, np.uint8)
            tile[: part.shape[0], : part.shape[1]] = part
            tiles.append(np.stack([tile] * 3, axis=2))
            origins.append((x, y))
    rows = []
    for start in range(0, len(tiles), batch):
        results = model.predict(tiles[start : start + batch], imgsz=TILE, conf=conf, verbose=False)
        for (ox, oy), result in zip(origins[start : start + batch], results, strict=True):
            if result.boxes is None:
                continue
            for box, score, cls in zip(result.boxes.xyxy.tolist(), result.boxes.conf.tolist(),
                                       result.boxes.cls.tolist(), strict=True):  # fmt: skip
                x0, y0, x1, y1 = box
                cut = min(x0, y0) < 4 or max(x1, y1) > TILE - 4  # the next tile has it whole
                edge = (ox == 0 and x0 < 4) or (oy == 0 and y0 < 4) or ox + x1 > width - 4 or oy + y1 > height - 4
                if cut and not edge:
                    continue
                rows.append({"box": [round(x0 + ox, 1), round(y0 + oy, 1), round(x1 + ox, 1), round(y1 + oy, 1)],
                             "class": CLASSES[int(cls)], "score": round(score, 4)})  # fmt: skip
    return merge(rows)
