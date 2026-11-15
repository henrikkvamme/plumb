"""Overview: rows per source, type, files, questions per file, extension of the named path."""
import json, collections, sys, os, re
Q = "./stoa/data/junction-dataset/questions.jsonl"
rows = [json.loads(l) for l in open(Q)]
print("rows", len(rows))
src = lambda p: p.split("/")[1]
by = collections.defaultdict(list)
for r in rows: by[src(r["path"])].append(r)
for s, rs in sorted(by.items()):
    files = collections.Counter(r["path"] for r in rs)
    ext = collections.Counter(os.path.splitext(r["path"])[1].lower() for r in rs)
    typ = collections.Counter(r["type"] for r in rs)
    unit = collections.Counter(str(r["unit"]) for r in rs)
    n = sorted(files.values())
    print(f"{s}: rows={len(rs)} files={len(files)} q/file min={n[0]} med={n[len(n)//2]} max={n[-1]}")
    print("   ext", dict(ext)); print("   type", dict(typ)); print("   unit", dict(unit))
    at = collections.Counter(type(r["answer"]).__name__ for r in rs)
    print("   answer py types", dict(at))
