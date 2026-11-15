"""A large sheet that was scanned from paper: is it a scan, how much is it turned, and where is its ink.

A render of a vector PDF has white paper and crisp ink. A scan has grey paper, noise, blur and a small skew. A thin
line (a dimension line is 1 px wide on a 300 dpi render) then is a soft grey band, lighter than a fixed ink level,
and a line that is turned by 1 degree leaves its pixel row every 57 px. The functions here undo both: they find the
skew from the long lines, turn the image upright, and mark ink relative to the local paper level. The map back to
the original pixels stays, so each point that a tool reports is in the pixels of the image that the user gave.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

PAPER_WHITE = 250  # a render has white paper: most of its pixels are at or above this
WHITE_SHARE = 0.5
SKEW_MAX_DEG = 3.0  # a scan turned more than this is not searched
SKEW_MIN_DEG = 0.02  # a line of 3,000 px at this angle stays within 1 px of its row
SKEW_POINTS = 600_000  # ink pixels sampled for the skew search
INK_SHARE = 0.18  # on a scan: ink is darker than the paper by this share of the paper-to-ink contrast
LINE_SMOOTH = 9  # px: the noise is smoothed along each axis, so a thin line on that axis keeps its contrast
PAPER_BLOCK = 16  # px: the paper level is found on blocks of this size
MIN_CONTRAST = 40  # grey levels between paper and ink: less is an empty image
WALL_SHARE = 0.4  # on a levelled scan, a wall pixel is darker than this share of the way from the ink to the paper


def is_scan(gray: np.ndarray) -> bool:
    """True when the paper is not white: a scan or a photo of paper, not a render."""
    sample = gray[::7, ::7]
    return float((sample >= PAPER_WHITE).mean()) < WHITE_SHARE


def skew_deg(dark: np.ndarray) -> float:
    """The angle in degrees by which the lines of the drawing are turned (positive: clockwise on the screen).

    The rows of an upright drawing hold long runs of ink, so the squared row sums of the ink peak at the right
    angle. Vertical lines give the same peak in the columns. A coarse search, then a fine one.
    """
    ys, xs = np.nonzero(dark)
    if len(xs) < 1000:
        return 0.0
    if len(xs) > SKEW_POINTS:
        pick = np.random.default_rng(0).choice(len(xs), SKEW_POINTS, replace=False)
        xs, ys = xs[pick], ys[pick]
    xs, ys = xs.astype(np.float64), ys.astype(np.float64)
    span = int(max(dark.shape) * 1.2)

    def score(angle: float) -> float:
        t = math.tan(math.radians(angle))
        rows = np.bincount(np.round(ys - xs * t).astype(np.int64) + span, minlength=3 * span)
        cols = np.bincount(np.round(xs + ys * t).astype(np.int64) + span, minlength=3 * span)
        return float((rows.astype(np.float64) ** 2).sum() + (cols.astype(np.float64) ** 2).sum())

    def peak(angles: np.ndarray) -> float:
        # Short lines give a flat top: several angles put each line in one row. The middle of the top is the angle.
        scores = np.array([score(float(a)) for a in angles])
        top = angles[scores >= scores.max() * (1 - 1e-9)]
        return float(top.mean())

    best = peak(np.arange(-SKEW_MAX_DEG, SKEW_MAX_DEG + 1e-9, 0.1))
    best = peak(np.arange(best - 0.1, best + 0.1 + 1e-9, 0.01))
    return round(best, 3)


@dataclass(frozen=True)
class Upright:
    """The ink of a sheet, turned so that its lines lie on the axes, with the map back to the original pixels."""

    dark: np.ndarray  # True where there is ink, in upright pixels
    angle: float  # degrees that the drawing was turned; 0 when it was used as it is
    scan: bool
    forward: np.ndarray  # 2x3: original pixels to upright pixels

    def to_upright(self, x: float, y: float) -> tuple[float, float]:
        m = self.forward
        return (m[0, 0] * x + m[0, 1] * y + m[0, 2], m[1, 0] * x + m[1, 1] * y + m[1, 2])

    def to_original(self, x: float, y: float) -> tuple[float, float]:
        m = self.forward
        dx, dy = x - m[0, 2], y - m[1, 2]
        return (m[0, 0] * dx + m[1, 0] * dy, m[0, 1] * dx + m[1, 1] * dy)  # the inverse of a rotation is its transpose


def _turn(gray: np.ndarray, angle: float) -> tuple[np.ndarray, np.ndarray]:
    """The image turned by `angle` degrees so that a line at that angle is level, on a canvas that holds it all."""
    height, width = gray.shape
    a = math.radians(angle)
    c, s = math.cos(a), math.sin(a)
    new_w = round(width * abs(c) + height * abs(s))
    new_h = round(width * abs(s) + height * abs(c))
    # x' = c x + s y + tx, y' = -s x + c y + ty: a point on y = y0 + x tan(a) goes to a constant y'
    cx, cy = width / 2, height / 2
    forward = np.array([[c, s, new_w / 2 - (c * cx + s * cy)], [-s, c, new_h / 2 - (-s * cx + c * cy)]])
    turned = cv2.warpAffine(gray, forward, (new_w, new_h), flags=cv2.INTER_LINEAR, borderValue=255)
    return turned, forward


def _paper_and_ink(gray: np.ndarray) -> tuple[np.ndarray, float]:
    """The paper level at each pixel (it can vary over a scan) and the ink level of the sheet."""
    small = cv2.resize(gray, (max(gray.shape[1] // PAPER_BLOCK, 1), max(gray.shape[0] // PAPER_BLOCK, 1)),
                       interpolation=cv2.INTER_AREA)  # fmt: skip
    paper_small = cv2.dilate(small, np.ones((5, 5), np.uint8))  # the lightest block nearby is paper
    paper = cv2.resize(paper_small, (gray.shape[1], gray.shape[0]), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    return paper, float(np.percentile(gray[::5, ::5], 0.5))


def levelled(gray: np.ndarray) -> np.ndarray:
    """The scan with its paper at 255 and its ink at 0, and the noise smoothed: a wall is solid ink in its core.

    Blur joins two thin lines a few pixels apart (a door leaf, a tick, a counter edge) to one grey band. That band
    is never as dark as the ink of a wall, so a level near the ink keeps the walls and drops the bands.
    """
    paper, ink = _paper_and_ink(gray)
    smooth = cv2.GaussianBlur(gray, (0, 0), 1.0).astype(np.float32)
    share = (smooth - ink) / np.maximum(paper - ink, MIN_CONTRAST)
    return np.clip(share * 255, 0, 255).astype(np.uint8)


def scan_ink(gray: np.ndarray) -> np.ndarray:
    """Ink on a scan: darker than the local paper by a share of the contrast, with the noise smoothed along each axis.

    A thin level line smoothed along its own row keeps its full contrast, while the noise drops by a factor of 3.
    """
    paper, ink = _paper_and_ink(gray)
    contrast = np.maximum(paper - ink, MIN_CONTRAST)
    level = paper - INK_SHARE * contrast
    along_rows = cv2.blur(gray, (LINE_SMOOTH, 1)).astype(np.float32)
    along_cols = cv2.blur(gray, (1, LINE_SMOOTH)).astype(np.float32)
    return (along_rows < level) | (along_cols < level)


def upright(rgb: np.ndarray, dark_level: int) -> Upright:
    """The ink of the sheet, upright. On a render the ink is every channel below `dark_level`, as before."""
    gray = rgb.max(axis=2) if rgb.ndim == 3 else rgb
    gray = np.ascontiguousarray(gray)
    scan = is_scan(gray)
    dark = scan_ink(gray) if scan else gray < dark_level
    angle = skew_deg(dark[::2, ::2])  # half resolution is enough to find the angle, and 4 times faster
    identity = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    if abs(angle) < SKEW_MIN_DEG:
        return Upright(dark, 0.0, scan, identity)
    turned, forward = _turn(gray, angle)
    dark = scan_ink(turned) if scan else turned < dark_level
    return Upright(dark, angle, scan, forward)
