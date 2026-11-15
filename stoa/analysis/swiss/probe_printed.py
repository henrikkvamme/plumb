# /// script
# requires-python = ">=3.11"
# dependencies = ["pymupdf"]
# ///
"""Is the printed area text enough to answer area questions without geometry?

About 30% of sheets print "12.34 m²" under each room number. For room-area questions on those sheets,
read the printed value under the room number and compare it with the reference. Also checks how often
a printed value differs from the reference by more than 2%, and whether the printed value for the
asked room is missing. Writes probe_printed.json.
Usage: uv run probe_printed.py   (needs templates.py output rows.json)
"""
import sys, re, json, pathlib, collections
import pymupdf

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from qparse import parse, OUTDOOR

ROOT = pathlib.Path(__file__).resolve().parents[2]
D = ROOT / "data/junction-dataset/data/swiss_dwellings"
OUT = ROOT / "data/external/swiss-derived"
NUM = re.compile(r"^(U\d+\.)?\d+\.\d+$|^U\d+\.\d+$")
M2 = re.compile(r"^(\d+(?:\.\d+)?)\s*m²$")

rows = json.load(open(OUT / "rows.json"))
by_floor = collections.defaultdict(list)
for r in rows:
    by_floor[pathlib.Path(r["path"]).stem].append(r)

stats = collections.Counter()
ex = []
per_family = collections.defaultdict(lambda: [0, 0])
for fl, rs in sorted(by_floor.items()):
    pg = pymupdf.open(D / f"{fl}.pdf")[0]
    spans = []
    for b in pg.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                x0, y0, x1, y1 = s["bbox"]
                spans.append((s["text"].strip(), (x0 + x1) / 2, (y0 + y1) / 2, s["size"]))
    m2 = [s for s in spans if M2.match(s[0])]
    if not m2:
        continue
    stats["floors_printed"] += 1
    nums = [s for s in spans if NUM.match(s[0])]
    labels = [s for s in spans if not NUM.match(s[0]) and not M2.match(s[0])]
    printed = {}
    lab = {}
    for n in nums:
        below = [s for s in m2 if abs(s[1] - n[1]) < 1.0 and 0 < s[2] - n[2] < 2.5 * n[3]]
        if below:
            printed[n[0]] = float(M2.match(min(below, key=lambda s: s[2] - n[2])[0]).group(1))
        above = [s for s in labels if abs(s[1] - n[1]) < 1.0 and 0 < n[2] - s[2] < 2.5 * n[3]]
        lab[n[0]] = min(above, key=lambda s: n[2] - s[2])[0] if above else None
    stats["rooms"] += len(nums)
    stats["rooms_with_printed"] += len(printed)
    for r in rs:
        fam, p, lang = parse(r["question"])
        if fam == "area_room":
            v = printed.get(p)
        elif fam == "area_label":
            v = round(sum(a for k, a in printed.items() if lab.get(k) == p), 2) if any(lab.get(k) == p for k in printed) else None
        elif fam == "area_total":
            v = round(sum(a for k, a in printed.items() if lab.get(k) not in OUTDOOR), 2)
        else:
            continue
        good = v is not None and abs(v - r["answer"]) <= 0.02 * abs(r["answer"])
        exact = v is not None and abs(v - r["answer"]) < 0.005
        per_family[fam][0] += good
        per_family[fam][1] += 1
        stats[f"{fam}_exact"] += exact
        if not good and len(ex) < 8:
            ex.append({"floor": fl, "fam": fam, "param": p, "ref": r["answer"], "printed": v})
out = {"stats": dict(stats), "families": {k: {"agree": a, "n": n, "rate": round(a / n, 4)} for k, (a, n) in per_family.items()}, "disagreements": ex}
json.dump(out, open(OUT / "probe_printed.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(out, ensure_ascii=False)[:1500])
