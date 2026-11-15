"""Symbol instances read from the vectors of a Revit sheet printed to PDF.

A Revit PDF printed through PScript has no blocks and no layers. But Revit prints one element after the other, so
the paths of one family instance (a toilet, a sink, a window) come as one run of consecutive drawings. `groups`
cuts the drawing stream of a page into such runs: a new drawing joins the open run when it lies close to it and
the run stays small.

Each run gets a signature that does not change with position or a turn by a right angle: the number of drawings and
path items, the two sides of its box and the length of its lines, in inches of the building. All instances of one
family type in one view style have the same signature. `catalog.py` counts signatures over all pages, and a person
names the frequent ones by eye (`classes.json`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pymupdf

MAX_SIDE_FT = 9.0  # a fixture or window is smaller; a run that grows past this is cut
JOIN_FT = 0.35  # a drawing joins the run when its box is this close to the box of the run
INK = 0.6  # a colour component above this on every channel is paper or a light hatch: not part of a symbol


@dataclass
class Group:
    rect: pymupdf.Rect  # page points
    drawings: int
    items: int
    length: float  # page points of line
    first: int  # seqno of the first drawing

    def signature(self, pt_ft: float) -> tuple:
        """(drawings, items, short side, long side, length) with the sizes in inches of the building."""
        inch = pt_ft / 12
        w, h = self.rect.width / inch, self.rect.height / inch
        return (self.drawings, self.items, round(min(w, h)), round(max(w, h)), round(self.length / inch / 2) * 2)


def _length(drawing: dict) -> float:
    total = 0.0
    for item in drawing["items"]:
        if item[0] == "l":
            total += math.dist(item[1], item[2])
        elif item[0] == "c":
            total += math.dist(item[1], item[4])
        elif item[0] == "re":
            total += 2 * (item[1].width + item[1].height)
        elif item[0] == "qu":
            q = item[1]
            total += math.dist(q.ul, q.ur) + math.dist(q.ur, q.lr) + math.dist(q.lr, q.ll) + math.dist(q.ll, q.ul)
    return total


def _ink(drawing: dict) -> bool:
    """True for a stroked drawing in dark ink. Fills are wall poche or masks: they are not symbol lines."""
    if drawing.get("type") not in ("s", "fs"):
        return False
    colour = drawing.get("color")
    return colour is None or min(colour) <= INK


def groups(page: pymupdf.Page, ft_per_in: float, drawings: list[dict] | None = None) -> list[Group]:
    """The runs of consecutive dark stroked drawings of the page, each smaller than `MAX_SIDE_FT`."""
    pt_ft = 72 / ft_per_in
    join, limit = JOIN_FT * pt_ft, MAX_SIDE_FT * pt_ft
    out: list[Group] = []
    run: Group | None = None
    for drawing in drawings if drawings is not None else page.get_drawings():
        if not _ink(drawing):
            continue
        r = pymupdf.Rect(drawing["rect"])
        if r.width > limit or r.height > limit:
            if run:
                out.append(run)
            run = None
            continue
        if run is not None:
            near = pymupdf.Rect(run.rect.x0 - join, run.rect.y0 - join, run.rect.x1 + join, run.rect.y1 + join)
            both = run.rect | r
            if near.intersects(r) or near.contains(r):
                if both.width <= limit and both.height <= limit:
                    run.rect = both
                    run.drawings += 1
                    run.items += len(drawing["items"])
                    run.length += _length(drawing)
                    continue
            out.append(run)
        run = Group(r, 1, len(drawing["items"]), _length(drawing), drawing.get("seqno", 0))
    if run:
        out.append(run)
    return out
