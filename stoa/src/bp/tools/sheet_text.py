"""Text on a large drawing sheet: labels, tags, printed scales and lengths.

A sheet is a raster of a full construction drawing (10,000 px and more on the long side), with a title block,
notes, a legend and one or more drawings. The functions here work on OCR lines only. They know nothing about the
kind of building or the discipline, so the same functions read an architectural plan, a slab plan and a piping plan.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import TYPE_CHECKING

import numpy as np

from bp.contract import Frozen
from bp.paths import EXPERIMENTS
from bp.tools import ocr

if TYPE_CHECKING:
    from pathlib import Path

    from bp.tools.ocr import TextLine

OCR_CACHE = EXPERIMENTS / "cache" / "sheet-ocr"
# px. A full sheet at print resolution is 9,900 px and more. The largest small plan in Stoa's set is 7,328 px.
SHEET_MIN_SIDE = 8000
# Letters on a 300 dpi sheet are 12 to 40 px high, so the image needs no upscale. Tiles of 960 px read more than
# larger ones: on a UK school plan 133 of 135 word instances, against 127 with 1280 px tiles.
OCR_SCALE = 0.75
OCR_TILE = 960
OCR_OVERLAP = 320
NEAR_HEIGHTS = 8.0  # a text is near a label when the gap between their boxes is below this many label heights
SQFT_M2 = 0.09290304


class Label(Frozen):
    """One label: a text line, or lines stacked on each other with the same centre ("MECHANICAL" above "ROOM")."""

    text: str
    bbox: tuple[float, float, float, float]
    height: float  # of one line

    @property
    def at(self) -> tuple[int, int]:
        return (round((self.bbox[0] + self.bbox[2]) / 2), round((self.bbox[1] + self.bbox[3]) / 2))


class PrintedScale(Frozen):
    text: str  # as printed: "1:200", "1/4\" = 1'-0\""
    ratio: int  # the N of 1:N
    count: int
    at: tuple[int, int]


def is_sheet(rgb: np.ndarray) -> bool:
    return max(rgb.shape[:2]) >= SHEET_MIN_SIDE


def pixel_key(rgb: np.ndarray) -> str:
    """A name for these pixels: the same image has the same key on each machine."""
    return hashlib.sha256(np.ascontiguousarray(rgb).data).hexdigest()[:32]


def _cache_path(rgb: np.ndarray) -> Path:
    return OCR_CACHE / f"{pixel_key(rgb)}-{OCR_SCALE}-{OCR_TILE}-{OCR_OVERLAP}.json"


def cached_lines(rgb: np.ndarray) -> list[TextLine] | None:
    """The text lines when this sheet was read before, or None. It never starts OCR."""
    path = _cache_path(rgb)
    return [ocr.TextLine(**row) for row in json.loads(path.read_text())] if path.exists() else None


def read_lines(rgb: np.ndarray) -> list[TextLine]:
    """Read the text lines of a sheet, from the disk cache when the same pixels were read before.

    OCR of one sheet takes 30 s to several minutes, and each run and each question reads the same sheets.
    """
    path = _cache_path(rgb)
    if path.exists():
        return [ocr.TextLine(**row) for row in json.loads(path.read_text())]
    lines = ocr.read_lines(rgb, upscale=OCR_SCALE, tile=OCR_TILE, overlap=OCR_OVERLAP)
    OCR_CACHE.mkdir(parents=True, exist_ok=True)
    scratch = path.with_suffix(f".{os.getpid()}.tmp")
    scratch.write_text(json.dumps([line.model_dump() for line in lines]))
    scratch.replace(path)
    return lines


def _horizontal(line: TextLine) -> bool:
    return line.width >= line.height or len(line.text) <= 2


def labels(lines: list[TextLine]) -> list[Label]:
    """Join stacked centred lines of the same height to one label. Every other line is its own label."""
    rows = sorted((ln for ln in lines if _horizontal(ln)), key=lambda ln: (ln.bbox[1], ln.bbox[0]))
    used = [False] * len(rows)
    out: list[Label] = [
        Label(text=ln.text, bbox=ln.bbox, height=ln.width) for ln in lines if not _horizontal(ln)
    ]  # vertical text: its line height is the box width
    for i, first in enumerate(rows):
        if used[i]:
            continue
        used[i] = True
        parts, box, height = [first.text], list(first.bbox), first.height
        grew = True
        while grew:
            grew = False
            for j, other in enumerate(rows):
                if used[j] or abs(other.height - height) > 0.4 * height:
                    continue
                gap = other.bbox[1] - box[3]
                same_centre = abs(other.cx - (box[0] + box[2]) / 2) < 0.8 * height
                if same_centre and -0.3 * height < gap < 0.6 * height and _is_name(other.text) and _is_name(parts[-1]):
                    used[j], grew = True, True
                    parts.append(other.text)
                    box = [min(box[0], other.bbox[0]), box[1], max(box[2], other.bbox[2]), other.bbox[3]]
                    break
        out.append(Label(text=" ".join(parts), bbox=(box[0], box[1], box[2], box[3]), height=height))
    return out


def _is_name(text: str) -> bool:
    """Words, not a number or a quantity: only words join to one label."""
    return bool(re.fullmatch(r"[A-Za-z(][A-Za-z'&/().,\- ]*", text.strip()))


def norm(text: str) -> str:
    """Lower case, one space between words, none around a slash or a hyphen ("OFFICE/ CLOSET" is "office/closet")."""
    words = " ".join(re.sub(r"[^a-z0-9./'\"-]+", " ", text.lower()).split())
    return re.sub(r"\s?([/-])\s?", r"\1", words)


def find(all_labels: list[Label], query: str, mode: str) -> list[Label]:
    """Labels that match. `exact`: the whole label is the query. `contains`: the query is in it. `regex`: a pattern."""
    if mode == "regex":
        pattern = re.compile(query, re.IGNORECASE)
        return [lb for lb in all_labels if pattern.search(lb.text)]
    wanted = norm(query)
    if not wanted:
        return []
    if mode == "exact":
        return [lb for lb in all_labels if norm(lb.text) == wanted]
    return [lb for lb in all_labels if wanted in norm(lb.text)]


def _gap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    dx = max(0.0, max(a[0], b[0]) - min(a[2], b[2]))
    dy = max(0.0, max(a[1], b[1]) - min(a[3], b[3]))
    return (dx * dx + dy * dy) ** 0.5


def near(all_labels: list[Label], label: Label, limit: int = 8) -> list[Label]:
    """The labels closest to one label, nearest first: a printed area, a room number, a tag under a name."""
    reach = NEAR_HEIGHTS * label.height
    close = [(g, lb) for lb in all_labels if lb is not label and (g := _gap(label.bbox, lb.bbox)) <= reach]
    return [lb for _, lb in sorted(close, key=lambda t: t[0])[:limit]]


def side(label: Label, other: Label) -> tuple[str, float]:
    """Where `other` lies from `label` (above, below, left, right) and the gap between them in label heights."""
    a, b = label.bbox, other.bbox
    dx = max(0.0, max(a[0], b[0]) - min(a[2], b[2]))
    dy = max(0.0, max(a[1], b[1]) - min(a[3], b[3]))
    if dy >= dx:
        where = "above" if other.at[1] < label.at[1] else "below"
    else:
        where = "left" if other.at[0] < label.at[0] else "right"
    return where, round(_gap(a, b) / label.height, 1)


def in_region(all_labels: list[Label], box: tuple[float, float, float, float]) -> list[Label]:
    """Labels with the centre in the box, in reading order (rows from the top, then left to right)."""
    inside = [lb for lb in all_labels if box[0] <= lb.at[0] <= box[2] and box[1] <= lb.at[1] <= box[3]]
    inside.sort(key=lambda lb: lb.at[1])
    rows: list[list[Label]] = []
    for lb in inside:
        if rows and abs(lb.at[1] - rows[-1][0].at[1]) < 0.6 * max(lb.height, rows[-1][0].height):
            rows[-1].append(lb)
        else:
            rows.append([lb])
    return [lb for row in rows for lb in sorted(row, key=lambda v: v.at[0])]


TAG = re.compile(r"(?<![A-Za-z0-9])([A-Z]{1,5})\s?-\s?(\d{1,4}[A-Z]?)(?![A-Za-z0-9])")


def tags(lines: list[TextLine], prefix: str) -> dict[str, list[tuple[int, int]]]:
    """Each different tag with this prefix ("PS" finds PS-1, PS-2A) and where it is printed."""
    wanted = prefix.strip().rstrip("-").upper()
    found: dict[str, list[tuple[int, int]]] = {}
    for line in lines:
        for m in TAG.finditer(line.text):
            if m.group(1) == wanted:
                found.setdefault(f"{wanted}-{m.group(2)}", []).append((round(line.cx), round(line.cy)))
    return found


# ----------------------------------------------------------------------------- scales and lengths

_QUOTES = {0x201D: '"', 0x201C: '"', 0x2033: '"', 0x2019: "'", 0x2018: "'", 0x2032: "'", ord("`"): "'"}
METRIC_SCALE = re.compile(r"(?<![\d.,])(?<!\d:)(?<!\d: )1\s?:\s?(\d{1,4})(?![\d.,]|\s?:\s?\d)")
# 1/4" = 1'-0"   1" = 40'-0"   3/32"=1'-0"   1 1/2" = 1'-0"
IMPERIAL_SCALE = re.compile(
    r"(?<![\d/])(\d+\s+\d+/\d+|\d+/\d+|\d+)\s?\"\s?=\s?(\d+)\s?'\s?-?\s?(\d+)?\s?\"?",
)
FEET_INCHES = re.compile(r"^(\d+)\s?'\s?-?\s?(?:(\d+)(?:\s+(\d+)/(\d+))?|(\d+)/(\d+))?\s?\"?$")


def clean(text: str) -> str:
    return text.translate(_QUOTES).replace("''", '"')


def _fraction(text: str) -> float:
    total = 0.0
    for part in text.split():
        if "/" in part:
            top, bottom = part.split("/")
            total += float(top) / float(bottom)
        else:
            total += float(part)
    return total


def printed_scales(lines: list[TextLine]) -> list[PrintedScale]:
    """Every scale notation on the sheet, as 1:N. The most frequent is first."""
    found: dict[int, list[tuple[str, tuple[int, int]]]] = {}
    for line in lines:
        text = clean(line.text)
        at = (round(line.cx), round(line.cy))
        for m in IMPERIAL_SCALE.finditer(text):
            paper_in = _fraction(m.group(1))
            real_in = 12 * int(m.group(2)) + int(m.group(3) or 0)
            if paper_in > 0 and real_in > 0:
                found.setdefault(round(real_in / paper_in), []).append((m.group(0).strip(), at))
        for m in METRIC_SCALE.finditer(text):
            if int(m.group(1)) >= 5:
                found.setdefault(int(m.group(1)), []).append((f"1:{m.group(1)}", at))
    out = [PrintedScale(text=hits[0][0], ratio=ratio, count=len(hits), at=hits[0][1]) for ratio, hits in found.items()]
    return sorted(out, key=lambda s: (-s.count, s.ratio))


def feet_inches_m(text: str) -> float | None:
    """A length in feet and inches, in metres: 12 ft 6 in, 8 ft 10 1/2 in or 6 ft, written with ' and "."""
    m = FEET_INCHES.match(clean(text).strip())
    if not m:
        return None
    inches = float(m.group(2) or 0)
    if m.group(3):
        inches += float(m.group(3)) / float(m.group(4))
    if m.group(5):
        inches += float(m.group(5)) / float(m.group(6))
    return (12 * int(m.group(1)) + inches) * 0.0254
