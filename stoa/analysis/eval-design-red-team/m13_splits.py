"""Exact sizes of the proposed pools. Unit = group. bucket = sha256('stoa-eval-v1|'+group) % 100."""
import collections, hashlib, re, statistics
from common import *
BUILDING = [  # building family across ifc_models and ifc_bench (near copies: disciplines, variants, sheets)
 (r"esplanades", "esplanades"), (r"warmond", "warmond"), (r"molio", "molio"), (r"clinic", "clinic"), (r"escape-route", "escape-route"),
 (r"vitoria", "vitoria"), (r"digital_?hub", "digitalhub"), (r"gymzaal", "gymzaal"), (r"institute|/ac20$", "ac20-institute"), (r"gdynia", "gdynia"),
 (r"smiley", "smiley-west"), (r"fzk", "fzk-haus"), (r"duplex", "duplex"), (r"barlad", "barlad"), (r"frigento", "frigento"), (r"chesapeake", "chesapeake"),
 (r"4351", "4351"), (r"ettenheim", "ettenheim"), (r"fantasy_hotel", "fantasy-hotel"), (r"fantasy_office", "fantasy-office"), (r"fantasy_residential", "fantasy-residential"),
 (r"hitos", "hitos"), (r"sixty5", "sixty5"), (r"city_house", "city-house")]
def group2(x):
    g = x["group"]
    if x["source"] in ("ifc_models", "ifc_bench"):
        for rx, name in BUILDING:
            if re.search(rx, g): return "bim/" + name
        return "bim/?" + g
    return g
def bucket(g): return int(hashlib.sha256(("stoa-eval-v1|" + g).encode()).hexdigest()[:8], 16) % 100
def pool(b): return "lock" if b < 15 else "dev" if b < 25 else "confirm" if b < 30 else "train"
it = items()
for x in it: x["g2"] = group2(x); x["pool"] = pool(bucket(x["g2"]))
tab = collections.defaultdict(lambda: [set(), set(), 0])
for x in it:
    t = tab[(x["source"], x["pool"])]; t[0].add(x["g2"]); t[1].add(x["pair"]); t[2] += 1
print("source pool groups items rows")
for (s, p), (g, i, r) in sorted(tab.items()): print(f"{s:16s} {p:8s} {len(g):5d} {len(i):6d} {r:6d}")
bim = collections.defaultdict(lambda: collections.Counter())
for x in it:
    if x["g2"].startswith("bim/"): bim[x["g2"]][x["source"]] += 1
print("BIM building families", len(bim))
for g, c in sorted(bim.items(), key=lambda kv: -sum(kv[1].values())): print(f"   {g:26s} bucket={bucket(g):2d} {pool(bucket(g)):8s} ifc_models={c['ifc_models']:4d} ifc_bench={c['ifc_bench']:4d}")
# languages of local questions per pool for swiss
sw = collections.Counter((x["pool"], x["lang"]) for x in it if x["source"]=="swiss_dwellings" and x["lang"]!="en"); print("swiss local rows per pool", dict(sw))
cat = collections.Counter(); seen = set()
for x in it:
    if x["source"]=="cubicasa5k" and x["path"] not in seen: seen.add(x["path"]); cat[(x["pool"], os.path.basename(x["path"]).rsplit("-",1)[0])] += 1
print("cubicasa drawings per pool/category", dict(cat))
one = [x["answer"] for x in it if x["source"]=="swiss_dwellings" and x["family"].startswith("What is the net floor area of room")]
print("swiss single-room area: n", len(one), "median", statistics.median(one), "2% of median", round(0.02*statistics.median(one),3), "share below 5 m2", round(sum(1 for a in one if a<5)/len(one),3))
