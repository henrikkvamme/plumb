"""Proposed splits: cluster ids, strata, deterministic hash assignment, measured sizes. Writes splits.json to argv[3]."""
import sys, os, json, re, hashlib, collections
sys.path.insert(0, os.path.dirname(__file__))
from common import load
SALT = "stoa-eval-v1"
IFC_FAMILY = [("digitalhub", r"rwth-digitalhub|digital_hub"), ("fzk", r"kit-fzk-haus|fzk_house"), ("smiley", r"kit-smiley-west|smiley_west"),
              ("molio", r"bsc-molio|molio_arc"), ("institute", r"kit-institute|ac20_arc"), ("duplex", r"bsc-duplex|duplex_"),
              ("clinic", r"bsc-clinic|dental_clinic"), ("sixty5", r"sixty5"), ("fantasy_office", r"fantasy_office"), ("fantasy_hotel", r"fantasy_hotel")]
def cluster(r, cubi):
    s, name = r["source"], os.path.basename(r["path"])
    if s == "cubicasa5k": return "cubi:" + cubi.get(name, name)
    if s == "swiss_dwellings": return "swiss:" + name.split("_")[0]
    if s in ("ifc_models", "ifc_bench"):
        for fam, pat in IFC_FAMILY:
            if re.search(pat, name): return "ifc:" + fam
        return "ifc:" + (name.split("_")[0] if s == "ifc_models" else re.sub(r"_(arc|gis_city)\.ifc$", "", name))
    return "od:" + r["path"].split("/")[3]
def item_key(r):
    q = r["question"]
    m = re.findall(r"'([^']*)'|«\s*([^»]*?)\s*»|„([^“”]*)[“”]", q); slot = "|".join(x for t in m for x in t if x)
    num = re.search(r"(?:room|Raum|pièce|locale) (U?\d+(?:\.\d+)?)", q); apt = re.search(r"(?:apartment|Wohnung|appartement|appartamento) ([A-Z])\b", q)
    if r["source"] in ("cubicasa5k", "swiss_dwellings"):
        return (r["path"], r["family"], num.group(1) if num else (apt.group(1) if apt else slot))
    return (r["path"], r["question"])   # other sources: every row is its own item
def h(x): return hashlib.sha1((SALT + x).encode()).hexdigest()
QUOTA = {"cubicasa5k": [("lock", 600), ("reserve", 600), ("dev_b", 400), ("dev_a", 300)],
         "swiss_dwellings": [("lock", 250), ("reserve", 100), ("dev_b", 150), ("dev_a", 150)]}
def build(rows, cubi):
    for r in rows: r["cluster"] = cluster(r, cubi); r["item"] = item_key(r)
    split = {}
    # cubicasa and swiss: stratified by subset or local language, proportional quotas, order by hash
    for src, quota in QUOTA.items():
        strata = collections.defaultdict(set); loc = {}
        for r in rows:
            if r["source"] != src: continue
            if src == "swiss_dwellings":
                if r["lang"] != "en": loc[r["cluster"]] = r["lang"]
            else: loc[r["cluster"]] = os.path.basename(r["path"]).rsplit("-", 1)[0]
        for c, s in loc.items(): strata[s].add(c)
        total = sum(len(v) for v in strata.values())
        for s, cs in strata.items():
            order = sorted(cs, key=h); pos = 0
            for name, n in quota:
                k = round(n * len(cs) / total)
                for c in order[pos:pos + k]: split[c] = name
                pos += k
            for c in order[pos:]: split[c] = "train"
    # ifc building families: alternate dev / lock by descending question count, so both halves get large and small families
    cnt = collections.Counter(r["cluster"] for r in rows if r["cluster"].startswith("ifc:"))
    for i, (c, _) in enumerate(sorted(cnt.items(), key=lambda x: (-x[1], x[0]))): split[c] = "dev_a" if i % 2 == 0 else "lock"
    split["od:Sports_Complex"] = "dev_a"
    for c in {r["cluster"] for r in rows if r["cluster"].startswith("od:")} - {"od:Sports_Complex"}: split[c] = "lock"
    for r in rows: r["split"] = split[r["cluster"]]
    return split
if __name__ == "__main__":
    rows = load(sys.argv[1]); cubi = json.load(open(sys.argv[2])); split = build(rows, cubi)
    print("clusters per source:", dict(collections.Counter(c.split(":")[0] for c in split)))
    items = collections.defaultdict(set); langs = collections.Counter()
    for r in rows: items[r["item"]].add(r["lang"])
    print("rows", len(rows), "items (language pairs merged)", len(items), "items with 2 languages", sum(1 for v in items.values() if len(v) == 2), "with 1", sum(1 for v in items.values() if len(v) == 1), "with >2", sum(1 for v in items.values() if len(v) > 2))
    agg = collections.defaultdict(lambda: [set(), set(), set(), 0])
    for r in rows:
        a = agg[(r["source"], r["split"])]; a[0].add(r["cluster"]); a[1].add(r["path"]); a[2].add(r["item"]); a[3] += 1
    print("source|split|clusters|drawings|items|rows")
    for (s, sp), a in sorted(agg.items()): print(f"{s}|{sp}|{len(a[0])}|{len(a[1])}|{len(a[2])}|{a[3]}")
    print("ifc families:", sorted((c, split[c], n) for c, n in collections.Counter(r["cluster"] for r in rows if r["cluster"].startswith("ifc:")).items()))
    st = collections.Counter((r["split"], os.path.basename(r["path"]).rsplit("-", 1)[0]) for r in rows if r["source"] == "cubicasa5k" and r["family"] == "windows" and r["lang"] == "en")
    print("cubicasa subset by split (drawings):", sorted(st.items()))
    st = collections.Counter((r["split"], r["lang"]) for r in rows if r["source"] == "swiss_dwellings" and r["family"] == "windows" and r["lang"] != "en")
    print("swiss local language by split (drawings):", sorted(st.items()))
    fam = collections.defaultdict(set)
    for r in rows:
        if r["split"] == "dev_a": fam[(r["source"], r["family"])].add(r["item"])
    print("dev_a items per family:", sorted((k, len(v)) for k, v in fam.items()))
    json.dump(split, open(sys.argv[3], "w"))
