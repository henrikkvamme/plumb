"""The hard-case generator: deterministic, valid items, real documents, balanced, twins that share one key."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from collections import Counter

import pytest

from bp.contract import CountKey, Item, LookupKey, MeasureKey, UnanswerableKey
from bp.hardcases.common import PARTITION, Draft, close, input_kind, rank, split_groups
from bp.hardcases.select import MAX_PER_DOC, Candidate, select
from bp.paths import DATASET, SPLIT

HAVE_DATA = (DATASET / "data").is_dir() and SPLIT.is_file()
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="the dataset is not here")

DIGEST = (
    "import hashlib; from bp.hardcases.build import build; items, _ = build(); "
    "print(hashlib.sha256(''.join(i.model_dump_json() for i in items).encode()).hexdigest())"
)


def digest(items: list[Item]) -> str:
    return hashlib.sha256("".join(i.model_dump_json() for i in items).encode()).hexdigest()


@pytest.fixture(scope="module")
def items() -> list[Item]:
    from bp.hardcases.build import build  # noqa: PLC0415 - the import reads the dataset, so only on demand

    built, _ = build()
    return built


# ----------------------------------------------------------------------------- without data


def test_rank_is_stable() -> None:
    assert rank("s", "a", 1) == rank("s", "a", 1)
    assert rank("s", "a", 1) != rank("t", "a", 1)


def test_close_is_relative() -> None:
    assert close(100.0, 100.9)
    assert not close(100.0, 101.5)


def _cand(unit: str, family: str, docs: tuple[str, ...]) -> Candidate:
    draft = Draft(doc=docs[0], family=family, skill="count", question=f"{family} {unit}?", key=CountKey(value=1))
    return Candidate(unit=unit, docs=docs, draft=draft)


def test_select_respects_limits() -> None:
    docs = ("data/x/a.pdf", "data/x/a.png", "data/x/a.dxf")
    cands = [_cand("a", f"f{i}", docs) for i in range(8)] * 2
    chosen = select(cands, {f"f{i}": 5 for i in range(8)}, seed="t", per_unit=20)
    per_doc = Counter(d.doc for d in chosen)
    assert max(per_doc.values()) <= MAX_PER_DOC
    assert len({(d.doc, d.family) for d in chosen}) == len(chosen)
    assert select(cands, {f"f{i}": 5 for i in range(8)}, seed="t", per_unit=20) == chosen


def test_select_caps_per_unit() -> None:
    docs = ("data/x/a.pdf", "data/x/a.png", "data/x/a.dxf")
    cands = [_cand("a", f"f{i}", docs) for i in range(8)]
    assert len(select(cands, {f"f{i}": 5 for i in range(8)}, seed="t", per_unit=3)) == 3


# ----------------------------------------------------------------------------- with data


@needs_data
def test_build_is_deterministic_across_processes(items: list[Item]) -> None:
    env = {**os.environ, "PYTHONHASHSEED": "12345"}
    out = subprocess.run([sys.executable, "-c", DIGEST], capture_output=True, text=True, check=True, env=env)
    assert out.stdout.strip() == digest(items)


@needs_data
def test_size_and_balance(items: list[Item]) -> None:
    assert 600 <= len(items) <= 1500
    assert len({it.item_id for it in items}) == len(items)
    per_doc = Counter(it.doc for it in items)
    assert max(per_doc.values()) <= MAX_PER_DOC
    family = Counter(it.family for it in items)
    assert max(family.values()) <= 0.08 * len(items)
    kinds = Counter(input_kind(it.doc) for it in items)
    assert set(kinds) == {"pdf", "raster", "cad", "model"}


@needs_data
def test_every_item_validates(items: list[Item]) -> None:
    skills = {"count", "measure", "lookup", "compound", "unanswerable"}
    for it in items:
        assert Item.model_validate_json(it.model_dump_json()) == it
        assert it.suite == "hard"
        assert it.origin == "derived"
        skill, kind = it.cell.split("/")
        assert skill in skills
        assert kind == input_kind(it.doc)
        assert (skill == "unanswerable") == isinstance(it.key, UnanswerableKey)
        if isinstance(it.key, UnanswerableKey):
            assert it.key.reasons
        if isinstance(it.key, MeasureKey):
            assert it.key.value > 0
        if isinstance(it.key, LookupKey):
            assert it.key.accepted


@needs_data
def test_every_doc_exists(items: list[Item]) -> None:
    for doc in {it.doc for it in items}:
        assert (DATASET / doc).is_file(), doc


@needs_data
def test_partition_follows_split(items: list[Item]) -> None:
    groups = split_groups()
    for it in items:
        assert PARTITION[groups[it.group]] == it.partition


@needs_data
def test_twins_share_the_key(items: list[Item]) -> None:
    with_twins = [it for it in items if it.twins]
    assert len(with_twins) >= 0.2 * len(items)
    for it in with_twins:
        # A twin lives on the same item, so it is scored against the same key; it must be a real translation.
        assert all(t.strip() and t != it.question for t in it.twins)
        assert len(set(it.twins)) == len(it.twins)
