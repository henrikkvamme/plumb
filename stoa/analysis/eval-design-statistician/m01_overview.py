"""Overview: rows, sources, types, drawings, questions per drawing, files per source."""
import json, os, sys, collections, statistics as st
root = sys.argv[1]
rows = [json.loads(l) for l in open(os.path.join(root, "questions.jsonl"))]
print("rows", len(rows))
src = lambda p: p.split("/")[1]
by = collections.defaultdict(list)
for r in rows: by[src(r["path"])].append(r)
for s, rs in sorted(by.items()):
    paths = collections.Counter(r["path"] for r in rs)
    types = collections.Counter(r["type"] for r in rs)
    units = collections.Counter(r["unit"] for r in rs)
    exts = collections.Counter(os.path.splitext(p)[1].lower() for p in paths)
    q = sorted(paths.values())
    print(f"{s}: q={len(rs)} drawings={len(paths)} qpd min/med/max={q[0]}/{st.median(q)}/{q[-1]} types={dict(types)} units={dict(units)} exts={dict(exts)}")
print("--- files on disk")
for s in sorted(os.listdir(os.path.join(root, "data"))):
    d = os.path.join(root, "data", s)
    n = collections.Counter(); stems = set()
    for dp, _, fs in os.walk(d):
        for f in fs:
            if f == "LICENSE.md": continue
            e = os.path.splitext(f)[1].lower(); n[e] += 1
            stems.add(os.path.join(dp, os.path.splitext(f)[0]))
    print(f"{s}: files={sum(n.values())} stems={len(stems)} exts={dict(n)}")
