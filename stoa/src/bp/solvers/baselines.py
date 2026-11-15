"""Baselines and canaries. They show what the harness measures when a solver knows nothing, or cheats."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import ClassVar

from bp.contract import Abstain, AnswerRecord, Calibration, IngestReport, MissingReason, Question
from bp.paths import ANALYSIS, ARTIFACTS, DATA, QUESTIONS, RUNS, SPLIT, SUITES


class _Base:
    name = "base"

    def __init__(self) -> None:
        self.path = ""

    def ingest(self, path: str) -> IngestReport:
        self.path = path
        return IngestReport(ok=True)

    def calibrate(self, calibration: Calibration) -> None:
        del calibration


class NullSolver(_Base):
    """Always abstains."""

    name = "null"

    def ask(self, question: Question) -> AnswerRecord:
        del question
        abstain = Abstain(reason=MissingReason.UNSUPPORTED, detail="the null solver", request="use a solver")
        return AnswerRecord(status="abstained", abstain=abstain)


class PriorSolver(_Base):
    """Answers with the most frequent answer for the exact question text. It does not open the document."""

    name = "prior"
    table_name = "prior-all.json"
    _tables: ClassVar[dict[str, dict[str, list[object]]]] = {}

    def ask(self, question: Question) -> AnswerRecord:
        table = self._tables.get(self.table_name)
        if table is None:
            table = json.loads((ARTIFACTS / self.table_name).read_text())
            self._tables[self.table_name] = table
        hit = table.get(question.text)
        if hit is None:
            abstain = Abstain(reason=MissingReason.UNSUPPORTED, detail="unseen question text", request="-")
            return AnswerRecord(status="abstained", abstain=abstain)
        value, unit = hit
        if not isinstance(value, (int, float, str)):
            return AnswerRecord(status="error", detail="bad table")
        return AnswerRecord(status="answered", value=value, unit=unit if isinstance(unit, str) else None)


class PriorDevSolver(PriorSolver):
    """The same, fitted on the DEV partition only."""

    name = "prior-dev"
    table_name = "prior-dev.json"


FORBIDDEN_PROBES: tuple[Path, ...] = (
    QUESTIONS,
    SPLIT,
    SUITES / "stoa.jsonl",
    DATA / "external",
    ANALYSIS / "questions" / "qcommon.py",
    RUNS,
)


def readable(path: Path) -> bool:
    try:
        if not path.exists():
            return False
        if path.is_dir():
            os.listdir(path)
        else:
            with path.open("rb") as handle:
                handle.read(16)
    except OSError:
        return False
    return True


class FileCanarySolver(_Base):
    """A cheat: it tries to read the keys and labels. The answer is the number of forbidden paths it could read."""

    name = "canary-files"

    def ask(self, question: Question) -> AnswerRecord:
        del question
        found = [str(p) for p in FORBIDDEN_PROBES if readable(p)]
        return AnswerRecord(status="answered", value=len(found), detail=";".join(found))


class NameCanarySolver(_Base):
    """A cheat: it reports everything that the file system tells about the document."""

    name = "canary-name"

    def ask(self, question: Question) -> AnswerRecord:
        del question
        path = Path(self.path)
        siblings = sorted(p.name for p in path.parent.iterdir())
        report = {"path": self.path, "real": os.path.realpath(self.path), "siblings": siblings}
        return AnswerRecord(status="answered", value=json.dumps(report))
