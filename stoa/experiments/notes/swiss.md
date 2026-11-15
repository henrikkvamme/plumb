# Swiss Dwellings vector PDF tool and solver

Date: 2026-11-14. Worker slug: swiss. Base commit 3a99e5f (working tree not committed).

## What was built

- `src/bp/tools/pdf_text.py`: a generic PDF page reader. It knows nothing about drawings.
  - `read_page(path, page)` returns a frozen `PdfPage`: text spans (merged lines from `get_text("dict")`),
    text runs (one record per text operator from `get_texttrace()`, never merged), vector paths and the image count.
  - `VectorPath` has the stroke, fill, width, dashes, bbox, operator letters (l/r/q/c), points, rings (subpaths)
    and straight line segments. `is_pdf` checks the magic bytes, `page_count` returns 0 for a file that is not a PDF.
- `src/bp/tools/swiss_plan.py`: the typed Swiss Dwellings tools, on top of `pdf_text`.
  - `detect(page)`: a sheet is a Swiss plan only when it has generator room fills, room numbers, a scale text and
    no raster images. Everything else is "not a plan".
  - `read_scale`: the "1:100 (A3)" text plus the scale bar. Both must agree.
  - `compile_plan` / `read_plan`: rooms (number, label, printed area, polygon, computed area, fill class, outdoor,
    apartment, holes), apartments (unit tags and red outlines), doors (stacked and distinct), fixtures (toilet,
    washbasin, bathtub, shower, kitchen, window, other, with copies and sizes).
  - Queries return a `Fact` (value, unit, evidence, warnings): `room`, `room_area`, `label_count`, `label_area`,
    `total_area`, `apartment_area`, `apartment_count`, `door_count`, `fixture_count`.
  - Room areas come from the even-odd XOR of the path rings, so multi-part rooms and holes are right.
    Separate inner fills are subtracted (`net_holes`).
- `src/bp/solvers/swiss.py`: a thin solver. `parse_question` reads en/de/fr/it questions with keywords into one
  of 12 intents. `SwissSolver.ingest` never fails (a failed ingest scores every question -1). `ask` abstains:
  - UNSUPPORTED: the file is not a one-page Swiss plan PDF, or the question does not parse.
  - NOT_ON_DOCUMENT: the room or apartment is not on the sheet, or a label count is 0.
  - AMBIGUOUS with a best estimate: the tool raised a warning, or the question label differs from the sheet label.
  - Otherwise it answers with confidence 0.97, evidence and one step.
  - It reads only the document. No labels, keys or dataset paths.
- `src/bp/toolbench/swiss.py`: `bench()` compares the tools against `data/external/swiss-dwellings-v3` (DXF layers
  ROOM_OUTLINE, ROOM_TEXT, DOOR, WINDOW) and `data/external/swiss-derived/source_floor.json`, on dev+val floors
  only. It writes `experiments/tools/swiss.json`.
- `tests/test_swiss.py`: 7 tests on small PDFs made in the test (parser in 4 languages, tool, hole ring,
  fixture classes, solver answers and abstentions, abstention on a non-PDF, a plain PDF and a missing file).

## Commands

```sh
cd stoa
uv run ruff check src tests && uv run ty check && uv run pytest -q
uv run bp run bp.solvers.swiss:SwissSolver --source swiss_dwellings --partition dev --jobs 6 --note "..."
uv run bp run bp.solvers.swiss:SwissSolver --source swiss_dwellings --partition val --jobs 6 --note "..."
uv run bp run bp.solvers.swiss:SwissSolver --source ifc_models --source opening_design --source ifc_bench --partition dev --jobs 4 --note "..."
uv run bp run bp.solvers.swiss:SwissSolver --source cubicasa5k --partition dev --docs 150 --jobs 4 --note "..."
uv run python -m bp.toolbench.swiss
```

The lock partition was not run.

## Results (final code)

| run id | selection | items | score | item acc | rows right | answered | wrong |
|---|---|---|---|---|---|---|---|
| `20261114-015600-bp.solvers.swiss.SwissSolver-stoa` | swiss_dwellings dev | 11272 | +0.9993 [+0.9987, +0.9998] | 99.94% | 22530/22544 (99.94%) | 99.95% | 0.01% |
| `20261114-015607-bp.solvers.swiss.SwissSolver-stoa` | swiss_dwellings val | 3765 | +0.9995 [+0.9984, +1.0000] | 99.95% | 7526/7530 (99.95%) | 99.95% | 0.00% |
| `20261114-015620-bp.solvers.swiss.SwissSolver-stoa` | ifc_models + opening_design + ifc_bench dev | 1543 | +0.0000 | 0% | - | 0.00% | 0.00% |
| `20261114-015603-bp.solvers.swiss.SwissSolver-stoa` | cubicasa5k dev, 150 docs | 1287 | +0.0000 | 0% | - | 0.00% | 0.00% |

- Dev by cell: area/pdf n=3603 acc 99.83%, wrong 0.0%. count/pdf n=7669 acc 99.99%.
- Val by cell: area/pdf n=1202 acc 99.83%, wrong 0.0%. count/pdf n=2563 acc 100.00%.
- Errors: 0 in every run. On other documents the solver abstains UNSUPPORTED on every item (0 wrong).
- Earlier sealed runs on the code before the text-run change: dev `20261114-014632-bp.solvers.swiss.SwissSolver-stoa`
  (22530/22544) and val `20261114-014643-bp.solvers.swiss.SwissSolver-stoa` (7526/7530).
- Progress on dev during development (in-process eval, same scoring): 99.43% -> 99.58 -> 99.63 -> 99.83 -> 99.86 ->
  99.88 -> 99.90 -> 99.94% rows.

## Every remaining failure

Dev, 14 rows (7 items):

1. Windows, 1 item, 2 rows, WRONG. `site3801_bldg5831_floor24661`: key 7, answer 6. One window is a 0.4 x 0.4 m box
   whose 2 glass lines do not span the box, so it fails the rule glass == 2 x copies. The DXF bench shows the same
   floor at -1. It is the only window miss in 833 floors.
2. Apartment area, 6 items, 12 rows, ABSTAINED (AMBIGUOUS). The floor has white "orphan" rooms inside a red outline
   with no unit tag (site11692 office unit, site1173 x2, site11876, site11749 "Verkauf", site2263 where the
   untagged outline is part of A). It is not clear from the sheet whether the key adds these rooms to the apartment.
   The best estimate was right on 5 of the 6 items. Including the orphans always (tried) made 3 floors wrong.

Val, 4 rows (2 items): `site1273_bldg2474_floor11569`, apartment area x2, ABSTAINED for the same orphan-room reason
(an orphan room of 1.56 m2). One estimate was right, one was wrong.

So all failures but one item are abstentions. The target (99.6% rows, the rest abstained) is met on dev and val.
The one wrong item is the site3801 window.

## Tool benchmark (`experiments/tools/swiss.json`, 833 dev+val floors, 0 errors)

- Rooms vs DXF: 22966 PDF rooms, 22966 DXF rooms, recall 1.0, precision 1.0. Labels agree on 21776/21776 pairs.
- Area relative error vs DXF ROOM_OUTLINE: median 0, p90 0, p99 1.1e-5, max 4.6e-4 (site42 room 3.19, 0.2197 vs
  0.2196). 100% of rooms within 0.1%.
- Counts vs DXF: doors (stacked) 100% exact (25402 = 25402). Windows 99.88% (14620 vs 14621, one floor -1).
  Apartments 100% (2667). Distinct doors vs DXF 7.9% exact, because the DXF keeps stacked copies.
- Counts vs source_floor.json (deduplicated geometry): toilets 3423, washbasins 3583, bathtubs 2309, showers 590,
  apartments 2667 and distinct doors 21507 all 100% exact. Windows 73.7% exact (14620 vs 14014): the source dedupes
  windows, the PDF and the keys keep stacked copies.
- Scale: 695 floors at 1:100 and 138 at 1:200. The scale bar agrees with the text on all 833.

## Printed vs polygon areas

- 249 floors print room areas, 6587 rooms. Rooms over 2% disagreement: 0. Relative difference median 0.023%,
  p95 0.11%, p99 0.21%, max 0.57%.
- 496 room-area keys sit on rooms with a printed area. The key equals the printed value (within 0.05%) on 496/496.
  It equals the polygon on 397/496.
- Answer: the key follows the print to the cent. The geometry agrees within the 2% tolerance on every room, so both
  score. The solver uses the polygon and warns if print and polygon differ by more than 2% (never on this data).

## What failed or was dropped

- Window rule by aspect ratio (lift boxes with cross lines looked like windows): broke small square windows.
- Window rule by depth (WINDOW_MAX_DEPTH_M 0.7): broke windows in thick walls. Final rule: glass lines == 2 x copies.
- Adding orphan rooms to a single apartment: 3 floors wrong. Now the solver abstains with an estimate.
- Labels from text runs: a ligature splits "Bürofläche" into several operators. Labels now come from merged spans,
  numbers from text runs (merged spans lost 8 rooms on "2.472.48"-style overlaps).

## Gate

- My files pass ruff, ty and pytest (7 tests). The full pytest suite passes.
- `uv run ruff check src tests` and `uv run ty check` still report findings in other workers' files
  (`toolbench/cubicasa_detect.py`, `tools/symbol_detector.py`, `tests/test_cubicasa_detect.py`). I did not touch them.

## Next steps

- Orphan outlines: learn when the key counts the rooms of an untagged outline (6 dev + 1 val floors). A rule on the
  room labels (office, shop) or the outline shape may settle it.
- site3801 window: accept a box whose glass lines are shorter than the box, if nothing else explains it.
- Generalise beyond the generator styles: the detector and classes rely on exact fills (1.0/0.95/0.89/0.81), stroke
  colours and widths. Another source needs a style map.
- A label count of 0 is answered NOT_ON_DOCUMENT. The public set never asks for an absent label. If a private set
  does, the answer "0" may be the expected value.
- No dependency or harness change is needed.
