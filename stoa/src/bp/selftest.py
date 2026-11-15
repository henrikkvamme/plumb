"""Checks that prove the harness. Each check has an expected value that was known before the harness existed.

The report goes to experiments/TRUST.md. A check that fails makes the command fail.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from bp.clients import InProcessClient, SubprocessClient, sandbox_available
from bp.contract import (
    AnswerRecord,
    Calibration,
    CountKey,
    IngestReport,
    Item,
    Key,
    LookupKey,
    MeasureKey,
    Question,
    TextKey,
)
from bp.paths import DATASET, EXPERIMENTS, RUNS, SESSIONS
from bp.runner import run_items
from bp.session import qid_for
from bp.stats import summarise
from bp.suites import read_items, select

if TYPE_CHECKING:
    from collections.abc import Callable

    from bp.session import Client, ItemResult

# Known before the harness existed (stoa/docs/DATASET.md).
PUBLIC_ROWS = 127_044
CUBICASA_ROWS = 85_514
PRIOR_ROWS_RIGHT = 47_308
NEUTRAL = re.compile(r"^doc-[0-9a-f]{12}\.[a-z0-9]+$")


class OracleSolver:
    """Returns the key. `spoil` makes each answer wrong by a small step, to prove that the scorer is not lax."""

    name = "oracle"

    def __init__(self, keys: dict[str, Key], *, spoil: bool = False) -> None:
        self._keys = keys
        self._spoil = spoil

    def ingest(self, path: str) -> IngestReport:
        del path
        return IngestReport(ok=True)

    def calibrate(self, calibration: Calibration) -> None:
        del calibration

    def ask(self, question: Question) -> AnswerRecord:
        key = self._keys[question.qid]
        if isinstance(key, CountKey):
            return AnswerRecord(status="answered", value=key.value + (1 if self._spoil else 0))
        if isinstance(key, MeasureKey):
            value = key.value * 1.03 + 0.006 if self._spoil else key.value
            return AnswerRecord(status="answered", value=value, unit=key.unit)
        if isinstance(key, LookupKey):
            return AnswerRecord(status="answered", value="" if self._spoil else key.accepted[0])
        if isinstance(key, TextKey):
            return AnswerRecord(status="answered", value="" if self._spoil else key.reference)
        return AnswerRecord(status="error", detail="no oracle for this key")


def _keys(items: list[Item]) -> dict[str, Key]:
    return {qid_for(it.item_id, i): it.key for it in items for i in range(1 + len(it.twins))}


def _in_process(items: list[Item], factory: Callable[[], object], tag: str) -> list[ItemResult]:
    def make(index: int) -> Client:
        del index
        return InProcessClient(factory)  # ty: ignore[invalid-argument-type]

    return run_items(items, make, root=DATASET, workdir=SESSIONS / f"selftest-{tag}", jobs=1, progress=False)


def _sealed(items: list[Item], solver: str, tag: str, *, sandbox: bool) -> list[ItemResult]:
    made: list[SubprocessClient] = []

    def make(index: int) -> Client:
        client = SubprocessClient(solver, sandbox=sandbox, log=RUNS / "_selftest" / f"worker-{tag}-{index}.log")
        made.append(client)
        return client

    try:
        return run_items(items, make, root=DATASET, workdir=SESSIONS / f"selftest-{tag}", jobs=2, progress=False)
    finally:
        for client in made:
            client.shutdown()


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.ok = True

    def check(self, name: str, expected: object, got: object, *, passed: bool | None = None) -> None:
        good = (expected == got) if passed is None else passed
        self.ok = self.ok and good
        self.lines.append(f"| {'PASS' if good else '**FAIL**'} | {name} | {expected} | {got} |")
        print(f"{'PASS' if good else 'FAIL'}  {name}: expected {expected}, got {got}")


def _check_tables(report: Report, items: list[Item]) -> None:
    rows = sum(1 + len(it.twins) for it in items)
    report.check("every public row is in exactly one item", PUBLIC_ROWS, rows)
    report.check("item ids are unique", len(items), len({it.item_id for it in items}))
    mixed = sum(1 for it in items if not (DATASET / it.doc).exists())
    report.check("every item points at a file that exists", 0, mixed)
    scorable = [it for it in items if not (isinstance(it.key, TextKey) and not it.key.facts)]
    report.lines.append(
        f"| note | free-text items with no number in the key (need a judge, not scored) | - | {len(items) - len(scorable)} |"
    )


def _check_oracle(report: Report, items: list[Item]) -> None:
    scorable = [it for it in items if not (isinstance(it.key, TextKey) and not it.key.facts)]
    keys = _keys(scorable)
    right = summarise(_in_process(scorable, lambda: OracleSolver(keys), "oracle"))
    report.check("oracle: every scorable item is right", len(scorable), round(right.accuracy.value * right.items))
    report.check("oracle: score is +1", 1.0, right.score.value)
    spoiled = summarise(_in_process(scorable, lambda: OracleSolver(keys, spoil=True), "spoiled"))
    report.check(
        "spoiled oracle (count +1, measure +3%): no item is right",
        0,
        round(spoiled.accuracy.value * spoiled.items),
    )
    report.check("spoiled oracle: score is -1", -1.0, spoiled.score.value)


def _check_baselines(report: Report, items: list[Item]) -> None:
    cubicasa = select(items, sources=("cubicasa5k",))
    report.check("cubicasa rows", CUBICASA_ROWS, sum(1 + len(it.twins) for it in cubicasa))
    prior = summarise(_sealed(cubicasa, "prior", "prior", sandbox=sandbox_available()))
    report.check("prior on cubicasa, sealed: rows right (55.32% in DATASET.md)", PRIOR_ROWS_RIGHT, prior.rows_right)
    sample = select(items, docs=300, seed="selftest")
    null = summarise(_sealed(sample, "null", "null", sandbox=sandbox_available()))
    report.check("null solver: score is 0", 0.0, null.score.value)
    report.check("null solver: accuracy is 0", 0.0, null.accuracy.value)
    first = summarise(_sealed(sample, "prior-dev", "det1", sandbox=sandbox_available()))
    second = summarise(_sealed(sample, "prior-dev", "det2", sandbox=sandbox_available()))
    report.check("the same run twice gives the same digest", first.digest, second.digest)


def _check_canaries(report: Report, items: list[Item]) -> None:
    sample = select(items, docs=12, seed="canary")
    if not sandbox_available():
        report.check("sandbox is available", True, False)
        return
    open_run = _sealed(sample, "canary-files", "open", sandbox=False)
    seen = {int(r.records[0].value) for r in open_run if isinstance(r.records[0].value, int)}
    report.check(
        "file canary WITHOUT the sandbox reads forbidden paths (the canary works)",
        True,
        min(seen) >= 4,
        passed=min(seen) >= 4,
    )
    closed = _sealed(sample, "canary-files", "closed", sandbox=True)
    values = {r.records[0].value for r in closed}
    report.check("file canary IN the sandbox: forbidden paths that it could read", {0}, values)
    names = _sealed(sample, "canary-name", "name", sandbox=True)
    stems = {Path(it.doc).stem for it in sample}
    leaks = 0
    for result in names:
        info = json.loads(str(result.records[0].value))
        text = json.dumps(info)
        path = Path(info["path"])
        fine = (
            NEUTRAL.match(path.name) is not None
            and all(NEUTRAL.match(s) for s in info["siblings"])
            and Path(info["real"]).name == path.name
            and not any(stem in text for stem in stems)
            and "junction-dataset" not in text
        )
        leaks += 0 if fine else 1
    report.check("name canary: answers that show an original name, source or path", 0, leaks)


def run(*, full: bool) -> bool:
    report = Report()
    items = read_items("stoa")
    _check_tables(report, items)
    _check_canaries(report, items)
    if full:
        _check_oracle(report, items)
        _check_baselines(report, items)
    head = [
        "# Harness trust report",
        "",
        "Generated by `uv run bp selftest`. Each row is a check with a value that was known before the harness",
        "existed, or a property that must hold. `uv run pytest` holds the unit and property tests of the scorer,",
        "the state machines and the statistics.",
        "",
        "| Result | Check | Expected | Got |",
        "|---|---|---|---|",
    ]
    (EXPERIMENTS / "TRUST.md").write_text("\n".join(head + report.lines) + "\n")
    return report.ok
