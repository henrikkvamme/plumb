# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Compare Stoa's ifc_bench questions with the public IFC-Bench v2 CSV.

Needs stoa/data/external/ifc-bench/ifc-bench-v2.csv (Hugging Face sylvainHellin/ifc-bench, CC BY 4.0)
and the eval split CSV. Matches each Stoa row to a public row by (model file, normalised question).
Also compares the answers, compares the IFC files byte for byte (md5) where the public file is local,
and classifies each Stoa question by kind and checkability.
Writes out/bench_leakage.json.
"""
import collections
import csv
import difflib
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
STOA = HERE.parents[1]
DS = STOA / "data" / "junction-dataset"
EXT = STOA / "data" / "external" / "ifc-bench"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)


def norm(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return re.sub(r"[^\w ]", "", s)


def kind(q: str, a: str) -> str:
    ql = q.lower()
    al = a.lower()
    if re.match(r"^(is|are|does|do|can|has|have|was|were|è|sono|ci sono|esiste)\b", ql):
        return "yes_no"
    if any(w in ql for w in ["why", "explain", "describe", "general composition", "typical", "how is", "perché", "descriv", "strategy", "what type of structural system", "assess", "estimate", "embodied", "complian", "accessib"]):
        return "explanation_or_judgement"
    if any(w in ql for w in ["compare", "difference", "largest", "smallest", "highest", "lowest", "most", "least", "greatest", "maximum", "minimum", "top ", "three", "biggest", "più grand", "maggior", "minor"]):
        return "superlative_or_comparison"
    if any(w in ql for w in ["breakdown", "list", "which", "what are", "types", "each", "distribution", "by level", "by floor", "per ", "quali", "elenca", "tipi"]):
        return "list_or_breakdown"
    if any(w in ql for w in ["how many", "number of", "total", "area", "volume", "length", "width", "height", "thickness", "quanti", "quante", "superficie", "numero"]):
        return "single_quantity"
    if any(w in ql for w in ["software", "program", "schema", "project name", "author", "location", "address", "latitude", "standard", "ifc version", "name of"]):
        return "metadata"
    return "other"


def lang(q: str) -> str:
    if re.search(r"\b(quanti|quante|quali|qual|del|della|nel|nella|sono|edificio|piano|elenca|pareti|porte)\b", q.lower()):
        return "it"
    return "en"


def main():
    pub = list(csv.DictReader(open(EXT / "ifc-bench-v2.csv", encoding="utf-8")))
    split = {r["id"]: r["split"] for r in csv.DictReader(open(EXT / "eval-split-hellin2026.csv"))}
    pub_by_file = collections.defaultdict(list)
    for r in pub:
        pub_by_file[f"{r['project']}_{r['ifc_model']}.ifc"].append(r)
    stoa = [json.loads(l) for l in open(DS / "questions.jsonl") if '"data/ifc_bench/' in l]
    res_rows = []
    stats = collections.Counter()
    for s in stoa:
        fn = s["path"].split("/")[-1]
        cands = pub_by_file.get(fn, [])
        nq = norm(s["question"])
        exact = [c for c in cands if norm(c["question"]) == nq]
        best, ratio = None, 0.0
        if exact:
            best, ratio = exact[0], 1.0
        else:
            for c in cands:
                r = difflib.SequenceMatcher(None, nq, norm(c["question"])).ratio()
                if r > ratio:
                    best, ratio = c, r
        ans_eq = best is not None and norm(best["ground_truth"]) == norm(s["answer"])
        ans_ratio = difflib.SequenceMatcher(None, norm(s["answer"]), norm(best["ground_truth"])).ratio() if best else 0
        k = kind(s["question"], s["answer"])
        rec = {
            "file": fn, "q": s["question"], "a": s["answer"][:300], "match_ratio": round(ratio, 3),
            "pub_id": best["id"] if best else None, "pub_q": best["question"] if best else None,
            "pub_cat": best["category"] if best else None, "pub_split": split.get(best["id"]) if best else None,
            "answer_identical": ans_eq, "answer_ratio": round(ans_ratio, 3), "kind": k, "lang": lang(s["question"]),
        }
        res_rows.append(rec)
        stats["q_exact"] += ratio == 1.0
        stats["q_ge_0.9"] += ratio >= 0.9
        stats["ans_identical"] += ans_eq
        stats["ans_ge_0.9"] += ans_ratio >= 0.9
    n = len(stoa)
    cat = collections.Counter(r["pub_cat"] for r in res_rows if r["match_ratio"] == 1.0)
    spl = collections.Counter(r["pub_split"] for r in res_rows if r["match_ratio"] == 1.0)
    kinds = collections.Counter(r["kind"] for r in res_rows)
    langs = collections.Counter(r["lang"] for r in res_rows)
    # which public questions are not in Stoa (for the same files)
    stoa_files = {s["path"].split("/")[-1] for s in stoa}
    matched_ids = {r["pub_id"] for r in res_rows if r["match_ratio"] == 1.0}
    pub_same_files = [r for r in pub if f"{r['project']}_{r['ifc_model']}.ifc" in stoa_files]
    # md5 of public files fetched locally (optional)
    md5 = {}
    for p in (EXT / "projects").glob("*/*.ifc") if (EXT / "projects").exists() else []:
        local = DS / "data" / "ifc_bench" / f"{p.parent.name}_{p.stem}.ifc"
        if local.exists():
            md5[local.name] = hashlib.md5(p.read_bytes()).hexdigest() == hashlib.md5(local.read_bytes()).hexdigest()
    summary = {
        "stoa_rows": n, "public_rows": len(pub), "public_files": len(pub_by_file), "stoa_files": len(stoa_files),
        "stats": dict(stats), "matched_category": dict(cat), "matched_split": dict(spl),
        "public_rows_on_stoa_files": len(pub_same_files), "public_rows_on_stoa_files_not_in_stoa": len([r for r in pub_same_files if r["id"] not in matched_ids]),
        "public_files_not_in_stoa": sorted(set(pub_by_file) - stoa_files),
        "kinds": dict(kinds), "langs": dict(langs),
        "kind_by_cat": {f"{k}|{c}": v for (k, c), v in sorted(collections.Counter((r["kind"], r["pub_cat"]) for r in res_rows).items(), key=str)},
        "md5_identical": md5,
    }
    non_exact = [r for r in res_rows if r["match_ratio"] < 1.0]
    ans_diff = [r for r in res_rows if r["match_ratio"] == 1.0 and not r["answer_identical"]]
    json.dump({"summary": summary, "non_exact": non_exact[:40], "answer_diff": ans_diff[:40], "rows": res_rows}, open(OUT / "bench_leakage.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps(summary, ensure_ascii=False, indent=0))


if __name__ == "__main__":
    main()
