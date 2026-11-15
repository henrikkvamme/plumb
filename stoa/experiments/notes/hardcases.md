# Hard cases: realistic hard questions with trusted keys

Date: 2026-11-14. Owner: the hardcases worker. Code: `src/bp/hardcases/`. Tests: `tests/test_hardcases.py`.

## What was built

A deterministic, seeded generator (seed `hard-v1`) that writes `suites/hard.jsonl` (git-ignored) and the tracked
sample `experiments/hard-cases-sample.md` (30 items, one per family first). Every row is a `bp.contract.Item` with
`suite="hard"`, `origin="derived"`, a family per question kind, `group` from `qcommon.group_key`, `partition` from
`split_v0.json` (test -> lock) and `cell = "<skill>/<input>"`. Keys come from labels and geometry, never from a solver.

Modules:

- `common.py`: the `Draft`, the group, the partition, the item id (`h-` + sha256 of doc, family, question).
- `swiss_facts.py`: reads each Swiss floor once. It takes room polygons, numbers and labels from the DXF, room areas
  and fills from `pdf_features.json`, and the source CSV geometries. The CSV maps onto the DXF by an exact rigid fit
  (Kabsch, residual about 1e-14 m), so each DXF room gets its source subtype, windows and doors. Cache:
  `data/external/swiss-derived/hardcases_swiss_facts.json` (1040 floors, about 6 s).
- `swiss_gen.py`: 22 Swiss families with de, fr and it twins.
- `cubicasa.py`: CubiCasa SVG labels (room classes, window and door polygons). 7 families, fi twins.
- `ifc.py`: IfcSpace footprints per storey, asked on the storey plan PDF or on the model. 6 families.
- `select.py`: a balanced seeded selector. At most 4 items per document, one item per family per document, a cap per
  plan, and each family spread evenly over the input kinds.
- `build.py`: the entry point.

## Trust rules (the second path)

- Swiss: a floor is used only when every room passes: DXF polygon area, PDF feature area and source CSV area agree
  within 1%, a printed "m²" label (if any) agrees within 0.006, and the public answer for that room (if any) agrees.
  The floor also needs an exact source alignment, unique room numbers, no label without a number, outdoor flags that
  agree, and public label counts and label areas that match. 980 of 1040 floors pass.
- Window and door counts come from two paths (DXF and source CSV). A count is used only when both agree. Shared doors
  are stacked duplicates in the DXF, so `doors_to_room` takes the de-duplicated count and keeps the raw count as an
  alternate.
- CubiCasa: an opening count is used only when it is the same at 3 px and 10 px touch tolerance. Plans with one floor
  and no `UserDefined` or generic `Room` class only. `compare_rooms` needs an area ratio of at least 1.3.
- IFC: the footprint area and the upward-face area agree within 1%, the public room answer agrees, rooms overlap less
  than 5%, and titles are unique. `named_rooms_area` keeps the `Qto` net area sum as an alternate.
- Lookups need a clear winner (largest room at least 5% above the second). `ambiguous_room` needs at least 15% spread
  between rooms with the same label.

## Families (final suite, 1038 items)

| family | n | family | n |
|---|---|---|---|
| absent_room | 47 | doors_to_room | 67 |
| absent_space | 36 | largest_apartment | 36 |
| ambiguous_room | 42 | largest_room_area | 36 |
| apartment_area | 36 | largest_room_lookup | 64 |
| apartment_area_sqft | 30 | named_rooms_area | 15 |
| apartments_over_2_rooms | 36 | room_difference | 59 |
| area_no_scale | 25 | rooms_over_n_area | 36 |
| average_room_size | 36 | rooms_over_n_count | 24 |
| bath_area | 42 | rooms_with_window | 42 |
| bath_tiles (+10% waste) | 36 | smallest_room_lookup | 36 |
| bathrooms_without_window | 61 | storey_area_sqft | 16 |
| bedroom_area | 36 | wall_material | 24 |
| bedrooms_with_window | 30 | ceiling_height | 24 |
| circulation_share | 36 | compare_rooms | 30 |

- Input: swiss pdf 250, swiss raster 250, swiss cad 250, cubicasa raster 159, ifc pdf 85, ifc model 44.
- Partition: dev 612, val 210, lock 216.
- Skill: unanswerable 198 (19.1%). The rest are count, measure, lookup and compound, spread over all four inputs.
- Twins: 356 items (de 196, fr 74, fi 64, it 22). IFC items have no twins.
- 824 documents, 684 groups. Candidates before selection: Swiss 21,586 on 980 floors, CubiCasa 10,710 on 2,534
  plans, IFC 177 on 35 storeys.
- Unanswerable reasons: `not_on_document` (ceiling height, wall material, absent room, absent space),
  `ambiguous` (two rooms with the same label), `no_scale` (CubiCasa area questions, only on 31 plans checked by eye
  to have no scale bar or dimension), `not_in_model` (IFC absent room, together with `not_on_document`).

## Commands

```sh
uv run python -m bp.hardcases.swiss_facts      # optional, rebuild the Swiss cache (about 6 s)
uv run python -m bp.hardcases.build            # writes suites/hard.jsonl and the sample (about 9 s)
uv run pytest -q tests/test_hardcases.py       # 10 tests, about 20 s with the dataset
uv run bp run null --suite hard --jobs 6 --note "hard suite, null baseline"
```

## Measured numbers

- Build digest (sha256 of the item JSON, first 16 hex): `1522399f162727ae`, the same in two processes with different
  hash seeds (the test checks this).
- Agreement with public answers, measured before the room-number fix: room areas by label 1006/1017, room counts by
  label 6299/6365, apartment areas 1834/1875, floor totals 1025/1040. The misses came from room numbers like
  "U1.03" that the parser dropped. After the fix the floor check requires full agreement; 980/1040 floors pass.
- Checked by eye on PNGs: site1584_bldg2779_floor12858 (bath area 5.67, bathrooms without window 2, room difference
  23.48, window counts per room). CubiCasa 9471, 14714, 2526, 11365 (bedrooms with window, bathroom without window,
  doors). All keys agreed with the drawing.
- Null baseline, run `20261114-015138-null-hard` (ledger): 1038 items, 1394 rows, 684 groups.
  Score +0.0954 [+0.0837, +0.1069], accuracy 19.08% [16.73, 21.38]. All of it comes from abstaining on the 198
  unanswerable items (score +0.500 per item there, 0 elsewhere). By source: cubicasa +0.154, ifc +0.089,
  swiss +0.084.

## What failed or is open

- `after_calibration` and `calibration` are not filled on the `no_scale` items. No CubiCasa plan carries a true scale,
  and the Swiss PNGs all have one, so there is no plan where a calibration makes an area answerable and the key is
  known. Swiss PNG items could get a `Calibration` from the DXF, but those are not unanswerable.
- Harness issue (not changed, `scoring.py` is not mine): `canonical_unit("%")` is None. A solver answer with unit "%"
  scores wrong against a "%" key; only unit None or "" passes. `circulation_share` (36 items) uses "%". Proposed fix:
  treat "%" as a dimensionless unit in `scoring.canonical_unit`.
- IFC families have no twins and `named_rooms_area` has only 15 items: only 35 of 80 storeys pass the checks.
- The first `largest_room_*` wording was ambiguous about corridors. It now says corridors and stair halls count, and
  the area key keeps the largest non-circulation room as an alternate.
- Gate state at the end: ruff and ty are clean on `src/bp/hardcases` and `tests/test_hardcases.py`, and my tests pass.
  The full gate does not pass because of other workers' files: ruff findings in `src/bp/tools/`, `src/bp/toolbench/`
  and `tests/test_cubicasa_detect.py`, a ty error in `src/bp/tools/symbol_detector.py`, and 3 failing tests in
  `tests/test_swiss.py`. I did not edit them.

## What to try next

- Calibration items: Swiss PNGs with the scale bar cropped out, with `after_calibration` set from the DXF scale.
- More IFC: relax the overlap check per model, add de or fr twins, and add door and window counts from `IfcRelSpaceBoundary`.
- A short manual or LLM review of 50 random keys per family, to measure the key error rate directly.
- Run a real solver on `--suite hard` and compare with the public `stoa` suite per family.
