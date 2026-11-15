"""Suite sizes on split_v0, clustering (ICC, design effect) of a prior baseline, and real-solver ICC proxies.
Run: uv run python m08_cells_icc.py   (reads ../questions/qcommon.py and split_v0.json)"""
import sys, os, json, math, collections
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(H, "..", "questions")); sys.path.insert(0, H)
import qcommon as q
from common import family_lang
rows = q.annotate(q.load())
sp = json.load(open(os.path.join(H, "..", "questions", "split_v0.json")))["groups"]
for r in rows:
    r["source"] = r["_src"]; r["fam"] = family_lang(r)[0]; r["g"] = q.group_key(r["path"]); r["split"] = sp[r["g"]]
    r["item"] = (r["path"], r["fam"], r["_sk"]) if r["_src"] in ("cubicasa5k", "swiss_dwellings", "ifc_models") else (r["path"], r["question"])
def icc(clusters):
    """one-way ANOVA ICC for 0/1 outcomes; clusters = list of lists"""
    k = len(clusters); N = sum(len(c) for c in clusters); 
    if k < 2 or N <= k: return float("nan"), 1.0, N
    gm = sum(sum(c) for c in clusters) / N
    ssb = sum(len(c) * (sum(c) / len(c) - gm) ** 2 for c in clusters); ssw = sum(sum((x - sum(c) / len(c)) ** 2 for x in c) for c in clusters)
    msb = ssb / (k - 1); msw = ssw / (N - k); n0 = (N - sum(len(c) ** 2 for c in clusters) / N) / (k - 1)
    rho = (msb - msw) / (msb + (n0 - 1) * msw) if msb + (n0 - 1) * msw > 0 else 0.0
    # design effect from the ratio-estimator cluster variance
    var_cl = k / (k - 1) * sum((sum(c) - gm * len(c)) ** 2 for c in clusters) / N ** 2; var_srs = gm * (1 - gm) / N
    return rho, (var_cl / var_srs if var_srs > 0 else 1.0), N
print("A. split_v0 sizes: source|split|groups|drawings|items|rows")
agg = collections.defaultdict(lambda: [set(), set(), set(), 0])
for r in rows:
    a = agg[(r["source"], r["split"])]; a[0].add(r["g"]); a[1].add(r["path"]); a[2].add(r["item"]); a[3] += 1
for k, a in sorted(agg.items()): print("|".join(map(str, [*k, len(a[0]), len(a[1]), len(a[2]), a[3]])))
print("B. family-mode prior fit on dev, scored on val+test items (one row per item): source|acc|items|groups|ICC|deff|n_eff")
mode = {}
by = collections.defaultdict(list)
for r in rows:
    if r["split"] == "dev": by[(r["source"], r["fam"])].append(r)
for k, rs in by.items(): mode[k] = q.best_constant(rs)[0]
seen = set(); cl = collections.defaultdict(lambda: collections.defaultdict(list)); famcl = collections.defaultdict(lambda: collections.defaultdict(list))
for r in rows:
    if r["split"] == "dev" or r["item"] in seen: continue
    seen.add(r["item"]); p = mode.get((r["source"], r["fam"]))
    ok = 0
    if p is not None and r["type"] != "text":
        try: ok = int(q.correct(p, r))
        except Exception: ok = 0
    cl[r["source"]][r["g"]].append(ok); famcl[(r["source"], r["fam"])][r["g"]].append(ok)
for s, c in sorted(cl.items()):
    L = list(c.values()); rho, deff, N = icc(L); acc = sum(map(sum, L)) / N
    print(f"{s}|{acc:.3f}|{N}|{len(L)}|{rho:.3f}|{deff:.2f}|{N/deff:.0f}")
print("C. items per (source,family) in test only: fam|items|groups")
t = collections.defaultdict(lambda: [set(), set()])
for r in rows:
    if r["split"] == "test": t[(r["source"], r["fam"])][0].add(r["item"]); t[(r["source"], r["fam"])][1].add(r["g"])
for k, a in sorted(t.items()): print(f"{k[0]}/{k[1]}|{len(a[0])}|{len(a[1])}")
print("D. questions per drawing (items): source|median|p10|p90")
per = collections.defaultdict(lambda: collections.defaultdict(set))
for r in rows: per[r["source"]][r["path"]].add(r["item"])
for s, d in sorted(per.items()):
    v = sorted(len(x) for x in d.values()); print(f"{s}|{v[len(v)//2]}|{v[len(v)//10]}|{v[9*len(v)//10]}")
