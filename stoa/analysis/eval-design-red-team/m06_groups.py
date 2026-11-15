"""Group sizes: swiss sites/buildings/floors, ifc models, cubicasa categories, near-copy floors."""
import collections, re, glob, os
from common import *
it = items()
sw = [x for x in it if x["source"]=="swiss_dwellings"]
files = sorted(set(x["path"] for x in sw))
key = lambda p: re.match(r".*site(\d+)_bldg(\d+)_floor(\d+)", p).groups()
sites = collections.Counter(key(p)[0] for p in files); bl = collections.Counter(key(p)[1] for p in files)
print("swiss floors", len(files), "sites", len(sites), "buildings", len(bl))
print(" floors per site hist", sorted(collections.Counter(sites.values()).items()))
print(" floors per building hist", sorted(collections.Counter(bl.values()).items()))
# all swiss files on disk
allsw = set(os.path.splitext(os.path.basename(f))[0] for f in glob.glob(ROOT+"/data/swiss_dwellings/*.pdf"))
print(" swiss pdf on disk", len(allsw))
# language of non-EN per swiss file
fl = collections.defaultdict(set)
for x in sw:
    if x["lang"]!="en": fl[x["path"]].add(x["lang"])
print(" local language per floor", collections.Counter(tuple(sorted(v)) for v in fl.values()))
# cubicasa
cc = [x for x in it if x["source"]=="cubicasa5k"]
cf = set(x["path"] for x in cc)
print("cubicasa files by category", collections.Counter(os.path.basename(p).rsplit("-",1)[0] for p in cf))
# ifc_models
im = [x for x in it if x["source"]=="ifc_models"]
g = collections.defaultdict(lambda: [set(), 0, set()])
for x in im: g[x["group"]][0].add(x["path"]); g[x["group"]][1]+=1; g[x["group"]][2].add(x["lang"])
print("ifc_models groups", len(g))
for k,(fs,n,ls) in sorted(g.items(), key=lambda kv:-kv[1][1]): print(f"   {n}\t{len(fs)} files\t{','.join(sorted(ls))}\t{k}")
disk = os.listdir(ROOT+"/data/ifc_models")
print("ifc_models on disk: resbim png", sum(1 for f in disk if f.startswith("resbim") and f.endswith(".png")), "resbim ifc", sum(1 for f in disk if f.startswith("resbim") and f.endswith(".ifc")), "other ifc", sum(1 for f in disk if not f.startswith("resbim") and f.endswith(".ifc")), "pdf", sum(1 for f in disk if f.endswith(".pdf")), "plan pdf", sum(1 for f in disk if "_plan" in f and f.endswith(".pdf")), "elev/section pdf", sum(1 for f in disk if f.endswith(".pdf") and "_plan" not in f))
qf = set(os.path.basename(x["path"]) for x in im)
print(" files with questions: ifc", sum(1 for f in qf if f.endswith(".ifc")), "pdf", sum(1 for f in qf if f.endswith(".pdf")), "resbim", sum(1 for f in qf if f.startswith("resbim")), "elev/section", sum(1 for f in qf if f.endswith(".pdf") and "_plan" not in f))
# whole-model questions asked on a sheet
wm = [x for x in im if x["path"].endswith(".pdf") and ("in the model" in x["family"])]
print(" whole-model questions on a PDF sheet", len(wm), "of", len(im), "; storey-scope on .ifc path", sum(1 for x in im if x["path"].endswith(".ifc")))
ib = [x for x in it if x["source"]=="ifc_bench"]
g2 = collections.Counter(x["group"] for x in ib); print("ifc_bench groups", len(g2), dict(g2))
