"""Count things on a raster floor plan with the symbol detector: the count is the number of marks.

ingest: open the image, run the detector once (global view plus tiles), keep every detection above the floor.
ask: map the question to a concept with English and Finnish word rules, count the concept's detections at or
above the tuned threshold, and return one evidence mark per counted object (the box centre).

It abstains when:
- the question is not a count, or names no concept it knows, or names two;
- the document is not a raster image, or the detector sees no plan on it;
- a detection of the asked classes has a score near the threshold (the count is uncertain);
- the count is above the largest count that held out well for that concept;
- the count on the left-right mirror of the plan differs (when calibration found that this check pays).

The model, thresholds and bands live in `artifacts/cubicasa-detect/<model>/` (see `bp.tools.symbol_detector`).
`BP_DETECT_MODEL` picks the model directory; the default is the name in `artifacts/cubicasa-detect/DEFAULT`.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

from bp.contract import Abstain, AnswerRecord, Calibration, Evidence, IngestReport, MissingReason, Question, Step
from bp.paths import ARTIFACTS
from bp.tools.symbol_detector import CONCEPTS, Detection, Detector, load_rgb

ROOT = ARTIFACTS / "cubicasa-detect"
RASTER_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"})
MIN_SIDE = 64
COUNT_TRIGGER = re.compile(r"\b(how many|number of|count the|kuinka monta|montako|lukumäärä)\b", re.IGNORECASE)
TRIGGER_FOCUS = re.compile(r"\b(?:how many|number of|count the|kuinka monta|montako)\b(.*)", re.IGNORECASE | re.DOTALL)
PARENS = re.compile(r"\([^)]*\)")
# Concept word rules, English and Finnish stems. Order does not matter; `_resolve` settles overlaps.
PATTERNS: dict[str, re.Pattern[str]] = {
    "floors": re.compile(r"\bfloors\b|\bstoreys?\b|\bstories\b|\bkerros"),
    "windows": re.compile(r"\bwindows?\b|\bikkun"),
    "doors": re.compile(r"\bdoors?\b|\bov(i|ea|et|ia)\b"),
    "toilets": re.compile(r"toilet (bowl|seat)s?|\bwc[- ]seats?|\btoilets\b|wc-istuin|\bistuin"),
    "sinks": re.compile(r"\bsinks?\b|wash ?basins?|\bbasins?\b|allas|altai|altaa"),
    "showers": re.compile(r"\bshowers?\b|suihku"),
    "bathtubs": re.compile(r"\bbath ?tubs?\b|\btubs?\b|amme"),
    "saunas": re.compile(r"\bsauna"),
    "kitchens": re.compile(r"\bkitchens?\b|keitti"),
    "bedrooms": re.compile(r"\bbedrooms?\b|makuuhuone"),
    "bathrooms": re.compile(r"\bbathrooms?\b|\bwashrooms?\b|kylpyhuone|pesuhuone|kylpy- tai"),
    "wc_rooms": re.compile(r"\bwc[- ]?rooms?\b|toilet rooms?|\bwc-til"),
    "balconies": re.compile(r"\bbalcon(y|ies)\b|parvek"),
}
FOCUS_WORDS = 6


def _resolve(found: set[str]) -> set[str]:
    out = set(found)
    if "bathrooms" in out:  # "bathrooms, not counting separate WC rooms"
        out -= {"wc_rooms", "toilets"}
    if "wc_rooms" in out:  # "separate WC rooms (toilet rooms marked WC)"
        out.discard("toilets")
    if {"showers", "bathtubs"} <= out:
        out -= {"showers", "bathtubs"}
        out.add("showers_tubs")
    return out


def concept_of(text: str) -> str | None:
    """The concept a count question asks for, or None when it is not one known count."""
    if not COUNT_TRIGGER.search(text):
        return None
    plain = PARENS.sub(" ", text.lower())
    focus_match = TRIGGER_FOCUS.search(plain)
    focus = " ".join(focus_match.group(1).split()[:FOCUS_WORDS]) if focus_match else ""
    for scope in (focus, plain):
        found = _resolve({name for name, pattern in PATTERNS.items() if pattern.search(scope)})
        if len(found) == 1:
            return found.pop()
        if len(found) > 1:
            return None
    return None


def model_directory(name: str = "") -> Path:
    chosen = name or os.environ.get("BP_DETECT_MODEL", "")
    if not chosen:
        pointer = ROOT / "DEFAULT"
        chosen = pointer.read_text().strip() if pointer.exists() else "rfdetr-l"
    return ROOT / chosen


def _doubt(concept: str, value: int, near: int, second: int | None, max_count: int) -> str:
    """Why a count is not sure, or an empty string."""
    if near:
        return f"{near} {concept} marks have a score near the threshold; the count is {value} or near it"
    if second is not None and second != value:
        return f"{value} {concept} marks, but {second} on the mirrored plan: the count is not stable"
    if value > max_count:
        return f"{value} {concept} marks: above {max_count}, exact counts this large were not reliable"
    return ""


def _abstain(reason: MissingReason, detail: str, request: str, **extra: Any) -> AnswerRecord:  # noqa: ANN401
    return AnswerRecord(status="abstained", abstain=Abstain(reason=reason, detail=detail, request=request), **extra)


class CubicasaDetectSolver:
    """One instance per document. The detector is cached per process."""

    name = "cubicasa-detect"

    def __init__(self) -> None:
        self.detections: list[Detection] | None = None
        self.mirrored: list[Detection] | None = None
        self.problem: tuple[MissingReason, str] | None = None
        self.size = (0, 0)
        self.seconds = 0.0
        self.detector: Detector | None = None

    def ingest(self, path: str) -> IngestReport:
        started = time.perf_counter()
        if Path(path).suffix.lower() not in RASTER_SUFFIXES:
            self.problem = (MissingReason.UNSUPPORTED, "not a raster image; this tool reads raster floor plans")
            return IngestReport(ok=True, detail=self.problem[1])
        try:
            image = load_rgb(path)
        except Exception as exc:
            self.problem = (MissingReason.UNREADABLE, f"cannot open the image: {type(exc).__name__}")
            return IngestReport(ok=True, detail=self.problem[1])
        self.size = image.size
        if min(image.size) < MIN_SIDE:
            self.problem = (MissingReason.UNREADABLE, f"the image is too small ({image.width} x {image.height} px)")
            return IngestReport(ok=True, detail=self.problem[1])
        self.detector = Detector.get(model_directory())
        self.detections = self.detector.detect(image)
        if self.detector.meta.get("mirror"):
            self.mirrored = self.detector.detect(image, mirror=True)
        self.seconds = time.perf_counter() - started
        plan_score = max((d.score for d in self.detections if d.label in {"floorplan", "door", "window"}), default=0)
        if plan_score < float(self.detector.meta.get("plan_min_score", 0.3)):
            self.problem = (MissingReason.NOT_A_DRAWING, "the detector finds no floor plan, door or window here")
        latency = self.seconds * 1000.0
        return IngestReport(ok=True, detail=f"{len(self.detections)} detections", latency_ms=latency)

    def sure_counts(self) -> dict[str, int]:
        """Every concept whose count passes the doubt rules of `ask`, for use as an agent tool."""
        if self.problem is not None or self.detections is None or self.detector is None:
            return {}
        out: dict[str, int] = {}
        for concept, classes in CONCEPTS.items():
            calib: dict[str, Any] = self.detector.meta.get("calibration", {}).get(concept, {})
            if not calib:
                continue
            threshold, band = float(calib.get("threshold", 0.5)), float(calib.get("band", 0.0))
            mine = [d for d in self.detections if d.label in classes]
            value = sum(1 for d in mine if d.score >= threshold)
            near = sum(1 for d in mine if threshold - band <= d.score < threshold + band)
            second = None
            if calib.get("mirror") and self.mirrored is not None:
                second = sum(1 for d in self.mirrored if d.label in classes and d.score >= threshold)
            if not _doubt(concept, value, near, second, int(calib.get("max_count", 10**6))):
                out[concept] = value
        return out

    def calibrate(self, calibration: Calibration) -> None:
        del calibration

    def ask(self, question: Question) -> AnswerRecord:
        concept = concept_of(question.text)
        if concept is None:
            return _abstain(MissingReason.UNSUPPORTED, "not a count this tool knows", "ask a count of one plan symbol")
        if self.problem is not None:
            return _abstain(self.problem[0], self.problem[1], "give a raster floor plan image")
        if self.detections is None or self.detector is None:
            return _abstain(MissingReason.UNREADABLE, "no detections", "give a raster floor plan image")
        calib: dict[str, Any] = self.detector.meta.get("calibration", {}).get(concept, {})
        classes = CONCEPTS[concept]
        threshold = float(calib.get("threshold", 0.5))
        band = float(calib.get("band", 0.0))
        max_count = int(calib.get("max_count", 10**6))
        mine = [d for d in self.detections if d.label in classes]
        counted = sorted((d for d in mine if d.score >= threshold), key=lambda d: (d.centre[1], d.centre[0]))
        near = [d for d in mine if threshold - band <= d.score < threshold + band]
        value = len(counted)
        second = None
        if calib.get("mirror") and self.mirrored is not None:
            second = sum(1 for d in self.mirrored if d.label in classes and d.score >= threshold)
        evidence = tuple(
            Evidence(kind="mark", points=(d.centre,), ref=d.label, note=f"score {d.score:.2f}") for d in counted
        )
        step = Step(
            tool="symbol_detector",
            method="model",
            summary=f"{concept}: {value} marks of {'/'.join(classes)} at score >= {threshold:.2f}; "
            f"{len(near)} within +-{band:.2f} of the threshold",
        )
        convention = f"one mark per {'/'.join(classes)} symbol at score >= {threshold:.2f}"
        doubt = _doubt(concept, value, len(near), second, max_count)
        if doubt:
            return _abstain(
                MissingReason.AMBIGUOUS, doubt, "check the marked symbols, or ask again with these marks shown",
                best_estimate=value, evidence=evidence, steps=(step,), convention=convention,
            )  # fmt: skip
        confidence = float(calib.get("answered_accuracy", 0.5))
        return AnswerRecord(
            status="answered", value=value, confidence=min(1.0, max(0.0, confidence)), convention=convention,
            evidence=evidence, steps=(step,), detail=f"ingest {self.seconds:.2f} s",
        )  # fmt: skip
