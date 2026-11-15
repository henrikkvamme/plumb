"""Render a document page to PNG bytes at a chosen longest side.

A PDF page is drawn with PyMuPDF at the exact size. An image is resized with Pillow. A DXF or an IFC file
is not rendered: the function returns None, because a picture of a model file needs a view that someone chose.
"""

from __future__ import annotations

import io
from pathlib import Path

import pymupdf
from PIL import Image

PDF_SUFFIXES = frozenset({".pdf"})
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"})
MAX_PDF_SCALE = 8.0  # a guard for pages with a tiny media box


def _png(image: Image.Image) -> bytes:
    """Flatten any transparency onto white and encode as PNG."""
    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        flat = Image.new("RGB", rgba.size, "white")
        flat.paste(rgba, mask=rgba.getchannel("A"))
        image = flat
    elif image.mode != "RGB":
        image = image.convert("RGB")
    out = io.BytesIO()
    image.save(out, format="PNG", optimize=False)
    return out.getvalue()


def page_count(path: str | Path) -> int:
    """The number of pages of a PDF, 1 for an image, 0 for any other file."""
    suffix = Path(path).suffix.lower()
    if suffix in PDF_SUFFIXES:
        with pymupdf.open(str(path)) as pdf:
            return pdf.page_count
    return 1 if suffix in IMAGE_SUFFIXES else 0


def render_pdf_page(path: str | Path, page: int, side: int) -> bytes:
    """Draw one PDF page so that its longest side is `side` pixels."""
    with pymupdf.open(str(path)) as pdf:
        target = pdf.load_page(page)
        rect = target.rect
        longest = max(rect.width, rect.height)
        if longest <= 0:
            msg = "the page has no size"
            raise ValueError(msg)
        zoom = min(side / longest, MAX_PDF_SCALE)
        pixmap = target.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        return pixmap.tobytes("png")


def render_image(path: str | Path, side: int, *, upscale: bool = False) -> bytes:
    """Resize an image so that its longest side is at most `side` pixels (exactly `side` with `upscale`)."""
    with Image.open(path) as source:
        source.load()
        longest = max(source.size)
        if longest > side or (upscale and longest < side):
            factor = side / longest
            size = (max(1, round(source.width * factor)), max(1, round(source.height * factor)))
            return _png(source.resize(size, Image.Resampling.LANCZOS))
        return _png(source)


def render_page(path: str | Path, side: int, page: int = 0) -> bytes | None:
    """PNG bytes of page `page` with the longest side `side`, or None for a file that is not rendered."""
    suffix = Path(path).suffix.lower()
    if suffix in PDF_SUFFIXES:
        return render_pdf_page(path, page, side)
    if suffix in IMAGE_SUFFIXES:
        return render_image(path, side)
    return None
