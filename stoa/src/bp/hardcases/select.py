"""Pick a balanced, deterministic subset of candidate questions.

A candidate is one question on one plan (a unit) that is valid on one or more documents of the plan (the PDF,
the PNG and the DXF of a Swiss floor). The selector walks the candidates of each family in a seeded order and
puts each on the input kind that has the fewest items of that family so far. Limits: at most 4 items per
document, one item per family per document, and a cap per unit so the suite spreads over many plans.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import TYPE_CHECKING

from bp.contract import Frozen
from bp.hardcases.common import Draft, input_kind, rank

if TYPE_CHECKING:
    from collections.abc import Sequence

MAX_PER_DOC = 4


class Candidate(Frozen):
    unit: str  # the plan: a Swiss floor, a CubiCasa plan, an IFC project storey
    docs: tuple[str, ...]  # documents that the question is valid on
    draft: Draft  # its doc is a placeholder; the selector sets the doc


def select(
    candidates: Sequence[Candidate],
    targets: dict[str, int],
    *,
    seed: str,
    per_unit: int = 6,
) -> list[Draft]:
    """`targets` maps a family to the number of items wanted per input kind."""
    by_family: dict[str, list[Candidate]] = defaultdict(list)
    for c in candidates:
        by_family[c.draft.family].append(c)
    per_doc: Counter[str] = Counter()
    unit_count: Counter[str] = Counter()
    doc_families: set[tuple[str, str]] = set()
    chosen: list[Draft] = []
    # Rare families first, so they get their documents before the common families fill them.
    order = sorted(by_family, key=lambda fam: (len(by_family[fam]), fam))
    for family in order:
        target = targets.get(family, 0)
        filled: Counter[str] = Counter()
        pool = sorted(by_family[family], key=lambda c: rank(seed, family, c.unit, c.draft.question))
        for cand in pool:
            if unit_count[cand.unit] >= per_unit:
                continue
            open_docs = [
                d
                for d in cand.docs
                if per_doc[d] < MAX_PER_DOC and (d, family) not in doc_families and filled[input_kind(d)] < target
            ]
            if not open_docs:
                continue
            doc = min(open_docs, key=lambda d: (filled[input_kind(d)], rank(seed, "doc", d)))
            filled[input_kind(doc)] += 1
            per_doc[doc] += 1
            unit_count[cand.unit] += 1
            doc_families.add((doc, family))
            chosen.append(cand.draft.model_copy(update={"doc": doc}))
    return chosen
