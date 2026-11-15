"""Shared helpers: load questions, assign source, template family, language and group."""
import json, os, re, collections

def load(root):
    rows = [json.loads(l) for l in open(os.path.join(root, "questions.jsonl"))]
    for i, r in enumerate(rows):
        r["i"] = i
        r["source"] = r["path"].split("/")[1]
        r["family"], r["lang"] = family_lang(r)
        r["group"] = group(r)
    return rows

CUBI = [("windows", r"windows|ikkunaa"), ("storeys", r"storeys|kerrosta"), ("toilet_bowls", r"toilet bowls|WC-istuinta"),
        ("sinks", r"sinks|allasta"), ("showers_baths", r"showers and bathtubs|suihkua"), ("doors", r"doors|ovea"),
        ("saunas", r"saunas|saunaa"), ("kitchens", r"kitchens|keittiötä"), ("bedrooms", r"bedrooms|makuuhuonetta"),
        ("bathrooms", r"bathrooms or|kylpy- tai"), ("wc_rooms", r"separate WC|erillistä WC"), ("balconies", r"balconies|parveketta")]
SWISS = [("area_room", r"of room |von Raum |de la pièce |del locale "), ("area_apartment", r"apartment [A-Z] |Wohnung [A-Z] |appartement [A-Z] |appartamento [A-Z] "),
         ("area_floor", r"all numbered indoor|aller nummerierten|intérieures numérotées|interni numerati"),
         ("area_label_total", r"total net area in m² of all rooms labelled|gesamte Nettofläche in m² aller Räume mit|pièces désignées|locali denominati"),
         ("count_label", r"rooms labelled|Räume mit der Bezeichnung|portant la désignation|con la denominazione"),
         ("apartments", r"apartments|Wohnungen|appartements|appartamenti"), ("doors", r"doors|Türen|portes|porte "),
         ("windows", r"windows|Fenster|fenêtres|finestre"), ("toilets", r"toilets|WCs|de WC|WC sono"),
         ("washbasins", r"washbasins|Lavabos|lavabos|lavabi"), ("bathtubs", r"bathtubs|Badewannen|baignoires|vasche"),
         ("showers", r"showers|Duschen|douches|docce")]
LANG = [("de", r"^(Wie|Was) "), ("fr", r"^(Combien|Quelle|Quel) "), ("it", r"^(Quant[iae]|Qual è) "), ("fi", r"^Kuinka "),
        ("nl", r"^(Wat|Hoeveel) "), ("es", r"^¿"), ("da", r"^(Hvad|Hvor) "), ("et", r"^(Mitu|Kui) "), ("pl", r"^(Jaka|Ile) "),
        ("ro", r"^Care "), ("en", r"^(How|What|On|Which|Is|Are|Where|Could|Does|Do|Can|Give|List|Provide|Describe|Show|Tell|Who|When|Please|In|For|Summar|Identify) ")]
IFC_ELEM = [("rooms", r"room|space|Räume|ruimtes|locales|rum |ruumi|pomieszcze"), ("doors", r"door|Türen|deuren|puertas|døre|ust |drzwi|porte"),
            ("windows", r"window|Fenster|ramen|ventanas|vinduer|akent|finestre|ferestre|okien"), ("walls", r"wall|Wände|wanden|muros|vægge|seina|ścian|muri|pereți"),
            ("stairs", r"stair|Treppen|trappen|escaleras|trapper|treppi|scări|schodów"), ("columns", r"column|Stützen|kolommen|pilares|søjler|posti|stâlpi"),
            ("beams", r"beam|Träger|balken|vigas|bjælker|tala|grinzi|belek"), ("slabs", r"slab|Decken|vloeren|dæk"),
            ("sanitary", r"sanitary|Sanitär|sanitaire"), ("lights", r"light fixture|iluminat")]

def lang_of(q):
    for l, p in LANG:
        if re.search(p, q): return l
    return "other"

def family_lang(r):
    q, s = r["question"], r["source"]
    lang = lang_of(q)
    if s == "cubicasa5k":
        for f, p in CUBI:
            if re.search(p, q): return f, lang
    if s == "swiss_dwellings":
        for f, p in SWISS:
            if re.search(p, q): return f, lang
    if s == "ifc_models":
        scope = "model" if re.search(r"in the model|enthält das Modell|bevat het model|en el modelo|i modellen|mudelis|nel modello|din modelul|w modelu", q) else "level"
        t = r["type"]
        if t == "area":
            if re.search(r"side area|Seitenfläche|zijoppervlakte|sideareal", q): return "wall_side_area_level", lang
            if re.search(r"total|gesamte|totale|samlede|kokku|łączna", q): return "area_rooms_level", lang
            return "area_room", lang
        if t == "volume":
            return ("slab_volume_level" if re.search(r"slab|Decken|vloeren|dæk", q) else "wall_volume_level"), lang
        if t == "length": return "wall_length_level", lang
        for f, p in IFC_ELEM:
            if re.search(p, q): return f"count_{f}_{scope}", lang
    if s == "opening_design":
        return "schedule_" + r["type"], lang
    if s == "ifc_bench":
        return "freetext", lang
    return "unknown", lang

def group(r):
    s, name = r["source"], os.path.basename(r["path"])
    if s == "swiss_dwellings": return name.split("_")[0]                    # site
    if s == "ifc_models": return name.split("_")[0]                         # project prefix, e.g. bimspeed-vitoria
    if s == "ifc_bench": return re.sub(r"_(arc|mep|str|electrical|plumbing|hvac|gis_city|city)\.ifc$", "", name)
    if s == "opening_design": return r["path"].split("/")[3]
    return os.path.splitext(name)[0]                                        # cubicasa: the drawing itself

def masked(q):
    return re.sub(r"\d+([.,]\d+)?", "<N>", q)
