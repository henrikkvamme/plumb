"""Benchmark of the ifc_model and ifc_sheet tools and of the free-text reporter against the public keys.

It runs outside the sandbox, so it reads the suite and the original file names. Three parts:
1. ifc_model, per question family: every ifc_models item of the partition, answered from the IFC model of
   the same project (for a PDF item the model is found through the file name: a bench-only shortcut that the
   solver cannot take).
2. ifc_sheet, per question family: the PDF items, answered from the sheet alone, with the split into
   answered right, answered wrong and abstained.
3. ifc_text, per report kind: the ifc_bench items, scored with the harness rule (every number of the
   reference in the text).
Writes experiments/tools/ifc.json. Run: uv run python -m bp.toolbench.ifc [partition]
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from typing import TYPE_CHECKING

from bp.contract import CountKey, Item, MeasureKey, Question, TextKey
from bp.paths import DATASET, EXPERIMENTS
from bp.scoring import Outcome, fact_present, score_item
from bp.solvers import ifc
from bp.suites import read_items
from bp.tools import ifc_model as im
from bp.tools import ifc_sheet as sh

if TYPE_CHECKING:
    from pathlib import Path

    from bp.contract import AnswerRecord

OUT = EXPERIMENTS / "tools" / "ifc.json"
MODELS = DATASET / "data" / "ifc_models"


def model_for(doc: str) -> Path:
    """The IFC model of an ifc_models document: itself, or the model whose stem prefixes the sheet name."""
    path = DATASET / doc
    if path.suffix == ".ifc":
        return path
    stems = [p.stem for p in MODELS.glob("*.ifc") if not p.name.startswith("resbim")]
    best = max((s for s in stems if path.name.startswith(s + "_")), key=len)
    return MODELS / f"{best}.ifc"


def _new() -> Counter[str]:
    return Counter()


def _tally(table: dict[str, Counter[str]], family: str, item: Item, records: list[AnswerRecord]) -> None:
    outcomes = [score_item(item.key, r).outcome for r in records]
    worst = Outcome.CORRECT
    for o in outcomes:
        if o is Outcome.WRONG or (o is Outcome.ABSTAINED and worst is Outcome.CORRECT):
            worst = o
    table[family]["items"] += 1
    table[family][worst.value] += 1


def _rates(table: dict[str, Counter[str]]) -> dict[str, dict[str, float | int]]:
    out: dict[str, dict[str, float | int]] = {}
    for family, c in sorted(table.items()):
        n = c["items"]
        answered = c["correct"] + c["wrong"]
        out[family] = {
            "items": n, "correct": c["correct"], "wrong": c["wrong"], "abstained": c["abstained"],
            "agreement": round(c["correct"] / n, 4) if n else 0.0,
            "precision": round(c["correct"] / answered, 4) if answered else 0.0,
        }  # fmt: skip
    return out


def bench_model(items: list[Item]) -> dict[str, dict[str, float | int]]:
    """ifc_model functions on every ifc_models item, through the project's IFC model."""
    table: dict[str, Counter[str]] = defaultdict(_new)
    by_model: dict[Path, list[Item]] = defaultdict(list)
    for item in items:
        by_model[model_for(item.doc)].append(item)
    for path, group in sorted(by_model.items()):
        model = im.open_model(str(path))
        for item in group:
            q = ifc.parse_question(item.question)
            family = q.family if q else "unparsed"
            records = []
            for text in (item.question, *item.twins):
                parsed = ifc.parse_question(text)
                records.append(ifc.answer_model(model, parsed) if parsed else ifc.abstain(
                    ifc.MissingReason.UNSUPPORTED, "unparsed", "-", tool="bench"))  # fmt: skip
            _tally(table, f"{family}/{'ifc' if item.doc.endswith('.ifc') else 'via_pdf'}", item, records)
    return _rates(table)


def bench_sheet(items: list[Item]) -> dict[str, dict[str, float | int]]:
    """ifc_sheet functions on the PDF items, from the sheet alone, through the solver's sheet route."""
    table: dict[str, Counter[str]] = defaultdict(_new)
    by_doc: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        if item.doc.endswith(".pdf"):
            by_doc[item.doc].append(item)
    for doc, group in sorted(by_doc.items()):
        sheet = sh.read_sheet(str(DATASET / doc))
        for item in group:
            q = ifc.parse_question(item.question)
            family = q.family if q else "unparsed"
            if q is not None and q.category is not None and family == "count_storey":
                family = f"count_storey_{q.category}"
            records = []
            for text in (item.question, *item.twins):
                parsed = ifc.parse_question(text)
                records.append(ifc.answer_sheet(sheet, parsed) if parsed else ifc.abstain(
                    ifc.MissingReason.UNSUPPORTED, "unparsed", "-", tool="bench"))  # fmt: skip
            _tally(table, family, item, records)
    return _rates(table)


def bench_text(items: list[Item]) -> dict[str, dict[str, float | int]]:
    """The free-text reports per kind: right when every number of the reference is in the text."""
    table: dict[str, Counter[str]] = defaultdict(_new)
    by_doc: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        by_doc[item.doc].append(item)
    for doc, group in sorted(by_doc.items()):
        try:
            model = im.open_model(str(DATASET / doc))
        except Exception:
            table["unreadable"]["items"] += len(group)
            continue
        for item in group:
            key = item.key
            if not isinstance(key, TextKey):
                continue
            plan = ifc.plan_text(item.question)
            kind = plan.kind if plan else "none"
            row = table[kind]
            row["items"] += 1
            if not key.facts:
                row["no_facts"] += 1
                continue
            if plan is None or not ifc.side_known(model, plan, item.question):
                row["no_plan"] += 1
                continue
            body, _ = ifc._report(model, plan, item.question)  # noqa: SLF001 - the bench measures the reporter
            hits = sum(fact_present(f, body) for f in key.facts)
            row["facts_total"] += len(key.facts)
            row["facts_found"] += hits
            row["all_facts"] += hits == len(key.facts)
    out: dict[str, dict[str, float | int]] = {}
    for kind, c in sorted(table.items(), key=lambda kv: -kv[1]["items"]):
        n = c["items"]
        out[kind] = {
            "items": n, "all_facts": c["all_facts"], "no_facts": c["no_facts"], "no_plan": c["no_plan"],
            "precision_if_answered": round(c["all_facts"] / n, 4) if n else 0.0,
            "fact_recall": round(c["facts_found"] / c["facts_total"], 4) if c["facts_total"] else 0.0,
        }  # fmt: skip
    return out


def bench_solver_split(items: list[Item]) -> dict[str, int]:
    """How many PDF items the sheet route answers, abstains on with not_on_document, and other reasons."""
    split: Counter[str] = Counter()
    by_doc: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        if item.doc.endswith(".pdf"):
            by_doc[item.doc].append(item)
    for doc, group in by_doc.items():
        solver = ifc.IfcSolver()
        solver.ingest(str(DATASET / doc))
        for item in group:
            record = solver.ask(Question(qid="bench", text=item.question))
            if record.status == "answered":
                split["answered"] += 1
            elif record.abstain is not None:
                split[f"abstained:{record.abstain.reason.value}"] += 1
            split["items"] += 1
    return dict(split)


def bench(partition: str = "dev") -> dict[str, object]:
    started = time.perf_counter()
    every = [it for it in read_items("stoa") if it.partition == partition]
    models = [it for it in every if it.source == "ifc_models" and isinstance(it.key, (CountKey, MeasureKey))]
    bench_items = [it for it in every if it.source == "ifc_bench"]
    result: dict[str, object] = {
        "partition": partition,
        "ifc_model": bench_model(models),
        "ifc_sheet": bench_sheet(models),
        "sheet_route_split": bench_solver_split(models),
        "ifc_text": bench_text(bench_items),
    }
    result["seconds"] = round(time.perf_counter() - started, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    target = OUT if partition == "dev" else OUT.with_name(f"ifc-{partition}.json")
    target.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(bench(sys.argv[1] if len(sys.argv) > 1 else "dev"), indent=1, ensure_ascii=False))
