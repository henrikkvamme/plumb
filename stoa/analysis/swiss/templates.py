# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Template families of swiss_dwellings questions.

Replaces quoted labels and numbers with placeholders, groups questions into templates,
and writes counts, languages and answer distributions to out/templates.json.
Usage: uv run templates.py
"""
import json, re, collections, pathlib, statistics

ROOT = pathlib.Path(__file__).resolve().parents[2]
Q = ROOT / "data/junction-dataset/questions.jsonl"
OUT = ROOT / "data/external/swiss-derived"  # git-ignored; derived from licensed data
OUT.mkdir(exist_ok=True)

rows = []
for line in Q.open():
    line = line.strip()
    if not line:
        continue
    r = json.loads(line)
    if r["path"].startswith("data/swiss_dwellings/"):
        rows.append(r)

QUOTE = re.compile(r"(['\"«»“”‘’])([^'\"«»“”‘’]+)(['\"«»“”‘’])")


def templ(q):
    labels = [m.group(2) for m in QUOTE.finditer(q)]
    t = QUOTE.sub(lambda m: m.group(1) + "{L}" + m.group(3), q)
    t = re.sub(r"\b\d+(\.\d+)?\b", "{N}", t)
    return t, labels


def lang(t):
    tl = t.lower()
    if re.search(r"\b(how|what|are|the|is)\b", tl):
        return "en"
    if re.search(r"\b(wie|welche|gibt|dieses|diesem|grundriss|geschoss)\b", tl):
        return "de"
    if re.search(r"\b(combien|quelle|est|sur|ce|cet|plan)\b", tl):
        return "fr"
    if re.search(r"\b(quant[ie]|qual|questo|sono|piano|pianta)\b", tl):
        return "it"
    return "?"


by_t = collections.defaultdict(list)
for r in rows:
    t, labels = templ(r["question"])
    r["_t"] = t
    r["_labels"] = labels
    by_t[t].append(r)

out = []
for t, rs in sorted(by_t.items(), key=lambda kv: -len(kv[1])):
    ans = [r["answer"] for r in rs]
    num = [a for a in ans if isinstance(a, (int, float))]
    d = {
        "template": t,
        "lang": lang(t),
        "n": len(rs),
        "type": collections.Counter(r["type"] for r in rs).most_common(),
        "unit": collections.Counter(r["unit"] for r in rs).most_common(),
        "floors": len({r["path"] for r in rs}),
    }
    if num:
        d["answer_mode"] = collections.Counter(num).most_common(5)
        d["answer_min"], d["answer_max"] = min(num), max(num)
        d["answer_median"] = statistics.median(num)
        d["mode_share"] = collections.Counter(num).most_common(1)[0][1] / len(num)
    labs = collections.Counter(l for r in rs for l in r["_labels"])
    if labs:
        d["labels"] = labs.most_common(60)
    out.append(d)

paths = {r["path"] for r in rows}
summary = {
    "rows": len(rows),
    "floors": len(paths),
    "templates": len(out),
    "types": collections.Counter(r["type"] for r in rows).most_common(),
    "templates_by_lang": collections.Counter(d["lang"] for d in out).most_common(),
    "rows_by_lang": collections.Counter(lang(r["_t"]) for r in rows).most_common(),
    "ext": collections.Counter(p.rsplit(".", 1)[1] for p in paths).most_common(),
    "questions_per_floor": statistics.mean(collections.Counter(r["path"] for r in rows).values()),
}
json.dump({"summary": summary, "templates": out}, open(OUT / "templates.json", "w"), indent=1, ensure_ascii=False)
json.dump(rows, open(OUT / "rows.json", "w"), ensure_ascii=False)
print(json.dumps(summary, ensure_ascii=False))
for d in out:
    print(d["n"], d["lang"], d["type"][0][0], round(d.get("mode_share", 0), 2), d["template"][:110])
