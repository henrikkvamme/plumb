"""Summaries with a cluster bootstrap. The cluster is the group of an item (a plan, a site, a model project)."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import TYPE_CHECKING

import numpy as np

from bp.contract import Frozen
from bp.scoring import Outcome

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from bp.session import ItemResult

BOOTSTRAP_ROUNDS = 2000
BOOTSTRAP_SEED = 20261114


class Interval(Frozen):
    value: float
    low: float
    high: float


class Slice(Frozen):
    items: int
    rows: int
    groups: int
    score: float
    accuracy: float
    row_accuracy: float
    answered: float
    wrong: float
    selective_accuracy: float | None


class Summary(Frozen):
    items: int
    rows: int
    groups: int
    score: Interval
    accuracy: Interval
    row_accuracy: float
    rows_right: int
    answered: float
    wrong: float
    abstained: float
    errors: float
    selective_accuracy: float | None
    alternate_accuracy: float
    estimate_accuracy: float
    recovered: float | None
    cost_usd: float
    latency_p50_ms: float
    latency_p95_ms: float
    digest: str
    by: dict[str, dict[str, Slice]]


ANSWERED = frozenset({Outcome.CORRECT, Outcome.WRONG})


def cluster_bootstrap(
    values: np.ndarray, groups: list[str], rounds: int = BOOTSTRAP_ROUNDS, seed: int = BOOTSTRAP_SEED
) -> Interval:
    """The mean of `values` with a 95% interval. It resamples whole groups, so items of one plan stay together."""
    if len(values) == 0:
        return Interval(value=0.0, low=0.0, high=0.0)
    index = {name: i for i, name in enumerate(dict.fromkeys(groups))}
    codes = np.array([index[g] for g in groups])
    sums = np.bincount(codes, weights=values, minlength=len(index))
    counts = np.bincount(codes, minlength=len(index)).astype(float)
    point = float(values.mean())
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(index), size=(rounds, len(index)))
    means = sums[picks].sum(axis=1) / counts[picks].sum(axis=1)
    low, high = np.quantile(means, [0.025, 0.975])
    return Interval(value=point, low=float(low), high=float(high))


def digest(results: Iterable[ItemResult]) -> str:
    """A hash of what was scored. Two runs of a deterministic solver must give the same digest."""
    lines = sorted(f"{r.item_id}:{r.outcome}:{r.rows_right}/{r.rows_total}" for r in results)
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def _slice(results: list[ItemResult]) -> Slice:
    n = len(results)
    rows = sum(r.rows_total for r in results)
    answered = [r for r in results if r.outcome in ANSWERED]
    return Slice(
        items=n,
        rows=rows,
        groups=len({r.group for r in results}),
        score=sum(r.score for r in results) / n,
        accuracy=sum(r.plain for r in results) / n,
        row_accuracy=sum(r.rows_right for r in results) / rows,
        answered=len(answered) / n,
        wrong=sum(r.outcome in {Outcome.WRONG, Outcome.ERROR} for r in results) / n,
        selective_accuracy=(sum(r.plain for r in answered) / len(answered)) if answered else None,
    )


def summarise(results: list[ItemResult]) -> Summary:
    if not results:
        msg = "no results"
        raise ValueError(msg)
    n = len(results)
    groups = [r.group for r in results]
    base = _slice(results)
    latencies = np.array([r.latency_ms for r in results])
    recovered = [r.recovered for r in results if r.recovered is not None]
    axes: dict[str, Callable[[ItemResult], str]] = {
        "source": lambda r: r.source,
        "cell": lambda r: r.cell,
        "suite": lambda r: r.suite,
        "condition": lambda r: r.condition,
        "partition": lambda r: r.partition,
        "family": lambda r: r.family,
    }
    by: dict[str, dict[str, Slice]] = {}
    for axis, key in axes.items():
        buckets: dict[str, list[ItemResult]] = defaultdict(list)
        for r in results:
            buckets[key(r)].append(r)
        by[axis] = {name: _slice(bucket) for name, bucket in sorted(buckets.items())}
    return Summary(
        items=n,
        rows=base.rows,
        groups=base.groups,
        score=cluster_bootstrap(np.array([r.score for r in results]), groups),
        accuracy=cluster_bootstrap(np.array([float(r.plain) for r in results]), groups),
        row_accuracy=base.row_accuracy,
        rows_right=sum(r.rows_right for r in results),
        answered=base.answered,
        wrong=base.wrong,
        abstained=sum(r.outcome in {Outcome.ABSTAINED, Outcome.ABSTAIN_RIGHT, Outcome.ABSTAIN_OTHER} for r in results)
        / n,
        errors=sum(r.outcome is Outcome.ERROR for r in results) / n,
        selective_accuracy=base.selective_accuracy,
        alternate_accuracy=sum(r.alternate for r in results) / n,
        estimate_accuracy=sum(r.plain or r.estimate_correct for r in results) / n,
        recovered=(sum(recovered) / len(recovered)) if recovered else None,
        cost_usd=sum(r.cost_usd for r in results),
        latency_p50_ms=float(np.quantile(latencies, 0.5)),
        latency_p95_ms=float(np.quantile(latencies, 0.95)),
        digest=digest(results),
        by=by,
    )


class Paired(Frozen):
    items: int
    score_difference: Interval  # b minus a
    accuracy_difference: Interval
    a_only_right: int
    b_only_right: int
    significant: bool


def paired(a: list[ItemResult], b: list[ItemResult]) -> Paired:
    """Compare two runs on the items that both hold. The interval is a paired cluster bootstrap of b minus a."""
    left = {r.item_id: r for r in a}
    common = [(left[r.item_id], r) for r in b if r.item_id in left]
    if not common:
        msg = "the two runs share no item"
        raise ValueError(msg)
    groups = [x.group for x, _ in common]
    score = cluster_bootstrap(np.array([y.score - x.score for x, y in common]), groups)
    accuracy = cluster_bootstrap(np.array([float(y.plain) - float(x.plain) for x, y in common]), groups)
    return Paired(
        items=len(common),
        score_difference=score,
        accuracy_difference=accuracy,
        a_only_right=sum(x.plain and not y.plain for x, y in common),
        b_only_right=sum(y.plain and not x.plain for x, y in common),
        significant=score.low > 0 or score.high < 0,
    )
