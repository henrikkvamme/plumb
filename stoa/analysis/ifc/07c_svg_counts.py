# /// script
# requires-python = ">=3.11"
# dependencies = ["lxml"]
# ///
"""Probe: the SVG copy of each sheet tags every drawn product with its IFC class, GUID and name
(<g class="IfcDoor" data-guid=... data-name=...>). How many storey-scope count questions on the PDF
does a count of SVG groups by class reproduce? Writes out/svg_counts.json.
"""
import collections
import json
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
DS = HERE.parents[1] / "data" / "junction-dataset"
MD = DS / "data" / "ifc_models"
OUT = HERE / "out"
WORDS = [
    ("door", ["door", "tür", "deur", "puerta", "dør", " ust ", "drzwi", "porte"], ["IfcDoor"]),
    ("window", ["window", "fenster", "raam", "ramen", "ventana", "vindue", "akent", "okien"], ["IfcWindow"]),
    ("stair", ["stair", "treppe", "trap", "escalera", "treppi", "schod", "scări"], ["IfcStair"]),
    ("column", ["column", "stütze", "kolom", "pilar", "søjle", "posti", "stâlp"], ["IfcColumn"]),
    ("wall", ["wall", "wände", "wand", "muro", "muri", "væg", "sein", "ścian", "pereți"], ["IfcWall", "IfcWallStandardCase", "IfcWallElementedCase"]),
    ("space", ["room", "räume", "ruimte", "local", " rum ", "ruumi", "pomieszcze"], ["IfcSpace"]),
]


def main():
    qs = [json.loads(l) for l in open(DS / "questions.jsonl") if '"data/ifc_models/' in l and ".pdf" in l]
    res = []
    cache = {}
    for r in qs:
        ql = " " + r["question"].lower() + " "
        if r["type"] != "count" or any(w in ql for w in [" model", "mudel", "modelo", "modell", "modelul", "modelu"]):
            continue
        hit = next(((c, cl) for c, ws, cl in WORDS if any(w in ql for w in ws)), None)
        if not hit:
            continue
        svg = MD / r["path"].split("/")[-1].replace(".pdf", ".svg")
        if svg not in cache:
            t = etree.parse(str(svg))
            cnt = collections.Counter()
            guids = collections.defaultdict(set)
            for g in t.iter("{http://www.w3.org/2000/svg}g"):
                c = g.get("class")
                if c and c.startswith("Ifc"):
                    cnt[c] += 1
                    guids[c].add(g.get("data-guid"))
            cache[svg] = (cnt, {k: len(v) for k, v in guids.items()})
        cnt, ug = cache[svg]
        est = sum(cnt[c] for c in hit[1])
        est_u = sum(ug.get(c, 0) for c in hit[1])
        res.append({"pdf": svg.name, "cls": hit[0], "ref": r["answer"], "svg_groups": est, "svg_unique_guids": est_u})
    summ = {}
    for c, _, _ in WORDS:
        rs = [x for x in res if x["cls"] == c]
        if rs:
            summ[c] = {"n": len(rs), "eq_groups": sum(x["svg_groups"] == x["ref"] for x in rs), "eq_unique": sum(x["svg_unique_guids"] == x["ref"] for x in rs),
                       "misses": [(x["pdf"][:45], x["ref"], x["svg_groups"], x["svg_unique_guids"]) for x in rs if x["svg_unique_guids"] != x["ref"]][:6]}
    tot = len(res)
    summ["_all"] = {"n": tot, "eq_unique": sum(x["svg_unique_guids"] == x["ref"] for x in res)}
    json.dump({"summary": summ, "rows": res}, open(OUT / "svg_counts.json", "w"), indent=1)
    print(json.dumps(summ, indent=0))


if __name__ == "__main__":
    main()
