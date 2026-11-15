"""One sealed session: one document, one new solver, a fixed order of calls.

The harness gives the solver a copy of the document under a neutral name and the question text. It gives
nothing else: no key, no source name, no original file name. The order of calls is a state machine.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import time
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from bp.contract import AnswerRecord, Calibration, Frozen, IngestReport, Item, Question, UnanswerableKey
from bp.machine import Machine, Run
from bp.scoring import ItemScore, Outcome, combine_twins, score_item

if TYPE_CHECKING:
    from pathlib import Path


class State(StrEnum):
    NEW = "new"
    READY = "ready"
    FAILED = "failed"
    CLOSED = "closed"


class Event(StrEnum):
    INGEST_OK = "ingest_ok"
    INGEST_FAIL = "ingest_fail"
    ASK = "ask"
    CALIBRATE = "calibrate"
    SKIP = "skip"  # a question that gets an error record because the ingest failed
    CLOSE = "close"


SESSION: Machine[State, Event] = Machine(
    name="session",
    initial=State.NEW,
    finals=frozenset({State.CLOSED}),
    table={
        (State.NEW, Event.INGEST_OK): State.READY,
        (State.NEW, Event.INGEST_FAIL): State.FAILED,
        (State.READY, Event.ASK): State.READY,
        (State.READY, Event.CALIBRATE): State.READY,
        (State.READY, Event.CLOSE): State.CLOSED,
        (State.FAILED, Event.SKIP): State.FAILED,
        (State.FAILED, Event.CLOSE): State.CLOSED,
    },
)
SESSION.verify()


class SolverFailureError(Exception):
    """The solver crashed, timed out or returned something that is not a record."""


class Client(Protocol):
    """How the harness talks to one solver. A client serves one document at a time."""

    def open(self, path: str) -> IngestReport: ...

    def ask(self, question: Question) -> AnswerRecord: ...

    def calibrate(self, calibration: Calibration) -> None: ...

    def close(self) -> None: ...


class ItemResult(Frozen):
    item_id: str
    group: str
    source: str
    family: str
    cell: str
    suite: str
    condition: str
    partition: str
    outcome: Outcome
    score: float
    plain: bool
    alternate: bool
    estimate_correct: bool
    rows_total: int
    rows_right: int
    recovered: bool | None = None  # after a calibration: did the answer then arrive
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    records: tuple[AnswerRecord, ...] = ()


def neutral_name(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return f"doc-{digest.hexdigest()[:12]}{path.suffix.lower()}"


def seal(path: Path, workdir: Path) -> Path:
    """Put the document in `workdir` under a neutral name. A hard link, or a copy when a link is not possible."""
    workdir.mkdir(parents=True, exist_ok=True)
    target = workdir / neutral_name(path)
    if not target.exists():
        try:
            os.link(path, target)
        except OSError:
            shutil.copyfile(path, target)
    return target


def qid_for(item_id: str, index: int) -> str:
    return "q-" + hashlib.sha256(f"{item_id}:{index}".encode()).hexdigest()[:12]


def _error(detail: str) -> AnswerRecord:
    return AnswerRecord(status="error", detail=detail[:500])


def _ask(client: Client, question: Question) -> AnswerRecord:
    started = time.perf_counter()
    try:
        record = client.ask(question)
    except SolverFailureError as exc:
        record = _error(str(exc))
    elapsed = (time.perf_counter() - started) * 1000.0
    return record.model_copy(update={"latency_ms": elapsed})


def _recovered(client: Client, run: Run[State, Event], item: Item, first: AnswerRecord) -> bool | None:
    """After a correct abstention, give the calibration and ask again. None when the step does not apply."""
    key = item.key
    if not isinstance(key, UnanswerableKey) or key.after_calibration is None or item.calibration is None:
        return None
    if first.status != "abstained":
        return None
    run.fire(Event.CALIBRATE)
    try:
        client.calibrate(item.calibration)
    except SolverFailureError:
        return False
    run.fire(Event.ASK)
    second = _ask(client, Question(qid=qid_for(item.item_id, 1000), text=item.question))
    return score_item(key.after_calibration, second).outcome is Outcome.CORRECT


def _result(item: Item, records: list[AnswerRecord], scores: list[ItemScore], recovered: bool | None) -> ItemResult:
    total = combine_twins(scores)
    return ItemResult(
        item_id=item.item_id,
        group=item.group,
        source=item.source,
        family=item.family,
        cell=item.cell,
        suite=item.suite,
        condition=item.condition,
        partition=item.partition,
        outcome=total.outcome,
        score=total.score,
        plain=total.plain,
        alternate=total.alternate,
        estimate_correct=total.estimate_correct,
        rows_total=len(scores),
        rows_right=sum(1 for s in scores if s.plain),
        recovered=recovered,
        latency_ms=sum(r.latency_ms for r in records),
        cost_usd=sum(r.cost_usd for r in records),
        records=tuple(records),
    )


def run_document(client: Client, sealed: Path, items: list[Item]) -> tuple[list[ItemResult], list[Event]]:
    """Run every item of one document through one session. It returns the results and the event trace."""
    run = Run(SESSION)
    try:
        report = client.open(str(sealed))
    except SolverFailureError as exc:
        report = IngestReport(ok=False, detail=str(exc))
    run.fire(Event.INGEST_OK if report.ok else Event.INGEST_FAIL)
    results: list[ItemResult] = []
    # Items with a calibration step go last: the calibration changes the state of the solver.
    ordered = sorted(items, key=lambda it: (it.calibration is not None, it.item_id))
    for item in ordered:
        texts = (item.question, *item.twins)
        records: list[AnswerRecord] = []
        for index, text in enumerate(texts):
            if run.state is State.FAILED:
                run.fire(Event.SKIP)
                records.append(_error(f"ingest failed: {report.detail}"))
            else:
                run.fire(Event.ASK)
                records.append(_ask(client, Question(qid=qid_for(item.item_id, index), text=text)))
        scores = [score_item(item.key, record) for record in records]
        recovered = None if run.state is State.FAILED else _recovered(client, run, item, records[0])
        results.append(_result(item, records, scores, recovered))
    try:
        client.close()
    except SolverFailureError:
        pass
    run.fire(Event.CLOSE)
    if results and report.cost_usd:
        first = results[0]
        results[0] = first.model_copy(update={"cost_usd": first.cost_usd + report.cost_usd})
    return results, run.events()
