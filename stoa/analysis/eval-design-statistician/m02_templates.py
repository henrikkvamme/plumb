"""Templates: mask digits and quoted or variable tokens, count templates per source."""
import json, os, sys, collections, re
root = sys.argv[1]; show = sys.argv[2] if len(sys.argv) > 2 else None
rows = [json.loads(l) for l in open(os.path.join(root, "questions.jsonl"))]
src = lambda p: p.split("/")[1]
def mask(q):
    q = re.sub(r"'[^']*'|\"[^\"]*\"|«[^»]*»|„[^“]*“", "<Q>", q)
    q = re.sub(r"\d+([.,]\d+)?", "<N>", q)
    return q
by = collections.defaultdict(collections.Counter)
ex = {}
for r in rows:
    t = mask(r["question"]); by[src(r["path"])][(t, r["type"])] += 1; ex.setdefault((src(r["path"]), t), r)
for s, c in sorted(by.items()):
    print(f"== {s}: masked templates={len(c)}")
    if show == s or show == "all":
        for (t, ty), n in c.most_common(int(sys.argv[3]) if len(sys.argv) > 3 else 80):
            e = ex[(s, t)]
            print(f"{n}\t{ty}\t{t[:150]}\t=> {str(e['answer'])[:60]}")
