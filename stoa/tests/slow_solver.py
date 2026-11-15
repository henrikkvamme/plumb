from __future__ import annotations

import time

from bp.contract import AnswerRecord, Calibration, IngestReport, Question


class SlowSolver:
    name = "slow"

    def ingest(self, path: str) -> IngestReport:
        return IngestReport(ok=True)

    def calibrate(self, calibration: Calibration) -> None: ...

    def ask(self, question: Question) -> AnswerRecord:
        time.sleep(5)
        return AnswerRecord(status="answered", value=3)


class LoudSolver(SlowSolver):
    def ask(self, question: Question) -> AnswerRecord:
        print('{"record": "noise on stdout"}')
        return AnswerRecord(status="answered", value=3)
