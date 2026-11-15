# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Classify the 820 ifc_bench questions by answer kind and by how checkable the reference is.

Kind (from question and reference text, first rule wins):
  unavailable   reference says the data is not in the model / must be estimated
  yes_no        reference starts with yes/no
  metadata      software, schema, project, site, location, author
  single_number reference holds exactly one number (with or without a unit)
  list_counts   reference is a list or breakdown with numbers (types and counts, spaces and areas ...)
  list_names    reference is a list without numbers (materials, types)
  explanation   everything else (free prose)
Checkability:
  exact   a deterministic check is possible (numbers within tolerance, set of names, yes/no)
  partial a deterministic check covers part of the answer (numbers inside prose)
  judge   only a reader or a judge model can decide
Also joins the public IFC-Bench category (1-4) from out/bench_leakage.json (run 03 first).
Writes out/bench_kinds.json.
"""
import collections
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DS = HERE.parents[1] / "data" / "junction-dataset"
OUT = HERE / "out"
NUM = re.compile(r"(?<![\w.])[-+]?\d+(?:[.,]\d+)?(?![\w])")


def kind(q, a):
    al = a.lower().strip()
    ql = q.lower()
    if re.search(r"not (directly |explicitly |explicitely )?(available|stored|provided|included|present|defined|contain)|cannot be (exactly )?(calculated|determined)|no information|estimated|estimate|assum", al):
        return "unavailable"
    if re.match(r"^(yes|no)\b", al):
        return "yes_no"
    if re.search(r"software|program|ifc (schema|standard|version)|schema|project (name|information)|site|location|latitude|author|organi[sz]ation|modell?ing standard", ql):
        return "metadata"
    nums = NUM.findall(a)
    lines = [l for l in a.splitlines() if l.strip()]
    listy = len(lines) >= 3 or a.count(" - ") >= 2 or a.count("•") >= 2
    if len(nums) == 1 and not listy:
        return "single_number"
    if listy and nums:
        return "list_counts"
    if listy:
        return "list_names"
    if nums:
        return "short_with_numbers"
    return "explanation"


CHECK = {"unavailable": "judge", "yes_no": "exact", "metadata": "exact", "single_number": "exact",
         "list_counts": "partial", "list_names": "partial", "short_with_numbers": "partial", "explanation": "judge"}


def main():
    rows = [json.loads(l) for l in open(DS / "questions.jsonl") if '"data/ifc_bench/' in l]
    leak = {(r["file"], r["q"]): r for r in json.load(open(OUT / "bench_leakage.json"))["rows"]}
    res = []
    for r in rows:
        fn = r["path"].split("/")[-1]
        k = kind(r["question"], r["answer"])
        lr = leak.get((fn, r["question"]), {})
        res.append({"file": fn, "q": r["question"], "a": r["answer"], "kind": k, "check": CHECK[k], "cat": lr.get("pub_cat"),
                    "n_numbers": len(NUM.findall(r["answer"])), "answer_chars": len(r["answer"])})
    kinds = collections.Counter(x["kind"] for x in res)
    check = collections.Counter(x["check"] for x in res)
    kc = collections.Counter((x["kind"], x["cat"]) for x in res)
    lens = sorted(x["answer_chars"] for x in res)
    summ = {
        "n": len(res), "kinds": dict(kinds.most_common()), "checkability": dict(check.most_common()),
        "kind_by_category": {f"{k}|cat{c}": v for (k, c), v in sorted(kc.items(), key=str)},
        "answer_chars_median": lens[len(lens) // 2], "answer_chars_p90": lens[int(0.9 * len(lens))],
        "examples": {k: [(x["file"], x["q"][:120], x["a"][:160].replace("\n", " ")) for x in res if x["kind"] == k][:4] for k in kinds},
    }
    json.dump({"summary": summ, "rows": res}, open(OUT / "bench_kinds.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in summ.items() if k != "examples"}, indent=0))


if __name__ == "__main__":
    main()
