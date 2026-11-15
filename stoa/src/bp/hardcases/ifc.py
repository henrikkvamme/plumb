"""Hard questions on IFC models and on their storey plan PDFs, with keys from IfcOpenShell.

Path 1 is the footprint of each IfcSpace (the union of its triangles seen from above), which is the convention
of the public ifc_models answers. Path 2 is the area of the faces that point up. A space is used only when the
two agree within 1% and, where the public set asks for the room, the public answer agrees too. A storey is used
only when all its spaces pass and no two spaces overlap (some models draw a room twice).
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from typing import TYPE_CHECKING

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as ue
import numpy as np
from pydantic import Field
from shapely.geometry import Polygon
from shapely.ops import unary_union

from bp.contract import CountKey, Frozen, Key, LookupKey, MeasureKey, MissingReason, UnanswerableKey
from bp.hardcases.common import SQFT_PER_M2, Draft, Skill, close, r2, rank
from bp.hardcases.select import Candidate
from bp.paths import DATA, DATASET

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

IFC_DIR = DATASET / "data" / "ifc_models"
CACHE = DATA / "external" / "hardcases_ifc_facts.json"
AGREE = 0.01

TARGETS = {
    "named_rooms_area": 20, "rooms_over_n_count": 20, "largest_room_lookup": 20, "storey_area_sqft": 15,
    "room_difference": 15, "absent_room": 12,
}  # fmt: skip


class Space(Frozen):
    guid: str
    name: str
    long_name: str
    area_fp: float
    area_up: float
    qto_net: float | None
    wkt: str  # footprint, to test overlaps

    @property
    def title(self) -> str:
        return f"{self.long_name} ({self.name})" if self.long_name and self.name else (self.long_name or self.name)


class Storey(Frozen):
    model: str  # file name of the IFC
    name: str
    spaces: tuple[Space, ...]


def storey_of(el: ifcopenshell.entity_instance) -> ifcopenshell.entity_instance | None:
    c = ue.get_container(el)
    if c is None:
        a = ue.get_aggregate(el)
        while a is not None and not a.is_a("IfcBuildingStorey"):
            c2 = ue.get_container(a)
            a = c2 if c2 is not None else ue.get_aggregate(a)
        return a
    while c is not None and not c.is_a("IfcBuildingStorey"):
        c = ue.get_aggregate(c)
    return c


def _geometry(model: ifcopenshell.file) -> dict[str, tuple[Polygon, float]]:
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    spaces = model.by_type("IfcSpace")
    out: dict[str, tuple[Polygon, float]] = {}
    if not spaces:
        return out
    it = ifcopenshell.geom.iterator(settings, model, 4, include=list(spaces))
    if not it.initialize():
        return out
    while True:
        shape = it.get()
        geometry = shape.geometry  # ty: ignore[missing-union-attribute] - a triangulation element has it
        verts = np.array(geometry.verts).reshape(-1, 3)
        faces = np.array(geometry.faces).reshape(-1, 3)
        if len(faces):
            tri = verts[faces]
            flat = [Polygon(t[:, :2]) for t in tri]
            fp = unary_union([p for p in flat if p.area > 1e-9])
            n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
            a = np.linalg.norm(n, axis=1) / 2
            nz = np.divide(n[:, 2], 2 * a, out=np.zeros_like(a), where=a > 0)
            out[shape.guid] = (fp, float(a[nz > 0.99].sum()))
        if not it.next():
            break
    return out


def _qto_net(space: ifcopenshell.entity_instance) -> float | None:
    for props in ue.get_psets(space, qtos_only=True).values():
        value = props.get("NetFloorArea")
        if isinstance(value, (int, float)):
            return float(value)
    return None


def model_storeys(file_name: str) -> list[Storey]:
    model = ifcopenshell.open(str(IFC_DIR / file_name))
    geo = _geometry(model)
    by_storey: dict[str, list[Space]] = defaultdict(list)
    for sp in model.by_type("IfcSpace"):
        st = storey_of(sp)
        if st is None or sp.GlobalId not in geo:
            continue
        fp, up = geo[sp.GlobalId]
        by_storey[str(st.Name)].append(
            Space(
                guid=sp.GlobalId,
                name=str(sp.Name or ""),
                long_name=str(sp.LongName or ""),
                area_fp=round(fp.area, 4),
                area_up=round(up, 4),
                qto_net=_qto_net(sp),
                wkt=fp.wkt,
            )
        )
    return [Storey(model=file_name, name=k, spaces=tuple(v)) for k, v in sorted(by_storey.items())]


def _safe(file_name: str) -> list[Storey]:
    try:
        return model_storeys(file_name)
    except Exception:  # a model that does not parse gives no items
        return []


def public_rows() -> list[tuple[str, str, float | None]]:
    from bp.suites import read_items  # noqa: PLC0415 - only the generator needs the public items

    out: list[tuple[str, str, float | None]] = []
    for item in read_items("stoa"):
        if item.source == "ifc_models":
            value = float(item.key.value) if isinstance(item.key, MeasureKey) else None
            out.append((item.doc, item.question, value))
    return out


def model_of(doc: str) -> str:
    name = doc.rsplit("/", 1)[1]
    return name if name.endswith(".ifc") else name.split("_plan-", 1)[0] + ".ifc"


def build_facts(jobs: int = 4) -> list[Storey]:
    models = sorted({model_of(d) for d, _, _ in public_rows() if (IFC_DIR / model_of(d)).is_file()})
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        storeys = [s for part in pool.map(_safe, models) for s in part]
    CACHE.write_text(json.dumps([s.model_dump() for s in storeys], ensure_ascii=False))
    return storeys


def load() -> list[Storey]:
    if not CACHE.exists():
        return build_facts()
    return [Storey.model_validate(s) for s in json.loads(CACHE.read_text())]


# ----------------------------------------------------------------------------- checks and context


class Context(Frozen):
    plans: tuple[str, ...]  # storey plan PDFs, relative to the dataset root
    room_ref: dict[str, float] = Field(default_factory=dict)  # public answer per room title


def contexts() -> dict[tuple[str, str], Context]:
    plans: dict[tuple[str, str], set[str]] = defaultdict(set)
    refs: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for doc, text, value in public_rows():
        storey = re.search(r"on '([^']+)'", text)
        if storey is None:
            continue
        key = (model_of(doc), storey.group(1))
        if doc.endswith(".pdf") and (DATASET / doc).is_file():
            plans[key].add(doc)
        room = re.search(r"of the room '(.+)' on '", text)
        if room and value is not None:
            refs[key][room.group(1)] = value
    keys = set(plans) | set(refs)
    return {k: Context(plans=tuple(sorted(plans.get(k, set()))), room_ref=dict(refs.get(k, {}))) for k in keys}


def storey_ok(st: Storey, ctx: Context) -> bool:
    if len(st.spaces) < 3:
        return False
    for sp in st.spaces:
        if not close(sp.area_fp, sp.area_up, AGREE) or sp.area_fp < 0.5:
            return False
        ref = ctx.room_ref.get(sp.title)
        if ref is not None and not close(ref, sp.area_fp, AGREE):
            return False
    from shapely import wkt  # noqa: PLC0415

    polys = [wkt.loads(sp.wkt) for sp in st.spaces]
    for i, p in enumerate(polys):
        for q in polys[i + 1 :]:
            if p.intersects(q) and p.intersection(q).area > 0.05 * min(p.area, q.area):
                return False
    titles = [sp.title for sp in st.spaces]
    return len(set(titles)) == len(titles)


class Spec(Frozen):
    family: str
    skill: Skill
    question: str
    key: Key
    how: str


def measure(value: float, unit: str = "m2", alternates: Iterable[float] = ()) -> MeasureKey:
    alts = tuple(sorted({r2(a) for a in alternates if not close(a, value, 0.02)}))
    return MeasureKey(value=r2(value), unit=unit, alternates=alts)


def qto_sum(spaces: Iterable[Space]) -> float | None:
    values = [sp.qto_net for sp in spaces]
    return None if any(v is None for v in values) else sum(v for v in values if v is not None)


# ----------------------------------------------------------------------------- families


def fam_named_area(st: Storey) -> list[Spec]:
    groups: dict[str, list[Space]] = defaultdict(list)
    for sp in st.spaces:
        if sp.long_name:
            groups[sp.long_name].append(sp)
    names = sorted((n for n, g in groups.items() if len(g) >= 2), key=lambda n: rank("named", st.model, st.name, n))
    if not names:
        return []
    rooms = groups[names[0]]
    total = sum(sp.area_fp for sp in rooms)
    qto = qto_sum(rooms)
    return [
        Spec(
            family="named_rooms_area",
            skill="measure",
            question=f"What is the total net floor area of all rooms named '{names[0]}' on '{st.name}', in m²?",
            key=measure(total, alternates=(qto,) if qto else ()),
            how=f"{len(rooms)} IfcSpace footprints; top-face areas agree within 1%; alternate is the Qto sum",
        )
    ]


def fam_rooms_over(st: Storey) -> list[Spec]:
    for n in (30, 20, 15, 10):
        if any(close(sp.area_fp, n, 0.03) for sp in st.spaces):
            continue
        count = sum(sp.area_fp > n for sp in st.spaces)
        if 0 < count < len(st.spaces):
            return [
                Spec(
                    family="rooms_over_n_count",
                    skill="count",
                    question=f"How many rooms on '{st.name}' have a net floor area larger than {n} m²?",
                    key=CountKey(value=count),
                    how=f"IfcSpace footprints, no room within 3% of {n} m2",
                )
            ]
    return []


def fam_largest(st: Storey) -> list[Spec]:
    rooms = sorted(st.spaces, key=lambda sp: -sp.area_fp)
    top, second = rooms[0], rooms[1]
    if top.area_fp < 1.05 * second.area_fp:
        return []
    accepted = {top.title, top.name}
    if top.long_name and sum(sp.long_name == top.long_name for sp in st.spaces) == 1:
        accepted.add(top.long_name)
    return [
        Spec(
            family="largest_room_lookup",
            skill="lookup",
            question=f"Which room on '{st.name}' has the largest net floor area? Give its name as written.",
            key=LookupKey(accepted=tuple(sorted(a for a in accepted if a))),
            how=f"{top.title} {top.area_fp:.2f} m2, next {second.area_fp:.2f} m2 (margin at least 5%)",
        )
    ]


def fam_storey_sqft(st: Storey) -> list[Spec]:
    total = sum(sp.area_fp for sp in st.spaces)
    qto = qto_sum(st.spaces)
    return [
        Spec(
            family="storey_area_sqft",
            skill="measure",
            question=f"What is the total net floor area of all rooms on '{st.name}', in square feet?",
            key=measure(total * SQFT_PER_M2, unit="ft2", alternates=(qto * SQFT_PER_M2,) if qto else ()),
            how=f"sum of {len(st.spaces)} IfcSpace footprints ({r2(total)} m2) x 10.7639; no two spaces overlap",
        )
    ]


def fam_difference(st: Storey) -> list[Spec]:
    rooms = sorted(st.spaces, key=lambda sp: rank("diff", st.model, st.name, sp.guid))
    for a in rooms:
        for b in rooms:
            diff = a.area_fp - b.area_fp
            if a.guid != b.guid and diff >= 3.0 and close(diff, a.area_up - b.area_up, AGREE):
                return [
                    Spec(
                        family="room_difference",
                        skill="compound",
                        question=f"On '{st.name}', how many square metres larger is room '{a.title}' than room '{b.title}'?",
                        key=measure(diff),
                        how=f"{a.area_fp:.2f} - {b.area_fp:.2f}; the top-face difference agrees within 1%",
                    )
                ]
    return []


def fam_absent(st: Storey) -> list[Spec]:
    names = " ".join(sp.title.lower() for sp in st.spaces)
    for word in ("Sauna", "Swimming pool", "Wine cellar"):
        if word.lower().split()[0] not in names:
            return [
                Spec(
                    family="absent_room",
                    skill="unanswerable",
                    question=f"What is the net floor area of the {word.lower()} on '{st.name}', in m²?",
                    key=UnanswerableKey(reasons=(MissingReason.NOT_ON_DOCUMENT, MissingReason.NOT_IN_MODEL)),
                    how=f"no IfcSpace on the storey has '{word}' in its name",
                )
            ]
    return []


FAMILIES: tuple[Callable[[Storey], list[Spec]], ...] = (
    fam_named_area, fam_rooms_over, fam_largest, fam_storey_sqft, fam_difference, fam_absent,
)  # fmt: skip


def candidates(seed: str) -> list[Candidate]:
    ctxs = contexts()
    out: list[Candidate] = []
    for st in load():
        ctx = ctxs.get((st.model, st.name))
        if ctx is None or not storey_ok(st, ctx):
            continue
        docs = (f"data/ifc_models/{st.model}", *ctx.plans)
        unit = f"{st.model}:{st.name}"
        for family in FAMILIES:
            for spec in family(st):
                draft = Draft(doc=docs[0], family=spec.family, skill=spec.skill, question=spec.question,
                              key=spec.key, how=spec.how)  # fmt: skip
                out.append(Candidate(unit=unit, docs=docs, draft=draft))
    return sorted(out, key=lambda c: rank(seed, c.unit, c.draft.family))


if __name__ == "__main__":
    result = build_facts()
    print(f"{len(result)} storeys from {len({s.model for s in result})} models -> {CACHE}")
