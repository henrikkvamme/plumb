"""Shared question parser for swiss_dwellings templates (imported by the probe scripts).

parse(question) -> (family, param, lang) or (None, None, None).
"""
import re

OUTDOOR = {"Balkon", "Balcon", "Balcone", "Loggia", "Terrasse", "Terrazza", "Sitzplatz", "Patio", "Garten", "Jardin", "Giardino"}

_P = [
    ("area_apartment", r"net floor area of apartment ([A-Z]+) in", "en"),
    ("area_apartment", r"Nettowohnfläche von Wohnung ([A-Z]+) in", "de"),
    ("area_apartment", r"surface nette de l'appartement ([A-Z]+) en", "fr"),
    ("area_apartment", r"superficie netta dell'appartamento ([A-Z]+) in", "it"),
    ("area_total", r"numbered indoor rooms", "en"),
    ("area_total", r"nummerierten Innenräume", "de"),
    ("area_total", r"pièces intérieures numérotées", "fr"),
    ("area_total", r"locali interni numerati", "it"),
    ("area_label", r"all rooms labelled '(.+)' on this floor", "en"),
    ("area_label", r"aller Räume mit der Bezeichnung «(.+)» in", "de"),
    ("area_label", r"toutes les pièces désignées «(.+)» à", "fr"),
    ("area_label", r"tous les locaux désignés «(.+)» à", "fr"),
    ("area_label", r"tutti i locali denominati «(.+)» in", "it"),
    ("area_room", r"net floor area of room (\S+) \(", "en"),
    ("area_room", r"Nettofläche von Raum (\S+) \(", "de"),
    ("area_room", r"surface nette de la pièce (\S+) \(", "fr"),
    ("area_room", r"superficie netta del locale (\S+) \(", "it"),
    ("count_label", r"rooms labelled '(.+)' are there", "en"),
    ("count_label", r"Bezeichnung «(.+)» gibt", "de"),
    ("count_label", r"désignation «(.+)» y a", "fr"),
    ("count_label", r"denominazione «(.+)» ci sono", "it"),
    ("apartments", r"How many apartments", "en"),
    ("apartments", r"Wie viele Wohnungen", "de"),
    ("apartments", r"Combien d'appartements", "fr"),
    ("apartments", r"Quanti appartamenti", "it"),
    ("doors", r"How many doors|Wie viele Türen|Combien de portes|Quante porte", None),
    ("windows", r"How many windows|Wie viele Fenster|Combien de fenêtres|Quante finestre", None),
    ("toilets", r"How many toilets|Wie viele WCs|Combien de WC|Quanti WC", None),
    ("washbasins", r"How many washbasins|Wie viele Lavabos|Combien de lavabos|Quanti lavabi", None),
    ("bathtubs", r"How many bathtubs|Wie viele Badewannen|Combien de baignoires|Quante vasche", None),
    ("showers", r"How many showers|Wie viele Duschen|Combien de douches|Quante docce", None),
]
_C = [(f, re.compile(p), l) for f, p, l in _P]


def lang_of(q):
    if re.match(r"(How|What)\b", q):
        return "en"
    if re.match(r"(Wie)\b", q):
        return "de"
    if re.match(r"(Combien|Quelle)\b", q):
        return "fr"
    if re.match(r"(Quant|Qual)", q):
        return "it"
    return "?"


def norm_label(s):
    return s.replace(" ", " ").replace(" ", " ").strip()


def parse(q):
    for fam, rx, _ in _C:
        m = rx.search(q)
        if m:
            param = norm_label(m.group(1)) if m.groups() else None
            return fam, param, lang_of(q)
    return None, None, lang_of(q)
