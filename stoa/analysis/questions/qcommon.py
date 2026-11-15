"""Shared helpers for the question-file analysis scripts.

Not a script. The analysis scripts in this folder import it. It has no third-party dependencies.

Template extraction: a question becomes a template string plus a list of slots. Slots are quoted
labels (room labels, room names, storey names, model names), room and apartment ids, and, for the
hand-written opening_design questions, the sheet id and project name.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

STOA = Path(__file__).resolve().parents[2]
FULL = STOA / "data" / "junction-dataset" / "questions.jsonl"
PREVIEW = STOA / "data" / "junction-dataset-preview" / "questions.jsonl"
OUT_DIR = Path(__file__).resolve().parent / "out"


def load(path: Path = FULL) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            r = json.loads(line)
            r["_i"] = i
            rows.append(r)
    return rows


def source(r: dict) -> str:
    return r["path"].split("/")[1]


def stem(path: str) -> str:
    """Drawing id without extension, so a PDF and its DXF/PNG copies share a key."""
    return path.rsplit(".", 1)[0]


# ---------------------------------------------------------------- quoted slots
# Opening and closing quote pairs seen in the file. Single and double ASCII quotes need care:
# French and English labels contain apostrophes ("Cage d'escalier", "WOMEN'S"). A quote opens only
# when no word character precedes it and closes only when no word character follows it.
_QUOTE_RES = [
    re.compile(r"«\s?(.+?)\s?»"),
    re.compile(r"„(.+?)[“”\"]"),
    re.compile(r"“(.+?)”"),
    re.compile(r"‚(.+?)[‘’]"),
    re.compile(r"(?<![\w])'(.+?)'(?![\w])"),
    re.compile(r"(?<![\w])\"(.+?)\"(?![\w])"),
]

ROOM_WORDS = r"Raum|room|pièce|locale|local|stanza|Raumes"
APT_WORDS = r"Wohnung|apartment|appartement|l'appartement|appartamento|dell'appartamento|logement"
MODEL_WORDS = (
    r"model|modell|modellen|Modell|modelo|modello|modelul|modelu|mudelis|het model|bevat het model"
)


def _quoted_spans(q: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for rx in _QUOTE_RES:
        for m in rx.finditer(q):
            s, e = m.span()
            if any(not (e <= a or s >= b) for a, b, _ in spans):
                continue
            spans.append((s, e, m.group(1)))
    spans.sort()
    return spans


def templatize(r: dict) -> tuple[str, list[tuple[str, str]]]:
    """Return (template, slots). Each slot is (kind, value)."""
    q = r["question"]
    src = source(r)
    if src == "opening_design":
        return _templatize_od(q)
    if src == "ifc_bench":
        return _templatize_bench(q)
    spans = _quoted_spans(q)
    kinds = []
    for s, e, val in spans:
        ctx = q[max(0, s - 22) : s]
        if src == "swiss_dwellings":
            kinds.append("label")
        elif re.search(r"(" + MODEL_WORDS + r")\s*$", ctx, re.I):
            kinds.append("model")
        else:
            kinds.append("quoted")
    if src == "ifc_models":
        # Two non-model quoted values: room name, then storey. One: storey.
        n_q = kinds.count("quoted")
        order = iter(["room", "storey"] if n_q == 2 else ["storey"] * n_q)
        kinds = [next(order) if k == "quoted" else k for k in kinds]
    out, slots, last = [], [], 0
    for (s, e, val), kind in zip(spans, kinds):
        out.append(q[last:s])
        out.append("{" + kind.upper() + "}")
        slots.append((kind, val))
        last = e
    out.append(q[last:])
    t = "".join(out)
    if src == "swiss_dwellings":
        def room_id(m):
            slots.append(("room_id", m.group(2)))
            return m.group(1) + " {ROOM_ID}"

        def apt_id(m):
            slots.append(("apt_id", m.group(2)))
            return m.group(1) + " {APT_ID}"

        t = re.sub(r"\b(" + ROOM_WORDS + r")\s+([A-Z]{0,2}\d[\w.\-]*)", room_id, t)
        t = re.sub(r"(" + APT_WORDS + r")\s+([A-Z][\w\-]*|\d+)", apt_id, t)
    return t, slots


def _templatize_od(q: str) -> tuple[str, list[tuple[str, str]]]:
    slots = []
    m = re.search(r"sheet ([A-Z]-?\d{3})", q)
    if m:
        slots.append(("sheet", m.group(1)))
        q = q.replace(m.group(1), "{SHEET}")
    for proj in ["Xcel Sports Complex", "Cannery Trail Residences"]:
        if proj in q:
            slots.append(("project", proj))
            q = q.replace(proj, "{PROJECT}")
    q = q.replace(" (1750 N Oxford Ave, Eau Claire, WI)", "")
    return q, slots


def _templatize_bench(q: str) -> tuple[str, list[tuple[str, str]]]:
    # Free-text IFC-Bench questions. The template is the question with case and spacing normalised.
    return re.sub(r"\s+", " ", q.strip()), []


# ---------------------------------------------------------------- language
# Stopword detector on the template text with slots removed (slot values are often in another
# language than the question: English questions quote German room labels).
STOP = {
    "en": "the how many what which is are were was of on this in all rooms floor plan drawn shown there model total net area with and does do types include information data applied building used".split(),
    "fi": "kuinka monta pohjapiirustuksessa on pohjapiirustukseen piirretty kerrosta lasketaan ja tai ilman".split(),
    "de": "wie viele sind auf diesem grundriss eingezeichnet gibt es der die des im mit bezeichnung gross groß von raum alle räume geschoss in enthält das modell".split(),
    "fr": "combien de y a-t-il à cet étage quelle est la surface nette pièce sont dessinées sur ce plan les des toutes".split(),
    "it": "quanti quante locali con la denominazione ci sono in questo piano qual è superficie netta del sono disegnate questa pianta di tutti nel modello".split(),
    "es": "cuál es el número de en la planta del local superficie útil plano los todos modelo".split(),
    "nl": "wat is de netto vloeroppervlakte van ruimte op hoeveel staan er plattegrond het totale alle wanden bevat model".split(),
    "da": "hvad er nettoarealet af rummet på hvor mange vist plantegningen for det samlede alle der i modellen".split(),
    "et": "kui suur on ruumi netopõrandapind korrusel mitu näidatud korruse plaanil kõigi ruumide kokku mudelis".split(),
    "pl": "jaka jest powierzchnia netto pomieszczenia na kondygnacji ile pokazano rzucie łączna wszystkich znajduje się w modelu".split(),
    "ro": "care este numărul de pe planul nivelului din modelul".split(),
    "sv": "hur många finns på denna ritning vad är rummet våning".split(),
}
STOP = {k: set(v) for k, v in STOP.items()}


def detect_lang(template: str) -> str:
    text = re.sub(r"\{[A-Z_]+\}", " ", template).lower()
    words = re.findall(r"[\wäöüßéèàâêîôûçåøæõšžąćęłńóśźżăâîșț\-]+", text)
    if not words:
        return "und"
    scores = {k: sum(w in s for w in words) / len(words) for k, s in STOP.items()}
    best = max(scores, key=scores.get)
    ranked = sorted(scores.values(), reverse=True)
    if ranked[0] == 0:
        return "und"
    # Ties between close languages: resolve by language-specific markers.
    if ranked[0] == ranked[1]:
        if re.search(r"[õ]|mitu|kui suur", text):
            return "et"
        if re.search(r"[øæå]|hvad|hvor", text):
            return "da"
        if re.search(r"[ăîșț]|care este", text):
            return "ro"
        if re.search(r"[łąęśźż]|ile |jaka", text):
            return "pl"
        if re.search(r"¿|cuál", text):
            return "es"
        if re.search(r"hoeveel|wat is", text):
            return "nl"
    return best


# ---------------------------------------------------------------- answers
def answer_key(r: dict):
    """Hashable answer for equality checks. Counts as int, measures rounded to 1e-6."""
    a = r["answer"]
    if isinstance(a, str):
        return a
    if r["type"] == "count":
        return int(a)
    return round(float(a), 6)


def correct(pred, r: dict) -> bool:
    """Scoring rule of the dataset README: counts exact, measures within 2%, text exact (no rule)."""
    a = r["answer"]
    if pred is None:
        return False
    if r["type"] == "count":
        return int(pred) == int(a)
    if r["type"] in ("area", "volume", "length"):
        a = float(a)
        if a == 0:
            return float(pred) == 0
        return abs(float(pred) - a) <= 0.02 * abs(a)
    return str(pred).strip() == str(a).strip()


def best_constant(rows: list[dict]):
    """The single answer that scores the most rows. For measures, search over observed values."""
    if not rows:
        return None, 0
    t = rows[0]["type"]
    if t in ("area", "volume", "length"):
        vals = sorted(float(r["answer"]) for r in rows)
        # A prediction p covers answers in [p/1.02, p/0.98]. Two-pointer over candidate p = v*1.02.
        best, bestn, j, k = None, 0, 0, 0
        n = len(vals)
        for i, v in enumerate(vals):
            p = v * 1.02 if v > 0 else v
            lo, hi = p / 1.02, p / 0.98
            while j < n and vals[j] < lo - 1e-12:
                j += 1
            while k < n and vals[k] <= hi + 1e-12:
                k += 1
            if k - j > bestn:
                best, bestn = p, k - j
        return best, bestn
    c = Counter(answer_key(r) for r in rows)
    v, n = c.most_common(1)[0]
    return v, n


def entropy_bits(values) -> float:
    c = Counter(values)
    n = sum(c.values())
    return -sum(v / n * math.log2(v / n) for v in c.values())


def sha256_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- annotation and pairing
def annotate(rows: list[dict]) -> list[dict]:
    """Add _src, _tpl, _slots, _lang, _sk (slot values key) to each row in place."""
    for r in rows:
        t, sl = templatize(r)
        r["_src"] = source(r)
        r["_tpl"] = t
        r["_slots"] = sl
        r["_lang"] = detect_lang(t) if r["_src"] != "opening_design" else "en"
        r["_sk"] = tuple(v for _, v in sl)
    return rows


def template_ids(rows: list[dict]) -> dict[tuple[str, str], str]:
    """Stable template ids: <source>/T<nnn>, ordered by frequency then text."""
    c = Counter((r["_src"], r["_tpl"]) for r in rows)
    ids = {}
    per_src: dict[str, int] = Counter()
    for (s, t), _ in sorted(c.items(), key=lambda kv: (kv[0][0], -kv[1], kv[0][1])):
        ids[(s, t)] = f"{s}/T{per_src[s]:03d}"
        per_src[s] += 1
    return ids


def pair_templates(rows: list[dict]) -> dict[tuple[str, str], dict]:
    """Find the English partner of each non-English template.

    Two questions are candidate pairs when they share the drawing (path) and the slot values. The
    partner is the English template with the most such co-occurrences with an equal answer. It
    returns {(src, tpl): {"partner": (src, tpl) or None, "both": n, "agree": n}}.
    """
    by_key: dict[tuple, list[dict]] = {}
    for r in rows:
        if r["_src"] in ("ifc_bench", "opening_design"):
            continue
        by_key.setdefault((r["path"], r["_sk"]), []).append(r)
    co: dict[tuple, Counter] = {}
    agree: dict[tuple, Counter] = {}
    for grp in by_key.values():
        ens = [r for r in grp if r["_lang"] == "en"]
        for r in grp:
            if r["_lang"] == "en":
                continue
            a = (r["_src"], r["_tpl"])
            for e in ens:
                b = (e["_src"], e["_tpl"])
                co.setdefault(a, Counter())[b] += 1
                if answer_key(e) == answer_key(r):
                    agree.setdefault(a, Counter())[b] += 1
    out = {}
    for a in co:
        ag = agree.get(a, Counter())
        b = max(co[a], key=lambda k: (ag[k], co[a][k])) if co[a] else None
        out[a] = {"partner": b, "both": co[a][b] if b else 0, "agree": ag[b] if b else 0}
    return out


def families(rows: list[dict]) -> dict[tuple[str, str], str]:
    """Family = an English template plus its translations. ifc_bench and opening_design get coarse
    keyword families because their questions are free text."""
    pairs = pair_templates(rows)
    ids = template_ids(rows)
    fam = {}
    for r in rows:
        k = (r["_src"], r["_tpl"])
        if k in fam:
            continue
        if r["_src"] == "ifc_bench":
            fam[k] = "ifc_bench/" + bench_family(r["question"])
        elif r["_src"] == "opening_design":
            fam[k] = "opening_design/" + r["type"]
        elif r["_lang"] == "en":
            fam[k] = "F:" + ids[k]
        elif k in pairs and pairs[k]["partner"] is not None:
            fam[k] = "F:" + ids[pairs[k]["partner"]]
        else:
            fam[k] = "F:" + ids[k]
    return fam


_BENCH_FAMS = [
    ("software_project", r"software|standard|project|location|coordinat|site|schema|author|town"),
    ("materials", r"material|insulation|glazing|finish|concrete|steel|timber"),
    ("spaces_areas", r"space|room|area|floor area|gross|net|unit|apartment|office|kitchen"),
    ("doors_windows", r"door|window|opening|curtain"),
    ("walls_slabs", r"wall|slab|roof|beam|column|stair|ramp|railing|foundation"),
    ("mep", r"duct|pipe|valve|sanitary|plumbing|light|electric|ventilat|heating|fixture|terminal|pump"),
    ("levels", r"level|storey|floor|elevation|height"),
]


def bench_family(q: str) -> str:
    ql = q.lower()
    for name, rx in _BENCH_FAMS:
        if re.search(rx, ql):
            return name
    return "other"


# ---------------------------------------------------------------- grouping keys
# ifc_bench files that are the same building as an ifc_models project. Eight pairs are
# byte-identical files (sha1 checked in split.py); duplex and dental_clinic are the same building.
BENCH_TO_PROJECT = {
    "molio": "bsc-molio",
    "ac20": "kit-institute",
    "digital_hub": "rwth-digitalhub",
    "fzk_house": "kit-fzk-haus",
    "smiley_west": "kit-smiley-west",
    "duplex": "bsc-duplex",
    "dental_clinic": "bsc-clinic",
}


def group_key(path: str) -> str:
    """The unit that must not cross a split: a building, model project or drawing set."""
    parts = path.split("/")
    src, name = parts[1], parts[-1]
    if src == "cubicasa5k":
        return "cubicasa5k:" + name.rsplit("-", 1)[1].split(".")[0]
    if src == "swiss_dwellings":
        m = re.match(r"site(\d+)_bldg(\d+)", name)
        return "swiss:site" + m.group(1)
    if src == "ifc_models":
        return "ifc:" + name.split("_", 1)[0]
    if src == "ifc_bench":
        base = re.sub(r"_(arc|str|mep|plumbing|heating|ventilation|electrical|gis_city)\.ifc$", "", name)
        base = base.replace(".ifc", "")
        proj = BENCH_TO_PROJECT.get(base)
        return "ifc:" + proj if proj else "ifc_bench:" + base
    if src == "opening_design":
        return "opening_design:" + parts[2]
    if src == "habs":
        return "habs:" + name.split("_sheet")[0]  # survey id, e.g. ak0003
    if src == "finna":
        return "finna:" + name.split("_")[0]  # archive record id
    if src == "europeana":
        return "europeana:" + stem(name).rsplit("_", 1)[0]
    return src + ":" + stem(name)
