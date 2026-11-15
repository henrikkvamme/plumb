# /// script
# requires-python = ">=3.11"
# dependencies = ["pymupdf==1.25.5"]
# ///
"""Probe: can the PDF text layer alone answer two swiss_dwellings count families?

Hypothesis: the renderer prints each room label and each apartment tag as text, so
  "How many rooms labelled X"  = number of text lines equal to X above the title block,
  "How many apartments"        = number of apartment tags ("Whg. A", ...) above the title block.
If so, a public score on these families measures text extraction, not drawing reading.

Writes analysis/questions/out/probe_swiss_text.json (agreement rate and disagreements).
Run: uv run probe_swiss_text.py
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

import pymupdf

from qcommon import FULL, OUT_DIR, STOA, annotate, load, write_json

TITLE_WORDS = {"Legende", "Légende", "Legenda", "Legend", "Projekt", "Projet", "Progetto", "Project"}
TAG = re.compile(r"^[A-Za-zÀ-ÿ]{2,6}\.\s?[A-Z0-9]{1,3}$")


def lines(pdf):
    page = pymupdf.open(pdf)[0]
    out = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            out.append((ln["bbox"][1], " ".join(s["text"] for s in ln["spans"]).strip()))
    cut = min((y for y, t in out if t in TITLE_WORDS), default=1e9)
    return [t for y, t in out if y < cut - 5]


def main() -> None:
    rows = [r for r in annotate(load(FULL)) if r["_src"] == "swiss_dwellings" and r["_lang"] == "en"]
    by_path = defaultdict(list)
    for r in rows:
        by_path[r["path"]].append(r)
    res = {"label_count": [0, 0], "apartments": [0, 0]}
    bad = {"label_count": [], "apartments": []}
    for path, rs in sorted(by_path.items()):
        txt = lines(STOA / "data" / "junction-dataset" / path)
        c = Counter(txt)
        tags = sum(1 for t in txt if TAG.match(t))
        for r in rs:
            if r["type"] != "count":
                continue
            if r["_tpl"].startswith("How many rooms labelled"):
                k, pred = "label_count", c[r["_slots"][0][1]]
            elif r["_tpl"].startswith("How many apartments"):
                k, pred = "apartments", tags
            else:
                continue
            res[k][0] += 1
            if pred == r["answer"]:
                res[k][1] += 1
            elif len(bad[k]) < 12:
                bad[k].append({"path": path, "question": r["question"], "answer": r["answer"], "text_count": pred})
    out = {
        k: {"checked": n, "agree": a, "rate": round(a / n, 4), "disagreements": bad[k]}
        for k, (n, a) in res.items()
    }
    write_json(OUT_DIR / "probe_swiss_text.json", out)
    for k, v in out.items():
        print(k, v["agree"], "/", v["checked"], v["rate"])


if __name__ == "__main__":
    main()
