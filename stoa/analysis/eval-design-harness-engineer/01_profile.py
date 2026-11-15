"""Profile questions.jsonl: sources, types, units, answer value kinds, groups. Compact output."""
import json, sys, re, collections, hashlib, os
ROOT = "./stoa/data/junction-dataset"
rows = []
blank = 0
with open(f"{ROOT}/questions.jsonl", "rb") as f:
    raw = f.read()
print("sha256", hashlib.sha256(raw).hexdigest(), "bytes", len(raw))
for line in raw.decode("utf-8").split("\n"):
    if not line.strip():
        blank += 1
        continue
    rows.append(json.loads(line))
print("rows", len(rows), "blank_lines", blank)
C = collections.Counter
src = lambda r: r["path"].split("/")[1]
print("keys", C(tuple(sorted(r.keys())) for r in rows))
print("by_source", dict(C(src(r) for r in rows)))
print("by_type", dict(C(r["type"] for r in rows)))
print("by_source_type", sorted(C((src(r), r["type"]) for r in rows).items()))
print("by_source_unit", sorted(C((src(r), r["type"], r["unit"]) for r in rows).items()))
print("answer_pytype", sorted(C((src(r), r["type"], type(r["answer"]).__name__) for r in rows).items()))
print("ext_by_source", sorted(C((src(r), os.path.splitext(r["path"])[1].lower()) for r in rows).items()))
dr = collections.defaultdict(set)
for r in rows: dr[src(r)].add(r["path"])
print("drawings_with_q", {k: len(v) for k, v in dr.items()}, "total", sum(len(v) for v in dr.values()))
qpd = C(r["path"] for r in rows)
for s in dr:
    v = sorted(qpd[p] for p in dr[s])
    print("q_per_drawing", s, "min", v[0], "med", v[len(v)//2], "max", v[-1])
# exact duplicates
d = C((r["path"], r["question"]) for r in rows)
print("dup_path_question", sum(1 for v in d.values() if v > 1))
# conflicting dup answers
da = collections.defaultdict(set)
for r in rows: da[(r["path"], r["question"])].add(json.dumps(r["answer"]))
print("dup_conflicting", sum(1 for v in da.values() if len(v) > 1))
# missing files
miss = [p for s in dr for p in dr[s] if not os.path.exists(f"{ROOT}/{p}")]
print("paths_missing_on_disk", len(miss), miss[:3])
# zero / negative numeric answers by type
for t in ["area", "length", "volume", "count"]:
    v = [r["answer"] for r in rows if r["type"] == t and isinstance(r["answer"], (int, float))]
    print("num", t, "n", len(v), "zero", sum(1 for x in v if x == 0), "neg", sum(1 for x in v if x < 0), "nonint", sum(1 for x in v if float(x) != int(x)), "min", min(v), "max", max(v))
# decimals of reference for measures
def dec(x):
    s = repr(x)
    return len(s.split(".")[1]) if "." in s and "e" not in s else 0
print("decimals_area", sorted(C((src(r), dec(r["answer"])) for r in rows if r["type"] == "area" and isinstance(r["answer"], (int, float))).items()))
print("decimals_len_vol", sorted(C((src(r), r["type"], dec(r["answer"])) for r in rows if r["type"] in ("length", "volume") and isinstance(r["answer"], (int, float))).items()))
# small-area: where 2% tolerance is below the rounding step
for s in ["swiss_dwellings", "ifc_models", "opening_design"]:
    v = [r["answer"] for r in rows if src(r) == s and r["type"] == "area" and isinstance(r["answer"], (int, float))]
    if not v: continue
    v.sort()
    print("area_dist", s, "n", len(v), "p1", v[len(v)//100], "p10", v[len(v)//10], "med", v[len(v)//2], "p90", v[9*len(v)//10], "max", v[-1],
          "tol_lt_0.05", sum(1 for x in v if 0.02 * x < 0.05), "tol_lt_0.005", sum(1 for x in v if 0.02 * x < 0.005))
