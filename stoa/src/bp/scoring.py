"""The scorer. Pure functions, no I/O.

Rules (EVALUATION.md section 5):
- a count is right when it is the exact integer;
- a measure is right within the tolerance of the key, or when it rounds to the printed key;
- a lookup is right when the normalised answer equals an accepted string;
- a text answer is right when it holds every key fact;
- an unanswerable question is right when the solver abstains.
The item score is +1 for right, 0 for an abstention on an answerable question, -1 for a wrong answer.
"""

from __future__ import annotations

import math
import re
import unicodedata
from enum import StrEnum

from bp.contract import (
    AnswerRecord,
    CountKey,
    Dimension,
    Frozen,
    Key,
    LookupKey,
    MeasureKey,
    TextKey,
    UnanswerableKey,
)


class Outcome(StrEnum):
    CORRECT = "correct"
    WRONG = "wrong"
    ABSTAINED = "abstained"  # the question had an answer
    ABSTAIN_RIGHT = "abstain_right"  # no answer exists, and the reason is one of the key reasons
    ABSTAIN_OTHER = "abstain_other"  # no answer exists, the solver abstained for another reason
    ERROR = "error"


SCORE: dict[Outcome, float] = {
    Outcome.CORRECT: 1.0,
    Outcome.WRONG: -1.0,
    Outcome.ABSTAINED: 0.0,
    Outcome.ABSTAIN_RIGHT: 1.0,
    Outcome.ABSTAIN_OTHER: 0.5,
    Outcome.ERROR: -1.0,
}


class ItemScore(Frozen):
    outcome: Outcome
    score: float
    plain: bool  # counts as right when an abstention is simply "not right"
    alternate: bool  # right under a second defensible convention
    estimate_correct: bool  # the best estimate of an abstention was right
    detail: str = ""


# unit -> (dimension, factor to SI)
_UNITS: dict[str, tuple[Dimension, float]] = {
    "m": (Dimension.LENGTH, 1.0),
    "mm": (Dimension.LENGTH, 0.001),
    "cm": (Dimension.LENGTH, 0.01),
    "ft": (Dimension.LENGTH, 0.3048),
    "in": (Dimension.LENGTH, 0.0254),
    "m2": (Dimension.AREA, 1.0),
    "mm2": (Dimension.AREA, 1e-6),
    "cm2": (Dimension.AREA, 1e-4),
    "ft2": (Dimension.AREA, 0.09290304),
    "m3": (Dimension.VOLUME, 1.0),
    "ft3": (Dimension.VOLUME, 0.028316846592),
    "%": (Dimension.RATIO, 1.0),
}

_UNIT_ALIASES: dict[str, str] = {
    "m²": "m2", "sqm": "m2", "sq m": "m2", "m^2": "m2", "square metres": "m2", "square meters": "m2",
    "ft²": "ft2", "sf": "ft2", "sqft": "ft2", "sq ft": "ft2", "ft^2": "ft2", "square feet": "ft2",
    "m³": "m3", "m^3": "m3", "cubic metres": "m3", "cubic meters": "m3", "ft³": "ft3",
    "meter": "m", "metre": "m", "meters": "m", "metres": "m", "feet": "ft", "foot": "ft",
    "percent": "%", "pct": "%", "millimetres": "mm", "millimeters": "mm", "inch": "in", "inches": "in",
}  # fmt: skip


def canonical_unit(unit: str | None) -> str | None:
    """Return the canonical unit name, or None when the unit is unknown or absent."""
    if unit is None:
        return None
    u = unit.strip().lower()
    u = _UNIT_ALIASES.get(u, u)
    return u if u in _UNITS else None


def convert(value: float, unit: str, to: str) -> float | None:
    """Convert between two canonical units. None when the dimensions differ."""
    src, dst = _UNITS[unit], _UNITS[to]
    if src[0] is not dst[0]:
        return None
    return value * src[1] / dst[1]


def _as_number(value: float | str | None) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    try:
        parsed = float(value.strip().replace(",", "."))
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def count_matches(value: float | str | None, key: int, tolerance: float = 0.0) -> bool:
    """Equal to the key. With a tolerance: within max(1, tolerance * key), for a key that is a measurement itself."""
    number = _as_number(value)
    if number is None:
        return False
    slack = max(1.0, tolerance * key) if tolerance > 0 else 0.0
    return abs(number - float(key)) <= slack


def measure_matches(
    value: float | str | None,
    unit: str | None,
    key: float,
    key_unit: str,
    tolerance: float,
    decimals: int = 2,
) -> bool:
    """Right within the tolerance, or equal to the key after rounding to `decimals` places.

    The second rule exists because some keys are rounded more coarsely than the tolerance (0.22 for 0.2249).
    Stoa prints its keys with 2 decimals, so 2 is the default. A missing unit is accepted. A unit of another
    dimension is wrong.
    """
    number = _as_number(value)
    if number is None:
        return False
    want = canonical_unit(key_unit)
    if unit is not None and unit.strip():
        have = canonical_unit(unit)
        if have is None:
            return False
        if want is not None and have != want:
            converted = convert(number, have, want)
            if converted is None:
                return False
            number = converted
    if abs(number - key) <= tolerance * abs(key):
        return True
    return round(number, decimals) == round(key, decimals)


def normalise_text(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    folded = re.sub(r"\s+", " ", folded)
    return folded.strip(" .,:;!?\"'`()[]")


_NUMBER = re.compile(r"-?\d+(?:[.,]\d+)?")


def numbers(text: str) -> list[float]:
    """Every number in a text, with a decimal point or a decimal comma."""
    return [float(m.group().replace(",", ".")) for m in _NUMBER.finditer(text)]


def fact_present(fact: str, answer: str) -> bool:
    """A number fact matches any equal number in the answer. Other facts match as normalised text."""
    fact_number = _as_number(fact)
    if fact_number is not None:
        return any(math.isclose(n, fact_number, rel_tol=1e-9, abs_tol=1e-9) for n in numbers(answer))
    return normalise_text(fact) in normalise_text(answer)


def _value_matches(value: float | str | None, unit: str | None, key: Key) -> tuple[bool, bool]:
    """Return (right, right under an alternate convention)."""
    if isinstance(key, CountKey):
        return count_matches(value, key.value, key.tolerance), any(count_matches(value, alt) for alt in key.alternates)
    if isinstance(key, MeasureKey):
        main = measure_matches(value, unit, key.value, key.unit, key.tolerance, key.decimals)
        alt = any(measure_matches(value, unit, a, key.unit, key.tolerance, key.decimals) for a in key.alternates)
        return main, alt
    if isinstance(key, LookupKey):
        answer = normalise_text(str(value)) if value is not None else ""
        return answer != "" and answer in {normalise_text(a) for a in key.accepted}, False
    if isinstance(key, TextKey):
        answer = str(value) if value is not None else ""
        return bool(key.facts) and all(fact_present(f, answer) for f in key.facts), False
    return False, False


def score_item(key: Key, record: AnswerRecord) -> ItemScore:
    """Score one answer against one key."""
    if record.status == "error":
        return ItemScore(outcome=Outcome.ERROR, score=SCORE[Outcome.ERROR], plain=False, alternate=False,
                         estimate_correct=False)  # fmt: skip

    if isinstance(key, UnanswerableKey):
        if record.status == "abstained":
            right_reason = record.abstain is not None and record.abstain.reason in key.reasons
            outcome = Outcome.ABSTAIN_RIGHT if right_reason else Outcome.ABSTAIN_OTHER
            return ItemScore(outcome=outcome, score=SCORE[outcome], plain=True, alternate=False,
                             estimate_correct=False)  # fmt: skip
        return ItemScore(outcome=Outcome.WRONG, score=SCORE[Outcome.WRONG], plain=False, alternate=False,
                         estimate_correct=False, detail="answered a question that has no answer")  # fmt: skip

    if record.status == "abstained":
        est, est_alt = _value_matches(record.best_estimate, record.unit, key)
        return ItemScore(outcome=Outcome.ABSTAINED, score=SCORE[Outcome.ABSTAINED], plain=False,
                         alternate=est_alt, estimate_correct=est)  # fmt: skip

    right, alt = _value_matches(record.value, record.unit, key)
    outcome = Outcome.CORRECT if right else Outcome.WRONG
    return ItemScore(outcome=outcome, score=SCORE[outcome], plain=right, alternate=right or alt,
                     estimate_correct=False)  # fmt: skip


def combine_twins(scores: list[ItemScore]) -> ItemScore:
    """An item with translations is right only when every translation is right. The worst outcome wins."""
    if not scores:
        msg = "an item needs at least one score"
        raise ValueError(msg)
    worst = min(scores, key=lambda s: s.score)
    return ItemScore(
        outcome=worst.outcome,
        score=worst.score,
        plain=all(s.plain for s in scores),
        alternate=all(s.alternate for s in scores),
        estimate_correct=all(s.estimate_correct for s in scores),
        detail=worst.detail,
    )
