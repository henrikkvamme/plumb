"""The bootstrap interval must hold the true value about 95% of the time, also with clustered items."""

from __future__ import annotations

import numpy as np
import pytest

from bp.scoring import Outcome
from bp.session import ItemResult
from bp.stats import cluster_bootstrap, digest, paired, summarise


def result(item_id: str, group: str, right: bool) -> ItemResult:
    outcome = Outcome.CORRECT if right else Outcome.WRONG
    return ItemResult(item_id=item_id, group=group, source="s", family="f", cell="c", suite="t", condition="native",
                      partition="dev", outcome=outcome, score=1.0 if right else -1.0, plain=right, alternate=right,
                      estimate_correct=False, rows_total=2, rows_right=2 if right else 1)  # fmt: skip


def test_interval_coverage_with_clusters() -> None:
    rng = np.random.default_rng(7)
    truth, hits, naive_hits, trials = 0.6, 0, 0, 300
    for trial in range(trials):
        # 120 plans with 8 items each. A plan is easy or hard, so its items agree with each other.
        rates = np.clip(truth + rng.normal(0, 0.25, size=120), 0, 1)
        values = (rng.random((120, 8)) < rates[:, None]).astype(float).ravel()
        groups = [f"g{g}" for g in range(120) for _ in range(8)]
        interval = cluster_bootstrap(values, groups, rounds=400, seed=trial)
        hits += interval.low <= rates.mean() <= interval.high
        solo = cluster_bootstrap(values, [str(i) for i in range(len(values))], rounds=400, seed=trial)
        naive_hits += solo.low <= truth <= solo.high
        del solo
    assert hits / trials > 0.80  # the interval describes this sample of plans
    truth_hits = 0
    for trial in range(trials):
        rates = np.clip(truth + rng.normal(0, 0.25, size=120), 0, 1)
        values = (rng.random((120, 8)) < rates[:, None]).astype(float).ravel()
        groups = [f"g{g}" for g in range(120) for _ in range(8)]
        interval = cluster_bootstrap(values, groups, rounds=400, seed=trial)
        truth_hits += interval.low <= np.clip(truth + rng.normal(0, 0.25, 200_000), 0, 1).mean() <= interval.high
    assert 0.90 <= truth_hits / trials <= 0.99
    assert naive_hits / trials < truth_hits / trials  # an interval that ignores the clusters is too narrow


def test_summary_and_digest() -> None:
    results = [result(f"i{i}", f"g{i % 5}", i % 4 != 0) for i in range(40)]
    summary = summarise(results)
    assert (summary.items, summary.rows, summary.groups) == (40, 80, 5)
    assert summary.accuracy.value == pytest.approx(0.75)
    assert summary.score.value == pytest.approx(0.5)
    assert summary.row_accuracy == pytest.approx((30 * 2 + 10) / 80)
    assert summary.score.low <= summary.score.value <= summary.score.high
    assert digest(results) == digest(list(reversed(results)))
    assert digest(results) != digest([*results[1:], result("i0", "g0", True)])


def test_paired_difference() -> None:
    a = [result(f"i{i}", f"g{i % 10}", i % 2 == 0) for i in range(200)]
    b = [result(f"i{i}", f"g{i % 10}", True) for i in range(200)]
    better = paired(a, b)
    assert (better.items, better.a_only_right, better.b_only_right) == (200, 0, 100)
    assert better.significant
    assert better.score_difference.value == pytest.approx(1.0)
    same = paired(a, a)
    assert not same.significant
