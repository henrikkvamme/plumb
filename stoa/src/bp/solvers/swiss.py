"""A thin solver for Swiss Dwellings floor plan sheets (vector PDF).

`ingest` reads the page once with `bp.tools.swiss_plan` and checks that the page is a sheet of this kind. It never
fails: on any other document every question abstains with the reason "unsupported". `ask` parses the question
(English, German, French, Italian) into an intent and calls one query of the tool. A query with a warning, an
intent that the parser cannot place, or a value that is missing gives an abstention, because a wrong answer
costs more than no answer.
"""

from __future__ import annotations

import re
import time
from typing import Literal

from bp.contract import (
    Abstain,
    AnswerRecord,
    Calibration,
    Evidence,
    Frozen,
    IngestReport,
    MissingReason,
    Question,
    Step,
)
from bp.tools import swiss_plan as sp
from bp.tools.pdf_text import page_count, read_page

Intent = Literal[
    "count_label", "apartments", "doors", "windows", "toilets", "washbasins", "bathtubs", "showers",
    "area_room", "area_label", "area_total", "area_apartment",
]  # fmt: skip


class Parsed(Frozen):
    intent: Intent
    room: str | None = None
    label: str | None = None
    apartment: str | None = None


# ----------------------------------------------------------------------------- question parser

_COUNT = re.compile(r"^\W*(how many|wie viele|combien|quant[eia])\b", re.IGNORECASE)
_AREA = re.compile(r"area|fläche|surface|superficie|m²|\bm2\b", re.IGNORECASE)
_TOTAL = re.compile(r"numbered|nummeriert|numérot|numerat|indoor|innenr|intérieur|intern[ie]", re.IGNORECASE)
_ROOM_NUMBER = re.compile(r"(?<![\w.])((?:U\d+\.)?\d+\.\d+|U\d+\.\d+)(?![\w.])")
_ROOM_WORD = re.compile(r"\b(room|raum|pièce|piece|locale|stanza|vano)\b", re.IGNORECASE)
_APARTMENT = re.compile(
    r"(?i:apartment|flat|unit|wohnung|whg\.?|appartement|appartamento|app\.?|logement)\s+([A-Z]{1,2})\b"
)
_QUOTES = (
    re.compile(r"«\s*(.+?)\s*»"),
    re.compile(r"“\s*(.+?)\s*”"),
    re.compile(r"„\s*(.+?)\s*[“”]"),
    re.compile(r"\u2018\s*(.+?)\s*\u2019"),
    re.compile(r"(?:^|[\s(])\"(.+?)\"(?=[\s).,?!]|$)"),
    re.compile(r"(?:^|[\s(])'(.+)'(?=[\s).,?!]|$)"),
)
_OBJECTS: dict[Intent, re.Pattern[str]] = {
    "apartments": re.compile(
        r"apartment|residential unit|wohnung|appartement|logement|appartament|unità abitativ", re.IGNORECASE
    ),
    "doors": re.compile(r"\bdoors?\b|tür|\bportes?\b|\bporta\b", re.IGNORECASE),
    "windows": re.compile(r"window|fenster|fenêtre|finestr", re.IGNORECASE),
    "toilets": re.compile(r"toilet|\bwcs?\b", re.IGNORECASE),
    "washbasins": re.compile(r"wash ?basin|lavabo|lavabi|waschbecken|lavandin", re.IGNORECASE),
    "bathtubs": re.compile(r"bath ?tub|badewanne|baignoire|vasch", re.IGNORECASE),
    "showers": re.compile(r"shower|dusche|douche|docc", re.IGNORECASE),
}


def quoted_label(text: str) -> str | None:
    for pattern in _QUOTES:
        match = pattern.search(text)
        if match:
            return sp.norm_label(match.group(1))
    return None


def parse_question(text: str) -> Parsed | str:  # noqa: PLR0911 - one return per intent
    """The intent of a question, or a string that says why it has none."""
    clean = sp.norm_label(text)
    label = quoted_label(clean)
    if _COUNT.search(clean):
        if label is not None:
            return Parsed(intent="count_label", label=label)
        hits = [intent for intent, pattern in _OBJECTS.items() if pattern.search(clean)]
        if len(hits) == 1:
            return Parsed(intent=hits[0])
        return f"count of {' or '.join(hits) or 'an object I do not know'}"
    if _AREA.search(clean):
        apartment = _APARTMENT.search(clean)
        number = _ROOM_NUMBER.search(clean)
        if apartment and not number:
            return Parsed(intent="area_apartment", apartment=apartment.group(1))
        if number and _ROOM_WORD.search(clean) and not apartment:
            return Parsed(intent="area_room", room=number.group(1), label=label)
        if label is not None and not number and not apartment:
            return Parsed(intent="area_label", label=label)
        if _TOTAL.search(clean) and label is None and not number and not apartment:
            return Parsed(intent="area_total")
        return "an area question that I cannot place"
    return "a question that is not a count or an area"


# ----------------------------------------------------------------------------- solver


def _abstain(reason: MissingReason, detail: str, request: str, estimate: float | None = None) -> AnswerRecord:
    return AnswerRecord(
        status="abstained",
        abstain=Abstain(reason=reason, detail=detail[:300], request=request),
        best_estimate=estimate,
    )


class SwissSolver:
    name = "swiss"

    def __init__(self) -> None:
        self.plan: sp.SwissPlan | None = None
        self.why_not = "not ingested"

    def ingest(self, path: str) -> IngestReport:
        started = time.perf_counter()
        try:
            pages = page_count(path)
            if pages != 1:
                self.why_not = "not a one-page PDF" if pages else "not a PDF"
            else:
                page = read_page(path)
                detection = sp.detect(page)
                if detection.is_plan:
                    self.plan = sp.compile_plan(page)
                    self.why_not = ""
                else:
                    self.why_not = "; ".join(detection.reasons)
        except Exception as exc:  # any document must give a session, never a failed ingest
            self.plan = None
            self.why_not = f"cannot read: {type(exc).__name__}: {exc}"[:300]
        elapsed = (time.perf_counter() - started) * 1000.0
        return IngestReport(ok=True, detail=self.why_not or "swiss plan", latency_ms=elapsed)

    def calibrate(self, calibration: Calibration) -> None:
        del calibration  # the sheets print their scale; a plan without one is not supported

    def ask(self, question: Question) -> AnswerRecord:
        plan = self.plan
        if plan is None:
            return _abstain(MissingReason.UNSUPPORTED, f"not a Swiss Dwellings sheet: {self.why_not}", "-")
        parsed = parse_question(question.text)
        if isinstance(parsed, str):
            return _abstain(MissingReason.UNSUPPORTED, f"question not understood: {parsed}", "ask a supported question")
        fact, tool = self._fact(plan, parsed)
        step = Step(tool=f"swiss_plan.{tool}", method="deterministic", summary=fact.note[:200] or str(fact.value))
        estimate = fact.value
        if fact.value is None:
            return _abstain(MissingReason.NOT_ON_DOCUMENT, "; ".join(fact.warnings), "-")
        if fact.warnings:
            record = _abstain(MissingReason.AMBIGUOUS, "; ".join(fact.warnings), "confirm the room outline", estimate)
            return record.model_copy(update={"unit": fact.unit, "steps": (step,), "evidence": fact.evidence[:20]})
        evidence: tuple[Evidence, ...] = fact.evidence[:40]
        if plan.scale is not None and fact.unit:
            evidence = (plan.scale.evidence, *evidence)
        return AnswerRecord(
            status="answered",
            value=fact.value,
            unit=fact.unit,
            confidence=0.97,
            convention="source data: stacked copies count" if parsed.intent in {"doors", "windows"} else "",
            evidence=evidence,
            steps=(step,),
        )

    @staticmethod
    def _fact(plan: sp.SwissPlan, parsed: Parsed) -> tuple[sp.Fact, str]:  # noqa: PLR0911 - one branch per intent
        intent = parsed.intent
        if intent == "count_label" and parsed.label is not None:
            fact = sp.label_count(plan, parsed.label)
            if fact.value == 0:  # the public set never asks for a label that is not there
                return fact.model_copy(
                    update={"value": None, "warnings": (f"no room labelled {parsed.label!r}",)}
                ), intent
            return fact, intent
        if intent == "apartments":
            return sp.apartment_count(plan), intent
        if intent == "doors":
            return sp.door_count(plan), intent
        if intent in {"windows", "toilets", "washbasins", "bathtubs", "showers"}:
            kind: sp.FixtureKind = {"windows": "window", "toilets": "toilet", "washbasins": "washbasin",
                                    "bathtubs": "bathtub", "showers": "shower"}[intent]  # fmt: skip
            return sp.fixture_count(plan, kind), intent
        if intent == "area_room" and parsed.room is not None:
            fact = sp.room_area(plan, parsed.room)
            r = sp.room(plan, parsed.room)
            if r is not None and parsed.label and r.label and sp.norm_label(r.label) != parsed.label:
                warning = f"the question names {parsed.label!r}, the sheet shows {r.label!r}"
                fact = fact.model_copy(update={"warnings": (*fact.warnings, warning)})
            return fact, intent
        if intent == "area_label" and parsed.label is not None:
            return sp.label_area(plan, parsed.label), intent
        if intent == "area_total":
            return sp.total_area(plan), intent
        if intent == "area_apartment" and parsed.apartment is not None:
            return sp.apartment_area(plan, parsed.apartment), intent
        return sp.Fact(value=None, warnings=("incomplete question",)), intent
