# cubicasa5k: data research

Source: `stoa/data/junction-dataset/data/cubicasa5k/` (4,787 PNG files, 85,514 count questions).
Date: 2026-11-13. Scripts: `stoa/analysis/cubicasa/*.py` (PEP 723, run with `uv run <script>.py`).
Outputs: `stoa/analysis/cubicasa/out/` (git ignores it: it holds derived answers under NC licences).

Labels: **[M]** = measured by a script named in the line. **[R]** = read in a source. **[E]** = my estimate.
**[V]** = I looked at the image (Read tool); small n, a judgement.

## Findings that change decisions

1. **The public cubicasa5k answers are 100% leaked.** Every Stoa PNG is byte-identical to `F1_original.png` of
   the public CubiCasa5K plan with the same group and id (4,787 of 4,787) [M, `image_identity.py`]. The public
   `model.svg` reproduces all 12 templates exactly (100.00% on every plan that has the template, 4,787 plans)
   [M, `count_rules.py`, `sauna_geometry.py`]. A hash lookup plus 12 one-line class counts scores 100% on
   67% of all public questions. Our public cubicasa score therefore tells us nothing about skill unless we
   exclude this path on purpose.
2. **Stoa's generator is "count SVG classes", not "read the drawing".** Each answer is a count of one
   CubiCasa annotation class (table in section 3). So the reference follows the annotator's SVG, including its
   gaps. Example: on the 212 plans where the annotator left every room `Space Undefined`, the bedroom answer is
   always 0 [M, `undefined_rooms.py`], even where the image shows MH1, MH2, MH3 [V: colorful-2571, colorful-2570,
   high_quality_architectural-2573, high_quality_architectural-2565].
3. **Stoa drops a question when the annotation is ambiguous for that template.** Rule found [M,
   `presence_rules.py`, `presence_check.py`]: doors are asked only if the SVG has no `Door None`
   (open doorway), `Door RollUp` or `Door ParallelSlide` (100.00% agreement on 4,787 plans). Bedrooms are not
   asked if a generic room `Space Room` ("H") or a `Space UserDefined` room exists (99.52%). Balconies are not
   asked if a generic `Space Outdoor` exists (100.00%). Sinks are not asked if a `WaterTap` exists, toilets if a `Urinal` exists (both 100.00%).
   Showers plus bathtubs are not asked if a shower overlaps a bathtub or a Jacuzzi exists (98.27%). Kitchens are
   not asked if a stove stands outside a kitchen room (99.67%). Every room template is skipped on all 1,168
   plans with a `Space UserDefined` room. **Consequence: the public set contains only the easy, unambiguous
   cases. The hard cases (open doorways, a shower in a bathtub, a room marked "H" or "MH/TYÖH") were removed.
   The host's "much harder hidden set" can be exactly these.**
4. **The 213 public CubiCasa5K plans that Stoa did not use are the most likely cubicasa part of a hidden set.**
   Public total 5,000; Stoa uses 4,787; 213 are missing (182 train, 18 val, 13 test split) [M,
   `svg_features.py`]. All 6 public plans whose `F2`/`F3` image differs from `F1` are among the 213 [M]. No other
   defect separates the 213 from the rest (no parse errors, similar floor counts) [M, `excluded_213.py`]. Their
   SVGs are public too, so a lookup would also "work" on them. We must not use it, and we should tell Stoa.
5. **Use the public split for an honest evaluation.** Stoa's plans sit in CubiCasa5K train 4,018, val 382,
   test 387 [M]. Any model pretrained on CubiCasa5K train (including the official CubiCasa model) has seen the
   labels of 84% of Stoa's plans. Evaluate cubicasa only on the 769 val+test plans (13,538 questions [M])
   and train only on train-split plans.
6. **Windows and doors decide most of the vision score.** They are 19.4% of cubicasa questions (9,574 + 7,038
   rows) with a mode guess of 13.6% and 11.6% [M, `templates.py`]. In my informal probe I scored 1/8 on windows
   and 2/5 on doors, but 100% on rooms, toilets, sinks and floors (59/72 overall) [V, n=8 plans]. The room and
   fixture templates are easy for a frontier vision model. Counting small symbols on large or low-resolution
   plans is not. A symbol detector trained on CubiCasa5K train SVGs is the obvious cheap component.
7. **English and Finnish twins always agree.** 12 pairs, 42,757 file-template pairs, 0 disagreements, and each
   file has either both or neither [M, `templates.py`]. Answer once per pair; it halves the cost.
8. **Label noise is low in random checks but systematic in one place.** Random audit: 0 clear errors in about
   57 answers on 5 random drawings [V]. Systematic error: bedrooms = 0 on the 212 untyped plans. 4 of 8 that I
   looked at clearly show MH rooms; the other 4 have no room labels [V]. Estimate: about 100 wrong bedroom
   answers (about 3.5% of 2,960) [E], and under 1% wrong answers across all cubicasa questions [E].

## Evidence

### 1. Images

Measured with `templates.py` (writes `out/images.json`) [M]:

| group | files | mode | width median (p10-p90, max) | height median | file size median |
|---|---|---|---|---|---|
| high_quality_architectural | 3,578 | RGB 3,159, RGBA 409, L 10 | 779 px (422-1,601, max 7,896) | 707 px | 293 KB |
| high_quality | 943 | RGB 840, RGBA 100, L 3 | 731 px (449-1,528, max 4,345) | 647 px | 151 KB |
| colorful | 266 | RGB 246, RGBA 20 | 719 px (388-1,680, max 6,768) | 698 px | 248 KB |

- No file has a DPI tag [M]. Smallest: colorful-11960, 240 x 161 px; largest: high_quality_architectural-1269,
  7,896 x 4,960 px [M]. Many plans are small: 10% are under about 430 px wide [M].
- Questions per file: 6 to 24 (always even, because of the pairs) [M].
- Duplicates: 19 pairs of byte-identical PNGs under two ids; their 168 shared questions never conflict [M,
  `out/duplicates.json`].

What a person sees (33 files viewed: 8 colorful, 7 high_quality, 18 high_quality_architectural) [V]:

- **high_quality_architectural**: architect CAD sheets and scans. Thin lines, dimension chains (for example
  10200, 13000), room areas in m², door codes, level marks (+108.382), hatching, furniture. Often a crop of a
  larger sheet with neighbour units at the edge (high_quality_architectural-9175, -710, -11743, -1). Screen
  captures with UI debris ("Activate Windows", PDF viewer toolbar "Automatic Zoom"), handwriting, highlighter,
  a pink sticky note (high_quality_architectural-7511, -12428).
- **high_quality**: clean real-estate marketing plans in black, grey or one brand colour (green, red, blue
  walls). Short Finnish labels: MH, OH, K, KH, KPH, PH, WC, VH, ET, S, PARVEKE. Agency logos (virtualdesign.fi,
  CUBICASA, ERKKERI). Some are faint scans with pen marks (high_quality-10004).
- **colorful**: rendered plans with colour fills, floor textures, furniture, plants; some 3D-like renders
  (colorful-2571, -2570) with m² per room.
- **Rotation**: text runs sideways or upside down in 13 of 33 viewed files [V]. OCR must handle 90° and 180°.
- **Scale**: dimension chains appear on many architectural sheets. Marketing plans often say "ei
  mittakaavassa" / "suuntaa antava" (not to scale): seen on 5 of 33 [V]. No scale bars seen. An area question on
  these needs "I do not know" unless room m² labels are printed.
- **Multi-storey sheets**: floors appear side by side on one image (1.krs, 2.krs, kellari). 963 plans have
  2-4 floors [M]. In the public zip, 1,165 of 1,171 extra floor images (`F2`-`F4_original.png`) are byte copies of `F1` [M, zip CRC], so one image shows all floors.

### 2. Templates

All 24 question texts are in `out/template_texts.txt` [M]. 12 English and Finnish pairs. Table from
`templates.py` (`out/templates.json`), counts per language [M]:

| template | questions | mode (accuracy) | share of 0 | range | mean | most common answers |
|---|---|---|---|---|---|---|
| windows | 4,787 x2 | 4 (13.6%) | 0.5% | 0-92 | 8.78 | 4:650, 3:515, 5:514, 6:377 |
| floors | 4,787 x2 | 1 (79.9%) | 0.0% | 1-4 | 1.23 | 1:3824, 2:827, 3:132, 4:4 |
| toilets | 4,782 x2 | 1 (60.4%) | 3.7% | 0-20 | 1.39 | 1:2890, 2:1479, 3:178, 0:175 |
| sinks | 4,725 x2 | 2 (51.0%) | 2.1% | 0-30 | 2.61 | 2:2409, 3:1281, 4:523, 1:165 |
| showers_tubs | 4,442 x2 | 1 (76.2%) | 6.3% | 0-22 | 1.19 | 1:3386, 2:532, 0:279, 3:182 |
| doors | 3,519 x2 | 6 (11.6%) | 0.1% | 0-43 | 8.74 | 6:408, 7:404, 5:361, 8:320 |
| saunas | 3,315 x2 | 1 (56.9%) | 42.6% | 0-2 | 0.58 | 1:1887, 0:1412, 2:16 |
| kitchens | 3,262 x2 | 1 (95.8%) | 2.0% | 0-4 | 1.00 | 1:3126, 2:69, 0:65, 4:2 |
| bedrooms | 2,960 x2 | 1 (31.1%) | 17.4% | 0-9 | 1.66 | 1:920, 2:815, 3:526, 0:516 |
| bathrooms | 2,384 x2 | 1 (88.6%) | 6.5% | 0-4 | 0.99 | 1:2112, 0:156, 2:108, 3:5 |
| wc_rooms | 2,332 x2 | 0 (55.6%) | 55.6% | 0-7 | 0.53 | 0:1297, 1:848, 2:173, 3:9 |
| balconies | 1,462 x2 | 0 (51.0%) | 51.0% | 0-3 | 0.50 | 0:745, 1:704, 2:12, 3:1 |

Mode guess per template over all rows: 55.32% [M].

**Why templates are missing (the filter rule).** `presence_rules.py` ranks SVG classes that predict a missing
template; `presence_geometry.py` adds "fixture in room class" tokens; `presence_check.py` scores explicit rules
over all 4,787 plans [M]:

| template | asked when ... | agreement |
|---|---|---|
| doors | no `Door None Beside`, `Door RollUp Beside`, `Door ParallelSlide Beside` | 100.00% |
| balconies | no `Space UserDefined`, no generic `Space Outdoor` | 100.00% |
| sinks | no `FixedFurniture WaterTap` | 100.00% |
| kitchens | no `Space UserDefined`, every `IntegratedStove` inside a `Space Kitchen*` | 99.67% |
| bedrooms | no `Space UserDefined`, no `Space Room` | 99.52% (23 asked anyway) |
| saunas | no `Space UserDefined`, no `SaunaStove Round`, sauna benches inside an undefined or sauna room | 98.45% |
| showers_tubs | no `Jacuzzi`, no shower that overlaps a bathtub | 98.27% |
| bathrooms | no `Space UserDefined`, showers and bathtubs inside `Space Bath*`, no generic `SaunaBench` | 93.13% |
| wc_rooms | no `Space UserDefined`, every toilet inside `Space Bath*`, no generic `SaunaBench` | 92.06% |
| windows, floors | always asked | - |
| toilets | no `FixedFurniture Urinal` (the 5 skipped plans are exactly the 5 with a urinal) | 100.00% |

Reading: Stoa asks a template only when its SVG count is unambiguous. Doors are missing on 1,268 plans because
1,065 of them contain an open doorway (`Door None`) and the rest a garage or parallel-slide door [M]. The
question text "open doorways without a door leaf do not count" is therefore never tested in the public set.

### 3. Label origin: rules that reproduce Stoa's answers

Download: Zenodo 2613548 `cubicasa5k.zip` (5.47 GB, CC BY-NC-SA 4.0 per Zenodo metadata [R]) into
`stoa/data/external/cubicasa5k/` (git ignores it; `SOURCE.md` there records the licence). Extraction:
`fetch_public_svgs.py --local`. Features: `svg_features.py`. Rules: `count_rules.py`, `sauna_geometry.py`.
Mapping: Stoa `<group>-<id>.png` = public `<group>/<id>/F1_original.png`, for all 4,787 [M].

Agreement on every plan that has the template (not a sample) [M]:

| template | rule (count of SVG elements) | agreement | nearest wrong variant |
|---|---|---|---|
| floors | number of `Floorplan` groups (basements count) | 100.00% | without basements 99.02% |
| windows | all `Window *` (Regular, Sauna, Full) | 100.00% | Regular only 99.37% |
| doors | all `Door *` (Swing Beside/Opposite, Slide, Zfold, Fold; one per element, so a double door = 1) | 100.00% | swing only 84.60%; per leaf 0.06% |
| toilets | `FixedFurniture Toilet` (plans with a urinal are skipped) | 100.00% | - |
| sinks | Sink + RoundSink + DoubleSink + DoubleSinkRight + SideSink + CornerSink, double = 1 | 100.00% | double = 2: 35.39% |
| showers_tubs | `Shower` + `Bathtub` + `BathtubRound` (`ShowerCab`, `ShowerPlatform`, `ShowerScreen` not counted) | 100.00% | with ShowerCab 94.55% |
| saunas | number of distinct rooms that hold a sauna stove, union with `Space Sauna` rooms | 100.00% | stove count 98.46%; `Space Sauna` 44.86% |
| bedrooms | `Space Bedroom*` | 100.00% | - |
| kitchens | `Space Kitchen*` (incl. Kitchenette, Open, Scullery) | 100.00% | without Scullery 98.47% |
| bathrooms | `Space Bath` not labelled WC + `Space Bath Shower` | 100.00% | all Space Bath 57.21% |
| wc_rooms | `Space Bath` labelled WC | 100.00% | - |
| balconies | `Space Outdoor Balcony*` (incl. Glazed, Covered) | 100.00% | with terraces 84.54% |

No template stays under 95%. There are no disagreements to show, so the useful check is the reverse: where
does the SVG convention differ from what a person reads in the image?

- `ShowerCab` (239 elements) is not a shower for Stoa, but a person counts a shower cabin as a shower [M, E].
- Saunas: 1,824 of the stove rooms are `Space Undefined` [M]. The sauna count comes from stove geometry, not
  from the "S" or "SAUNA" label.
- Bedrooms: a room labelled "H" (huone) is `Space Room`, never a bedroom; those plans are dropped [M].
- Toilets: a WC room without a drawn toilet symbol counts 0 (colorful-12872: three WC rooms, toilets = 0) [V].
  This follows the question text ("drawn").
- Scope: the SVG covers the whole image, including partial neighbour units (high_quality_architectural-9175:
  doors 11, windows 7 for a sheet that centres on one flat) [V].

### 4. Leakage map

From `svg_features.py` (`out/public_ids.json`) [M]:

| public split | in Stoa | not in Stoa |
|---|---|---|
| train | 4,018 | 182 |
| val | 382 | 18 |
| test | 387 | 13 |
| total | 4,787 | 213 |

Not in Stoa by group: high_quality_architectural 154, high_quality 49, colorful 10 [M]. The 213 are
candidates for clean training data and for the hidden test set (finding 4). File names keep the public id, so
the mapping needs no image matching.

### 5. Label noise

- Random audit, 5 drawings chosen with seed 99 (`out/audit_sample.json`), about 57 answers [V]:
  high_quality_architectural-2030 (12/12 correct), -11122 (rooms, fixtures, floors correct; doors 13 and
  windows 14 plausible but not countable with certainty), -10581 (all plausible), -11743 (all plausible),
  -357 (716 x 862 px house plan: doors 21 and windows 22 not verifiable; bedrooms 0 doubtful, no labels legible).
  Clear errors: 0. Not verifiable by eye: about 8.
- Review of the 13 disagreements in the probe (section 6) [V]: the reference looks right in 9 (my counting was
  wrong, for example "S/VH" is a sauna), ambiguous in 4 (high_quality_architectural-14050 windows 0 next to a
  glazed balcony wall; -9175 includes the neighbour unit; -7731 showers; -11612 low-quality scan).
- Targeted check of untyped plans (all rooms `Space Undefined`, bedrooms = 0): 8 viewed, 4 clearly wrong
  (MH labels visible), 4 without room labels where 0 is defensible [V].
- Totals: 40+ answers checked in random samples with 0 clear errors [V]; one systematic error class (212
  bedroom answers, about half wrong [E]).

### 6. Informal probe (frontier vision model, PNG only)

INFORMAL, n = 8 random drawings (seed 2026), 72 answers. I wrote my answers to `out/probe_my_answers.json`
before I read the reference [V]:

| template | exact | template | exact |
|---|---|---|---|
| windows | 1/8 | toilets | 8/8 |
| doors | 2/5 | sinks | 8/8 |
| showers_tubs | 6/8 | floors | 8/8 |
| saunas | 5/6 | bedrooms | 5/5 |
| kitchens | 6/6 | bathrooms | 3/3 |
| balconies | 4/4 | wc_rooms | 3/3 |

Overall 59/72 = 82% [V]. My window counts were off by 1 to 10 on plans with 10+ windows.

### 7. English and Finnish pairs

Same answer in 42,757 of 42,757 file-template pairs; no file has only one language of a pair [M,
`templates.py`, `out/templates.json` key `pairs`].

## Scripts

| script | produces |
|---|---|
| `templates.py` | template census, pairs, presence, image stats |
| `list_public_zip.py` | listing of the public zip by HTTP range requests (Zenodo rate-limits parallel requests) |
| `fetch_public_svgs.py --local` | `model.svg` and split lists from the downloaded zip |
| `svg_features.py` | per-plan SVG class counts, labels, split; public id map |
| `image_identity.py` | byte identity of Stoa PNG vs public images |
| `count_rules.py`, `sauna_geometry.py` | rule agreement per template |
| `presence_rules.py`, `presence_geometry.py`, `presence_check.py` | the filter rule |
| `undefined_rooms.py` | answers on plans with only undefined rooms |
| `excluded_213.py`, `svg_png_alignment.py` | the 213 left-out plans (alignment test was inconclusive: SVG canvas size is not the image size) |

## Risks for the hidden test set

- **Leak-shaped success.** Anything that touches CubiCasa5K labels (lookup, a pretrained CubiCasa model, a
  detector trained on all 5,000 SVGs) inflates the public score. Judges will ask. Keep a leak-free run as the
  reported number.
- **The ambiguous cases are absent from the public set** (open doorways, shower over bathtub, "H" rooms,
  user-defined rooms, garage doors). A hidden set that keeps them will test conventions that the public set never
  shows. Follow the question text literally and state the convention in the answer.
- **Generator convention vs drawing.** Stoa's hidden answers likely come from the same SVG counts. Where SVG and
  image differ (ShowerCab not counted, untyped rooms count 0, neighbour units counted), a correct reading of the
  drawing loses points. We cannot fix this; we can report confidence and say which convention we used.
- **The 213 plans** are the obvious cubicasa holdout. They look like the public set, so a good public-like
  solver transfers; the harder part of the hidden set is more likely other sources.
- **Windows and doors on large or low-resolution sheets.** Many plans are under 500 px wide, or show 3 storeys on
  one sheet with 20 to 90 windows. Exact counts there are fragile; one miss fails the question.
- **Rotated and cropped scans** with UI debris and neighbour units need rotation-aware OCR and a scope decision.

## Open questions for Stoa

1. Is the hidden cubicasa part drawn from the 213 CubiCasa5K plans that the public set leaves out?
2. Are hidden answers generated by the same SVG-count rules? If not, which convention wins: the drawing or the
   annotation (for example a shower cabin, an unlabelled bedroom, a partial neighbour flat)?
3. Does the hidden set keep the ambiguous cases that the public generator drops (open doorways, a shower in a
   bathtub, rooms marked H)? If yes, may we answer "ambiguous" with an explanation?
4. May we train on CubiCasa5K train-split SVGs? They contain the labels of 84% of the public Stoa plans.
5. How is "I do not know" scored on a count question?
