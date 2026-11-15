"""Statistics the design depends on: answer-balanced sampling, cluster SE, design effect, free-text shape."""
import collections, random, statistics, re, math, hashlib
from common import *
it = items()
en = [x for x in it if x["lang"]=="en" or not x["has_pair"]]   # one row per unique item
# --- 1. answer-balanced sampling on cubicasa: cap K drawings per (family, answer)
cc = [x for x in en if x["source"]=="cubicasa5k"]
def prior_acc(xs):
    f = collections.defaultdict(collections.Counter)
    for x in xs: f[x["family"]][x["answer"]] += 1
    micro = sum(c.most_common(1)[0][1] for c in f.values())/len(xs)
    macro = statistics.mean(c.most_common(1)[0][1]/sum(c.values()) for c in f.values())
    return micro, macro
print("cubicasa natural: items", len(cc), "prior micro %.3f macro-by-family %.3f" % prior_acc(cc))
for K in (5, 10, 20):
    random.seed(1); b = collections.defaultdict(list)
    for x in cc: b[(x["family"], x["answer"])].append(x)
    bal = [x for v in b.values() for x in random.sample(v, min(K, len(v)))]
    print(f"cubicasa balanced cap K={K}: items {len(bal)} drawings {len(set(x['path'] for x in bal))} prior micro %.3f macro %.3f" % prior_acc(bal))
sw = [x for x in en if x["source"]=="swiss_dwellings" and x["type"]=="count"]
print("swiss count natural: items", len(sw), "prior micro %.3f macro %.3f" % prior_acc(sw))
# --- 2. cluster SE of a real (dumb) solver: the mode-per-family guess, per source
def mode_correct(xs):
    f = collections.defaultdict(collections.Counter)
    for x in xs: f[x["family"]][x["answer"]] += 1
    m = {k: c.most_common(1)[0][0] for k, c in f.items()}
    return [(x["group"], int(x["answer"] == m[x["family"]])) for x in xs]
for name, xs in (("cubicasa", cc), ("swiss_count", sw)):
    gc = collections.defaultdict(list)
    for g, c in mode_correct(xs): gc[g].append(c)
    groups = sorted(gc); p = sum(map(sum, gc.values()))/sum(map(len, gc.values())); m = statistics.mean(len(v) for v in gc.values())
    # ICC via one-way ANOVA estimator
    N = sum(len(v) for v in gc.values()); k = len(groups)
    ssb = sum(len(v)*(statistics.mean(v)-p)**2 for v in gc.values()); ssw = sum(sum((c-statistics.mean(v))**2 for c in v) for v in gc.values())
    msb = ssb/(k-1); msw = ssw/(N-k); n0 = (N - sum(len(v)**2 for v in gc.values())/N)/(k-1); icc = (msb-msw)/(msb+(n0-1)*msw)
    print(f"{name}: groups {k} items/group {m:.1f} p={p:.3f} ICC={icc:.3f} design effect={1+(m-1)*icc:.2f}")
    for n in (50, 100, 200, 400):
        random.seed(5); est = []
        for _ in range(2000):
            s = random.choices(groups, k=n); h = sum(sum(gc[g]) for g in s); t = sum(len(gc[g]) for g in s); est.append(h/t)
        print(f"   n={n} drawings: items ~{int(n*m)} cluster-bootstrap SE={statistics.pstdev(est)*100:.2f} pts; naive binomial SE={100*math.sqrt(p*(1-p)/(n*m)):.2f}")
# --- 3. free text shape
for s in ("ifc_bench", "opening_design"):
    tx = [x for x in it if x["source"]==s and x["type"]=="text"]
    L = sorted(len(str(x["answer"])) for x in tx); nums = sorted(len(re.findall(r"\d+(?:[.,]\d+)?", str(x["answer"]))) for x in tx)
    neg = sum(1 for x in tx if re.match(r"\s*(No |There (is|are) no|None|Not |The model (does not|contains no)|N/A)", str(x["answer"])))
    notfound = sum(1 for x in tx if re.search(r"not found|no .{0,40}(found|available|defined|in (the )?model)|does not contain|not (available|specified|defined)", str(x["answer"]), re.I))
    print(f"{s} text: n={len(tx)} answer chars p10/50/90 = {L[len(L)//10]}/{L[len(L)//2]}/{L[9*len(L)//10]}; numbers per answer p10/50/90 = {nums[len(nums)//10]}/{nums[len(nums)//2]}/{nums[9*len(nums)//10]}; starts-negative={neg}; mentions-missing={notfound}; multi-line={sum(1 for x in tx if chr(10) in str(x['answer']))}")
# --- 4. area answer precision, duplicates
ar = [x for x in it if x["type"]=="area" and x["source"]=="swiss_dwellings"]
print("swiss area decimals", collections.Counter(len(str(x["answer"]).split(".")[-1]) if "." in str(x["answer"]) else 0 for x in ar).most_common(4), "min/median/max", min(x["answer"] for x in ar), statistics.median(x["answer"] for x in ar), max(x["answer"] for x in ar))
print("2% tolerance on median swiss room area in m2:", round(0.02*statistics.median(x["answer"] for x in ar if "room" in x["family"]),3))
dup = collections.Counter((x["path"], x["question"]) for x in it); print("duplicate (path,question) rows", sum(1 for v in dup.values() if v>1))
print("questions per drawing (unique items): cubicasa median", statistics.median(collections.Counter(x["path"] for x in cc).values()), "swiss median", statistics.median(collections.Counter(x["path"] for x in en if x["source"]=="swiss_dwellings").values()))
