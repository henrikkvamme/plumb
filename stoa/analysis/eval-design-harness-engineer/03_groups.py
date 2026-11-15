"""Group structure: files on disk, stems, siblings, groups per source, near-copies, pair agreement."""
import json, re, os, collections, hashlib
ROOT = "./stoa/data/junction-dataset"
rows = [json.loads(l) for l in open(f"{ROOT}/questions.jsonl", encoding="utf-8") if l.strip()]
C = collections.Counter
src = lambda r: r["path"].split("/")[1]
P = print
asked = set(r["path"] for r in rows)
# files on disk
for s in sorted(os.listdir(f"{ROOT}/data")):
    files = []
    for dp, dn, fn in os.walk(f"{ROOT}/data/{s}"):
        for f in fn:
            files.append(os.path.relpath(os.path.join(dp, f), ROOT))
    ext = C(os.path.splitext(f)[1].lower() for f in files)
    stems = collections.defaultdict(set)
    for f in files:
        st, e = os.path.splitext(f)
        stems[st].add(e.lower())
    asked_stems = set(os.path.splitext(p)[0] for p in asked if p.split("/")[1] == s)
    multi = sum(1 for v in stems.values() if len(v) > 1)
    P("DISK", s, "files", len(files), "stems", len(stems), "stems_multi_ext", multi, "stems_asked", len(asked_stems), "stems_unasked", len(set(stems) - asked_stems), "ext", dict(ext.most_common(8)))
# cubicasa
cc = [r for r in rows if src(r) == "cubicasa5k"]
P("CUBI prefix drawings", C(re.sub(r"-\d+\.png$", "", os.path.basename(p)) for p in set(r["path"] for r in cc)))
P("CUBI lang", C("fi" if re.match(r"Kuinka", r["question"]) else "en" for r in cc))
# swiss
sw = [r for r in rows if src(r) == "swiss_dwellings"]
m = lambda p: re.match(r"data/swiss_dwellings/site(\d+)_bldg(\d+)_floor(\d+)\.pdf", p).groups()
floors = set(r["path"] for r in sw)
sites = C(m(p)[0] for p in floors); bl = C(m(p)[:2] for p in floors)
P("SWISS floors", len(floors), "sites", len(sites), "bldgs", len(bl), "floors_per_site top", sorted(sites.values(), reverse=True)[:10], "sites_with_1_floor", sum(1 for v in sites.values() if v == 1), "median", sorted(sites.values())[len(sites)//2])
def lang(q):
    if re.match(r"(How|What)", q): return "en"
    if re.match(r"(Wie|Welche)", q): return "de"
    if re.match(r"(Combien|Quelle)", q): return "fr"
    if re.match(r"(Quant|Qual)", q): return "it"
    return "??"
P("SWISS lang rows", C(lang(r["question"]) for r in sw))
fl = collections.defaultdict(set)
for r in sw: fl[r["path"]].add(lang(r["question"]))
P("SWISS langsets per floor", C(tuple(sorted(v)) for v in fl.values()))
sl = collections.defaultdict(set)
for p, v in fl.items(): sl[m(p)[0]] |= (v - {"en"})
P("SWISS local lang per site", C(tuple(sorted(v)) for v in sl.values()))
# near-copy floors: identical answer vector on EN fixed templates within a site
fixed = ["How many windows are drawn", "How many doors (interior", "How many toilets (WC)", "How many washbasins", "How many apartments", "What is the total net floor area in m² of all numbered"]
vec = collections.defaultdict(dict)
for r in sw:
    for i, f in enumerate(fixed):
        if r["question"].startswith(f): vec[r["path"]][i] = r["answer"]
bysite = collections.defaultdict(list)
for p, v in vec.items(): bysite[m(p)[0]].append(tuple(v.get(i) for i in range(len(fixed))))
dupfloors = sum(len(v) - len(set(v)) for v in bysite.values())
allv = C(t for v in bysite.values() for t in v)
P("SWISS floors_with_identical_6-answer_vector_to_another_floor_in_same_site", dupfloors, "of", len(vec), "| identical across whole set (extra copies)", sum(c - 1 for c in allv.values()))
# sibling files exist?
P("SWISS siblings", C(tuple(e for e in (".dxf", ".png", ".dwg", ".svg") if os.path.exists(f"{ROOT}/{p[:-4]}{e}")) for p in floors))
# ifc_models
im = [r for r in rows if src(r) == "ifc_models"]
files = set(r["path"] for r in im)
ifcs = sorted(f for f in os.listdir(f"{ROOT}/data/ifc_models") if f.lower().endswith(".ifc"))
P("IFCM asked files", len(files), "ifc asked", sum(1 for f in files if f.endswith(".ifc")), "pdf asked", sum(1 for f in files if f.endswith(".pdf")), "ifc on disk", len(ifcs))
def model_of(p):
    b = os.path.basename(p)
    st = os.path.splitext(b)[0]
    best = ""
    for i in ifcs:
        s0 = os.path.splitext(i)[0]
        if (st == s0 or st.startswith(s0 + "_")) and len(s0) > len(best): best = s0
    return best or "?" + st
mods = C(model_of(p) for p in files)
P("IFCM models (asked files grouped)", len(mods), "unmatched", sum(1 for k in mods if k.startswith("?")), "files per model top", sorted(mods.values(), reverse=True)[:8])
qm = C(model_of(r["path"]) for r in im)
P("IFCM questions per model top", sorted(qm.values(), reverse=True)[:10], "min", min(qm.values()))
P("IFCM whole-model questions asked on a pdf", sum(1 for r in im if r["path"].endswith(".pdf") and re.search(r"\b(model|Modell|modell|modelu|mudelis|modello|modelo|modellen)\b", r["question"])), "on ifc", sum(1 for r in im if r["path"].endswith(".ifc")))
# ifc_bench
ib = [r for r in rows if src(r) == "ifc_bench"]
P("IFCB models", len(set(r["path"] for r in ib)), "ext on disk", C(os.path.splitext(f)[1] for f in os.listdir(f"{ROOT}/data/ifc_bench")))
na = sum(1 for r in ib if re.search(r"not available|No .* found|not stored|does not (store|contain|include)|no explicit|not defined|cannot be determined|not present", str(r["answer"]), re.I))
P("IFCB answers that say info is not available (regex)", na, "of", len(ib))
ln = sorted(len(str(r["answer"])) for r in ib)
P("IFCB answer chars p10/med/p90/max", ln[len(ln)//10], ln[len(ln)//2], ln[9*len(ln)//10], ln[-1])
P("IFCB answers with >=1 number", sum(1 for r in ib if re.search(r"\d", str(r["answer"]))), "with >=5 numbers", sum(1 for r in ib if len(re.findall(r"\d+(?:\.\d+)?", str(r["answer"]))) >= 5))
# hash overlap ifc_bench vs ifc_models (size first)
def sizes(d): return {f: os.path.getsize(f"{ROOT}/data/{d}/{f}") for f in os.listdir(f"{ROOT}/data/{d}") if f.lower().endswith(".ifc")}
a, b = sizes("ifc_bench"), sizes("ifc_models")
same = [(x, y) for x, sx in a.items() for y, sy in b.items() if sx == sy]
P("IFC same-size pairs bench/models", len(same), same[:5])
# opening_design
od = [r for r in rows if src(r) == "opening_design"]
P("OD", C(r["path"] for r in od))
