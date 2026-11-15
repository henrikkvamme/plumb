"""Benchmark the IFC contractor quantities (`bp.tools.quantities_ifc`) against two other sources.

1. Public keys: the ifc_bench questions on wall length (exterior, interior), door and window width (min, max, mean)
   and skirting. The number is read from the free-text answer. A key that says the value is not in the model counts
   as "no value": our tool is right there only when it gives no value (abstains).
2. Axis vs Qto: for each wall with both a Qto_WallBaseQuantities Length and an Axis curve, the relative difference.
3. Footprint vs Qto: for each space with a Qto perimeter, the edge of its plan footprint against that perimeter.

The scoring tolerance is the harness rule for measures: 2% relative, or 1 cm absolute for widths (keys round to cm).
Writes experiments/tools/quantities-ifc.json. Run: uv run python -m bp.toolbench.quantities_ifc [--max-mb N]
"""

from __future__ import annotations

import contextlib
import json
import re
import sys
import time
from collections import defaultdict
from typing import Any

from bp.paths import DATASET, EXPERIMENTS
from bp.toolbench.quantities import quantiles
from bp.tools import ifc_model as im
from bp.tools import quantities_ifc as qi

OUT = EXPERIMENTS / "tools" / "quantities-ifc.json"
BENCH = DATASET / "data" / "ifc_bench"
REL_TOL = 0.02
WIDTH_TOL_M = 0.01
NO_VALUE = re.compile(r"not available|no .*data|cannot be determined", re.IGNORECASE)
NUMBER = r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(mm|m\b|meters|metres)"

# (quantity, question pattern, answer pattern). The answer pattern finds the number for that quantity.
CASES: list[tuple[str, re.Pattern[str], re.Pattern[str]]] = [
    ("exterior_wall_m", re.compile(r"length.*(exterior|outside).*wall|(exterior|outside) wall.*length|length (of )?exterior", re.IGNORECASE),
     re.compile(r"exterior[^0-9]{0,40}?" + NUMBER, re.IGNORECASE)),
    ("interior_wall_m", re.compile(r"length.*(interior|inside).*wall|(interior|inside) wall.*length|exterior and interior|compared interior|vs interior", re.IGNORECASE),
     re.compile(r"interior[^0-9]{0,40}?" + NUMBER, re.IGNORECASE)),
    ("door_mean_m", re.compile(r"average door width", re.IGNORECASE), re.compile(r"average[^0-9]{0,40}?" + NUMBER, re.IGNORECASE)),
    ("door_max_m", re.compile(r"(largest|widest|maximum).*door|door.*(maximum|largest)", re.IGNORECASE),
     re.compile(r"(?:largest|widest|maximum|is)[\s\S]{0,90}?" + NUMBER, re.IGNORECASE)),
    ("door_min_m", re.compile(r"(narrowest|smallest|minimum).*door|door.*minimum", re.IGNORECASE),
     re.compile(r"(?:smallest|shortest|minimum|narrowest)[\s\S]{0,90}?" + NUMBER, re.IGNORECASE)),
    ("window_max_m", re.compile(r"(largest|widest|maximum).*window", re.IGNORECASE),
     re.compile(r"(?:largest|widest|maximum)[\s\S]{0,90}?" + NUMBER, re.IGNORECASE)),
    ("window_min_m", re.compile(r"(narrowest|smallest|minimum).*window", re.IGNORECASE),
     re.compile(r"(?:smallest|shortest|minimum|narrowest)[\s\S]{0,90}?" + NUMBER, re.IGNORECASE)),
    ("skirting_m", re.compile(r"skirting|baseboard", re.IGNORECASE), re.compile(NUMBER, re.IGNORECASE)),
]  # fmt: skip
SKIP = re.compile(r"top 5|five largest|different window widths|insulation|surface|area", re.IGNORECASE)


def _metres(text: str, unit: str) -> float:
    value = float(text.replace(",", ""))
    return value / 1000.0 if unit.lower() == "mm" else value


def keys() -> dict[str, dict[str, float | None]]:
    """Per ifc_bench file: quantity -> the key value in metres, or None when the key says it is not in the model."""
    out: dict[str, dict[str, float | None]] = defaultdict(dict)
    for line in (DATASET / "questions.jsonl").open():
        row = json.loads(line)
        if not row["path"].startswith("data/ifc_bench/") or SKIP.search(row["question"]):
            continue
        answer = str(row["answer"])
        for quantity, asks, finds in CASES:
            if not asks.search(row["question"]):
                continue
            if NO_VALUE.search(answer):
                out[row["path"]].setdefault(quantity, None)
                continue
            if quantity.startswith("door") and "door" not in row["question"].lower():
                continue
            if found := finds.search(answer):
                out[row["path"]][quantity] = round(_metres(found.group(1), found.group(2)), 4)
    return dict(out)


def ours(model: im.IfcModel) -> dict[str, float | None]:
    totals = qi.wall_totals(qi.wall_rows(model), None)
    doors = [r.width_m for r in qi.opening_rows(model, "door") if r.width_m is not None]
    windows = [r.width_m for r in qi.opening_rows(model, "window") if r.width_m is not None]
    nominal = [r.nominal_width_m for r in qi.opening_rows(model, "door") if r.nominal_width_m is not None]
    spaces = qi.space_rows(model)
    skirting = [s.baseboard_m for s in spaces if s.baseboard_m is not None]
    return {
        "total_wall_m": totals.total_m,
        "exterior_wall_m": totals.exterior_m,
        "interior_wall_m": totals.interior_m,
        "door_mean_m": round(sum(doors) / len(doors), 3) if doors else None,
        "door_max_m": max(doors, default=None),
        "door_min_m": min(doors, default=None),
        "window_max_m": max(windows, default=None),
        "window_min_m": min(windows, default=None),
        "door_nominal_mean_m": round(sum(nominal) / len(nominal), 3) if nominal else None,
        "door_nominal_max_m": max(nominal, default=None),
        "door_nominal_min_m": min(nominal, default=None),
        "skirting_m": round(sum(skirting), 3) if skirting and len(skirting) == len(spaces) else None,
    }


def _outcome(quantity: str, key: float | None, got: float | None) -> str:
    if got is None:
        return "abstained"
    if key is None:
        return "wrong"
    if quantity.startswith(("door", "window")):
        return "right" if abs(got - key) <= WIDTH_TOL_M + 1e-9 else "wrong"
    return "right" if abs(got - key) <= REL_TOL * abs(key) else "wrong"


def _axis_vs_qto(model: im.IfcModel) -> list[float]:
    elements, _ = im.category_elements(model, "wall")
    out = []
    for e in elements:
        qto = im.qto_value(e, ("Length",))
        axis = None
        with contextlib.suppress(Exception):
            axis = qi.axis_length(e)
        if qto and axis:
            out.append(abs(axis - qto) / qto)
    return out


def _footprint_vs_qto(model: im.IfcModel) -> list[float]:
    spaces = im.by_type(model, "IfcSpace")
    with_qto = {s.GlobalId: q * model.length_scale for s in spaces
                if (q := im.qto_value(s, ("NetPerimeter", "GrossPerimeter")))}  # fmt: skip
    if not with_qto:
        return []
    shapes = qi._footprints(model, [s for s in spaces if s.GlobalId in with_qto])  # noqa: SLF001 - bench of the same module
    return [abs(shapes[g].length - p) / p for g, p in with_qto.items() if g in shapes and p > 0]


def bench(max_mb: float) -> dict[str, Any]:
    want = keys()
    files = sorted(p for p in BENCH.glob("*_arc.ifc"))
    table: dict[str, dict[str, int]] = defaultdict(lambda: {"right": 0, "wrong": 0, "abstained": 0})
    nominal_table: dict[str, dict[str, int]] = defaultdict(lambda: {"right": 0, "wrong": 0, "abstained": 0})
    rows, axis, footprint, skipped = [], [], [], []
    for path in files:
        doc = f"data/ifc_bench/{path.name}"
        if path.stat().st_size > max_mb * 1e6:
            skipped.append(path.name)
            continue
        t0 = time.monotonic()
        model = im.open_model(str(path))
        got = ours(model)
        a, f = _axis_vs_qto(model), _footprint_vs_qto(model)
        axis += a
        footprint += f
        compared = {}
        for quantity, key in want.get(doc, {}).items():
            outcome = _outcome(quantity, key, got.get(quantity))
            table[quantity][outcome] += 1
            compared[quantity] = {"key": key, "ours": got.get(quantity), "outcome": outcome}
            if quantity.startswith("door_") and (alt := got.get(quantity.replace("door_", "door_nominal_"))):
                compared[quantity]["nominal"] = alt
                compared[quantity]["nominal_outcome"] = _outcome(quantity, key, alt)
                nominal_table[quantity][_outcome(quantity, key, alt)] += 1
        rows.append({"file": path.name, "seconds": round(time.monotonic() - t0, 1), "ours": got,
                     "compared": compared, "walls_axis_vs_qto": len(a), "spaces_footprint_vs_qto": len(f)})  # fmt: skip
        print(path.name, json.dumps(compared), file=sys.stderr)
    return {
        "rule": f"measures right within {REL_TOL:.0%}, widths within {WIDTH_TOL_M} m; a key with no value is right "
        "only when we abstain",
        "keys_vs_ours": dict(table),
        "door_keys_vs_nominal_width": dict(nominal_table),
        "wall_axis_vs_qto_rel": quantiles(axis),
        "space_footprint_vs_qto_rel": quantiles(footprint),
        "skipped_large": skipped,
        "files": rows,
    }


def main() -> None:
    max_mb = 100.0
    if "--max-mb" in sys.argv:
        max_mb = float(sys.argv[sys.argv.index("--max-mb") + 1])
    report = bench(max_mb)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: report[k] for k in ("keys_vs_ours", "door_keys_vs_nominal_width", "wall_axis_vs_qto_rel", "space_footprint_vs_qto_rel")},
                     indent=1))  # fmt: skip


if __name__ == "__main__":
    main()
