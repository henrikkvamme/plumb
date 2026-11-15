"""Template counts per source. Compact output."""
import collections, sys
from common import *
rows = load()
by = collections.defaultdict(lambda: collections.Counter())
ex = {}
for r in rows:
    s = src(r["path"]); t = template(r["question"]); by[s][t] += 1; ex.setdefault((s,t), r)
for s in sorted(by):
    c = by[s]; print(f"== {s}: templates={len(c)} rows={sum(c.values())}")
    if s in ("ifc_bench","opening_design"):
        sizes = collections.Counter(c.values()); print("   template-size histogram", sorted(sizes.items())[:12]); continue
    for t, n in c.most_common(200 if s!="ifc_models" else 15):
        print(f"{n}\t{t[:150]}")
