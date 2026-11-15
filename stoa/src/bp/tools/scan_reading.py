"""Read a historic scan: an old drawing on a small or damaged raster (HABS, Finna, Europeana, Wikimedia).

A scan is not a modern flat plan. The room model and the symbol detector of the small raster tools are trained on
CubiCasa and Swiss plans, and on a scan they give noise. This module reads only what a scan holds for sure:

- the printed text (OCR with large overlapping tiles, so a long title line is read whole), joined to phrases;
- the title block and the captions: title, years and dates, people (architect, drawn by), sheet number, printed
  scale, kind of drawing;
- the scale: a scale bar (tick labels in a row, refined on the tick marks of the bar), and the dimension lines of
  the drawing (`bp.tools.sheet_geometry`). A printed ratio such as 1:500 alone gives no pixels per metre: the print
  size of a scan is not known;
- the extent of each drawing on the page (the connected line work), to measure an overall length.

`is_scan` is the route rule. Everything here is deterministic and runs without a model call.
"""

from __future__ import annotations

import itertools
import json
import math
import os
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import cv2
import numpy as np

from bp.contract import Frozen
from bp.paths import EXPERIMENTS
from bp.tools import ocr, sheet_geometry, sheet_text
from bp.tools.ocr import TextLine
from bp.tools.sheet_text import Label  # a field type of TitleText: pydantic needs it at run time

if TYPE_CHECKING:
    from pathlib import Path

    from bp.contract import Calibration
    from bp.tools import count_head

SCAN_OCR = EXPERIMENTS / "cache" / "scan-ocr"
# OCR of a scan. A large image is read at 1.5 times its size in tiles of 2400 px that overlap by 900 px: a long title
# line is whole in one tile, and it takes about 4 s on a 3000 px scan. A small image is read at 2 times its size in
# tiles of 1280 px (small digits vanish on larger tiles), with a wide overlap.
LARGE_SIDE = 2000
LARGE_OCR = (1.5, 2400, 900)
SMALL_OCR = (2.0, 1280, 640)

# Route rule. Measured on 40 historic scans, 6 Swiss PNG plans, 400 CubiCasa val plans and 20 synthetic style plans
# (15 November 2026): every historic scan was outside the count model's distribution with a style margin of +0.02 or
# less; 397 of 400 CubiCasa plans were inside it and the 3 others had a style margin of +4.5 or more; Swiss PNG plans
# had 19 to 46 room numbers that OCR read; historic scans 3 or fewer (dimension figures such as "2.71" on a HABS sheet
# look like room numbers). 5 keeps a margin on both sides.
STYLE_CUT = 1.0
FLAT_PLAN_NUMBERS = 5  # room numbers such as "2.18" or printed areas "15.6 m2": this many make a modern flat plan

# ----------------------------------------------------------------------------- OCR and phrases


def _ocr_params(rgb: np.ndarray) -> tuple[float, int, int]:
    return LARGE_OCR if max(rgb.shape[:2]) >= LARGE_SIDE else SMALL_OCR


def _cache_path(rgb: np.ndarray) -> Path:
    up, tile, overlap = _ocr_params(rgb)
    return SCAN_OCR / f"{sheet_text.pixel_key(rgb)}-{up}-{tile}-{overlap}-r.json"


ROTATED_MIN_CHARS = 4
ROTATED_MIN_SCORE = 0.7


def _rotated_lines(rgb: np.ndarray, up: float, tile: int, overlap: int, flat: list[TextLine]) -> list[TextLine]:
    """Text that reads from the bottom up (a title block along the right edge, a vertical dimension), as tall boxes.

    The image is turned a quarter to the right, read, and the boxes are turned back. A rotated read that lies on a
    line of the upright read is a misread of that line and is dropped.
    """
    height = rgb.shape[0]
    turned = np.ascontiguousarray(np.rot90(rgb, k=-1))
    out: list[TextLine] = []
    for line in ocr.read_lines(turned, upscale=up, tile=tile, overlap=overlap):
        if len(re.findall(r"\w", line.text)) < ROTATED_MIN_CHARS or line.score < ROTATED_MIN_SCORE:
            continue
        # turned (u, v) is original (x, y) = (v, height - 1 - u)
        box = tuple((float(v), float(height - 1 - u)) for u, v in line.box)
        back = TextLine(text=line.text, box=box, score=line.score)
        if back.height < back.width:
            continue
        if any(ocr._inside(back.bbox, f.bbox) > 0.3 for f in flat):  # noqa: SLF001 - the same overlap rule as OCR
            continue
        out.append(back)
    return out


def read_lines(rgb: np.ndarray) -> list[TextLine]:
    """The OCR lines of a scan, from the disk cache when the same pixels were read before.

    A large scan is also read turned a quarter: many title blocks run up the right edge of the sheet.
    """
    path = _cache_path(rgb)
    if path.exists():
        return [TextLine(**row) for row in json.loads(path.read_text())]
    up, tile, overlap = _ocr_params(rgb)
    lines = ocr.read_lines(rgb, upscale=up, tile=tile, overlap=overlap)
    if max(rgb.shape[:2]) >= LARGE_SIDE:
        lines = lines + _rotated_lines(rgb, up, tile, overlap, lines)
    SCAN_OCR.mkdir(parents=True, exist_ok=True)
    scratch = path.with_suffix(f".{os.getpid()}.tmp")
    scratch.write_text(json.dumps([line.model_dump() for line in lines]))
    scratch.replace(path)
    return lines


PHRASE_GAP = 1.6  # words on one row join to a phrase when the gap is below this many text heights


def _join_text(a: str, b: str) -> str:
    """Two texts side by side; when tiles cut one line, the second can repeat the end of the first."""
    low_a, low_b = a.lower(), b.lower()
    if low_b in low_a:
        return a
    if low_a in low_b:
        return b
    for k in range(min(len(a), len(b)) - 1, 1, -1):
        if low_a.endswith(low_b[:k]):
            return a + b[k:]
    return f"{a} {b}"


def phrases(lines: list[TextLine]) -> list[TextLine]:
    """Join the words of one row to phrases: "BED" "ROOM" is "BED ROOM", "SECOND" "FLOOR" "PLAN" is one caption.

    Old drawings space their letters and words widely, and OCR reads many words as their own lines. Words join when
    they have about the same height, overlap in height by half, and the gap between them is below 1.6 text heights.
    Vertical text stays as it is.
    """
    flat = sorted((ln for ln in lines if ln.width >= ln.height or len(ln.text) <= 2), key=lambda ln: ln.bbox[0])
    out = [ln for ln in lines if not (ln.width >= ln.height or len(ln.text) <= 2)]
    used = [False] * len(flat)
    for i, first in enumerate(flat):
        if used[i]:
            continue
        used[i] = True
        text, box, score = first.text, list(first.bbox), first.score
        grew = True
        while grew:
            grew = False
            height = box[3] - box[1]
            for j, other in enumerate(flat):
                if used[j]:
                    continue
                ob = other.bbox
                oh = ob[3] - ob[1]
                if not (0.6 < oh / max(height, 1.0) < 1.6):
                    continue
                overlap = min(box[3], ob[3]) - max(box[1], ob[1])
                gap = ob[0] - box[2]
                if overlap < 0.5 * min(height, oh) or not (-0.5 * (ob[2] - ob[0]) < gap < PHRASE_GAP * height):
                    continue
                if _is_number(text) != _is_number(other.text):
                    continue  # a dimension figure next to a room name stays apart
                used[j], grew = True, True
                text = _join_text(text, other.text)
                box = [min(box[0], ob[0]), min(box[1], ob[1]), max(box[2], ob[2]), max(box[3], ob[3])]
                score = min(score, other.score)
                break
        corners = ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3]))
        out.append(TextLine(text=text, box=corners, score=score))
    return sorted(out, key=lambda ln: (round(ln.cy), ln.cx))


def _is_number(text: str) -> bool:
    return bool(re.fullmatch(r"[\d\s.,'\"/+\-:x\u00d7°]+", text.strip()))


# ----------------------------------------------------------------------------- route rule


PRINTED_AREA = re.compile(r"\d[.,]\d|m\s?[2\u00b2]")  # "15.6 m" or "15 m2"; a bare "10 m" is a scale bar label


def flat_plan_signs(lines: list[TextLine]) -> int:
    """How many texts look like those of a modern flat plan: room numbers ("2.18") and printed areas ("15.6 m2")."""
    return sum(
        1 for ln in lines
        if ocr.room_number(ln.text) or (ocr.area_value(ln.text) is not None and PRINTED_AREA.search(ln.text))
    )  # fmt: skip


def looks_unlike_flat_plan(counts: count_head.PlanCounts) -> bool:
    """The count model's signal: outside its distribution and not in the style of a CubiCasa plan."""
    style = counts.style_margin
    return not counts.in_distribution and (style is None or style < STYLE_CUT)


def is_scan(counts: count_head.PlanCounts, lines: list[TextLine]) -> bool:
    """A small raster that is not a modern flat plan: the count model doubts it, and OCR reads no room numbers."""
    return looks_unlike_flat_plan(counts) and flat_plan_signs(lines) < FLAT_PLAN_NUMBERS


# ----------------------------------------------------------------------------- title block and captions

YEAR = re.compile(r"(?<![\d.,/])(1[5-9]\d\d|20[0-2]\d)(?![\d,])")
MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december|"
    "jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec|"
    "januari|februari|mars|maj|juni|juli|augusti|oktober|"  # sv
    "januar|februar|märz|mai|oktober|dezember|"  # de
    "janvier|février|fevrier|avril|juin|juillet|août|aout|septembre|octobre|novembre|décembre|"  # fr
    "tammikuu|helmikuu|maaliskuu|huhtikuu|toukokuu|kesäkuu|heinäkuu|elokuu|syyskuu|lokakuu|marraskuu|joulukuu"  # fi
)
DATE = re.compile(
    r"(?<!\d)(\d{1,2})\s?[./-]\s?(\d{1,2})\s?[./-]\s?(\d{2}|\d{4})(?!\d)"
    rf"|(?<!\w)(\d{{1,2}}\.?\s*(?:{MONTHS})\.?,?\s*\d{{2,4}})"
    rf"|(?<!\w)((?:{MONTHS})\.?\s+\d{{1,2}},?\s*\d{{4}})"
    rf"|(?<!\w)((?:{MONTHS})\.?\s+\d{{4}})",
    re.IGNORECASE,
)
ROLES = {
    "architect": re.compile(r"\b(architect|arkitekt|architekt|arkkitehti|architecte|architetto|arch\.)", re.IGNORECASE),
    "drawn by": re.compile(
        r"\b(drawn|del\.|delin|delineated|gez\.|gezeichnet|ritad|piirt|dessin|dessiné|dessine|mesuré|mesure)",
        re.IGNORECASE,
    ),
    "measured by": re.compile(r"\b(measured|aufgenommen|uppmätt|mitannut)", re.IGNORECASE),
    "builder": re.compile(r"\b(builder|byggmästare|baumeister|rakennusmestari)", re.IGNORECASE),
}
SHEET_NUMBER = re.compile(
    r"\b(sheet\s*\d+\s*of\s*\d+|\d+\s+of\s+\d+(?:\s*sheets)?|pl\.?\s*n[ro]\.?\s*\d+|pl\.\s*\d+|blatt\s*(?:nr\.?)?\s*\d+"
    r"|ritn\.?\s*(?:n[ro]\.?)?\s*\d+|piir\.?\s*\d+|n[ro]\.\s*\d+|sheets?\s*\d+\s*-\s*\d+)",
    re.IGNORECASE,
)
SCALE_WORD = re.compile(r"\b(scale|skala|kaava|maßstab|massstab|mittakaava|échelle|echelle|m\s?=|maatstaf)", re.IGNORECASE)
RATIO = re.compile(r"(?<![\d.,])1\s?[:/]\s?(\d{1,3}(?:,\d{3})+|\d{2,6})(?![\d.,])")  # 1:500, 1/500, 1:125,000
# An engineer's scale: 1" = 20' (an inch to N feet), 1:12N. OCR often reads the 1 as I or l.
ENGINEER = re.compile(r"(?<![\d/.])([1Il])\s?[\"\u201d]\s?=\s?(\d{1,4})\s?['\u2019](?!\s?-?\s?\d)")
COMMON_RATIOS = frozenset({10, 20, 25, 50, 100, 150, 200, 250, 300, 400, 500, 600, 1000, 1250, 1500, 2000, 2500,
                           2880, 4000, 5000, 10000})  # fmt: skip
KINDS = {
    "floor plan": re.compile(
        r"\b(floor plan|plan of|plan af|plan av|plan över|grundriss|grundriß|pohjapiirros|plan du|plan de|plan "
        r"d[eu]s?|plan zur|planta|pianta|stock|souterrain|kellare|källare|étage|etage|floor)\b|\bplan\b",
        re.IGNORECASE,
    ),
    "elevation": re.compile(r"\b(elevation|élévation|fasad|facade|façade|ansicht|julkisivu|aufriss|vue)\b", re.IGNORECASE),
    "section": re.compile(r"\b(section|sektion|schnitt|leikkaus|coupe|genomskärning|profil)\b", re.IGNORECASE),
    "site plan": re.compile(
        r"\b(site plan|asemapiirros|lageplan|situationsplan|tomt|plot plan|general plan|plan général|"
        r"nykytilannepiirustus|location|sketch map)\b",
        re.IGNORECASE,
    ),
    "detail": re.compile(r"\b(detail|details|yksityiskohta|détail)\b", re.IGNORECASE),
}


class TitleText(Frozen):
    """One text of the title block or a caption, with what it gives."""

    role: str  # "title", "year", "date", "architect", "drawn by", "sheet number", "printed scale", "kind"
    value: str  # the value read from the text: "1824", "1:500", "elevation"
    text: str  # the label as OCR read it
    label: Label


def _neighbour_name(all_labels: list[Label], label: Label) -> str | None:
    """The text right of or below a role word ("DRAWN BY:" then "KENNETH L. LAMBERT")."""
    for other in sheet_text.near(all_labels, label, limit=4):
        where, gap = sheet_text.side(label, other)
        if where in ("right", "below") and gap <= 3 and re.search(r"[A-Za-z]{3}", other.text):
            return other.text
    return None


def title_texts(all_labels: list[Label]) -> list[TitleText]:
    """Every text that gives a title block fact, in the order of the labels."""
    out: list[TitleText] = []
    for label in all_labels:
        text = sheet_text.clean(label.text)
        out.extend(TitleText(role="date", value=m.group(0).strip(), text=label.text, label=label)
                   for m in DATE.finditer(text))  # fmt: skip
        out.extend(TitleText(role="year", value=m.group(1), text=label.text, label=label) for m in YEAR.finditer(text))
        for role, pattern in ROLES.items():
            m = pattern.search(text)
            if m is None:
                continue
            rest = (text[: m.start()] + " " + text[m.end() :]).strip(" :-,.;")
            rest = re.sub(r"^(by|av|von|par)\b[: ]*", "", rest.strip(" :-,."), flags=re.IGNORECASE).strip(" :-,.")
            name = rest if re.search(r"[A-Za-z]{3}", rest) else _neighbour_name(all_labels, label)
            if name:
                out.append(TitleText(role=role, value=name, text=label.text, label=label))
        out.extend(TitleText(role="sheet number", value=m.group(0).strip(), text=label.text, label=label)
                   for m in SHEET_NUMBER.finditer(text))  # fmt: skip
        out.extend(TitleText(role="kind", value=kind, text=label.text, label=label)
                   for kind, pattern in KINDS.items() if pattern.search(text))  # fmt: skip
    out.extend(TitleText(role="printed scale", value=value, text=lb.text, label=lb) for value, lb in printed_ratios(all_labels))
    out.extend(TitleText(role="title", value=lb.text, text=lb.text, label=lb) for lb in titles(all_labels))
    return out


def printed_ratios(all_labels: list[Label]) -> list[tuple[str, Label]]:
    """Every printed scale as "1:N": 1:500, 1/500 next to a scale word, or imperial (1/4" = 1'-0", 1" = 20')."""
    lines = [TextLine(text=lb.text, box=((lb.bbox[0], lb.bbox[1]), (lb.bbox[2], lb.bbox[3])), score=1.0)
             for lb in all_labels]  # fmt: skip
    out: list[tuple[str, Label]] = []
    by_text = {lb.text: lb for lb in all_labels}
    for found in sheet_text.printed_scales(lines):
        if found.text.startswith("1:"):
            continue  # the metric ones are read below, with the 1/N form
        label = next((lb for lb in all_labels if found.text in sheet_text.clean(lb.text)), None)
        if label is not None:
            out.append((f"1:{found.ratio} ({found.text})", label))
    for label in all_labels:
        text = sheet_text.clean(label.text)
        out.extend((f"1:{12 * int(m.group(2))} ({m.group(0).strip()})", label) for m in ENGINEER.finditer(text)
                   if int(m.group(2)) >= 1)  # fmt: skip
        for m in RATIO.finditer(text):
            ratio = int(m.group(1).replace(",", ""))
            slash = "/" in m.group(0)
            near_word = SCALE_WORD.search(text) or any(
                SCALE_WORD.search(other.text) for other in sheet_text.near(all_labels, label, limit=4)
            )
            # "1/500" is also a fraction or a date: only a common ratio, or one next to a scale word, is a scale
            if (slash and not (near_word or ratio in COMMON_RATIOS)) or ratio < 10:
                continue
            out.append((f"1:{ratio}", by_text.get(label.text, label)))
    return out


def titles(all_labels: list[Label], keep: int = 4) -> list[Label]:
    """The texts in the largest letters: the title of the sheet and the captions of its drawings."""
    words = [lb for lb in all_labels if len(re.findall(r"[A-Za-zÀ-ÿ]", lb.text)) >= 4]
    return sorted(words, key=lambda lb: -lb.height)[:keep]


# ----------------------------------------------------------------------------- scale

UNITS = (
    (re.compile(r"^(m|mtr|meter|meters|metres|metre|mètres|metri|metriä|metrar|m\.)$", re.IGNORECASE), "m", 1.0),
    (re.compile(r"^(ft|feet|foot)$", re.IGNORECASE), "ft", 0.3048),
    (re.compile(r"^(cm)$", re.IGNORECASE), "cm", 0.01),
    (re.compile(r"^(km)$", re.IGNORECASE), "km", 1000.0),
)
# Old units with no single value in metres: a Paris foot (pied) is 0.325 m, a Vienna foot (Fuss) 0.316 m, a Swedish
# or Finnish foot (fot, jalka) 0.297 m, and each changed over time and place. They are read, never converted.
OLD_UNITS = re.compile(
    r"^(alnar|aln|toises?|klafter|ellen|pieds?|fuss|fuß|schuh|fot|jalkaa|jalka|faden|sazhen|saschen|piedi|palmi)$",
    re.IGNORECASE,
)
NUMBER_TOKEN = re.compile(r"^[|+'.\-\s]*(\d{1,3})[|+'.\-\s]*$")
BAR_FIT = 0.3  # a label lies within this share of one step of its fitted place
MIN_LABELS = 3
AGREE = 0.02  # two scale witnesses agree when they differ by less than this
TICK_PX = 1.5  # a tick mark found on the image is placed to about this many pixels


class BarScale(Frozen):
    """A scale bar: tick labels in a row whose positions grow in proportion to their values."""

    values: tuple[float, ...]
    xs_px: tuple[float, ...]  # the place of each value: a tick mark when found, else the centre of the label
    on_ticks: bool  # True when the places are tick marks on the bar line
    row_y: float
    px_per_unit: float
    unit: str | None  # "m", "ft", "cm", "km"; an old unit by name; None when no unit word was read
    metres_per_unit: float | None
    ppm: float | None  # None when the unit is not read or has no value in metres
    error: float  # relative error of px_per_unit, from the fit and the place error
    texts: tuple[str, ...]


@dataclass
class _Token:
    value: float
    x: float
    line: TextLine


def _tokens(lines: list[TextLine]) -> list[_Token]:
    """Numbers that can be tick labels. A line with several numbers ("0 1 2 3 4 5 m") gives each at its place."""
    out: list[_Token] = []
    for line in lines:
        parts = line.text.split()
        if not parts or line.width < line.height * 0.3:
            continue
        numbers = [(i, NUMBER_TOKEN.match(p)) for i, p in enumerate(parts)]
        if not all(m or _unit_of(p) for (_, m), p in zip(numbers, parts, strict=True)):
            continue
        if len(parts) == 1:
            m = numbers[0][1]
            if m:
                out.append(_Token(float(m.group(1)), line.cx, line))
            continue
        total = len(line.text)
        x0, _, x1, _ = line.bbox
        at = 0
        for part, (_, m) in zip(parts, numbers, strict=True):
            start = line.text.index(part, at)
            at = start + len(part)
            if m:
                centre = (start + len(part) / 2) / total
                out.append(_Token(float(m.group(1)), x0 + centre * (x1 - x0), line))
    return out


def _unit_of(word: str) -> tuple[str, float | None] | None:
    clean = word.strip(" .:;,|")
    clean = re.sub(r"^\d+\s?", "", clean)  # "15m" or "5 m"
    for pattern, name, metres in UNITS:
        if pattern.match(clean):
            return name, metres
    if OLD_UNITS.match(clean):
        return clean.lower(), None
    return None


FEET_MARK = re.compile(r"\d\s*'|\d\s*/\s*\d+\s*\"")  # 1' or 1/4": a scale or a label in feet and inches
UNIT_CLEAR = 2.0  # the nearest unit word must be this many times nearer than a word of another unit


def _bar_unit(lines: list[TextLine], row: list[_Token]) -> tuple[str, float | None] | None:
    """The unit of a bar: a word in the last label, right of it, or above or below the bar ("SCALE METERS").

    A sheet can carry a bar in feet and one in metres close together. When words of two units lie near the bar and
    neither is clearly nearer, the unit is not known: a bar read in the wrong unit is off by 3.3 times.
    """
    h = max(t.line.height for t in row)
    lo, hi = min(t.x for t in row) - 3 * h, max(t.x for t in row) + 6 * h
    y = sum(t.line.cy for t in row) / len(row)
    found: list[tuple[float, tuple[str, float | None]]] = []
    for line in lines:
        if not (lo <= line.cx <= hi and abs(line.cy - y) <= 5 * h):
            continue
        distance = abs(line.cy - y) + 0.2 * abs(line.cx - row[-1].x)
        units = [u for u in (_unit_of(word) for word in re.split(r"[\s,]+", line.text)) if u is not None]
        if FEET_MARK.search(line.text):
            units.append(("ft", 0.3048))
        found += [(distance, unit) for unit in units]
    if not found:
        return None
    found.sort(key=lambda f: f[0])
    best_distance, best = found[0]
    rival = next((d for d, unit in found if unit[0] != best[0]), None)
    if rival is not None and rival < UNIT_CLEAR * max(best_distance, 1.0):
        return None
    return best


def _rows(tokens: list[_Token]) -> list[list[_Token]]:
    rows: list[list[_Token]] = []
    for tok in sorted(tokens, key=lambda t: t.line.cy):
        for row in rows:
            ref = row[0].line
            if abs(ref.cy - tok.line.cy) < 0.6 * max(ref.height, tok.line.height):
                row.append(tok)
                break
        else:
            rows.append([tok])
    return [sorted(r, key=lambda t: t.x) for r in rows if len(r) >= MIN_LABELS]


def _increasing_run(row: list[_Token]) -> list[_Token]:
    """The longest run of labels, left to right, whose values grow (a subdivided first segment is dropped)."""
    best: list[_Token] = []
    for start in range(len(row)):
        run = [row[start]]
        for tok in row[start + 1 :]:
            if tok.value > run[-1].value:
                run.append(tok)
        if len(run) > len(best):
            best = run
    return best


def _fit(values: np.ndarray, xs: np.ndarray) -> tuple[float, float, float] | None:
    """(slope, intercept, largest residual) of x = intercept + slope * value, or None when it is not linear."""
    slope, start = np.polyfit(values, xs, 1)
    if slope <= 0:
        return None
    residual = float(np.abs(xs - (start + slope * values)).max())
    step = float(np.diff(np.sort(values)).min())
    if residual > BAR_FIT * slope * step:
        return None
    return float(slope), float(start), residual


def _ticks_on_bar(dark: np.ndarray, row: list[_Token], slope: float, start: float) -> tuple[float, list[float]] | None:
    """The row of the bar line near the labels, and the x of each tick mark on it."""
    h = max(t.line.height for t in row)
    top = min(t.line.bbox[1] for t in row)
    bottom = max(t.line.bbox[3] for t in row)
    lo = max(0, int(start + slope * row[0].value - 0.5 * slope))
    hi = min(dark.shape[1] - 1, int(start + slope * row[-1].value + 0.5 * slope))
    need = 0.6 * slope * (row[-1].value - row[0].value)
    best: tuple[int, int] | None = None  # (run length, y)
    for y in [*range(int(bottom), min(dark.shape[0], int(bottom + 3 * h))), *range(max(0, int(top - 3 * h)), int(top))]:
        run = dark[y, lo : hi + 1]
        length = int(run.sum())
        if length >= need and (best is None or length > best[0]):
            best = (length, y)
    if best is None:
        return None
    y = best[1]
    reach = max(3, round(0.6 * h))
    band = dark[max(0, y - reach) : y + reach + 1, lo : hi + 1]
    extent = band.sum(axis=0)
    base = float(np.median(extent))
    marks = extent >= base + max(3.0, 0.3 * h)
    ticks: list[float] = []
    i = 0
    while i < len(marks):
        if marks[i]:
            j = i
            while j + 1 < len(marks) and marks[j + 1]:
                j += 1
            if j - i <= max(4, 0.3 * slope):  # a tick is thin; a filled segment is not
                ticks.append(lo + (i + j) / 2)
            i = j + 1
        else:
            i += 1
    return float(y), ticks


SPLIT_GAP = 3.0  # a gap this many times the middle gap between labels parts two bars on one row


def _segments(row: list[_Token]) -> list[list[_Token]]:
    """Part a row of numbers at wide gaps: a sheet can carry a bar in metres and one in feet on the same row."""
    row = sorted(row, key=lambda t: t.x)
    if len(row) < 2 * MIN_LABELS:
        return [row]
    gaps = [b.x - a.x for a, b in itertools.pairwise(row)]
    middle = float(np.median(gaps))
    height = max(t.line.height for t in row)
    parts: list[list[_Token]] = [[row[0]]]
    for gap, tok in zip(gaps, row[1:], strict=True):
        if gap > SPLIT_GAP * middle and gap > 4 * height:
            parts.append([])
        parts[-1].append(tok)
    return parts


def scale_bars(gray: np.ndarray, lines: list[TextLine]) -> list[BarScale]:
    """Every scale bar that OCR reads, longest first."""
    dark = gray < min(160.0, float(np.percentile(gray, 50)) - 40.0)
    found: list[BarScale] = []
    for row in (part for whole in _rows(_tokens(lines)) for part in _segments(whole)):
        run = _increasing_run(row)
        if len(run) < MIN_LABELS:
            continue
        values = np.array([t.value for t in run])
        fit = _fit(values, np.array([t.x for t in run]))
        if fit is None:
            continue
        slope, start, residual = fit
        xs = [t.x for t in run]
        on_ticks = False
        bar = _ticks_on_bar(dark, run, slope, start)
        row_y = float(np.mean([t.line.cy for t in run]))
        if bar is not None:
            row_y, ticks = bar
            matched = []
            for t in run:
                near = [x for x in ticks if abs(x - (start + slope * t.value)) <= 0.3 * slope]
                matched.append(min(near, key=lambda x: abs(x - (start + slope * t.value))) if near else None)
            if sum(m is not None for m in matched) >= MIN_LABELS:
                keep = [(t.value, m) for t, m in zip(run, matched, strict=True) if m is not None]
                tick_fit = _fit(np.array([v for v, _ in keep]), np.array([m for _, m in keep]))
                if tick_fit is not None:
                    slope, start, residual = tick_fit
                    run = [t for t, m in zip(run, matched, strict=True) if m is not None]
                    xs = [m for m in matched if m is not None]
                    on_ticks = True
        span = slope * (run[-1].value - run[0].value)
        place = TICK_PX if on_ticks else 0.5 * max(t.line.height for t in run)
        error = max(residual, place) * 2 / span
        unit = _bar_unit(lines, run)
        metres = unit[1] if unit else None
        found.append(BarScale(
            values=tuple(t.value for t in run), xs_px=tuple(round(x, 1) for x in xs), on_ticks=on_ticks,
            row_y=round(row_y, 1), px_per_unit=round(slope, 3), unit=unit[0] if unit else None,
            metres_per_unit=metres, ppm=round(slope / metres, 3) if metres else None, error=round(error, 4),
            texts=tuple(dict.fromkeys(t.line.text for t in run)),
        ))  # fmt: skip
    return sorted(found, key=lambda b: -(b.xs_px[-1] - b.xs_px[0]))


class ScanScale(Frozen):
    """The pixels per metre of a scan, with its witnesses and a relative error."""

    ppm: float
    source: str  # "user", "scale bar", "scale bars", "dimension lines", "scale bar and dimension lines"
    error: float  # relative error of ppm
    confirmed: bool  # two independent witnesses agree within 2%
    detail: str


def scan_scale(
    bars: list[BarScale], dimensions: sheet_geometry.DimensionScale | None, calibration: Calibration | None = None
) -> ScanScale | None:
    """The scale from the user, or from the bars with a unit and the dimension lines. None when nothing proves it.

    Two witnesses that disagree by more than 2% give no scale: one of them is read wrong, and a wrong length costs
    more than no length.
    """
    if calibration and calibration.points and calibration.real_length_m and calibration.real_length_m > 0:
        (ax, ay), (bx, by) = calibration.points
        pixels = math.hypot(bx - ax, by - ay)
        if pixels >= 2:
            return ScanScale(ppm=round(pixels / calibration.real_length_m, 3), source="user", error=0.01,
                             confirmed=False,
                             detail=f"{calibration.real_length_m:g} m between two points that the user marked")  # fmt: skip
    witnesses: list[tuple[str, float, float]] = [  # (name, ppm, relative error)
        (f"scale bar {bar.values[0]:g} to {bar.values[-1]:g} {bar.unit}", bar.ppm, bar.error) for bar in bars if bar.ppm
    ]
    if dimensions is not None:
        witnesses.append((f"{dimensions.agreeing} dimension lines", dimensions.ppm, max(0.01, dimensions.spread)))
    if not witnesses:
        return None
    first = witnesses[0]
    others = [w for w in witnesses[1:] if abs(w[1] / first[1] - 1) > AGREE]
    if others:
        return None
    agree = [w for w in witnesses if abs(w[1] / first[1] - 1) <= AGREE]
    names = ", ".join(w[0] for w in agree)
    kinds = {"bar" if w[0].startswith("scale bar") else "lines" for w in agree}
    source = {frozenset({"bar"}): "scale bar", frozenset({"lines"}): "dimension lines"}.get(
        frozenset(kinds), "scale bar and dimension lines"
    )
    if source == "scale bar" and len(agree) > 1:
        source = "scale bars"
    error = max(min(w[2] for w in agree), *(abs(w[1] / first[1] - 1) for w in agree))
    return ScanScale(ppm=first[1], source=source, error=round(error, 4), confirmed=len(agree) > 1,
                     detail=f"from {names}")  # fmt: skip


# ----------------------------------------------------------------------------- extent of each drawing


class Drawing(Frozen):
    """One drawing on the page: a connected piece of line work, with the caption nearest below or above it."""

    index: int
    bbox: tuple[int, int, int, int]  # x0, y0, x1, y1 in pixels, to the outer face of the lines
    caption: str | None


MIN_DRAWING_SHARE = 0.02  # of the page side: a smaller piece is a mark, a letter or a dot
BIG_SHARE = 0.6  # a piece this wide or high can be the border or a trim line of the sheet: see _is_frame
FRAME_BAND = 0.03  # of the short side of the piece: the band along its edge
FRAME_INNER = 0.25  # a frame has less than this share of its pixels inside the band
THIN_SHARE = 0.015  # of the long page side: a piece thinner than this is a lone line, a rule or a border


def drawings(gray: np.ndarray, labels: list[Label], keep: int = 6) -> list[Drawing]:
    """The largest pieces of connected line work, text removed, the sheet border left out. Largest first.

    A drawing can fill the whole page; a border is told from it by where its pixels lie (_is_frame), not by its size.

    Lines that a scan breaks by a pixel or two are joined first (a closing of 3 px). A dimension chain that touches
    the walls with its extension lines makes the piece wider than the building: the caption and the size tell.
    """
    height, width = gray.shape
    dark = (gray < min(160.0, float(np.percentile(gray, 50)) - 40.0)).astype(np.uint8)
    for lb in labels:
        x0, y0, x1, y1 = (round(v) for v in lb.bbox)
        dark[max(0, y0 - 1) : y1 + 2, max(0, x0 - 1) : x1 + 2] = 0
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    count, comp, stats, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    pieces = []
    for i in range(1, count):
        x, y, w, h, _ = (int(v) for v in stats[i])
        if max(w / width, h / height) < MIN_DRAWING_SHARE * 5 or min(w, h) < THIN_SHARE * max(width, height):
            continue
        if (w >= BIG_SHARE * width or h >= BIG_SHARE * height) and _is_frame(comp[y : y + h, x : x + w] == i):
            continue
        pieces.append((x, y, x + w - 1, y + h - 1))
    pieces.sort(key=lambda b: -((b[2] - b[0]) * (b[3] - b[1])))
    out = []
    for index, box in enumerate(pieces[:keep]):
        out.append(Drawing(index=index, bbox=box, caption=_caption(labels, box)))
    return out


def _is_frame(mask: np.ndarray) -> bool:
    """A trim line or a border with a few lines on it: most of its pixels lie near the edge of its box."""
    h, w = mask.shape
    band = max(3, round(FRAME_BAND * min(h, w)))
    inner = int(mask[band:-band, band:-band].sum())
    return inner < FRAME_INNER * max(1, int(mask.sum()))


def _caption(labels: list[Label], box: tuple[int, int, int, int]) -> str | None:
    x0, y0, x1, y1 = box
    best: tuple[float, str] | None = None
    for lb in labels:
        cx, cy = lb.at
        if not (x0 - 0.1 * (x1 - x0) <= cx <= x1 + 0.1 * (x1 - x0)) or len(lb.text) < 4:
            continue
        gap = cy - y1 if cy > y1 else (y0 - cy if cy < y0 else None)
        if gap is None or gap > 0.4 * (y1 - y0) + 10 * lb.height:
            continue
        if best is None or gap < best[0]:
            best = (gap, lb.text)
    return best[1] if best else None


# ----------------------------------------------------------------------------- one reading per scan


@dataclass
class ScanReading:
    """What the tools and the facts of one scan are built from. The facts of the same image read the same object."""

    rgb: np.ndarray
    lines: list[TextLine]  # OCR lines joined to phrases
    labels: list[Label]
    bars: list[BarScale]
    dimensions: sheet_geometry.DimensionScale | None
    calibration: Calibration | None = None
    _drawings: list[Drawing] | None = field(default=None, repr=False)

    @property
    def gray(self) -> np.ndarray:
        return self.rgb.mean(axis=2)

    @property
    def scale(self) -> ScanScale | None:
        return scan_scale(self.bars, self.dimensions, self.calibration)

    @property
    def drawings(self) -> list[Drawing]:
        if self._drawings is None:
            self._drawings = drawings(self.gray, self.labels)
        return self._drawings

    @property
    def title(self) -> list[TitleText]:
        return title_texts(self.labels)


CACHE_SIZE = 4
_readings: OrderedDict[tuple[str, str], ScanReading] = OrderedDict()
_lock = threading.Lock()


def read_scan(rgb: np.ndarray, calibration: Calibration | None = None, lines: list[TextLine] | None = None) -> ScanReading:
    """Read one scan, once per process and calibration."""
    key = (sheet_text.pixel_key(rgb), calibration.model_dump_json() if calibration else "")
    with _lock:
        if key in _readings:
            return _readings[key]
    raw = lines if lines is not None else read_lines(rgb)
    joined = phrases(raw)
    gray = rgb.mean(axis=2)
    reading = ScanReading(
        rgb=rgb, lines=joined, labels=sheet_text.labels(joined), bars=scale_bars(gray, raw),
        dimensions=sheet_geometry.dimension_scale(rgb, raw), calibration=calibration,
    )  # fmt: skip
    with _lock:
        _readings[key] = reading
        _readings.move_to_end(key)
        while len(_readings) > CACHE_SIZE:
            _readings.popitem(last=False)
    return reading
