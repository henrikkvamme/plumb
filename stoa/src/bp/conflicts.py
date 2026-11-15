"""Facts of one document that do not add up.

Two readings of the same quantity that disagree by more than their error margins are a conflict: a measured area
against the printed area of the room, the rooms of a group against its printed total, scale witnesses that
disagree, the printed scale against the measured one, two door counts. A conflict names the entities that take
part and the ones whose values are in doubt, so the agent can lower the confidence of an answer that uses them.

The tolerances come from the error margins of the facts (`bp.rates`), so a conflict means "outside the band that
held about 9 of 10 test items", not a fixed share.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bp.contract import Conflict

if TYPE_CHECKING:
    from bp.facts import DocumentFacts, Entity, Fact
    from bp.tools import sheet_plan

# A printed area and its measured outline may differ by the rounding of the print and by this share. On 6,587 Swiss
# test rooms the largest difference was 0.57% (experiments/tools/swiss.json, printed_vs_polygon), so 1% is above
# every measured case.
PRINTED_GAP = 0.01
PRINTED_ROUNDING_M2 = 0.05  # half of 1 sq ft (0.046 m2), and above the 0.005 m2 of a Swiss print with 2 places
USER_SCALE_GAP = 0.02  # the user scale and the dimension lines: as in facts.py
SCALE_FIT = 0.02  # a printed ratio fits the measured scale at a common resolution within this
WEAK_LINES = 5  # fewer agreeing dimension lines than this is a weak scale (bp.rates.STRONG_LINES)
# Two door counts: the door key of the sheets is right within 3% (jobs/sheets/usace.py DOOR_TOLERANCE), at least 2.
DOOR_GAP = 0.03
DOOR_FLOOR = 2
MEASURED_UNITS = frozenset({"m2", "m²", "m", "ft2", "ft", "sqft"})


def _fact(entity: Entity, key: str) -> Fact | None:
    return next((f for f in entity.facts if f.key == key and isinstance(f.value, (int, float))), None)


def _number(fact: Fact) -> float:
    assert isinstance(fact.value, (int, float))
    return float(fact.value)


def _area_conflict(entity: Entity) -> Conflict | None:
    measured, printed = _fact(entity, "area"), _fact(entity, "printed_area")
    if measured is None or printed is None:
        return None
    a, b = _number(measured), _number(printed)
    tolerance = max(measured.margin or 0.0, PRINTED_GAP * b, PRINTED_ROUNDING_M2)
    if abs(a - b) <= tolerance:
        return None
    unit = "m²" if measured.unit in {"m2", "m²"} else measured.unit
    text = (
        f"{entity.label}: the outline measures {a:g} {unit}, and the drawing prints {b:g} {unit}. They differ by "
        f"{abs(a - b):.2f} {unit} ({100 * abs(a - b) / b:.0f}%), more than the margin of ±{tolerance:.2f} {unit}."
    )
    return Conflict(id=f"area:{entity.id}", entity_ids=(entity.id,), text=text, doubtful=(entity.id,))


def _sum_conflict(group: Entity, by_id: dict[str, Entity]) -> Conflict | None:
    total = _fact(group, "printed_area") or _fact(group, "printed_total")
    if total is None or not group.members:
        return None
    parts = [(m, _fact(by_id[m], "area")) for m in group.members if m in by_id]
    measured = [(m, f) for m, f in parts if f is not None]
    if not measured or len(measured) < len(parts):
        return None
    summed = sum(_number(f) for _, f in measured)
    whole = _number(total)
    tolerance = max(sum(f.margin or 0.0 for _, f in measured), PRINTED_GAP * whole, PRINTED_ROUNDING_M2)
    if abs(summed - whole) <= tolerance:
        return None
    text = (
        f"{group.label}: its {len(measured)} rooms add up to {summed:.2f} m², and the drawing prints a total of "
        f"{whole:g} m². The difference of {abs(summed - whole):.2f} m² is more than the margin of ±{tolerance:.2f} m²."
    )
    ids = tuple(m for m, _ in measured)
    return Conflict(id=f"sum:{group.id}", entity_ids=(group.id, *ids), text=text, doubtful=ids)


def count_conflict(
    cid: str, ids: tuple[str, ...], what: str, a: tuple[str, int], b: tuple[str, int]
) -> Conflict | None:
    """Two counts of the same things from two methods: a conflict when they differ by more than 3% (at least 2)."""
    (first, x), (second, y) = a, b
    if abs(x - y) <= max(DOOR_FLOOR, DOOR_GAP * max(x, y)):
        return None
    text = f"{what}: {first} gives {x}, and {second} gives {y}. A count from either is an estimate."
    return Conflict(id=cid, entity_ids=ids, text=text, doubtful=ids)


def find(facts: DocumentFacts) -> tuple[Conflict, ...]:
    """The conflicts that the facts alone show: measured against printed areas, and sums against printed totals."""
    by_id = {e.id: e for e in facts.entities}
    out: list[Conflict] = []
    for entity in facts.entities:
        found = _area_conflict(entity) or _sum_conflict(entity, by_id)
        if found is not None:
            out.append(found)
    return (*facts.conflicts, *out)


def sheet_scale(plan: sheet_plan.SheetPlan) -> list[Conflict]:
    """The scale and door conflicts of a large sheet.

    The user scale against the dimension lines, few lines that agree, the printed ratio against the measured scale,
    and the door count of the swing finder against the detector.
    """
    from bp.tools import sheet_rooms, sheet_text  # noqa: PLC0415 - they load cv2; only a sheet needs them

    scale, measured = plan.scale, plan.measured
    out: list[Conflict] = []
    witnesses = tuple(f"scale:witness:{i}" for i in range(len(measured.witnesses))) if measured else ()
    if scale is not None and measured is not None and scale.source == "user":
        gap = abs(measured.ppm / scale.ppm - 1)
        if gap > USER_SCALE_GAP:
            text = (f"The scale from the user ({scale.ppm:.1f} px/m) and the dimension lines of the sheet "
                    f"({measured.ppm:.1f} px/m) differ by {100 * gap:.0f}%. Each measured length and area depends on it.")  # fmt: skip
            out.append(Conflict(id="scale:user", entity_ids=("scale", *witnesses), text=text, doubtful=("scale",),
                                all_measured=True))  # fmt: skip
    if scale is not None and measured is not None and scale.source == "dimension lines":
        if measured.agreeing < WEAK_LINES and measured.read >= 2 * measured.agreeing:
            text = (f"Only {measured.agreeing} of {measured.read} dimension lines agree on one scale. The others give "
                    "other scales: a detail at another scale, or a misread text.")  # fmt: skip
            out.append(Conflict(id="scale:witnesses", entity_ids=("scale", *witnesses), text=text, doubtful=("scale",),
                                all_measured=True))  # fmt: skip
        ratios = {s.ratio for s in sheet_text.printed_scales(plan.lines)}
        if len(ratios) == 1:
            ratio = next(iter(ratios))
            fits = [dpi for dpi in sheet_rooms.RENDER_DPI if abs(scale.ppm / (dpi / 0.0254 / ratio) - 1) <= SCALE_FIT]
            if not fits:
                text = (f"The sheet prints the scale 1:{ratio}, but the dimension lines give {scale.ppm:.1f} px/m, "
                        f"which fits 1:{ratio} at no common resolution.")  # fmt: skip
                # Many dimension lines that agree are stronger than one printed ratio: the sheet can be printed at
                # another size, or the ratio belongs to another drawing on the sheet (as sheet_plan decides too).
                strong = measured.agreeing >= WEAK_LINES
                text += (f" The {measured.agreeing} dimension lines that agree are used: the sheet may be printed at "
                         "another size." if strong else " Each measured length and area depends on the scale.")  # fmt: skip
                out.append(Conflict(id="scale:printed", entity_ids=("scale", *witnesses), text=text,
                                    doubtful=() if strong else ("scale",), all_measured=not strong))  # fmt: skip
    detector = _detected_doors(plan)
    if scale is not None and detector is not None:
        # The same witness as count_door_swings: the second detector when it has seen the sheet, else the arc finder.
        # With the arc finder here and the second detector in the tool, the agent abstained on counts that agreed.
        second = plan.second_swings
        witness = ("the arc finder", len(plan.arc_swings)) if second is None else ("the second door detector", len(second))
        found = count_conflict("doors:count", _door_ids(plan), "Door leaves on this sheet",
                               witness, ("the door detector", len(plan.swings)))  # fmt: skip
        if found is not None:
            out.append(found)
    return out


def _door_ids(plan: sheet_plan.SheetPlan) -> tuple[str, ...]:
    from bp.tools.sheet_plan import door_id  # noqa: PLC0415 - sheet_plan loads cv2; only a sheet needs it

    return tuple(door_id(s) for s in plan.swings)


def _detected_doors(plan: sheet_plan.SheetPlan) -> int | None:
    """The door count of the trained detector, when its result for this sheet is in the cache. None otherwise."""
    from bp.tools import sheet_text  # noqa: PLC0415 - it loads cv2; only a sheet needs it

    try:
        from bp.tools import sheet_doors  # noqa: PLC0415 - optional: the detector cache may be absent
    except ImportError:
        return None
    found = sheet_doors.detected(sheet_text.pixel_key(plan.rgb))
    return None if found is None else len(found)


def swiss_scale(ratio: int, agrees: bool | None, bar_ratio: float | None) -> list[Conflict]:
    """The scale text of a Swiss plan against its scale bar."""
    if agrees is not False or bar_ratio is None:
        return []
    text = (f"The title block says 1:{ratio}, and the scale bar measures 1:{bar_ratio:.0f}. Each measured length and "
            "area depends on the scale.")  # fmt: skip
    return [Conflict(id="scale:bar", entity_ids=("scale",), text=text, doubtful=("scale",), all_measured=True)]


# ----------------------------------------------------------------------------- links from tool rows to facts


def row_ids(row: dict[str, Any], known: set[str]) -> list[str]:
    """The fact entities that one row of a tool result is about: its `entity_id`, else its room number or letter."""
    ids: list[str] = []
    entity = row.get("entity_id")
    if isinstance(entity, str):
        ids.append(entity)
    elif isinstance(row.get("letter"), str):
        ids.append(f"apartment:{row['letter']}")
    elif isinstance(row.get("number"), str):
        ids.append(f"room:{row['number']}")
    return [i for i in ids if i in known]


def is_measured(row: dict[str, Any]) -> bool:
    """True for a row that holds a measured length or area."""
    return any(key.endswith(("_m2", "_m", "_sqft", "_ft", "_ft2")) or key in {"area", "length"} for key in row)


def touching(facts: DocumentFacts, ids: set[str], *, measured: bool) -> list[Conflict]:
    """The conflicts that put one of `ids` in doubt; a scale conflict too when a measured value is used."""
    return [c for c in facts.conflicts if set(c.doubtful) & ids or (measured and c.all_measured)]


def margin_of(facts: DocumentFacts, entity_id: str, value: float) -> tuple[Fact, float] | None:
    """The measured fact of the entity that `value` comes from, and the factor from the fact to the value.

    The factor is 1 for the value as the fact gives it, or a unit change (m2 to sq ft, m to ft), so that a tool
    row that gives the area in sq ft still finds the margin of the area fact.
    """
    entity = next((e for e in facts.entities if e.id == entity_id), None)
    if entity is None or value == 0:
        return None
    for fact in entity.facts:
        if (
            fact.margin is None
            or fact.margin_share is None
            or not isinstance(fact.value, (int, float))
            or not fact.value
        ):
            continue
        for factor in (1.0, 1 / 0.09290304, 1 / 0.3048):
            expected = float(fact.value) * factor
            # a tool rounds: to 2 places, or a unit change to a whole number
            if abs(value - expected) <= max(0.006, 0.51 if factor != 1.0 else 0.0, 1e-6 * abs(expected)):
                return fact, factor
    return None
