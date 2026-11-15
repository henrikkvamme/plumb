"""Shared helpers for the red-team eval-design measurements."""
import json, re, os, collections
ROOT = "./stoa/data/junction-dataset"
Q = ROOT + "/questions.jsonl"
def load():
    return [json.loads(l) for l in open(Q)]
def src(p): return p.split("/")[1]
_quoted = re.compile(r"'(?:[^']|'(?=\w))*'|«[^»]*»|„[^“”\"]*[“”\"]|“[^”]*”|\"[^\"]*\"|”[^”]*”|‘[^’]*’")
_num = re.compile(r"\d+(?:[.,]\d+)*")
def template(q, source=None):
    """Mask quoted labels and numbers. Returns the template string."""
    t = _quoted.sub("<L>", q)
    t = re.sub(r"\b(Wohnung|apartment|l'appartement|appartement|appartamento|Apartment) [A-Z]{1,2}\b", r"\1 <A>", t)
    t = _num.sub("<N>", t)
    return t

EN_START = ("How ", "What ", "Which ", "On sheet", "Are ", "Is ", "Does ", "Do ", "Where ", "List ", "Who ", "When ", "Can ", "Give ", "Show ", "Provide ", "Describe ", "Tell ", "Why ", "In ", "For ", "Has ", "Have ", "Were ", "Was ", "Name ", "Identify ", "Summar", "Explain ", "Count ", "Could ", "Please ", "Break ", "Find ", "At ", "Of ", "Total ", "Compare ", "Did ", "Should ", "Would ", "Based ", "From ", "Per ", "Get ", "The ", "Each ", "Any ", "Across ", "Between ", "Within ", "To ", "By ", "With ", "A ", "An ", "I ")
LANG_START = [("Kuinka","fi"),("Wie ","de"),("Combien","fr"),("Quelle","fr"),("Quanti","it"),("Quante","it"),
  ("Qual è","it"),("¿","es"),("Wat ","nl"),("Hoeveel","nl"),("Hvad","da"),("Hvor","da"),("Kui ","et"),("Mitu","et"),
  ("Ile ","pl"),("Jaka","pl"),("Care ","ro"),("Câ","ro"),("Qual ","pt"),("Quant","pt")]
def lang(q):
    for k,l in LANG_START:
        if q.startswith(k): return l
    return "en"
def model_of(path):
    """Group key: the unit that near-copies share."""
    s = src(path); b = os.path.basename(path)
    if s == "swiss_dwellings":
        m = re.match(r"site(\d+)_bldg(\d+)_floor(\d+)", b); return f"swiss/site{m.group(1)}"
    if s == "ifc_models":
        stem = os.path.splitext(b)[0]; stem = re.sub(r"_(plan|elevation|section)[-_].*$", "", stem); return "ifcm/" + stem
    if s == "ifc_bench":
        return "ifcb/" + re.sub(r"_(arc|mep|str|heating|plumbing|ventilation|electrical|facade|kitchen|gis_city)\.ifc$", "", b)
    if s == "opening_design":
        return "od/" + path.split("/")[2]
    return s + "/" + os.path.splitext(b)[0]
def items():
    """Rows with source, lang, template, family (EN template of the pair), pair id, group."""
    rows = load(); out = []; prev = None; pid = -1
    for i, r in enumerate(rows):
        s = src(r["path"]); l = lang(r["question"]); t = template(r["question"])
        paired = prev is not None and l != "en" and prev["lang"] == "en" and prev["path"] == r["path"] and prev["answer"] == r["answer"] and not prev.get("_used")
        if paired:
            fam = prev["family"]; prev["_used"] = True; prev["has_pair"] = True
        else:
            pid += 1; fam = t
        d = dict(r, i=i, source=s, lang=l, template=t, family=fam, pair=pid, group=model_of(r["path"]), has_pair=paired)
        out.append(d); prev = d
    return out
