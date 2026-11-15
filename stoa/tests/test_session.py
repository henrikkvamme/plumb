"""The session order, failures of a solver, and the calibration step."""

from __future__ import annotations

from pathlib import Path

from bp.clients import InProcessClient, SubprocessClient
from bp.contract import (
    Abstain,
    AnswerRecord,
    Calibration,
    CountKey,
    IngestReport,
    Item,
    MeasureKey,
    MissingReason,
    Question,
    UnanswerableKey,
)
from bp.runner import run_items
from bp.scoring import Outcome
from bp.session import Event, run_document, seal


class Fake:
    name = "fake"

    def __init__(self, *, ingest_ok: bool = True, crash: bool = False) -> None:
        self.ingest_ok, self.crash, self.scale = ingest_ok, crash, None

    def ingest(self, path: str) -> IngestReport:
        assert Path(path).name.startswith("doc-")
        return IngestReport(ok=self.ingest_ok, detail="" if self.ingest_ok else "cannot read")

    def calibrate(self, calibration: Calibration) -> None:
        self.scale = calibration.scale_ratio

    def ask(self, question: Question) -> AnswerRecord:
        if self.crash:
            raise RuntimeError("boom")
        if "area" in question.text:
            if self.scale is None:
                abstain = Abstain(reason=MissingReason.NO_SCALE, detail="no scale", request="give the scale")
                return AnswerRecord(status="abstained", abstain=abstain)
            return AnswerRecord(status="answered", value=12.5, unit="m2")
        return AnswerRecord(status="answered", value=3 if "doors" in question.text else 99)


def item(item_id: str, question: str, key, twins=(), calibration=None) -> Item:
    return Item(item_id=item_id, doc="plan.png", question=question, twins=twins, key=key, source="s", family="f",
                group="g", cell="c", suite="t", calibration=calibration)  # fmt: skip


def doc(tmp_path: Path) -> Path:
    source = tmp_path / "src" / "secret-original-name.png"
    source.parent.mkdir()
    source.write_bytes(b"png")
    return seal(source, tmp_path / "sealed")


def test_session_scores_twins_and_keeps_the_order(tmp_path: Path) -> None:
    items = [item("a", "how many doors", CountKey(value=3), twins=("kuinka monta doors", "windows?"))]
    results, events = run_document(InProcessClient(Fake), doc(tmp_path), items)
    assert events == [Event.INGEST_OK, Event.ASK, Event.ASK, Event.ASK, Event.CLOSE]
    assert (results[0].rows_total, results[0].rows_right, results[0].outcome) == (3, 2, Outcome.WRONG)


def test_failed_ingest_gives_errors(tmp_path: Path) -> None:
    items = [item("a", "how many doors", CountKey(value=3)), item("b", "how many doors", CountKey(value=3))]
    results, events = run_document(InProcessClient(lambda: Fake(ingest_ok=False)), doc(tmp_path), items)
    assert events == [Event.INGEST_FAIL, Event.SKIP, Event.SKIP, Event.CLOSE]
    assert {r.outcome for r in results} == {Outcome.ERROR}
    assert all(r.score == -1.0 for r in results)


def test_crash_is_an_error_not_a_stop(tmp_path: Path) -> None:
    items = [item("a", "how many doors", CountKey(value=3))]
    results, _ = run_document(InProcessClient(lambda: Fake(crash=True)), doc(tmp_path), items)
    assert results[0].outcome is Outcome.ERROR
    assert "boom" in results[0].records[0].detail


def test_calibration_recovers_the_answer(tmp_path: Path) -> None:
    key = UnanswerableKey(reasons=(MissingReason.NO_SCALE,), after_calibration=MeasureKey(value=12.5, unit="m2"))
    items = [
        item("z", "what is the area", key, calibration=Calibration(scale_ratio=100.0)),
        item("y", "how many doors", CountKey(value=3)),
    ]
    results, events = run_document(InProcessClient(Fake), doc(tmp_path), items)
    by_id = {r.item_id: r for r in results}
    assert (by_id["z"].outcome, by_id["z"].score, by_id["z"].recovered) == (Outcome.ABSTAIN_RIGHT, 1.0, True)
    assert by_id["y"].recovered is None
    assert events == [Event.INGEST_OK, Event.ASK, Event.ASK, Event.CALIBRATE, Event.ASK, Event.CLOSE]


def test_worker_process_round_trip_and_time_limit(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "plan.png").write_bytes(b"png")
    items = [item("a", "how many doors", CountKey(value=3))]
    clients: list[SubprocessClient] = []

    def make(spec: str, ask_timeout: float):
        def build(index: int) -> SubprocessClient:
            client = SubprocessClient(spec, sandbox=False, log=tmp_path / f"w{index}.log", ask_timeout=ask_timeout)
            clients.append(client)
            return client

        return build

    null = run_items(items, make("null", 30.0), root=root, workdir=tmp_path / "s1", progress=False)
    assert null[0].outcome is Outcome.ABSTAINED
    slow = run_items(
        items, make("tests.slow_solver:SlowSolver", 0.5), root=root, workdir=tmp_path / "s2", progress=False
    )
    assert slow[0].outcome is Outcome.ERROR
    assert "time limit" in slow[0].records[0].detail
    loud = run_items(
        items, make("tests.slow_solver:LoudSolver", 30.0), root=root, workdir=tmp_path / "s3", progress=False
    )
    assert loud[0].outcome is Outcome.CORRECT  # a solver that prints to stdout does not break the protocol
    for client in clients:
        client.shutdown()
    assert not (tmp_path / "s1").exists()  # the sealed copies are removed
