"""Build scored items from the public Stoa questions and load them.

One item is one independent question on one document. Translations of the same question become twins of one
item. The item files hold keys, so they live in `suites/`, outside git and outside the reach of a solver.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from bp.contract import CountKey, Item, Key, LookupKey, MeasureKey, TextKey
from bp.paths import ANALYSIS, SPLIT, SUITES
from bp.scoring import numbers

if TYPE_CHECKING:
    from pathlib import Path

INPUT_KIND = {"png": "raster", "pdf": "pdf", "ifc": "model", "dxf": "cad", "jpg": "raster", "jpeg": "raster"}
PARTITION = {"dev": "dev", "val": "val", "test": "lock"}


def _qcommon() -> Any:  # noqa: ANN401 - an analysis module without types
    spec = importlib.util.spec_from_file_location("qcommon", ANALYSIS / "questions" / "qcommon.py")
    if spec is None or spec.loader is None:
        msg = "cannot load analysis/questions/qcommon.py"
        raise RuntimeError(msg)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _decimals(answer: object) -> int:
    text = repr(answer)
    return max(2, len(text.split(".")[1])) if isinstance(answer, float) and "." in text and "e" not in text else 2


def make_key(row: dict[str, Any]) -> Key:
    kind, answer = row["type"], row["answer"]
    if kind == "count":
        return CountKey(value=int(answer))
    if kind in {"area", "volume", "length"}:
        return MeasureKey(value=float(answer), unit=str(row["unit"]), decimals=_decimals(answer))
    if row["path"].split("/")[1] == "opening_design":
        return LookupKey(accepted=(str(answer),))
    facts = tuple(dict.fromkeys(repr(n) for n in numbers(str(answer))))
    return TextKey(reference=str(answer), facts=facts)


def build_stoa_items() -> list[Item]:
    """Every public question as an item, twins merged, with the partition of split_v0."""
    qc = _qcommon()
    rows: list[dict[str, Any]] = qc.annotate(qc.load())
    families: dict[tuple[str, str], str] = qc.families(rows)
    split: dict[str, str] = json.loads(SPLIT.read_text())["groups"]
    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        family = families[(row["_src"], row["_tpl"])]
        buckets[(row["path"], family, row["_sk"], row["type"], repr(row["answer"]))].append(row)
    items: list[Item] = []
    for (path, family, slots, kind, answer), bucket in buckets.items():
        english = [r for r in bucket if r["_lang"] == "en"]
        first = english[0] if english else bucket[0]
        twins = tuple(dict.fromkeys(r["question"] for r in bucket if r["question"] != first["question"]))
        if len(twins) + 1 != len(bucket):  # the same text twice on one document: keep the row count honest
            twins = tuple(r["question"] for r in bucket if r is not first)
        group = qc.group_key(path)
        source = first["_src"]
        item_id = hashlib.sha256(json.dumps([path, family, slots, kind, answer]).encode()).hexdigest()[:16]
        items.append(
            Item(
                item_id=item_id,
                doc=path,
                question=first["question"],
                twins=twins,
                key=make_key(first),
                source=source,
                family=family,
                group=group,
                cell=f"{kind}/{INPUT_KIND.get(path.rsplit('.', 1)[-1].lower(), 'other')}",
                suite="stoa",
                partition=PARTITION[split[group]],  # ty: ignore[invalid-argument-type]
            )
        )
    items.sort(key=lambda it: it.item_id)
    return items


def write_items(name: str, items: list[Item]) -> Path:
    SUITES.mkdir(parents=True, exist_ok=True)
    path = SUITES / f"{name}.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(item.model_dump_json() + "\n")
    return path


def read_items(name: str) -> list[Item]:
    path = SUITES / f"{name}.jsonl"
    with path.open(encoding="utf-8") as handle:
        return [Item.model_validate_json(line) for line in handle if line.strip()]


def suite_hash(items: list[Item]) -> str:
    digest = hashlib.sha256()
    for item in sorted(items, key=lambda it: it.item_id):
        digest.update(item.model_dump_json().encode())
    return digest.hexdigest()[:16]


def select(
    items: list[Item],
    *,
    sources: tuple[str, ...] = (),
    partitions: tuple[str, ...] = (),
    cells: tuple[str, ...] = (),
    docs: int = 0,
    seed: str = "s0",
) -> list[Item]:
    """Filter, then keep `docs` whole documents in an order that depends only on the seed and the document."""
    kept = [
        it
        for it in items
        if (not sources or it.source in sources)
        and (not partitions or it.partition in partitions)
        and (not cells or it.cell in cells)
    ]
    if docs > 0:
        names = sorted({it.doc for it in kept}, key=lambda d: hashlib.sha256(f"{seed}:{d}".encode()).hexdigest())
        chosen = set(names[:docs])
        kept = [it for it in kept if it.doc in chosen]
    return kept
