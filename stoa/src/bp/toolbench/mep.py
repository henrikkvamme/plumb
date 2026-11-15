"""Benchmark of the MEP tools (`bp.tools.ifc_mep`, `bp.solvers.mep_tools`) on the IFC files with building services.

The keys come from `mep_truth`, which reads the STEP text and measures lengths by ports or by the OCC kernel. It
shares no code with the tool. Steps:
1. `facts <file>...` reads the truth of each file and caches it in experiments/cache/mep/<sha>.json. The OCC part
   is heavy on large files: run it on a VM.
2. `items` writes suites/mep.jsonl: counts per kind, per storey and per type, and lengths per kind, storey and
   system, with the partition of the file's project (split_v0).
3. `bench` answers every item with the tools through a fixed router (no model), scores it with the harness rule
   (+1 right, 0 abstained, -1 wrong; a length is right within 2%) and writes experiments/tools/mep.json.
Run: uv run python -m bp.toolbench.mep facts|items|bench [paths]
"""

from __future__ import annotations

import functools
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from bp.contract import Abstain, AnswerRecord, CountKey, Item, MeasureKey, MissingReason
from bp.paths import DATASET, EXPERIMENTS, SPLIT, SUITES
from bp.scoring import score_item
from bp.suites import PARTITION, _qcommon, read_items, write_items
from bp.toolbench import mep_truth
from bp.tools import ifc_mep, ifc_model

CACHE = EXPERIMENTS / "cache" / "mep"
OUT = EXPERIMENTS / "tools" / "mep.json"
SUITE = "mep"
SPECS = SUITES / "mep-specs.json"  # item id -> the tool route of the item (kind, storey, system, type)
ROOTS = (DATASET / "data" / "ifc_models", DATASET / "data" / "ifc_bench")
MARKERS = (b"IFCFLOWSEGMENT(", b"IFCPIPESEGMENT(", b"IFCDUCTSEGMENT(", b"IFCFLOWTERMINAL(", b"IFCFLOWFITTING(",
           b"IFCPIPEFITTING(", b"IFCCABLECARRIERSEGMENT(", b"IFCVALVE(", b"IFCSANITARYTERMINAL(")  # fmt: skip
CAPS = {"count_storey": 8, "count_type": 6, "length_storey": 6, "length_system": 6}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()[:16]


def mep_files() -> list[Path]:
    """IFC files with at least 20 distribution elements, one per content (byte-identical copies dropped)."""
    seen: set[str] = set()
    out = []
    for root in ROOTS:
        for path in sorted(root.glob("*.ifc")):
            hits = 0
            with path.open("rb") as handle:
                for line in handle:
                    if any(m in line for m in MARKERS):
                        hits += 1
                        if hits >= 20:
                            break
            if hits < 20:
                continue
            key = sha(path)
            if key not in seen:
                seen.add(key)
                out.append(path)
    return out


# ----------------------------------------------------------------------------- facts


def facts(path: Path) -> dict[str, Any]:
    """The truth of one file as plain JSON, cached by content."""
    path = path.resolve()
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / f"{sha(path)}.json"
    if target.exists():
        return json.loads(target.read_text())
    started = time.perf_counter()
    truth = mep_truth.read_truth(path)
    segs = {sid for sid, k in truth.kinds.items() if k in ifc_mep.SEGMENT_KINDS}
    need = {truth.guid[s] for s in segs}  # every segment: the OCC extent also checks the port lengths
    mesh: dict[str, float] = {}
    try:
        mesh = mep_truth.truth_mesh_lengths(path, need) if need else {}
    except Exception as exc:  # IfcOpenShell cannot parse a few files; the port lengths still count
        print(f"{path.name}: no OCC lengths ({exc})", file=sys.stderr)
    rows = []
    for sid, kind in truth.kinds.items():
        guid = truth.guid[sid]
        length = truth.port_length_m.get(sid)
        method = "ports" if length is not None else ("mesh" if guid in mesh else "")
        if length is None and guid in mesh:
            length = mesh[guid]
        rows.append({"guid": guid, "kind": kind, "type": truth.type_name.get(sid, ""), "storey": truth.storey.get(sid, ""),
                     "systems": truth.systems.get(sid, []), "length_m": length, "length_method": method,
                     "mesh_m": mesh.get(guid)})  # fmt: skip
    doc = str(path.relative_to(DATASET))
    out = {"doc": doc, "schema": truth.schema, "unit_m": truth.unit_m, "system_source": truth.system_source,
           "elements": rows, "seconds": round(time.perf_counter() - started, 1)}  # fmt: skip
    target.write_text(json.dumps(out, ensure_ascii=False))
    return out


# ----------------------------------------------------------------------------- items


def _label(kind: str) -> str:
    return ifc_mep.kind_label(kind)


def _length_key(rows: list[dict[str, Any]]) -> MeasureKey | None:
    """The sum of the true lengths, or None when a segment has no true length."""
    if not rows or any(r["length_m"] is None for r in rows):
        return None
    value = sum(r["length_m"] for r in rows)
    return MeasureKey(value=round(value, 3), unit="m", decimals=2) if value > 0 else None


def items_for(  # noqa: C901, PLR0912 - one block per family
    data: dict[str, Any], partition: str, group: str, specs: dict[str, dict[str, Any]]
) -> list[Item]:
    doc = data["doc"]
    rows = data["elements"]
    out: list[Item] = []

    def add(family: str, question: str, key: CountKey | MeasureKey, spec: dict[str, Any]) -> None:
        item_id = "mep-" + hashlib.sha256(f"{doc}|{family}|{question}".encode()).hexdigest()[:14]
        specs[item_id] = spec
        out.append(Item(item_id=item_id, doc=doc, question=question, key=key, source=doc.split("/")[1],
                        family=family, group=group, cell="model query/model", suite=SUITE, partition=partition,  # ty: ignore[invalid-argument-type]
                        origin="derived"))  # fmt: skip

    by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_kind[r["kind"]].append(r)
    for kind, members in sorted(by_kind.items(), key=lambda kv: -len(kv[1])):
        if kind not in ifc_mep.KINDS:
            continue  # an untyped generic class has no plain name to ask for
        label = _label(kind)
        add("count_model", f"How many {label} are there in the model?", CountKey(value=len(members)), {"kind": kind})
        storeys = Counter(r["storey"] for r in members if r["storey"])
        for storey, n in storeys.most_common(2):
            add("count_storey", f"How many {label} are on the storey '{storey}'?", CountKey(value=n),
                {"kind": kind, "storey": storey})  # fmt: skip
        types = Counter(r["type"] for r in members if r["type"])
        for name, n in types.most_common(1):
            if len(types) > 1:
                add("count_type", f"How many {label} of the type '{name}' are there in the model?", CountKey(value=n),
                    {"kind": kind, "type": name})  # fmt: skip
        if kind not in ifc_mep.SEGMENT_KINDS:
            continue
        key = _length_key(members)
        if key is not None:
            add("length_model", f"What is the total length of all {label} in the model, in metres?", key, {"kind": kind})
        for storey, _ in storeys.most_common(3):
            key = _length_key([r for r in members if r["storey"] == storey])
            if key is not None:
                add("length_storey", f"What is the total length of the {label} on the storey '{storey}', in metres?",
                    key, {"kind": kind, "storey": storey})  # fmt: skip
        systems = Counter(s for r in members for s in dict.fromkeys(r["systems"]))
        for system, _ in systems.most_common(3):
            key = _length_key([r for r in members if system in r["systems"]])
            if key is not None:
                add("length_system", f"What is the total length of the {label} in the system '{system}', in metres?",
                    key, {"kind": kind, "system": system})  # fmt: skip
    caps: Counter[str] = Counter()
    kept = []
    for item in out:
        caps[item.family] += 1
        if caps[item.family] <= CAPS.get(item.family, 99):
            kept.append(item)
    return kept


def build_items() -> list[Item]:
    qc = _qcommon()
    split: dict[str, str] = json.loads(SPLIT.read_text())["groups"]
    items: list[Item] = []
    specs: dict[str, dict[str, Any]] = {}
    for path in sorted(CACHE.glob("*.json")):
        data = json.loads(path.read_text())
        group = qc.group_key(data["doc"])
        partition = PARTITION.get(split.get(group, ""), "lock")  # a project outside the split stays held out
        items.extend(items_for(data, partition, group, specs))
    write_items(SUITE, items)
    SPECS.write_text(json.dumps(specs, ensure_ascii=False, indent=0))
    return items


# ----------------------------------------------------------------------------- tool answers (no model)


def answer(index: ifc_mep.MepIndex, spec: dict[str, Any], family: str) -> AnswerRecord:
    """Answer one item with the MEP functions, as the agent would call them: a fixed route per family."""
    from bp.solvers.mep_tools import length_status  # noqa: PLC0415

    kind = spec["kind"]
    if family.startswith("count"):
        found = ifc_mep.select(index, kind, storey=spec.get("storey"))
        if "type" in spec:
            groups = {g.key: g.count for g in ifc_mep.grouped(found, "type")}
            value = groups.get(spec["type"], 0)
        else:
            value = len(found)
        return AnswerRecord(status="answered", value=value, unit="count")
    if family == "length_system":
        found = [e for e in ifc_mep.select(index, kind) if spec["system"] in e.systems]
    else:
        found = ifc_mep.select(index, kind, storey=spec.get("storey"))
    sure, why, _ = length_status(index, found)
    total = sum(e.length_m or 0.0 for e in found)
    if not sure:
        return AnswerRecord(status="abstained", best_estimate=total, abstain=Abstain(
            reason=MissingReason.AMBIGUOUS, detail=why, request="a model with quantity sets"))  # fmt: skip
    return AnswerRecord(status="answered", value=round(total, 2), unit="m")


@functools.cache
def _cache_by_doc() -> dict[str, dict[str, Any]]:
    out = {}
    for path in CACHE.glob("*.json"):
        data = json.loads(path.read_text())
        out[data["doc"]] = data
    return out


def mesh_agreement(index: ifc_mep.MepIndex, doc: str) -> dict[str, Any]:
    """How often the tool's segment length agrees with the OCC extent of the truth, per length source of the tool."""
    cached = _cache_by_doc().get(doc)
    if cached is None:
        return {}
    mesh = {r["guid"]: r.get("mesh_m") for r in cached["elements"]}
    tally: dict[str, Counter[str]] = defaultdict(Counter)
    for e in index.elements:
        reference = mesh.get(e.global_id)
        if e.kind not in ifc_mep.SEGMENT_KINDS or reference is None or e.length_m is None:
            continue
        source = e.length_detail if e.length_source == "geometry" else e.length_source
        ok = abs(e.length_m - reference) <= max(0.02 * reference, 0.01)
        tally[source]["agree" if ok else "differ"] += 1
    return {"mesh_agreement": {k: dict(v) for k, v in tally.items()}}


def bench(partitions: tuple[str, ...] = ("dev", "val", "lock")) -> dict[str, Any]:
    started = time.perf_counter()
    items = [it for it in read_items(SUITE) if it.partition in partitions]
    specs: dict[str, dict[str, Any]] = json.loads(SPECS.read_text())
    by_doc: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        by_doc[item.doc].append(item)
    table: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    misses: list[dict[str, Any]] = []
    per_file: dict[str, dict[str, Any]] = {}
    for doc, group in sorted(by_doc.items()):
        t0 = time.perf_counter()
        try:
            model = ifc_model.open_model(str(DATASET / doc))
        except Exception as exc:  # the agent cannot open this file either: every item abstains
            per_file[doc] = {"error": f"the file does not open: {exc}"}
            for item in group:
                for part in (item.partition, "all"):
                    table[part][item.family]["items"] += 1
                    table[part][item.family]["abstained"] += 1
            continue
        index = ifc_mep.build_index(model)
        check = ifc_mep.length_check(index)
        per_file[doc] = {"elements": len(index.elements), "length_check": check.status, "check_note": check.note,
                         "index_seconds": round(time.perf_counter() - t0, 1)} | mesh_agreement(index, doc)  # fmt: skip
        for item in group:
            spec = specs[item.item_id]
            record = answer(index, spec, item.family)
            outcome = score_item(item.key, record).outcome.value
            for part in (item.partition, "all"):
                table[part][item.family]["items"] += 1
                table[part][item.family][outcome] += 1
            if outcome != "correct":
                misses.append({"doc": doc, "family": item.family, "question": item.question, "outcome": outcome,
                               "key": item.key.model_dump(mode="json"), "value": record.value,
                               "estimate": record.best_estimate})  # fmt: skip
    result = {
        "partitions": list(partitions),
        "scores": {part: {fam: dict(c) | {"score": round((c["correct"] - c["wrong"] - c["error"]) / c["items"], 3)}
                          for fam, c in sorted(fams.items())} for part, fams in sorted(table.items())},
        "files": per_file, "misses": misses[:200], "seconds": round(time.perf_counter() - started, 1),
    }  # fmt: skip
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    return result


def main(argv: list[str]) -> None:
    command = argv[0] if argv else "bench"
    if command == "files":
        print("\n".join(str(p) for p in mep_files()))
    elif command == "facts":
        paths = [Path(a) for a in argv[1:]] or mep_files()
        for path in paths:
            data = facts(path)
            print(path.name, len(data["elements"]), data["seconds"], flush=True)
    elif command == "items":
        found = build_items()
        print(len(found), dict(Counter((it.partition, it.family) for it in found)))
    else:
        print(json.dumps(bench()["scores"], indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
