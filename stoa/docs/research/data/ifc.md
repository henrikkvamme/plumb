# ifc_models and ifc_bench: what the data tells us

Scope: `data/junction-dataset/data/ifc_models/` and `data/junction-dataset/data/ifc_bench/`, with their rows in
`questions.jsonl`. Date: 13 November 2026.

Labels used for each figure:

- **MEASURED**: a script in `stoa/analysis/ifc/` computed it. The script name follows the figure.
- **READ**: a source states it. The source follows the figure.
- **ESTIMATE**: my judgement. It is not a measurement.

All scripts run with `uv run stoa/analysis/ifc/<script>.py`. They use PEP 723 headers and pin
`ifcopenshell==0.9.0.post1` and `pymupdf==1.26.5`. Outputs go to `stoa/analysis/ifc/out/`.

## Findings that change decisions

1. **A small deterministic IfcOpenShell probe reproduces the ifc_models answers.** One fixed rule matches
   3,057 of 3,062 references (99.8%, MEASURED, `05_probe_models.py`, `06_probe_summary.py`). The rule is short:
   use the Qto value when the model has one, else the geometry footprint. Find the storey by containment or
   by aggregation. Count classes with `by_type`. Two class rules are needed: IFC2X3 MEP fixtures are
   `IfcFlowTerminal` filtered by type, and only top-level stairs count. With the 2-decimal areas, 2,215 of
   2,218 area answers match exactly (MEASURED). The 5 misses are 4 Molio stair rows and 1 clinic room name
   that my parser did not match. Decision: the ifc_models answers are the output of an IfcOpenShell script.
   They are not a person's reading of the drawing. When we have the IFC, a probe is the baseline to beat,
   and an LLM is not needed for these questions.
2. **The PDF sheet alone answers most room questions.** Room net area comes from the smallest light-blue
   polygon that contains the room label, scaled by the scale bar. This gives 1,764 of 1,792 rows (98.4%,
   MEASURED, `07_pdf_room_area.py`). The number of blue polygons equals the storey room count in 96 of 96
   rows (MEASURED). The sum of the blue polygons gives the total storey area in 64 of 70 rows (MEASURED,
   `07d_pdf_total_area.py`). Decision: for a PDF-only track, vector parsing is the main path. Vision is a
   fallback. Volume, wall length and wall side-area questions cannot be read from a plan cut (ESTIMATE, see
   question 4).
3. **ifc_bench is a verbatim copy of public IFC-Bench v2, and the public set has 206 more answers.** All
   820 questions and all 820 answers in Stoa's ifc_bench rows are exact copies of the public CSV (MEASURED,
   `03_bench_leakage.py`). All 30 IFC files are byte-identical to the Hugging Face files (MEASURED, sha256
   equals the HF etag). Stoa took every public row on 25 models. The public CSV has 206 more rows on 6
   models that are not in Stoa's data (samuel_macalister arc 52 and mep 22, schependomlaan 51, wbdg_office
   arc 33, mep 37 and str 11; MEASURED). Decision: a public ifc_bench score proves nothing, because any
   model trained on IFC-Bench has seen the answers. The 206 rows are a likely hidden-test pool (ESTIMATE).
   Ask Stoa (see open questions).
4. **Counts follow the model's conventions, not what the drawing shows.** Gymzaal models every room twice
   (48 spaces, 48 overlap pairs), and the reference says 48 rooms. Duplex MEP has 21 rooms plus 21 "MEP
   Space" copies, and the reference says 42 (MEASURED, `08_space_semantics.py`). On the Molio Grundplan the
   reference says 21 walls, but the SVG draws 11 (MEASURED, `07c_svg_counts.py`). Molio has 579 `IfcStair`
   entities, but only 15 are top level. The storey stair answers are 2 and 1, while containment gives 80 and
   44 (MEASURED). Decision: a vision model that counts what it sees will lose points on these rows. A
   solver must copy the generator's convention, which is "elements assigned to the storey".
5. **Volume, length and side-area questions exist only for models with Qto, and geometry does not
   reproduce them.** All 266 of these questions are on the 8 models that carry Qto sets (MEASURED). Qto
   matches 100%. Geometry matches wall volume in 60.6% of rows, slab volume in 69.4% and wall length in
   46.9% (MEASURED). My geometry side area is about 2 times the reference, because it counts both faces
   (MEASURED). Molio walls often have only an `Axis` representation, so geometry gives 9-13% of the
   reference volume (MEASURED). Decision: read Qto. Do not compute geometry for these families, except as a
   last fallback with a low confidence.
6. **Twin questions and repeated rooms inflate public scores.** The 3,062 ifc_models rows are 1,699
   distinct items. 2,726 rows have a twin in another language with the same answer (MEASURED,
   `12_shortcuts.py`). Copying the answer of a same-named room in the same model is correct for 34.6% of
   room items (MEASURED). Decision: split every evaluation by model, never by row.
7. **Cost is small.** The largest file (sixty5_arc, 343 MB) opens in 2.9-6.9 s. Geometry for its 8,109
   spaces, walls and slabs takes 6.5 s. Peak RSS is 2.1-2.4 GB (MEASURED, `11_cost.py`, `02_inventory.py`,
   14-CPU arm64 Mac). The full probe over all 84 question paths takes 28.6 s (MEASURED). One file,
   `dental_clinic_mep.ifc`, does not parse in IfcOpenShell 0.9.0 (MEASURED). Decision: a solver can open
   the IFC per question with no cache problems. It needs a parse-failure fallback.
8. **Much of the data has no questions.** The 500 ResBIM models (all Revit 2026, IFC4, 2 storeys, no
   `IfcSpace`, no Qto) and their 500 PNG renders have no questions. Also without questions: all 24
   elevations, all 12 sections, 2 plans, 4 digitalhub models and 5 ifc_bench files (MEASURED). Decision: if
   the hidden set asks about these, our public score tells us nothing about them (ESTIMATE). See the risks.

## Evidence

### Question 1. Inventory

Scripts: `02_inventory.py` (one subprocess per file, writes `out/inventory.jsonl`), `02b_inventory_table.py`
(writes `out/inventory_table.md` and `out/inventory_summary.json`).

MEASURED:

- 563 IFC files in total: 533 in ifc_models (500 ResBIM plus 33 others) and 30 in ifc_bench. The counts
  in the brief were reversed.
- ifc_models also holds 107 PDF sheets, 107 SVG files and 500 PNG files (the PNGs are ResBIM renders).
- The 62 files that are not ResBIM:
  - Schemas: IFC2X3 31, IFC4 29, IFC4X3 2.
  - Authoring tools: Autodesk Revit 47, ArchiCAD 14, Forensic-BIM 1.
  - 40 have `IfcSpace`. 23 have Qto or BaseQuantities sets.
- ResBIM: 500 files. All are Revit 2026, IFC4, 2 storeys, 0 `IfcSpace`, no Qto, and at most 0.41 MB.
- ResBIM PNG: a 7572x4189 greyscale raster. It shows dimension strings in mm, grid axes and room labels.
  It has no scale bar and no title block.
- 8 files are byte-identical between ifc_models and ifc_bench: molio, fzk, institute (= ac20), smiley and
  four digitalhub v2 files.
- `dental_clinic_mep.ifc` fails with "Syntax error during parse". It is byte-identical to the Hugging Face
  file, so the defect is upstream.

Question coverage (MEASURED, `05_probe_models.py`, `09_bench_kinds.py`):

- ifc_models: 3,062 questions on 84 paths (69 PDF, 15 IFC).
- ifc_bench: 820 questions on 25 of the 30 files.
- ifc_bench files with no questions: city_house_munich_arc, dental_clinic_mep, fantasy_hotel_2_arc,
  sixty5_facade, sixty5_kitchen. The public CSV has no questions on them either.
- ifc_models paths with no questions: ResBIM, digitalhub hzg and lft (v1 and v2), all elevations and
  sections, and frigento plan-03 and plan-04.

Licences:

- ResBIM: MIT (READ, Hugging Face `tsesterh/ResBIM-IFC`).
- IFC-Bench v2: CC BY 4.0 for the dataset. The README says 4 models are GPLv3: 4351, ettenheim_gis, hitos
  and samuel_macalister (READ, `stoa/data/external/ifc-bench/README.md` and `LICENSE`).
- Downloads are in `stoa/data/external/ifc-bench/`: the public CSV, the eval split CSV, the README, LICENSE,
  CHANGELOG, the HF API record (sha d536c338, last modified 2026-10-28) and the paper (arXiv 2605.01698).
  Total size is 896 KB.

### Question 2. Rendered sheets

Script: `04_sheets.py` (writes `out/sheets.json` and PNG renders in `out/sheets/`).

MEASURED:

- 107 sheets: 71 plans, 24 elevations, 12 sections.
- Scale text: 1:100 on 93 sheets and 1:200 on 14. The scale bar agrees with the 1:N text within 0.02%.
- All sheets are vector PDF. There are 0 raster images and 0 printed area values.
- Rooms are light-blue fills (RGB 0.89, 0.93, 0.97) with a name and number label. Cut walls are grey 0.29.
- 863 of 896 room ids asked about are printed on the sheet.
- The storey on the sheet equals the storey in the question in 2,518 of 2,518 rows.
- 176 of 2,694 PDF rows (6.5%) are model-wide counts ("How many doors are in the model"). A single storey
  sheet cannot answer them.

Sheets I looked at (READ, by eye, more than 12):

- fzk, vitoria, molio and digitalhub plans: clean plans.
- esplanades and tuwien: plans rotated on the sheet. Tuwien room names have no numbers.
- warmond: loggia spaces placed far away from the building. This is a placement artifact.
- institute section: storey levels are shown.
- barlad Level 1 and frigento: walls only, no rooms.
- gymzaal: overlapping duplicate labels.
- smiley: 10 terraced houses.
- gdynia elevation: levels in mm.
- Two ResBIM PNGs.

### Question 3. Templates and the IfcOpenShell probe

Scripts: `01_templates.py` (coarse families, `out/templates.json`), `05_probe_models.py` (exact parser and
probe, `out/probe_rows.jsonl`), `06_probe_summary.py` (`out/probe_summary.json`).

Families (MEASURED): area_room 2,079; count_storey 402; count_model 240; area_total_storey 75; volume_slabs
72; volume_walls 66; length_walls 64; area_wall_side 64. 161 distinct templates.

Languages of ifc_models (MEASURED): en 1,699, de 318, et 315, nl 281, da 197, es 196, pl 38, ro 14, it 4.
All 820 ifc_bench questions are English.

Agreement per family (MEASURED, tolerance 2% for measures, exact for counts):

| Family | Rows | Best rule | Best rule agrees | Other candidate |
|---|---|---|---|---|
| area_room | 2,079 | Qto NetFloorArea, else geometry footprint | 2,078 | footprint alone 99.7%; Qto present on 900 rows and right on 900 |
| area_total_storey | 75 | same, summed | 75 | footprint alone 97.3% |
| volume_walls | 66 | Qto NetVolume | 66 | geometry 60.6% |
| volume_slabs | 72 | Qto NetVolume | 72 | geometry 69.4% |
| length_walls | 64 | Qto Length | 64 | geometry long side 46.9% |
| area_wall_side | 64 | Qto NetSideArea | 64 | geometry side about 2x |
| count_model | 240 | by_type, with 2 class rules | 240 | plain by_type 95.4% |
| count_storey | 402 | storey containment or aggregation | 398 | - |

Five disagreements of the next-best rule (MEASURED, from `out/probe_rows.jsonl`):

| Model | Question | Reference | Other rule | Cause |
|---|---|---|---|---|
| molio | net floor area of 'Teknikrum (Rum nr. 602)' on '6. sal' | 23.21 | footprint 24.53 | reference uses Qto (23.21) |
| molio | total net floor area of all rooms on '6. sal' | 99.54 | footprint 102.59 | reference uses Qto |
| clinic-electrical | light fixtures in the model | 1,120 | by_type IfcLightFixture 0 | IFC2X3 uses IfcFlowTerminal (1,120) |
| tuwien | total net volume of all walls on 'OG1' | 102.88 | geometry 16.14 | geometry incomplete, Qto is right |
| molio | stairs shown on the floor plan of '4. Sal' | 2 | containment 80 | 80 nested stair parts; the generator counted 2 |

More of the same kind (MEASURED): fzk Erdgeschoss wall length 66.86 vs geometry 68.30; smiley 2.OG wall
side area 858.94 vs geometry 1,878.32 (two faces); Molio Kælder slab volume 277.33 vs geometry 0.68.

How the generator picks rooms (MEASURED, `08_space_semantics.py`): it asks only about rooms with a unique
name on the storey. On tuwien EG, OG1, DG1 and DG2 there are 27, 25, 24 and 16 rooms. It asked about 9, 8,
8 and 4, and 7, 7, 7 and 5 of the skipped rooms have non-unique names. No model and question pair has two
different answers.

### Question 4. PDF-only difficulty

Scripts: `07_pdf_room_area.py`, `07b_pdf_counts.py`, `07c_svg_counts.py`, `07d_pdf_total_area.py`.

MEASURED:

- Room area from the sheet: label found 1,792; ambiguous label 90; polygon found 1,790; correct within 2%
  1,764 of 1,792 (98.4%).
- The failures are in 2 sheets:
  - gymzaal ground floor: 62 of 88 correct. The polygon under the label is 10-17% smaller than the
    reference. Examples: 'kleedkamer (11)' 33.72 vs 36.39, 'cv ruimte (8)' 8.06 vs 9.74, 'toilet (10)' 3.19
    vs 3.76, 'sanitair (7)' 1.96 vs 2.23, 'werkkast (3)' 1.12 vs 1.26. Each room has two overlapping spaces
    with different areas.
  - gdynia plan-02-1: 14 of 16 correct. The polygon for 'Comunication (-1.1)' (10.43) was not found.
- Storey room counts equal the number of blue polygons in 96 of 96 rows.
- Total storey area from the polygon sum: 64 of 70. Misses: gdynia plan-03 54.77 vs 48.51, digitalhub E01
  1,154.36 vs 1,127.08, molio 1. sal 523.76 vs 416.62.
- Wall counts from grey fills equal the reference in 34 of 62 rows. Door counts from arcs: 0 of 88. Doors
  are not drawn as Bezier arcs.
- SVG files tag each product with `class`, `data-guid` and `data-name`. The class count matches the
  reference in 238 of 390 storey counts. Per class: spaces 96/96, doors 54/88, windows 24/36, walls 28/62,
  columns 22/44, stairs 14/64. The tagging is not consistent: the barlad Level 1 SVG has no classes, and
  the gymzaal and digitalhub SVGs tag only `IfcSpace`.

ESTIMATE: volume, wall length and wall side-area questions (266 rows, 8.7%) cannot be answered from a plan
cut at about 1.2 m. They need the storey height and the slab thickness, and the Qto net values subtract
openings that the plan does not show. Model-wide counts on a storey sheet (176 rows) also cannot be
answered from one sheet. A PDF-only solver can expect a ceiling of about 85-90% on the ifc_models mix.

### Question 5. ifc_bench leakage, scoring and kinds

Scripts: `03_bench_leakage.py` (`out/bench_leakage.json`), `09_bench_kinds.py` (`out/bench_kinds.json`).

MEASURED:

- 820 of 820 questions and 820 of 820 answers equal the public IFC-Bench v2 CSV, including the v2.0.3
  corrections.
- In the public eval split, Stoa's rows are 399 test and 421 train.
- Categories: 1 = 126, 2 = 442, 3 = 89, 4 = 163.
- The public CSV has 1,026 rows on 31 models. Stoa's 820 rows are every public row on 25 of them. The 206
  remaining rows are on 6 models that Stoa did not ship.

Answer kinds (MEASURED, heuristic classifier): list_counts 491, unavailable 118, single_number 64, yes_no
51, short_with_numbers 30, metadata 26, explanation 22, list_names 18. Checkability: partial 539, exact
141, judge 140. Answer length: median 199 characters, p90 743. 30 answers use imperial units, 38 use
thousands separators, 100 say the information is not available.

How IFC-Bench scores (READ, arXiv 2605.01698, Hellin et al., Automation in Construction 2026):

- An LLM judge applies 5 binary criteria: abstention, faithfulness, completeness, transparency and
  relevance. The rubric depends on the category.
- An answer is correct only when the four substantive criteria all pass.
- Judge agreement: Krippendorff alpha 0.70-1.00 between judges, 0.32-0.57 between human experts.
- Best published result: GLM 4.7 adaptive, about 56% overall. Per category: 55.6-63.9, 49.8-53.4,
  66.7-68.4 and 57.8-61.8.

Proposed deterministic scoring for our own evaluation (ESTIMATE, not tested end to end):

| Kind | Rule |
|---|---|
| single_number | normalise units (imperial to SI, strip thousands separators), then 2% tolerance |
| list_counts | parse "label: N" pairs; score per item; a row passes when all items match |
| list_names | set match after case and whitespace normalisation |
| yes_no | first yes or no token |
| metadata | normalised string match |
| unavailable, explanation | LLM judge with the IFC-Bench rubric |

This covers about 680 of 820 rows without a judge (ESTIMATE from the kind counts).

### Question 6. Label noise

Script: `10_label_check.py` (`out/label_check.json`, `out/label_check.txt`).

MEASURED:

- Part A, 30 ifc_models rows stratified by family: 17 consistent (every reading agrees), 13
  convention-dependent (the reference follows one reading and another differs by more than 2%), 0
  contradicted by every reading. For counts the convention verdict is too strict, because the alternative
  rules nearly always differ. Read the 13 as "the reference picks a convention", not as errors.
- Part B, ifc_bench: 58 of 58 "Total X: N" answers equal the IfcOpenShell `by_type` count.

Semantic noise that a person would call wrong (MEASURED, `08_space_semantics.py`):

- Gymzaal: every room is modelled twice. The count reference includes both.
- Duplex MEP: 21 "MEP Space" copies are counted as rooms.
- Clinic: roof spaces such as 2R02 (589 m2) count as rooms, and 3R01-04 are asked about.
- Tuwien UG1: Garage overlaps Stellplatz. Smiley 1.OG: 7 overlapping pairs.

Conclusion (ESTIMATE): the labels have no random noise. They have systematic convention noise. A reference
is the generator's answer, even where an architect would give another answer.

### Question 7. Cost

Script: `11_cost.py` (`out/cost.jsonl`). Machine: 14-CPU arm64 Mac.

MEASURED:

| File | Size | Open | Geometry | Peak RSS |
|---|---|---|---|---|
| sixty5_arc | 343 MB | 2.9 s (6.9 s in the inventory run) | 6.5 s for 8,109 elements | 2.1-2.4 GB |
| sixty5_plumbing | 222 MB | 2.4 s | - | 1.3 GB |
| barlad | 85 MB | 0.98 s | 1.15 s | 610 MB |
| fzk | small | 0.65 s total | - | - |

- The full probe over 84 paths: 28.6 s wall time, 1.9 GB peak RSS.
- Molio: geometry for 252 of 359 elements. The rest have no body representation.

ESTIMATE: one question costs under 1 s for most models and under 12 s for the largest. Opening each IFC
once and caching the parsed model per request is enough. Memory is the limit on a small container: give
it at least 3 GB.

## Shortcuts that work on the public set

Script: `12_shortcuts.py` (`out/shortcuts.json`). MEASURED, leave-one-out, twins removed:

- Same-name room copy: 409 of 1,183 room items (34.6%).
- Family mode per model: area_room 14.0%, area_total_storey 45.0%, count_storey 11.6%, slab volume
  19.4%, wall length 18.8%.
- A language twin gives the answer for free when a row-level split puts the twins on both sides: 2,726
  of 3,062 rows have one.

## Risks for the hidden test set

1. **The hidden set may use another generator convention or models without Qto.** On public data the rule
   "Qto first, then geometry" is right. On a model with no Qto, geometry gives 47-69% for volume and length
   (MEASURED). If the hidden set has volume questions on such models, expect a large drop (ESTIMATE).
2. **Counting what is drawn fails on convention rows.** Duplicate spaces, nested stairs and walls that are
   assigned to a storey but not drawn all score against a visual counter (MEASURED on public rows). A
   vision model will look worse than its real skill on these rows.
3. **ifc_bench answers are public.** A strong public score can come from memorised IFC-Bench data. If the
   hidden set uses the 206 public rows on the 6 missing models, the answers are on the internet (READ,
   ESTIMATE that they are used). If Stoa writes new questions, the public score does not predict the
   hidden score.
4. **The hidden set may use the modalities with no public questions.** These are the ResBIM PNG rasters
   (no scale bar, dimensions in mm), the elevations and sections (heights and levels), and the 5 ifc_bench
   files with no questions (ESTIMATE). Our vector-PDF path does not transfer to a raster.
5. **Twins and language variants.** A row-level random split overstates accuracy (MEASURED: 2,726 rows
   with a twin). Hidden questions in a new language would also test the parser (ESTIMATE).
6. **The SVG leaks the answer when it is given.** `class` and `data-guid` tags give the element class
   directly, but only on some sheets (MEASURED). A method that depends on the tags breaks on an SVG without
   them, or on a PDF.
7. **Parse failures.** `dental_clinic_mep.ifc` does not parse in IfcOpenShell 0.9.0 (MEASURED). A hidden
   question on it needs a fallback, for example a lenient STEP reader or a PDF path.
8. **Sheet artifacts.** Rotated plans, spaces placed far away from the building and overlapping labels
   (READ, by eye) break simple layout rules. They did not break the polygon method on the public sheets,
   except gymzaal.
9. **Scoring mismatch.** IFC-Bench is scored by an LLM judge that also checks abstention and transparency
   (READ). A terse correct number can fail the transparency criterion (ESTIMATE). A deterministic scorer and
   the judge will rank systems differently.

## Open questions for Stoa

1. Does the hidden test set use the same generator, the same models and the same templates as the public
   ifc_models rows? Or new models?
2. Will hidden questions be asked about models with no Qto sets? If yes, which value is the reference for
   volume and length?
3. Does the hidden set include the 206 public IFC-Bench rows on samuel_macalister, schependomlaan and
   wbdg_office? Will those IFC files be given?
4. Will the ResBIM PNGs, the elevations or the sections get questions? What kind?
5. For a PDF-only question, do we also get the SVG? Do we ever get the IFC?
6. How is ifc_bench scored: the IFC-Bench LLM judge with its rubrics, or exact match?
7. For counts, is the intended answer "assigned to the storey in the model" or "visible on the drawing"?
   Today the references follow the model.
8. What should a solver do with duplicate spaces (gymzaal, duplex MEP) and roof spaces (clinic)?
9. Is `dental_clinic_mep.ifc` meant to fail to parse, or is it a defect in the copy?
