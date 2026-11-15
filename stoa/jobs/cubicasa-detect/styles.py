"""Synthetic raster plans: the Swiss vector floors drawn in many styles, with exact labels.

    uv run python jobs/cubicasa-detect/styles.py scenes     # on the Mac: data/scenes.json.gz (DEV and VAL floors)
    uv run python jobs/cubicasa-detect/styles.py sheet      # on the Mac: data/contact.png, labels drawn on top
    uv run python jobs/cubicasa-detect/styles.py test       # on the Mac: stoa/data/styles-test (VAL floors, all families)
    uv run python jobs/cubicasa-detect/styles.py real       # on the Mac: data/real-labels.json for the Stoa PNGs
    python styles.py make --out /root/cache/syn --per 3     # on the VM: PNG files and labels.json (DEV floors)

Why: the detector that learned on CubiCasa finds half of the doors on a Swiss sheet. The drawing style is the
gap, and the hidden test can hold styles we have not seen. A floor in vector form gives exact labels in any style.

- A scene is the geometry of one floor in the pixel frame of its Stoa PNG: walls, rooms, doors (hinge, leaf, swing,
  gap in the wall), windows, fixtures with their kind. LOCK floors are never read (`sheet_labels` refuses).
- A style family sets how walls, doors, windows, fills and text look. `HELD_OUT` families are never used for
  training: they measure how the detector does on a style it has not seen.
- Every coordinate goes through one affine map (scale, rotation, shift), so the labels stay exact.
- The filters after the drawing (blur, noise, JPEG, threshold, shading) do not move anything.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import math
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
SCENES = DATA / "scenes.json.gz"
TEST = HERE.parents[1] / "data" / "styles-test"  # outside the job folder: `gpu run` syncs that to the VM
SS = 2  # supersampling of the drawing
VALID_FRACTION = 0.08  # of the floors, for model selection
TOUCH_M = 0.06  # an opening belongs to a room when it is within 6 cm of the room polygon (as bp.tools.dxf_plan)

FAMILIES = ("cad_solid", "cad_outline", "hatch", "colour", "grey_poche", "scan", "thin", "dark", "blueprint", "sketch")
HELD_OUT = ("blueprint", "sketch")

FIXTURE_CLASS = {"toilet": "toilet", "washbasin": "sink", "bathtub": "bathtub", "shower": "shower"}
ROOM_CLASS = {
    "KITCHEN": "kitchen", "BATHROOM": "bathroom", "BEDROOM": "bedroom",
    "BALCONY": "balcony", "LOGGIA": "balcony", "TERRACE": "balcony",
}  # fmt: skip
ROOM_KEYS = ("number", "subtype", "unit", "area_m2", "at", "polygon", "windows", "doors", "door_ids", "window_ids")
# What a drawing prints in a room, per language. The first entry is the long form.
WORDS: dict[str, dict[str, tuple[str, ...]]] = {
    "ROOM": {"en": ("Room",), "de": ("Zimmer",), "fr": ("Pièce",), "it": ("Stanza",), "fi": ("Huone", "H"),
             "sv": ("Rum",), "es": ("Habitación",), "nl": ("Kamer",), "et": ("Tuba",), "da": ("Værelse",)},
    "BEDROOM": {"en": ("Bedroom", "BR", "Bed"), "de": ("Schlafzimmer",), "fr": ("Chambre",), "it": ("Camera",),
                "fi": ("Makuuhuone", "MH"), "sv": ("Sovrum",), "es": ("Dormitorio",), "nl": ("Slaapkamer",),
                "et": ("Magamistuba",), "da": ("Soveværelse",)},
    "KITCHEN": {"en": ("Kitchen", "Kit."), "de": ("Küche",), "fr": ("Cuisine",), "it": ("Cucina",),
                "fi": ("Keittiö", "K"), "sv": ("Kök",), "es": ("Cocina",), "nl": ("Keuken",), "et": ("Köök",),
                "da": ("Køkken",)},
    "BATHROOM": {"en": ("Bathroom", "Bath", "WC"), "de": ("Bad", "Bad/WC"), "fr": ("Salle de bain", "Bain"),
                 "it": ("Bagno",), "fi": ("Kylpyhuone", "KH"), "sv": ("Badrum",), "es": ("Baño",),
                 "nl": ("Badkamer",), "et": ("Vannituba",), "da": ("Badeværelse",)},
    "CORRIDOR": {"en": ("Hall", "Corridor", "Entry"), "de": ("Korridor", "Flur"), "fr": ("Couloir",),
                 "it": ("Corridoio",), "fi": ("Eteinen", "ET"), "sv": ("Hall",), "es": ("Pasillo",),
                 "nl": ("Gang",), "et": ("Esik",), "da": ("Gang",)},
    "LIVING_DINING": {"en": ("Living/Dining",), "de": ("Wohnen/Essen",), "fr": ("Séjour/repas",),
                      "it": ("Soggiorno/pranzo",), "fi": ("Olohuone", "OH"), "sv": ("Vardagsrum",),
                      "es": ("Salón comedor",), "nl": ("Woonkamer",), "et": ("Elutuba",), "da": ("Stue",)},
    "LIVING_ROOM": {"en": ("Living room", "Living"), "de": ("Wohnen", "Wohnzimmer"), "fr": ("Séjour",),
                    "it": ("Soggiorno",), "fi": ("Olohuone", "OH"), "sv": ("Vardagsrum",), "es": ("Salón",),
                    "nl": ("Woonkamer",), "et": ("Elutuba",), "da": ("Stue",)},
    "DINING": {"en": ("Dining",), "de": ("Essen",), "fr": ("Repas",), "it": ("Pranzo",), "fi": ("Ruokailu", "RH"),
               "sv": ("Matrum",), "es": ("Comedor",), "nl": ("Eetkamer",), "et": ("Söögituba",), "da": ("Spisestue",)},
    "BALCONY": {"en": ("Balcony",), "de": ("Balkon",), "fr": ("Balcon",), "it": ("Balcone",),
                "fi": ("Parveke", "PARV"), "sv": ("Balkong",), "es": ("Balcón",), "nl": ("Balkon",),
                "et": ("Rõdu",), "da": ("Altan",)},
    "LOGGIA": {"en": ("Loggia",), "de": ("Loggia",), "fr": ("Loggia",), "it": ("Loggia",), "fi": ("Lasitettu parveke",),
               "sv": ("Loggia",), "es": ("Logia",), "nl": ("Loggia",), "et": ("Lodža",), "da": ("Loggia",)},
    "TERRACE": {"en": ("Terrace",), "de": ("Terrasse",), "fr": ("Terrasse",), "it": ("Terrazza",),
                "fi": ("Terassi",), "sv": ("Terrass",), "es": ("Terraza",), "nl": ("Terras",), "et": ("Terrass",),
                "da": ("Terrasse",)},
    "STOREROOM": {"en": ("Storage", "Closet"), "de": ("Reduit", "Abstellraum"), "fr": ("Réduit",),
                  "it": ("Ripostiglio",), "fi": ("Varasto", "VAR"), "sv": ("Förråd",), "es": ("Trastero",),
                  "nl": ("Berging",), "et": ("Panipaik",), "da": ("Depot",)},
    "STAIRCASE": {"en": ("Stairs",), "de": ("Treppenhaus",), "fr": ("Escalier",), "it": ("Scale",),
                  "fi": ("Porras",), "sv": ("Trappa",), "es": ("Escalera",), "nl": ("Trap",), "et": ("Trepp",),
                  "da": ("Trappe",)},
    "ELEVATOR": {"en": ("Lift", "Elevator"), "de": ("Lift",), "fr": ("Ascenseur",), "it": ("Ascensore",),
                 "fi": ("Hissi",), "sv": ("Hiss",), "es": ("Ascensor",), "nl": ("Lift",), "et": ("Lift",),
                 "da": ("Elevator",)},
}  # fmt: skip
PASTEL = {
    "ROOM": (250, 240, 215), "BEDROOM": (226, 236, 250), "KITCHEN": (252, 232, 214), "BATHROOM": (214, 240, 244),
    "CORRIDOR": (238, 238, 232), "LIVING_DINING": (252, 246, 205), "LIVING_ROOM": (252, 246, 205),
    "DINING": (250, 238, 200), "BALCONY": (222, 242, 220), "LOGGIA": (222, 242, 220), "TERRACE": (222, 242, 220),
    "STOREROOM": (236, 230, 240), "STAIRCASE": (232, 232, 232), "ELEVATOR": (226, 226, 226),
}  # fmt: skip


# ----------------------------------------------------------------------------- scenes (on the Mac)


def _r(points: object, nd: int = 1) -> list[list[float]]:
    return [[round(float(x), nd), round(float(y), nd)] for x, y in points]  # ty: ignore[not-iterable]


def _bbox(pts: list) -> list[float]:
    return [round(min(p[0] for p in pts), 1), round(min(p[1] for p in pts), 1),
            round(max(p[0] for p in pts), 1), round(max(p[1] for p in pts), 1)]  # fmt: skip


def scene(stem: str) -> dict | None:  # noqa: C901, PLR0912, PLR0915 - one pass over one floor
    """The geometry and the labels of one floor, in the pixel frame of its Stoa PNG."""
    import ezdxf  # noqa: PLC0415
    from shapely.geometry import Polygon  # noqa: PLC0415

    from bp.toolbench import raster as R  # noqa: N812, PLC0415
    from bp.tools import swiss_plan  # noqa: PLC0415
    from bp.tools.pdf_text import read_page  # noqa: PLC0415

    try:
        lab = R.sheet_labels(stem)
        plan = swiss_plan.read_plan(R.SWISS_DIR / f"{stem}.pdf")
    except Exception:  # noqa: BLE001 - a floor whose map cannot be fitted is left out
        return None
    a, b, c, d = lab.map

    def px(x: float, y: float) -> tuple[float, float]:
        return (a * x + b, c * y + d)

    doors: list[dict] = []
    windows: list[list[list[float]]] = []
    fixtures: list[dict] = []
    seen: set[str] = set()
    arcs: list[dict] = []
    pairs: list[tuple[list, list]] = []
    leaf: list | None = None
    for e in ezdxf.readfile(R.SWISS_DIR / f"{stem}.dxf").modelspace():
        layer, kind = e.dxf.layer, e.dxftype()
        if layer == "DOOR":
            if kind == "ARC":
                cx, cy, rad = float(e.dxf.center[0]), float(e.dxf.center[1]), float(e.dxf.radius)
                a0, a1 = float(e.dxf.start_angle), float(e.dxf.end_angle)
                if a1 < a0:
                    a1 += 360
                arc = [(cx + rad * math.cos(math.radians(t)), cy + rad * math.sin(math.radians(t)))
                       for t in np.linspace(a0, a1, 13)]  # fmt: skip
                arcs.append({"hinge": px(cx, cy), "arc": [px(*p) for p in arc]})
            elif kind == "LWPOLYLINE":
                pts = [px(float(p[0]), float(p[1])) for p in e.get_points()]
                if len(pts) == 2:  # the leaf; the gap in the wall is the next entity
                    leaf = pts
                elif len(pts) == 5 and leaf:
                    pairs.append((leaf, pts[:4]))
                    leaf = None
        elif layer == "WINDOW" and kind == "LWPOLYLINE" and e.closed and len(e) == 4:
            pts = _r([px(float(p[0]), float(p[1])) for p in e.get_points()])
            key = json.dumps(_r(pts, 0))
            if key not in seen:
                seen.add(key)
                windows.append(pts)
        elif layer == "FIXTURE":
            if kind == "CIRCLE":
                fixtures.append({"circle": [*px(float(e.dxf.center[0]), float(e.dxf.center[1])),
                                            float(e.dxf.radius) * abs(a)]})  # fmt: skip
            elif kind == "LWPOLYLINE":
                fixtures.append({"line": _r([px(float(p[0]), float(p[1])) for p in e.get_points()]),
                                 "closed": bool(e.closed)})  # fmt: skip
    for blade, gap in pairs:  # the swing of a leaf is the arc around its hinge that ends at its tip
        key = json.dumps(_r(gap, 0))
        if key in seen:  # the source draws a door once for each unit that lists it
            continue
        seen.add(key)

        def cost(g: dict, blade: list = blade) -> float:
            tip = min(math.dist(g["arc"][0], blade[1]), math.dist(g["arc"][-1], blade[1]))
            return math.dist(g["hinge"], blade[0]) + tip

        best = min(arcs, key=cost, default=None)
        swing = best["arc"] if best and math.dist(best["hinge"], blade[0]) < 0.1 * lab.ppm else [blade[1]]
        doors.append({"hinge": _r([blade[0]])[0], "arc": _r(swing), "leaf": _r(blade), "gap": _r(gap)})
    k = lab.width / read_page(R.SWISS_DIR / f"{stem}.pdf").width
    marks = []
    done: set[tuple[float, ...]] = set()
    for f in plan.fixtures:
        if f.kind not in FIXTURE_CLASS:
            continue
        box = tuple(round(v * k, 1) for v in f.bbox)
        if box not in done:
            done.add(box)
            marks.append([FIXTURE_CLASS[f.kind], *box])
    facts = {r["num"]: r for r in R._facts().get(stem, {}).get("rooms", [])}  # noqa: SLF001
    touch = TOUCH_M * lab.ppm
    gaps = [Polygon(dr["gap"]).buffer(0) for dr in doors]
    panes = [Polygon(w).buffer(0) for w in windows]
    rooms = []
    for room, shape in zip(lab.rooms, lab.room_shapes, strict=True):
        f = facts.get(room.number, {})
        poly = shape if shape.geom_type == "Polygon" else max(shape.geoms, key=lambda g: g.area)
        rooms.append({
            "number": room.number, "label": room.label, "subtype": f.get("subtype"), "unit": room.apartment,
            "outdoor": room.outdoor, "area_m2": room.area_m2, "at": [round(room.x, 1), round(room.y, 1)],
            "polygon": _r(poly.exterior.coords), "holes": [_r(h.coords) for h in poly.interiors],
            "windows": f.get("windows_dxf"), "doors": f.get("doors_dxf"),
            "door_ids": [i for i, g in enumerate(gaps) if g.distance(shape) <= touch],
            "window_ids": [i for i, g in enumerate(panes) if g.distance(shape) <= touch],
        })  # fmt: skip
    walls = []
    for w in lab.walls:
        for g in getattr(w, "geoms", [w]):
            if g.geom_type == "Polygon" and g.area > 1:
                walls.append({"outer": _r(g.exterior.coords), "holes": [_r(h.coords) for h in g.interiors]})
    return {
        "stem": stem, "partition": lab.partition, "width": lab.width, "height": lab.height,
        "ppm": round(lab.ppm, 3), "walls": walls, "rooms": rooms, "doors": doors, "windows": windows,
        "fixtures": fixtures, "marks": marks,
    }  # fmt: skip


def scenes(limit: int) -> None:
    from bp.toolbench import raster as R  # noqa: N812, PLC0415

    stems = [*R.stems("dev"), *R.stems("val")][: limit or None]
    with ProcessPoolExecutor(max_workers=8) as pool:
        rows = [s for s in pool.map(scene, stems, chunksize=4) if s]
    DATA.mkdir(exist_ok=True)
    with gzip.open(SCENES, "wt") as fh:
        json.dump(rows, fh)
    agree = sum(1 for s in rows for r in s["rooms"] if r["doors"] == len(r["door_ids"]))
    agree_w = sum(1 for s in rows for r in s["rooms"] if r["windows"] == len(r["window_ids"]))
    total = sum(len(s["rooms"]) for s in rows)
    print(json.dumps({"floors": len(rows), "of": len(stems), "rooms": total,
                      "doors_per_room_agree": round(agree / total, 4),
                      "windows_per_room_agree": round(agree_w / total, 4),
                      "bytes": SCENES.stat().st_size}))  # fmt: skip


def load_scenes(path: Path = SCENES) -> list[dict]:
    with gzip.open(path, "rt") as fh:
        return json.load(fh)


# ----------------------------------------------------------------------------- styles


@dataclass
class Style:
    family: str
    bg: tuple[int, int, int] = (255, 255, 255)
    ink: tuple[int, int, int] = (0, 0, 0)
    wall: str = "solid"  # solid | outline | hatch | tint
    wall_fill: tuple[int, int, int] = (0, 0, 0)
    line: float = 1.5  # px of a thin line
    wall_line: float = 2.0
    fills: str = "none"  # none | pastel | one
    fill_colour: tuple[int, int, int] = (245, 240, 225)
    door: str = "arc_leaf"  # arc_leaf | arc | leaf | sector | gap
    window: str = "lines"  # lines | box | thick | triple
    window_colour: tuple[int, int, int] | None = None
    fixtures: bool = True
    text: str = "all"  # all | label | number | none
    upper: bool = False
    lang: str = "de"
    font: str = ""
    font_scale: float = 1.0
    wobble: float = 0.0
    scale: float = 1.0
    angle: float = 0.0
    margin: float = 60.0
    frame: bool = False
    grid: bool = False
    dims: bool = False
    blur: float = 0.0
    noise: float = 0.0
    jpeg: int = 0
    threshold: bool = False
    shade: float = 0.0
    grey: bool = False
    specks: int = 0


def fonts() -> list[str]:
    roots = [Path("/System/Library/Fonts/Supplemental"), Path("/usr/share/fonts"), Path("/Library/Fonts")]
    skip = ("Symbol", "Wingding", "Webding", "Emoji", "Dingbat", "Braille", "Math", "Ornament", "Kufi", "Naskh",
            "CJK", "Color", "Awesome", "Icon", "Chancery", "Zapfino", "Brush", "Party", "Trattatello", "Herculanum",
            "Papyrus", "Chalkduster", "Bradley", "Luminari", "Skia")  # fmt: skip
    out = []
    for root in roots:
        if root.exists():
            out += [str(p) for p in sorted(root.rglob("*.ttf")) if not any(s.lower() in p.name.lower() for s in skip)]
    keep = []
    for path in out:
        try:
            font = ImageFont.truetype(path, 20)
            if font.getmask("Küche 12.5 m²").getbbox() and font.getlength("W") > font.getlength("i"):
                keep.append(path)
        except Exception:  # noqa: BLE001, S112 - a font PIL cannot read
            continue
    return keep


def pick_style(family: str, rng: random.Random, font_list: list[str]) -> Style:  # noqa: C901, PLR0912, PLR0915
    s = Style(family=family)
    s.scale = rng.uniform(0.5, 1.15)
    s.angle = rng.choice([0, 0, 0, 90, 180, 270]) + (rng.uniform(-3, 3) if rng.random() < 0.3 else 0.0)  # noqa: PLR2004
    s.margin = rng.uniform(20, 160)
    s.lang = rng.choice(list(WORDS["ROOM"]))
    s.font = rng.choice(font_list) if font_list else ""
    s.font_scale = rng.uniform(0.8, 1.5)
    s.upper = rng.random() < 0.35  # noqa: PLR2004
    s.text = rng.choices(["all", "label", "number", "none"], [5, 3, 1, 2])[0]
    s.door = rng.choices(["arc_leaf", "arc", "leaf", "sector", "gap"], [6, 2, 2, 2, 1])[0]
    s.window = rng.choice(["lines", "box", "thick", "triple"])
    s.fixtures = rng.random() < 0.85  # noqa: PLR2004
    s.line = rng.uniform(1.0, 2.2)
    s.wall_line = s.line * rng.uniform(1.0, 2.2)
    s.frame = rng.random() < 0.25  # noqa: PLR2004
    s.dims = rng.random() < 0.3  # noqa: PLR2004
    s.jpeg = rng.choice([0, 0, 0, 85, 60, 35])
    s.blur = rng.choice([0, 0, 0.4, 0.8])
    if family == "cad_solid":
        s.wall = "solid"
    elif family == "cad_outline":
        s.wall = "outline"
        s.wall_line = s.line * rng.uniform(1.5, 3.0)
    elif family == "hatch":
        s.wall = "hatch"
    elif family == "colour":
        s.wall = rng.choice(["solid", "tint"])
        s.wall_fill = rng.choice([(60, 60, 60), (40, 50, 70), (120, 120, 120), (90, 70, 60)])
        s.fills = "pastel"
        s.window_colour = rng.choice([(90, 150, 220), (120, 190, 230), None])
        s.ink = rng.choice([(0, 0, 0), (50, 50, 60), (70, 50, 40)])
    elif family == "grey_poche":
        s.wall = "tint"
        g = rng.randint(110, 200)
        s.wall_fill = (g, g, g)
        s.fills = rng.choice(["none", "one"])
        s.fill_colour = rng.choice([(248, 244, 232), (240, 240, 240), (252, 250, 240)])
    elif family == "scan":
        s.wall = rng.choice(["solid", "hatch", "outline"])
        s.grey = True
        s.threshold = rng.random() < 0.5  # noqa: PLR2004
        s.blur = rng.uniform(0.5, 1.4)
        s.noise = rng.uniform(4, 22)
        s.shade = rng.uniform(0.05, 0.25)
        s.specks = rng.randint(0, 400)
        s.angle += rng.uniform(-2, 2)
        s.jpeg = rng.choice([0, 70, 45, 30])
        s.bg = rng.choice([(255, 255, 255), (244, 240, 228), (232, 232, 226)])
    elif family == "thin":
        s.wall = "outline"
        s.line = rng.uniform(0.8, 1.2)
        s.wall_line = s.line
        s.fixtures = rng.random() < 0.5  # noqa: PLR2004
        s.ink = rng.choice([(0, 0, 0), (80, 80, 80), (40, 60, 120)])
    elif family == "dark":
        s.bg = rng.choice([(18, 18, 22), (30, 32, 40), (0, 0, 0)])
        s.ink = rng.choice([(235, 235, 235), (200, 220, 240), (255, 255, 255)])
        s.wall = rng.choice(["solid", "outline", "tint"])
        s.wall_fill = s.ink if s.wall == "solid" else (90, 95, 110)
    elif family == "blueprint":
        s.bg = rng.choice([(18, 60, 140), (10, 50, 110), (30, 80, 160)])
        s.ink = rng.choice([(255, 255, 255), (220, 235, 255)])
        s.wall = rng.choice(["outline", "hatch", "solid"])
        s.wall_fill = s.ink
        s.grid = rng.random() < 0.6  # noqa: PLR2004
        s.noise = rng.uniform(0, 8)
    elif family == "sketch":
        s.wobble = rng.uniform(0.8, 2.0)
        s.wall = rng.choice(["outline", "hatch", "tint"])
        g = rng.randint(30, 90)
        s.ink = (g, g, g + rng.randint(0, 20))
        s.wall_fill = (150, 150, 150)
        s.bg = rng.choice([(250, 247, 238), (255, 255, 255), (243, 238, 224)])
        s.noise = rng.uniform(2, 10)
        s.blur = rng.uniform(0.3, 0.8)
        s.shade = rng.uniform(0, 0.12)
    if s.wall == "solid" and family not in ("colour", "dark", "blueprint"):
        s.wall_fill = s.ink
    return s


# ----------------------------------------------------------------------------- drawing


class Canvas:
    def __init__(self, sc: dict, style: Style, rng: random.Random) -> None:
        self.style, self.rng = style, rng
        t = math.radians(style.angle)
        cos, sin = math.cos(t) * style.scale, math.sin(t) * style.scale
        self.m = (cos, -sin, sin, cos)
        pts = [p for w in sc["walls"] for p in w["outer"]] + [p for r in sc["rooms"] for p in r["polygon"]]
        moved = [(self.m[0] * x + self.m[1] * y, self.m[2] * x + self.m[3] * y) for x, y in pts]
        x0, y0 = min(p[0] for p in moved), min(p[1] for p in moved)
        x1, y1 = max(p[0] for p in moved), max(p[1] for p in moved)
        left, top = style.margin * rng.uniform(0.6, 1.6), style.margin * rng.uniform(0.6, 1.6)
        self.dx, self.dy = left - x0, top - y0
        self.width = int(x1 - x0 + left + style.margin * rng.uniform(0.6, 1.6))
        self.height = int(y1 - y0 + top + style.margin * rng.uniform(0.6, 2.4))
        self.image = Image.new("RGB", (self.width * SS, self.height * SS), style.bg)
        self.draw = ImageDraw.Draw(self.image)
        self.extent = (x0 + self.dx, y0 + self.dy, x1 + self.dx, y1 + self.dy)

    def t(self, p: list[float] | tuple[float, float]) -> tuple[float, float]:
        return (self.m[0] * p[0] + self.m[1] * p[1] + self.dx, self.m[2] * p[0] + self.m[3] * p[1] + self.dy)

    def ts(self, pts: list) -> list[tuple[float, float]]:
        return [self.t(p) for p in pts]

    def box(self, pts: list) -> list[float]:
        return _bbox(self.ts(pts))

    def _wob(self, pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
        w = self.style.wobble
        if not w:
            return pts
        out: list[tuple[float, float]] = []
        for (xa, ya), (xb, yb) in zip(pts, pts[1:], strict=False):
            n = max(1, int(math.hypot(xb - xa, yb - ya) / 14))
            ox, oy = self.rng.gauss(0, w * 0.6), self.rng.gauss(0, w * 0.6)
            for i in range(n):
                f = i / n
                bend = math.sin(f * math.pi) * w
                out.append((xa + (xb - xa) * f + ox * (1 - f) + self.rng.gauss(0, 0.25) * bend,
                            ya + (yb - ya) * f + oy * (1 - f) + self.rng.gauss(0, 0.25) * bend))  # fmt: skip
        out.append(pts[-1])
        return out

    def line(self, pts: list, width: float, colour: tuple[int, ...] | None = None, *, moved: bool = False) -> None:
        q = self._wob(pts if moved else self.ts(pts))
        self.draw.line([(x * SS, y * SS) for x, y in q], fill=colour or self.style.ink,
                       width=max(1, round(width * SS)), joint="curve")  # fmt: skip

    def fill(self, pts: list, colour: tuple[int, ...], *, moved: bool = False) -> None:
        q = pts if moved else self.ts(pts)
        self.draw.polygon([(x * SS, y * SS) for x, y in q], fill=colour)

    def mask(self, shapes: list[dict]) -> Image.Image:
        m = Image.new("L", self.image.size, 0)
        d = ImageDraw.Draw(m)
        for s in shapes:
            d.polygon([(x * SS, y * SS) for x, y in self.ts(s["outer"])], fill=255)
            for h in s["holes"]:
                d.polygon([(x * SS, y * SS) for x, y in self.ts(h)], fill=0)
        return m


def _hatch(size: tuple[int, int], style: Style, rng: random.Random) -> Image.Image:
    layer = Image.new("RGB", size, style.bg)
    d = ImageDraw.Draw(layer)
    step = rng.uniform(4, 9) * SS
    slope = rng.choice([1, -1])
    w, h = size
    x = -h
    while x < w + h:
        d.line([(x, 0), (x + slope * h, h)], fill=style.ink, width=max(1, round(style.line * SS * 0.7)))
        x += step
    return layer


def _font(style: Style, px: float) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(style.font, max(6, round(px)))
    except Exception:  # noqa: BLE001 - no font file on this machine
        return ImageFont.load_default(max(6, round(px)))


def _room_text(room: dict, style: Style, rng: random.Random) -> list[str]:
    words = WORDS.get(room["subtype"] or "", {}).get(style.lang)
    short = words and rng.random() < 0.4  # noqa: PLR2004
    label = (rng.choice(words) if short else (words[0] if words else room["label"])) or ""
    label = label.upper() if style.upper else label
    area = room["area_m2"]
    area_text = rng.choice([f"{area:.1f} m²", f"{area:.2f} m2", f"{area:.1f}".replace(".", ",") + " m²"])
    if style.text == "all":
        return [t for t in (room["number"], label, area_text) if t]
    if style.text == "label":
        return [t for t in (label, area_text if rng.random() < 0.5 else "") if t]  # noqa: PLR2004
    if style.text == "number":
        return [room["number"]]
    return []


def _mix(a: tuple[int, ...], b: tuple[int, ...], f: float) -> tuple[int, ...]:
    return tuple(int(x + (y - x) * f) for x, y in zip(a, b, strict=True))


def render(sc: dict, style: Style, seed: int) -> tuple[Image.Image, dict]:  # noqa: C901, PLR0912, PLR0915
    """One styled image of a scene and its labels (boxes and rooms in the pixels of that image)."""
    rng = random.Random(seed)  # noqa: S311 - drawing variety, not security
    cv = Canvas(sc, style, rng)
    s = style
    ppm = sc["ppm"] * s.scale
    if s.grid:
        step = rng.uniform(20, 60)
        faint = _mix(s.bg, s.ink, 0.25)
        for gx in np.arange(0, cv.width, step):
            cv.line([(gx, 0), (gx, cv.height)], 0.5, faint, moved=True)
        for gy in np.arange(0, cv.height, step):
            cv.line([(0, gy), (cv.width, gy)], 0.5, faint, moved=True)
    if s.fills != "none":
        for room in sc["rooms"]:
            colour = PASTEL.get(room["subtype"] or "", (245, 245, 240)) if s.fills == "pastel" else s.fill_colour
            cv.fill(room["polygon"], colour)
    # Walls.
    if s.wall in ("solid", "tint", "hatch"):
        mask = cv.mask(sc["walls"])
        layer = _hatch(cv.image.size, s, rng) if s.wall == "hatch" else Image.new("RGB", cv.image.size, s.wall_fill)
        cv.image.paste(layer, mask=mask)
        cv.draw = ImageDraw.Draw(cv.image)
    if s.wall != "solid":
        for w in sc["walls"]:
            for ring in [w["outer"], *w["holes"]]:
                cv.line(ring, s.wall_line)
    # Windows: a box in the wall with glass lines.
    for win in sc["windows"]:
        p = cv.ts(win)
        long_first = math.dist(p[0], p[1]) >= math.dist(p[1], p[2])
        q = p if long_first else [p[1], p[2], p[3], p[0]]
        colour = s.window_colour or s.ink
        if s.window != "thick":
            cv.fill(q, s.bg, moved=True)
            cv.line([*q, q[0]], s.line, colour, moved=True)
        mids = {"lines": (0.5,), "box": (), "triple": (0.33, 0.67), "thick": (0.5,)}[s.window]
        for f in mids:
            a = (q[0][0] + (q[3][0] - q[0][0]) * f, q[0][1] + (q[3][1] - q[0][1]) * f)
            b = (q[1][0] + (q[2][0] - q[1][0]) * f, q[1][1] + (q[2][1] - q[1][1]) * f)
            cv.line([a, b], s.line * (2.5 if s.window == "thick" else 1), colour, moved=True)
    # Doors: the gap in the wall, the leaf and the swing.
    for door in sc["doors"]:
        if s.wall != "outline" or s.door == "gap":
            cv.fill(door["gap"], s.bg)
        arc, leaf = cv.ts(door["arc"]), cv.ts(door["leaf"])
        if s.door == "sector":
            cv.fill([cv.t(door["hinge"]), *arc], _mix(s.bg, s.ink, 0.12), moved=True)
        if s.door in ("arc_leaf", "arc", "sector") and len(arc) > 1:
            cv.line(arc, s.line * (0.7 if s.door == "arc_leaf" else 1), moved=True)
        if s.door in ("arc_leaf", "leaf", "sector"):
            cv.line(leaf, s.line * rng.choice([1, 1.6, 2.2]), moved=True)
    # Fixtures as the source draws them.
    if s.fixtures:
        for f in sc["fixtures"]:
            if "circle" in f:
                x, y = cv.t(f["circle"][:2])
                r = f["circle"][2] * s.scale
                ring = [(x + r * math.cos(k * math.pi / 8), y + r * math.sin(k * math.pi / 8)) for k in range(17)]
                cv.line(ring, s.line * 0.8, moved=True)
            else:
                cv.line(f["line"] + ([f["line"][0]] if f["closed"] else []), s.line * 0.8)
    # Text, upright, at the room number position.
    if s.text != "none":
        size = 0.153 * ppm * 1.25 * s.font_scale
        font = _font(s, size * SS)
        for room in sc["rooms"]:
            x, y = cv.t(room["at"])
            lines = _room_text(room, s, rng)
            y -= len(lines) * size * 0.6
            for text in lines:
                cv.draw.text((x * SS, y * SS), text, fill=s.ink, font=font, anchor="mm")
                y += size * 1.2
    if s.dims:
        x0, y0, x1, y1 = cv.extent
        off = min(s.margin * 0.4, 30)
        for a, b in (((x0, y0 - off), (x1, y0 - off)), ((x0 - off, y0), (x0 - off, y1))):
            if min(a[0], a[1], b[0], b[1]) > 4:  # noqa: PLR2004
                cv.line([a, b], s.line * 0.7, moved=True)
                mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 7)
                cv.draw.text((mid[0] * SS, mid[1] * SS), f"{math.dist(a, b) / ppm:.2f}", fill=s.ink,
                             font=_font(s, 11 * SS), anchor="mm")  # fmt: skip
    if s.frame:
        cv.draw.rectangle([4 * SS, 4 * SS, (cv.width - 5) * SS, (cv.height - 5) * SS], outline=s.ink,
                          width=round(s.line * SS))  # fmt: skip
    image = finish(cv.image.resize((cv.width, cv.height), Image.Resampling.LANCZOS), s, rng)
    # Labels.
    door_boxes = [cv.box([d["hinge"], *d["arc"], *d["gap"]]) for d in sc["doors"]]
    window_boxes = [cv.box(w) for w in sc["windows"]]
    boxes: list[list] = []
    if s.door != "gap":
        boxes += [["door", *b] for b in door_boxes]
    else:  # a gap with no leaf is a doorway, as in CubiCasa
        boxes += [["doorway", *cv.box(d["gap"])] for d in sc["doors"]]
    boxes += [["window", *b] for b in window_boxes]
    if s.fixtures:
        for label, bx0, by0, bx1, by1 in sc["marks"]:
            boxes.append([label, *cv.box([(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)])])
    boxes.append(["floorplan", *(round(v, 1) for v in cv.extent)])
    boxes += [[ROOM_CLASS[r["subtype"]], *cv.box(r["polygon"])] for r in sc["rooms"] if r["subtype"] in ROOM_CLASS]
    rooms = [{**{k: r[k] for k in ROOM_KEYS}, "at": [round(v, 1) for v in cv.t(r["at"])],
              "polygon": _r(cv.ts(r["polygon"]))} for r in sc["rooms"]]  # fmt: skip
    labels = {
        "stem": sc["stem"], "family": s.family, "seed": seed, "width": cv.width, "height": cv.height,
        "ppm": round(ppm, 3), "angle": round(s.angle, 2), "door_style": s.door, "text": s.text, "lang": s.lang,
        "boxes": boxes, "rooms": rooms, "door_boxes": door_boxes, "window_boxes": window_boxes,
    }  # fmt: skip
    return image, labels


def finish(image: Image.Image, s: Style, rng: random.Random) -> Image.Image:
    """Filters that change the look and move nothing."""
    if s.grey:
        image = image.convert("L").convert("RGB")
    if s.blur:
        image = image.filter(ImageFilter.GaussianBlur(s.blur))
    arr = np.asarray(image).astype(np.float32)
    nrng = np.random.default_rng(rng.getrandbits(32))
    if s.shade:
        h, w = arr.shape[:2]
        gx, gy = rng.uniform(-1, 1), rng.uniform(-1, 1)
        ramp = (np.linspace(-1, 1, w)[None, :] * gx + np.linspace(-1, 1, h)[:, None] * gy) * s.shade * 255 / 2
        arr -= np.abs(ramp)[..., None]
    if s.noise:
        arr += nrng.normal(0, s.noise, arr.shape[:2])[..., None]
    if s.specks:
        ys = nrng.integers(0, arr.shape[0], s.specks)
        xs = nrng.integers(0, arr.shape[1], s.specks)
        arr[ys, xs] = nrng.choice([0, 255], s.specks)[:, None]
    if s.threshold:
        level = float(np.percentile(arr, 50)) - rng.uniform(40, 90)
        arr = np.where(arr.mean(axis=2, keepdims=True) < level, 0, 255).repeat(3, axis=2)
    image = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    if s.jpeg:
        buf = io.BytesIO()
        image.save(buf, "JPEG", quality=s.jpeg)
        image = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    return image


# ----------------------------------------------------------------------------- outputs


def seed_of(stem: str, family: str, index: int) -> int:
    return int.from_bytes(hashlib.sha256(f"{stem}:{family}:{index}".encode()).digest()[:4], "big")


def _split(stem: str) -> str:
    digest = hashlib.sha256(f"styles:{stem}".encode()).digest()
    return "valid" if digest[0] / 256 < VALID_FRACTION else "train"


def one(job: tuple[dict, str, int, str, list[str]]) -> dict:
    sc, family, index, out, font_list = job
    seed = seed_of(sc["stem"], family, index)
    style = pick_style(family, random.Random(seed), font_list)  # noqa: S311
    image, labels = render(sc, style, seed)
    name = f"syn-{sc['stem']}-{family}-{index}"
    image.save(Path(out) / f"{name}.png", compress_level=3)
    return {**labels, "name": name, "partition": sc["partition"], "split": _split(sc["stem"])}


def _run(jobs: list, out: Path, workers: int, font_count: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        labels = list(pool.map(one, jobs, chunksize=4))
    (out / "labels.json").write_text(json.dumps({r["name"]: r for r in labels}))
    print(json.dumps({"images": len(labels), "families": sorted({r["family"] for r in labels}),
                      "fonts": font_count}), flush=True)  # fmt: skip


def make(out: Path, per: int, limit: int, workers: int) -> None:
    """The training images: `per` images of each DEV floor, in the training families only."""
    rows = [sc for sc in load_scenes() if sc["partition"] == "dev"][: limit or None]
    font_list = fonts()
    train = [f for f in FAMILIES if f not in HELD_OUT]
    jobs = []
    for sc in rows:
        rng = random.Random(seed_of(sc["stem"], "pick", 0))  # noqa: S311
        jobs += [(sc, rng.choice(train), i, str(out), font_list) for i in range(per)]
    _run(jobs, out, workers, len(font_list))


def test(out: Path, limit: int, workers: int) -> None:
    """The test images: each VAL floor once in a training family (a new floor in a known style) and once in each
    held-out family (a new floor in a style the detector never saw)."""
    rows = [sc for sc in load_scenes() if sc["partition"] == "val"][: limit or None]
    font_list = fonts()
    train = [f for f in FAMILIES if f not in HELD_OUT]
    jobs = []
    for sc in rows:
        rng = random.Random(seed_of(sc["stem"], "test", 0))  # noqa: S311
        jobs += [(sc, f, 100, str(out), font_list) for f in (rng.choice(train), *HELD_OUT)]
    _run(jobs, out, workers, len(font_list))


def real() -> None:
    """Labels for the Stoa PNG of each DEV and VAL floor (the scene is in the pixel frame of that PNG)."""
    out = {}
    for sc in load_scenes():
        door_boxes = [_bbox([d["hinge"], *d["arc"], *d["gap"]]) for d in sc["doors"]]
        window_boxes = [_bbox(w) for w in sc["windows"]]
        boxes = [["door", *b] for b in door_boxes] + [["window", *b] for b in window_boxes]
        boxes += [list(m) for m in sc["marks"]]
        pts = [p for w in sc["walls"] for p in w["outer"]] + [p for r in sc["rooms"] for p in r["polygon"]]
        boxes.append(["floorplan", *_bbox(pts)])
        boxes += [[ROOM_CLASS[r["subtype"]], *_bbox(r["polygon"])] for r in sc["rooms"] if r["subtype"] in ROOM_CLASS]
        out[sc["stem"]] = {
            "stem": sc["stem"], "family": "stoa", "partition": sc["partition"], "split": _split(sc["stem"]),
            "width": sc["width"], "height": sc["height"], "ppm": sc["ppm"], "boxes": boxes,
            "rooms": [{k: r[k] for k in ROOM_KEYS} for r in sc["rooms"]],
            "door_boxes": door_boxes, "window_boxes": window_boxes,
        }  # fmt: skip
    (DATA / "real-labels.json").write_text(json.dumps(out))
    print(json.dumps({"floors": len(out), "dev": sum(1 for v in out.values() if v["partition"] == "dev")}))


COLOURS = {"door": (230, 30, 30), "doorway": (230, 120, 30), "window": (30, 90, 230), "toilet": (20, 160, 60),
           "sink": (150, 30, 200), "shower": (0, 170, 170), "bathtub": (200, 150, 0)}  # fmt: skip


def sheet(n: int, cell: int = 900) -> None:
    """A contact sheet for a check by eye: one floor per family, the small-object boxes drawn on top."""
    rows = load_scenes()
    font_list = fonts()
    rng = random.Random(7)  # noqa: S311
    tiles = []
    for i in range(n):
        sc = rng.choice(rows[:40])
        family = FAMILIES[i % len(FAMILIES)]
        seed = seed_of(sc["stem"], family, i)
        image, labels = render(sc, pick_style(family, random.Random(seed), font_list), seed)  # noqa: S311
        d = ImageDraw.Draw(image)
        for label, *b in labels["boxes"]:
            if label in COLOURS:
                d.rectangle(b, outline=COLOURS[label], width=2)
        image.thumbnail((cell, cell))
        tile = Image.new("RGB", (cell, cell + 24), (255, 255, 255))
        tile.paste(image, (0, 24))
        ImageDraw.Draw(tile).text((4, 4), f"{family} door={labels['door_style']} text={labels['text']}", fill=(0, 0, 0))
        tiles.append(tile)
    cols = 4
    grid = Image.new("RGB", (cols * cell, math.ceil(n / cols) * (cell + 24)), (255, 255, 255))
    for i, tile in enumerate(tiles):
        grid.paste(tile, ((i % cols) * cell, (i // cols) * (cell + 24)))
    grid.save(DATA / "contact.png")
    print(DATA / "contact.png", len(font_list), "fonts")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["scenes", "sheet", "make", "test", "real"])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--n", type=int, default=12)
    parser.add_argument("--out", default="")
    parser.add_argument("--per", type=int, default=3)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.step == "scenes":
        scenes(args.limit)
    elif args.step == "sheet":
        sheet(args.n)
    elif args.step == "make":
        make(Path(args.out or DATA / "syn"), args.per, args.limit, args.workers)
    elif args.step == "test":
        test(Path(args.out or TEST), args.limit, args.workers)
    else:
        real()


if __name__ == "__main__":
    sys.exit(main())
