"""Read the text and the vector paths of one PDF page, with their coordinates.

This tool knows nothing about any kind of drawing. It turns a page into frozen records: text spans with a box,
and vector paths with their style (stroke colour, fill colour, line width, dashes), their bounding box, the
sequence of drawing operators and the points. Coordinates are PDF points in the page space of PyMuPDF
(origin at the top left, y grows downwards). Other tools build on these records.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pymupdf

from bp.contract import Frozen

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

Point = tuple[float, float]
BBox = tuple[float, float, float, float]
RGB = tuple[float, float, float]

# PyMuPDF operator names -> one letter in `VectorPath.ops`.
_OPS = {"l": "l", "re": "r", "qu": "q", "c": "c"}
_SAME_POINT = 1e-6


class TextSpan(Frozen):
    """One run of text with one font and size. `bbox` is (x0, y0, x1, y1) in points."""

    text: str
    bbox: BBox
    size: float
    font: str = ""

    @property
    def cx(self) -> float:
        return (self.bbox[0] + self.bbox[2]) / 2

    @property
    def cy(self) -> float:
        return (self.bbox[1] + self.bbox[3]) / 2


class VectorPath(Frozen):
    """One vector path as PyMuPDF reports it.

    `ops` holds one letter per drawing operator: l (line), r (rectangle), q (quad), c (Bezier curve).
    `points` is the outline in drawing order with repeated points removed (curves give their end points).
    `rings` splits the outline into its subpaths: a new subpath starts at each rectangle or quad, and where an
    operator does not start at the end of the one before. A room with holes or with two parts is one path with
    several rings. `lines` holds the end points of each straight line operator.
    """

    seqno: int
    kind: str  # "f" fill, "s" stroke, "fs" both
    stroke: RGB | None
    fill: RGB | None
    width: float
    dashed: bool
    bbox: BBox
    ops: str
    points: tuple[Point, ...]
    rings: tuple[tuple[Point, ...], ...]
    lines: tuple[tuple[Point, Point], ...]
    even_odd: bool = False

    def count(self, op: str) -> int:
        return self.ops.count(op)


class PdfPage(Frozen):
    """One page: its size, its producer, its text spans and its vector paths."""

    page: int
    width: float
    height: float
    producer: str
    spans: tuple[TextSpan, ...]  # text merged into lines by PyMuPDF
    runs: tuple[TextSpan, ...]  # one record per text-showing operator, never merged
    paths: tuple[VectorPath, ...]
    images: int


def _rgb(value: Sequence[float] | None) -> RGB | None:
    if value is None or len(value) < 3:
        return None
    return (float(value[0]), float(value[1]), float(value[2]))


def _dedupe(raw: Iterable[pymupdf.Point]) -> list[Point]:
    points: list[Point] = []
    for p in raw:
        if not points or abs(p.x - points[-1][0]) > _SAME_POINT or abs(p.y - points[-1][1]) > _SAME_POINT:
            points.append((p.x, p.y))
    return points


def _outline(
    items: Iterable[tuple[object, ...]],
) -> tuple[str, list[Point], list[list[Point]], list[tuple[Point, Point]]]:
    ops: list[str] = []
    raw: list[pymupdf.Point] = []
    rings: list[list[pymupdf.Point]] = []
    current: list[pymupdf.Point] = []
    lines: list[tuple[Point, Point]] = []

    def close_ring() -> None:
        if current:
            rings.append(list(current))
            current.clear()

    for item in items:
        op = str(item[0])
        ops.append(_OPS.get(op, "?"))
        if op in {"l", "c"}:
            a, b = item[1], item[4 if op == "c" else 2]
            if not (isinstance(a, pymupdf.Point) and isinstance(b, pymupdf.Point)):
                continue
            if current and (abs(a.x - current[-1].x) > _SAME_POINT or abs(a.y - current[-1].y) > _SAME_POINT):
                close_ring()
            if not current:
                current.append(a)
            current.append(b)
            raw += [a, b]
            if op == "l":
                lines.append(((a.x, a.y), (b.x, b.y)))
        elif op in {"re", "qu"}:
            shape = item[1]
            if isinstance(shape, pymupdf.Rect):
                corners = [shape.tl, shape.tr, shape.br, shape.bl]
            elif isinstance(shape, pymupdf.Quad):
                corners = [shape.ul, shape.ur, shape.lr, shape.ll]
            else:
                continue
            close_ring()
            rings.append(corners)
            raw += corners
    close_ring()
    return "".join(ops), _dedupe(raw), [_dedupe(r) for r in rings], lines


def _spans(page: pymupdf.Page) -> list[TextSpan]:
    out: list[TextSpan] = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                text = str(span["text"]).strip()
                if not text:
                    continue
                x0, y0, x1, y1 = (float(v) for v in span["bbox"])
                out.append(
                    TextSpan.model_construct(
                        text=text, bbox=(x0, y0, x1, y1), size=float(span["size"]), font=str(span.get("font", ""))
                    )
                )
    return out


def _runs(page: pymupdf.Page) -> list[TextSpan]:
    """One record per text operator, never merged.

    Two numbers drawn so close that PyMuPDF merges them into one span ("2.472.48") stay two records here.
    """
    out: list[TextSpan] = []
    for trace in page.get_texttrace():
        text = "".join(chr(c[0]) for c in trace["chars"]).strip()
        if not text:
            continue
        x0, y0, x1, y1 = (float(v) for v in trace["bbox"])
        out.append(
            TextSpan.model_construct(
                text=text, bbox=(x0, y0, x1, y1), size=float(trace["size"]), font=str(trace["font"])
            )
        )
    return out


def _paths(page: pymupdf.Page) -> list[VectorPath]:
    out: list[VectorPath] = []
    for index, drawing in enumerate(page.get_drawings()):
        ops, points, rings, lines = _outline(drawing["items"])
        rect = drawing["rect"]
        dashes = str(drawing.get("dashes") or "")
        out.append(
            VectorPath.model_construct(
                seqno=int(drawing.get("seqno", index)),
                kind=str(drawing.get("type", "")),
                stroke=_rgb(drawing.get("color")),
                fill=_rgb(drawing.get("fill")),
                width=float(drawing.get("width") or 0.0),
                dashed=bool(dashes) and not dashes.startswith("[]"),
                bbox=(float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)),
                ops=ops,
                points=tuple(points),
                rings=tuple(tuple(r) for r in rings),
                lines=tuple(lines),
                even_odd=bool(drawing.get("even_odd", False)),
            )
        )
    return out


def is_pdf(path: str | Path) -> bool:
    """True when the file starts with the PDF magic bytes. It does not trust the file name."""
    try:
        with Path(path).open("rb") as handle:
            head = handle.read(1024)
    except OSError:
        return False
    return b"%PDF-" in head


def page_count(path: str | Path) -> int:
    """The number of pages, or 0 when the file is not a PDF that PyMuPDF can open."""
    if not is_pdf(path):
        return 0
    try:
        with pymupdf.open(str(path)) as pdf:
            return pdf.page_count
    except (RuntimeError, ValueError):
        return 0


def read_page(path: str | Path, page: int = 0) -> PdfPage:
    """Read one page into text spans and vector paths. It raises ValueError when the file is not a readable PDF."""
    if not is_pdf(path):
        msg = "not a PDF file"
        raise ValueError(msg)
    try:
        pdf = pymupdf.open(str(path))
    except RuntimeError as exc:
        msg = f"PyMuPDF cannot open the file: {exc}"
        raise ValueError(msg) from exc
    with pdf:
        if not 0 <= page < pdf.page_count:
            msg = f"page {page} not in 0..{pdf.page_count - 1}"
            raise ValueError(msg)
        pg = pdf[page]
        metadata = pdf.metadata or {}
        return PdfPage.model_construct(
            page=page,
            width=float(pg.rect.width),
            height=float(pg.rect.height),
            producer=str(metadata.get("producer") or ""),
            spans=tuple(_spans(pg)),
            runs=tuple(_runs(pg)),
            paths=tuple(_paths(pg)),
            images=len(pg.get_images(full=False)),
        )
