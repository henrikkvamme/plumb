"""Derive templates by masking quoted spans and numbers. Report per-source template counts, mode-guess accuracy."""
import json, re, collections, statistics
ROOT = "./stoa/data/junction-dataset"
rows = [json.loads(l) for l in open(f"{ROOT}/questions.jsonl", encoding="utf-8") if l.strip()]
src = lambda r: r["path"].split("/")[1]
Q = re.compile(r"""(["'“”‘’«»„][^"'“”‘’«»„]{1,60}["'“”‘’«»„])""")
def tmpl(q):
    t = Q.sub("<Q>", q)
    t = re.sub(r"\d+(?:[.,]\d+)*", "<N>", t)
    return t
C = collections.Counter
T = collections.defaultdict(list)
for r in rows:
    r["_t"] = tmpl(r["question"])
    T[(src(r), r["_t"])].append(r)
out = {}
for s in ["cubicasa5k", "swiss_dwellings", "ifc_models", "ifc_bench", "opening_design"]:
    ts = {k: v for k, v in T.items() if k[0] == s}
    n = sum(len(v) for v in ts.values())
    sizes = sorted((len(v) for v in ts.values()), reverse=True)
    # mode-guess (exact for count; within 2% for measures; exact string for text)
    hit = 0
    for k, v in ts.items():
        c = C(json.dumps(r["answer"]) for r in v)
        hit += c.most_common(1)[0][1]
    print(s, "rows", n, "templates", len(ts), "singletons", sum(1 for x in sizes if x == 1), "top5sizes", sizes[:5], "mode_guess_exact", round(hit / n, 4))
    out[s] = sorted(((len(v), k[1], v[0]["type"], C(json.dumps(r["answer"]) for r in v).most_common(3)) for k, v in ts.items()), reverse=True)
json.dump(out, open("out/02_templates.json", "w"), ensure_ascii=False, indent=0)
with open("out/02_templates.txt", "w") as f:
    for s, lst in out.items():
        f.write(f"## {s} {len(lst)}\n")
        for n, t, ty, mc in lst[:90]:
            f.write(f"{n}\t{ty}\t{t[:230]}\t{mc[:2]}\n")
