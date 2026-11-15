"""Hard questions on CubiCasa5K plans (PNG), with keys from the public CubiCasa5K SVG annotation.

The SVG has room polygons with a class (Space Bedroom, Space Kitchen ...), windows and doors as polygons that
span the wall. A plan has no scale, so areas have no answer in m², but area ratios do. Families: comparisons of
two rooms, conditional counts (bedrooms with a window, bathrooms without one, doors into a room), an ambiguous
comparison, and the area of a room on plans that print no size (no_scale, hand-checked list).

A key is kept only when it does not change between a tight and a loose contact tolerance (the second path).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from functools import cache
from typing import TYPE_CHECKING

from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry  # noqa: TC002 - pydantic needs it at runtime

from bp.contract import CountKey, Frozen, LookupKey, MissingReason, UnanswerableKey
from bp.hardcases.common import Draft, Skill, rank
from bp.hardcases.select import Candidate
from bp.paths import DATA, DATASET

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

SVG_ROOT = DATA / "external" / "cubicasa5k" / "svg"
PNG_DIR = DATASET / "data" / "cubicasa5k"
NS = "{http://www.w3.org/2000/svg}"
TOLERANCES = (3.0, 10.0)  # px: the key must be the same under both
BAD_DOORS = ("Door None", "Door RollUp", "Door ParallelSlide")

TARGETS = {
    "compare_rooms": 30, "ambiguous_room": 12, "bedrooms_with_window": 30, "bathrooms_without_window": 25,
    "doors_to_room": 25, "area_no_scale": 25, "absent_space": 12,
}  # fmt: skip

# CubiCasa plans are Finnish. A room kind: (English, Finnish, Finnish abbreviations on plans).
NAMES = {
    "kitchen": ("kitchen", "keittiö", ("K", "KEITTIÖ")),
    "living": ("living room", "olohuone", ("OH", "OLOHUONE")),
    "bedroom": ("bedroom", "makuuhuone", ("MH", "MAKUUHUONE")),
    "bath": ("bathroom", "kylpyhuone", ("KH", "PH", "KPH", "KYLPYHUONE", "PESUHUONE")),
    "sauna": ("sauna", "sauna", ("S", "SAUNA")),
}
GENITIVE_FI = {"kitchen": "keittiön", "living": "olohuoneen", "bedroom": "makuuhuoneen", "bath": "kylpyhuoneen",
               "sauna": "saunan"}  # fmt: skip
ILLATIVE_FI = {"kitchen": "keittiöön", "living": "olohuoneeseen", "bedroom": "makuuhuoneeseen",
               "bath": "kylpyhuoneeseen", "sauna": "saunaan"}  # fmt: skip

# Plans viewed by eye on 14 November 2026: no printed room size, no total area, no dimension line, no scale bar.
# 32 plans were viewed in a seeded order; high_quality-5879 prints room sizes and is left out.
NO_SCALE_CHECKED: frozenset[str] = frozenset(
    {
        "high_quality-10568",
        "high_quality-11365",
        "high_quality-11613",
        "high_quality-11751",
        "high_quality-11981",
        "high_quality-12112",
        "high_quality-12150",
        "high_quality-12511",
        "high_quality-12790",
        "high_quality-13117",
        "high_quality-13346",
        "high_quality-13355",
        "high_quality-1403",
        "high_quality-14127",
        "high_quality-14707",
        "high_quality-14714",
        "high_quality-20174",
        "high_quality-2526",
        "high_quality-3760",
        "high_quality-3814",
        "high_quality-4021",
        "high_quality-4708",
        "high_quality-5024",
        "high_quality-5712",
        "high_quality-5972",
        "high_quality-6624",
        "high_quality-6690",
        "high_quality-810",
        "high_quality-8562",
        "high_quality-9471",
        "high_quality-9941",
    }
)


class Room(Frozen):
    model_config = Frozen.model_config | {"arbitrary_types_allowed": True}
    cls: str
    label: str
    poly: BaseGeometry


class Plan(Frozen):
    model_config = Frozen.model_config | {"arbitrary_types_allowed": True}
    name: str  # group-id, as in the PNG name
    floors: int
    rooms: tuple[Room, ...]
    windows: tuple[BaseGeometry, ...]
    doors: tuple[BaseGeometry, ...]
    door_classes: tuple[str, ...]


def kind_of(room: Room) -> str | None:
    c = room.cls
    if c.startswith("Space Kitchen"):
        return "kitchen"
    if c == "Space LivingRoom":
        return "living"
    if c.startswith("Space Bedroom"):
        return "bedroom"
    if c.startswith("Space Bath") and room.label.strip().upper() != "WC":
        return "bath"
    if c == "Space Sauna":
        return "sauna"
    return None


def _polygon(g: ET.Element) -> BaseGeometry | None:
    for child in g:
        if child.tag == NS + "polygon":
            nums = [float(v) for v in child.get("points", "").replace(",", " ").split()]
            pts = list(zip(nums[0::2], nums[1::2], strict=False))
            if len(pts) >= 3:
                shape = Polygon(pts).buffer(0)
                return shape if shape.area > 0 else None
    return None


def _label(g: ET.Element) -> str:
    for sub in g.iter(NS + "g"):
        if "NameLabel" in sub.get("class", ""):
            text = sub.find(NS + "text")
            return (text.text or "").strip() if text is not None else ""
    return ""


def parse_svg(path: Path, name: str) -> Plan:
    root = ET.parse(path).getroot()  # noqa: S314 - a local file from the public CubiCasa5K archive
    rooms: list[Room] = []
    windows: list[BaseGeometry] = []
    doors: list[BaseGeometry] = []
    door_classes: list[str] = []
    floors = 0
    for g in root.iter(NS + "g"):
        cls = g.get("class", "")
        if cls.startswith("Floorplan"):
            floors += 1
        elif cls.startswith("Space ") and (poly := _polygon(g)) is not None:
            rooms.append(Room(cls=cls, label=_label(g), poly=poly))
        elif cls.startswith("Window") and (poly := _polygon(g)) is not None:
            windows.append(poly)
        elif cls.startswith("Door") and (poly := _polygon(g)) is not None:
            doors.append(poly)
            door_classes.append(cls)
    return Plan(name=name, floors=floors, rooms=tuple(rooms), windows=tuple(windows), doors=tuple(doors),
                door_classes=tuple(door_classes))  # fmt: skip


def touches(opening: BaseGeometry, room: BaseGeometry, tol: float) -> bool:
    if opening.distance(room) > tol:
        return False
    x0, y0, x1, y1 = opening.bounds
    long_side = max(x1 - x0, y1 - y0)
    return opening.buffer(tol).intersection(room).area >= 0.25 * tol * long_side


def robust_count(openings: Sequence[BaseGeometry], room: BaseGeometry) -> int | None:
    counts = {sum(touches(o, room, t) for o in openings) for t in TOLERANCES}
    return counts.pop() if len(counts) == 1 else None


@cache
def plans() -> tuple[Plan, ...]:
    out: list[Plan] = []
    for png in sorted(PNG_DIR.glob("*.png")):
        group, _, ident = png.stem.rpartition("-")
        svg = SVG_ROOT / group / ident / "model.svg"
        if svg.is_file():
            out.append(parse_svg(svg, png.stem))
    return tuple(out)


def usable(plan: Plan) -> bool:
    classes = {r.cls for r in plan.rooms}
    return plan.floors == 1 and "Space UserDefined" not in classes and "Space Room" not in classes


def of_kind(plan: Plan, kind: str) -> list[Room]:
    return [r for r in plan.rooms if kind_of(r) == kind]


def accepted(kind: str) -> tuple[str, ...]:
    en, fi, abbr = NAMES[kind]
    return (en, f"the {en}", fi, *abbr)


class Spec(Frozen):
    family: str
    skill: Skill
    question: str
    finnish: str
    key: CountKey | LookupKey | UnanswerableKey
    how: str


# ----------------------------------------------------------------------------- families


def fam_compare(plan: Plan) -> list[Spec]:
    unique = [k for k in NAMES if len(of_kind(plan, k)) == 1]
    pairs = [(a, b) for i, a in enumerate(unique) for b in unique[i + 1 :]]
    pairs.sort(key=lambda p: rank("cmp", plan.name, *p))
    for a, b in pairs:
        area_a, area_b = of_kind(plan, a)[0].poly.area, of_kind(plan, b)[0].poly.area
        ratio = max(area_a, area_b) / min(area_a, area_b)
        if ratio < 1.3:
            continue
        big = a if area_a > area_b else b
        return [
            Spec(
                family="compare_rooms",
                skill="lookup",
                question=f"Which room has the larger floor area on this plan: the {NAMES[a][0]} or the {NAMES[b][0]}?",
                finnish=f"Kumpi on pinta-alaltaan suurempi tässä pohjapiirustuksessa: {NAMES[a][1]} vai {NAMES[b][1]}?",
                key=LookupKey(accepted=accepted(big)),
                how=f"SVG polygon areas, ratio {ratio:.2f} (at least 1.3)",
            )
        ]
    return []


def fam_ambiguous(plan: Plan) -> list[Spec]:
    beds, kitchens = of_kind(plan, "bedroom"), of_kind(plan, "kitchen")
    if len(beds) < 2 or len(kitchens) != 1:
        return []
    k = kitchens[0].poly.area
    bigger = [b for b in beds if b.poly.area > 1.1 * k]
    smaller = [b for b in beds if b.poly.area < k / 1.1]
    if not bigger or not smaller:
        return []
    return [
        Spec(
            family="ambiguous_room",
            skill="unanswerable",
            question="Is the bedroom larger than the kitchen on this plan?",
            finnish="Onko makuuhuone suurempi kuin keittiö tässä pohjapiirustuksessa?",
            key=UnanswerableKey(reasons=(MissingReason.AMBIGUOUS,)),
            how=f"{len(beds)} bedrooms: {len(bigger)} larger and {len(smaller)} smaller than the kitchen by 10%",
        )
    ]


def fam_bedroom_window(plan: Plan) -> list[Spec]:
    beds = of_kind(plan, "bedroom")
    counts = [robust_count(plan.windows, b.poly) for b in beds]
    if not beds or any(c is None for c in counts):
        return []
    n = sum(1 for c in counts if c)
    return [
        Spec(
            family="bedrooms_with_window",
            skill="count",
            question="How many bedrooms on this plan have at least one window?",
            finnish="Kuinka monessa makuuhuoneessa on tässä pohjapiirustuksessa vähintään yksi ikkuna?",
            key=CountKey(value=n),
            how=f"{len(beds)} SVG bedrooms; windows that touch the room at 3 px and 10 px give the same result",
        )
    ]


def fam_bath_no_window(plan: Plan) -> list[Spec]:
    baths = of_kind(plan, "bath")
    counts = [robust_count(plan.windows, b.poly) for b in baths]
    if not baths or any(c is None for c in counts):
        return []
    n = sum(1 for c in counts if c == 0)
    return [
        Spec(
            family="bathrooms_without_window",
            skill="count",
            question="How many bathrooms on this plan have no window? Separate WC rooms do not count as bathrooms.",
            finnish="Kuinka monessa kylpyhuoneessa ei ole ikkunaa tässä pohjapiirustuksessa? Erillisiä WC-tiloja ei lasketa kylpyhuoneiksi.",
            key=CountKey(value=n),
            how=f"{len(baths)} SVG bathrooms (Space Bath, not labelled WC); robust under both tolerances",
        )
    ]


def fam_doors_into(plan: Plan) -> list[Spec]:
    if any(c.startswith(BAD_DOORS) for c in plan.door_classes):
        return []
    kinds = sorted((k for k in NAMES if len(of_kind(plan, k)) == 1), key=lambda k: rank("door", plan.name, k))
    for kind in kinds:
        n = robust_count(plan.doors, of_kind(plan, kind)[0].poly)
        if n is None or n == 0:
            continue
        return [
            Spec(
                family="doors_to_room",
                skill="count",
                question=f"How many doors lead into the {NAMES[kind][0]} on this plan? Count each door once, also a double door.",
                finnish=f"Kuinka monta ovea johtaa {ILLATIVE_FI[kind]} tässä pohjapiirustuksessa? Laske jokainen ovi kerran, myös pariovi.",
                key=CountKey(value=n),
                how="SVG doors (one element per door) that touch the room at 3 px and 10 px",
            )
        ]
    return []


def fam_no_scale(plan: Plan) -> list[Spec]:
    if plan.name not in NO_SCALE_CHECKED:
        return []
    kinds = sorted((k for k in NAMES if len(of_kind(plan, k)) == 1), key=lambda k: rank("ns", plan.name, k))
    if not kinds:
        return []
    kind = kinds[0]
    return [
        Spec(
            family="area_no_scale",
            skill="unanswerable",
            question=f"What is the floor area of the {NAMES[kind][0]} in m²?",
            finnish=f"Mikä on {GENITIVE_FI[kind]} pinta-ala neliömetreinä?",
            key=UnanswerableKey(reasons=(MissingReason.NO_SCALE,)),
            how="hand-checked: the image prints no room size, no total area, no dimension and no scale",
        )
    ]


def fam_absent(plan: Plan) -> list[Spec]:
    classes = {r.cls for r in plan.rooms}
    labels = {r.label.upper() for r in plan.rooms}
    if any(c.startswith(("Space Garage", "Space CarPort")) for c in classes) or labels & {"AT", "AUTOTALLI", "GARAGE"}:
        return []
    return [
        Spec(
            family="absent_space",
            skill="unanswerable",
            question="How many cars fit in the garage on this plan?",
            finnish="Kuinka monta autoa mahtuu tämän pohjapiirustuksen autotalliin?",
            key=UnanswerableKey(reasons=(MissingReason.NOT_ON_DOCUMENT,)),
            how="the SVG has no Space Garage or CarPort and no room label AT or AUTOTALLI",
        )
    ]


FAMILIES: tuple[Callable[[Plan], list[Spec]], ...] = (
    fam_compare, fam_ambiguous, fam_bedroom_window, fam_bath_no_window, fam_doors_into, fam_no_scale, fam_absent,
)  # fmt: skip


def plan_specs(plan: Plan) -> list[Spec]:
    if not usable(plan):
        return []
    out: list[Spec] = []
    for family in FAMILIES:
        out.extend(family(plan))
    return out


def candidates(seed: str) -> list[Candidate]:
    out: list[Candidate] = []
    for plan in plans():
        doc = f"data/cubicasa5k/{plan.name}.png"
        for spec in plan_specs(plan):
            twin = rank(seed, "twin", plan.name, spec.family) % 5 < 2
            draft = Draft(
                doc=doc, family=spec.family, skill=spec.skill,
                question=spec.question, key=spec.key, twins=(spec.finnish,) if twin else (), how=spec.how,
            )  # fmt: skip
            out.append(Candidate(unit=plan.name, docs=(doc,), draft=draft))
    return out
