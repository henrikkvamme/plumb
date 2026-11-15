# State of the art, November 2026: what is known, with checked sources

Digest of the 11 reports in `stoa/docs/research/sota/`. Written 2026-11-14. Each report has a Sources table with a check column and a Verification section. This digest uses the corrected values. For a detail, open the report.

This file reports what the sources say. The "What this means for us" paragraphs are the view of each report. Where they differ from `DECISION.md` or `EVALUATION.md` (for example on routing by template, or on the headline number), those two documents hold the decision.

Report keys: `vlm` = vlm-on-drawings.md, `cv` = floorplan-cv.md, `doc` = doc-parsing.md, `bim` = bim-cad-tooling.md, `agent` = agentic-program-synthesis.md, `rl` = small-models-rl.md, `syn` = synthetic-data.md, `eval` = eval-methodology.md, `ux` = verification-ux.md, `stack` = stack-rust-python.md, `video` = explainer-video-craft.md.

Status of each figure:
- **S** (SOURCED): a paper or a web page states it. The id names the report and its source row: VLM-S1 = S1 in `vlm`. Links are in section 7.
- **M-A** (MEASURED, analysis): a script in `stoa/analysis/` measured it. The figure is in `docs/research/data/`.
- **M-R** (MEASURED, report): the report's agent measured it with a scratchpad script. The script is not in the repository, and the verifier did not run it again. Trust it less than M-A.
- **M-D** (MEASURED, digest): I ran it again on the full dataset for this digest. Section 6.3 lists these.
- **E** (ESTIMATE): reasoning or arithmetic with assumed inputs. Do not quote it as a result.

## 1. In short

1. **Do not let a model count symbols.** Best published exact-match rate: doors 0.39, windows 0.34 (January 2026 models). Nobody has tested the late-2026 models on this. Count with vector geometry or a trained detector. The count is the number of marks.
2. **Give the model structure, not pixels.** Compile each document once into a typed fact store. The LLM plans, queries and explains. Evidence: 81.38 with JSON against 31.06 with the image; 36.7-41.3% to 74.3-76.0% with an evidence graph.
3. **Deterministic code reproduces the public answers where vector data exists, at $0**: IFC room areas 99.6%, Swiss windows 150 of 150. But the public answers leak (cubicasa5k is 95.7% of public CubiCasa5K, ifc_bench is public IFC-Bench v2). A score from a lookup does not transfer to the hidden set.
4. **An agent loop per question breaks the cost target.** About $0.31 per question (E, Opus 5.5, 15 calls) against the host's target of about 10 cents per document with its questions. Use the agent only for the residual. Use two tiers at most.
5. **Build "I do not know" from explicit checks, not from the model's confidence.** No scale, no layer, two witnesses disagree. The best of 17 agents reached 59.5% on act-or-abstain tasks.
6. **The evaluation must imitate the shift.** Hold out drawings, templates, languages and IFC projects. Use clustered error bars (1.88 times the naive ones on cubicasa). Report the blind baseline (55.32% on cubicasa). Score abstention and evidence.
7. **Evidence view: marks on the drawing and a colour per item, not prose.** A two-level colour flag raised accuracy on a hard task from 26% to 58%. Prose explanations raise trust in wrong answers.
8. **Henrik's three ideas:** RL is an optional polish step, not the core. A Rust core costs time and buys no points this weekend. Synthetic data is right for tests and as a training supplement, not as the only training data.

## 2. Topics

### 2.1 Vision-language models on drawings (`vlm`)

| Finding | Status | Source |
|---|---|---|
| Exact door / window count on 120 floor plans (partly CubiCasa5K): Gemini 3 Pro 0.39 / 0.34, GPT-5.2 0.28 / 0.27, Claude Opus 4.5 0.16 / 0.16, open models 0.09-0.12 / 0.03-0.18. Bedrooms up to 0.91 and toilets up to 0.82, because a text label marks them | S | VLM-S1 |
| Structure against pixels: GPT-5-mini 81.38 with the layout as JSON, 31.06 with the image only (FloorplanQA, single-room layouts) | S | VLM-S7 |
| Room area: open VLMs about 43% MAPE (2 of 3 models gave scorable output). Pixel count of a colour mask: 1.58% per floor plan, 5.68% per room. Stoa's tolerance is 2% | S | VLM-S8 |
| Hybrids: P&ID evidence graph 36.7-41.3% to 74.3-76.0% (4B-8B open VLMs). Detector plus GPT-5, toilet counts: CVC-FP 86.67 against 40.00, CubiCasa5K 87.63 against 85.57. Takeoff system 81.6 against 61.4 (best frontier model) and 77.6 (human estimators), on the vendor's own benchmark | S | VLM-S9, S11, S10 |
| Large sheets (LED-BENCH): whole sheet 36.38. Sheet plus 4 fixed overlapping crops in one call 49.34. Search-then-reread (3 calls) 49.74. Locate-then-reread 41.43. Best model: GPT-5.6 Sol 52.65 | S | VLM-S3 |
| Point, then count in code: best counting method, points grounded in more than 94% of cases. Tested on open 3-8B models and photos, not on drawings | S | VLM-S14 |
| One image at full size (2,576 px, 4,784 tokens) plus about 1,500 output tokens: Opus 5.5 about $0.05, Sonnet 5.5 about $0.025, Haiku 5.5 about $0.001 | E | from VLM-S16, S17 |

Does not work: zero-shot counts of small symbols; area from a VLM; sending a PDF to Claude when you need coordinates (pages are rasterised server side, VLM-S24); normalised 0-1000 coordinates from Claude (use pixels, VLM-S24); more thinking for counting (peaks near 40%, then declines, VLM-S22). No benchmark scores calibration or abstention on drawings (E, absence claim).

What this means for us: the VLM reads labels and text, and it judges a few disputed crops. It never states a count or an area. For large sheets, send the sheet plus 4 fixed crops in one call. Measure the late-2026 models on our own held-out split before we spend on them: a 200-plan batch run costs under $10 (E).

### 2.2 Floor-plan computer vision and detectors (`cv`)

| Finding | Status | Source |
|---|---|---|
| Counts are large. cubicasa: windows mean 8.78 (max 92), doors 8.74 (max 43). Swiss: doors mean 30.7 (max 157), windows 17.8 (max 137) | M-D (cubicasa), M-R (Swiss) | section 6.3, `cv` M2 |
| With a 3% error per object, the exact-count rate is about 77% (cubicasa windows) and 39% (Swiss doors). With 1%: 92% and 73%. No paper reports exact-count accuracy for a detector; mAP is the only published metric | E | `cv` finding 2 |
| Stoa's cubicasa5k holds 4,787 of the 5,000 public CubiCasa5K images (95.7%). 213 remain. Public RT-DETR, Raster2Seq and CubiCasa weights trained on them. The public `model.svg` files reproduce all 12 Stoa templates exactly | M-A, M-D | `data/cubicasa.md`, CV-S12, S13 |
| In-domain detector: RT-DETR-L AP50 door 89.8, window 89.3, about 2.3 h on 2 A100. It has 5 classes (no toilets or sinks). Window confidence 0.9+ on line art, 0.3-0.5 on rendered styles | S | CV-S13 |
| Zero-shot open-vocabulary: Grounding DINO mAP50 about 0.0 on CubiCasa symbols; fine-tuned 39.3 against 67.1 for a small YOLOv8s. SAM 3: 15.2 AP zero-shot on RF-100VL | S | CV-S14, S18 |
| Learned vector spotters do not transfer: VecFormer PQ 91.1 on FloorPlanCAD, 8.43 zero-shot on SESYD; SymPoint 83.3 to 33.2. Training: 8 A100 GPUs, 500 epochs | S | CV-S2, S5, S6 |
| Swiss DXF layer rules on 150 floors: windows = WINDOW polylines / 3 on 150 of 150. Apartments = UNIT_OUTLINE count on 135. Doors = DOOR arcs on 82; DOOR polylines // 2 on 98. My rerun on another 150 floors: 150, 134, 81, 101 | M-R, M-D | `cv` M4, section 6.3 |

Does not work: mAP or "97% detection" as a proxy for exact counts (the 97% is recall at IoU >= 0.1, CV-S14); any public CubiCasa weight as an honest score on Stoa's cubicasa questions; training a vector spotter this weekend.

What this means for us: use DXF and IFC geometry where it exists. For rasters, train one RF-DETR on CubiCasa by k-fold splits, tune thresholds on exact counts, and test it on the 1,040 Swiss PNGs (M-D). That cross-style test is our best proxy for hidden drawings. Swiss door answers follow the generator's database rule, not the visible doors: read `data/swiss.md`.

### 2.3 Document parsing and OCR (`doc`)

| Finding | Status | Source |
|---|---|---|
| Schedule sheet A-801: 1,037 of 1,044 text lines are rotated 90 degrees. PyMuPDF `find_tables()` finds 0 tables ("lines") or 1 junk table ("text"). A naive token count is right for 3 of 6 door types. A count in the TYPE column band is right for 6 of 6 (band chosen by hand) | M-R | `doc` M1 |
| opening_design: 587 of 678 PDFs have a text layer (more than 200 characters). 437 of 678 contain a scale string. Swiss and ifc_models samples: 40 of 40 carry a scale note | M-R, M-D (587, 437) | `doc` M2, M3 |
| Page parsing, OmniDocBench v1.6: PaddleOCR-VL-1.6 (0.9B, Apache-2.0) 96.33, GLM-OCR (0.9B, MIT) 95.22, Gemini 3 Pro 92.91, GPT-5.2 86.59 | S | DOC-S1 |
| Skewed pages (Real5 "Skew"): PaddleOCR-VL-1.6 92.66, Gemini 3 Pro 89.45, MinerU2.5 75.24, DeepSeek-OCR 2 61.28 | S | DOC-S1 |
| Old scans (olmOCR-bench): Chandra 2 51.1, dots.mocr 48.2, dots.ocr 40.9. CHURRO, trained on historic pages: 82.3% printed, 70.1% handwritten | S | DOC-S5, S15, S6 |
| Schedule tables by VLM (20 tables, industry blog): Gemini 2.5 Pro 94.2% at 47.4 s per page and $58 per 1,000 pages, Textract 82.1%, Azure 81.5%, GPT-4o 38.5% (dropped rows) | S | DOC-S9 |

Does not work: OCR or a VLM where a text layer exists; `find_tables()` on rotated schedules; majority vote over repeated VLM runs (DOC-S9); any OCR on old scans without low confidence.

What this means for us: vector PDF first. Rebuild tables from word boxes in the rotated frame, at $0. Read the scale by regex, per view, and check it against one dimension. For rasters, run PaddleOCR-VL-1.6 on a Verda GPU, not a Claude call. On historic scans, give text answers a low confidence or abstain.

### 2.4 BIM and CAD tooling (`bim`)

| Finding | Status | Source |
|---|---|---|
| Room net floor area by `ifcopenshell.util.shape.get_footprint_area`: within 2% for 1,145 of 1,150 matched rooms (99.6%). The analysis scripts report 2,078 of 2,079 rows with "Qto, else footprint" and 99.7% with footprint alone. The row sets differ; both values are shown | M-R, M-A | `bim` M1, `data/ifc.md` |
| `Qto_SpaceBaseQuantities.NetFloorArea` exists for 417 of 1,150 rooms (36%); all 417 are within 2%. Wall net volume: Qto 69 of 69, geometry 45 of 69. Wall length Qto is in millimetres in the Molio model | M-R | `bim` M1, M3 |
| Storey counts: `get_decomposition` 204 of 207, direct containment 140 of 207. Model counts: `by_type` with subtypes 127 of 136, without 116. Molio has 579 IfcStair; the answer is 15 (top-level stairs) | M-R (579: M-A) | `bim` M3, M4 |
| Our 820 ifc_bench questions match the public IFC-Bench v2 CSV, 820 of 820. 399 are in the paper's test split. The 206 public questions that we lack are on 3 projects | M-R, M-A | `bim` M5, `data/ifc.md` |
| Agent on IFC-Bench v2 (514 test questions): 56.0% [51.8, 60.3] for an iterating code agent (GLM 4.7), 19.1% for single-pass code. Hand-made tools: no gain for the strong model, -10.2 points for the weaker one. Materials questions 42%. Spread per project 25-90% | S | BIM-S1 |
| IFC-Bench scoring is an LLM judge with 5 binary criteria (abstention plus 4 substantive ones). It has no 2% rule. The judge sees the execution trace | S | BIM-S1 |
| Question targets: png 85,514, pdf 40,342, ifc 1,188. No question targets DWG or DXF. OCG layers exist in 14 of 1,825 PDFs, a /VP viewport in 11 | M-D (targets), M-R | section 6.3, `bim` M7 |

Does not work: one-shot text-to-code on IFC; Qto alone (64% of rooms have none); geometry alone for walls; counting every IfcStair; scale from PDF metadata; LibreDWG output as truth (about 10% AutoCAD import failures by its own manual, BIM-S14).

What this means for us: a deterministic IfcOpenShell solver for ifc_models (geometry for rooms, Qto for walls and slabs, unit scaling), with the GlobalId as evidence. A small code agent for free-text IFC questions, capped at 10-15 runs. Plan for 50-65% there (E). Split by project. Never read the public IFC-Bench answers at inference.

### 2.5 Agents, tools and program synthesis (`agent`)

| Finding | Status | Source |
|---|---|---|
| Compile once, then query: a knowledge graph of a P&ID gives +18% accuracy over images and 85% fewer tokens. GPT-5-mini reaches 91% at $0.004 per task. In a second study the errors track the F1 of the recovered graph (0.742) | S | AG-S2, S3 |
| Crop-and-zoom agents: "only marginal or negative gains over direct inference at substantially higher token cost". The returned pixels are often redundant | S | AG-S4, S5 |
| Cost of a 15-call agent loop with one image and prompt caching: Opus 5.5 $0.314, Sonnet 5.5 $0.157, Haiku 5.5 $0.009. Without caching: Opus $1.255. All 127,044 public questions with an Opus agent: about $40,000 | E | `agent` section E |
| One Sonnet 5.5 compile call per drawing: about $0.036. Per question: $0.0020 on cubicasa (17.9 questions per drawing), $0.0010 on Swiss (36.1). A hidden set with fewer questions per drawing raises this | E | `agent` section E |
| Cascades: more than two tiers gave no gain in 118 of 135 comparisons. Early abstention cut cost by 13.0% and errors by 5.0% | S | AG-S7, S9 |
| Abstention: reasoning fine-tuning degrades it by 24% on average. Best of 17 agents: 59.5% paired accuracy. Code interpreters reduce overconfidence; search tools raise it | S | AG-S10, S11, S12 |
| Offline solver induction against the answer key: 43% to 67% on disjoint splits. Risk: about 34.4% of trials that passed fixed tests violated the task; coding agents hard-code test cases | S | AG-S13, S16, S17 |
| Replay: the Claude API returns a 400 for `temperature`, `top_p` or `top_k` under API version 2026-10-21. Frozen agent paths keep 93.8% completion (agent 96.8%) at 24% lower cost | S | AG-S22, S19 |

Does not work: a zoom agent as the counting method; more agent steps for counting (AG-S25); deep cascades; fixed unit tests as the only check on induced code; the model's own confidence as the abstention signal.

What this means for us: route by file type and template with no LLM. Answer from the compiled fact store. On a miss, one Haiku-class call fills a closed DSL, or a capped code agent runs for IFC. Cache every LLM output by a hash of its input. Caching and the Batch API (50% off, AG-S20) are mandatory.

### 2.6 Small models, fine-tuning and reinforcement learning (`rl`)

| Finding | Status | Source |
|---|---|---|
| RL with a point-matching reward: Qwen2-VL-2B on PixMo-Count test 50.5 to 75.6. SFT alone 59.9. With forced thinking 72.8 | S | RL-S1 |
| Plain GRPO with a 0/1 count reward "underperforms compared to supervised fine-tuning" | S | RL-S6 |
| Controls matter: R1-V GRPO 48.0% to 82.5%, but the base model answers directly at 86%. Random rewards gave another model +21.4 points | S | RL-S9, S12 |
| Mode answer per cubicasa template: kitchens 95.8%, bathrooms 88.6%, storeys 79.9%, doors 11.6%, windows 13.6%; all templates 55.32% | M-D | section 6.3 |
| Fine-tuned counters above the training count range (up to 2 times): 1-26% on real images, 16-34% when the count is the number of points. In range: 70-82%. A new drawing style was not tested | S | RL-S5 |
| The stated count and the points disagree: consistency 20.56% (Qwen2.5-VL-3B) to 99.27% (InternVL3.5) | S | RL-S5 |

What this means for us: a detector gives boxes, runs deterministically and costs near zero. A small pointer VLM is a second witness for abstention, and it meets Stoa's "small fine-tuned model" wish. Count its points, never its stated number. Section 3.1 has the RL decision.

### 2.7 Synthetic data (`syn`)

| Finding | Status | Source |
|---|---|---|
| Synthetic only against real: ChartQA 20.96% (synthetic only), 41.56% (real), 51.84% (synthetic pre-training, then real). P&ID edge mAP: 63.8 (synthetic), 69.4 (12 real images), 72.6 (mixed) | S | SYN-S3, S2 |
| Structure matters more than volume: topology seeded from real drawings about 64%, random placement about 33%. Gains flatten after about 400 images | S | SYN-S2 |
| A DXF, PDF and PNG generator with a scene graph: 0.072 s per drawing. Augraphy 8.2.6 adds 1.2 s per image. Its default pipeline warps geometry, so area labels break. It fails on Python 3.14 | M-R | `syn` MEAS |
| Metamorphic tests need no labels. They found over 4.9 million perception failures in VQA models | S | SYN-S10 |

What this means for us: build the generator for tests first: one-factor shift suites (symbol, language, rotation, scale, no-scale, clutter, scan, count range) and "not answerable" cases. The public set has none of these cases outside ifc_bench. Do not use Swiss Dwellings as an answer source at inference: that is a leak. Section 3.3 has the decision.

### 2.8 Evaluation methodology (`eval`)

| Finding | Status | Source |
|---|---|---|
| Distribution shift is a bigger risk than test-set reuse (120 Kaggle competitions). New test sets from the same process: drops of 3-15% (CIFAR-10) and 11-14% (ImageNet) | S | EV-S2, S1 |
| cubicasa has 24 distinct question strings on 4,787 drawings. A mode guess per template scores 55.32% | M-D | section 6.3 |
| Clustered error bars: naive SE 0.00170, clustered SE 0.00319 (ratio 1.88) on that baseline. Elsewhere "over 3X larger" | M-R, S | `eval`, EV-S19 |
| Minimum detectable effect: cubicasa 500-drawing holdout 1.7 points, 100-drawing holdout 3.9, ifc_bench 12.1, opening_design (64 questions) 35 | E | `eval` section 5 |
| Abstention metrics: effective reliability (+1 right, -c wrong, 0 abstain; c = 1, 10, 100); confidence target t with a t/(1-t) penalty | S | EV-S14, S16 |
| LLM judges need a reference answer. High percent agreement can hide different scores: report Cohen's kappa | S | EV-S24, S23 |
| Temperature 0 is not deterministic: 80 distinct completions in 1,000 identical requests; accuracy varies up to 15% across runs | S | EV-S30, S31 |
| Evidence scoring: best model 76.0 strict attributed accuracy on CiteVQA; models often give the right answer and cite the wrong region | S | EV-S45 |

Does not work: random question splits; naive standard errors; tuning on the 64 opening_design questions; a judge without a reference; the mean over answered questions only; SaaS harnesses with small free tiers.

What this means for us: a custom runner of 300 to 600 lines (E). Splits by drawing, template, language, source and IFC project. The headline is the worst split. Accept a change only on a paired, clustered difference. Add a metamorphic suite, a "verifiable accuracy" metric (answer and evidence both right), and 60-100 hand-labelled questions on historic scans. The three designs are in `docs/research/eval/`.

### 2.9 Verification UX (`ux`)

| Finding | Status | Source |
|---|---|---|
| Sources lower agreement with a wrong LLM answer from 78.2% to 68.2% (N=308). Explanations raise reliance on right and wrong answers | S | UX-S1 |
| A wrong LLM explanation lowers user accuracy to 0.35, below the no-evidence baseline of 0.49 | S | UX-S3 |
| A green/red confidence flag per number: accuracy on the hard task 58% (high and low flags), 53% (low only), 26% (none) | S | UX-S12 |
| Links from each value to its source field cut verification time by 20% | S | UX-S13 |
| Citations alone mislead: random citations raise trust. Commercial search engines fully supported 51.5% of sentences; 74.5% of citations supported their sentence | S | UX-S14, S8 |
| People cannot read confidence from prose: human AUC 0.59-0.60 against model AUC 0.75-0.78. A frequency format lets users adjust | S | UX-S7, S18 |
| "I'm not sure, but...": agreement 80.9% to 74.8%; accuracy when the AI is wrong 43.6% to 52.0% | S | UX-S2 |
| Stoa's product: a citation to the document and page per sentence, a "Show thought process" toggle, numbered change boxes, "When the documents do not hold the answer, Stoa says so." | S | UX-S26 |

Does not work: long rationales; saliency heat maps (UX-S19, S20); citations nobody checks; a raw confidence number; relying on the person to fix errors.

What this means for us: an answer is marks on the sheet, a polygon with an arithmetic tape, or a row list of GlobalIds. Colour: green = a deterministic check passed, amber = model judgement, red = methods disagree. Confidence reads "right 47 of 50 times on held-out questions of this kind" (E, format). Abstain in the first person with a next step: "No scale found. Click two points of a known length." No vendor page that the report opened shows a per-answer confidence (E, limited scan).

### 2.10 Implementation stack: Rust or Python (`stack`)

| Finding | Status | Source |
|---|---|---|
| Parsing takes milliseconds in Python: PyMuPDF 10 ms per Swiss PDF page, ezdxf 34 ms per Swiss DXF, IfcOpenShell 14.4 s for 30 ifc_bench models | M-R | `stack` |
| The Rust `dxf` crate 0.6.2 returns no HATCH entity and no error. All 300 sampled Swiss DXFs contain HATCH (my rerun: 150 of 150) | M-R, M-D, S | ST-S6 |
| IfcOpenShell opens 29 of 30 ifc_bench models. `dental_clinic_mep.ifc` has a syntax error | M-R, M-A | `stack`, `data/ifc.md` |
| Coding agents in Rust: Multi-SWE-bench, same agent: Python 52.20%, Rust 15.90% (different repositories). Rust-SWE-bench: best baseline 21.2% | S | ST-S1, S2 |
| A Codex CLI port from Rust to Python: 73.8% against 70.0% on 80 SWE-bench Verified tasks, 42.5% against 47.5% on Terminal-Bench, 15.9 times less code | S | ST-S3 |

What this means for us: Python for parsers, geometry, scorer and training; the TypeScript starter for the service and UI (repo rule). Get type safety from pyright strict, a `Quantity(value, unit)` type and an `Answer = Value | Abstain(reason)` union. Count entity types per file to catch silent parser drops. Section 3.2 has the decision.

### 2.11 Explainer video craft (`video`)

The video is made; this is for the record. Script and voice first, then cut each scene to its audio (VID-S1). Render HTML to video from code (HyperFrames 0.9.42, Apache-2.0, or Remotion 4.0.543, free for up to 3 employees; VID-S2, S5), not with a pixel video model (VID-S8). Look at a still per scene: agent-made videos mostly have layout defects (VID-S9). Voice: Kokoro-82M, local, Apache-2.0 (VID-S10). Pace: about 150 words per minute (E, from VID-S15).

## 3. Henrik's three ideas

### 3.1 Reinforcement learning

| Evidence for | Evidence against |
|---|---|
| Many answers are checkable by machine (counts exact, areas within 2%) | A 0/1 "count is right" reward does worse than SFT (S, RL-S6). The reward must score points, and Stoa's cubicasa files have no point labels (PNG only, M-D) |
| Point-matching RL: 50.5 to 75.6 on PixMo-Count; SFT alone 59.9 (S, RL-S1) | The mode answer scores 55.32% on cubicasa, 95.8% on kitchens (M-D). A group of samples that all say "1" teaches nothing |
| Few-shot detection: COCO 2-shot 19.6 to 41.5; SFT 21.0 (S, RL-S3) | RL gains can be a format effect: base model 86% direct against 82.5% after GRPO (S, RL-S9). Random rewards: +21.4 points (S, RL-S12) |
| On mechanical drawings: 76.36 (SFT) to 84.85 (RL) (S, RL-S14) | SFT matches RL at a matched rollout budget (S, RL-S13). RL improves pass@1 and rarely adds capability (S, RL-S11) |
| Executor rewards work for program synthesis: a 7B text-to-SQL model matches 70B-class systems (S, RL-S17). This maps to IFC and DXF queries | Prompt optimisation beats GRPO by 6% with up to 35 times fewer rollouts (S, RL-S18). We have only 820 ifc_bench questions |
| One GRPO run fits in 4-10 h on one A100; whole plan under $60 (E). A model trained on Verda is a plus (brief) | Counters collapse above the trained count range: 1-26% (S, RL-S5). RL for zoom tools: gains are "dominated by intrinsic learning" (S, VLM-S25) |

Reading: RL is a polish step after a detector or an SFT pointer works. If we run it: point-matching reward, only the high-entropy templates (doors, windows, sinks, WC seats), and a report against the mode baseline and a random-reward control.

### 3.2 A Rust core with Python for training

| Evidence for | Evidence against |
|---|---|
| The type system catches 2 to 3 of 7 typical harness errors (E) | Strict Python catches the same 2 to 3. The other 4 need tests in both languages (E) |
| The Rust DXF parser is about 4 times faster: 2.41 s against 10.06 s for 300 files (M-R) | That parser drops every HATCH entity with no error (M-R, S ST-S6). Parsing is 10-34 ms; model calls drive the cost criterion |
| Incremental rebuild 0.4-0.7 s (M-R) | Clean release build 37.6 s for each new crate tree (M-R). 55% of Rust developers wait more than 10 s for a rebuild (S, ST-S10) |
| Google: 4 times lower rollback rate for Rust changes (S, ST-S4) | The baseline is C++. No study compares Rust with typed Python (absence claim) |
| ifc-lite: a Rust core in WASM with a WebGPU viewer, "99.9%+ agreement" with IfcOpenShell (S, BIM-S10). Usable from the TypeScript app | No Rust DWG reader. `ifc_rs` is alpha and reads a subset of IFC4; 15 of 30 ifc_bench models are IFC2X3 (S ST-S8, M-R). `ort` 2.0 is a release candidate |
| A single static binary helps a later product | Coding agents resolve fewer Rust issues: 15.90% against 52.20% for Python (S, ST-S1). A Rust-to-Python port reached near-parity with 15.9 times less code (S, ST-S3) |
| | The repo rule is the TypeScript starter plus Python. Rust adds a third language: 3 to 6 h (E) |

Reading: no Rust core this weekend. Use ifc-lite from TypeScript for the 3D evidence view if time allows.

### 3.3 Synthetic data

| Evidence for | Evidence against |
|---|---|
| Pre-training on synthetic data, then real data: 51.84% against 41.56% real only (S, SYN-S3). Mixed 72.6 against 69.4 real only (S, SYN-S2) | Synthetic only: 20.96% against 41.56% (S, SYN-S3); 63.8 against 69.4 from only 12 real images (S, SYN-S2) |
| A synthetic prior helps low-data fine-tuning: MPE 7.05 against 12.1, in one setting (S, SYN-S1) | Random placement without real structure: about 33% against about 64% (S, SYN-S2). More of the same data stops helping after about 400 images |
| A generator with exact labels is cheap: 0.072 s per drawing; about 6 h to build (M-R, E) | Counting does not extrapolate past trained counts: 16-34% at best on real images (S, RL-S5 = SYN-S6) |
| As a test suite it covers what the public set lacks: no scale, unseen symbols and languages, rotated sheets, counts above the public maximum, "not answerable" | Template test sets over-estimate skill: up to 34.5% drop on small changes (S, SYN-S4). Our generator repeats our own conventions, not Stoa's hidden ones (E) |
| Metamorphic checks need no labels, so they also run on the 6,701 historic files (M-D) | The default scan-degradation pipeline warps walls, so area labels break (M-R) |
| Public seeds with exact geometry exist under CC BY 4.0 (S, SYN-S17, S19) | Swiss Dwellings is the source of Stoa's Swiss answers. As an answer source it is a leak (M-A, `data/swiss.md`). Learned plan generators need RPLAN and have research-only or GPL terms (S, SYN-S20, S21) |

Reading: yes for evaluation, first. For training, only as pre-training or a supplement, seeded from real layouts.

## 4. Tools we can use this weekend

**AGPL** = network copyleft; fine for the hackathon, but Stoa cannot ship it without a commercial licence. **NC** = non-commercial.

| Name | Version | Licence | What for | Caveat |
|---|---|---|---|---|
| IfcOpenShell | 0.9.0.post1 (2026-10-15) | LGPL-3.0-or-later | IFC parsing, geometry, Qto, IfcConvert | Pin to match Stoa's generator. One ifc_bench model does not parse |
| ifc-lite, web-ifc | crates 28.2.0; npm | MPL-2.0 | 3D evidence view in the browser | Moves fast; quantity API not tested |
| ezdxf | 1.4.5 (2026-10-16) | MIT | Read and render DXF | DWG only through the ODA File Converter |
| shapely | 2.2.0 | BSD-3-Clause | Polygon area, point in polygon | 2D only |
| PyMuPDF | 2.1 (2026-11-02) | **AGPL-3.0** or commercial | Text with boxes, vector paths | Wrap it so pypdfium2 or pdfplumber can replace it |
| pypdfium2 | 5.15.2 (2026-11-09) | Apache-2.0 / BSD-3-Clause | Render, text, page objects | Path segments only through the raw API |
| LibreDWG `dwg2dxf` | 0.14 (Homebrew) | **GPL-3.0-or-later** | DWG to DXF | About 10% AutoCAD import failures; some R2010+ objects are skipped |
| ODA File Converter | ODA Platform 27.10 | closed, "custom" | DWG to DXF, best fidelity | Licence text not readable online; GUI app |
| RF-DETR N/S/M/L | rfdetr 1.12.1 (2026-11-12) | Apache-2.0 | Symbol detector | Atto, Femto, Pico, XL, 2XL are PML 1.0 |
| Ultralytics (YOLO, RT-DETR) | 8.4.212 | **AGPL-3.0** | Detector training | Prefer RF-DETR |
| RT-DETR-L floor-plan weights | repo `OldDeLorean/rtdetr-floorplan-detector` | none stated; trained with **AGPL** code | Baseline for doors and windows on Swiss PNGs | Saw Stoa's cubicasa images; 5 classes |
| Raster2Seq | repo, `hf:cubicasa5k` | code MIT, weights **CC BY-NC 4.0 (NC)** | Room polygons on rasters | Trained on CubiCasa5K; reads no text |
| PaddleOCR-VL-1.6 | 0.9B (2026-05-28) | Apache-2.0 | Raster OCR, tables, text spotting | No per-language figure for Nordic labels |
| PP-OCRv5 | PaddleOCR 3.x | Apache-2.0 (repo) | Cheap word boxes on CPU | Finnish and Swedish not in its list of text types |
| CHURRO-3B | Qwen2.5-VL-3B base | **qwen-research (NC)** | Text on historic scans | 70.1% on handwriting |
| Qwen3-VL-4B/8B, Qwen3.5-4B | - | Apache-2.0 | Labels, OCR, pointer fine-tune base | Qwen2.5-VL-3B is under the Qwen research licence (NC). Qwen3.5 GRPO runs without vLLM only |
| Molmo2-4B/8B | - | Apache-2.0; trained on some NC data | Pointing as a second witness | No training code released |
| Augraphy | 8.2.6 | MIT | Scan degradation | Python 3.11 with numpy<2. No warps for area sets |
| PDF.js, OpenSeadragon, Set-of-Mark | - | Apache-2.0, BSD-3-Clause, MIT | Sheet viewer, deep zoom, numbered marks | - |
| Data: CubiCasa5K | 5,000 plans | **CC BY-NC 4.0 (NC)**; Stoa applies CC BY-NC-SA | Detector labels (public SVG) | Same images as Stoa's: leak question |
| Data: Swiss Dwellings, MSD, ResPlan | 45,176 apartments; 17,000 plans | CC BY 4.0 | Generator seeds | Swiss Dwellings as answer source is a leak |
| Data: IFC-Bench v2 | 1,027 pairs (card) | CC BY 4.0; some models GPLv3 | Judge rubric, extra dev questions | Holds the answers to our ifc_bench |
| Data: FloorPlanCAD, ArchCAD-400K | 15,663 drawings; 40k samples released | **NC**; ArchCAD gated | Symbol crops | Licence statements conflict (section 6.2) |

## 5. Benchmarks that exist

| Benchmark | What it measures | Best published result | Date | Link |
|---|---|---|---|---|
| AECV-Bench | Exact counts of doors, windows, bedrooms, toilets on 120 floor plans; drawing QA | Mean 0.51 (Gemini 3 Pro); door 0.39, window 0.34 | Jan 2026 | https://arxiv.org/abs/2601.04819 |
| LED-BENCH | Free answers on 107 large sheets, 377 questions | 52.65 (GPT-5.6 Sol) | Oct 2026 | https://arxiv.org/html/2610.19571v2 |
| DrawingVQA | Multiple choice on 33 structural drawings, 92 questions | 77.2 (Gemini 3 Pro); professionals 94.9 | Jul 2026 | https://arxiv.org/html/2607.15418v1 |
| MMArch | 1,212 short answers on architectural figures | 52% proprietary, about 30% open; experts 95% | Aug 2026 | https://arxiv.org/abs/2608.09281 |
| CaseVBench | Bounding boxes on 119 millwork pages, IoU 0.5 | 92 (GPT-6 Astra) | v7, 13 Nov 2026 | https://coxit.co/ai-drawing-benchmark/ |
| TakeoffBench-v1 | Material takeoff on 10 residential plan sets | 81.6 (Handoff-H1, the authors' system); frontier 61.4; estimators 77.6 | Aug 2026 | https://arxiv.org/html/2608.15032v1 |
| AEC-Bench | 196 agent tasks on drawings and specs | Text-catchable about 100%, visual-required about 5% | Mar 2026 | https://arxiv.org/html/2603.29199v1 |
| Construction AI Leaderboard | 5 axes, including AEC-Bench and IFC-Bench-V2 | 73.7 overall (Claude Opus 5.5); 70.2 on drawings at $0.33 per task | 7 Nov 2026 | https://huggingface.co/blog/ONESTRUCTION/construction-ai-leaderboard |
| FloorplanQA | Spatial reasoning on 2,000 single-room layouts, 16,000 questions | 81.38 with JSON, 31.06 with image (GPT-5-mini) | v4, May 2026 | https://arxiv.org/html/2507.07644v4 |
| IFC-Bench v2 | Free-text questions on IFC models, 514 in the test split, LLM judge | 56.0% (adaptive agent, GLM 4.7) | May 2026 | https://arxiv.org/html/2605.01698v1 |
| IFC-MCQ | Multiple-choice IFC retrieval | 100% (a 27B open model); 14 of 17 models over 95% | Oct 2026 | https://arxiv.org/html/2610.30533 |
| OmniDocBench v1.6 | Page parsing | 96.33 (PaddleOCR-VL-1.6) | Jun 2026 | https://arxiv.org/html/2606.03264v1 |
| olmOCR-bench, "Old scans" | OCR on old scans | 51.1 (Chandra 2) | 2026 | https://github.com/datalab-to/chandra |
| CiteVQA | Answer and cited region both right | 76.0 strict attributed accuracy; best open model 22.5 | May 2026 | https://arxiv.org/abs/2605.12882 |

## 6. Claims that failed verification, disagreements, and what I measured

### 6.1 Failed or corrected claims: do not repeat the left column

| Claim (wrong or unsupported) | What the check found | Report |
|---|---|---|
| Frontier models count doors and windows right on about 0.40-0.55 of plans | 0.40-0.55 is the mean over four classes. Doors and windows: 0.39 and 0.34 at best | `vlm`, `cv` |
| Small detectors reach 97% per object with 1,500 training plans | 97% is the detection rate at IoU >= 0.1. The same model has mAP50 67.1. It is not a count metric | `cv` |
| Train on the CubiCasa images that have no Stoa question | About 213 images remain. Use k-fold by drawing | `cv` |
| The RT-DETR floor-plan detector counts toilets and sinks | It has 5 classes: wall, door, window, railing, linkage_point | `rl` |
| Qwen3-VL-8B is the best open model on doors and windows | Nemotron Nano 12B has the best open scores (0.12 and 0.18) | `vlm` |
| DrawingVQA uses IFC models | "IFC" there means "Issued for Construction" | `vlm` |
| The cobbie rubric (exact counts, 2%, cited properties) matches Stoa's scoring | Not supported. It is an LLM judge with 5 binary criteria | `bim`, `agent` |
| IFC agents reach 78.7% on ifc-bench v2 (ECPPM 2026) | No paper or repository with this figure was found | `rl` |
| Claude Opus 5 leads the Construction AI Leaderboard | Opus 5.5 is first overall (73.7) and on drawings (70.2). Opus 5 is first on the BIM axis. Per-model IFC scores were not readable | `bim` |
| Fine-tuned counters collapse on a new drawing style | The test is higher counts (up to 2 times), not a new style. In range 93-100% on synthetic images; real out-of-range 16-34% with points, 2-19% with a direct count | `rl`, `syn` |
| Generic SFT gave no counting gain in Perception-R1 | SFT moved the test score from 50.5 to 59.9. The 74.9 / 72.8 row is "with thinking". The base model differs between the arXiv abstract page (Qwen2.5-VL-3B) and the paper body (Qwen2-VL-2B) | `rl` |
| The best agent resolved 28.6% of Rust issues; a Python port reached parity | Best baseline 21.2%; 28.6% is the authors' own agent. "Near-parity"; on Terminal-Bench Rust is ahead (47.5% against 42.5%) | `stack` |
| Colour-coded confidence gave about 50% less overreliance | The paper reports accuracy: 26%, 58%, 53% | `ux` |
| The Stoa host said the interface weighs 5% | A team member proposed 5%. The host answered "Should be a good ballpark" | `ux` |
| FloorplanQA scores floor plans with a 2% tolerance, like Stoa | 2% is the default; area tasks use 5%. The layouts are single rooms with furniture | `syn` |
| Only RF-DETR XL and 2XL are under PML 1.0; YOLO26 is the newest YOLO | Atto, Femto, Pico, XL and 2XL are PML 1.0. The repository also lists YOLO27 | `vlm`, `stack`, `cv` |
| An Opus call everywhere costs about $0.10-0.19 per question | Unsourced. Estimates: $0.045-0.05 for one call with one image, $0.31 for a 15-call loop | `vlm`, `agent` |
| Preview-set figures: ifc_bench has 249 questions on 5 models; opening_design has 20 DWG files | Full set: 820 questions on 25 models; 271 DWG files | `bim` |

### 6.2 Where reports disagree

| Topic | Value A | Value B | Note |
|---|---|---|---|
| VLM door and window accuracy | "often 0.40-0.55" (abstract quote in `doc`, `agent`, `rl`, `syn`) | best 0.39 and 0.34 (Table 1 in `vlm`, `cv`) | Same paper. Use Table 1 |
| IFC-Bench size | 1,027 pairs (dataset card); 1,027 tasks on 37 models in 21 projects (paper, per `agent`) | 1,026 CSV rows (`bim` M5); 31 models (leaderboard blog, `data/ifc.md`) | Not resolved. Ours: 820 questions on 25 models, 30 IFC files in the folder (M-D) |
| IFC-Bench judge | "four substantive criteria" (`bim`) | "five binary criteria" (`agent`) | Same rubric: abstention plus four |
| cobbie code licence | CC BY 4.0 in the README (`bim`) | GitHub API says NOASSERTION (`agent`) | Read its LICENSE file before copying code |
| PP-OCRv6 in PaddleOCR 3.7.0 | Confirmed from the repository, 50 languages (`cv`, CV-S27) | UNVERIFIED, no source opened (`doc`) | `cv` opened the repository |
| ArchCAD licence on Hugging Face | cc-by-nc-4.0 confirmed on the card (`cv`) | No licence line found in the card (`syn`) | Treat as NC |
| FloorPlanCAD | 35 classes; annotations CC BY-NC 4.0 (`cv`) | 30 classes; card text NC, Hugging Face tag CC BY-SA 4.0 (`syn`) | Treat as NC |
| Temperature 0 | Listed as a determinism measure (`stack`) | The Claude API rejects `temperature` under version 2026-10-21 (`agent`); temperature 0 is not deterministic (`eval`) | Use recorded outputs and replay |
| Historic scans | "about 6,570" (`syn`, `eval`) | 6,701 files: 6,566 JPEG and 135 SVG (M-D; `doc` per-source counts agree) | Use 6,701 |
| opening_design PDFs without text | 91 of 678 with 200 characters or fewer (`doc`) | 74 with no text layer (`data/wild.md`) | M-D: 91 with 200 characters or fewer, 66 with zero characters |

### 6.3 What I measured for this digest (M-D)

Scripts: three small scripts in the session scratch directory. They are not in the repository. All ran on `stoa/data/junction-dataset/`.

- File counts: 1,049 DXF (1,040 Swiss, 9 opening_design), 271 DWG, 611 IFC (533 ifc_models, 48 opening_design, 30 ifc_bench), 1,825 PDF, 6,566 JPEG, 6,327 PNG.
- Questions: 127,044. Targets: png 85,514, pdf 40,342, ifc 1,188. ifc_bench: 820 questions on 25 files. ifc_models: 3,062 on 84 files. opening_design: 64 on 3 files.
- cubicasa5k: 4,787 drawings (3,578 + 943 + 266 by prefix), 24 question strings, mode baseline 47,308 of 85,514 = 55.32%. The mode shares and the count means in sections 2.2 and 2.6 match the reports.
- Swiss DXF rules on 150 floors (seed 0, my own sample): windows 150, apartments 134, door arcs 81, door polylines // 2 101. Door arcs are too many on the other 69 floors and never too few. HATCH is in 150 of 150 files.
- opening_design PDFs (PyMuPDF 2.1, all pages): 587 with more than 200 characters, 437 with a scale string. Both match `doc`.
- Arithmetic checked: 0.97^8.78 = 77%, 0.97^30.7 = 39%, 0.99^8.78 = 92%, 0.99^30.7 = 73%; the MDE table rows for 3.9 and 12.1 points; the $0.036 compile call and $0.0020 per question; 127,044 x $0.314 = about $40,000.
- Not re-run: every other M-R figure, most of all the IFC results in section 2.4 and the Rust figures in section 2.10.

## 7. Source list

"arXiv:ID" means `https://arxiv.org/abs/ID`. Format: id, title or site, link, date, check status from the report. Other ids in brackets are the same source in another report. Only sources that this digest cites or uses in a table are listed.

- **Vision-language models (`vlm`)** VLM-S1 AECV-Bench, arXiv:2601.04819, 2026-01-08, corrected (date, title; QA 0.854 not found) [CV-S1, DOC-S8, AG-S24, RL-S15, SYN-S25]. VLM-S3 LED-BENCH, arXiv:2610.19571, 2026-10-14, confirmed. VLM-S4 DrawingVQA, arXiv:2607.15418, 2026-07-16, corrected (meaning of IFC). VLM-S5 CaseVBench, https://coxit.co/ai-drawing-benchmark/, v7 2026-11-13, confirmed. VLM-S7 FloorplanQA, arXiv:2507.07644, v4 2026-05-25, confirmed [SYN-S24, corrected]. VLM-S8 Aliyev and Barsi, https://pp.bme.hu/ci/article/view/44138, 2026-08-05, partly. VLM-S9 P&ID evidence graph, arXiv:2609.05880, v2 2026-10-29, confirmed [AG-S3]. VLM-S10 Handoff-H1, arXiv:2608.15032, 2026-08-15, confirmed, vendor benchmark [UX-S25]. VLM-S11 Co-DETR plus LLM, arXiv:2509.17283, v2 2025-09-26, confirmed (CVC-FP n=15 not found in text). VLM-S12 MMArch, arXiv:2608.09281, 2026-08-10, confirmed. VLM-S14 Point-then-count, arXiv:2603.21746, v2 2026-05-28, confirmed [RL-S5 and SYN-S6, corrected]. VLM-S16 Claude vision docs, https://platform.claude.com/docs/en/build-with-claude/vision, read 2026-11-13, confirmed. VLM-S17 Claude prices, https://platform.claude.com/docs/en/about-claude/pricing, 2026-11-03, confirmed [AG-S20, EV-S38]. VLM-S18 AEC-Bench, arXiv:2603.29199, 2026-03-31, confirmed [AG-S6]. VLM-S22 VLMs are Biased, arXiv:2505.23941, v4 2026-04-19, confirmed. VLM-S24 Claude coordinates docs, https://platform.claude.com/docs/en/build-with-claude/vision-coordinates, read 2026-11-13, confirmed. VLM-S25 Vision tool-use RL, arXiv:2602.01334, v2 2026-05-21, confirmed.
- **Floor-plan computer vision (`cv`)** CV-S2 VecFormer, arXiv:2505.23395, v3 2025-10-17, confirmed. CV-S5 TempFit, arXiv:2610.17776, 2026-10-13, confirmed (date not checked). CV-S6 CADSpotting, arXiv:2412.07377, v5 2026-08-07, confirmed. CV-S12 CubiCasa5K, arXiv:1904.01920, 2019-04-03, confirmed. CV-S13 RT-DETR floor-plan detector, https://github.com/OldDeLorean/rtdetr-floorplan-detector, read 2026-11-13, confirmed [RL-S16, corrected: 5 classes]. CV-S14 gdino, https://github.com/heypaprika/gdino, read 2026-11-13, confirmed. CV-S18 SAM 3, arXiv:2511.16719, v2 2026-03-28, confirmed. CV-S27 PaddleOCR, https://github.com/PaddlePaddle/PaddleOCR, 3.7.0 2026-06-11, confirmed.
- **Document parsing (`doc`)** DOC-S1 PaddleOCR-VL-1.6 report, arXiv:2606.03264, 2026-06-02, confirmed. DOC-S5 Chandra OCR 2, https://github.com/datalab-to/chandra, 2026-03, confirmed. DOC-S6 CHURRO, arXiv:2509.19768, 2025-09-24, confirmed. DOC-S9 Businessware benchmark, https://www.businesswaretech.com/blog/benchmarking-ai-on-tables-and-engineering-drawings-results-findings, 2025-08, confirmed, industry blog. DOC-S15 dots.mocr, https://huggingface.co/dots-studio/dots.mocr, 2026-03, confirmed.
- **BIM and CAD (`bim`)** BIM-S1 Adaptive exploration on IFC, arXiv:2605.01698, 2026-05-03, confirmed [AG-S1]. BIM-S5 IFC-MCQ, arXiv:2610.30533, 2026-10-21, confirmed. BIM-S10 ifc-lite, https://github.com/LTplus-AG/ifc-lite, read 2026-11-13, confirmed [ST-S7]. BIM-S14 LibreDWG manual, https://www.gnu.org/software/libredwg/manual/LibreDWG.html, 0.13.4 2026-03-17, confirmed.
- **Agents (`agent`)** AG-S2 ChatP&ID, arXiv:2603.22528, 2026-03-23, confirmed. AG-S4 Illusion of Visual Tool-Use, arXiv:2608.06270, 2026-08-06, confirmed. AG-S5 Thinking With Tools, Not With Pixels, arXiv:2608.09682, 2026-08-10, confirmed. AG-S7 Depth of LLM cascades, arXiv:2605.06350, 2026-05-07, confirmed. AG-S9 Early abstention cascades, arXiv:2502.09054, 2025-02-13, confirmed. AG-S10 AbstentionBench, arXiv:2506.09038, 2025-06-10, confirmed [EV-S17]. AG-S11 AgentAbstain, arXiv:2607.10059, 2026-07-11, confirmed. AG-S12 Confidence Dichotomy, arXiv:2601.07264, 2026-01-12, confirmed. AG-S13 Self-evolving code-with-image, arXiv:2608.11292, 2026-08-11, corrected. AG-S16 TestJack, arXiv:2610.10619, 2026-10-07, confirmed. AG-S17 EvilGenie, arXiv:2511.21654, 2025-11-26, confirmed. AG-S19 ReTrace, arXiv:2611.14492, 2026-11-10, confirmed. AG-S20 Claude pricing, https://platform.claude.com/docs/en/about-claude/pricing.md, read 2026-11-13, confirmed. AG-S22 Claude API versioning, https://platform.claude.com/docs/en/api/versioning.md, 2026-11-03, confirmed. AG-S25 DecoyCount, arXiv:2610.34855, 2026-10-26, confirmed.
- **Small models and RL (`rl`)** RL-S1 Perception-R1, arXiv:2504.07954, 2025-04, corrected. RL-S3 Visual-RFT, arXiv:2503.01785, 2025-03, confirmed. RL-S5 = VLM-S14, corrected. RL-S6 CrowdVLM-R1, arXiv:2504.03724, 2025-03, confirmed. RL-S9 R1-V, https://github.com/Deep-Agent/R1-V, 2025-02, confirmed [SYN-S7]. RL-S11 Does RL incentivize reasoning, arXiv:2504.13837, v5 2025-11, confirmed. RL-S12 Spurious Rewards, arXiv:2506.10947, rev. 2026-02, confirmed. RL-S13 RL generalizes, SFT memorizes, arXiv:2611.14912, 2026-11-11, confirmed. RL-S14 MechVQA, https://github.com/xiaofengShi/MechVQA, 2026, confirmed [VLM-S20]. RL-S17 Arctic-Text2SQL-R1, arXiv:2505.20315, rev. 2026-01, confirmed. RL-S18 GEPA, arXiv:2507.19457, v2 2026-02, partly (venue not verified). RL-S21 Unsloth Qwen3.5 guide, https://unsloth.ai/docs/models/qwen3.5/fine-tune, 2026, confirmed.
- **Synthetic data (`syn`)** SYN-S1 Synthetic pre-training for floor plan generation, arXiv:2607.06483, v2 2026-09-21, partly. SYN-S2 SynthPID, arXiv:2604.16513, 2026, partly (venue not stated). SYN-S3 ChartQA, arXiv:2203.10244, 2022, confirmed. SYN-S4 CharXiv, arXiv:2406.18521, 2024-06-26, confirmed. SYN-S10 Metamorphic testing of VQA, https://openaccess.thecvf.com/content/CVPR2021/html/Yuan_Perception_Matters_Detecting_Perception_Failures_of_VQA_Models_Using_Metamorphic_CVPR_2021_paper.html, 2021, confirmed. SYN-S17 Swiss Dwellings v3.0.0, https://zenodo.org/records/7788422, 2023-03-31, partly (confirmed through DataCite) [CV-S29]. SYN-S19 ResPlan, https://github.com/m-agour/ResPlan, v2 2026-08, confirmed. SYN-S20 HouseDiffusion, https://github.com/aminshabani/house_diffusion, read 2026-11-13, corrected. SYN-S21 House-GAN++, https://github.com/ennauata/houseganpp, read 2026-11-13, corrected.
- **Evaluation (`eval`)** EV-S1 Do ImageNet classifiers generalize, arXiv:1902.10811, 2019-02, confirmed. EV-S2 Meta-analysis of overfitting, https://papers.nips.cc/paper/2019/hash/ee39e503b6bedf0c98c388b7e8589aca-Abstract.html, 2019, confirmed. EV-S14 Reliable VQA, arXiv:2204.13631, 2022-04, confirmed. EV-S16 Why language models hallucinate, arXiv:2509.04664, 2025-09, confirmed. EV-S19 Adding Error Bars to Evals, arXiv:2411.00640, 2024-11, confirmed. EV-S23 Judging the Judges, arXiv:2406.12624, rev. 2025-08, confirmed. EV-S24 No Free Labels, arXiv:2503.05061, 2025-03, confirmed. EV-S30 Defeating nondeterminism, https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/, 2025-09-10, confirmed. EV-S31 Non-determinism of "deterministic" settings, arXiv:2408.04667, rev. 2025-04, confirmed. EV-S45 CiteVQA, arXiv:2605.12882, rev. 2026-10, confirmed.
- **Verification UX (`ux`)** UX-S1 Explanations, sources and inconsistencies, arXiv:2502.08554, 2025-02-12, confirmed [EV-S49]. UX-S2 "I'm Not Sure, But...", arXiv:2405.00623, 2024-05-01, confirmed. UX-S3 LLMs help verify, except when wrong, arXiv:2310.12558, 2023-10-19, confirmed. UX-S7 What LLMs know, arXiv:2401.13835, 2024-01-24, confirmed. UX-S8 Verifiability in generative search, arXiv:2304.09848, 2023-04-19, confirmed. UX-S12 LLM-based search, arXiv:2307.03744, v2 2023-11-08, corrected (title of the CHI 2025 version). UX-S13 SymGen, arXiv:2311.09188, v2 2024-04-15, confirmed. UX-S14 Citations and trust, https://doi.org/10.1609/aaai.v39i22.34550, 2025, confirmed. UX-S18 Uncertainty presentation, https://doi.org/10.1145/3637318, 2024, confirmed. UX-S19 HIVE, arXiv:2112.03184, 2021-12-06, confirmed. UX-S20 Feature attribution, arXiv:2105.14944, 2021-05-31, confirmed. UX-S26 Stoa product page, https://stoabuild.com/product, read 2026-11-13, confirmed.
- **Stack (`stack`)** ST-S1 Multi-SWE-bench, arXiv:2504.02605, 2025-04-03, confirmed. ST-S2 Rust-SWE-bench, arXiv:2602.22764, 2026-02-26, confirmed. ST-S3 Codex Rust to Python, arXiv:2604.11518, 2026-04-13, corrected. ST-S4 Rust in Android, https://security.googleblog.com/2025/11/rust-in-android-move-fast-fix-things.html, 2025-11-13, confirmed. ST-S6 dxf-rs, https://github.com/ixmilia/dxf-rs, crate 0.6.2 2026-10-03, confirmed. ST-S8 ifc_rs, https://github.com/MetabuildDev/ifc_rs, 0.1.0-alpha.9 2024-12-04, confirmed. ST-S10 Rust compiler performance survey, https://blog.rust-lang.org/2025/09/10/rust-compiler-performance-survey-2025-results/, 2025-09-10, confirmed.
- **Video (`video`)** VID-S1 3Blue1Brown FAQ, https://www.3blue1brown.com/faq, read 2026-11-13, partly. VID-S2 HyperFrames, https://raw.githubusercontent.com/heygen-com/hyperframes/main/README.md, 2026-11-13, confirmed. VID-S5 Remotion licence, https://raw.githubusercontent.com/remotion-dev/remotion/main/LICENSE.md, 2026, confirmed. VID-S8 Code2Video, arXiv:2510.01174, 2025-10-01, confirmed. VID-S9 TheoremExplainAgent, arXiv:2502.19400, 2025-02-26, confirmed. VID-S10 Kokoro-82M, https://huggingface.co/hexgrad/Kokoro-82M, read 2026-11-13, confirmed. VID-S15 Words per minute, https://en.wikipedia.org/wiki/Words_per_minute, read 2026-11-13, confirmed.
