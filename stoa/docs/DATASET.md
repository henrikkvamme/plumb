# The dataset, and how a public-set score misleads

Digest of five data reports in `stoa/docs/research/data/`, written 2026-11-14. Each figure has a tag and a report.

- **[M]** MEASURED: a script in `stoa/analysis/` printed it. **[S]** SOURCED: a paper, a licence file or the host said it.
  **[E]** ESTIMATE: a judgement. Counts that an agent made by eye on a small sample are [E] here.
- Reports: `cubicasa.md`, `swiss.md`, `ifc.md`, `wild.md`, `questions.md`. Host facts: `stoa/docs/HOST.md` (#n = row).
- The reports have no verifier section. The checks behind this digest are: three re-runs by the lead (marked
  "lead re-ran"), and the figures that I measured again (marked "digest check", listed in section 8).

## 1. In short

1. The public score is mostly a score on two clean, generated sources. cubicasa5k is 67.3% of the rows and
   swiss_dwellings is 29.6% [M]. Both have public originals that hold the answers.
2. A solver that opens no drawing scores 55.3% on cubicasa5k and 41.7% on the micro average [M]. A lookup in
   public data scores about 100% on cubicasa5k, swiss counts and ifc_bench [M]. None of this is skill.
3. The references follow the generator, not the drawing. Example: the Swiss door count equals what a person
   counts on only 74 of 1,040 floors [M]. The public set also drops the ambiguous cases and never asks for "none".
4. 8,611 of 14,550 drawings have no question: all 6,566 historic scans, 984 opening_design drawings, 500 ResBIM
   models [M]. The host said that the hidden set is "much more difficult" and has "tricky drawings" [S, #1, #2].
5. Rule for our work: a solver reads only the one file that the question names. It does not read the file name
   as a key, a sibling format, `LICENSE.md`, `data/external/` or other answers. Section 6 has the exact list.
6. Split by building, not by row. Report one row per translation pair, per (source, task) cell, next to the
   no-drawing prior. There are 64,132 independent items, not 127,044 [M, digest check].
7. No dataset file goes into the repository. Section 7 has the licence of each source and each download.

## 2. What we got

Totals: 16,891 files, 14,550 drawings (file stems), 5,939 drawings with questions (40.8%), 127,044 questions
[M, `wild/coverage.py`; digest check on files and rows]. The dataset README says "about 14,000", "about 120,000"
and "about 30 languages" [S]. The questions use 11 languages [M, questions.md].

| source | files and formats | drawings: all / with questions | questions | types | question languages | origin and licence |
|---|---|---|---|---|---|---|
| cubicasa5k | 4,787 PNG | 4,787 / 4,787 | 85,514 | count | en, fi (42,757 each) | CubiCasa5K, Zenodo 2613548, CC BY-NC-SA 4.0 [S] |
| swiss_dwellings | 1,040 each of PDF, DXF, PNG | 1,040 / 1,040 | 37,584, all on the PDF path | count 25,568, area 12,016 | en 18,792, de 12,620, fr 4,461, it 1,711 | drawn by Stoa from Swiss Dwellings v3.0.0, Zenodo 7788422, CC BY 4.0 [S] |
| ifc_models | 533 IFC (500 are ResBIM), 107 PDF, 107 SVG, 500 PNG | 1,140 / 84 (69 PDF, 15 IFC) | 3,062 (2,694 on PDF, 368 on IFC) | count 642, area 2,218, volume 138, length 64 | en 1,699, de 318, et 315, nl 281, da 197, es 196, pl 38, ro 14, it 4 | open IFC models, licence per file; sheets rendered by Stoa with IfcOpenShell [S] |
| ifc_bench | 30 IFC | 30 / 25 | 820 | text | en | IFC-Bench v2 (Hugging Face), CC BY 4.0, 4 models GPLv3 [S] |
| opening_design | 678 PDF, 271 DWG, 48 IFC, 9 DXF, in 39 projects | 987 / 3 | 64 | count 39, text 16, area 9 (ft2) | en | OpeningDesign GitHub, CC BY-SA 4.0 (989 files), MIT (17) [S] |
| habs | 1,506 JPG | 1,506 / 0 | 0 | - | sheets: en [E, by eye] | Library of Congress, public domain [S] |
| finna | 1,800 JPG | 1,800 / 0 | 0 | - | sheets: sv, fi [E, by eye] | Helsinki City Archives, CC BY 4.0 [S] |
| europeana | 1,085 JPG | 1,085 / 0 | 0 | - | sheets: 11+ languages [E, by eye, n=30] | per file: PDM 487, CC BY 176, CC BY-NC 113, CC0 93, BY-NC-SA 87, other [M] |
| wikimedia | 2,175 JPG, 135 SVG | 2,175 / 0 | 0 | - | sheets: de, fr, en, sv, ru [E, by eye, n=30] | Commons, file list from WAFFLE; PDM 1,207, BY-SA 4.0 449, other [M] |

All counts [M]: `wild/coverage.py`, `questions/templates.py`, `wild/meta_lookup.py`, and the digest check.

Facts per source that change a decision:

- **cubicasa5k.** Finnish real-estate plans, median width 719 to 779 px by group, 10% under about 430 px, no DPI tag [M].
  963 plans show 2 to 4 floors on one image [M]. Text runs sideways or upside down in 13 of 33 viewed files
  [E, by eye]. 19 pairs of PNGs are byte-identical under two ids; their answers never conflict [M]. (cubicasa.md)
- **swiss_dwellings.** One generated A3 sheet per floor, Matplotlib output, vector only, 1:100 on 863 sheets and
  1:200 on 177 [M]. One floor per site: 1,040 floors, 1,040 sites [M]. The sheet says that the label language
  and numbering are synthetic [S, LICENSE.md and PDF footer]. Nothing looks like a scan. (swiss.md)
- **ifc_models.** 62 parsed files that are not ResBIM, in both IFC sources (IFC2X3 31, IFC4 29, IFC4X3 2), plus 500 ResBIM models with no `IfcSpace` and no
  Qto [M]. 107 sheets: 71 plans, 24 elevations, 12 sections [M]. `dental_clinic_mep.ifc` (ifc_bench) does not
  parse in IfcOpenShell 0.9.0 [M]. 8 IFC files are byte-identical in ifc_models and ifc_bench [M]. (ifc.md)
- **opening_design.** Real US drawing sets: 2,741 PDF pages, 74 PDFs with no text layer, feet and inches [M].
  43 sheet codes exist in 2 to 6 revisions [M]. The 64 questions are hand-written and sit on 3 sheets. (wild.md)
- **Historic scans.** Small and damaged: europeana median 1.26 MP with 237 files under 1,000 px; wikimedia median
  2.07 MP with 579 under 1,000 px [M]. In 120 scans viewed, 5 are not drawings and 3 are maps [E, by eye]. (wild.md)

## 3. How the questions were made

**Templates.** 966 templates in total: cubicasa5k 24, swiss_dwellings 48, ifc_models 129, ifc_bench 701,
opening_design 64 [M, questions.md, `templates.json`]. A family is an English template plus its translations:
12 for cubicasa5k, 12 for swiss_dwellings, 21 for ifc_models. ifc_bench and opening_design are free text.

**Translation pairs.** 62,910 translation groups. The answers are equal in every language of every group: 0
violations [M, `questions/consistency.py`]. Each cubicasa5k and swiss file has both languages of a pair or
neither [M]. ifc_models: 2,726 of 3,062 rows have a twin [M, ifc.md]. Independent items: 42,757 + 18,792 +
1,699 + 820 + 64 = 64,132 [M, digest check]. questions.md says 63,404; see section 8.

**Answer generators.** No answer comes from a person who read the drawing, except in opening_design.

| source | generator | evidence |
|---|---|---|
| cubicasa5k | count of one annotation class in the public CubiCasa5K `model.svg` | 12 rules, 100.00% on every plan that has the template [M, `cubicasa/count_rules.py`, `sauna_geometry.py`]. Lead re-ran on 400 random plans: windows 400/400, doors 289/289, toilets 400/400 |
| swiss_dwellings | the source geometry of Swiss Dwellings v3.0.0, drawn and counted by one program | PDF-only rule parser matches 37,444 of 37,584 (0.9963) [M, `swiss/probe_pdf.py`; lead re-ran] |
| ifc_models | an IfcOpenShell script: Qto value when present, else footprint; `by_type` counts; storey by containment or aggregation | 3,057 of 3,062 rows are matched by at least one candidate rule [M, `ifc/06_probe_summary.py`; lead re-ran] |
| ifc_bench | copy of the public IFC-Bench v2 CSV | 820 of 820 questions and answers identical [M, `ifc/03_bench_leakage.py`; lead re-ran] |
| opening_design | hand-written schedule lookups on 3 sheets | 61 of 64 questions read a table; 3 need a drawing [M, wild.md] |

**Conventions that differ from what a person counts.**

| source | convention | number |
|---|---|---|
| swiss | A door that two units list counts once per unit. The copies are drawn exactly on top of each other. | Reference 31,928 doors, 27,025 distinct on the sheets. Distinct count matches on 74 of 1,040 floors (7.1%); windows on 765 (73.6%) [M, `swiss/duplicates.py`, `door_rule.py`] |
| swiss | Bathtub and shower questions exist only when the answer is at least 1. "Rooms labelled X" is never 0. | 897 and 322 floors; 0 zeros in 12,730 label rows [M; digest check on the minimum] |
| swiss | Floor total = numbered rooms minus outdoor rooms, shafts and voids. Lift and stair are inside. Room area = polygon minus holes. | Variant without the outdoor rule: 23.1% [M, `swiss/probe_dxf.py`] |
| swiss | Apartments = number of "Whg. X" / "App. X" tags. | Outline polygons give 88.4% [M] |
| cubicasa | A template is dropped when the annotation is ambiguous. Doors: dropped when the plan has an open doorway, a roll-up or a parallel-slide door. | Doors missing on 1,268 plans, 1,065 of them with an open doorway; rule agreement 100.00% [M, `cubicasa/presence_check.py`] |
| cubicasa | Bedrooms dropped when a room is "H" (`Space Room`) or user-defined. All room templates dropped on 1,168 plans with a user-defined room. | Agreement 99.52% (bedrooms), 92.06% to 100% for the other rules [M] |
| cubicasa | Double door = 1. Double sink = 1. `ShowerCab` is not a shower. Sauna = room with a stove. Neighbour units on the image count. | Double sink = 2 gives 35.39%; with `ShowerCab` 94.55% [M, `count_rules.py`] |
| cubicasa | Untyped plans (all rooms `Space Undefined`) give bedrooms = 0. | 212 plans [M]; 4 of 8 viewed show bedroom labels [E, by eye] |
| cubicasa | A WC room with no drawn toilet symbol has 0 toilets. | 22 of 2,332 plans [M, `questions/consistency.py`] |
| ifc_models | A count is "elements assigned to the storey in the model", not what the sheet shows. | Gymzaal: 48 rooms (each modelled twice). Molio: 21 walls in the reference, 11 drawn. Molio stairs: reference 2, containment 80 [M, ifc.md] |
| ifc_models | Volume, length and side area come from Qto. All 266 such rows are on the 8 models with Qto. | Geometry matches wall volume 60.6%, slab volume 69.4%, wall length 46.9% [M, `ifc/05_probe_models.py`] |
| ifc_models | A room is asked only when its name is unique on the storey. 176 questions on a plan PDF ask about the whole model. | 176 of 2,694 PDF rows (6.5%) [M] |
| opening_design | A printed total is the answer, also when the rows sum to another value. | 3,672 SF printed, 3,671 by rows; revision A-801: 11 of 16 values differ [M, wild.md] |

Label noise. Random noise is low: 0 violations in 15 hard consistency checks on swiss and ifc_models [M].
The noise is convention noise. Two estimates for wrong cubicasa5k answers disagree: under 1% [E, cubicasa.md]
and 2 to 5% [E, questions.md]. Neither comes from an audit.

## 4. How the public score misleads

| trick | public score it buys | expected on the hidden set |
|---|---|---|
| Prior: most common answer per template, no drawing | 55.3% on cubicasa5k [M, lead re-ran; digest check 55.32%]. Micro 41.7%, macro over sources 14.6%, grouped 2-fold [M, `questions/baselines.py`] | Near 0 on new templates and free text [E] |
| Prior fit on the rows it scores | Micro 43.9%, macro 36.5%; ifc_models 44.2%, opening_design 64.1% [M] | 0 [E] |
| Micro average | cubicasa5k is 67.3% of rows. 10 points more on ifc_models moves the micro average by 0.24 points [M] | The hidden set is small and run by people [S, #9]; the mix is unknown |
| CubiCasa5K lookup: file name = public id, PNG byte-identical (4,787 of 4,787), count SVG classes | 100% on cubicasa5k = 67.3% of all rows [M, `cubicasa/image_identity.py`, `count_rules.py`; lead re-ran] | Works only if Stoa uses the 213 other public plans and keeps the names [E]. Judges will ask |
| A model trained on CubiCasa5K train (also the official model) | It has seen the labels of 4,018 of 4,787 plans (84%) [M]. Score not measured | Unknown; not a leak on new drawings |
| Swiss lookup: site, building and floor id in the file name and title block, then public `geometries.csv` | 100% on 7 count families, 99.5% on floor totals, no drawing opened [M, `swiss/probe_source.py`] | Total leak if the hidden set uses other floors of the same generator; 0 on real drawings [E] |
| Swiss style parser: exact colours, stroke widths, vertex counts | 99.63% of 37,584 in 13 s, no model [M, lead re-ran] | Breaks on real drawings [E] |
| PDF text layer only (`get_text()`) | "Rooms labelled X" 6,364 of 6,365; apartments 1,040 of 1,040; together 39.4% of swiss rows. Printed areas on 307 sheets: 1,216 of 1,224 room areas [M, `questions/probe_swiss_text.py`, `swiss/probe_printed.py`] | 0 on scans: 6,566 historic rasters and 74 opening_design PDFs have no text layer [M] |
| Sibling format: read the DXF (semantic layers, metres) for a PDF question | 98.75%, 99.39% with best variants [M, `swiss/probe_dxf.py`]. From the PNG alone, room area is within 2% for 20.8% [M, `probe_png.py`, 400 questions] | The host gives one document at a time [S, #9]. A sibling may not exist |
| Sibling model: open the IFC for a plan-PDF question; read `class` tags in the SVG | IFC: 3,057 of 3,062 by at least one rule [M]. SVG tags: 238 of 390 storey counts [M, `ifc/07c_svg_counts.py`]. PDF only: room area 1,764 of 1,792 [M] | Depends on what Stoa hands over. PDF-only ceiling about 85 to 90% on this mix [E] |
| ifc_bench public CSV, or a model that saw IFC-Bench | 820 of 820 [M] | 206 more public rows on 6 models are a likely pool [E]; new questions: no transfer |
| Translation twin: copy the other language | 100% on 62,910 groups; each success counts twice [M] | No gain. New languages are likely: 5 of 9 ifc_models languages are new since the preview [M] |
| Row or drawing split with a room-name prior | ifc_models: 29.8% (row split), 29.0% (drawing split), 2.1% (building split) [M]. Same-name room copy: 34.6% of room items [M, `ifc/12_shortcuts.py`] | 0 on a new building |
| One gold answer of another question on the same drawing | sw bathtubs 29.2% to 82.5%; cc toilet bowls 60.4% to 81.8% [M, `baselines.py`] | Small, and only for the same templates [E] |
| Question presence | A bathtub question means at least 1 bathtub; a label question means the label exists [M] | "None" and "cannot be determined" can be asked [S, #6] |
| Copy the generator convention | Swiss doors: stacked copies 100%, distinct doors 7.1% [M] | Unknown which convention Stoa keeps. Ask. State the convention in the answer |
| `LICENSE.md` title and public archive records | Gives 1 of 20 answerable probe answers directly. 4 of 20 probe files disagree with the sheet [E, by eye, wild.md] | Hidden files probably have no row [E]. The file name may not reach us [E] |

The two sources that carry the score, cubicasa5k and swiss_dwellings, are 96.9% of the rows together [M].
What stays hard and honest in the public set: windows and doors on cubicasa5k (mode guess 13.6% and 11.6%,
19.4% of cubicasa rows) [M], and swiss areas from the PNG. An informal probe of a frontier vision model on 8
plans scored windows 1/8 and doors 2/5, and 59/72 overall [E, by eye, n=8, cubicasa.md].

## 5. What the hidden set probably is

What the host said [S, HOST.md]: the hidden set decides most of the score and is much harder (#1). It has
"tricky drawings" with the same extensions and other content (#2). Questions can be compound: find the toilets,
then compute the tile area (#4, #5). "I don't know" answers matter, and a missing scale is a case to solve with
the user (#6, #7). Stoa gives one document at a time, then a series of questions, through our interface (#9).
Most drawings are European and have a scale; some are from the US; scans are "a pain" (#12, #13). A hint was
promised for Saturday at about midday (#15). No new host talk was in `context/stoa-drawings/` when I wrote this.

Scenarios, all [E] from wild.md. The weights are one agent's judgement:

| # | scenario | weight |
|---|---|---|
| A | Harder questions on released files, also on drawings with no public question: multi-step, cross-table, "cannot be determined" | 0.45 [E] |
| B | New held-out files and "tricky drawings": a PDF that is a scan, a PNG of a schedule, a rotated or multi-page set | 0.35 [E] |
| C | Mostly the public templates on cubicasa, swiss and IFC, with harder variants | 0.20 [E] |

In A and B (0.80 together [E]) the public score says little.

Candidate pools that the public set points to:

| pool | size | note |
|---|---|---|
| CubiCasa5K plans not in the dataset | 213 (train 182, val 18, test 13) [M] | Their SVG answers are public. No defect separates them [M, `cubicasa/excluded_213.py`] |
| The dropped ambiguous cubicasa cases | open doorways on 1,065 plans; 1,168 plans with a user-defined room [M] | The public set never tests "open doorways do not count" |
| Swiss floors not in the dataset | 12,865 of 13,905; 3,530 are sibling floors of our buildings; 4,047 are on sites that we never see [M] | A sibling floor has the same door count 43% of the time, against 1.9% for a random floor [M, `swiss/source_siblings.py`] |
| IFC-Bench rows that Stoa did not ship | 206 rows on 6 models [M] | The answers are on the internet |
| ifc_models files with no question | 500 ResBIM models and PNG renders, 24 elevations, 12 sections, 2 plans, 4 digitalhub models [M] | The ResBIM PNG has dimensions in mm and no scale bar [M] |
| opening_design drawings with no question | 984 of 987 [M] | "DOOR SCHEDULE" in 25 PDFs, "WINDOW SCHEDULE" in 8, a finish or room schedule in 60 [M] |
| Historic scans | 6,566 [M] | Scale bar or ratio on 28/30 habs, 24/30 finna, 15/30 europeana, 17/30 wikimedia sheets [E, by eye] |

**The 50 probe questions.** `stoa/docs/research/data/wild-probe-questions.jsonl`, written and checked by eye by
one agent. They are our only labelled rows on these sources. 25 rows on 7 opening_design sheets in 5 projects:
14 count, 7 area (ft2), 1 length (ft), 3 text. 25 rows on historic scans: habs 7, finna 6, europeana 6,
wikimedia 6; 9 count, 7 text, 4 length, 5 "cannot be determined". Traps on purpose: the archive revision of
A-801 (41 doors, not 38), rounded totals (3,672 against 3,671), duplicate door numbers (46 rows, 43 distinct),
a camera photo with "Original 1:100" printed on it, a cover sheet with no plan. The answers are [E, by eye]:
no second person checked them. The no-answer form is "cannot be determined - <reason>". Stoa's form is unknown.

## 6. Rules for our own work (data side)

**A solver may read only the file that the question names (`path`), and the question text.** It may not read:

1. `stoa/data/junction-dataset/questions.jsonl`, and any file derived from it: `stoa/analysis/**/out/`,
   `stoa/docs/research/data/templates.json` (answer distributions), few-shot rows from the split that it scores.
2. `stoa/data/external/cubicasa5k/` (`cubicasa5k.zip`, `svg/`, `splits/`) and any other copy of a CubiCasa5K
   `model.svg`. Also: a model whose weights were trained on CubiCasa5K, unless the report says so (rule 9).
3. `stoa/data/external/swiss-dwellings-v3/` (`geometries.csv`) and `stoa/data/external/swiss-derived/`
   (`source_rows.csv`, `probe_*.json`, `rows.json`, `leakage_map.json` and the rest).
4. `stoa/data/external/ifc-bench/ifc-bench-v2.csv` and `eval-split-hellin2026.csv`, and the Hugging Face set.
5. `data/<source>/LICENSE.md`: title, credit and record URL of each file. Also the public records behind them
   (loc.gov, finna.fi, Europeana, Commons) and the WAFFLE labels for wikimedia.
6. The file name and the folder as a key: `<group>-<id>.png` (CubiCasa5K id), `site{S}_bldg{B}_floor{F}` (Swiss
   ids), `<model>_plan-NN-<storey>` (IFC model and storey), opening_design folder names (`_Archive`, dates,
   "Current Set"). The harness should hand the solver a file with a neutral name.
7. The Swiss title block as a database key ("Site 3387 · Gebäude 5238", "Plan-Nr. 5238-23498"). Reading the
   scale and the plan name from the title block is allowed.
8. A sibling of the file: the same stem with another extension (swiss `.dxf` and `.png` for a `.pdf`
   question; ifc_models `.svg` and `.ifc` for a plan-PDF question), the 8 byte-identical IFC copies in the
   other IFC source, and another revision of the same sheet code in opening_design.
9. Answers of other questions on the same drawing, and the answer of the other language of a pair.

A run that breaks one of these on purpose (for example "PDF plus DXF sibling") is a separate, named track.

**How to split.** Never by row.

- cubicasa5k: group by plan id. Keep the 19 byte-identical PNG pairs on one side. When any component was
  trained on CubiCasa5K, score only the 769 plans of the public val and test split (13,538 questions) [M].
- swiss_dwellings: group by `site_id`. The public set is site-disjoint already. The key matters when we add
  source floors or synthetic sheets from the same generator.
- ifc_models and ifc_bench: one group per project, across both sources. 7 projects have questions in both [M].
- opening_design: group by project folder. There are 2 groups, so report an interval, not a point.
- A manifest exists: `stoa/analysis/questions/split_v0.json`, dev 76,414 / val 25,388 / test 25,242 rows [M].
  It splits cubicasa5k by its own hash and not by the public CubiCasa5K split. The two reports differ here:
  questions.md uses the manifest, cubicasa.md asks for the public split. Both hold when rule 2 is kept.

**What to report with each score.**

- The (source, task) cell, never the micro average alone. One row per translation group.
- The no-drawing prior for the same cell, next to the accuracy.
- Which file the solver read (PDF, PNG, DXF, IFC) and which leak rule, if any, the run broke.
- The convention used where two exist (stacked or distinct doors, printed total or row sum, Qto or geometry).
- The abstention rate. The public set has no "none" case for swiss bathtubs, showers and labels.
- For ifc_models (16 groups) and opening_design (2 groups): the number of groups.

The evaluation design itself is in `stoa/docs/EVALUATION.md`. The three designs behind it are in `stoa/docs/research/eval/`.

## 7. Licences

The licence column is [S] from each `LICENSE.md`, the dataset README and the records that the reports name. The
"may we" columns are my reading [E], not legal advice. NC = non-commercial only. SA = a shared adaptation
keeps the licence. ND = no adaptation. Keep the credit line of `LICENSE.md` with each drawing that we show.
Whether trained weights are an "adaptation" under SA or ND is not settled; the table takes the careful side.

| source or download | licence | show in the video | train on it | commit it |
|---|---|---|---|---|
| cubicasa5k (dataset) | CC BY-NC-SA 4.0 (GitHub says CC BY-NC 4.0; Stoa applies the stricter) | yes, with credit, NC | yes, NC; share weights under the same terms | no |
| swiss_dwellings (dataset) | CC BY 4.0, derived work by Stoa | yes, with credit | yes | no |
| ifc_models | per file: MIT (DigitalHub, ResBIM and others), KIT "unrestricted use" with citation, CC BY-ND 3.0 (Duplex, Clinic) | yes, with credit; Duplex and Clinic only unchanged | yes; not for Duplex and Clinic if weights are shared | no |
| ifc_bench | questions CC BY 4.0 (Hellin); models per file; 4 models GPLv3 (4351, ettenheim_gis, hitos, samuel_macalister) | yes, with credit | yes; the answers are public, so say so | no |
| opening_design | CC BY-SA 4.0 (989), MIT (17) | yes, with credit; SA | yes; SA | no |
| habs | public domain | yes | yes | no |
| finna | CC BY 4.0 | yes, with credit | yes | no |
| europeana | per file: PDM 487, CC BY 176, CC BY-NC 113, CC0 93, BY-NC-SA 87, other | check the row of the file | check the row; NC and SA rows as above | no |
| wikimedia | per file: PDM 1,207, CC BY-SA 4.0 449, other | check the row of the file | check the row | no |
| download: `external/cubicasa5k/cubicasa5k.zip` (5.47 GB, Zenodo 2613548) | CC BY-NC-SA 4.0 | yes, with credit, NC | train split only, and report it (section 6) | no |
| download: `external/swiss-dwellings-v3/` (932 MB zip, Zenodo 7788422) | CC BY 4.0 | yes, with credit | allowed by licence; a leak for evaluation | no |
| download: `external/ifc-bench/` (CSV, split, README, paper arXiv 2605.01698; 896 KB) | CC BY 4.0 for the data; paper licence not recorded | yes, with credit | a leak for evaluation | no |
| derived: `external/swiss-derived/` (99 MB), `analysis/**/out/` | as the source they come from | - | - | no |

`stoa/.gitignore` ignores `/data/` and `analysis/**/out/` [M, digest check]. Two tracked files hold text derived
from the dataset: `stoa/docs/research/data/templates.json` (question templates, example questions, answer
distributions) and `stoa/analysis/questions/split_v0.json` (file ids). They hold no drawing. Questions inherit
the licence of their drawing [S, dataset README], so a person must decide whether these two files stay tracked.
Not downloaded and not checked: WAFFLE, and "Modified Swiss Dwellings" on 4TU.

## 8. Where to find the details

| topic | report | scripts (in `stoa/analysis/`) |
|---|---|---|
| cubicasa5k leak, SVG rules, dropped templates, the 213 plans | `research/data/cubicasa.md` | `cubicasa/image_identity.py`, `count_rules.py`, `sauna_geometry.py`, `presence_check.py`, `excluded_213.py`, `undefined_rooms.py` |
| Swiss formats, parsers, door rule, printed areas, sibling floors | `research/data/swiss.md` | `swiss/probe_pdf.py`, `probe_dxf.py`, `probe_png.py`, `probe_source.py`, `duplicates.py`, `door_rule.py`, `probe_printed.py`, `source_siblings.py` |
| IFC inventory, IfcOpenShell rules, PDF-only, ifc_bench copy, cost | `research/data/ifc.md` | `ifc/02_inventory.py`, `05_probe_models.py`, `06_probe_summary.py`, `07_pdf_room_area.py`, `03_bench_leakage.py`, `08_space_semantics.py`, `12_shortcuts.py` |
| opening_design, historic scans, metadata, scenarios, 50 probes | `research/data/wild.md`, `wild-probe-questions.jsonl` | `wild/coverage.py`, `od_inventory.py`, `od_revisions.py`, `od_probe_schedule.py`, `meta_lookup.py`, `scan_sample.py`, `build_probe_questions.py` |
| Templates, priors, pairs, consistency, formats, split | `research/data/questions.md`, `templates.json` | `questions/templates.py`, `baselines.py`, `consistency.py`, `answer_formats.py`, `split.py`, `split_v0.json` |
| Host facts | `docs/HOST.md`, `context/stoa-drawings/` | - |
| Evaluation design, hidden-set attack ideas | `research/eval/*.md`, `research/ideas/hidden-set-adversary.md` | `eval-design-*/` |

**Where reports disagree, and what I measured (digest check).**

| item | values | status |
|---|---|---|
| Independent items | questions.md: 63,404. Sum of the per-source figures: 64,132 | I ran the key of `baselines.py` per source. It merges ifc_bench to 149 items and opening_design to 7, but all 820 and 64 rows are distinct questions. Use 64,132 |
| ifc_models rule agreement | ifc.md: "one fixed rule matches 3,057 of 3,062". Lead: "at least one candidate rule" | I read `out/probe_summary.json`: 3,057 is the `any_rule` count. Best single rule for room area: footprint, 2,072 of 2,079. The lead's wording is right |
| ifc_models templates | ifc.md: 161 templates, 8 families. questions.md: 129 templates, 21 families | Two template definitions. Not resolved; this digest uses questions.md |
| ifc_models translation groups | ifc.md: 2,726 rows with a twin (1,363 pairs). questions.md: 62,910 groups in total, which leaves 1,361 for ifc_models | Difference of 2, not resolved |
| "Not available" answers in ifc_bench | wild.md: about 25. ifc.md: 100 (118 by answer kind). questions.md: 120 (14.4% of text answers) | I counted 74 answers with the exact phrase "not available" and 91 with a wider pattern. The count depends on the pattern; use "74 to 120" |
| Swiss no-drawing prior | swiss.md: 19.6% (English templates, fit on all rows). questions.md: 14.8% (family constant, grouped 2-fold), 18.9% in sample | Different methods. Use 14.8% for a held-out claim |
| Wrong cubicasa5k answers | cubicasa.md: under 1% [E]. questions.md: 2 to 5% [E] | Both estimates; no audit |
| Drawings with no question | BRIEF.md: "about 6,700 historic scans". wild.md: 6,566 and "8,600". questions.md: "about 60%" | Measured: 6,701 files, 6,566 drawings (135 wikimedia SVG are siblings); 8,611 of 14,550 drawings (59.2%) |
| IFC file counts | BRIEF.md and ifc.md differ; ifc.md says that the brief had them reversed | Measured: ifc_models 533, ifc_bench 30, opening_design 48 |
| cubicasa5k split | questions.md: `split_v0.json` by hash. cubicasa.md: the public CubiCasa5K split | See section 6 |
| cc doors mode | 11.6% (all rows), 11.4% (grouped 2-fold table in questions.md) | Different methods |

Not verified by anyone: every [E, by eye] figure, the 50 probe answers, the scenario weights, and the licence
reading in section 7.
