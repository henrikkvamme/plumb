# /// script
# requires-python = ">=3.11"
# dependencies = ["pymupdf==1.25.5"]
# ///
"""Probe: is the reference answer printed verbatim in the drawing's text layer?

For each numeric question on a PDF (swiss_dwellings, ifc_models plans, opening_design), search the
PDF text for the answer written with 0-2 decimals, dot or comma. A hit means the answer can be
read, not measured. Counts are skipped for small values (a "2" is everywhere); areas and lengths
are checked. Writes analysis/questions/out/probe_text_answer_leak.json.
Run: uv run probe_text_answer_leak.py
"""

from __future__ import annotations

import re
from collections import defaultdict

import pymupdf

from qcommon import FULL, OUT_DIR, STOA, annotate, families, load, write_json


def forms(x: float) -> set[str]:
    out = set()
    for d in (0, 1, 2):
        s = f"{x:.{d}f}"
        if abs(float(s) - x) <= 0.005 + 1e-9:
            out.add(s)
            out.add(s.replace(".", ","))
    return out


def main() -> None:
    rows = annotate(load(FULL))
    fam = families(rows)
    cache: dict[str, set[str]] = {}
    hits = defaultdict(lambda: [0, 0])
    ex = defaultdict(list)
    for r in rows:
        if not r["path"].endswith(".pdf") or r["type"] not in ("area", "volume", "length"):
            continue
        if r["_lang"] != "en":
            continue
        p = r["path"]
        if p not in cache:
            doc = pymupdf.open(STOA / "data" / "junction-dataset" / p)
            text = " ".join(pg.get_text() for pg in doc)
            cache[p] = set(re.findall(r"\d+(?:[.,]\d+)?", text))
        key = f"{r['_src']}|{fam[(r['_src'], r['_tpl'])]}|{r['_tpl'][:60]}"
        hits[key][0] += 1
        if forms(float(r["answer"])) & cache[p]:
            hits[key][1] += 1
            if len(ex[key]) < 3:
                ex[key].append([p, r["question"][:100], r["answer"]])
    out = {k: {"checked": n, "answer_in_text": h, "rate": round(h / n, 4), "examples": ex[k]} for k, (n, h) in sorted(hits.items())}
    write_json(OUT_DIR / "probe_text_answer_leak.json", out)
    for k, v in out.items():
        print(v["answer_in_text"], "/", v["checked"], v["rate"], k)


if __name__ == "__main__":
    main()
