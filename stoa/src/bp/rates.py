"""How sure a fact is, and its error margin, from measured benchmark results.

Every rate here is a measured share from a tool benchmark (`experiments/tools/*.json`) or a sealed run
(`experiments/LEDGER.md`), summarised in `docs/RESULTS.md`. The comment at each number names its source.
A fact that no benchmark covers gets `unmeasured(...)`: a low confidence and a basis that says so.

Use `Rate` for the confidence and the basis of a fact, and `Margin` for the error margin of a measured value.
Both are frozen and small, so the fact builders of every document kind (sheets, Swiss plans, IFC, DXF, small
rasters) can share them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bp.contract import Frozen

if TYPE_CHECKING:
    from collections.abc import Iterable

UNMEASURED_CONFIDENCE = 0.5


class Rate(Frozen):
    """The confidence of a fact and one plain sentence that says why."""

    confidence: float
    basis: str
    measured: bool = True  # False: no benchmark covers this fact, and the confidence is a rule

    def lowered(self, factor: float, why: str) -> Rate:
        """The same rate with a lower confidence, and the reason added to the basis."""
        return Rate(confidence=round(self.confidence * factor, 3), basis=f"{self.basis}; {why}", measured=self.measured)


class Margin(Frozen):
    """Plus or minus `value`, in the unit of the measured value. `share` of the test items were inside it."""

    value: float
    share: float
    basis: str


def unmeasured(what: str, confidence: float = UNMEASURED_CONFIDENCE) -> Rate:
    """The rate of a fact that no benchmark covers. It says so, and it is low."""
    return Rate(
        confidence=confidence,
        basis=f"no benchmark covers {what}, so this confidence is a rule, not a measurement",
        measured=False,
    )


NOT_GIVEN = Rate(confidence=0.0, basis="the document does not give this value")


def relative(value: float, share_of_value: float, share: float, basis: str, floor: float = 0.0) -> Margin:
    """A margin that is a share of the value, at least `floor` (the rounding of the reading)."""
    return Margin(value=round(max(abs(value) * share_of_value, floor), 4), share=share, basis=basis)


def sum_margin(parts: Iterable[Margin]) -> Margin | None:
    """The margin of a sum of measured values: the margins added.

    The plain sum holds whenever each part is inside its own margin, also when one error (the scale) moves every
    part the same way. It is wider than a quadrature sum of independent errors, so it does not claim too much.
    The share of the sum is the smallest share of a part.
    """
    items = list(parts)
    if not items:
        return None
    basis = items[0].basis if len({m.basis for m in items}) == 1 else "the margins of its parts"
    return Margin(
        value=round(sum(m.value for m in items), 4),
        share=min(m.share for m in items),
        basis=f"the margins of its {len(items)} parts added: {basis}",
    )


# ----------------------------------------------------------------------------- Swiss vector plans (PDF)
# Source: experiments/tools/swiss.json, 833 test floors (dev and val), checked against the DXF and the source data.

SWISS_ROOMS = Rate(
    confidence=0.999, basis="all 22,966 rooms on 833 test floors were found with the right number and name"
)
SWISS_AREA = Rate(confidence=0.999, basis="22,966 test rooms against the CAD source: the largest area error was 0.05%")
SWISS_PRINTED = Rate(
    confidence=0.999,
    basis="6,587 printed room areas on 249 test floors: none differs from the outline by more than 0.6%",
)
SWISS_APARTMENTS = Rate(confidence=0.999, basis="the apartment count was exact on all 833 test floors")
SWISS_DOORS = Rate(confidence=0.999, basis="the door count was exact on all 833 test floors, each place counted once")
SWISS_SCALE = Rate(confidence=0.999, basis="the scale text and the scale bar agreed on 833 of 833 test floors")
SWISS_FIXTURE: dict[str, Rate] = {
    "toilet": Rate(confidence=0.999, basis="the toilet count was exact on all 833 test floors (3,423 toilets)"),
    "washbasin": Rate(confidence=0.999, basis="the washbasin count was exact on all 833 test floors (3,583 basins)"),
    "bathtub": Rate(confidence=0.999, basis="the bathtub count was exact on all 833 test floors (2,309 tubs)"),
    "shower": Rate(confidence=0.999, basis="the shower count was exact on all 833 test floors (590 showers)"),
    # windows vs DXF: exact on 832 of 833 floors (99.88%)
    "window": Rate(confidence=0.998, basis="the window count was exact on 832 of 833 test floors"),
}
SWISS_SIZE = unmeasured("the sizes of fixture and window boxes")
# Relative margin of a Swiss room area: the largest error on 22,966 test rooms was 0.0455%, so 0.05% holds for all.
SWISS_AREA_MARGIN = 0.0005
SWISS_AREA_MARGIN_BASIS = "the largest area error on 22,966 test rooms"
# A printed area and its outline: the largest difference on 6,587 test rooms was 0.57%, p99 0.21%.
SWISS_PRINTED_GAP = 0.0057


def swiss_fixture(kind: str) -> Rate:
    return SWISS_FIXTURE.get(kind) or unmeasured(f"the {kind} symbols of this kind of plan")


def swiss_area_margin(value: float) -> Margin:
    # 0.005 m2 floor: the CAD areas are given to 4 places; the PDF rounds to 2 in the text
    return relative(value, SWISS_AREA_MARGIN, 1.0, SWISS_AREA_MARGIN_BASIS, floor=0.005)


# ----------------------------------------------------------------------------- large raster sheets (USACE, DAF)
# Sources: experiments/tools/raster.json (OCR on 210 Swiss raster sheets) and the sheet runs in LEDGER.md.

SHEET_TEXT = Rate(confidence=0.894, basis="OCR read 89 of 100 room labels right on 210 test sheets")
# printed areas and scales: 80 of 82 right and 0 wrong on the held-out USACE sheets (lock run 20261114-200914-696)
SHEET_PRINTED = Rate(confidence=0.97, basis="printed areas and scales: 80 of 82 right, 0 wrong on 30 held-out sheets")
# door count: right within 3% on 31 of 60 dev sheets (run 20261114-193632-837), 4 of 16 on lock
SHEET_DOOR_COUNT = Rate(
    confidence=0.5, basis="the door count was within 3% on 31 of 60 test sheets, so it is an estimate"
)
SHEET_DOOR = unmeasured("one door leaf alone (only the door count per sheet is checked)")
SHEET_WITNESS = Rate(
    confidence=0.894, basis="a dimension text that OCR read (89 of 100 labels right on 210 test sheets) and its line"
)
SHEET_PERIMETER = unmeasured("wall lengths on sheets")
SHEET_LEAF_WIDTH = unmeasured("door leaf widths on sheets")

# Room areas from the wall lines on large sheets. Source: 130 rooms on the 12 dev USACE sheets that have a scale
# (renders with the printed "NNN SF" removed), measured area against the printed area of the same room. Script
# and output on 15 November 2026:
# `stoa/analysis/sheets/room_margin.py`. Confidence is the share within 5% (the tolerance of the room_area key);
# the margin is the smallest round margin that holds about 9 of 10 rooms of the bucket, with its measured share.
SMALL_ROOM_M2 = 100 * 0.09290304  # 100 sq ft
STRONG_LINES = 5  # dimension lines that agree (as in sheet_plan.STRONG_WITNESSES)
LARGEST_SPREAD = 0.019  # the widest spread of agreeing dimension lines in the benchmark


class RoomBucket(Frozen):
    name: str
    rooms: int  # in the benchmark
    within_5: int  # of those, within 5% of the printed area
    margin: float  # relative
    inside: int  # of those, inside the margin

    def share(self) -> float:
        return round(self.inside / self.rooms, 3)


ROOM_NORMAL = RoomBucket(name="closed, 9 m2 or more, scale from 5 or more dimension lines or from a printed ratio "
                         "and door sizes", rooms=65, within_5=61, margin=0.05, inside=61)  # fmt: skip
ROOM_SMALL = RoomBucket(name="closed and smaller than 9 m2", rooms=22, within_5=17, margin=0.10, inside=20)
ROOM_WEAK_SCALE = RoomBucket(name="closed, scale from 3 or 4 dimension lines", rooms=14, within_5=10, margin=0.25,
                             inside=14)  # fmt: skip
ROOM_DIVIDED = RoomBucket(name="toilets, showers, locker rooms and stairs (stalls and flights split the floor)",
                          rooms=29, within_5=10, margin=0.50, inside=25)  # fmt: skip
# On a scan (the dev twins of `jobs/sheet-scans/make.py`, `sheets-scan` dev, 15 November 2026), blur moves each wall
# face by about a pixel: the error of a small room grows. Rooms under 9 m2 that closed on the scans: 2 of 4 within 5%
# (errors +2.3, -1.2, +7.4 and -8.3%). The room_area tool gives them only as an estimate on a scan.
ROOM_SCAN_SMALL = RoomBucket(name="on a scan, closed and smaller than 9 m2", rooms=4, within_5=2, margin=0.10,
                             inside=4)  # fmt: skip
USER_SCALE_FACTOR = 0.95  # rule: a scale from two points that the user marked; no benchmark measures it


def sheet_room(
    area_m2: float, *, divided: bool, scale_source: str, agreeing: int | None, spread: float | None, scan: bool = False
) -> tuple[Rate, Margin]:
    """The rate and the margin of one room area from the wall lines, from its own evidence."""
    buckets = [ROOM_DIVIDED] if divided else [ROOM_NORMAL]
    if not divided and area_m2 < SMALL_ROOM_M2:
        buckets.append(ROOM_SMALL)
        if scan:
            buckets.append(ROOM_SCAN_SMALL)
    if not divided and scale_source == "dimension lines" and (agreeing or 0) < STRONG_LINES:
        buckets.append(ROOM_WEAK_SCALE)
    worst = min(buckets, key=lambda b: b.within_5 / b.rooms)
    widest = max(buckets, key=lambda b: b.margin)
    confidence = round(worst.within_5 / worst.rooms, 3)
    basis = (f"{worst.within_5} of {worst.rooms} test rooms of this kind ({worst.name}) were within 5% of the "
             "printed area")  # fmt: skip
    margin = widest.margin
    margin_basis = f"{widest.inside} of {widest.rooms} test rooms of this kind ({widest.name}) were inside it"
    if spread is not None and spread > LARGEST_SPREAD:
        # An area goes with the square of the scale: a wider spread of the scale witnesses than the benchmark saw
        # widens the margin by twice the extra spread.
        margin += 2 * (spread - LARGEST_SPREAD)
        margin_basis += f"; widened, because the dimension lines spread {100 * spread:.1f}%"
    rate = Rate(confidence=confidence, basis=basis)
    if scale_source == "user":
        rate = rate.lowered(USER_SCALE_FACTOR, "the scale is from the user, and no benchmark measures that")
    return rate, relative(area_m2, margin, widest.share(), margin_basis, floor=0.01)
