"""A scanned sheet: the skew, the map back to the original pixels and the ink of thin grey lines."""

from __future__ import annotations

import cv2
import numpy as np

from bp import rates
from bp.tools import sheet_geometry, sheet_scan


def _drawing(size: int = 1600) -> np.ndarray:
    """White paper with long level and plumb lines, 1 px wide, like the line work of a sheet."""
    gray = np.full((size, size), 255, np.uint8)
    for y in range(200, size - 200, 150):
        gray[y, 150 : size - 150] = 0
    for x in range(200, size - 200, 220):
        gray[150 : size - 150, x] = 0
    return gray


def _scanned(gray: np.ndarray, angle: float) -> np.ndarray:
    height, width = gray.shape
    turn = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    out = cv2.warpAffine(gray, turn, (width, height), flags=cv2.INTER_LINEAR, borderValue=255)
    out = (40 + out.astype(np.float32) * (230 - 40) / 255).astype(np.uint8)
    out = cv2.GaussianBlur(out, (0, 0), 1.2)
    noise = np.random.default_rng(1).normal(0, 7, out.shape)
    return np.clip(out + noise, 0, 255).astype(np.uint8)


def test_a_render_is_not_a_scan_and_stays_as_it_is() -> None:
    gray = _drawing()
    up = sheet_scan.upright(np.stack([gray] * 3, axis=2), sheet_geometry.DARK)
    assert not up.scan
    assert up.angle == 0.0
    assert np.array_equal(up.dark, gray < sheet_geometry.DARK)


def test_the_skew_of_a_scan_is_found_and_undone() -> None:
    # cv2 turns counterclockwise on the screen for a positive angle: the lines then rise to the right
    scan = _scanned(_drawing(), 1.0)
    up = sheet_scan.upright(np.stack([scan] * 3, axis=2), sheet_geometry.DARK)
    assert up.scan
    assert abs(up.angle + 1.0) <= 0.03
    # a level line of the upright ink is one row: its dark pixels lie within 3 rows over 1,000 px
    rows = np.flatnonzero(up.dark[:, up.dark.shape[1] // 2 - 500 : up.dark.shape[1] // 2 + 500].sum(axis=1) > 900)
    assert len(rows) >= 5


def test_points_go_back_to_the_original_pixels() -> None:
    scan = _scanned(_drawing(), -2.0)
    up = sheet_scan.upright(np.stack([scan] * 3, axis=2), sheet_geometry.DARK)
    for x, y in ((0.0, 0.0), (800.0, 120.0), (1599.0, 1599.0)):
        back = up.to_original(*up.to_upright(x, y))
        assert abs(back[0] - x) < 1e-6
        assert abs(back[1] - y) < 1e-6


def test_a_thin_grey_line_on_a_scan_is_ink() -> None:
    scan = _scanned(_drawing(), 0.0)
    assert scan[200, 800] > sheet_geometry.DARK  # a fixed ink level misses the blurred line
    ink = sheet_scan.scan_ink(scan)
    assert ink[199:202, 300:1300].any(axis=0).mean() > 0.98
    assert ink[260:330, 430:630].mean() < 0.01  # the paper between the lines stays paper


def test_a_small_room_on_a_scan_gets_the_scan_margin() -> None:
    clean_rate, clean_margin = rates.sheet_room(7.0, divided=False, scale_source="printed scale and doors",
                                                agreeing=None, spread=None)  # fmt: skip
    scan_rate, scan_margin = rates.sheet_room(7.0, divided=False, scale_source="printed scale and doors",
                                              agreeing=None, spread=None, scan=True)  # fmt: skip
    assert scan_rate.confidence == 0.5
    assert scan_rate.confidence < clean_rate.confidence
    assert scan_margin == clean_margin  # both 10%: the small-room margin holds the 4 scanned rooms
    big, _ = rates.sheet_room(30.0, divided=False, scale_source="printed scale and doors", agreeing=None,
                              spread=None, scan=True)  # fmt: skip
    assert big.confidence == rates.sheet_room(30.0, divided=False, scale_source="printed scale and doors",
                                              agreeing=None, spread=None)[0].confidence  # fmt: skip
