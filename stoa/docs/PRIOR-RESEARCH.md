# The earlier research, checked claim by claim

Date: 2026-11-14. Subject: `inputs/prior-research/` (`weekend-plan.md` = W, `concepts.md` = C, `research-tracks.json` = T).
Its agents had no shell and no dataset. This file checks it against `research/data/`, `research/sota/`, `research/ideas/` and `HOST.md`.

Status of each figure: **M** = MEASURED by a script in `stoa/analysis/` (the report is named). **MH** = measured for this
digest on `data/junction-dataset/` with small scripts in the session scratch directory (not kept in the repository).
**S** = SOURCED (paper id). **E** = ESTIMATE. Paths are relative to `stoa/docs/`.

## 1. In short

- The design direction holds: compile each drawing once, answer by typed query, use exact geometry for vector files and IFC, show marks as evidence, use two tiers, split by drawing. We keep these.
- No accuracy figure in the prior research was measured. Its three "measured" figures came out close after a real measurement, but only inside the public distribution: Swiss rules 97% is now 99.63% (M), template lookup 95.0% is 93.1% on the preview and 0% across sources (MH), the preview counts are exact (MH).
- It did not see the main fact: the public answers leak. cubicasa5k PNGs are byte-identical to public CubiCasa5K and `model.svg` gives 100% (M). The public Swiss CSV and the public IFC-Bench CSV give the other answers (M). A public score is not a skill score. A mode guess scores 55.3% on cubicasa5k (M).
- Wrong and removed: the training split ("train minus Stoa ids" leaves 182 plans), the "0.55" door and window figure (best is 0.39 and 0.34), "the cobbie rubric matches Stoa's scoring", routing by source folder, "each WC room holds a toilet", ShowerCab as a shower.
- The CubiCasa5K detector stays UNMEASURED and is no longer the centre. It serves 67.3% of public rows, but the host runs a small, hand-run, harder hidden set on "tricky drawings". Its honest tests are the 769 val+test plans and the Swiss PNGs.
- Cost: the host target is about 10 cents per document for ingestion plus questions. The prior "$0.005 per question" needs 18 to 36 questions per drawing. "Opus everywhere" is out.
- Of its 10 questions for Stoa: the host answered 1, 2 and 8 in direction. Our measurements answered 5 and half of 4 and 7. Questions 3, 6 and 9 are open.

## 2. The claim table

Verdicts: CONFIRMED, WRONG, PARTLY, UNMEASURED (no measurement exists, also when the value was close), SUPERSEDED.

### 2a. Figures that the prior research presents as measured

| # | Claim (file) | Verdict | Evidence | Effect on our plan |
|---|---|---|---|---|
| 1 | Preview counts: cubicasa5k 4,270 questions on 241 drawings, swiss 2,358 on 65, ifc_models 1,049 on 6 (827 IFC, 222 PDF), ifc_bench 249 on 5, opening_design 64 on 3 (W top) | CONFIRMED for the preview, SUPERSEDED | MH: all 10 numbers reproduce. Full set (MH, equal to `research/data/questions.md` M): 85,514 on 4,787; 37,584 on 1,040; 3,062 on 84 files (2,694 PDF, 368 IFC); 820 on 25; 64 on 3 | Use full-set shares: 67.3%, 29.6%, 2.4%, 0.65%, 0.05% |
| 2 | "Swiss rules already score about 97% at $0 (measured on the preview)", rules fitted on the same 65 floors (W s1, s2; T) | UNMEASURED as stated (script not kept, in-sample), SUPERSEDED | `research/data/swiss.md` M, all 1,040 floors: DXF probe 98.75% (99.39% best variants), PDF-only probe 99.63% (37,444 of 37,584). MH: the two named rules hold on 1,040 of 1,040 floors (doors = 5-vertex polylines on `DOOR`; windows = `WINDOW` polylines / 3) | Keep the rule parser. The DXF is not needed: the PDF alone is enough |
| 3 | "DOOR: one 5-vertex leaf rectangle + one ARC per door" (T) | WRONG for the ARC part | MH: ARC count equals the answer on 597 of 1,040 floors (57.4%). The reference counts stacked copies of shared doors (`swiss.md` M) | Count openings, not arcs. State the counting rule in the answer |
| 4 | "Exact template lookup already covers 95.0% of held-out preview questions (measured)": cubicasa 100%, swiss 99.4%, ifc_models 92.0%, ifc_bench 3.2%, opening_design 0%; 465 signatures (W s1; T) | PARTLY | MH re-run, 5-fold by file: preview 93.1% (463 signatures; ifc_models 78.5% with only 6 files, ifc_bench 0.8%); full set 99.4%. Leave one source out: 0% for every source | In-distribution figure only. A new source or a hand-written question has no template. Keep a parser that does not need a known template |
| 5 | Swiss DXF is layered, metres, `ROOM_OUTLINE`, `UNIT_OUTLINE`, `ROOM_TEXT`, `DOOR`, `WINDOW`, `FIXTURE`; 65 PDF, 65 DXF, 65 PNG in the preview; 1,614 counts + 744 areas (T) | CONFIRMED | `swiss.md` M (1,031 of 1,040 files have all eight layers, `$INSUNITS` 6). MH: 65/65/65 and 1,614/744 | None |
| 6 | "The printed area labels match the answers to 0.01 m²" (T); verifier "polygon area must match the printed label within 0.5%" (W s2) | PARTLY | `swiss.md` M: only 307 of 1,040 sheets (29.5%) print areas. On those, 1,216 of 1,224 room-area answers are exact | The label check works on 30% of Swiss sheets. The other 70% need polygon plus scale |
| 7 | opening_design: 64 questions on 3 sheets (41, 20, 3), schedule lookups; `find_tables()` finds 0 tables; 38 door ids on A-801 (T) | CONFIRMED | MH: 41/20/3. `research/sota/doc-parsing.md` M1: 0 tables, type counts 6 of 6 with a hand-picked band. `research/data/wild.md` M: parser 14 of 16 values | Rebuild tables from word boxes with `page.rotation_matrix`. Not general yet |

### 2b. Other figures and sourced claims

| # | Claim (file) | Verdict | Evidence | Effect on our plan |
|---|---|---|---|---|
| 8 | "Frontier models get door and window counts exactly right on at most about 0.55 of plans, and 0.15-0.43 in the per-model CSVs" (W s1, AECV-Bench 2601.04819) | WRONG number, right direction | S: Table 1 best door 0.39, best window 0.34 (Gemini 3 Pro); Claude Opus 4.5 0.16 and 0.16. 0.40-0.55 is the mean over classes (`research/sota/floorplan-cv.md`, `vlm-on-drawings.md`). The CSVs were not opened | Do not let a VLM count small symbols. No source covers 2026 models: measure it ourselves |
| 9 | "Small supervised detectors reach 97% per-object detection on doors and windows with only 1,500 plans" (W s1) | PARTLY (misleading) | S: 97% is detection rate at IoU >= 0.1. The same YOLOv8s has mAP50 67.1 (`floorplan-cv.md` S14) | Not a count metric. E: 3% error per object gives 77% exact on a cubicasa window question and 39% on a Swiss door question |
| 10 | "RT-DETR-L reaches about 90 AP50 in 2.3 h on 2xA100" (W s1) | CONFIRMED (S) | Doors 89.8, windows 89.3 (`floorplan-cv.md` S13). 5 classes, no fixtures (`small-models-rl.md`). Trained on the 4,200 train split, which holds 4,018 Stoa plans (M) | Its score on Stoa cubicasa is contaminated. Test it on Swiss PNGs |
| 11 | Evidence graph raised P&ID exact match "from about 39% to about 75%" (W s1, 2609.05880) | CONFIRMED (S) | 36.7-41.3% to 74.3-76.0% with 4B-8B VLMs; graph F1 0.742 (`agentic-program-synthesis.md` S3) | Supports compile once, then query |
| 12 | "Deeper cascades gave no gain in 118 of 135 comparisons" (W s2, 2605.06350) | CONFIRMED (S) | Also "at most 0.43 percentage points" (`agentic-program-synthesis.md` S7) | Two tiers |
| 13 | "Generic SFT gave no counting gain in Perception-R1" (W s1) | PARTLY | S: SFT moved PixMo val 60.2 to 58.0 and test 50.5 to 59.9; RL reached 75.6 (`small-models-rl.md` S1) | Pointer VLM stays a stretch. Added reason: fine-tuned counters fall to 1-26% above the training count range (S5) |
| 14 | "GLM-4.7 reached 56%" on ifc-bench; agent "beats static queries by 37 points" (W s2, s5) | CONFIRMED (S) | 56.0% [51.8, 60.3] (`bim-cad-tooling.md`) or 55.4-56.6% (`agentic-program-synthesis.md`), 514 test questions; +36.8 to +38.5 points | Code agent for free-text IFC questions only |
| 15 | cobbie "rubric (exact counts, 2%, cited properties) matches Stoa's scoring" (W s5) | WRONG | S: an LLM judge with five binary criteria, no 2% rule (2605.01698; two reports agree) | Do not copy the rubric as Stoa's rule. Text scoring is unknown |
| 16 | CHI 2025 (2502.08554): sources and visible inconsistencies reduce overreliance, explanations increase it (W s2, s5) | CONFIRMED (S) | 68.2% against 78.2% agreement with wrong answers (`verification-ux.md` S1) | Marks and disagreement first, prose hidden by default |
| 17 | Grounding DINO 0.0 mAP50 zero-shot on CubiCasa symbols (W s5) | CONFIRMED (S) | `floorplan-cv.md` S14 | No zero-shot open-vocabulary detector |
| 18 | CubiCasa5K: Zenodo 2613548, 5.5 GB, CC BY-NC-SA 4.0 (W s3); "CC BY-NC" (C); split 4,200/400/400 (C) | CONFIRMED, licence sources differ | `research/data/cubicasa.md`: 5.47 GB, Zenodo metadata says CC BY-NC-SA 4.0. The GitHub LICENSE says CC BY-NC 4.0 (`floorplan-cv.md` S11). Split M: 4,200/400/400 | Treat as NC-SA. Record it |
| 19 | "Do not use the default 11-class mapping. It merges Toilet with Urinal and drops showers" (W s3) | CONFIRMED (S) | `house.py` (`floorplan-cv.md` S11) | Build classes from raw SVG names |
| 20 | Shower group = Shower + ShowerCab + Bathtub (T) | WRONG | `cubicasa.md` M: `Shower` + `Bathtub` + `BathtubRound` gives 100.00%; with `ShowerCab` 94.55% | A shower cabin is not a shower for Stoa. A person counts it |
| 21 | Verifier witness "each WC room holds a toilet" (W s2) | WRONG as a hard rule | `questions.md` M: 26 of 2,332 plans (1.1%) have more WC rooms than toilet bowls; 22 have a WC room and 0 bowls | Use inequalities as soft checks only |
| 22 | "About 18 questions share one drawing" (W s1); "about 21 questions per drawing" (C) | PARTLY | MH: preview cubicasa 17.72; full set 21.39 overall, cubicasa 17.86, swiss 36.14 | True on the public set. The hidden session is a short series per document (HOST 9) |
| 23 | "Swiss DXF solver ... 30% of questions"; "ifc_models: 13% of questions on only 6 models"; "opening_design (0.8%)"; "our 53% slice" (W s2, s5) | SUPERSEDED (preview shares) | MH: preview 29.5%, 13.1%, 0.8%, 53.4%. Full: 29.6%, 2.4% on 16 projects, 0.05%, 67.3% | A 10-point gain on ifc_models moves the micro average by 0.24 points (M) |
| 24 | "120,000 questions", "30 languages", "14,000 unlabeled drawings" (C) | WRONG | M: 127,044 questions, 11 question languages (`questions.md`). 8,611 of 14,550 drawings have no question (MH; `wild.md` gives 5,939 / 14,550) | Language tests cover 11 languages plus unseen ones |
| 25 | "The full set probably holds most of the 5,000 plans" (W s3) | CONFIRMED | M: 4,787 of 5,000, train 4,018, val 382, test 387 (`cubicasa.md`) | See row 26 |
| 26 | Train on "the CubiCasa train split minus every id in Stoa's question file"; "about 60% of full-set drawings have no question ... train only on CubiCasa plans without a Stoa question" (W s3) | WRONG | M: every one of the 4,787 Stoa cubicasa drawings has a question. Train minus Stoa ids leaves 182 plans (213 over all splits). The 59% without questions are other sources | Train on the public train split. Report cubicasa only on the 769 val+test plans (13,538 questions) |
| 27 | "Test: the 241 preview drawings. None is in training" (W s3) | PARTLY | MH: 197 of the 241 are in the public train split, 17 in val, 27 in test. The preview is a strict sample of the full set (`questions.md` M) | Any public CubiCasa weight file has seen them |
| 28 | "CubiCasa labels are noisy, so some reference answers are wrong. The ceiling is below 100%" (W s3) | PARTLY | Against the SVG the ceiling is 100.00% (M). Against the drawing: 0 clear errors in about 57 audited answers; one systematic class, bedrooms = 0 on 212 untyped plans (`cubicasa.md`). `questions.md` estimates 2-5% (E) | The risk is convention, not random noise |
| 29 | Calibration gate: SVG counts must agree at least 95% per template, else "Stoa did not derive it from the SVG" (W s3) | CONFIRMED as a method | M: 100.00% on all 12 templates; double door = 1, double sink = 1 (`cubicasa.md`) | Done. The answer is yes for all templates |
| 30 | Opus everywhere "costs about $0.10-0.19 per question" (W s1) | UNMEASURED | E: $0.045-0.05 for one call with one image; $0.31 for a cached 15-call loop (`agentic-program-synthesis.md`, `vlm-on-drawings.md`). S: $0.040 per page on CaseVBench | One agent run per question breaks the 10 cent target |
| 31 | "Cost target: under $0.005 per question blended"; Haiku parse "about $0.0003" (W s2) | UNMEASURED | E: Haiku parse plausible, $0.00007 with a cached prompt. The target assumes 18-36 questions per drawing (`eval-methodology.md`) | Budget per document, not per question |
| 32 | Detector accuracy: doors and windows 60-80%, toilets and sinks 80-90%, showers and bathtubs 40-70%; rooms 85-95%; "blended estimate 80-85%, cubicasa about 75%" (W s2) | UNMEASURED | No detector was trained. No source reports exact counts per plan (`floorplan-cv.md`). An informal probe of a frontier model: windows 1/8, doors 2/5, rooms and fixtures near 100% (`cubicasa.md`, n = 8) | Train only after the harness exists. Doors and windows are 19.4% of cubicasa rows |
| 33 | IFC recipes "90% target, unmeasured" (W s2) | SUPERSEDED | M: 3,057 of 3,062 (99.8%) with Qto first, else geometry (`research/data/ifc.md`). An earlier probe: areas 1,145/1,150, storey counts 204/207, model counts 127/136 (`bim-cad-tooling.md`) | No LLM for templated IFC questions |
| 34 | CodeAct agent on Sonnet 5.5 "55-65%" on ifc_bench (W s2) | UNMEASURED | Our 820 rows are a verbatim copy of public IFC-Bench v2 (M, MH: 820 of 820) | A public ifc_bench score proves nothing |
| 35 | Training runs: about $12, $3, $10; total $25-30; 4-5 h on 1A100 (W s3) | UNMEASURED | Nothing ran. `floorplan-cv.md` E: 4-6 h, $10-15 | Fine as a budget |
| 36 | Router "by file type and source folder" (W s2) | WRONG for the hidden set | HOST 2 and 9: one document at a time, same extensions, other content | Route by content sniffing, never by folder or file name |
| 37 | "Swiss questions name the PDF" and the plan reads the DXF sibling (W s2, s6) | PARTLY | M: question targets are png 85,514, pdf 40,342, ifc 1,188; none is DXF or DWG (`bim-cad-tooling.md`, MH) | PDF path first. DXF is a second witness when it is given |
| 38 | Raster claims in C: areas on rasters "when a scale exists" (C4); DXF "blocks" label fixtures (C5, C9) | WRONG or PARTLY | M: flood-fill area on Swiss PNG is within 2% for 20.8% of rooms. Swiss DXF has no fixture blocks. Distinct doors on the sheet match the reference on 74 of 1,040 floors (`swiss.md`) | Raster areas are low confidence. Pixels cannot reproduce the Swiss door count |

### 2c. Claims that are only in `research-tracks.json` or `concepts.md`

| # | Claim | Verdict | Evidence | Effect on our plan |
|---|---|---|---|---|
| 39 | CubiCasa5K image types: 3,732, 992, 276 (T) | CONFIRMED by consistency | M: Stoa holds 3,578, 943, 266, and the 213 left-out plans are 154, 49, 10 (`cubicasa.md`) | The 213 are a likely hidden cubicasa pool |
| 40 | Co-DETR plus LLM against GPT-5: CubiCasa toilets 87.63 against 85.57, CVC-FP 86.7 against 40.0, SESYD 95.8 against 68.8 (T) | CONFIRMED (S) | `vlm-on-drawings.md` S11. CVC-FP has 15 images, SESYD 48 | A hybrid gains most on unusual styles |
| 41 | Point-then-count: 99.9-100% in distribution, 76-82 against 69-75 on OCID, 97.9 out of distribution (T) | CONFIRMED (S), scope caveat | Open 3-8B models on synthetic shapes and OCID photos, not drawings. Omitted: 16-34% on real images above the training count range (`synthetic-data.md` S6) | Count the points, show them. Do not expect transfer to larger buildings |
| 42 | Claude prices: Opus 5.5 $4/$20, Haiku 5.5 $0.10/$0.50, Batch -50%; image tokens `ceil(w/28) x ceil(h/28)`, max 2,576 px and 4,784 tokens (T) | CONFIRMED (S) | `agentic-program-synthesis.md` S20, S47. Batch is not usable in a live session | Cost arithmetic can use them |
| 43 | "Minimum cacheable prefix 286 tokens" (T) | WRONG | S: 286 tokens is the tool-use system prompt size (`agentic-program-synthesis.md` S20) | Check the caching limits before we rely on them |
| 44 | IFC-Bench: "1,026 QA pairs over 51 IFC models in 22 projects" (T) | PARTLY | MH: 1,026 rows, 31 models, 19 projects in the public CSV. See section 6 | Split IFC evaluation by project |
| 45 | "Stoa's ifc_bench slice comes from this benchmark" (T) | CONFIRMED, sharper | M: 820 of 820 questions and answers are verbatim; 206 public rows on 6 models are not in Stoa's set (`ifc.md`) | Leak. The 206 rows are a likely hidden pool (E) |
| 46 | ViperGPT has "no repo on GitHub" (T) | WRONG | S: `cvlab-columbia/viper` exists (`agentic-program-synthesis.md` S48) | None |
| 47 | Colour-coded confidence gives "roughly 50% less overreliance, not verified" (T) | WRONG number | S: accuracy 26% (none) against 58% (high and low marks) on the hard task; no overreliance percentage (`verification-ux.md` S12) | Two-level status colour per item |
| 48 | PaddleOCR 3.7.0, PP-OCRv6, 50 languages (T) | Reports disagree | UNVERIFIED in `doc-parsing.md`. Confirmed in `floorplan-cv.md` S27 from the repository | Use it. Finnish, Swedish and Estonian quality is UNMEASURED |
| 49 | "opening_design has 20 DWGs" (T); ODA converter "non-commercial only" (T) | SUPERSEDED; UNVERIFIED | M: 271 DWG files, all in opening_design; no question targets them (`bim-cad-tooling.md`) | DWG is low priority. Keep one conversion path |
| 50 | "A 20M-parameter detector replaces Opus pointing for 76% of the questions"; "60-85% exact per class" (C1) | UNMEASURED | No measurement. Symbol counts are 52% of cubicasa English rows (`research/ideas/learned-perception.md` M) | See row 32 |
| 51 | Recipe Foundry: induce one program per template from the answer key, "close to 100% on vector templates" (C2) | CONFIRMED as an outcome | M: 99.63% and 99.8%. S: answer-supervised programs can have "wrong semantics but correct denotation" (`agentic-program-synthesis.md` S15) | Hold out by drawing and by template. Write each convention down as a named rule |
| 52 | Rosetta: the vector file labels its own raster (C5) | PARTLY | M: 1,040 Swiss floors have PNG, DXF and exact answers. Stacked doors do not exist in pixels | Use Swiss PNGs as the cross-style test for a detector, not for door counts |

## 3. What the prior research did not see

**The answers leak through public originals.** It suspected that the CubiCasa SVGs "very likely" produced the answers and planned to hold out drawings. It did not see the size of the leak. All 4,787 PNGs are byte-identical to public `F1_original.png`, and 12 class counts on `model.svg` give 100% (M, `cubicasa.md`). All 1,040 Swiss floors are in public `geometries.csv` under ids that are printed in the title block (M, `swiss.md`). All 820 ifc_bench questions and answers are in the public CSV (M, `ifc.md`). Consequence: a lookup scores 100% on cubicasa5k (67.3% of public rows) and on seven Swiss count families, and it transfers nothing. Our harness bans these paths and reports a leak-free number. We say this in the pitch.

**The hidden-set facts from the host.** The prior plan optimised a blended accuracy on 7,990 template rows. The host said the hidden set is "much more difficult", has "tricky drawings" with the same extensions and other structure, runs "one at a time" through our interface, and can ask compound questions such as tile area for all toilets (HOST 1, 2, 5, 9). Consequence: a few tens of questions decide the result. General skills matter (scale, labels, schedules, areas, two-step questions, no crash on an unknown file), not template coverage. The plan stays open until the hint on Saturday at about midday (HOST 15).

**The sources without questions.** The prior research asked whether the scans have questions (question 7) and planned nothing for them. 8,611 of 14,550 drawings have no question (MH). Among them: 6,566 historic scans, 984 opening_design drawings, 500 ResBIM plans, all elevations and sections (M, `questions.md`, `wild.md`, `ifc.md`). In 120 sampled scans, a scale is present on 28/30 habs, 24/30 finna, 15/30 europeana and 17/30 wikimedia sheets (M by eye, `wild.md`). Consequence: we need a raster path with OCR, a scale check and "cannot be determined". The 50 probe rows in `research/data/wild-probe-questions.jsonl` are our only labelled test there.

**The generator conventions.** Public answers follow the generator, not the drawing. Swiss doors count a shared door once per unit: distinct doors match on 7.1% of floors (M). cubicasa drops a question when the annotation is ambiguous (open doorways on 1,065 plans, shower over bathtub, rooms marked "H"), so the public set holds only the easy cases (M). IFC counts include duplicate spaces and nested stair parts (M). Question presence leaks: a bathtub question exists only when a bathtub exists (M). Consequence: a correct reading can lose public points, and a convention copy can lose hidden points. Each answer names its counting rule. We ask Stoa which convention the hidden set uses.

**The cost target.** The prior plan set its own target ($0.005 per question) and did not know the host's. The host said: "If it's like 10 cents to do both, that's where you got to find", for ingestion and query together (HOST 10). Consequence: the unit is the document. Rule parsers cost $0 (Swiss: 13 s for 1,040 floors, M). One model read per raster document fits. One agent loop per question does not (E: $0.16 to $0.31).

## 4. What we keep from it, and why it survived

| Kept | Why it survived |
|---|---|
| Compile once per drawing, answer by typed query ("Fact Sheet", C2, C4) | S: evidence graph +35 points on P&ID; GPT-5-mini 81.38 on layout JSON against 31.06 on the image (FloorplanQA, single-room layouts). M: rule parsers reach 99.63% (Swiss) and 99.8% (IFC). It fits the session format and the 10 cent target |
| Deterministic geometry for vector files and IFC, no model at inference | M, see rows 2 and 33. Change: PDF first, DXF second; Qto first for walls and slabs |
| A count is the number of accepted marks; polygons with arithmetic; IFC ledger per GlobalId ("Contact Sheet", "Building Twin") | S: `verification-ux.md` supports it. HOST 6 asks for transparent reasoning. HOST 9: 3D is evaluated through our UI |
| Two tiers and a deterministic verifier as the escalation signal | S: 118 of 135. M: where two area extractions agreed within 1%, the weaker one was right in 227 of 227 cases; where they disagreed, in 2 of 66 (`research/ideas/verification-first.md`) |
| Flip and rotation invariance of counts | S: sound metamorphic check (`eval-methodology.md`). Now a harness-wide suite |
| Split by drawing; tune thresholds on exact counts, not mAP; never look up an SVG by file name | All confirmed. Extended: also hold out templates, languages, sources and IFC projects |
| Symbol detector on CubiCasa5K train split (RF-DETR, Apache 2.0) | Still the only cheap tool for symbol counts on rasters. Status UNMEASURED. It is one component, not the plan |
| Pointer VLM as stretch only; GRPO Question Compiler dropped | `small-models-rl.md` agrees, with stronger reasons |
| Schedule rebuild from PDF word boxes | M: 6 of 6 and 14 of 16 on A-801 |
| Licence disclosure (NC data, AGPL code) | Confirmed. Added: PyMuPDF is AGPL-3.0 |

Not kept: accuracy targets as planning inputs, the preview as the test set, routing by folder, the cobbie rubric as Stoa's scoring, a frontier model on every question, and the Saturday timeline (it predates the host talk).

## 5. The 10 questions for Stoa (W section 6)

| # | Question | Status | Evidence |
|---|---|---|---|
| 1 | Hidden test set with automatic scoring, or demo only? | Answered | HOST 1: "I would say most important." HOST 9: "One at a time." HOST 14: "We are not confident that it's the best way to measure things." The exact scoring rule is open |
| 2 | How is cost counted? Does precompute count? | Answered in part | HOST 10: "If it's like 10 cents to do both, that's where you got to find." Ingestion counts. API dollars against GPU seconds is open |
| 3 | May we read the DXF sibling of a Swiss PDF? | Open | Less important now: the PDF alone gives 99.63% (M). "One at a time" suggests that siblings can be absent (E) |
| 4 | May we train on public CubiCasa5K SVGs? Are test drawings in its train split? | Open (permission); answered by measurement (overlap) | M: 4,018 Stoa plans are in train, 382 in val, 387 in test; 213 public plans are not in Stoa's set |
| 5 | Were the cubicasa answers generated from those SVGs? Rules for double doors and "door with leaf"? | Answered by measurement | M: 100.00% on 12 templates. A double door counts 1. The door question is asked only on plans with no open doorway (`cubicasa.md`). The hidden convention is open |
| 6 | How are free-text answers scored? | Open | HOST 4: "The questions might be actually a bit more complex." No rule was given |
| 7 | Questions on the historic scans, or other templates and languages? | Answered for the full set, open for the hidden set | M: 0 questions on 6,566 scans; 11 languages. HOST 2: "We have like a few tricky drawings internally, which we don't share." HOST 12: "There are also images that don't have a scale." |
| 8 | May the system abstain, and how is that scored? | Answered in direction | HOST 6: "The I don't knows are super important." HOST 7: "If you want an answer, give us a scale or calibrate." The score of an abstention is open |
| 9 | Are non-commercial weights acceptable? | Open | Not discussed |
| 10 | What does "verified in seconds" mean? | Answered in part | HOST 6: "We appreciate deterministic as much as possible." HOST 11: the interface weighs about 5%, "Should be a good ballpark." |

New questions that matter more: which door and room convention the hidden set uses, whether the 213 left-out CubiCasa plans or the 206 left-out IFC-Bench rows are in it, and whether the file name reaches us.

## 6. Where reports disagree, and what this digest measured

| Topic | Values | Note |
|---|---|---|
| AECV-Bench door and window accuracy | "Correct it": 0.39 and 0.34 best (`floorplan-cv.md`, `vlm-on-drawings.md`). "Confirmed": "often 0.40-0.55" (`agentic-program-synthesis.md`, `small-models-rl.md`, `doc-parsing.md`) | Both are in the paper (S). Table 1 has the per-class values. The abstract has the range. Use Table 1 |
| IFC-Bench v2 size | Prior: 1,026 pairs, 51 models, 22 projects. Paper: 1,027 tasks, 37 models, 21 projects (`agentic-program-synthesis.md`). Dataset card: 1,027. `ifc.md`: 1,026 rows on 31 models | MH: the local public CSV has 1,026 rows, 31 (project, model) pairs, 19 projects |
| Files in `ifc_bench/` | 30 (`ifc.md`), 31 (`bim-cad-tooling.md`) | MH: 30 IFC files plus `LICENSE.md` |
| opening_design PDFs with no text layer | 74 (`wild.md`), 91 (`doc-parsing.md`, 200 characters or fewer) | MH: 66 with zero characters, 91 with 200 or fewer |
| Swiss doors from DXF arcs | 82 of 150 (`floorplan-cv.md`), 81 of 150 (`verification-first.md`), 13.9% with unique arcs (`swiss.md`) | MH: 597 of 1,040 with raw arcs. The cause is stacked copies of shared doors (`swiss.md`), not double leaves |
| Swiss door polylines | "DOOR polylines // 2 on 98/150" (`floorplan-cv.md`), 5-vertex polylines 150/150 (`verification-first.md`), 100% (`swiss.md`) | MH: 1,040 of 1,040 with 5-vertex polylines |
| Rooms with a Qto area | 900 of 2,079 rows (`ifc.md`), 417 of 1,150 rooms, 36% (`bim-cad-tooling.md`) | Different units (rows, rooms). Both say: Qto is right where present, and often absent |
| ifc_models templates | 129 templates in 21 families (`questions.md`), 161 templates in 8 families (`ifc.md`) | Different slot rules. Not settled here |
| "Not available" answers in ifc_bench | 120 (`questions.md`), 118 or 100 (`ifc.md`), "about 25" (`wild.md`) | Different patterns. Not settled here |
| cubicasa plans with all 12 templates | 489 (`research/ideas/wildcard.md`), 1,161 (`verification-first.md`) | MH: 489 plans have all 24 questions |
| Historic scans | 6,566 (`questions.md`, `wild.md`), 6,570 (`synthetic-data.md`, `learned-perception.md`), "about 6,700" (`BRIEF.md`) | MH: 6,566 file stems |
| cubicasa5k mode guess | 55.3% (lead), 55.32% (`cubicasa.md`, `eval-methodology.md`) | MH: 47,308 of 85,514 = 55.32% |
