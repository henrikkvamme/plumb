"""Label-noise probes that need no solver: duplicate images with different answers, internal consistency, abstaining references."""
import sys, os, json, collections, re
sys.path.insert(0, os.path.dirname(__file__))
from common import load
rows = load(sys.argv[1]); cl = json.load(open(sys.argv[2]))
# 1. CubiCasa near-duplicate images: do the same questions get the same answer?
ans = collections.defaultdict(dict)
for r in rows:
    if r["source"] == "cubicasa5k" and r["lang"] == "en": ans[os.path.basename(r["path"])][r["family"]] = r["answer"]
members = collections.defaultdict(list)
for f, rep in cl.items(): members[rep].append(f)
tot = collections.Counter(); dis = collections.Counter(); onlyone = 0
for rep, fs in members.items():
    if len(fs) != 2: continue
    a, b = ans[fs[0]], ans[fs[1]]
    onlyone += len(set(a) ^ set(b))
    for fam in set(a) & set(b):
        tot[fam] += 1; dis[fam] += int(a[fam] != b[fam])
print("cubicasa duplicate pairs: shared questions", sum(tot.values()), "different answers", sum(dis.values()), "question asked for only one of the pair", onlyone)
for fam in sorted(tot): print(f"  {fam}: {dis[fam]}/{tot[fam]}")
# 2. Swiss: sum of apartment areas must not exceed the floor area; number of apartment-area questions vs apartments count
by = collections.defaultdict(dict)
for r in rows:
    if r["source"] == "swiss_dwellings" and r["lang"] == "en":
        k = r["family"]
        if k == "area_apartment": by[r["path"]].setdefault("apts", []).append(r["answer"])
        elif k in ("area_floor", "apartments"): by[r["path"]][k] = r["answer"]
viol = eq = more = fewer = n = 0
for p, d in by.items():
    if "apts" not in d: continue
    n += 1; s = sum(d["apts"])
    viol += int(s > d["area_floor"] * 1.0005); eq += int(abs(s - d["area_floor"]) <= 0.02 * d["area_floor"])
    more += int(len(d["apts"]) > d["apartments"]); fewer += int(len(d["apts"]) < d["apartments"])
print(f"swiss floors with apartment-area questions: {n}; sum(apartment areas) > floor area: {viol}; within 2% of floor area: {eq}; more apartment-area questions than apartments: {more}; fewer: {fewer}")
# 3. Swiss: decimals of area answers, share of count answers equal to 0
dec = collections.Counter(len(str(r["answer"]).split(".")[-1]) if "." in str(r["answer"]) else 0 for r in rows if r["source"] == "swiss_dwellings" and r["type"] == "area")
print("swiss area decimals", dict(dec))
small = sum(1 for r in rows if r["type"] in ("area", "length", "volume") and float(r["answer"]) < 2.5); allm = sum(1 for r in rows if r["type"] in ("area", "length", "volume"))
print(f"measure answers below 2.5 (2% band narrower than 0.05): {small}/{allm}")
# 4. ifc_bench: reference answers that abstain
pat = re.compile(r"not available|no .{0,40} found|cannot be|not directly available|does not (store|contain)|not stored|no explicit|not defined|n/a", re.I)
fb = [r for r in rows if r["source"] == "ifc_bench"]
ab = [r for r in fb if pat.search(str(r["answer"]))]
print(f"ifc_bench references with an abstention phrase: {len(ab)}/{len(fb)}")
ln = sorted(len(str(r["answer"])) for r in fb); print("ifc_bench answer chars p10/p50/p90/max", ln[len(ln)//10], ln[len(ln)//2], ln[len(ln)*9//10], ln[-1])
hasnum = sum(1 for r in fb if re.search(r"\d", str(r["answer"]))); print("ifc_bench references with at least one digit", hasnum)
nums = sorted(len(re.findall(r"\d+(?:[.,]\d+)?", str(r["answer"]))) for r in fb); print("numbers per reference p50/p90", nums[len(nums)//2], nums[len(nums)*9//10])
# 5. ifc_models: families by file extension, questions per project
ext = collections.Counter((os.path.splitext(r["path"])[1], "model" if r["family"].endswith("_model") else "level_or_room") for r in rows if r["source"] == "ifc_models")
print("ifc_models questions by ext and scope", dict(ext))
pj = collections.Counter(r["group"] for r in rows if r["source"] == "ifc_models"); print("ifc_models questions per project", pj.most_common())
pd_ = collections.defaultdict(set)
for r in rows:
    if r["source"] == "ifc_models": pd_[r["group"]].add(r["path"])
print("ifc_models drawings per project", sorted(((k, len(v)) for k, v in pd_.items()), key=lambda x: -x[1]))
# same question text on PDF siblings of one model with different answers
q = collections.defaultdict(set)
for r in rows:
    if r["source"] == "ifc_models" and r["family"].endswith("_model"): q[(r["group"], r["question"])].add(r["answer"])
print("ifc_models model-scope questions:", len(q), "with conflicting answers across files:", sum(1 for v in q.values() if len(v) > 1))
pj = collections.Counter(r["group"] for r in rows if r["source"] == "ifc_bench"); print("ifc_bench questions per model group", pj.most_common())
