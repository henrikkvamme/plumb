"""Prior baselines with grouped 5-fold CV, answer distributions, clustering (ICC), and EN/local pair agreement."""
import sys, os, collections, math, random, re, statistics as st
sys.path.insert(0, os.path.dirname(__file__))
from common import load
rows = load(sys.argv[1])
num = [r for r in rows if r["type"] in ("count", "area", "length", "volume")]
random.seed(0)
groups = sorted({(r["source"], r["group"]) for r in rows})
fold = {g: random.randrange(5) for g in groups}
def ok(r, pred):
    if pred is None: return 0
    a = float(r["answer"])
    if r["type"] == "count": return int(round(pred) == round(a))
    return int(abs(pred - a) <= 0.02 * abs(a)) if a != 0 else int(pred == 0)
def slot(r):
    m = re.findall(r"'([^']*)'|«\s*([^»]*?)\s*»|„([^“”]*)[“”]", r["question"])
    return "|".join(x for t in m for x in t if x)
def fit_predict(keyf):
    """Mode for counts, median for measures, per key, trained on the other 4 folds."""
    out = {}
    for k in range(5):
        tr = collections.defaultdict(list)
        for r in num:
            if fold[(r["source"], r["group"])] != k: tr[keyf(r)].append(float(r["answer"]))
        model = {}
        for key, v in tr.items():
            model[key] = collections.Counter(v).most_common(1)[0][0] if key[-1] == "count" else st.median(v)
        for r in num:
            if fold[(r["source"], r["group"])] == k: out[r["i"]] = model.get(keyf(r))
    return out
B = {
 "B0_type": fit_predict(lambda r: (r["type"],)),
 "B1_family": fit_predict(lambda r: (r["source"], r["family"], r["type"])),
 "B2_family_slot": fit_predict(lambda r: (r["source"], r["family"], slot(r) if r["source"] == "swiss_dwellings" else "", r["type"])),
}
# B2 falls back to B1 when the slot was not seen in training
for i, v in B["B2_family_slot"].items():
    if v is None: B["B2_family_slot"][i] = B["B1_family"][i]
def acc(rs, b): return sum(ok(r, B[b][r["i"]]) for r in rs) / len(rs)
print("== baseline accuracy per source (grouped 5-fold CV) n|B0|B1|B2")
bysrc = collections.defaultdict(list)
for r in num: bysrc[r["source"]].append(r)
for s, rs in sorted(bysrc.items()): print(f"{s}|{len(rs)}|" + "|".join(f"{acc(rs,b):.4f}" for b in B))
print(f"ALL_micro|{len(num)}|" + "|".join(f"{acc(num,b):.4f}" for b in B))
print("== per family: n|drawings|B1|B2|mode|mode_share|zero_share|p50|p90|max|entropy_bits")
byfam = collections.defaultdict(list)
for r in num: byfam[(r["source"], r["family"], r["type"])].append(r)
macro = collections.defaultdict(list)
for (s, f, t), rs in sorted(byfam.items()):
    v = sorted(float(r["answer"]) for r in rs); c = collections.Counter(v)
    ent = -sum(n/len(v) * math.log2(n/len(v)) for n in c.values()) if t == "count" else float("nan")
    m, mn = c.most_common(1)[0]
    b1, b2 = acc(rs, "B1_family"), acc(rs, "B2_family_slot"); macro[s].append((b1, b2))
    print(f"{s}|{f}|{t}|{len(rs)}|{len({r['path'] for r in rs})}|{b1:.3f}|{b2:.3f}|{m:g}|{mn/len(v):.3f}|{c.get(0.0,0)/len(v):.3f}|{v[len(v)//2]:g}|{v[int(len(v)*.9)]:g}|{v[-1]:g}|{ent:.2f}")
print("== macro over families per source: B1|B2")
for s, v in macro.items(): print(f"{s}|{sum(x[0] for x in v)/len(v):.4f}|{sum(x[1] for x in v)/len(v):.4f}|families={len(v)}")
# ICC of B1 correctness within drawing and within group (one-way ANOVA estimator)
def icc(rs, keyf):
    cl = collections.defaultdict(list)
    for r in rs: cl[keyf(r)].append(ok(r, B["B1_family"][r["i"]]))
    k = len(cl); N = sum(len(v) for v in cl.values()); gm = sum(sum(v) for v in cl.values()) / N
    if k < 2: return float("nan"), k, N / max(k, 1), float("nan")
    ssb = sum(len(v) * (sum(v)/len(v) - gm) ** 2 for v in cl.values()); ssw = sum(sum((x - sum(v)/len(v)) ** 2 for x in v) for v in cl.values())
    msb, msw = ssb / (k - 1), ssw / max(N - k, 1)
    m0 = (N - sum(len(v) ** 2 for v in cl.values()) / N) / (k - 1)
    rho = (msb - msw) / (msb + (m0 - 1) * msw) if (msb + (m0 - 1) * msw) > 0 else float("nan")
    mbar = N / k; cv2 = st.pvariance([len(v) for v in cl.values()]) / mbar ** 2
    deff = 1 + ((1 + cv2) * mbar - 1) * rho
    return rho, k, mbar, deff
print("== clustering of B1 correctness: source|level|ICC|clusters|mean_size|design_effect|effective_n")
for s, rs in sorted(bysrc.items()):
    for lvl, kf in (("drawing", lambda r: r["path"]), ("group", lambda r: r["group"])):
        rho, k, mbar, deff = icc(rs, kf)
        print(f"{s}|{lvl}|{rho:.3f}|{k}|{mbar:.1f}|{deff:.2f}|{len(rs)/deff if deff==deff and deff>0 else float('nan'):.0f}")
# EN vs local pair agreement on the same drawing and family (and slot)
pairs = collections.defaultdict(dict)
for r in num:
    if r["source"] in ("cubicasa5k", "swiss_dwellings"):
        pairs[(r["path"], r["family"], slot(r) if r["family"] != "area_room" else re.sub(r"\D+", " ", r["question"]).split()[0] if re.search(r"\d", r["question"]) else "", re.search(r"(apartment|Wohnung|appartement|appartamento) ([A-Z])", r["question"]).group(2) if r["family"] == "area_apartment" else "")][r["lang"]] = r["answer"]
tot = collections.Counter(); agree = collections.Counter(); single = collections.Counter()
for (p, f, _, _), d in pairs.items():
    s = p.split("/")[1]
    if len(d) < 2: single[s] += 1; continue
    tot[s] += 1; agree[s] += int(len(set(d.values())) == 1)
for s in tot: print(f"pair agreement {s}: pairs={tot[s]} agree={agree[s]} unpaired={single[s]}")
