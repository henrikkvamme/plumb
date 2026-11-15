"""Door swings and room areas on a drawn plan."""

from __future__ import annotations

import cv2
import numpy as np

from bp.tools import sheet_rooms

PPM = 100.0


def plan() -> np.ndarray:
    """A room of 5 m x 4 m with wall lines, and one 0.9 m door in the bottom wall that opens into the room."""
    gray = np.full((1200, 1600), 255, np.uint8)
    cv2.rectangle(gray, (200, 200), (700, 600), 0, 6)
    cv2.line(gray, (404, 600), (490, 600), 255, 12)  # the door opening
    cv2.line(gray, (400, 600), (400, 510), 0, 3)  # the open leaf
    cv2.ellipse(gray, (400, 600), (90, 90), 0, 270, 360, 0, 2)  # the swing
    return gray


def test_one_door_swing_is_found_at_its_hinge() -> None:
    swings = sheet_rooms.door_swings(plan(), PPM)

    assert len(swings) == 1
    assert abs(swings[0].centre[0] - 400) < 4
    assert abs(swings[0].centre[1] - 600) < 4
    assert abs(swings[0].radius_px - 90) < 4


def test_room_area_closes_the_door_opening() -> None:
    gray = plan()
    swings = sheet_rooms.door_swings(gray, PPM)
    walls = sheet_rooms.wall_barriers(sheet_rooms.room_barriers(gray, swings), PPM)

    room = sheet_rooms.room_at(walls, (430, 380, 480, 400), PPM)

    assert room is not None
    assert abs(room.area_px / PPM**2 - 20.0) < 0.6


def test_open_room_gives_no_area() -> None:
    gray = plan()
    cv2.line(gray, (700, 250), (700, 550), 255, 12)  # a 3 m hole in the right wall
    walls = sheet_rooms.wall_barriers(sheet_rooms.room_barriers(gray, []), PPM)

    assert sheet_rooms.room_at(walls, (430, 380, 480, 400), PPM) is None


def test_printed_scale_needs_doors_of_a_common_size() -> None:
    assert sheet_rooms.scale_from_doors(plan(), 100) is None  # one door does not prove a resolution
