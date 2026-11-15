"""Per source and family: questions, drawings, groups, languages, unknown share."""
import sys, collections
sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import load
rows = load(sys.argv[1])
unk = collections.Counter((r["source"], r["question"][:90]) for r in rows if r["family"] == "unknown" or r["lang"] == "other")
print("unknown family or lang:", sum(unk.values()))
for k, n in unk.most_common(15): print("  ", n, k)
agg = collections.defaultdict(lambda: [0, set(), set(), collections.Counter()])
for r in rows:
    a = agg[(r["source"], r["family"])]; a[0] += 1; a[1].add(r["path"]); a[2].add(r["group"]); a[3][r["lang"]] += 1
print("source|family|q|drawings|groups|langs")
for (s, f), a in sorted(agg.items()):
    print(f"{s}|{f}|{a[0]}|{len(a[1])}|{len(a[2])}|{dict(a[3])}")
print("--- groups per source")
g = collections.defaultdict(lambda: collections.defaultdict(set))
for r in rows: g[r["source"]][r["group"]].add(r["path"])
for s, d in g.items():
    sizes = sorted((len(v) for v in d.values()), reverse=True)
    print(s, "groups", len(d), "drawings", sum(sizes), "top sizes", sizes[:12], "singletons", sum(1 for x in sizes if x == 1))
lg = collections.defaultdict(collections.Counter)
for r in rows: lg[r["source"]][r["lang"]] += 1
for s, c in lg.items(): print(s, dict(c))
