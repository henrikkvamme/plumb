"""What every hard-case generator shares: the draft of an item, the group, the partition and the id."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from functools import cache
from typing import TYPE_CHECKING, Literal, Protocol

from bp.contract import Calibration, Frozen, Item, Key
from bp.paths import ANALYSIS, DATASET, SPLIT

if TYPE_CHECKING:
    from collections.abc import Callable

Skill = Literal["count", "measure", "lookup", "compound", "unanswerable"]
INPUT_KIND = {"png": "raster", "pdf": "pdf", "ifc": "model", "dxf": "cad", "jpg": "raster", "jpeg": "raster"}
PARTITION: dict[str, Literal["dev", "val", "lock"]] = {"dev": "dev", "val": "val", "test": "lock"}
SQFT_PER_M2 = 1 / 0.09290304


class Draft(Frozen):
    """An item before it gets its id, group, partition and cell."""

    doc: str  # relative to the dataset root, starts with "data/"
    family: str
    skill: Skill
    question: str
    key: Key
    twins: tuple[str, ...] = ()
    how: str = ""  # how the key was computed, for the human-readable sample
    calibration: Calibration | None = None


class _GroupKey(Protocol):
    def __call__(self, path: str) -> str: ...


@cache
def group_key() -> Callable[[str], str]:
    """The same group key as the public items (analysis/questions/qcommon.py)."""
    spec = importlib.util.spec_from_file_location("qcommon", ANALYSIS / "questions" / "qcommon.py")
    if spec is None or spec.loader is None:
        msg = "cannot load analysis/questions/qcommon.py"
        raise RuntimeError(msg)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn: _GroupKey = module.group_key
    return fn


@cache
def split_groups() -> dict[str, str]:
    groups: dict[str, str] = json.loads(SPLIT.read_text())["groups"]
    return groups


def stable_hash(*parts: object) -> str:
    return hashlib.sha256(json.dumps([str(p) for p in parts], ensure_ascii=False).encode()).hexdigest()


def rank(seed: str, *parts: object) -> int:
    """A deterministic pseudo-random order that depends only on the seed and the parts."""
    return int(stable_hash(seed, *parts)[:12], 16)


def input_kind(doc: str) -> str:
    return INPUT_KIND.get(doc.rsplit(".", 1)[-1].lower(), "other")


def source_of(doc: str) -> str:
    return doc.split("/")[1]


def to_item(draft: Draft) -> Item:
    group = group_key()(draft.doc)
    split = split_groups().get(group)
    if split is None:
        msg = f"group {group} of {draft.doc} is not in split_v0"
        raise KeyError(msg)
    if not (DATASET / draft.doc).is_file():
        msg = f"document {draft.doc} does not exist"
        raise FileNotFoundError(msg)
    return Item(
        item_id="h-" + stable_hash(draft.doc, draft.family, draft.question)[:14],
        doc=draft.doc,
        question=draft.question,
        twins=draft.twins,
        key=draft.key,
        source=source_of(draft.doc),
        family=draft.family,
        group=group,
        cell=f"{draft.skill}/{input_kind(draft.doc)}",
        suite="hard",
        partition=PARTITION[split],
        origin="derived",
        calibration=draft.calibration,
    )


def close(a: float, b: float, rel: float = 0.01) -> bool:
    """Two computations of one value agree within `rel` of the larger."""
    return abs(a - b) <= rel * max(abs(a), abs(b), 1e-9)


def r2(value: float) -> float:
    return round(value + 0.0, 2)
