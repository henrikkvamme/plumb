"""Reference implementation of the proposed split. Prints sizes. Deterministic: sha256('stoa-eval-v1|'+group) % 100."""
import json, re, os, collections, hashlib, random
ROOT = "./stoa/data/junction-dataset"
rows = [json.loads(l) for l in open(f"{ROOT}/questions.jsonl", encoding="utf-8") if l.strip()]
C = collections.Counter; P = print
src = lambda r: r["path"].split("/")[1]
def bucket(g): return int(hashlib.sha256(("stoa-eval-v1|" + g).encode()).hexdigest()[:8], 16) % 100
BENCH = {"ac20": "kit-institute", "fantasy_office_building": "kit-institute", "digital_hub": "rwth-digitalhub", "smiley_west": "kit-smiley-west", "duplex": "bsc-duplex",
         "fzk_house": "kit-fzk-haus", "molio": "bsc-molio", "dental_clinic": "bsc-clinic"}
def group(p):
    s = p.split("/")[1]; b = os.path.basename(p)
    if s == "cubicasa5k": return "cubi:" + b[:-4]
    if s == "swiss_dwellings": return "swiss:" + re.match(r"site(\d+)_", b).group(1)
    if s == "ifc_models": return "ifc:" + b.split("_")[0]
    if s == "ifc_bench":
        st = re.sub(r"_(arc|mep|str|heating|plumbing|ventilation|electrical|facade|kitchen|gis_city)$", "", b[:-4]); st = re.sub(r"_\d+$", "", st)
        return "ifc:" + BENCH.get(st, "bench-" + st)
    if s == "opening_design": return "od:" + p.split("/")[2]
    return s + ":" + b
# IFC projects: deal by question count, largest first, alternating dev/test (no train: IFC answers come from code, not from a trained model)
ifc_rows = C(group(r["path"]) for r in rows if src(r) in ("ifc_models", "ifc_bench"))
ifc_split = {}
for i, (g, n) in enumerate(sorted(ifc_rows.items(), key=lambda kv: (-kv[1], kv[0]))): ifc_split[g] = "dev" if i % 2 == 0 else "test"
def split(p):
    g = group(p)
    if g.startswith("ifc:"): return ifc_split[g]
    if g.startswith("od:"): return "dev"
    b = bucket(g)
    return "train" if b < 60 else ("dev" if b < 80 else "test")
dq = collections.defaultdict(C); dd = collections.defaultdict(lambda: collections.defaultdict(set)); gg = collections.defaultdict(lambda: collections.defaultdict(set))
for r in rows:
    s, sp = src(r), split(r["path"])
    dq[s][sp] += 1; dd[s][sp].add(r["path"]); gg[s][sp].add(group(r["path"]))
for s in dq:
    P("SPLIT", s, {sp: (len(gg[s][sp]), len(dd[s][sp]), dq[s][sp]) for sp in ("train", "dev", "test")}, "(groups, drawings, questions)")
P("IFC projects", len(ifc_rows), sorted(ifc_split.items()))
P("IFC rows per project", sorted(ifc_rows.items(), key=lambda kv: -kv[1]))
# mini: 150 cubicasa + 100 swiss drawings from dev (seeded), all dev ifc/ifc_bench capped at 40 q per file, all opening_design
random.seed(20261113)
mini = set(random.sample(sorted(dd["cubicasa5k"]["dev"]), 150)) | set(random.sample(sorted(dd["swiss_dwellings"]["dev"]), 100))
nq = C(); nd = C(); capc = C()
for r in rows:
    s = src(r)
    if r["path"] in mini: nq[s] += 1
    elif s in ("ifc_models", "ifc_bench") and split(r["path"]) == "dev":
        capc[r["path"]] += 1
        if capc[r["path"]] <= 40: nq[s] += 1
    elif s == "opening_design": nq[s] += 1
P("MINI questions", dict(nq), "total", sum(nq.values()), "drawings", 250 + len(dd["ifc_models"]["dev"]) + len(dd["ifc_bench"]["dev"]) + 3)
# smoke from train: 2 cubicasa, 3 swiss; plus 3 ifc_models files, 2 ifc_bench (dev), 2 opening_design; max 6 q per drawing
P("SMOKE approx", "12 drawings x <=6 questions = <=72")
# time-locked families
P("LOCK cubicasa balconies rows", sum(1 for r in rows if src(r) == "cubicasa5k" and re.search(r"balconies|parveketta", r["question"])),
  "swiss showers", sum(1 for r in rows if src(r) == "swiss_dwellings" and re.search(r"showers|Duschen|douches|docce", r["question"])),
  "swiss label_area", sum(1 for r in rows if src(r) == "swiss_dwellings" and re.search(r"all rooms labelled|aller Räume mit der Bezeichnung|toutes les pièces désignées|tutti i locali denominati", r["question"])),
  "ifc stairs", sum(1 for r in rows if src(r) == "ifc_models" and re.search(r"stairs|Treppen|trapp|escaler|schod|scări|trepp", r["question"])))
# wild groups
for s in ["habs", "finna", "europeana", "wikimedia"]:
    fs = [f for f in os.listdir(f"{ROOT}/data/{s}") if not f.endswith(".md")]
    key = {"habs": lambda f: f.split("_sheet_")[0], "finna": lambda f: f.split("_")[0], "europeana": lambda f: f.split("_")[0], "wikimedia": lambda f: os.path.splitext(f)[0]}[s]
    P("WILD", s, "files", len(fs), "groups", len(set(key(f) for f in fs)))
od = collections.Counter()
for dp, dn, fn in os.walk(f"{ROOT}/data/opening_design"):
    for f in fn:
        if f.lower().endswith(".pdf"): od[os.path.relpath(dp, f"{ROOT}/data/opening_design").split("/")[0]] += 1
P("OD projects with pdf", len(od), "pdfs", sum(od.values()), "top", od.most_common(6))
