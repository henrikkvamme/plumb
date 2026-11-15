"""Read printed text lines on a raster image, with a box and a score for each line.

It wraps RapidOCR (PP-OCRv6 on onnxruntime, installed with the package). The detector shrinks any image whose long
side is above `Global.max_side_len`, and small room labels (5 to 8 px high on a 150 dpi sheet) then vanish. So the
image is upscaled and cut into overlapping tiles, each tile is read at its own size, and lines that two tiles both
read are merged. Boxes are in the pixel space of the input image.

The models are the small PP-OCRv6 pair that ships inside the `rapidocr` wheel, or the medium pair when its files
are in `artifacts/raster-rooms/ocr/` (no network at run time).
"""

from __future__ import annotations

import contextlib
import io
import logging
import os
import re
from functools import cache
from typing import TYPE_CHECKING, Any

import numpy as np
from PIL import Image

from bp.contract import Frozen
from bp.paths import ARTIFACTS

if TYPE_CHECKING:
    from pathlib import Path

OCR_DIR = ARTIFACTS / "raster-rooms" / "ocr"
UPSCALE = 2.0
TILE = 1280  # tile side in upscaled pixels
OVERLAP = 192  # a line shorter than this is whole in at least one tile
MIN_SCORE = 0.5
SAME_LINE_IOU = 0.3


class TextLine(Frozen):
    """One line of text. `box` holds 4 corners (x, y) in input pixels, clockwise from the top left."""

    text: str
    box: tuple[tuple[float, float], ...]
    score: float

    @property
    def cx(self) -> float:
        return sum(p[0] for p in self.box) / len(self.box)

    @property
    def cy(self) -> float:
        return sum(p[1] for p in self.box) / len(self.box)

    @property
    def height(self) -> float:
        ys = [p[1] for p in self.box]
        return max(ys) - min(ys)

    @property
    def width(self) -> float:
        xs = [p[0] for p in self.box]
        return max(xs) - min(xs)

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        xs = [p[0] for p in self.box]
        ys = [p[1] for p in self.box]
        return (min(xs), min(ys), max(xs), max(ys))


@cache
def _engine() -> Any:  # noqa: ANN401 - RapidOCR has no public type
    from rapidocr import RapidOCR  # noqa: PLC0415 - heavy import, only when OCR runs

    params: dict[str, Any] = {"Global.log_level": "critical", "Global.max_side_len": 4000}
    threads = int(os.environ.get("BP_OCR_THREADS", "0"))
    if threads > 0:  # several OCR processes side by side: give each a few threads
        params["EngineConfig.onnxruntime.intra_op_num_threads"] = threads
    det, rec = OCR_DIR / "PP-OCRv6_det_medium.onnx", OCR_DIR / "PP-OCRv6_rec_medium.onnx"
    if det.exists() and rec.exists():
        params |= {"Det.model_path": str(det), "Rec.model_path": str(rec)}
    with contextlib.redirect_stdout(io.StringIO()):
        engine = RapidOCR(params=params)
    for name in ("RapidOCR", "rapidocr"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    return engine


def _run(image: np.ndarray) -> list[tuple[np.ndarray, str, float]]:
    with contextlib.redirect_stdout(io.StringIO()):
        result = _engine()(image)
    if result is None or result.boxes is None or result.txts is None:
        return []
    return [
        (np.asarray(b, dtype=float), str(t), float(s))
        for b, t, s in zip(result.boxes, result.txts, result.scores, strict=True)
    ]


def _tiles(width: int, height: int, tile: int = TILE, overlap: int = OVERLAP) -> list[tuple[int, int]]:
    def starts(size: int) -> list[int]:
        if size <= tile:
            return [0]
        step = tile - overlap
        out = list(range(0, size - tile, step))
        out.append(size - tile)
        return out

    return [(x, y) for y in starts(height) for x in starts(width)]


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _inside(inner: tuple[float, float, float, float], outer: tuple[float, float, float, float]) -> float:
    """The share of `inner` that lies in `outer`."""
    ix = max(0.0, min(inner[2], outer[2]) - max(inner[0], outer[0]))
    iy = max(0.0, min(inner[3], outer[3]) - max(inner[1], outer[1]))
    area = (inner[2] - inner[0]) * (inner[3] - inner[1])
    return ix * iy / area if area > 0 else 0.0


def merge_lines(lines: list[TextLine]) -> list[TextLine]:
    """Keep one line where tiles overlap: the longer text wins, then the higher score."""
    order = sorted(lines, key=lambda line: (-len(line.text), -line.score))
    kept: list[TextLine] = []
    for line in order:
        box = line.bbox
        if any(_iou(box, k.bbox) > SAME_LINE_IOU or _inside(box, k.bbox) > 0.8 for k in kept):
            continue
        kept.append(line)
    return sorted(kept, key=lambda line: (round(line.cy), line.cx))


def to_rgb(image: np.ndarray | Image.Image | str | Path) -> np.ndarray:
    """An RGB uint8 array. Transparent pixels become white."""
    if not isinstance(image, np.ndarray):
        pil = image if isinstance(image, Image.Image) else Image.open(image)
        if pil.mode in {"RGBA", "LA", "P"}:
            pil = pil.convert("RGBA")
            white = Image.new("RGBA", pil.size, (255, 255, 255, 255))
            pil = Image.alpha_composite(white, pil)
        return np.asarray(pil.convert("RGB"))
    if image.ndim == 2:
        return np.repeat(image[:, :, None], 3, axis=2)
    return image[:, :, :3]


def read_lines(
    image: np.ndarray | Image.Image | str | Path,
    *,
    upscale: float = UPSCALE,
    min_score: float = MIN_SCORE,
    tile: int = TILE,
    overlap: int = OVERLAP,
) -> list[TextLine]:
    """Every text line on the image, read on scaled overlapping tiles. `tile` and `overlap` are in scaled pixels."""
    rgb = to_rgb(image)
    height, width = rgb.shape[:2]
    if upscale != 1.0:
        size = (round(width * upscale), round(height * upscale))
        big = np.asarray(Image.fromarray(rgb).resize(size, Image.Resampling.BICUBIC))
    else:
        big = rgb
    found: list[TextLine] = []
    for x0, y0 in _tiles(big.shape[1], big.shape[0], tile, overlap):
        part = big[y0 : y0 + tile, x0 : x0 + tile]
        if part.min() > 245:
            continue
        for box, text, score in _run(np.ascontiguousarray(part)):
            clean = text.strip()
            if score < min_score or not clean:
                continue
            pts = tuple((float((px + x0) / upscale), float((py + y0) / upscale)) for px, py in box)
            found.append(TextLine(text=clean, box=pts, score=round(score, 4)))
    return merge_lines(found)


# ----------------------------------------------------------------------------- text normalisers

_NUMBER_FIX = str.maketrans({",": ".", "O": "0", "o": "0", "/": ".", "$": "5", "T": "7", "l": "1", "I": "1", "|": "1"})
_EDGE = " :;[](){}-_'\"`"  # OCR glues a wall stroke or a colon to the number: "[2.08", ":2.14", "4.08-"
ROOM_NUMBER = re.compile(r"^(U\d+\.)?\d+\.\d+$|^U\d+\.\d+$")
AREA_TEXT = re.compile(r"^(\d+(?:[.,]\d+)?)\s*m\s*(?:²|2|\?|a)?$")


def room_number(text: str) -> str | None:
    """The room number that a line reads, with OCR slips mended ("2,18" -> "2.18", "[2.08" -> "2.08", "2/31" -> "2.31")."""
    raw = text.strip().strip(_EDGE).replace(" ", "")
    # a unit prefix keeps its letter
    candidate = "U" + raw[1:].translate(_NUMBER_FIX) if raw.startswith("U") else raw.translate(_NUMBER_FIX)
    return candidate if ROOM_NUMBER.match(candidate) else None


def area_value(text: str) -> float | None:
    """The value of a printed area ("15.61 m²", "7.59 m2"), or None."""
    match = AREA_TEXT.match(text.strip())
    return float(match.group(1).replace(",", ".")) if match else None
