"""The confidence-threshold study for the direct VLM baseline. It makes no model call and it is not a solver.

It reads the saved items of finished runs (which ran with `BP_VLM_MIN_CONF=0`), turns each answer below a
threshold into an abstention, scores again with the real keys, and prints the score for each threshold.
It reads labels, so it runs outside the sandbox: `uv run python -m bp.solvers.vlm_direct_study <run id> ...`.
"""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

from bp.contract import AnswerRecord, Frozen
from bp.paths import EXPERIMENTS
from bp.scoring import ItemScore, combine_twins, score_item
from bp.stats import summarise
from bp.suites import read_items
from bp.track import load_results

if TYPE_CHECKING:
    from bp.contract import Item
    from bp.session import ItemResult

GRID = tuple(round(0.05 * step, 2) for step in range(21))


class Point(Frozen):
    threshold: float
    score: float
    low: float
    high: float
    accuracy: float
    answered: float
    wrong: float
    selective_accuracy: float | None


def apply_threshold(record: AnswerRecord, threshold: float) -> AnswerRecord:
    """An answer under the threshold becomes an abstention that keeps its value as the best estimate."""
    if record.status == "answered" and record.confidence < threshold:
        return record.model_copy(update={"status": "abstained", "best_estimate": record.value, "value": None})
    return record


def rescore(result: ItemResult, item: Item, threshold: float) -> ItemResult:
    records = tuple(apply_threshold(record, threshold) for record in result.records)
    scores: list[ItemScore] = [score_item(item.key, record) for record in records]
    total = combine_twins(scores)
    return result.model_copy(
        update={
            "records": records,
            "outcome": total.outcome,
            "score": total.score,
            "plain": total.plain,
            "alternate": total.alternate,
            "estimate_correct": total.estimate_correct,
            "rows_right": sum(1 for s in scores if s.plain),
        }
    )


def study(results: list[ItemResult], grid: tuple[float, ...] = GRID) -> list[Point]:
    items = {item.item_id: item for item in read_items("stoa")}
    points: list[Point] = []
    for threshold in grid:
        summary = summarise([rescore(result, items[result.item_id], threshold) for result in results])
        points.append(
            Point(
                threshold=threshold,
                score=summary.score.value,
                low=summary.score.low,
                high=summary.score.high,
                accuracy=summary.accuracy.value,
                answered=summary.answered,
                wrong=summary.wrong,
                selective_accuracy=summary.selective_accuracy,
            )
        )
    return points


def main(run_ids: list[str]) -> None:
    results = [result for run_id in run_ids for result in load_results(run_id)]
    points = study(results)
    print(f"items {len(results)} from {len(run_ids)} runs")
    print("thr    score  [low, high]        acc%  answered%  wrong%  sel acc%")
    for p in points:
        selective = "-" if p.selective_accuracy is None else f"{100 * p.selective_accuracy:.1f}"
        print(
            f"{p.threshold:.2f}  {p.score:+.3f}  [{p.low:+.3f}, {p.high:+.3f}]  {100 * p.accuracy:5.1f}  "
            f"{100 * p.answered:8.1f}  {100 * p.wrong:6.1f}  {selective:>7}"
        )
    out = EXPERIMENTS / "notes" / "vlm-direct-threshold.json"
    previous = json.loads(out.read_text()) if out.exists() else {}
    previous[",".join(run_ids)] = [p.model_dump() for p in points]
    out.write_text(json.dumps(previous, indent=1) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
