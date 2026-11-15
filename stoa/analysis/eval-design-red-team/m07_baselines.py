"""Answer priors: what a solver that never looks at the drawing scores."""
import collections, statistics, random, hashlib
from common import *
from common import _quoted
it = items()
def ok(pred, x):
    a = x["answer"]
    if x["type"] == "count": return pred == a
    if x["type"] in ("area","length","volume"):
        try: return abs(float(pred)-float(a)) <= 0.02*abs(float(a))
        except Exception: return False
    return False
def fold(g): return int(hashlib.sha1(g.encode()).hexdigest(), 16) % 5
def prior_score(xs, keyf):
    """5-fold by group: predict mode (count) or median (measure) of the key in the other folds."""
    hit = 0
    for f in range(5):
        tr = collections.defaultdict(list)
        for x in xs:
            if fold(x["group"]) != f: tr[keyf(x)].append(x["answer"])
        pred = {}
        for k, v in tr.items():
            pred[k] = collections.Counter(v).most_common(1)[0][0] if isinstance(v[0], int) else statistics.median(v)
        for x in xs:
            if fold(x["group"]) == f and keyf(x) in pred: hit += ok(pred[keyf(x)], x)
    return hit
tot = len(it); print("micro share by source:", {s: round(100*n/tot,1) for s,n in collections.Counter(x["source"] for x in it).items()})
res = {}
for s in ("cubicasa5k","swiss_dwellings","ifc_models"):
    xs = [x for x in it if x["source"]==s]
    for typ in ("count","area","volume","length"):
        ys = [x for x in xs if x["type"]==typ]
        if not ys: continue
        h1 = prior_score(ys, lambda x: x["family"])
        lab = lambda x: (x["family"], tuple(_quoted.findall(x["question"])[:1]) if s=="swiss_dwellings" else ())
        h2 = prior_score(ys, lab)
        print(f"{s} {typ}: n={len(ys)} prior(mode/median per family, 5-fold by group)={100*h1/len(ys):.1f}%  per family+label={100*h2/len(ys):.1f}%")
        res[(s,typ)] = (len(ys), h1)
    fams = collections.defaultdict(list)
    for x in xs: fams[x["family"]].append(x)
    if s != "ifc_models":
        for f, ys in sorted(fams.items(), key=lambda kv: -len(kv[1])):
            if ys[0]["type"]!="count": continue
            c = collections.Counter(y["answer"] for y in ys); m, n = c.most_common(1)[0]
            print(f"   {len(ys)}\tmode={m} share={100*n/len(ys):.1f}%\tzero={100*c[0]/len(ys):.1f}%\tmax={max(c)}\tdistinct={len(c)}\t{f[:60]}")
# headline candidates for the "never looks" solver
cc = res[("cubicasa5k","count")]; print("cubicasa mode baseline", round(100*cc[1]/cc[0],1))
allhit = sum(h for n,h in res.values()); print("micro over all 127044 rows (text=0):", round(100*allhit/tot,1))
