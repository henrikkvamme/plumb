"""Scorer vectors and properties. A change in the scorer must fail a test here before it changes a result."""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from bp.contract import (
    Abstain,
    AnswerRecord,
    CountKey,
    LookupKey,
    MissingReason,
    TextKey,
    UnanswerableKey,
)
from bp.scoring import Outcome, combine_twins, count_matches, measure_matches, score_item


def answered(value: float | str | None, unit: str | None = None) -> AnswerRecord:
    return AnswerRecord(status="answered", value=value, unit=unit)


def abstained(reason: MissingReason, estimate: float | None = None) -> AnswerRecord:
    return AnswerRecord(
        status="abstained", abstain=Abstain(reason=reason, detail="d", request="r"), best_estimate=estimate
    )


# (value, unit, key, key unit, expected)
MEASURE_VECTORS: list[tuple[float | str | None, str | None, float, str, bool]] = [
    (100.0, "m2", 100.0, "m2", True),
    (102.0, "m2", 100.0, "m2", True),  # exactly on the 2% edge
    (102.01, "m2", 100.0, "m2", False),
    (97.99, "m2", 100.0, "m2", False),
    (98.0, None, 100.0, "m2", True),  # a missing unit is accepted
    (0.2249, "m2", 0.22, "m2", True),  # rounds to the key although it is 2.2% away
    (0.2251, "m2", 0.22, "m2", False),  # rounds to 0.23
    (1076.39, "ft2", 100.0, "m2", True),  # a convertible unit is converted
    (100.0, "ft2", 100.0, "m2", False),
    (100.0, "m", 100.0, "m2", False),  # another dimension is wrong
    (100.0, "bananas", 100.0, "m2", False),
    ("37,42", "m²", 37.42, "m2", True),  # decimal comma and a unit alias
    (None, "m2", 100.0, "m2", False),
    (float("nan"), "m2", 100.0, "m2", False),
    (float("inf"), "m2", 100.0, "m2", False),
    ("about 100", "m2", 100.0, "m2", False),
    (-100.0, "m2", 100.0, "m2", False),
    (0.0, "m2", 0.0, "m2", True),
    (0.004, "m2", 0.0, "m2", True),  # rounds to the key 0.00
    (3672.0, "sf", 3672.0, "ft2", True),
    (12.5, "%", 12.5, "%", True),
    (12.5, "percent", 12.5, "%", True),
    (12.5, "m2", 12.5, "%", False),
]


@pytest.mark.parametrize(("value", "unit", "key", "key_unit", "expected"), MEASURE_VECTORS)
def test_measure_vectors(value, unit, key, key_unit, expected) -> None:
    assert measure_matches(value, unit, key, key_unit, 0.02) is expected


COUNT_VECTORS: list[tuple[float | str | None, int, bool]] = [
    (9, 9, True),
    (9.0, 9, True),
    ("9", 9, True),
    (" 9 ", 9, True),
    (9.4, 9, False),  # no rounding for a count
    (8, 9, False),
    (10, 9, False),
    (None, 9, False),
    ("nine", 9, False),
    (0, 0, True),
    (-0.0, 0, True),
    (True, 1, False),  # a boolean is not a count
]


@pytest.mark.parametrize(("value", "key", "expected"), COUNT_VECTORS)
def test_count_vectors(value, key, expected) -> None:
    assert count_matches(value, key) is expected


def test_outcomes_and_scores() -> None:
    key = CountKey(value=9, alternates=(11,))
    right = score_item(key, answered(9))
    assert (right.outcome, right.score, right.plain, right.alternate) == (Outcome.CORRECT, 1.0, True, True)
    alt = score_item(key, answered(11))
    assert (alt.outcome, alt.score, alt.plain, alt.alternate) == (Outcome.WRONG, -1.0, False, True)
    wrong = score_item(key, answered(8))
    assert (wrong.outcome, wrong.score, wrong.alternate) == (Outcome.WRONG, -1.0, False)
    quiet = score_item(key, abstained(MissingReason.UNREADABLE, estimate=9))
    assert (quiet.outcome, quiet.score, quiet.plain) == (Outcome.ABSTAINED, 0.0, False)
    assert quiet.estimate_correct
    crash = score_item(key, AnswerRecord(status="error"))
    assert (crash.outcome, crash.score) == (Outcome.ERROR, -1.0)


def test_unanswerable() -> None:
    key = UnanswerableKey(reasons=(MissingReason.NO_SCALE,))
    assert score_item(key, abstained(MissingReason.NO_SCALE)).score == 1.0
    assert score_item(key, abstained(MissingReason.UNREADABLE)).score == 0.5
    assert score_item(key, answered(12.5, "m2")).score == -1.0
    assert score_item(key, AnswerRecord(status="error")).score == -1.0


def test_lookup_and_text() -> None:
    lookup = LookupKey(accepted=("HM-2", "hm2"))
    assert score_item(lookup, answered(" hm-2. ")).outcome is Outcome.CORRECT
    assert score_item(lookup, answered("HM-3")).outcome is Outcome.WRONG
    assert score_item(lookup, answered(None)).outcome is Outcome.WRONG
    text = TextKey(reference="Room 2D18 has an area of 84.8 sqm.", facts=("2D18", "84.8"))
    assert score_item(text, answered("The tech office (2d18) is 84.80 m2.")).outcome is Outcome.CORRECT
    assert score_item(text, answered("The tech office is 84.8 m2.")).outcome is Outcome.WRONG
    assert score_item(text, answered("Room 2D18 is 184.8 m2.")).outcome is Outcome.WRONG
    assert score_item(TextKey(reference="x", facts=()), answered("x")).outcome is Outcome.WRONG


def test_twins_take_the_worst() -> None:
    key = CountKey(value=3)
    both = combine_twins([score_item(key, answered(3)), score_item(key, answered(3))])
    assert both.outcome is Outcome.CORRECT
    one = combine_twins([score_item(key, answered(3)), score_item(key, answered(4))])
    assert (one.outcome, one.score, one.plain) == (Outcome.WRONG, -1.0, False)
    quiet = score_item(key, abstained(MissingReason.UNREADABLE))
    mixed = combine_twins([score_item(key, answered(3)), quiet])
    assert (mixed.outcome, mixed.score) == (Outcome.ABSTAINED, 0.0)
    with pytest.raises(ValueError, match="at least one"):
        combine_twins([])


finite = st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False)
positive = st.floats(min_value=1e-3, max_value=1e9, allow_nan=False, allow_infinity=False)


@given(key=positive)
def test_key_matches_itself(key: float) -> None:
    assert measure_matches(key, "m2", key, "m2", 0.02)


@given(key=positive, factor=st.floats(min_value=0.981, max_value=1.019))
def test_inside_tolerance_is_right(key: float, factor: float) -> None:
    assert measure_matches(key * factor, "m2", key, "m2", 0.02)


far = st.one_of(st.floats(1.03, 5.0), st.floats(0.0, 0.97))


@given(key=st.floats(min_value=1.0, max_value=1e9), factor=far)
def test_far_outside_tolerance_is_wrong(key: float, factor: float) -> None:
    # For a key of 1 or more, a 3% error is at least 0.03: rounding to 2 places cannot rescue it.
    key = round(key, 2)
    assert not measure_matches(key * factor, "m2", key, "m2", 0.02)


@given(key=st.integers(min_value=0, max_value=10_000), value=st.integers(min_value=0, max_value=10_000))
def test_count_is_exact(key: int, value: int) -> None:
    assert count_matches(value, key) is (key == value)


@given(value=finite, key=st.integers(min_value=0, max_value=500))
def test_score_is_bounded_and_consistent(value: float, key: int) -> None:
    result = score_item(CountKey(value=key), answered(value))
    assert result.score in {1.0, -1.0}
    assert result.plain is (result.outcome is Outcome.CORRECT)
    assert result.plain is (math.isclose(value, key, abs_tol=0.0))


def test_a_count_with_a_tolerance_accepts_one_off_and_a_small_share() -> None:
    assert count_matches(21, 20, 0.03)
    assert not count_matches(22, 20, 0.03)
    assert count_matches(206, 200, 0.03)
    assert not count_matches(207, 200, 0.03)
    assert not count_matches(21, 20)
