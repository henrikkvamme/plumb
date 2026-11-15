# /// script
# requires-python = ">=3.11"
# dependencies = ["pymupdf==1.26.5"]
# ///
"""Probe: do simple vector counts on a sheet reproduce the storey count answers?

  walls   : number of dark-grey (0.29) filled paths (cut elements: walls and columns are drawn the same way)
  doors   : number of quarter-circle swing arcs (paths with a Bezier curve and no fill)
  windows : not drawn as a distinct symbol class, so not probed
Compares with the storey-scope count questions on the same sheet. Writes out/pdf_counts.json.
"""
import collections
import json
import re
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
DS = HERE.parents[1] / "data" / "junction-dataset"
MD = DS / "data" / "ifc_models"
OUT = HERE / "out"
WORDS = {
    "wall": ["wall", "wände", "wanden", "muros", "vægge", "seina", "ścian", "muri"],
    "door": ["door", "türen", "deuren", "puertas", "døre", " ust ", "drzwi"],
    "column": ["column", "stützen", "kolommen", "pilares", "søjler", "posti", "stâlpi"],
}


def main():
    qs = [json.loads(l) for l in open(DS / "questions.jsonl") if '"data/ifc_models/' in l and ".pdf" in l]
    res = []
    for r in qs:
        ql = " " + r["question"].lower() + " "
        if r["type"] != "count" or any(w in ql for w in ["model", "mudel"]):
            continue
        cls = next((c for c, ws in WORDS.items() if any(w in ql for w in ws)), None)
        if not cls:
            continue
        page = pymupdf.open(MD / r["path"].split("/")[-1])[0]
        dr = page.get_drawings()
        grey = sum(1 for d in dr if d.get("fill") and all(abs(a - 0.29) < 0.02 for a in d["fill"]))
        arcs = sum(1 for d in dr if not d.get("fill") and any(it[0] == "c" for it in d["items"]))
        est = {"wall": grey, "column": None, "door": arcs}[cls]
        res.append({"pdf": r["path"].split("/")[-1], "cls": cls, "ref": r["answer"], "est": est, "grey": grey, "arcs": arcs})
    summ = {}
    for cls in WORDS:
        rs = [x for x in res if x["cls"] == cls and x["est"] is not None]
        if rs:
            summ[cls] = {"n": len(rs), "exact": sum(x["est"] == x["ref"] for x in rs),
                         "within_10pct": sum(abs(x["est"] - x["ref"]) <= 0.1 * max(1, x["ref"]) for x in rs),
                         "examples": [(x["pdf"][:45], x["ref"], x["est"]) for x in rs[:10]]}
    json.dump({"summary": summ, "rows": res}, open(OUT / "pdf_counts.json", "w"), indent=1)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "examples"} for k, v in summ.items()}))
    for k, v in summ.items():
        print(k, v["examples"])


if __name__ == "__main__":
    main()
