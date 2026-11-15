import json, re, os, collections, math, random
ROOT = "./stoa/data/junction-dataset"
rows = [json.loads(l) for l in open(f"{ROOT}/questions.jsonl", encoding="utf-8") if l.strip()]
C = collections.Counter; P = print
src = lambda r: r["path"].split("/")[1]
# cubicasa EN/FI pairs: rows come in adjacent pairs? check by order
cc = [r for r in rows if src(r) == "cubicasa5k"]
byp = collections.defaultdict(list)
for r in cc: byp[r["path"]].append(r)
pairs = mism = 0
for p, v in byp.items():
    en = [r for r in v if not r["question"].startswith("Kuinka")]
    fi = [r for r in v if r["question"].startswith("Kuinka")]
    if len(en) != len(fi): mism += 1; continue
    for a, b in zip(en, fi):
        pairs += 1
        if a["answer"] != b["answer"]: mism += 1
P("CUBI en/fi pairs", pairs, "mismatch", mism)
# cubicasa answer distribution extremes
P("CUBI max answers by template", sorted(C((r["question"][:40], r["answer"]) for r in cc if r["answer"] >= 30).items())[:10])
P("CUBI zero share", round(sum(1 for r in cc if r["answer"] == 0) / len(cc), 4))
# families per drawing count distribution
P("CUBI q per drawing", sorted(C(len(v) for v in byp.values()).items()))
# swiss pair agreement: same floor, count templates en vs local for the fixed templates
sw = [r for r in rows if src(r) == "swiss_dwellings"]
key = [("windows", r"windows are drawn|Fenster sind|fenêtres sont|finestre sono"), ("doors", r"How many doors|Wie viele Türen|Combien de portes|Quante porte"),
       ("toilets", r"toilets \(WC\)|Wie viele WCs|Combien de WC|Quanti WC"), ("washbasins", r"washbasins|Lavabos|lavabos|lavabi"),
       ("bathtubs", r"bathtubs|Badewannen|baignoires|vasche"), ("showers", r"showers|Duschen|douches|docce"),
       ("apartments", r"How many apartments|Wie viele Wohnungen|Combien d.appartements|Quanti appartamenti"),
       ("floor_area", r"all numbered indoor|aller nummerierten|intérieures numérotées|interni numerati"),
       ("apt_area", r"area of apartment|Nettowohnfläche von Wohnung|de l.appartement|dell.appartamento"),
       ("label_area", r"all rooms labelled|aller Räume mit der Bezeichnung|toutes les pièces désignées|tutti i locali denominati"),
       ("room_area", r"area of room|Nettofläche von Raum|de la pièce|del locale"),
       ("label_count", r"rooms labelled|Räume mit der Bezeichnung|portant la désignation|con la denominazione")]
def fam(q):
    for k, rx in key:
        if re.search(rx, q): return k
    return "?"
fc = C(fam(r["question"]) for r in sw)
P("SWISS families", dict(fc))
P("SWISS drawings per family", {k: len(set(r["path"] for r in sw if fam(r["question"]) == k)) for k, _ in key})
d = collections.defaultdict(list)
for r in sw:
    f = fam(r["question"])
    if f in ("windows", "doors", "toilets", "washbasins", "bathtubs", "showers", "apartments", "floor_area"):
        d[(r["path"], f)].append(r["answer"])
P("SWISS fixed-family pairs", sum(1 for v in d.values() if len(v) == 2), "mismatch", sum(1 for v in d.values() if len(v) == 2 and v[0] != v[1]), "non-pairs", C(len(v) for v in d.values()))
# zero answers per family (is 'absent -> not asked'?)
P("SWISS zero answers by family", {k: sum(1 for r in sw if fam(r["question"]) == k and r["answer"] == 0) for k, _ in key})
P("CUBI zero by template(en)", {r0: sum(1 for r in cc if r["question"] == r0 and r["answer"] == 0) for r0 in sorted(set(r["question"] for r in cc if r["question"].startswith("How")))})
# label vocabulary swiss
labs = C(re.search(r"['‘«„\"]\s?(.+?)\s?['’»“\"]", r["question"]).group(1) if re.search(r"['‘«„\"]\s?(.+?)\s?['’»“\"]", r["question"]) else None for r in sw if fam(r["question"]) in ("label_count", "label_area"))
P("SWISS label vocab size", len(labs), labs.most_common(25))
# ifc models
im = [r for r in rows if src(r) == "ifc_models"]
ifcs = sorted(os.path.splitext(f)[0] for f in os.listdir(f"{ROOT}/data/ifc_models") if f.lower().endswith(".ifc"))
def model_of(p):
    st = os.path.splitext(os.path.basename(p))[0]; best = ""
    for s0 in ifcs:
        if (st == s0 or st.startswith(s0 + "_")) and len(s0) > len(best): best = s0
    return best
def lang(q):
    for l, rx in [("en", r"^(How|What)"), ("de", r"^Wie"), ("et", r"^(Kui|Mitu)"), ("nl", r"^(Wat|Hoeveel)"), ("es", r"^¿"), ("da", r"^(Hvad|Hvor)"), ("pl", r"^(Jaka|Ile)"), ("ro", r"^Care"), ("it", r"^Qual")]:
        if re.search(rx, q): return l
    return "??"
P("IFCM lang rows", C(lang(r["question"]) for r in im))
mm = collections.defaultdict(lambda: [0, set(), set()])
for r in im:
    k = model_of(r["path"]); mm[k][0] += 1; mm[k][1].add(lang(r["question"])); mm[k][2].add(r["path"])
for k, v in sorted(mm.items(), key=lambda kv: -kv[1][0]): P("IFCM", v[0], len(v[2]), sorted(v[1]), k)
P("IFCM type by ext", C((os.path.splitext(r["path"])[1], r["type"]) for r in im))
# ICC proxy: mode-guess correctness per template, clustered by drawing (cubicasa) -> design effect
def icc(groups):
    # one-way ANOVA ICC for binary outcomes
    n = sum(len(g) for g in groups); k = len(groups)
    gm = sum(sum(g) for g in groups) / n
    ssb = sum(len(g) * (sum(g) / len(g) - gm) ** 2 for g in groups)
    ssw = sum(sum((x - sum(g) / len(g)) ** 2 for x in g) for g in groups)
    msb = ssb / (k - 1); msw = ssw / (n - k)
    n0 = (n - sum(len(g) ** 2 for g in groups) / n) / (k - 1)
    return (msb - msw) / (msb + (n0 - 1) * msw), n0, gm
T = collections.defaultdict(C)
for r in cc: T[r["question"]][r["answer"]] += 1
mode = {q: c.most_common(1)[0][0] for q, c in T.items()}
g = collections.defaultdict(list)
for r in cc: g[r["path"]].append(1 if r["answer"] == mode[r["question"]] else 0)
i, n0, gm = icc(list(g.values()))
P("CUBI mode-baseline acc", round(gm, 4), "ICC by drawing", round(i, 3), "avg cluster", round(n0, 1), "design effect", round(1 + (n0 - 1) * i, 2))
