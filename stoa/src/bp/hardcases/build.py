"""Build suites/hard.jsonl and the tracked sample experiments/hard-cases-sample.md.

Usage: `uv run python -m bp.hardcases.build` (add `--refresh` to read the Swiss floors again).
It runs outside the sandbox, because it reads labels. The output is deterministic for a given seed.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from typing import TYPE_CHECKING

from bp.contract import CountKey, Item, LookupKey, MeasureKey, UnanswerableKey
from bp.hardcases import cubicasa, ifc, swiss_facts
from bp.hardcases.common import Draft, input_kind, rank, to_item
from bp.hardcases.select import Candidate, select
from bp.hardcases.swiss_gen import Context, floor_specs, public_context
from bp.paths import EXPERIMENTS
from bp.suites import read_items, write_items

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

SEED = "hard-v1"
TWIN_SHARE = 2  # out of 5: the share of items that carry a translation twin
SAMPLE = EXPERIMENTS / "hard-cases-sample.md"

SWISS_TARGETS = {
    "bath_area": 14, "bath_tiles": 12, "bedroom_area": 12, "apartment_area": 12, "apartment_area_sqft": 10,
    "rooms_over_n_area": 12, "largest_room_area": 12, "largest_room_lookup": 12, "smallest_room_lookup": 12,
    "room_difference": 12, "average_room_size": 12, "circulation_share": 12, "apartments_over_2_rooms": 12,
    "rooms_with_window": 14, "doors_to_room": 14, "bathrooms_without_window": 12, "largest_apartment": 12,
    "absent_room": 8, "absent_space": 8, "ceiling_height": 8, "wall_material": 8, "ambiguous_room": 10,
}  # fmt: skip


def swiss_contexts() -> dict[str, Context]:
    rows: list[tuple[str, str, float | None]] = []
    for item in read_items("stoa"):
        if item.source != "swiss_dwellings":
            continue
        stem = item.doc.rsplit("/", 1)[1].rsplit(".", 1)[0]
        value = float(item.key.value) if isinstance(item.key, (MeasureKey, CountKey)) else None
        rows.extend((stem, text, value) for text in (item.question, *item.twins))
    return public_context(rows)


def swiss_candidates(refresh: bool = False) -> list[Candidate]:
    if refresh or not swiss_facts.CACHE.exists():
        swiss_facts.save(swiss_facts.build_facts())
    contexts = swiss_contexts()
    out: list[Candidate] = []
    for floor in swiss_facts.load():
        ctx = contexts.get(floor.stem)
        if ctx is None:
            continue
        docs = tuple(f"data/swiss_dwellings/{floor.stem}.{ext}" for ext in ("pdf", "png", "dxf"))
        for spec in floor_specs(floor, ctx):
            twin = spec.local and rank(SEED, "twin", floor.stem, spec.family) % 5 < TWIN_SHARE
            draft = Draft(
                doc=docs[0], family=spec.family, skill=spec.skill, question=spec.question, key=spec.key,
                twins=(spec.local,) if twin else (), how=spec.how,
            )  # fmt: skip
            out.append(Candidate(unit=floor.stem, docs=docs, draft=draft))
    return out


def build_drafts(refresh: bool = False) -> list[Draft]:
    drafts: list[Draft] = []
    drafts += select(swiss_candidates(refresh), SWISS_TARGETS, seed=SEED)
    drafts += select(cubicasa.candidates(SEED), cubicasa.TARGETS, seed=SEED, per_unit=3)
    drafts += select(ifc.candidates(SEED), ifc.TARGETS, seed=SEED, per_unit=8)
    return drafts


def build(refresh: bool = False) -> tuple[list[Item], dict[str, str]]:
    """The items, sorted by id, and how each key was computed (by item id)."""
    pairs = [(to_item(d), d.how) for d in build_drafts(refresh)]
    ids = [it.item_id for it, _ in pairs]
    if len(set(ids)) != len(ids):
        msg = "two items share an id"
        raise ValueError(msg)
    items = sorted((it for it, _ in pairs), key=lambda it: it.item_id)
    return items, {it.item_id: how for it, how in pairs}


# ----------------------------------------------------------------------------- the human-readable sample


def key_text(item: Item) -> str:
    key = item.key
    if isinstance(key, CountKey):
        alt = f" (alternate {', '.join(map(str, key.alternates))})" if key.alternates else ""
        return f"{key.value}{alt}"
    if isinstance(key, MeasureKey):
        alt = f" (alternate {', '.join(map(str, key.alternates))})" if key.alternates else ""
        return f"{key.value} {key.unit}{alt}"
    if isinstance(key, LookupKey):
        return " / ".join(key.accepted[:3])
    if isinstance(key, UnanswerableKey):
        return "no answer: " + ", ".join(r.value for r in key.reasons)
    return key.reference


def write_sample(items: Sequence[Item], how: dict[str, str], path: Path = SAMPLE, n: int = 30) -> None:
    """One item per family first, then fill up to `n`, in a seeded order. No dataset content beyond the keys."""
    ordered = sorted(items, key=lambda it: rank(SEED, "sample", it.item_id))
    picked: list[Item] = []
    seen: set[str] = set()
    for it in ordered:
        if it.family not in seen:
            picked.append(it)
            seen.add(it.family)
    picked += [it for it in ordered if it not in picked][: max(0, n - len(picked))]
    picked = sorted(picked[:n], key=lambda it: (it.family, it.item_id))
    lines = [
        "# Hard cases: a sample of 30 items",
        "",
        "Generated by `uv run python -m bp.hardcases.build` (seed `" + SEED + "`). The full suite is",
        "`suites/hard.jsonl` (not in git). Keys come from public labels, never from a solver. The method is in",
        "`experiments/notes/hardcases.md`.",
        "",
        "| family | input | question | key | how the key was computed |",
        "|---|---|---|---|---|",
    ]
    for it in picked:
        question = it.question.replace("|", "/")
        if it.twins:
            question += " <br>twin: " + it.twins[0].replace("|", "/")
        lines.append(
            f"| {it.family} | {it.source} {input_kind(it.doc)} | {question} | {key_text(it)} | {how.get(it.item_id, '')} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def report(items: Sequence[Item]) -> dict[str, dict[str, int]]:
    return {
        "family": dict(sorted(Counter(it.family for it in items).items())),
        "input": dict(sorted(Counter(f"{it.source}/{input_kind(it.doc)}" for it in items).items())),
        "partition": dict(sorted(Counter(it.partition for it in items).items())),
        "cell": dict(sorted(Counter(it.cell for it in items).items())),
        "twins": {"with": sum(bool(it.twins) for it in items), "without": sum(not it.twins for it in items)},
    }


def main() -> None:
    refresh = "--refresh" in sys.argv
    items, how = build(refresh)
    path = write_items("hard", items)
    write_sample(items, how)
    print(f"{len(items)} items -> {path}")
    print(json.dumps(report(items), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
