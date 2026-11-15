"""Count questions on raster floor plans, answered by the count head (`bp.tools.count_head`).

The solver reads the plan once at ingest. For a question it finds the family with rules (English and Finnish),
and answers only when the head is sure enough (a threshold tuned on held-out DEV plans) and the plan looks like
the training plans. Otherwise it abstains and says why.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from bp.contract import Abstain, AnswerRecord, Calibration, Evidence, IngestReport, MissingReason, Question, Step
from bp.tools.count_head import PlanCounts, count_plan, family_of, get_model, is_raster


def _abstain(reason: MissingReason, detail: str, request: str, **extra: object) -> AnswerRecord:
    return AnswerRecord(status="abstained", abstain=Abstain(reason=reason, detail=detail, request=request), **extra)  # ty: ignore[invalid-argument-type]


class CubicasaCountSolver:
    """E1: the best single model, one view."""

    name = "cubicasa-count"
    spec: ClassVar[str] = "e1.json"

    def __init__(self) -> None:
        self.counts: PlanCounts | None = None
        self.problem: str = ""

    def ingest(self, path: str) -> IngestReport:
        document = Path(path)
        if not is_raster(document):
            self.problem = "not_raster"
            return IngestReport(ok=True, detail="not a raster image: this solver reads raster plans only")
        try:
            self.counts = count_plan(document, get_model(self.spec))
        except OSError as exc:
            self.problem = "unreadable"
            return IngestReport(ok=True, detail=f"cannot read the image: {exc}")
        return IngestReport(ok=True, latency_ms=self.counts.latency_ms)

    def calibrate(self, calibration: Calibration) -> None:
        del calibration  # counts do not need a scale

    def ask(self, question: Question) -> AnswerRecord:  # noqa: PLR0911 - one return per abstain reason
        family = family_of(question.text)
        if family is None:
            return _abstain(MissingReason.UNSUPPORTED, "not a count question that this tool knows", "ask another tool")
        if self.problem == "not_raster":
            return _abstain(MissingReason.UNSUPPORTED, "the document is not a raster plan", "give a PNG or JPEG plan")
        if self.counts is None:
            return _abstain(MissingReason.UNREADABLE, "the image could not be read", "give the plan again")
        counts = self.counts
        if not counts.in_distribution:
            margin = "none" if counts.style_margin is None else f"{counts.style_margin:.2f}"
            detail = (
                f"the plan does not look like the CubiCasa training plans (distance ratio {counts.ood_distance:.2f},"
                f" style margin {margin})"
            )
            step = Step(tool="count_head", method="model", summary=detail)
            return _abstain(MissingReason.UNSUPPORTED, detail, "check the count by hand", steps=(step,))
        head = counts.counts.get(family)
        if head is None:
            return _abstain(MissingReason.UNSUPPORTED, f"no head for {family}", "ask another tool")
        box = counts.evidence.box
        evidence = Evidence(
            kind="calc",
            page=0,
            points=(box[0], (box[1][0], box[0][1]), box[1], (box[0][0], box[1][1])),
            ref=f"count_head:{family}",
            note="top counts " + ", ".join(f"{v}: {p:.2f}" for v, p in head.top),
        )
        step = Step(
            tool="count_head",
            method="model",
            summary=f"{family}: count {head.value} with probability {head.probability:.2f} (threshold {head.threshold:.2f})",
        )
        common = {"confidence": round(head.probability, 4), "evidence": (evidence,), "steps": (step,)}
        if head.overflow:
            detail = f"{family}: the count is over what the head can tell apart (at least {head.value})"
            return _abstain(MissingReason.AMBIGUOUS, detail, "count by hand or use a detector", **common)
        if not head.trusted:
            detail = (
                f"{family}: most likely {head.value}, probability {head.probability:.2f} is under {head.threshold:.2f}"
            )
            return _abstain(
                MissingReason.AMBIGUOUS, detail, "check the count by hand", best_estimate=head.value, **common
            )
        return AnswerRecord(
            status="answered",
            value=head.value,
            convention=f"count of {family} as the CubiCasa annotation counts them",
            **common,  # ty: ignore[invalid-argument-type]
        )


class CubicasaCountTTASolver(CubicasaCountSolver):
    """E2: the best single model with 8 dihedral views."""

    name = "cubicasa-count-tta"
    spec: ClassVar[str] = "e2-tta.json"


class CubicasaCountEnsembleSolver(CubicasaCountSolver):
    """E2: the two best models, 8 views each."""

    name = "cubicasa-count-ens"
    spec: ClassVar[str] = "e2-ens.json"
