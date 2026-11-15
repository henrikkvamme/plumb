"""Hard questions on Swiss Dwellings floors: aggregates, derived values, conditional counts, lookups, units, gaps.

Each family is a function `floor -> list[Spec]`. A spec holds no document: the same question is valid on the
PDF, the PNG and the DXF of the floor, so the selector picks the input. Every key comes from the DXF path and is
kept only when the source path (and the PDF probe, and the printed area, and the public answer, where they
exist) agrees within 1%.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING

from pydantic import Field

from bp.contract import CountKey, Frozen, Key, LookupKey, MeasureKey, MissingReason, UnanswerableKey
from bp.hardcases.common import SQFT_PER_M2, Skill, close, r2, rank
from bp.hardcases.swiss_facts import OUTDOOR_SUBTYPES, SwissFloor, SwissRoom

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

AGREE = 0.01


class Spec(Frozen):
    family: str
    skill: Skill
    question: str
    key: Key
    local: str = ""  # the same question in the language of the sheet, or ""
    how: str = ""


class Context(Frozen):
    """What the generator knows about a floor beyond the facts: its language and public reference answers."""

    lang: str
    apartment_ref: dict[str, float] = Field(default_factory=dict)  # public answer: net area of apartment X
    room_ref: dict[str, float] = Field(default_factory=dict)  # public answer: net area of room N
    label_count_ref: dict[str, float] = Field(default_factory=dict)  # public answer: number of rooms labelled X
    label_area_ref: dict[str, float] = Field(default_factory=dict)  # public answer: total area of rooms labelled X


# ----------------------------------------------------------------------------- vocabulary per sheet language

BATH = {"de": "Bad", "fr": "Bain", "it": "Bagno"}
BED = {"de": "Schlafzimmer", "fr": "Chambre à coucher", "it": "Camera da letto"}
ROOM = {"de": "Zimmer", "fr": "Pièce", "it": "Stanza"}
KITCHEN = {"de": "Küche", "fr": "Cuisine", "it": "Cucina"}
CORRIDOR = {"de": "Korridor", "fr": "Couloir", "it": "Corridoio"}
STAIR = {"de": "Treppenhaus", "fr": "Cage d'escalier", "it": "Vano scala"}
APT_TAG = {"de": "Whg.", "fr": "App.", "it": "App."}

ABSENT = (  # things a Swiss Dwellings sheet never labels; (en, de, fr, it, labels that would mean it is there)
    ("the sauna", "der Sauna", "du sauna", "della sauna", ("Sauna",)),
    ("the garage", "der Garage", "du garage", "del garage", ("Garage", "Einstellhalle", "Autorimessa")),
    ("the swimming pool", "des Schwimmbads", "de la piscine", "della piscina", ("Schwimmbad", "Piscine", "Piscina")),
    ("the wine cellar", "des Weinkellers", "de la cave à vin", "della cantina dei vini", ("Weinkeller",)),
)


def q(lang: str, text: str) -> str:
    """Quote a label as the public questions do: '...' in English, «...» elsewhere."""
    return f"'{text}'" if lang == "en" else f"«{text}»"


# ----------------------------------------------------------------------------- checks


def indoor(r: SwissRoom) -> bool:
    return not r.outdoor


def outdoor_agrees(r: SwissRoom) -> bool:
    return r.subtype is None or r.outdoor == (r.subtype in OUTDOOR_SUBTYPES)


def area_ok(r: SwissRoom, ctx: Context) -> bool:
    """Every witness of the room area agrees with the DXF polygon."""
    if r.area_pdf is None or r.area_src is None:
        return False
    if not (close(r.area_dxf, r.area_pdf, AGREE) and close(r.area_dxf, r.area_src, AGREE)):
        return False
    if r.printed is not None and abs(r.printed - r.area_dxf) > 0.006:
        return False
    ref = ctx.room_ref.get(r.num)
    return ref is None or close(ref, r.area_dxf, AGREE)


def floor_ok(f: SwissFloor, ctx: Context) -> bool:
    """A floor is usable when every room passes the area checks and the outdoor flag agrees with the source."""
    if not f.source_aligned or f.error or not f.rooms or f.stray_labels:
        return False
    if len({r.num for r in f.rooms}) != len(f.rooms):
        return False
    for lab, n in ctx.label_count_ref.items():
        if len(labelled(f, lab)) != n:
            return False
    for lab, area in ctx.label_area_ref.items():
        if not close(sum(r.area_dxf for r in labelled(f, lab)), area, AGREE):
            return False
    return all(area_ok(r, ctx) and outdoor_agrees(r) for r in f.rooms)


def openings_ok(rooms: Iterable[SwissRoom]) -> bool:
    return all(r.windows_src == r.windows_dxf and r.doors_src == r.doors_dxf for r in rooms)


def sum_paths(rooms: Sequence[SwissRoom]) -> tuple[float, float, float]:
    return (
        sum(r.area_dxf for r in rooms),
        sum(r.area_pdf or 0.0 for r in rooms),
        sum(r.area_src or 0.0 for r in rooms),
    )


def agree3(values: tuple[float, float, float]) -> bool:
    a, b, c = values
    return close(a, b, AGREE) and close(a, c, AGREE)


def labelled(f: SwissFloor, label: str) -> list[SwissRoom]:
    return [r for r in f.rooms if r.label == label]


def unique_label(f: SwissFloor, r: SwissRoom) -> bool:
    return r.label is not None and len(labelled(f, r.label)) == 1


def measure(value: float, unit: str = "m2", alternates: Iterable[float] = ()) -> MeasureKey:
    main = r2(value)
    alts = tuple(sorted({r2(a) for a in alternates if not close(a, value, 0.02)}))
    return MeasureKey(value=main, unit=unit, alternates=alts)


def apartment_rooms(f: SwissFloor, letter: str) -> list[SwissRoom]:
    return [r for r in f.rooms if r.unit == letter and indoor(r)]


def apartment_area(f: SwissFloor, letter: str, ctx: Context) -> float | None:
    rooms = apartment_rooms(f, letter)
    if not rooms:
        return None
    paths = sum_paths(rooms)
    ref = ctx.apartment_ref.get(letter)
    if not agree3(paths) or (ref is not None and not close(ref, paths[0], AGREE)):
        return None
    return paths[0]


# ----------------------------------------------------------------------------- families: aggregate areas


def fam_bath_area(f: SwissFloor, ctx: Context) -> list[Spec]:
    lab = BATH[ctx.lang]
    rooms = labelled(f, lab)
    if not rooms or any(r.subtype != "BATHROOM" for r in rooms):
        return []
    total = sum_paths(rooms)
    typed = [r for r in f.rooms if r.subtype == "BATHROOM"]
    if not agree3(total):
        return []
    en = (
        f"How many square metres of bathroom floor are there on this floor? Count the rooms labelled {q('en', lab)} "
        "and give the net area as drawn."
    )
    local = {
        "de": f"Wie viele Quadratmeter Badezimmerboden gibt es auf diesem Geschoss? Zähle die Räume mit der Bezeichnung {q('de', lab)} und gib die Nettofläche wie gezeichnet an.",
        "fr": f"Combien de mètres carrés de sol de salle de bain y a-t-il à cet étage ? Compte les pièces désignées {q('fr', lab)} et donne la surface nette dessinée.",
        "it": f"Quanti metri quadrati di pavimento di bagno ci sono in questo piano? Conta i locali denominati {q('it', lab)} e indica la superficie netta disegnata.",
    }[ctx.lang]
    alt = sum(r.area_dxf for r in typed)
    how = f"sum of DXF polygon areas of {len(rooms)} rooms labelled {lab}; PDF and source sums agree within 1%"
    if not close(alt, total[0], 0.02):
        how += f"; alternate {r2(alt)} adds {len(typed) - len(rooms)} unlabelled rooms of source type BATHROOM"
    return [
        Spec(
            family="bath_area",
            skill="measure",
            question=en,
            local=local,
            key=measure(total[0], alternates=(alt,)),
            how=how,
        )
    ]


def fam_bath_tiles(f: SwissFloor, ctx: Context) -> list[Spec]:
    base = fam_bath_area(f, ctx)
    if not base:
        return []
    lab = BATH[ctx.lang]
    key = base[0].key
    assert isinstance(key, MeasureKey)
    en = (
        f"I want to tile the floors of all bathrooms on this floor (rooms labelled {q('en', lab)}). How many m² of tiles "
        "should I order if I add 10% for waste?"
    )
    local = {
        "de": f"Ich will die Böden aller Bäder auf diesem Geschoss fliesen (Räume mit der Bezeichnung {q('de', lab)}). Wie viele m² Fliesen soll ich bestellen, wenn ich 10% Verschnitt dazurechne?",
        "fr": f"Je veux carreler le sol de toutes les salles de bain de cet étage (pièces désignées {q('fr', lab)}). Combien de m² de carrelage dois-je commander en ajoutant 10% de chutes ?",
        "it": f"Voglio piastrellare i pavimenti di tutti i bagni di questo piano (locali denominati {q('it', lab)}). Quanti m² di piastrelle devo ordinare aggiungendo il 10% di sfrido?",
    }[ctx.lang]
    tiles = MeasureKey(value=r2(key.value * 1.1), unit="m2", alternates=tuple(r2(a * 1.1) for a in key.alternates))
    return [Spec(family="bath_tiles", skill="compound", question=en, local=local, key=tiles,
                 how=f"1.1 x bathroom floor area {key.value} m2")]  # fmt: skip


def fam_bedroom_area(f: SwissFloor, ctx: Context) -> list[Spec]:
    lab = BED[ctx.lang]
    rooms = labelled(f, lab)
    if not rooms or any(r.subtype != "BEDROOM" for r in rooms) or not agree3(total := sum_paths(rooms)):
        return []
    en = f"What is the total floor area of all bedrooms (rooms labelled {q('en', lab)}) on this floor, in m²?"
    local = {
        "de": f"Wie gross ist die gesamte Fläche aller Schlafzimmer (Räume mit der Bezeichnung {q('de', lab)}) auf diesem Geschoss, in m²?",
        "fr": f"Quelle est la surface totale de toutes les chambres (pièces désignées {q('fr', lab)}) à cet étage, en m² ?",
        "it": f"Qual è la superficie totale di tutte le camere (locali denominati {q('it', lab)}) in questo piano, in m²?",
    }[ctx.lang]
    return [Spec(family="bedroom_area", skill="measure", question=en, local=local, key=measure(total[0]),
                 how=f"sum of {len(rooms)} rooms labelled {lab}, three paths agree")]  # fmt: skip


def fam_apartment_area(f: SwissFloor, ctx: Context) -> list[Spec]:
    out: list[Spec] = []
    for letter in f.apartments:
        area = apartment_area(f, letter, ctx)
        if area is None:
            continue
        en = (
            f"What is the living area of apartment {letter} in m²? Count the rooms inside its outline and leave out "
            "balconies, loggias and terraces."
        )
        local = {
            "de": f"Wie gross ist die Wohnfläche von Wohnung {letter} in m²? Zähle die Räume innerhalb ihrer Umrandung, ohne Balkone, Loggien und Terrassen.",
            "fr": f"Quelle est la surface habitable de l'appartement {letter} en m² ? Compte les pièces à l'intérieur de son contour, sans balcons, loggias ni terrasses.",
            "it": f"Qual è la superficie abitabile dell'appartamento {letter} in m²? Conta i locali dentro il suo contorno, esclusi balconi, logge e terrazze.",
        }[ctx.lang]
        how = "sum of indoor rooms inside the unit outline; DXF, PDF, source agree"
        if letter in ctx.apartment_ref:
            how += "; equals the public answer"
        out.append(Spec(family="apartment_area", skill="measure", question=en, local=local, key=measure(area), how=how))
        sq = measure(area * SQFT_PER_M2, unit="ft2")
        out.append(
            Spec(
                family="apartment_area_sqft",
                skill="measure",
                question=f"What is the living area of apartment {letter} in square feet? Leave out balconies, loggias and terraces.",
                local={
                    "de": f"Wie gross ist die Wohnfläche von Wohnung {letter} in Quadratfuss (sq ft)? Ohne Balkone, Loggien und Terrassen.",
                    "fr": f"Quelle est la surface habitable de l'appartement {letter} en pieds carrés (sq ft) ? Sans balcons, loggias ni terrasses.",
                    "it": f"Qual è la superficie abitabile dell'appartamento {letter} in piedi quadrati (sq ft)? Esclusi balconi, logge e terrazze.",
                }[ctx.lang],
                key=sq,
                how=f"{r2(area)} m2 x 10.7639",
            )
        )
    return out


def fam_rooms_over(f: SwissFloor, ctx: Context) -> list[Spec]:
    rooms = [r for r in f.rooms if indoor(r)]
    for n in (20, 15, 12, 10):
        if any(close(r.area_dxf, n, 0.03) for r in rooms):
            continue
        big = [r for r in rooms if r.area_dxf > n]
        if len(big) < 2 or len(big) == len(rooms) or not agree3(total := sum_paths(big)):
            continue
        en = f"What is the total area of all indoor rooms larger than {n} m² on this floor? Do not count balconies or loggias."
        local = {
            "de": f"Wie gross ist die Summe der Flächen aller Innenräume über {n} m² auf diesem Geschoss? Balkone und Loggien nicht mitzählen.",
            "fr": f"Quelle est la surface totale de toutes les pièces intérieures de plus de {n} m² à cet étage ? Sans balcons ni loggias.",
            "it": f"Qual è la superficie totale di tutti i locali interni più grandi di {n} m² in questo piano? Esclusi balconi e logge.",
        }[ctx.lang]
        return [Spec(family="rooms_over_n_area", skill="measure", question=en, local=local, key=measure(total[0]),
                     how=f"{len(big)} indoor rooms over {n} m2, no room within 3% of {n}")]  # fmt: skip
    return []


# ----------------------------------------------------------------------------- families: compound and derived


def fam_largest_room(f: SwissFloor, ctx: Context) -> list[Spec]:
    rooms = sorted((r for r in f.rooms if indoor(r)), key=lambda r: -r.area_dxf)
    if len(rooms) < 3:
        return []
    top, second = rooms[0], rooms[1]
    living = [r for r in rooms if r.subtype not in {"CORRIDOR", "STAIRCASE", "ELEVATOR"}]
    out = [
        Spec(
            family="largest_room_area",
            skill="compound",
            question="What is the floor area of the largest numbered indoor room on this floor, in m²? Corridors and stair halls count as rooms, balconies do not.",
            local={
                "de": "Wie gross ist der grösste nummerierte Innenraum auf diesem Geschoss, in m²? Korridore und Treppenhäuser zählen als Räume, Balkone nicht.",
                "fr": "Quelle est la surface de la plus grande pièce intérieure numérotée de cet étage, en m² ? Les couloirs et cages d'escalier comptent comme pièces, les balcons non.",
                "it": "Qual è la superficie del locale interno numerato più grande di questo piano, in m²? Corridoi e vani scala contano come locali, i balconi no.",
            }[ctx.lang],
            key=measure(top.area_dxf, alternates=(living[0].area_dxf,) if living else ()),
            how=f"room {top.num} ({top.label}) has the largest DXF polygon; alternate leaves out corridors and stairs",
        )
    ]
    if top.area_dxf >= 1.05 * second.area_dxf:
        accepted = [top.num, f"room {top.num}"]
        if top.label:
            accepted += [f"{top.num} {top.label}", f"{top.label} {top.num}", f"{top.label} ({top.num})"]
            if unique_label(f, top):
                accepted.append(top.label)
        out.append(
            Spec(
                family="largest_room_lookup",
                skill="lookup",
                question="Which numbered indoor room on this floor is the largest? Corridors and stair halls count as rooms. Give its room number.",
                local={
                    "de": "Welcher nummerierte Innenraum auf diesem Geschoss ist der grösste? Korridore und Treppenhäuser zählen als Räume. Gib die Raumnummer an.",
                    "fr": "Quelle pièce intérieure numérotée de cet étage est la plus grande ? Les couloirs et cages d'escalier comptent comme pièces. Donne son numéro.",
                    "it": "Quale locale interno numerato di questo piano è il più grande? Corridoi e vani scala contano come locali. Indica il numero del locale.",
                }[ctx.lang],
                key=LookupKey(accepted=tuple(accepted)),
                how=f"{top.num} {top.area_dxf:.2f} m2, next {second.num} {second.area_dxf:.2f} m2 (margin at least 5%)",
            )
        )
    return out


def fam_smallest_room(f: SwissFloor, ctx: Context) -> list[Spec]:
    rooms = sorted((r for r in f.rooms if indoor(r) and r.label), key=lambda r: r.area_dxf)
    if len(rooms) < 4 or rooms[1].area_dxf < 1.15 * rooms[0].area_dxf:
        return []
    low = rooms[0]
    assert low.label is not None
    accepted = [
        low.num,
        f"room {low.num}",
        f"{low.num} {low.label}",
        f"{low.label} {low.num}",
        f"{low.label} ({low.num})",
    ]
    if unique_label(f, low):
        accepted.append(low.label)
    return [
        Spec(
            family="smallest_room_lookup",
            skill="lookup",
            question="Among the indoor rooms that carry a name on this plan, which one is the smallest? Give its room number.",
            local={
                "de": "Welcher der beschrifteten Innenräume auf diesem Plan ist der kleinste? Gib die Raumnummer an.",
                "fr": "Parmi les pièces intérieures qui portent un nom sur ce plan, laquelle est la plus petite ? Donne son numéro.",
                "it": "Tra i locali interni con un nome su questa pianta, qual è il più piccolo? Indica il numero del locale.",
            }[ctx.lang],
            key=LookupKey(accepted=tuple(accepted)),
            how=f"{low.num} {low.label} {low.area_dxf:.2f} m2, next {rooms[1].area_dxf:.2f} m2 (margin at least 15%)",
        )
    ]


def fam_room_difference(f: SwissFloor, ctx: Context) -> list[Spec]:
    rooms = sorted((r for r in f.rooms if indoor(r) and r.label), key=lambda r: rank("diff", f.stem, r.num))
    for a in rooms:
        for b in rooms:
            diff = a.area_dxf - b.area_dxf
            if a.num == b.num or diff < 3.0:
                continue
            pdf = (a.area_pdf or 0.0) - (b.area_pdf or 0.0)
            src = (a.area_src or 0.0) - (b.area_src or 0.0)
            if not (close(diff, pdf, AGREE) and close(diff, src, AGREE)):
                continue
            la, lb = a.label or "", b.label or ""
            return [
                Spec(
                    family="room_difference",
                    skill="compound",
                    question=f"How many square metres larger is room {a.num} ({q('en', la)}) than room {b.num} ({q('en', lb)})?",
                    local={
                        "de": f"Um wie viele Quadratmeter ist Raum {a.num} ({q('de', la)}) grösser als Raum {b.num} ({q('de', lb)})?",
                        "fr": f"De combien de mètres carrés la pièce {a.num} ({q('fr', la)}) est-elle plus grande que la pièce {b.num} ({q('fr', lb)}) ?",
                        "it": f"Di quanti metri quadrati il locale {a.num} ({q('it', la)}) è più grande del locale {b.num} ({q('it', lb)})?",
                    }[ctx.lang],
                    key=measure(diff),
                    how=f"{a.area_dxf:.2f} - {b.area_dxf:.2f}; PDF and source differences agree within 1%",
                )
            ]
    return []


def fam_average_room(f: SwissFloor, ctx: Context) -> list[Spec]:
    for lab, family in ((BED[ctx.lang], "average_bedroom"), (ROOM[ctx.lang], "average_room_label")):
        rooms = labelled(f, lab)
        if len(rooms) < 2 or not agree3(total := sum_paths(rooms)):
            continue
        avg = total[0] / len(rooms)
        return [
            Spec(
                family="average_room_size",
                skill="compound",
                question=f"What is the average floor area of the rooms labelled {q('en', lab)} on this floor, in m²?",
                local={
                    "de": f"Wie gross ist die durchschnittliche Fläche der Räume mit der Bezeichnung {q('de', lab)} auf diesem Geschoss, in m²?",
                    "fr": f"Quelle est la surface moyenne des pièces désignées {q('fr', lab)} à cet étage, en m² ?",
                    "it": f"Qual è la superficie media dei locali denominati {q('it', lab)} in questo piano, in m²?",
                }[ctx.lang],
                key=measure(avg),
                how=f"{family}: {r2(total[0])} m2 / {len(rooms)} rooms",
            )
        ]
    return []


def fam_circulation_share(f: SwissFloor, ctx: Context) -> list[Spec]:
    labs = [CORRIDOR[ctx.lang], STAIR[ctx.lang]]
    present = [lab for lab in labs if labelled(f, lab)]
    indoor_rooms = [r for r in f.rooms if indoor(r)]
    circ = [r for r in indoor_rooms if r.label in present]
    if not circ or not agree3(whole := sum_paths(indoor_rooms)) or not agree3(part := sum_paths(circ)):
        return []
    share = 100.0 * part[0] / whole[0]
    typed = [r for r in indoor_rooms if r.subtype in {"CORRIDOR", "STAIRCASE"}]
    alt = 100.0 * sum(r.area_dxf for r in typed) / whole[0]
    names = " or ".join(q("en", lab) for lab in present)
    names_local = {"de": " oder ", "fr": " ou ", "it": " o "}[ctx.lang].join(q(ctx.lang, lab) for lab in present)
    en = (
        f"What share of the net indoor floor area is circulation (rooms labelled {names})? Take all numbered indoor "
        "rooms as the whole, and give the share in percent."
    )
    local = {
        "de": f"Welcher Anteil der Netto-Innenfläche ist Verkehrsfläche (Räume mit der Bezeichnung {names_local})? Nimm alle nummerierten Innenräume als Ganzes und gib den Anteil in Prozent an.",
        "fr": f"Quelle part de la surface nette intérieure est de la circulation (pièces désignées {names_local}) ? Prends toutes les pièces intérieures numérotées comme total et donne la part en pour cent.",
        "it": f"Quale quota della superficie netta interna è distribuzione (locali denominati {names_local})? Considera tutti i locali interni numerati come totale e indica la quota in percentuale.",
    }[ctx.lang]
    return [Spec(family="circulation_share", skill="compound", question=en, local=local,
                 key=measure(share, unit="%", alternates=(alt,)),
                 how=f"{r2(part[0])} / {r2(whole[0])} m2; alternate counts source types CORRIDOR and STAIRCASE")]  # fmt: skip


# ----------------------------------------------------------------------------- families: conditional counts


def fam_apartments_rooms(f: SwissFloor, ctx: Context) -> list[Spec]:
    if len(f.apartments) < 2:
        return []
    labs = (ROOM[ctx.lang], BED[ctx.lang])
    n_label, n_type = 0, 0
    for letter in f.apartments:
        rooms = [r for r in f.rooms if r.unit == letter]
        n_label += sum(r.label in labs for r in rooms) > 2
        n_type += sum(r.subtype in {"ROOM", "BEDROOM"} for r in rooms) > 2
    if n_label != n_type:
        return []
    en = f"How many apartments on this floor have more than 2 rooms labelled {q('en', labs[0])} or {q('en', labs[1])}?"
    local = {
        "de": f"Wie viele Wohnungen auf diesem Geschoss haben mehr als 2 Räume mit der Bezeichnung {q('de', labs[0])} oder {q('de', labs[1])}?",
        "fr": f"Combien d'appartements de cet étage ont plus de 2 pièces désignées {q('fr', labs[0])} ou {q('fr', labs[1])} ?",
        "it": f"Quanti appartamenti di questo piano hanno più di 2 locali denominati {q('it', labs[0])} o {q('it', labs[1])}?",
    }[ctx.lang]
    return [Spec(family="apartments_over_2_rooms", skill="count", question=en, local=local, key=CountKey(value=n_label),
                 how="per apartment tag, count labelled rooms; source types ROOM and BEDROOM give the same count")]  # fmt: skip


def fam_rooms_with_window(f: SwissFloor, ctx: Context) -> list[Spec]:
    rooms = [r for r in f.rooms if indoor(r)]
    if not openings_ok(rooms):
        return []
    n = sum(r.windows_dxf > 0 for r in rooms)
    en = "How many numbered indoor rooms on this floor have at least one window? Do not count balconies or loggias."
    local = {
        "de": "Wie viele nummerierte Innenräume auf diesem Geschoss haben mindestens ein Fenster? Balkone und Loggien nicht mitzählen.",
        "fr": "Combien de pièces intérieures numérotées de cet étage ont au moins une fenêtre ? Sans balcons ni loggias.",
        "it": "Quanti locali interni numerati di questo piano hanno almeno una finestra? Esclusi balconi e logge.",
    }[ctx.lang]
    return [Spec(family="rooms_with_window", skill="count", question=en, local=local, key=CountKey(value=n),
                 how="window rectangles within 6 cm of the room polygon; DXF and source agree on every room")]  # fmt: skip


def fam_doors_to_room(f: SwissFloor, ctx: Context) -> list[Spec]:
    rooms = sorted(
        (r for r in f.rooms if indoor(r) and r.label and r.doors_dxf >= 2 and openings_ok([r])),
        key=lambda r: rank("doors", f.stem, r.num),
    )
    if not rooms:
        return []
    r = rooms[0]
    lab = r.label or ""
    alts = (r.doors_dxf_raw,) if r.doors_dxf_raw != r.doors_dxf else ()
    return [
        Spec(
            family="doors_to_room",
            skill="count",
            question=f"How many doors open into room {r.num} ({q('en', lab)})? Count each door opening once.",
            local={
                "de": f"Wie viele Türen führen in Raum {r.num} ({q('de', lab)})? Zähle jede Türöffnung einmal.",
                "fr": f"Combien de portes donnent dans la pièce {r.num} ({q('fr', lab)}) ? Compte chaque ouverture de porte une fois.",
                "it": f"Quante porte danno sul locale {r.num} ({q('it', lab)})? Conta ogni apertura di porta una volta.",
            }[ctx.lang],
            key=CountKey(value=r.doors_dxf, alternates=alts),
            how="distinct door openings within 6 cm of the room polygon; alternate counts stacked copies",
        )
    ]


def fam_bath_no_window(f: SwissFloor, ctx: Context) -> list[Spec]:
    lab = BATH[ctx.lang]
    rooms = labelled(f, lab)
    if len(rooms) < 2 or not openings_ok(rooms):
        return []
    n = sum(r.windows_dxf == 0 for r in rooms)
    en = f"How many bathrooms (rooms labelled {q('en', lab)}) on this floor have no window?"
    local = {
        "de": f"Wie viele Bäder (Räume mit der Bezeichnung {q('de', lab)}) auf diesem Geschoss haben kein Fenster?",
        "fr": f"Combien de salles de bain (pièces désignées {q('fr', lab)}) de cet étage n'ont pas de fenêtre ?",
        "it": f"Quanti bagni (locali denominati {q('it', lab)}) di questo piano non hanno finestre?",
    }[ctx.lang]
    return [Spec(family="bathrooms_without_window", skill="count", question=en, local=local, key=CountKey(value=n),
                 how=f"{len(rooms)} rooms labelled {lab}, windows within 6 cm; DXF and source agree")]  # fmt: skip


def fam_largest_apartment(f: SwissFloor, ctx: Context) -> list[Spec]:
    areas = {x: a for x in f.apartments if (a := apartment_area(f, x, ctx)) is not None}
    if len(areas) < 2 or len(areas) != len(f.apartments):
        return []
    ordered = sorted(areas, key=lambda x: -areas[x])
    top, second = ordered[0], ordered[1]
    if areas[top] < 1.03 * areas[second]:
        return []
    tag = APT_TAG[ctx.lang]
    accepted = (top, f"apartment {top}", f"{tag} {top}", f"Wohnung {top}", f"appartement {top}", f"appartamento {top}")
    return [
        Spec(
            family="largest_apartment",
            skill="lookup",
            question="Which apartment on this floor has the largest living area (balconies and loggias excluded)? Give its letter.",
            local={
                "de": "Welche Wohnung auf diesem Geschoss hat die grösste Wohnfläche (ohne Balkone und Loggien)? Gib ihren Buchstaben an.",
                "fr": "Quel appartement de cet étage a la plus grande surface habitable (sans balcons ni loggias) ? Donne sa lettre.",
                "it": "Quale appartamento di questo piano ha la superficie abitabile più grande (esclusi balconi e logge)? Indica la sua lettera.",
            }[ctx.lang],
            key=LookupKey(accepted=accepted),
            how=f"{top} {areas[top]:.2f} m2, next {second} {areas[second]:.2f} m2 (margin at least 3%)",
        )
    ]


# ----------------------------------------------------------------------------- families: no answer on the sheet


def fam_missing_room(f: SwissFloor, ctx: Context) -> list[Spec]:
    nums = [r.num for r in f.rooms if re.fullmatch(r"\d+\.\d+", r.num)]
    if not nums:
        return []
    prefix = nums[0].split(".")[0]
    width = len(nums[0].split(".")[1])
    top = max(int(n.split(".")[1]) for n in nums if n.startswith(prefix + "."))
    ghost = f"{prefix}.{top + 7:0{width}d}"
    return [
        Spec(
            family="absent_room",
            skill="unanswerable",
            question=f"What is the net floor area of room {ghost} in m²?",
            local={
                "de": f"Wie gross ist die Nettofläche von Raum {ghost} in m²?",
                "fr": f"Quelle est la surface nette de la pièce {ghost} en m² ?",
                "it": f"Qual è la superficie netta del locale {ghost} in m²?",
            }[ctx.lang],
            key=UnanswerableKey(reasons=(MissingReason.NOT_ON_DOCUMENT,)),
            how=f"the highest room number on the sheet is {prefix}.{top:0{width}d}",
        )
    ]


def fam_absent_space(f: SwissFloor, ctx: Context) -> list[Spec]:
    labels = {r.label for r in f.rooms}
    options = [a for a in ABSENT if not labels & set(a[4])]
    if not options:
        return []
    en, de, fr, it, _ = options[rank("absent", f.stem) % len(options)]
    return [
        Spec(
            family="absent_space",
            skill="unanswerable",
            question=f"What is the floor area of {en} on this plan, in m²?",
            local={
                "de": f"Wie gross ist die Fläche {de} auf diesem Plan, in m²?",
                "fr": f"Quelle est la surface {fr} sur ce plan, en m² ?",
                "it": f"Qual è la superficie {it} in questa pianta, in m²?",
            }[ctx.lang],
            key=UnanswerableKey(reasons=(MissingReason.NOT_ON_DOCUMENT,)),
            how="no room on the sheet carries such a label",
        )
    ]


def fam_not_shown(f: SwissFloor, ctx: Context) -> list[Spec]:
    rooms = sorted((r for r in f.rooms if indoor(r) and r.label), key=lambda r: rank("shown", f.stem, r.num))
    if not rooms:
        return []
    r = rooms[0]
    lab = r.label or ""
    if rank("height", f.stem) % 2 == 0:
        return [
            Spec(
                family="ceiling_height",
                skill="unanswerable",
                question=f"What is the ceiling height of room {r.num} ({q('en', lab)}), in metres?",
                local={
                    "de": f"Wie hoch ist die Raumhöhe von Raum {r.num} ({q('de', lab)}), in Metern?",
                    "fr": f"Quelle est la hauteur sous plafond de la pièce {r.num} ({q('fr', lab)}), en mètres ?",
                    "it": f"Qual è l'altezza del soffitto del locale {r.num} ({q('it', lab)}), in metri?",
                }[ctx.lang],
                key=UnanswerableKey(reasons=(MissingReason.NOT_ON_DOCUMENT,)),
                how="a floor plan cut shows no heights; the sheet has no section and no height text",
            )
        ]
    return [
        Spec(
            family="wall_material",
            skill="unanswerable",
            question=f"What material are the walls of room {r.num} ({q('en', lab)}) made of?",
            local={
                "de": f"Aus welchem Material sind die Wände von Raum {r.num} ({q('de', lab)})?",
                "fr": f"En quel matériau sont les murs de la pièce {r.num} ({q('fr', lab)}) ?",
                "it": f"Di che materiale sono le pareti del locale {r.num} ({q('it', lab)})?",
            }[ctx.lang],
            key=UnanswerableKey(reasons=(MissingReason.NOT_ON_DOCUMENT,)),
            how="all walls use one hatch, the sheet has no material legend",
        )
    ]


def fam_ambiguous(f: SwissFloor, ctx: Context) -> list[Spec]:
    lab = KITCHEN[ctx.lang]
    rooms = labelled(f, lab)
    if len(rooms) < 2:
        return []
    areas = sorted(r.area_dxf for r in rooms)
    if areas[-1] < 1.15 * areas[0]:
        return []
    en_word = {"de": "die Küche", "fr": "la cuisine", "it": "la cucina"}[ctx.lang]
    return [
        Spec(
            family="ambiguous_room",
            skill="unanswerable",
            question=f"How big is the kitchen ({q('en', lab)}) on this plan, in m²?",
            local={
                "de": f"Wie gross ist {en_word} ({q('de', lab)}) auf diesem Plan, in m²?",
                "fr": f"Quelle est la taille de {en_word} ({q('fr', lab)}) sur ce plan, en m² ?",
                "it": f"Quanto è grande {en_word} ({q('it', lab)}) in questa pianta, in m²?",
            }[ctx.lang],
            key=UnanswerableKey(reasons=(MissingReason.AMBIGUOUS,)),
            how=f"{len(rooms)} rooms are labelled {lab}, with areas from {areas[0]:.2f} to {areas[-1]:.2f} m2",
        )
    ]


FAMILIES: tuple[Callable[[SwissFloor, Context], list[Spec]], ...] = (
    fam_bath_area,
    fam_bath_tiles,
    fam_bedroom_area,
    fam_apartment_area,
    fam_rooms_over,
    fam_largest_room,
    fam_smallest_room,
    fam_room_difference,
    fam_average_room,
    fam_circulation_share,
    fam_apartments_rooms,
    fam_rooms_with_window,
    fam_doors_to_room,
    fam_bath_no_window,
    fam_largest_apartment,
    fam_missing_room,
    fam_absent_space,
    fam_not_shown,
    fam_ambiguous,
)


def floor_specs(f: SwissFloor, ctx: Context) -> list[Spec]:
    """Every spec of one floor, or none when the floor fails the checks."""
    if ctx.lang not in BATH or not floor_ok(f, ctx):
        return []
    out: list[Spec] = []
    for family in FAMILIES:
        out.extend(family(f, ctx))
    return out


def public_context(rows: Iterable[tuple[str, str, float | None]]) -> dict[str, Context]:
    """Build each floor's context from public items: (stem, question text, numeric key or None)."""
    lang: dict[str, str] = {}
    apt: dict[str, dict[str, float]] = defaultdict(dict)
    room: dict[str, dict[str, float]] = defaultdict(dict)
    count: dict[str, dict[str, float]] = defaultdict(dict)
    area: dict[str, dict[str, float]] = defaultdict(dict)
    for stem, text, value in rows:
        if text.startswith("Wie "):
            lang[stem] = "de"
        elif text.startswith(("Combien", "Quelle")):
            lang[stem] = "fr"
        elif text.startswith(("Quant", "Qual")):
            lang[stem] = "it"
        if value is None:
            continue
        if m := re.search(r"net floor area of apartment ([A-Z]+) in", text):
            apt[stem][m.group(1)] = value
        elif m := re.search(r"net floor area of room (\S+) \(", text):
            room[stem][m.group(1)] = value
        elif m := re.search(r"rooms labelled '(.+)' are there", text):
            count[stem][m.group(1)] = value
        elif m := re.search(r"all rooms labelled '(.+)' on this floor", text):
            area[stem][m.group(1)] = value
    return {
        s: Context(
            lang=lang[s],
            apartment_ref=dict(apt.get(s, {})),
            room_ref=dict(room.get(s, {})),
            label_count_ref=dict(count.get(s, {})),
            label_area_ref=dict(area.get(s, {})),
        )
        for s in lang
    }
