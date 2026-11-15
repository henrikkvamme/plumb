"""A page render as drawing ink on a transparent sheet, so the desk puts every drawing, also a scan, on its own paper.

`ink`: each pixel becomes black, with an alpha equal to its darkness against the paper of the sheet.
`walls`: only the thick dark strokes, for the cast shadow and the raised walls of the 3D view.
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

LAYERS = ("page", "ink", "walls")
INK = (22, 22, 24)


def _darkness(png: bytes) -> Image.Image:
    grey = np.asarray(Image.open(io.BytesIO(png)).convert("L"), dtype=np.float32)
    if float(np.median(grey)) < 110:
        grey = 255.0 - grey
    paper = float(np.percentile(grey, 90))
    black = float(np.percentile(grey, 0.5))
    span = max(paper - black - 8.0, 40.0)
    dark = np.clip((paper - 8.0 - grey) / span, 0.0, 1.0) ** 0.85
    return Image.fromarray((dark * 255).astype(np.uint8), "L")


def _walls(alpha: Image.Image, rooms: list[list[tuple[float, float]]], page_width: float) -> Image.Image:
    """The thick dark strokes. With room outlines: the ink in a band along the outlines, with hatching closed."""
    if not rooms:
        solid = alpha.point(lambda v: 255 if v > 150 else 0)
        return solid.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    scale = alpha.width / page_width
    sides = sorted(
        ((max(x for x, _ in room) - min(x for x, _ in room)) * (max(y for _, y in room) - min(y for _, y in room))) ** 0.5
        for room in rooms
    )
    reach = max(5, round(sides[len(sides) // 2] * scale * 0.22))
    band = Image.new("L", alpha.size, 0)
    draw = ImageDraw.Draw(band)
    for room in rooms:
        outline = [(x * scale, y * scale) for x, y in room]
        draw.line([*outline, outline[0]], fill=255, width=reach, joint="curve")
    solid = alpha.point(lambda v: 255 if v > 90 else 0)
    closed = solid.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
    kept = ImageChops.darker(closed, band)
    return kept.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))


def layer(png: bytes, kind: str, rooms: list[list[tuple[float, float]]] | None = None, page_width: float = 1.0) -> bytes:
    if kind == "page":
        return png
    alpha = _darkness(png)
    if kind == "walls":
        alpha = _walls(alpha, rooms or [], page_width).filter(ImageFilter.GaussianBlur(0.6))
    sheet = Image.new("RGBA", alpha.size, (*INK, 0))
    sheet.putalpha(alpha)
    out = io.BytesIO()
    sheet.save(out, "PNG")
    return out.getvalue()
