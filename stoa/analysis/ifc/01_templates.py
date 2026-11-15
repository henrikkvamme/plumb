# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Template families of the ifc_models and ifc_bench questions.

Replaces quoted names with {Q} and numbers with {N}, then groups.
Writes out/templates.json and prints a compact table.
Note: the family split here is coarse (it puts the 64 wall side-area questions under area_total_storey).
05_probe_models.py has the exact family parser. Language codes are only meaningful for ifc_models;
all 820 ifc_bench questions are English (03_bench_leakage.py).
"""
import collections
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "data" / "junction-dataset"
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

QUOTE = re.compile(r"'[^']*'|„[^“]*“|«[^»]*»|\"[^\"]*\"|“[^”]*”|‘[^’]*’|”[^”]*”")


def template(q: str) -> str:
    return QUOTE.sub("{Q}", q)


# Family by keywords in the English and local texts, decided by the unit and a scope word.
def family(r) -> str:
    q = r["question"].lower()
    t = r["type"]
    model_scope = any(w in q for w in ["model", "modell", "modèle", "modelo", "modello", "modelul", "mudel", "modellen", "het model"])
    if t == "area":
        if any(w in q for w in ["total", "gesamt", "totale", "kokku", "samlede", "total", "suma", "totală", "summa"]) or "all" in q:
            return "area_total_storey"
        return "area_room"
    if t == "volume":
        return "volume_slabs" if any(w in q for w in ["slab", "decke", "vloer", "plaat", "losa", "dæk", "placă", "plăc", "plaad", "geschossdecke"]) else "volume_walls"
    if t == "length":
        return "length_walls"
    if t == "count":
        return "count_model" if model_scope else "count_storey"
    return t


def lang(q: str) -> str:
    ql = q.lower()
    tests = [
        ("en", ["what is", "how many"]), ("de", ["wie ", "geschoss", "anzahl"]), ("nl", ["wat is", "hoeveel"]),
        ("et", ["kui ", "mitu "]), ("es", ["¿"]), ("ro", ["care ", "câte", "câți"]), ("da", ["hvor ", "hvad", "antal"]),
        ("it", ["qual ", "quant"]), ("fr", ["quel", "combien"]), ("pl", ["ile ", "jaka"]),
    ]
    for code, keys in tests:
        if any(k in ql for k in keys):
            return code
    return "?"


def main():
    rows = [json.loads(l) for l in open(ROOT / "questions.jsonl")]
    rows = [r for r in rows if r["path"].startswith(("data/ifc_models/", "data/ifc_bench/"))]
    res = {}
    for src in ["ifc_models", "ifc_bench"]:
        rs = [r for r in rows if r["path"].startswith(f"data/{src}/")]
        tpl = collections.Counter(template(r["question"]) for r in rs)
        fam = collections.Counter((family(r), r["path"].rsplit(".", 1)[1]) for r in rs) if src == "ifc_models" else None
        lg = collections.Counter(lang(r["question"]) for r in rs) if src == "ifc_models" else collections.Counter({"en": len(rs)})
        res[src] = {
            "rows": len(rs),
            "n_templates": len(tpl),
            "templates": tpl.most_common(),
            "families": {f"{a}|{b}": c for (a, b), c in fam.most_common()} if fam else None,
            "langs": dict(lg.most_common()),
        }
        if src == "ifc_models":
            # language per family
            fl = collections.Counter((family(r), lang(r["question"])) for r in rs)
            res[src]["family_lang"] = {f"{a}|{b}": c for (a, b), c in sorted(fl.items())}
            unknown = [r["question"] for r in rs if lang(r["question"]) == "?"][:20]
            res[src]["unknown_lang_examples"] = unknown
    (OUT / "templates.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    for src, v in res.items():
        print(src, "rows", v["rows"], "templates", v["n_templates"], "langs", v["langs"])
        if v["families"]:
            print(" families", v["families"])


if __name__ == "__main__":
    main()
