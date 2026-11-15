"""A picture of a DXF floor plan, in the page frame of `bp.facts_models.dxf_facts` plus a pad on each side."""

from __future__ import annotations

import io
import os
from functools import lru_cache
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

PAD_M = 0.8
PAPER = (255, 255, 255)
INK = (24, 24, 26)
TONES = {"WALL": (INK, 2.4), "ROOM_OUTLINE": ((150, 150, 150), 1.0), "UNIT_OUTLINE": ((200, 60, 50), 1.6),
         "FIXTURE": ((90, 90, 94), 1.0), "DOOR": ((60, 60, 64), 1.2), "WINDOW": ((60, 60, 64), 1.2)}  # fmt: skip
OVERSAMPLE = 2
LETTER = 0.5
FONTS = ("/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/dejavu/DejaVuSans.ttf")  # fmt: skip


def is_dxf(path: Path) -> bool:
    return path.suffix.lower() == ".dxf"


def _texts(path: Path) -> list[tuple[float, float, str]]:
    import ezdxf  # noqa: PLC0415

    return [(e.dxf.insert.x, float(e.dxf.get("height", 0.2)), str(e.dxf.text))
            for e in ezdxf.readfile(str(path)).modelspace().query("TEXT")]  # fmt: skip


@lru_cache(maxsize=32)
def frame(path: Path) -> tuple[float, float, float, float, float]:
    """The left and top edge of the page in drawing units, its size in metres, and metres per drawing unit."""
    from bp.facts_models import _bounds  # noqa: PLC0415 - the page frame must match the facts of the agent
    from bp.tools import dxf_plan  # noqa: PLC0415

    plan = dxf_plan.read_dxf(path)
    unit = plan.unit_m or 1.0
    x0, y0, x1, y1 = _bounds(plan)
    x1 = max([x1, *(x + len(text) * height * LETTER for x, height, text in _texts(path))])
    return x0, y1, (x1 - x0) * unit + 2 * PAD_M, (y1 - y0) * unit + 2 * PAD_M, unit


def render(path: Path, side: int) -> bytes | None:
    import ezdxf  # noqa: PLC0415
    from ezdxf import path as paths  # noqa: PLC0415
    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415

    left, top, width_m, height_m, unit = frame(path)
    if width_m <= 2 * PAD_M or height_m <= 2 * PAD_M:
        return None
    scale = side * OVERSAMPLE / max(width_m, height_m)
    size = (max(1, round(width_m * scale)), max(1, round(height_m * scale)))
    image = Image.new("RGB", size, PAPER)
    draw = ImageDraw.Draw(image)

    face = next((f for f in FONTS if os.path.exists(f)), None)  # noqa: PTH110

    def at(x: float, y: float) -> tuple[float, float]:
        return ((x - left) * unit + PAD_M) * scale, ((top - y) * unit + PAD_M) * scale

    def stroke(entity: Any, tone: tuple[int, int, int], weight: float) -> None:  # noqa: ANN401 - a DXF entity
        if entity.dxftype() == "HATCH":
            for part in paths.from_hatch(entity):
                ring = [at(p.x, p.y) for p in part.flattening(0.01 / unit)]
                if len(ring) > 2:
                    draw.polygon(ring, fill=tone)
            return
        if entity.dxftype() in {"TEXT", "MTEXT"}:
            wide = entity.dxftype() == "MTEXT"
            text = entity.plain_text() if wide else entity.dxf.text
            height = float(entity.dxf.get("char_height" if wide else "height", 0.2)) * unit * scale
            where = entity.dxf.insert
            x, y = at(where.x, where.y)
            tall = max(6.0, height * 1.25)
            font = ImageFont.truetype(face, tall) if face else ImageFont.load_default(size=tall)
            draw.text((x, y - height * 1.2), str(text), fill=INK, font=font)
            return
        if entity.dxftype() == "INSERT":
            for child in entity.virtual_entities():
                stroke(child, tone, weight)
            return
        try:
            found = paths.make_path(entity)
        except (TypeError, ValueError):
            return
        line = [at(p.x, p.y) for p in found.flattening(0.01 / unit)]
        if len(line) > 1:
            draw.line(line, fill=tone, width=max(1, round(weight * OVERSAMPLE * side / 2400)), joint="curve")

    entities = list(ezdxf.readfile(str(path)).modelspace())
    for entity in sorted(entities, key=lambda e: e.dxftype() != "HATCH"):
        tone, weight = TONES.get(str(entity.dxf.layer).upper(), ((70, 70, 74), 1.0))
        stroke(entity, tone, weight)
    out = io.BytesIO()
    image.resize((size[0] // OVERSAMPLE, size[1] // OVERSAMPLE), Image.LANCZOS).save(out, "PNG", optimize=True)
    return out.getvalue()
