"""Measure the pixels per metre of a raster drawing from two independent witnesses.

1. The scale bar. OCR finds a row of tick labels ("0 2 4 10", "0 1 2 5") whose x positions grow in proportion to
   their values. Below them the bar is a row of filled and empty segments. Its edges are found on one image row
   with sub-pixel interpolation. Each edge sits at x0 + s * v, moved by half the outline width: outwards at the two
   ends and towards the empty segment inside. A least-squares fit gives s (pixels per bar unit), x0 and the line
   width. The unit comes from the text right of the last label ("m", "cm", "mm", "ft").
2. The scale text "1:N (A3)": the paper size gives pixels per paper metre from the image size (the image must
   be the whole sheet: its aspect ratio must match the paper), so pixels per real metre = that / N.

The two agree when they differ by less than 1%. No witness: None. The witnesses never use an assumed dpi.
"""

from __future__ import annotations

import itertools
import re
import statistics
from typing import TYPE_CHECKING, Literal

import numpy as np

from bp.contract import Evidence, Frozen

if TYPE_CHECKING:
    from bp.tools.ocr import TextLine

AGREE = 0.01
PAPER_MM = {"A0": (1189, 841), "A1": (841, 594), "A2": (594, 420), "A3": (420, 297), "A4": (297, 210)}
ASPECT_TOL = 0.02
UNIT_M = {"m": 1.0, "cm": 0.01, "mm": 0.001, "ft": 0.3048}
RATIO = re.compile(r"1\s*:\s*(\d{2,5})")
PAPER = re.compile(r"\(?\s*(A[0-4])\s*\)?")
TICK = re.compile(r"^\d{1,3}$")
DARK = 128.0
LABEL_ROW_TOL = 0.6  # labels of one bar share a baseline within this share of the text height
LABEL_FIT_TOL = 0.25  # a label sits within this share of one bar unit of its fitted place
EDGE_TOL = 0.35  # an edge sits within this share of the smallest segment of its label


class BarWitness(Frozen):
    ppm: float
    unit: str
    values: tuple[float, ...]  # the tick labels read, in bar units
    edges_px: tuple[float, ...]
    row_y: int
    line_width_px: float
    residual_px: float


class TextWitness(Frozen):
    ratio: int
    paper: str | None
    ppm: float | None  # None when the paper is not printed or the image is not the whole sheet
    text: str


class RasterScale(Frozen):
    ppm: float  # the chosen pixels per metre
    # "areas": from the printed room areas against the room shapes; "doors": an estimate from the door symbols;
    # "user": two points and their real distance from the user.
    source: Literal["both", "bar", "text", "areas", "doors", "user"]
    agree: bool | None  # None when only one witness exists
    difference: float | None  # relative difference of the two witnesses
    bar: BarWitness | None
    text: TextWitness | None
    evidence: tuple[Evidence, ...]

    @property
    def ratio(self) -> int | None:
        return self.text.ratio if self.text else None

    @property
    def confirmed(self) -> bool:
        return bool(self.agree)


# ----------------------------------------------------------------------------- scale text


def text_witness(lines: list[TextLine], width: int, height: int) -> tuple[TextWitness, TextLine] | None:
    """The first "1:N" text; with a paper size ("(A3)") it gives the pixels per metre."""
    best: tuple[TextWitness, TextLine] | None = None
    for line in lines:
        match = RATIO.search(line.text.replace(" ", ""))
        if match is None:
            continue
        ratio = int(match.group(1))
        if ratio < 10:
            continue
        paper_match = PAPER.search(line.text[match.end() - 1 :])
        paper = paper_match.group(1) if paper_match else None
        ppm = None
        if paper is not None:
            long_mm, short_mm = PAPER_MM[paper]
            long_px, short_px = max(width, height), min(width, height)
            if abs((long_px / short_px) / (long_mm / short_mm) - 1.0) < ASPECT_TOL:
                ppm = long_px / (long_mm / 1000.0) / ratio
        witness = TextWitness(ratio=ratio, paper=paper, ppm=ppm, text=line.text)
        if best is None or (best[0].ppm is None and ppm is not None):
            best = (witness, line)
    return best


# ----------------------------------------------------------------------------- scale bar


def _label_rows(lines: list[TextLine]) -> list[list[tuple[float, TextLine]]]:
    ticks = [(float(line.text), line) for line in lines if TICK.match(line.text.strip())]
    rows: list[list[tuple[float, TextLine]]] = []
    for value, line in sorted(ticks, key=lambda t: t[1].cy):
        for row in rows:
            ref = row[0][1]
            if abs(ref.cy - line.cy) < LABEL_ROW_TOL * max(ref.height, line.height):
                row.append((value, line))
                break
        else:
            rows.append([(value, line)])
    out = []
    for row in rows:
        row.sort(key=lambda t: t[1].cx)
        values = [v for v, _ in row]
        if len(row) >= 3 and values[0] == 0 and all(b > a for a, b in itertools.pairwise(values)):
            out.append(row)
    return out


def _fit_labels(row: list[tuple[float, TextLine]]) -> tuple[float, float] | None:
    values = np.array([v for v, _ in row])
    xs = np.array([line.cx for _, line in row])
    s, x0 = np.polyfit(values, xs, 1)
    if s <= 0:
        return None
    if np.abs(xs - (x0 + s * values)).max() > LABEL_FIT_TOL * s * max(1.0, float(np.diff(values).min())):
        return None
    return float(s), float(x0)


def _edges(profile: np.ndarray, offset: int) -> list[tuple[float, int]]:
    """Sub-pixel crossings of the dark level, with +1 for light -> dark and -1 for dark -> light."""
    dark = profile < DARK
    out: list[tuple[float, int]] = []
    for i in np.nonzero(np.diff(dark.astype(np.int8)))[0]:
        a, b = float(profile[i]), float(profile[i + 1])
        t = (a - DARK) / (a - b) if a != b else 0.5
        out.append((offset + i + 0.5 + t, 1 if b < a else -1))
    return out


def _bar_on_row(
    gray: np.ndarray, y: int, values: list[float], s: float, x0: float
) -> tuple[list[float], list[int], float, float, float] | None:
    """Match the edges on row `y` to the labels and fit x0, s and the line width."""
    lo = max(0, int(x0 - 0.5 * s * min(np.diff(values))))
    hi = min(gray.shape[1], int(x0 + s * values[-1] + 0.5 * s * min(np.diff(values))) + 1)
    if hi - lo < 10:
        return None
    edges = _edges(gray[y, lo:hi].astype(float), lo)
    if len(edges) != len(values):
        return None
    tol = EDGE_TOL * s * float(min(np.diff(values)))
    rows, rhs, signs = [], [], []
    for i, ((x, direction), v) in enumerate(zip(edges, values, strict=True)):
        if abs(x - (x0 + s * v)) > tol:
            return None
        if i == 0:
            sign = -1.0  # the outline grows the bar outwards
        elif i == len(values) - 1:
            sign = 1.0
        else:
            sign = 1.0 if direction < 0 else -1.0  # a dark segment grows into the light one next to it
        rows.append([1.0, v, sign / 2.0])
        rhs.append(x)
        signs.append(sign)
    if edges[0][1] != 1 or edges[-1][1] != -1:
        return None
    a = np.array(rows)
    b = np.array(rhs)
    sol, *_ = np.linalg.lstsq(a, b, rcond=None)
    residual = float(np.abs(a @ sol - b).max())
    return [x for x, _ in edges], [int(d) for _, d in edges], float(sol[1]), float(sol[2]), residual


def _unit_after(lines: list[TextLine], last: TextLine) -> str | None:
    for line in lines:
        word = line.text.strip().lower()
        if word in UNIT_M and abs(line.cy - last.cy) < 2 * last.height and 0 < line.cx - last.cx < 6 * last.height:
            return word
    return None


def bar_witness(gray: np.ndarray, lines: list[TextLine]) -> tuple[BarWitness, list[tuple[float, float]]] | None:
    for row in _label_rows(lines):
        fit = _fit_labels(row)
        if fit is None:
            continue
        s, x0 = fit
        values = [v for v, _ in row]
        h = max(line.height for _, line in row)
        bottom = max(line.bbox[3] for _, line in row)
        top = min(line.bbox[1] for _, line in row)
        hits = []
        for y in [
            *range(int(bottom), min(gray.shape[0], int(bottom + 4 * h))),
            *range(max(0, int(top - 4 * h)), int(top)),
        ]:
            got = _bar_on_row(gray, y, values, s, x0)
            if got is not None:
                hits.append((y, got))
        if not hits:
            continue
        y, (edges, _, slope, width, residual) = hits[len(hits) // 2]  # the middle row of the bar
        slopes = [got[2] for _, got in hits]
        unit = _unit_after(lines, row[-1][1]) or "m"
        ppm = statistics.median(slopes) / UNIT_M[unit]
        witness = BarWitness(
            ppm=ppm,
            unit=unit,
            values=tuple(values),
            edges_px=tuple(round(e, 3) for e in edges),
            row_y=y,
            line_width_px=round(width, 3),
            residual_px=round(residual, 3),
        )
        del slope
        return witness, [(edges[0], float(y)), (edges[-1], float(y))]
    return None


# ----------------------------------------------------------------------------- both


def measure_scale(gray: np.ndarray, lines: list[TextLine]) -> RasterScale | None:
    """Pixels per metre of the image, from the scale bar and the scale text. None when neither gives one."""
    height, width = gray.shape[:2]
    bar = bar_witness(gray, lines)
    text = text_witness(lines, width, height)
    evidence: list[Evidence] = []
    bar_w = bar[0] if bar else None
    text_w = text[0] if text else None
    if bar is not None:
        evidence.append(Evidence(kind="scale", points=tuple(bar[1]), ref=f"scale bar {bar[0].values} {bar[0].unit}"))
    if text is not None:
        evidence.append(Evidence(kind="scale", points=((text[1].cx, text[1].cy),), ref=text[1].text))
    text_ppm = text_w.ppm if text_w else None
    if bar_w is None and text_ppm is None:
        return None
    if bar_w is not None and text_ppm is not None:
        diff = abs(bar_w.ppm / text_ppm - 1.0)
        agree = diff < AGREE
        # The text is exact when it agrees; when the two differ, trust the bar that is measured on the image.
        ppm, source = (text_ppm, "both") if agree else (bar_w.ppm, "bar")
        return RasterScale(ppm=ppm, source=source, agree=agree, difference=round(diff, 5), bar=bar_w, text=text_w,
                           evidence=tuple(evidence))  # fmt: skip
    if bar_w is not None:
        return RasterScale(ppm=bar_w.ppm, source="bar", agree=None, difference=None, bar=bar_w, text=text_w,
                           evidence=tuple(evidence))  # fmt: skip
    assert text_ppm is not None
    return RasterScale(ppm=text_ppm, source="text", agree=None, difference=None, bar=None, text=text_w,
                       evidence=tuple(evidence))  # fmt: skip
