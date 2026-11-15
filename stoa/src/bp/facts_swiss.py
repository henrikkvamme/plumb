"""The facts of a Swiss vector plan (one-page PDF): rooms, apartments, doors, fixtures and the scale.

The same reading as `stoa-desk/py/desk/facts.py`, in `bp` types, with a confidence, a basis and a margin on each
fact. Every rate is from the Swiss tool benchmark on 833 test floors (`experiments/tools/swiss.json`), see
`bp.rates`. Coordinates are PDF points of page 0.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bp import conflicts, rates
from bp.facts import DocumentFacts, Entity, Fact, Page, rated
from bp.tools import pdf_text, swiss_plan

if TYPE_CHECKING:
    from pathlib import Path

UNKNOWN = ("Room heights", "Wall materials and finishes", "Volumes", "Anything on other storeys")


def _box(bbox: tuple[float, float, float, float]) -> tuple[tuple[float, float], ...]:
    return ((bbox[0], bbox[1]), (bbox[2], bbox[3]))


def _bounds(points: tuple[tuple[float, float], ...]) -> tuple[float, float, float, float]:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _warned(rate: rates.Rate, warnings: tuple[str, ...] | list[str]) -> rates.Rate:
    # A warning of the Swiss reader marks a room that the benchmark did not see as clean; the factor is a rule.
    return (
        rate.lowered(0.8, "lowered by a rule, because the reader warns: " + "; ".join(warnings)) if warnings else rate
    )


def _scale(plan: swiss_plan.SwissPlan) -> tuple[list[Entity], list[Fact]]:
    scale = plan.scale
    if scale is None:
        return [], [rated("scale", None, rates.NOT_GIVEN, note="no scale found")]
    text = f"1:{scale.ratio}"
    rate = (
        rates.SWISS_SCALE
        if scale.agrees
        else rates.unmeasured("a Swiss plan whose scale bar does not confirm the text")
    )
    status = "known" if scale.agrees else "estimated"
    source = "title block" + (", confirmed by the scale bar" if scale.agrees else "")
    facts = (
        rated("scale", text, rate, status=status, source=source),
        rated("metres_per_point", round(scale.metres_per_point, 5), rate, status=status, source="scale ratio and paper size"),
    )  # fmt: skip
    at = scale.evidence.points[0]
    entity = Entity(id="scale", kind="scale", label=f"Scale {text}", geometry="point", points=((at[0], at[1]),),
                    facts=facts)  # fmt: skip
    return [entity], [facts[0]]


def _room(plan: swiss_plan.SwissPlan, r: swiss_plan.Room, area_source: str) -> Entity:
    warnings = swiss_plan.room_area(plan, r.number).warnings
    area_rate = _warned(rates.SWISS_AREA, warnings)
    margin = rates.swiss_area_margin(r.area_m2) if r.area_m2 is not None else None
    if warnings and margin is not None:
        # a warned room is outside what the benchmark measured as clean: its margin is unknown
        margin = None
    facts = [
        rated("name", r.label, rates.SWISS_ROOMS, source="text above the room number"),
        rated("number", r.number, rates.SWISS_ROOMS, source="text on the sheet"),
        rated("area", r.area_m2, area_rate, margin, unit="m2", status="estimated" if warnings else "known",
              source=area_source, note="; ".join(warnings)),
    ]  # fmt: skip
    if r.printed_area_m2 is not None:
        facts.append(rated("printed_area", r.printed_area_m2, rates.SWISS_PRINTED, unit="m2", source="text below the room number"))  # fmt: skip
    facts.append(rated("apartment", r.apartment, rates.SWISS_ROOMS, source="red unit outline that holds the room"))
    facts.append(rated("outdoor", "yes" if r.outdoor else "no", rates.SWISS_ROOMS, source="fill colour and label"))
    name = f"{r.label} {r.number}" if r.label else r.number
    if len(r.polygon) >= 3:
        geometry, points = "polygon", tuple((x, y) for x, y in r.polygon)
    else:
        geometry, points = "point", ((r.at[0], r.at[1]),)
    return Entity(id=f"room:{r.number}", kind="room", label=name, geometry=geometry, points=points, facts=tuple(facts))


def _apartment(plan: swiss_plan.SwissPlan, a: swiss_plan.Apartment, rooms: dict[str, Entity]) -> Entity:
    members = [r for r in plan.rooms if r.apartment == a.letter]
    counted = [r for r in members if not r.outdoor and r.fill != swiss_plan.SHARED_FILL]
    area = swiss_plan.apartment_area(plan, a.letter)
    parts = [m for r in counted if (m := _area_margin(rooms.get(f"room:{r.number}"))) is not None]
    margin = rates.sum_margin(parts) if parts and len(parts) == len(counted) and not area.warnings else None
    facts = (
        rated("living_area", area.value, _warned(rates.SWISS_AREA, area.warnings), margin, unit="m2",
              status="estimated" if area.warnings else "known", source="sum of its indoor rooms",
              note="; ".join(area.warnings)),
        rated("rooms", len(members), rates.SWISS_ROOMS, source="rooms inside the unit outline"),
    )  # fmt: skip
    return Entity(id=f"apartment:{a.letter}", kind="apartment", label=f"Apartment {a.letter}", geometry="point",
                  points=((a.at[0], a.at[1]),), facts=facts, members=tuple(f"room:{r.number}" for r in members))  # fmt: skip


def _area_margin(entity: Entity | None) -> rates.Margin | None:
    if entity is None:
        return None
    fact = next((f for f in entity.facts if f.key == "area"), None)
    if fact is None or fact.margin is None or fact.margin_share is None:
        return None
    return rates.Margin(value=fact.margin, share=fact.margin_share, basis=fact.margin_basis)


def swiss_facts(path: str | Path) -> DocumentFacts | None:
    """The facts of a Swiss plan PDF, or None when the file is not a one-page plan of this kind."""
    if pdf_text.page_count(str(path)) != 1:
        return None
    page = pdf_text.read_page(str(path))
    if not swiss_plan.detect(page).is_plan:
        return None
    plan = swiss_plan.compile_plan(page)
    scale = plan.scale
    area_source = f"room polygon at the sheet scale 1:{scale.ratio}" if scale else "no scale"
    entities, summary = _scale(plan)
    rooms = {f"room:{r.number}": _room(plan, r, area_source) for r in plan.rooms}
    from bp import facts_quantities  # noqa: PLC0415 - perimeter, baseboard and wall length; loads the tool module

    room_extra, wall_facts, wall_entities = facts_quantities.swiss(page, plan)
    rooms, summary = facts_quantities.with_room_facts(rooms, room_extra), [*summary, *wall_facts]
    entities.extend(wall_entities)
    entities.extend(rooms.values())
    entities.extend(_apartment(plan, a, rooms) for a in plan.apartments)

    seen: set[tuple[float, ...]] = set()
    for e in plan.doors.evidence:
        key = tuple(round(v, 1) for p in e.points for v in p)
        if key in seen or not e.points:
            continue
        seen.add(key)
        n = len(seen)
        kind = rated("kind", "door opening", rates.SWISS_DOORS, source="dark grey door symbol in the vector drawing")
        entities.append(Entity(id=f"door:{n}", kind="door", label=f"Door {n}", geometry="box",
                               points=_box(_bounds(tuple(e.points))), facts=(kind,)))  # fmt: skip

    counts: dict[swiss_plan.FixtureKind, int] = {}
    for f in plan.fixtures:
        if f.kind == "other":
            continue
        counts[f.kind] = counts.get(f.kind, 0) + 1
        rate = rates.swiss_fixture(f.kind)
        size = rated("size", f"{f.edge_long_m:.2f} x {f.edge_short_m:.2f}", rates.SWISS_SIZE if scale else rates.NOT_GIVEN,
                     unit="m", source="box edges at the sheet scale")  # fmt: skip
        entities.append(Entity(
            id=f"{f.kind}:{counts[f.kind]}", kind="window" if f.kind == "window" else "fixture", group=f.kind,
            label=f"{f.kind.capitalize()} {counts[f.kind]}", geometry="box", points=_box(f.bbox),
            facts=(rated("kind", f.kind, rate, source="symbol drawn inside the box"), size),
        ))  # fmt: skip

    measured = sum(1 for r in plan.rooms if r.area_m2 is not None)
    summary += [
        rated("rooms", len(plan.rooms), rates.SWISS_ROOMS, source="room numbers on the sheet"),
        rated("rooms_with_area", measured, rates.SWISS_ROOMS, source=area_source),
        rated("apartments", len(plan.apartments), rates.SWISS_APARTMENTS, source="unit tags (Whg. or App.)"),
        rated("door_openings", plan.doors.distinct, rates.SWISS_DOORS, source="door symbols, each place once"),
        # The same count as the agent tool: one window symbol can stand for several windows side by side.
        *[rated(f"{kind}s", swiss_plan.fixture_count(plan, kind).value, rates.swiss_fixture(kind),
                source="fixture symbols") for kind in sorted(counts)],
    ]  # fmt: skip
    bar_ratio = None
    if scale is not None and scale.bar_points_per_metre is not None:
        bar_ratio = 1.0 / (scale.bar_points_per_metre * scale.metres_per_point / scale.ratio)
    found = conflicts.swiss_scale(scale.ratio, scale.agrees, bar_ratio) if scale is not None else []
    return DocumentFacts(
        kind="plan_pdf",
        pages=(Page(index=0, width=page.width, height=page.height, unit="pt"),),
        entities=tuple(entities),
        unknown=UNKNOWN,
        summary=tuple(summary),
        conflicts=tuple(found),
    )
