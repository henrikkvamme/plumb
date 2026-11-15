# Stoa "Make Blueprints Talk" - weekend plan

Accuracy figures are estimates unless marked "measured". Citations come from the research tracks and I did not check them again. I measured the preview counts below tonight from `./stoa-drawings/data/stoa-sample/preview/junction-dataset-preview/questions.jsonl`.

| Source | Questions | Drawings | File the question names |
|---|---|---|---|
| cubicasa5k | 4,270 | 241 | PNG |
| swiss_dwellings | 2,358 | 65 | PDF (DXF sibling exists) |
| ifc_models | 1,049 | 6 | 827 IFC, 222 PDF |
| ifc_bench | 249 | 5 | IFC |
| opening_design | 64 | 3 | PDF |

## 1. Top 3 approaches

| # | Approach | Acc | Verify | Creative | Cost | 36 h |
|---|---|---|---|---|---|---|
| 1 | **Fact Sheet**: compile each drawing once (geometry solvers, trained detector, OCR), answer by query, Claude judges only disputed marks | 4 | 5 | 4 | 5 | 4 |
| 2 | **Pointer VLM**: Qwen3.5-4B LoRA plus count reward | 3 | 4 | 4 | 4 | 2 |
| 3 | **Opus with Set-of-Mark** on everything (current Drawing Desk, improved) | 2 | 4 | 2 | 1 | 5 |

**1. Fact Sheet - build this.**
- Frontier models get door and window counts exactly right on at most about 0.55 of plans, and 0.15-0.43 in the per-model CSVs (https://arxiv.org/abs/2601.04819).
- Small supervised detectors reach 97% per-object detection on doors and windows with only 1,500 training plans (https://github.com/heypaprika/gdino). RT-DETR-L reaches about 90 AP50 in 2.3 h on 2xA100 (https://github.com/OldDeLorean/rtdetr-floorplan-detector).
- The evidence-graph pattern raised exact match from about 39% to about 75% on P&ID questions (https://arxiv.org/abs/2609.05880).
- Swiss rules already score about 97% at $0 (measured on the preview).
- About 18 questions share one drawing, so the per-question cost is near zero.

**2. Pointer VLM - stretch only.**
- It fits Stoa's "small fine-tuned model" request, and counting the points works (https://arxiv.org/abs/2603.21746).
- No number exists for this task. Generic SFT gave no counting gain in Perception-R1 (https://arxiv.org/abs/2504.07954). Qwen3.5 tooling for GRPO is untested.
- It costs 5-15x less than Haiku at best, and only on a busy GPU.

**3. Opus everywhere - fallback and baseline only.** It works today, but it costs about $0.10-0.19 per question and counts symbols badly.

**Dropped:** the GRPO Question Compiler. Exact template lookup already covers 95.0% of held-out preview questions (measured). Symbol Twin is also dropped: no preview question needs it.

## 2. Architecture

**Router ($0).** It routes by file type and source folder. Slot regex plus exact template lookup gives a typed query. On a miss, Haiku 5.5 with a strict JSON schema parses the question (about $0.0003). Free-form questions go to the agent.

**Compile once per drawing into a fact sheet (JSON, cached).**

| Component | Answers | Expected accuracy |
|---|---|---|
| Swiss DXF solver (ezdxf + shapely), PDF text as cross-check | 30% of questions: room, door, window, toilet counts and net areas | 97% measured, 99% target. The rules were fitted on the same 65 floors |
| Symbol detector | cubicasa windows, doors, WC seats, sinks, showers+bathtubs | doors and windows 60-80%, toilets and sinks 80-90%, showers and bathtubs 40-70% |
| Room and floor detector, plus PaddleOCR labels (MH, KH/PH/PESUH/SH, WC, S, K) | cubicasa bedrooms, bathrooms, WC rooms, saunas, kitchens, storeys | 85-95% |
| IFC recipes (Qto, storeys, spaces) | ifc_models: 13% of questions on only 6 models | 90% target, unmeasured |
| CodeAct IfcOpenShell agent on Sonnet 5.5, max 15 code runs, cites class and property | ifc_bench free text | 55-65%. GLM-4.7 reached 56% (https://arxiv.org/abs/2605.01698) |
| Schedule table rebuild from PDF word boxes, Haiku writes the filter | opening_design (0.8%) | unknown, lowest priority |

The blended estimate is 80-85%. cubicasa decides it, at about 75%.

**Verifier (deterministic).**
- The count must equal the number of accepted marks.
- The polygon area must match the printed label within 0.5%.
- Two witnesses must agree. The detector count must not change under flip and rotation. Fixture counts must fit the OCR and room evidence, for example each WC room holds a toilet.
- Agreement gives a green badge. Disagreement sends only the disputed crops to one Claude call with numbered marks (accept or reject by ID).
- Exactly two tiers. Deeper cascades gave no gain in 118 of 135 comparisons (https://arxiv.org/abs/2605.06350).
- If the judge does not raise held-out accuracy, we do not call it. We show amber and return the detector count.

**UI (Contact Sheet).**
- Counts: numbered marks, one crop per object, and a "not counted" row with the nearest rejected candidates. A click toggles a mark and updates the count.
- Areas: the polygon, the shoelace tape, the printed label and the 2% band.
- IFC: a ledger with one row per GlobalId.
- Each answer shows its path, its tier and its cost. A cost meter compares the run with Opus alone.
- Evidence and visible disagreement come first, not prose (https://arxiv.org/abs/2502.08554).

**Cost target:** under $0.005 per question blended.

## 3. Verda training plan

**Data.** CubiCasa5K, Zenodo 2613548, 5.5 GB, CC BY-NC-SA 4.0. Labels come from `model.svg`, parsed with CubiCasa's `house.py` logic (https://github.com/CubiCasa/CubiCasa5k). The converter base is https://github.com/xmarva/floorplan-detection.

**Classes.**
- Model A, symbols: window, door, toilet, urinal, sink, bathtub, shower, sauna_bench, sauna_stove.
- Model B, rooms and floors: bedroom, kitchen, bath, sauna, wc_room, other_room, floor (one box per floor group).
- Do not use the default 11-class mapping. It merges Toilet with Urinal and drops showers.

**Calibration gate before training.** Compute counts from the SVGs for the 241 preview drawings and compare them with Stoa's answers. Fix the class mapping until each template agrees at least 95%. This settles double doors, "with leaf" and the shower group. If a template stays below 95%, Stoa did not derive it from the SVG. Then use text or rules for it.

**Runs.**

| Run | Model | GPU | Hours | Cost |
|---|---|---|---|---|
| A | Ultralytics YOLO11m, imgsz 1536 (1280 if VRAM is short), 120 epochs, mosaic, flips, 90-degree rotation | 1A100.22V, `--hours 7` | 4-5 | about $12 |
| B | YOLO11m, imgsz 1024, 80 epochs, same VM after A | 1A100.22V | 1-1.5 | about $3 |
| C (Saturday evening, one choice) | Retry A with fixes. If A is good: RF-DETR-M (Apache-2.0, https://github.com/roboflow/rf-detr) as a second witness and licence-clean variant | 1A100.22V | 4 | about $10 |

- Total is about $25-30. No V100: it has no bf16, and the saving is small.
- Tonight's fallback is the OldDeLorean RT-DETR-L weights for doors and windows.

**Eval split.**
- Train: the CubiCasa train split minus every id in Stoa's question file.
- Tune thresholds for exact-count accuracy, not mAP, on the CubiCasa val split minus Stoa ids.
- Test: the 241 preview drawings. None is in training. Report per template.
- Split by drawing, never by question.

**Leakage risks.**
- The full set probably holds most of the 5,000 plans, so hidden test drawings can be in our training set. The clean fix: about 60% of full-set drawings have no question. If we get the full question file, train only on CubiCasa plans without a Stoa question.
- We never look up an SVG by filename at inference. The pitch says this.
- The weights are non-commercial (CC BY-NC-SA data, AGPL Ultralytics). We disclose it to Stoa.
- CubiCasa labels are noisy, so some reference answers are wrong. The ceiling is below 100%.

## 4. Timeline (Fri 22:00 to Sun 10:00)

Three workstreams: **CV** (Verda), **GEO** (solvers, router, harness), **UI** (evidence and pitch).

| Time | CV | GEO | UI |
|---|---|---|---|
| Fri 22-24 | Start the VM, download CubiCasa, write the split map and the SVG converter | Scoring harness. Current Claude baseline on 300 questions through Batch. Mode-answer baseline | Define the evidence JSON contract: marks, polygons, ledger, cost |
| Sat 00-02 | Calibration gate. Start run A by 02:00 | Port the measured Swiss rules into Drawing Desk | Mark overlay and crop grid on mock data |
| Sat 02-08 | Runs A and B, unattended | Template lookup and Haiku fallback. IFC recipes measured against the 6 models | Rest |
| Sat 08-12 | Tune thresholds. Add tiling for large images. **First real cubicasa number** | WC and washbasin split, outdoor label lists, apartment area misses | Area tape, IFC ledger |
| Sat 12:00 | **Gate:** each class uses the detector only where it beats the Claude baseline | | |
| Sat 12-18 | OCR room labels. Fact sheet per drawing. Witness checks | ifc_bench agent with a Haiku judge copied from the cobbie rubric | Wire real fact sheets. Toggle and recount |
| Sat 18-24 | Disputed-crop judging, measured. Start run C | opening_design schedules, only if all else is green | "Not counted" row, cost meter, path chips |
| Sun 00-04 | Full preview eval per source and template. **Freeze at 04:00** | Fixes from the eval only | Deploy with `infra/dokploy/host.sh` |
| Sun 04-10 | Pull weights, `pnpm j gpu down`, check `pnpm j gpu ls` | Accuracy against cost chart | Pitch, demo video, submit by 09:00 |

**Cut order:** Pointer VLM, RF-DETR witness, opening_design, Haiku parser. Never cut the harness or the evidence UI.

## 5. Five citations for the pitch

1. **AECV-Bench** (https://arxiv.org/abs/2601.04819) - frontier models leave door and window counting "unsolved". This is our 53% slice.
2. **Grounded and Faithful P&ID Reasoning** (https://arxiv.org/abs/2609.05880) - CV builds an evidence graph and a small model queries it: +35 points exact match. This is our architecture.
3. **ifc-bench v2 / cobbie** (https://arxiv.org/abs/2605.01698, https://github.com/sylvainHellin/cobbie) - an exploring IfcOpenShell agent beats static queries by 37 points. Its rubric (exact counts, 2%, cited properties) matches Stoa's scoring.
4. **heypaprika/gdino** (https://github.com/heypaprika/gdino) - Grounding DINO scores 0.0 mAP50 zero-shot on CubiCasa symbols, and a small supervised detector reaches 97% detection. Bigger general models do not make domain training obsolete.
5. **Fostering Appropriate Reliance on LLMs, CHI 2025** (https://arxiv.org/abs/2502.08554) - sources and visible inconsistencies reduce overreliance, and explanations increase it. This is why we show marks and disputes.

## 6. Questions for the Stoa track owner

1. How do you score: a hidden test set with automatic scoring, or the demo and pitch only?
2. How do you count inference cost: API dollars, GPU seconds, or both? Does one-off precompute per drawing count?
3. Swiss questions name the PDF. May we read the DXF sibling of the same drawing?
4. May we train on the public CubiCasa5K SVG annotations? Are test drawings in its train split? Can you give us the list of evaluated drawings to hold out?
5. Were the cubicasa answers generated from those SVGs? What are the rules for double doors and "door with leaf"?
6. How do you score free-text answers: an LLM judge, which rubric?
7. Does the full set have questions on the historic scans (habs, finna, europeana, wikimedia), or templates and languages beyond the preview?
8. May the system abstain or mark "needs review", and how is that scored?
9. Are non-commercial weights (CC BY-NC-SA data, AGPL code) acceptable for judging?
10. What does "verified in seconds" mean to your engineers: marks on the plan, a list, or a tolerance band?