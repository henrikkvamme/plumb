# ifc lane: IFC model tool, BIM sheet tool, IFC solver

Worker slug: `ifc`. Date: 14 November 2026. Every number below comes from a run I made. Run ids are in
`experiments/LEDGER.md`.

## What I built

| File | What it is |
|---|---|
| `src/bp/tools/ifc_model.py` | Typed queries on an IFC file. Frozen pydantic results with GlobalIds as evidence: `project_info`, `storeys`, `header_info`, `site_location`, `count_elements` (by category, optional storey), `count_class`, `class_histogram`, `type_breakdown`, `storey_summaries`, `material_breakdown`, `spaces` / `find_spaces` / `space_info` (net floor area from Qto, else plan footprint of the body geometry, marked by `area_source`), `storey_space_area`, `storey_quantity` (sum of a Qto entry such as NetVolume, Length, NetSideArea, with unit scales), `common_property` (Pset_*Common: IsExternal, LoadBearing, FireRating), `thickness_m`, `systems`, `classes_elements` (IFC2X3 MEP through type classes). |
| `src/bp/tools/ifc_sheet.py` | What a vector PDF sheet exported from a BIM model gives, from the sheet alone: title (project, view, storey), scale text 1:N, scale bar (m per pt), whether the two agree, room polygons (light fills) with area in m2, text lines, room tags, `room_area` with status found / no_label / no_region / ambiguous / no_scale, `total_room_area`, `storey_matches`, sheet kind. |
| `src/bp/solvers/ifc.py` | `IfcSolver`. Sniffs by content (`ISO-10303-21`, `%PDF`, other). A multilingual template parser (`parse_question`: en, de, nl, da, et, es, pl, ro, it). IFC route: answers the 8 ifc_models families with the model rules. Sheet route: answers room area, storey room count and storey room total; abstains on the rest with a reason. Free-text route for ifc_bench: `plan_text` picks one of 15 report kinds, `_report` writes the text from tool facts. Any other document: abstains with `unsupported`. |
| `src/bp/toolbench/ifc.py` | `bench(partition) -> dict`. Writes `experiments/tools/ifc.json` (dev) and `ifc-val.json`. Measures ifc_model per family (also on PDF items, through the project's IFC found by file name: a bench-only shortcut), ifc_sheet per family, the sheet route split, and the free-text reports per kind. |
| `tests/test_ifc.py` | 15 tests on an IFC file and a PDF sheet made in the test (no dataset). |

Rules that the IFC route copies from the public generator (analysis/ifc/05): storey by containment or
aggregation; Qto first; stairs top level only; IFC2X3 sanitary and light fixtures are `IfcFlowTerminal` with
a matching type. Volume, length and side-area questions abstain (`not_in_model`) when the model has no Qto.
I did not add the geometry fallback for those (47-69% in the earlier probe).

## Commands

```sh
uv run bp run bp.solvers.ifc:IfcSolver --source ifc_models --partition val --jobs 6 --note "..."
uv run bp run bp.solvers.ifc:IfcSolver --source ifc_models --partition dev --jobs 6 --note "..."
uv run bp run bp.solvers.ifc:IfcSolver --source ifc_bench --partition val --jobs 4 --note "..."
uv run bp run bp.solvers.ifc:IfcSolver --source ifc_bench --partition dev --jobs 4 --note "..."
uv run bp run bp.solvers.ifc:IfcSolver --source swiss_dwellings --partition val --docs 10 --jobs 6 --note "..."
uv run bp run bp.solvers.ifc:IfcSolver --source cubicasa5k --partition val --docs 20 --jobs 6 --note "..."
uv run bp run bp.solvers.ifc:IfcSolver --source ifc_models --source ifc_bench --partition lock --jobs 6 --note "..."
uv run python -m bp.toolbench.ifc dev    # and: val
```

## Sealed runs (all sealed = yes)

| Run id | Selection | Items | Score | Accuracy | Answered | Wrong |
|---|---|---|---|---|---|---|
| `20261114-013601-...IfcSolver-stoa` | ifc_models val (first version) | 308 | +0.643 | 64.29% | 64.29% | 0.00% |
| `20261114-014706-...IfcSolver-stoa` | ifc_models val | 308 | **+0.682** [+0.029, +0.917] | 68.18% | 68.18% | 0.00% |
| `20261114-014707-...IfcSolver-stoa` | ifc_models dev | 1012 | **+0.744** [+0.515, +0.863] | 74.60% | 74.80% | 0.20% |
| `20261114-014708-...IfcSolver-stoa` | ifc_bench val | 182 | +0.005 | 1.10% | 1.65% | 0.55% |
| `20261114-014709-...IfcSolver-stoa` | ifc_bench dev | 512 | +0.010 | 1.56% | 2.15% | 0.59% |
| (overwritten, see below) | swiss_dwellings val, 10 docs | 168 | 0.000 | 0% | 0% | 0% |
| `20261114-014723-...IfcSolver-stoa` | cubicasa5k val, 20 docs | 169 | 0.000 | 0% | 0% | 0% |
| `20261114-014757-...IfcSolver-stoa` | ifc_models + ifc_bench LOCK (opened once, at the end, no tuning after) | 493 | +0.647 | 64.91% | 65.11% | 0.20% |

Per cell:

- val ifc_models: area/model 24 items 100%; count/model 20 items 100%; area/pdf 199 items 76.9% (0 wrong);
  count/pdf 60 items 21.7% (0 wrong); length/pdf 2 and volume/pdf 3 abstained.
- dev ifc_models: area/pdf 739 items 96.08% (2 wrong, 0.3%); count/model 16 items 100%; count/pdf 171 items
  16.96%; length/pdf 27 and volume/pdf 59 all abstained.
- lock: area/model 268 items 99.63% (1 abstained, 0 wrong); count/model 24 items 100%; area/pdf 25 items
  84.0% (1 wrong); count/pdf 52 items 11.5%; ifc_bench 114 items +0.018.
- The first val run (+0.643) missed the Spanish storey count ("¿Cuál es el número ..."). I fixed the parser,
  which gave +0.682.

## The honest PDF route: what a sheet alone answers

2,694 of the 3,062 public ifc_models rows are asked on a PDF sheet. The sheet prints no areas (0 printed area
values, docs/research/data/ifc.md). So a room area is the room polygon times the scale. The scale bar and the
1:N text agree within 2% on the sheets, and both are on the sheet. That is a measurement from the document, not
a lookup.

Split of the PDF items (harness items, twins included):

| Partition | PDF items | Answered right | Answered wrong | Abstained: not_on_document | Abstained: unsupported | Abstained: ambiguous |
|---|---|---|---|---|---|---|
| dev | 996 | 741 | 2 | 158 | 97 | 0 |
| val | 264 | 166 | 0 | 31 | 23 | 44 |

Per family on dev (toolbench, `experiments/tools/ifc.json`):

| Family | Items | Sheet route |
|---|---|---|
| room net area | 691 | 691 right |
| room count on the storey | 29 | 29 right (count of room polygons) |
| total room area on the storey | 21 | 19 right, 2 wrong (digitalhub E01 2.4% off, molio 1. sal 25% off) |
| model-wide counts (doors, walls ... in the model) | 45 | abstain, not_on_document (one storey sheet) |
| slab volume, wall volume, wall length, wall side area | 113 | abstain, not_on_document (a plan cut has no heights or net quantities) |
| storey counts of doors 26, walls 22, windows 17, stairs 17, columns 15 | 97 | abstain, unsupported (drawn, but not tagged in a way I can count; earlier probe: wall fills 34/62, door arcs 0/88) |

So 743 of 996 dev PDF items (74.6%) are answerable from the sheet, and 166 + 44 of 264 val items. The 44 val
abstentions are gymzaal: every room is modelled twice, so the tag lies in two overlapping polygons of
different area. The solver abstains (`ambiguous`) and gives the smaller polygon as `best_estimate`. That
estimate is right on 31 of 44 (70%). Answering it would add about +0.058 to the val score. I did not do it:
the rule would be tuned on val (gymzaal is only in val), and the convention is a coin with 70% odds.

## Tool benchmark (dev, agreement with the public keys)

ifc_model (IFC route, 100% everywhere): area_room 691/691 (via the project IFC of the PDF items),
area_total_storey 21/21, area_wall_side 27/27, count_model 16/16 (.ifc) and 45/45 (via PDF), count_storey
126/126, length_walls 27/27, volume_slabs 31/31, volume_walls 28/28. On val also 100% on every family
(area_room 21/21 .ifc and 186/186 via PDF, count_model 14/14 and 24/24, count_storey 6/6 and 36/36, ...).

ifc_sheet: see the table above. On val: area_room 142 right, 0 wrong, 44 abstained; total area 11/11; room
count 13/13.

Free-text reports (ifc_bench dev, "every number of the reference is in the text"):

| Kind | Items | All facts | No facts in key | Fact recall |
|---|---|---|---|---|
| types (type breakdowns) | 138 | 41 | 6 | 0.55 |
| none (no report fits) | 151 | 0 | 25 | - |
| systems | 45 | 5 | 13 | 0.23 |
| materials | 35 | 9 | 6 | 0.42 |
| spaces | 34 | 2 | 0 | 0.50 |
| thickness | 18 | 3 | 0 | 0.70 |
| fire_rating | 16 | 1 | 13 | 0.33 |
| metadata | 11 | 8 | 0 | 0.41 |
| others (wall_length, count, load_bearing, levels, space_heights, location, slab_volume, largest_room) | 64 | 11 | 7 | - |

Only `metadata` is above one half on dev (8/11), so `ANSWER_KINDS = {"metadata"}`. Every other report is an
abstention with the report as `best_estimate`. The best estimate holds every fact on 72 of 512 dev items and
19 of 182 val items.

What is a scoring limit, not a tool limit (seen in the misses):

- Hyphens in type names become negative numbers: "Treppe-1-OG" gives the fact -1.0.
- Thousands separators: "10,957" becomes the fact 10.957, "2,450" becomes 2.45.
- Rounding: the reference prints 69% where the report prints 68.8%, or 208.3 m2 where it prints 208.29.
- Words inside names: "S1" in "Blok S1" gives the fact 1.0.
- 128 items of the whole suite have no number in the key. An answer to them is always scored wrong, also when
  it is right ("cooling systems are not available in this model").
- The references are LLM-written and pick conventions freely (family name of a door type in one answer, the
  full type name in the next; interior walls derived from type names when the model has no IsExternal).

## Documents that are neither

swiss_dwellings val 10 docs: 168 items, 0 answered. cubicasa5k val 20 docs: 169 items, 0 answered
(`20261114-014723`). The sheet route only answers when the title has a storey and the sheet has a scale.

## What failed, and problems for the lead

- Harness: run ids have a resolution of one second. My swiss run and my cubicasa run started in the same
  second, and the cubicasa run overwrote `experiments/runs/20261114-014723-bp.solvers.ifc.IfcSolver-stoa`. The
  swiss number above is from the console output only. Fix idea: add the selector hash or a counter to
  `new_run_id` (in `track.py`, which I may not change).
- The full gate fails today on files of other workers (ruff and ty on `src/bp/hardcases/*`,
  `src/bp/solvers/swiss.py`, `src/bp/tools/swiss_plan.py`, `src/bp/toolbench/swiss.py`,
  `src/bp/toolbench/cubicasa_detect.py`, `src/bp/tools/symbol_detector.py`, `src/bp/tools/pdf_text.py`).
  My files pass ruff and ty, and `pytest -q` passes (all tests).
- The storey totals on sheets give 2 wrong on dev and 1 wrong on lock. The union of polygons did not separate
  the bad cases, so I kept the answer at confidence 0.8.
- `dental_clinic_mep.ifc` does not parse in IfcOpenShell 0.9.0. The solver abstains with `unreadable`.

## What I would try next

1. Storey element counts on sheets (97 dev items abstained): read the door leaf and swing lines, window
   frames and stair treads as symbol groups by colour and stroke width, and measure each on dev before it
   answers.
2. Gymzaal-style duplicates: the drawing order of the polygons may follow the IFC order, which the generator
   used. Test that on a dev-like sheet made from a dev IFC with duplicated spaces, not on val.
3. ifc_bench: the type-breakdown report is right on 41 of 138. Print integer and one-decimal percentages and
   the Revit family name next to the type name, then gate again on dev. A judge model would score these
   answers more fairly than the number rule.
4. Geometry fallback for wall length and volume on models without Qto, with a low confidence and a
   `best_estimate` only.
