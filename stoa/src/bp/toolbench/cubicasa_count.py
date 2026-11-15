"""The benchmark for the count head (`bp.tools.count_head`) and its question rules.

It reads the item labels (suites/stoa.jsonl) and the dataset images, so it runs in a normal process, never in a
solver. `bench()` measures:

- `family_of` on every public count question: the share of CubiCasa question texts (both languages) that map to
  the right family, and the share of other sources' count questions that map to any family (a false claim);
- `count_plan` on the VAL plans: per family exact accuracy, answered share, accuracy when answered and the
  score (+1 right, -1 wrong, 0 abstained), against the DEV mode of each family;
- the out-of-distribution flag on rendered pages of other sources (PDF plans), which the head never saw.

It writes `experiments/tools/cubicasa_count.json`.
"""

from __future__ import annotations

import json
import random
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

from bp.contract import CountKey, Item
from bp.paths import DATASET, EXPERIMENTS
from bp.suites import read_items
from bp.tools.count_head import FAMILY_CODES, CountModel, count_plan, family_of, get_model

OUT = EXPERIMENTS / "tools" / "cubicasa_count.json"


def family_of_item(item: Item) -> str | None:
    return FAMILY_CODES.get(item.family.rsplit("/", 1)[-1]) if item.source == "cubicasa5k" else None


def bench_rules(items: list[Item]) -> dict[str, object]:
    right = total = 0
    wrong: Counter[str] = Counter()
    claimed = other = 0
    claims: Counter[str] = Counter()
    for item in items:
        truth = family_of_item(item)
        for text in (item.question, *item.twins):
            got = family_of(text)
            if truth is not None:
                total += 1
                right += got == truth
                if got != truth:
                    wrong[f"{truth} -> {got}: {text[:80]}"] += 1
            elif isinstance(item.key, CountKey):
                other += 1
                if got is not None:
                    claimed += 1
                    claims[f"{got}: {text[:80]}"] += 1
    return {
        "cubicasa_texts": total,
        "cubicasa_right": right,
        "cubicasa_accuracy": round(right / total, 4) if total else 0.0,
        "cubicasa_wrong": dict(wrong.most_common(10)),
        "other_count_texts": other,
        "other_claimed": claimed,
        "other_claimed_share": round(claimed / other, 4) if other else 0.0,
        "other_claims": dict(claims.most_common(15)),
    }


def bench_counts(items: list[Item], model: CountModel, partition: str) -> dict[str, object]:
    by_doc: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        if item.source == "cubicasa5k" and item.partition == partition and isinstance(item.key, CountKey):
            by_doc[item.doc].append(item)
    dev_values: dict[str, Counter[int]] = defaultdict(Counter)
    for item in items:
        family = family_of_item(item)
        if family and item.partition == "dev" and isinstance(item.key, CountKey):
            dev_values[family][item.key.value] += 1
    modes = {f: c.most_common(1)[0][0] for f, c in dev_values.items()}
    stats: dict[str, Counter[str]] = defaultdict(Counter)
    latencies: list[float] = []
    ood = 0
    for doc, doc_items in sorted(by_doc.items()):
        counts = count_plan(DATASET / doc, model)
        latencies.append(counts.latency_ms)
        ood += not counts.in_distribution
        for item in doc_items:
            family = family_of_item(item)
            key = item.key
            if family is None or not isinstance(key, CountKey):
                continue
            head = counts.counts[family]
            row = stats[family]
            row["n"] += 1
            row["exact"] += head.value == key.value
            row["prior"] += modes.get(family) == key.value
            if counts.in_distribution and head.trusted:
                row["answered"] += 1
                row["answered_right"] += head.value == key.value
    families = {}
    for family, row in sorted(stats.items()):
        n, answered, good = row["n"], row["answered"], row["answered_right"]
        families[family] = {
            "n": n,
            "exact_accuracy": round(row["exact"] / n, 4),
            "prior_accuracy": round(row["prior"] / n, 4),
            "answered_share": round(answered / n, 4),
            "accuracy_when_answered": round(good / answered, 4) if answered else 0.0,
            "score": round((2 * good - answered) / n, 4),
        }
    n = sum(r["n"] for r in stats.values())
    answered = sum(r["answered"] for r in stats.values())
    good = sum(r["answered_right"] for r in stats.values())
    latencies.sort()
    return {
        "partition": partition,
        "plans": len(by_doc),
        "items": n,
        "ood_flagged_plans": ood,
        "exact_accuracy": round(sum(r["exact"] for r in stats.values()) / n, 4),
        "prior_accuracy": round(sum(r["prior"] for r in stats.values()) / n, 4),
        "answered_share": round(answered / n, 4),
        "accuracy_when_answered": round(good / answered, 4) if answered else 0.0,
        "score": round((2 * good - answered) / n, 4),
        "latency_ms_median": round(latencies[len(latencies) // 2], 1) if latencies else 0.0,
        "families": families,
    }


def bench_ood(model: CountModel, sample: int = 40) -> dict[str, object]:
    """Render the first page of other sources' PDFs and check that the head calls them out of distribution."""
    pdfs = sorted(p for p in (DATASET / "data").rglob("*.pdf"))
    random.Random(0).shuffle(pdfs)  # noqa: S311 - a sample, not security
    flagged = 0
    ratios: list[float] = []
    with tempfile.TemporaryDirectory() as tmp:
        for index, pdf in enumerate(pdfs[:sample]):
            with pymupdf.open(pdf) as document:
                pixmap = document[0].get_pixmap(dpi=72)
                target = Path(tmp) / f"page-{index}.png"
                pixmap.save(target)
            counts = count_plan(target, model)
            flagged += not counts.in_distribution
            ratios.append(counts.ood_distance)
    ratios.sort()
    return {
        "pages": len(ratios),
        "flagged": flagged,
        "flagged_share": round(flagged / len(ratios), 4) if ratios else 0.0,
        "ratio_median": ratios[len(ratios) // 2] if ratios else 0.0,
    }


def bench(spec: str = "e1.json", partition: str = "val") -> dict[str, object]:
    started = time.perf_counter()
    items = read_items("stoa")
    model = get_model(spec)
    result: dict[str, object] = {
        "tool": "count_head",
        "spec": spec,
        "family_of": bench_rules(items),
        "count_plan": bench_counts(items, model, partition),
        "ood_other_sources": bench_ood(model),
    }
    result["seconds"] = round(time.perf_counter() - started, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, object] = json.loads(OUT.read_text()) if OUT.exists() else {}
    existing[f"{spec}:{partition}"] = result
    OUT.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    import sys

    print(json.dumps(bench(*sys.argv[1:]), indent=2, ensure_ascii=False))
