# Vision-language models on floor plans and construction drawings (state at 13 November 2026)

Track: how good are frontier and open vision-language models (VLMs) on floor plans, engineering drawings and
construction documents, and what works around their limits.

Labels used in this file:

- **MEASURED (source)**: a number that a cited source reports. I opened the source. The source id is in brackets.
- **DERIVED**: arithmetic on measured numbers. The inputs are named.
- **ESTIMATE**: my own judgement or a calculation with an assumed input. Do not quote it as a result.

## Findings that change decisions

1. **Do not let a VLM count doors and windows.** On 120 floor plans (partly CubiCasa5K, our biggest source),
   the best exact-match rate in January 2026 was 0.39 for doors and 0.34 for windows (Gemini 3 Pro). Claude
   Opus 4.5 scored 0.16 and 0.16. Open models scored 0.09-0.12 on doors and 0.03-0.18 on windows (Qwen3-VL-8B and
   GLM-4.6V tie for best open mean at 0.39; Qwen3-VL-8B has 0.09 and 0.10). Bedrooms (up to 0.91) and toilets (up
   to 0.82) are easy because a text label marks them. MEASURED [S1]. Counts must be exact in Stoa's
   scoring, so this moves accuracy directly. Use a detector or vector geometry for symbol counts. Use the VLM
   for labels and text.
2. **Nobody has re-run a floor-plan symbol-counting benchmark on the 2026 frontier models.** AECV-Bench lists
   only models up to Gemini 3 Pro, GPT-5.2 and Claude Opus 4.5 [S1, S2]. The newest models are much better
   at layout and at boxing large objects: on CaseVBench (millwork drawings, boxes at IoU 0.5) GPT-6 Astra
   scores 92 and Claude Opus 5.5 79, at $0.186 and $0.040 per page. MEASURED [S5]. On Blueprint-Bench 2,
   Gemini 4 Carbon ties the human baseline (0.586), but that human baseline was tested on only 12 apartments, and
   the task is photos to floor plan, not reading a drawing. MEASURED [S6]. CaseVBench also lists Claude Fable 5.2
   at 85 and Gemini 4 Carbon at 83, both above Opus 5.5 [S5]. But no source shows exact counts of small
   line-art symbols on 2026 models. ESTIMATE: the gap is closing for large objects and layout, and is open for
   small symbols. Measure it ourselves on our own split before we spend on it.
3. **Give the model structure, not pixels.** On FloorplanQA, GPT-5-mini scores 81.38 with the layout as JSON
   and 31.06 with only a rendered image. A Python tool adds 30 to 43 points on distance, angle, visibility and
   placement for GPT-4.1. MEASURED [S7]. For room areas, open VLMs had about 43% MAPE (three were tested and only two gave outputs that could be
   scored; the 43% is the paper's headline figure), and a pixel count of the colour mask had 1.58% MAPE at floor-plan
   level and 5.68% per room, on colour-coded plans. MEASURED [S8]. The area tolerance is 2%. DERIVED: VLM area
   estimates fail the tolerance. Areas must come from polygons (DXF, IFC, vector PDF) or segmentation plus a
   scale, and the LLM must only call the computation.
4. **Hybrids beat frontier models, most of all on unusual drawing styles.** An evidence graph raised P&ID
   topology exact match from 36.7-41.3% (image only) to 74.3-76.0% with 4B to 8B open VLMs. MEASURED [S9].
   A CV-plus-agent takeoff system scored 81.6 against 61.4 for the best frontier model and 77.6 for human
   estimators. MEASURED [S10] (vendor's own benchmark). Co-DETR door detection plus GPT-5 counted toilets
   right on 86.67% of CVC-FP plans against 40.00% for GPT-5 alone, and on CubiCasa5K 87.63% against 85.57%.
   MEASURED [S11] (CVC-FP has only 15 images). The hybrid gain is small on CubiCasa and large on other styles.
   ESTIMATE: that is exactly the risk profile of the hidden test set, so a hybrid moves accuracy most there.
5. **For large sheets, send overlapping crops in one call.** On LED-BENCH (377 questions, large sheets, four
   models), whole-sheet answering scored 36.38. Full sheet plus four fixed overlapping crops in one call scored
   49.34 (+12.96). Search-then-reread with 3 calls scored 49.74 (+13.35). Locate-then-reread with 3 calls
   scored 41.43 and lowered mechanical accuracy from 44.12 to 36.47. MEASURED [S3]. Fixed crops give almost the
   whole gain at one third of the calls. That moves both accuracy and cost.
6. **The best 2026 model is still near 50% on hard drawing QA.** LED-BENCH: GPT-5.6 Sol 52.65 (October 2026).
   MEASURED [S3]. MMArch: best proprietary 52%, best open about 30%, experts 95%. MEASURED [S12]. DrawingVQA
   (33 "Issued for Construction" structural drawings; IFC here is not the BIM file format): Gemini 3 Pro 77.2 on multiple choice (random is 27.2), professionals 94.9; quantity takeoff is the weakest
   dimension, and Gemini 3 Pro scored lower there (33.3) than Gemini 2.5 Pro (41.7). MEASURED [S4]. Newer is
   not always better at counting.
7. **Make the model point, then count in code.** VLMs often encode the right count inside but say a wrong
   number; probes find the error, and selective re-prompting adds up to 15.6 points. MEASURED [S13]. Point-then-
   count gives the best counting accuracy and better out-of-distribution results, with points grounded in more
   than 94% of cases. MEASURED [S14]. Caveat: S14 tests open 3-8B models (Qwen2.5-VL, LLaVA-OneVision, InternVL3.5, Gemma 4 E4B) on synthetic shapes and OCID photos, not on drawings and not on Claude or Gemini. Google's code-execution "agentic vision" draws numbered
   boxes to count and gives 5-10% on most vision benchmarks, and a building-plan checker gained 5%. MEASURED
   [S15] (vendor). Each point or box is also the evidence a person checks. That moves verifiability.
8. **A VLM look at one image is cheap; the risk is accuracy, not cost.** Claude caps an image at 2,576 px long
   edge and 4,784 visual tokens; Opus 5.5 costs about $19.14 per 1,000 such images in input. MEASURED [S16].
   Haiku 5.5 is $0.10 per million input tokens [S17]. DERIVED: one full-size image in Haiku 5.5 costs about
   $0.0005 in input. But cheap models are weak at drawing grounding: on CaseVBench GPT-6 Luna scores 23 and
   Claude Sonnet 5 scores 21. MEASURED [S5]. ESTIMATE: use a strong model only on the few crops a detector is
   unsure about, not a cheap model on everything.
9. **Images alone did not help agents on visual drawing checks.** In AEC-Bench, defects that text can catch
   score about 100%, defects that need visual inspection about 5%, and more rendering of pages "does not lead to
   better performance on visually grounded tasks". MEASURED [S18]. Do not expect "render the PDF and ask" to
   fix opening_design or ifc_models plan sheets.
10. **No published benchmark scores calibration or abstention on drawings.** None of S1 to S6 or S12 reports
    confidence calibration or an "I do not know" rate. ESTIMATE: Stoa asked for both, so our own abstention
    metric (accuracy at coverage) is a differentiator with no prior art to compare against.

## Landscape

### Drawing benchmarks with measured model results

| Benchmark (date) | Data | Task | Best model result | Human | Source |
|---|---|---|---|---|---|
| AECV-Bench (Jan 2026) | 120 floor plans (CubiCasa5K, CVC-FP, web); 192 QA on 21 drawings | Count doors, windows, bedrooms, toilets; OCR, counting, spatial QA | Mean count acc 0.51 (Gemini 3 Pro); door 0.39, window 0.34; QA 0.854 (NOT FOUND in the paper text or tables; UNVERIFIED, may be in a figure) | none | S1, S2 |
| DrawingVQA (Jul 2026, CVPR 2026 Findings) | 33 structural drawings "Issued for Construction" (IFC), 92 QA | Multiple choice, 3 depths | 77.2 (Gemini 3 Pro preview) | Professionals 94.9 | S4 |
| LED-BENCH (Oct 2026) | 107 large sheets, 377 QA, mech/arch/transport | Free answer on full sheets | 52.65 (GPT-5.6 Sol); architecture 48.89 | none | S3 |
| MMArch (Aug 2026) | 1,212 short answers from paper figures | Perceive, know, judge | 52% proprietary, about 30% open | 95% | S12 |
| CaseVBench (live, v7 13 Nov 2026) | 119 pages, 1,430 objects, millwork | Bounding boxes, IoU 0.5 | 92 (GPT-6 Astra), $0.186/page | none | S5 |
| Blueprint-Bench 2 (live) | Apartment photos to floor plan | Room graph | 0.586 (Gemini 4 Carbon) | 0.586 | S6 |
| TakeoffBench-v1 (Aug 2026) | 10 residential plan sets | Material takeoff, 9 trades | Frontier 61.4 (Claude Fable 5); hybrid 81.6 | 77.6 | S10 |
| AEC-Bench (Mar 2026) | 196 agent tasks | Drawing and spec review | Per task; visual-required callouts about 5% | none | S18 |
| Construction AI Leaderboard (Nov 2026) | 5 axes incl. AEC-Bench, IFC-Bench-V2 | Aggregate | Opus 5.5 73.7 overall; 70.2 on drawings at $0.33/task | none | S19 |
| FloorplanQA (ICML 2026) | 2,000 symbolic layouts, 16,000 QA | Spatial reasoning, text input | 75-95% metric tasks with tools; image-only far lower | none | S7 |
| MechVQA (ICML 2026) | 3.3k mechanical drawings, 21K QA | 10 tasks | Fine-tuned MechVL beats best closed model by 7.57 pp | none | S20 |

Not found: a P&ID QA benchmark with frontier-model scores other than TopoPID-VQA [S9]. Construction's Last Exam
(Togal) has a 33-task geometry release (areas, counts, linear), but its leaderboard did not load for me, so I
have no scores. UNVERIFIED [S21].

### AECV-Bench counting, full table (exact-match accuracy, MEASURED [S1])

| Model | Mean | Door | Window | Bedroom | Toilet | Mean MAPE % |
|---|---|---|---|---|---|---|
| Gemini 3 Pro | 0.51 | 0.39 | 0.34 | 0.89 | 0.82 | 16.0 |
| GPT-5.2 | 0.49 | 0.28 | 0.27 | 0.91 | 0.76 | 19.4 |
| Claude Opus 4.5 | 0.42 | 0.16 | 0.16 | 0.91 | 0.76 | 24.9 |
| Grok 4.1 Fast | 0.37 | 0.09 | 0.17 | 0.73 | 0.67 | 28.4 |
| GLM-4.6V (open) | 0.39 | 0.09 | 0.03 | 0.79 | 0.82 | 29.5 |
| Qwen3-VL-8B (open) | 0.39 | 0.09 | 0.10 | 0.76 | 0.81 | 30.5 |
| Nemotron Nano 12B v2 VL (open) | 0.38 | 0.12 | 0.18 | 0.70 | 0.75 | 35.4 |

The paper names the failure modes: models "misinterpret door swings, confuse windows with openings or facade
elements, hallucinate fixtures, or miss instances in dense regions" [S1].

### Why counting fails (mechanisms with evidence)

| Mechanism | Evidence | Source |
|---|---|---|
| Count is encoded inside but read out wrong | Probes detect counting errors; steering the count direction helps; up to +15.6 pp with selective re-prompt | S13 |
| Priors override pixels | 17.05% average counting accuracy on modified familiar objects (for example a 4-stripe Adidas logo) | S22 |
| Density and adjacency | Dense scenes are the hardest category; top models degrade from perception to analytical counting | S23 |
| Downscaling loses small symbols | Claude: "Small elements lose precision when an image is downscaled"; counts "might not always be precisely accurate, especially with large numbers of small objects" | S16, S24 |
| Lost place while tracing | DrawingVQA: models "visually derailed while tracing" and "stop after identifying the first plausible link" | S4 |

### High-resolution strategies

| Strategy | Evidence on drawings or high-res | Calls | Source |
|---|---|---|---|
| Full sheet plus 4 fixed overlapping crops | +12.96 pp on LED-BENCH | 1 | S3 |
| Search then reread | +13.35 pp | 3 | S3 |
| Locate then reread | +5.05 pp, but hurts mechanical | 3 | S3 |
| Code-execution zoom (Gemini agentic vision) | +5-10% on vision benchmarks; +5% on a plan checker | many | S15 |
| RL-trained zoom agents (DeepEyes and others) | Gains are "dominated by intrinsic learning"; tool RL "learns to coexist safely with tools rather than master them" | many | S25 |
| Higher input resolution | "Higher input resolution generally improves accuracy, particularly for GPT-5.6 Sol and Gemini 3.5 Flash" | 1 | S3 |

### Grounding output from current APIs

| Provider | Format | Limits | Source |
|---|---|---|---|
| Claude (4.7 and later, high-res tier) | Absolute pixel coordinates `[x1, y1, x2, y2]`; "does not work well" with 0-1000 normalised coordinates | 2,576 px long edge, 4,784 visual tokens; tokens = ceil(w/28) x ceil(h/28); PDF pages rasterised server side, so coordinates do not map back | S24, S16 |
| Gemini | `box_2d` = `[ymin, xmin, ymax, xmax]` normalised 0-1000; masks also available | 258 tokens per 768x768 tile | S26 |
| Gemini 4 Argon | 85.1% mAP@50 text-prompted detection (Roboflow, natural images) | 13-20 s per request | S27 |
| Molmo 2 (open, Apache 2.0) | Points; counting trained through pointing | 4B / 8B | S28 |

### Price per image and per question

| Model | Input $/M | Output $/M | Source |
|---|---|---|---|
| Claude Opus 5.5 | 4.00 | 20.00 | S17 |
| Claude Sonnet 5.5 | 2.00 | 10.00 | S17 |
| Claude Haiku 5.5 | 0.10 | 0.50 | S17 |
| Gemini 4 Argon / Carbon | 2.00 (4.00 from 1 Dec 2026) | 10.00 (20.00) | S29 |
| Gemini 3.8 Flash | 0.75 (1.50 from 1 Jan 2027) | 3.75 (7.50) | S29 |
| Gemini 3.5 Flash-Lite | 0.30 | 2.50 | S29 |
| GPT-6 Astra | 10.00 | 50.00 | S30 |
| GPT-6.1 Sol | 2.00 | 10.00 | S30 |
| GPT-6.1 Terra | 1.00 | 5.00 | S30 |
| GPT-6 Luna | 0.10 | 0.50 | S30 |

All three providers list batch at 50% of standard [S29, S30]; Claude batch is in the Claude API skill docs.

Measured cost per drawing page, CaseVBench box task: Claude Opus 5.5 $0.040, Gemini 4 Argon $0.021, Claude
Sonnet 5.5 $0.020, GPT-6 Astra $0.186, GPT-6 Luna $0.004. MEASURED [S5]. Measured on AEC-Bench agent tasks:
Opus 5.5 $0.33 per task, GPT-6.1 Sol $0.12, Sonnet 5.5 $0.14. MEASURED [S19].

ESTIMATE, per question with one full-resolution image and about 1,500 output tokens (with thinking):
Opus 5.5 about $0.05; Sonnet 5.5 about $0.025; Haiku 5.5 about $0.001; Gemini 3.8 Flash about $0.007. The
input part is DERIVED from S16 and S17 (4,784 tokens). The output token count is an assumption. OpenAI does not
publish an image-token formula for the GPT-6 models on its pricing page [S30], so I give no GPT figure.

DERIVED from the lead's measured counts: cubicasa5k has 85,514 questions on 4,787 plans, 17.9 questions per
plan. If one model pass per drawing builds a fact sheet that answers all questions, the per-question cost is
about 1/18 of the per-drawing cost.

### Best published hybrid pipelines

| System | Pattern | Result | Source |
|---|---|---|---|
| Graph-Grounded Harness (P&ID) | Tiled symbol detection, line masks, OCR, connection graph; VLM answers only through 7 read-only graph operators and must cite results | 36.7-41.3% to 74.3-76.0% exact match (Qwen3-VL-4B/8B, Gemma-4-E4B) | S9 |
| Handoff-H1 (takeoff) | Purpose-built CV primitives, tool-using agents with CV-backed counting, knowledge base | 81.6 vs 61.4 frontier vs 77.6 human | S10 |
| Co-DETR + GPT-5 CoT (facility counts) | Door detector, room connection, consolidation, omission correction | Toilets CVC-FP 86.67 vs 40.00; SESYD 95.83 vs 68.75 | S11 |
| Training-free agentic CV (structural plans) | Deterministic primitives, scale by dimension-ratio consensus, VLM proposes typed corrections that deterministic tests admit or reject, fail-closed | Scale within 0.1% on every held-out drawing; column recall 0.922, precision 0.997 | S31 |
| Evidence-gated floor-plan parsing (SALI-FP) | Multimodal pipeline to reviewable semantic maps, vectors and relation records; edits gated by image evidence | 11,534 plans processed in a production audit; no accuracy in abstract | S32 |
| Wall detection plus sequence model fusion | Deterministic fusion of two trained vectorisers (CubiCasa5K, ResPlan-FP) | +7 wall F1 from fusion; zero-shot Gemini 3.1 Pro wall F1 0.811 at tolerance 0.05 and 0.472 at 0.015, on a 200-plan ResPlan-FP subset (clean renders, not CubiCasa) | S33 |

The common design: deterministic perception produces a typed evidence store; the LLM only plans, queries and
explains; every claim cites a primitive. S31 also holds out a seed-disjoint half after rules were frozen. That
is the evaluation discipline Stoa's hidden test needs. Caveat: S31's plans are author-generated and both halves share one
generator, so the paper says it does not address independently drawn plans.

## What we can use this weekend

| Item | What | Licence | Effort | Moves |
|---|---|---|---|---|
| Point-then-count prompt contract | Ask Claude for pixel boxes (pre-resized image) or Gemini for `box_2d`; count the list in code; draw numbered marks as evidence | n/a | 2-3 h | Accuracy, verifiability |
| Claude image pre-resize | Resize to fit 2,576 px and 4,784 tokens with the reference `resized_size()` [S24]; set `"transformations": {"oversized_image": "error"}` so a silent resize fails loudly | n/a | 1 h | Accuracy of coordinates |
| Fixed overlapping crops | Full sheet plus 4 overlapping crops in one request for large PDF sheets (opening_design, ifc_models plans) | n/a | 1-2 h | Accuracy at 1 call [S3] |
| Disputed-crop verifier | Detector proposes candidates; only low-confidence candidates go to Opus 5.5 or Gemini 4 Argon as numbered crops, answer accept or reject per id | API | 3-4 h | Accuracy, cost |
| Graph-operator harness | LLM gets read-only operators over our fact sheet (rooms, openings, polygons, labels) and must cite operator results [S9 pattern] | n/a | 4-6 h | Verifiability, creativity |
| RF-DETR N/S/M/L | Symbol detector for doors, windows, fixtures; `pip install rfdetr` gives only Apache 2.0 code and models; Atto, Femto, Pico, XL and 2XL are PML 1.0 via `rfdetr[plus]` | Apache 2.0 | CV track | Accuracy |
| Qwen3-VL-8B-Instruct | Open VLM for labels and OCR (32 languages); weak at symbol counts (door 0.09 [S1]) | Apache 2.0 | 2 h to serve on Verda | Cost |
| Molmo 2 (4B/8B) | Pointing model, counts by pointing; fine-tune candidate | Apache 2.0 (code and weights: HF cards for Molmo2-4B and Molmo2-8B list apache-2.0) | 6+ h | Creativity, "small fine-tuned model" |
| AECV-Bench data | 120 counting plans as an external sanity check; contains a CubiCasa5K subset, so check overlap with our data before using it as held-out | No licence file in repo: internal evaluation only | 1 h | Evaluation trust |
| Batch APIs | 50% off for evaluation sweeps on all three providers | n/a | 0.5 h | Cost |

Concrete calls:

- Claude: model `claude-opus-5-5` (effort `medium` is the default, set it explicitly) or `claude-haiku-5-5`;
  structured outputs with a schema `{items: [{id, label, box: [x1,y1,x2,y2]}]}` [S24]. Opus 5.5 rejects
  forced `tool_choice`; use structured outputs instead (Claude API skill docs).
- Gemini: model `gemini-4-argon` or `gemini-3.8-flash`, prompt "The box_2d should be [ymin, xmin, ymax, xmax]
  normalized to 0-1000" [S26]; enable code execution for agentic zoom [S15].

## What does not work

| Claim | Evidence | Source |
|---|---|---|
| Zero-shot VLM door and window counts on floor plans | Best 0.39 / 0.34 exact match; open models 0.03-0.18 | S1 |
| VLM area estimation | MAPE about 43% vs 1.58% for pixel counting | S8 |
| Rendered images instead of structured layout | 31.06 vs 81.38 (GPT-5-mini) | S7 |
| A Python tool for planning-type spatial tasks | Max Box 7.5 to 3.0, Shortest Path 25.0 to 12.5 with tools | S7 |
| Locate-then-reread crops | Mechanical accuracy 44.12 to 36.47 | S3 |
| More page rendering for agents | "does not lead to better performance on visually grounded tasks"; visual callouts about 5% | S18 |
| Text extraction alone for layout questions | pdftotext "collapses spatial layout and geometric relationships into linear text" | S18 |
| Cheap frontier tiers for grounding | GPT-6 Luna 23, Claude Sonnet 5 21, DeepSeek V4.1 Flash 16 on CaseVBench | S5 |
| Expecting the next model to fix counting | Gemini 3 Pro scored lower on DrawingVQA quantity takeoff (33.3) than Gemini 2.5 Pro (41.7) | S4 |
| Tool-use RL as a fix for perception | Gains mostly intrinsic; "limited progress in tool-based correction of intrinsic failures" | S25 |
| Thinking more on counting | Counting accuracy rises to about 40% with thinking tokens, then declines with excessive reasoning | S22 |
| Normalised coordinates from Claude | Docs: Claude "does not work well" with 0-1000 coordinates | S24 |
| Sending PDFs to Claude when you need coordinates | Pages are rasterised server side, "coordinates can't be reliably mapped back onto the page" | S24 |

## Open questions

1. How do Claude Opus 5.5, Gemini 4 Argon and GPT-6 Astra do on exact door and window counts on our own
   CubiCasa held-out split? No source measures it. A 200-plan run through batch costs ESTIMATE under $10.
2. Do Gemini `box_2d` boxes beat Claude pixel boxes on small line-art symbols? CaseVBench tests large objects
   only [S5]. Roboflow tests natural images only [S27].
3. Is a VLM's stated confidence calibrated on drawings? No source measures it (finding 10).
4. What is the image-token formula for GPT-6 models? Not on the OpenAI pricing page [S30].
5. Does the S13 probe-based error detector work for API models? It needs activations, so only for open
   models we host.
6. How much of the hidden test set is historic scans without a scale bar? For those, the honest area answer
   is "I do not know, give me a scale", and S31 shows scale can be estimated by dimension-ratio consensus when
   dimensions are printed.
7. Point-then-count numbers in S14 are from open 3-8B models on synthetic shapes and OCID, and TakeoffBench is the
   vendor's own benchmark; neither says how Claude or Gemini do on drawings.

## Check of the prior research

Scope: the prior-research claims on VLM performance, benchmarks, hybrids and cost
(`weekend-plan.md` section 1 and `research-tracks.json` track 3).

| Prior claim | Verdict | Detail |
|---|---|---|
| AECV-Bench: frontier door and window counts right "on at most about 0.55 of plans, and 0.15-0.43 in the per-model CSVs" | Correct the numbers | Paper Table 1: best door 0.39, best window 0.34; range across models door 0.09-0.39, window 0.03-0.34 [S1]. "0.40-0.55" is the abstract's range for mean accuracy and QA counting, not door/window. I did not open the CSVs. |
| AECV-Bench counts "doors, windows, spaces, bedrooms and toilets" and repo results are "updated through current models" | Correct | The January 2026 paper counts 4 classes, no spaces [S1]. The repo lists only models up to Gemini 3 Pro / GPT-5.2 / Opus 4.5 [S2]. |
| Co-DETR + LLM beats GPT-5: CubiCasa toilets 87.63 vs 85.57, CVC-FP 86.7 vs 40.0, SESYD 95.8 vs 68.8 | Confirmed | Exact numbers in S11. Add: CVC-FP n=15, SESYD n=48, toilets only for those sets. |
| P&ID evidence graph: about 39% to about 75% exact match | Confirmed | 36.7-41.3% to 74.3-76.0%, Qwen3-VL-4B/8B and Gemma-4-E4B, NeurIPS 2026 VLM4RWD workshop [S9]. |
| ONESTRUCTION leaderboard: Opus 5.5 73.7, Argon 73.6, Opus 5 72.7, GPT-6.1 Sol 70.2, Sonnet 5.5 66.9; Opus 5.5 70.2 on drawings at $0.33 and 1.7 min; Sonnet 5.5 58.6 at $0.14 | Confirmed | All figures in S19. Add: single run, medium effort, non-official harness and time limit. |
| AEC-Bench: text-catchable callouts 100%, visual about 5%, rendering did not help | Confirmed | S18. Correction: arXiv lists authors Mankodiya, Gallik, Galanos, Mulyar; submitted 31 March 2026. |
| DrawingVQA overall scores (Gemini 3 Pro 77.2, 2.5 Pro 71.7, o3 58.7, Sonnet 4.5 57.6, Qwen3-VL-8B 53.3, GPT-4o 48.9; professionals 94.9) | Confirmed | S4. The claim "without the image, o3 drops to 29.5%" is confirmed in the text-only table (o3 58.7 to 29.5). |
| Point-then-count: 99.9-100% in distribution, 76-82 vs 69-75 on OCID, 97.9 OOD | Confirmed, with a scope caveat | Tables 1 and 2 of S14: synthetic ID PtC 99.76-100.00; real-world PtC 76.19-81.90 vs DC 69.05-74.52; OOD best 97.94 (InternVL3.5). These are open 3-8B models on synthetic shapes and OCID, not drawings. |
| MechVL beats best closed model by 7.57 pp; MMArch best proprietary 52%, open about 30%, experts 95% | Confirmed | S20, S12. |
| "Opus everywhere costs about $0.10-0.19 per question" | Plausible, not a measurement | My estimate for one image plus about 1,500 output tokens is about $0.05 on Opus 5.5. Several crops and higher effort can reach $0.10-0.19. CaseVBench measures $0.040 per page for Opus 5.5 [S5]. |
| Small supervised detectors reach 97% per object on doors and windows (gdino repo); RT-DETR-L 90 AP50 | Not checked | Belongs to the CV track. |

## Sources

| id | URL | title | date | claim it supports | exact supporting quote | check |
|---|---|---|---|---|---|---|
| S1 | https://arxiv.org/abs/2601.04819 (PDF read) | AECV-Bench: Benchmarking Multimodal Models on Architectural and Engineering Drawing Understanding (Kondratenko, Birhane, Hsain, Maciocci; AECFoundry, UNSW) | 5 Jan 2026 | Per-class counting table; failure modes; CubiCasa5K subset | Table 1 row "Google Gemini 3 Pro 0.51 0.39 0.34 0.89 0.82"; "A subset was carefully selected from CubiCasa5K (Kalervo et al., 2019), and from the CVC-FP"; "Models frequently misinterpret door swings, confuse windows with openings or façade elements, hallucinate fixtures, or miss instances in dense regions" | corrected: arXiv lists submission 8 Jan 2026 (the PDF itself is dated 5 Jan) and the arXiv title ends "Drawings Understanding". Table 1, subset quote and failure-mode quote confirmed. Qwen3-VL-8B is not the best open model on door/window (Nemotron 0.12/0.18). QA 0.854 not found |
| S2 | https://github.com/AECFoundry/AECV-Bench | AECV-Bench repository | read 13 Nov 2026 | No newer models; no licence file | Benchmarked models list ends at "Claude Opus 4.5, Gemini 3 Pro Preview, GPT-5.2 ..."; no LICENSE in file listing | confirmed: model list ends at Claude Opus 4.5, Gemini 3 Pro, GPT-5.2 and others; GitHub API shows no licence |
| S3 | https://arxiv.org/html/2610.19571v2 | LED-BENCH: A Benchmark for Large-format Engineering Drawing Understanding (Li, Wang, You, Wan, Huang, Liang, Hua) | 14 Oct 2026 | Model scores; crop strategies; resolution | Table 3 "GPT-5.6 Sol 58.81 48.89 50.26 52.65"; Table 5 "Fixed overlapping crops ... 1 ... 49.34 ... +12.96"; "improves Architecture and Transportation but decreases Mechanical from 44.12% to 36.47%"; "Higher input resolution generally improves accuracy, particularly for GPT-5.6 Sol and Gemini 3.5 Flash" | confirmed: Tables 3 and 5, resolution sentence and 107 sheets / 377 questions all in the paper; v2 revised 17 Oct 2026 |
| S4 | https://arxiv.org/html/2607.15418v1 | DrawingVQA: A Real-World Benchmark for Multi-Depth Visual-Textual Reasoning on Construction Drawings (Jung, Fu, Golparvar-Fard) | 16 Jul 2026 | Scores; QTO weakest; failure modes | "Gemini-3-pro-preview 77.2"; "Human: Professionals 94.9"; "the most significant weakness for all MLLMs is Quantity Take Off (QTO)"; "it often stops after identifying the first plausible link and fails to perform a complete visual scan" | corrected: IFC means "Issued for Construction", not the BIM format. 77.2, 94.9, QTO 33.3 vs 41.7, "derailed", "first plausible link", random 27.2 and CVPR 2026 Findings confirmed. o3 text-only 29.5 also confirmed |
| S5 | https://coxit.co/ai-drawing-benchmark/ | CaseVBench (COXIT with LVL10 Consulting) | v7, 13 Nov 2026 | Box detection scores and cost per page of 2026 models | "GPT-6 Astra 92 ... $0.186"; "Claude Opus 5.5 79 ... $0.040"; "GPT-6 Luna 23 ... $0.004"; miscount causes "image resolution limits, small and dense symbols, and objects that look similar to the surrounding linework" | confirmed: all scores and costs match v7 (13 Nov 2026). Note Claude Fable 5.2 (85) and Gemini 4 Carbon (83) rank above Opus 5.5 |
| S6 | https://andonlabs.com/evals/blueprint-bench-2 | Blueprint-Bench 2 (Andon Labs) | May 2026, live | 2026 models reach human level on photo-to-plan room graphs | "Gemini 4 Carbon 0.586"; "Human* 0.586"; "All models achieve ~90% on room count" | confirmed: 0.586 tie, ~90% room count. Caveat: human baseline on 12 apartments only. Date "May 2026" not checked |
| S7 | https://arxiv.org/html/2507.07644v4 | FloorplanQA: A Benchmark for Spatial Reasoning in LLMs using Structured Representations (Rodionov et al.) | v4 2026, ICML 2026 | JSON vs image; tool gains and losses | Table 3 "GPT-5-mini 81.38 ... 31.06"; Table 2 "Pair Distance 56.0 99.0"; "The structured JSON is the dominant signal"; "the bottleneck for complex spatial tasks is algorithmic reasoning about spatial constraints, not numerical precision" | confirmed: Table 3 (81.38, 31.06), Table 2 tool gains and losses, both quotes; ICML 2026 in arXiv comments; v4 25 May 2026 |
| S8 | https://pp.bme.hu/ci/article/view/44138 | Evaluating Vision-language Models for Zero-shot Room Area Estimation in Floor Plan Images (Aliyev, Barsi) | 5 Aug 2026 | VLM area error vs pixel counting | "Results show moderate predictive correlation (R2 ≈ 0.71), but substantial estimation errors (MAPE ≈ 43%)"; "achieved MAPE = 5.68% at the room-instance level, and MAPE = 1.58% when evaluated at the floor plan level" | partly: MAPE 43%, 1.58% and 5.68% confirmed; but only two of the three open VLMs gave scorable output. Publisher page is Periodica Polytechnica Civil Engineering 70(3), 5 Aug 2026 |
| S9 | https://arxiv.org/abs/2609.05880 | Grounded and Faithful P&ID Reasoning: Constraining Vision-Language Models with Recovered Evidence Graphs (Gadekar, Sakhinana, Runkana) | v2 29 Oct 2026 | Evidence graph doubles exact match | Image-only "36.7-41.3%"; "Graph-Grounded Harness (Ours)" "74.3-76.0%"; "grounding pays off where the recovered graph is right, and perception error still breaks topology questions where it is not" | confirmed: 36.7-41.3 to 74.3-76.0, three models, NeurIPS 2026 VLM4RWD workshop, v2 29 Oct 2026 |
| S10 | https://arxiv.org/html/2608.15032v1 | Handoff-H1: An Orchestrated Vision-Agent System for Material Quantity Takeoff from Construction Blueprints (Chicelli et al.) | 15 Aug 2026 | Hybrid beats frontier and humans | "claude-fable-5 61.4"; "Handoff-H1 81.6"; "human estimators 77.6"; "purpose-built computer-vision models that extract primitives" | confirmed: 61.4, 77.6, 81.6; the benchmark is the authors' own (vendor system) |
| S11 | https://arxiv.org/html/2509.17283v2 | Automated Facility Enumeration for Building Compliance Checking using Door Detection and Large Language Models (Zhang, Le, Akhtar, Ngo) | v2 26 Sep 2025 | Detector + LLM vs GPT-5 | Table 1 "CubiCasa5K 97 85.57 87.63"; "CVC-FP 15 40.00 86.67"; "SESYD 48 68.75 95.83"; "we adopt Co-DETR" | confirmed: Table 1 numbers; n=97 (CubiCasa5K), 48 (SESYD); CVC-FP n=15 not found by my search of the text (partly unverified) |
| S12 | https://arxiv.org/abs/2608.09281 | MMArch: Benchmarking Multimodal Reasoning Grounded in Architectural Evidence (Du et al.) | 10 Aug 2026 | Best model 52% vs experts 95% | "the best proprietary system 52%"; "the strongest open-source model attains about 30%"; "human experts reach 95%" | confirmed: abstract has 52%, about 30%, 95%, 1,212 items; submitted 10 Aug 2026 |
| S13 | https://arxiv.org/abs/2607.09544 | The Count Is There, but Misaligned (El-Shangiti et al.) | 10 Jul 2026 | Count encoded but misread; +15.6 pp | "VLMs often encode the correct count even when they output the wrong answer"; up to 15.6 points improvement | confirmed: title, date and "up to 15.6 absolute percentage points" |
| S14 | https://arxiv.org/abs/2603.21746 | Getting to the Point: Pointing Improves LVLMs at Counting (Alghisi et al.) | v2 28 May 2026 | Point-then-count best; OOD gains | "PtC achieves the highest accuracy among the evaluated approaches"; "predicted points correctly grounded in the image in more than 94% of cases" | confirmed: title, v2 28 May 2026, PtC best, 94% grounding. Submitted 23 Mar 2026. Tables give the exact numbers; open 3-8B models only |
| S15 | https://blog.google/innovation-and-ai/technology/developers-tools/agentic-vision-gemini-3-flash/ | Introducing Agentic Vision in Gemini 3 Flash (Doshi, Google DeepMind) | 27 Jan 2026 | Code-execution zoom, numbered boxes, plan checker | "Enabling code execution with Gemini 3 Flash delivers a consistent 5-10% quality boost across most vision benchmarks"; "improved accuracy by 5% by enabling code execution with Gemini 3 Flash to iteratively inspect high-resolution inputs" | confirmed: both quotes, 27 Jan 2026, Rohan Doshi, numbered boxes example (a hand-counting demo) |
| S16 | https://platform.claude.com/docs/en/build-with-claude/vision | Claude Vision docs (Anthropic) | read 13 Nov 2026 | Image limits, token cost, counting limitation | "High-resolution | Claude 4.7 and later models | 2,576 px | 4,784"; "the 4K image about $19.14 USD per thousand"; "Claude can give approximate counts of objects in an image but might not always be precisely accurate, especially with large numbers of small objects" | confirmed: 2,576 px, 4,784 tokens, $19.14 per 1,000 4K images, counting caveat |
| S17 | Claude API skill model table (bundled docs, cached 3 Nov 2026) | Claude current models and prices (Anthropic) | 3 Nov 2026 | Claude prices | "Claude Opus 5.5 ... $4.00 ... $20.00"; "Claude Haiku 5.5 ... $0.10 ... $0.50"; "Claude Sonnet 5.5 ... $2.00 ... $10.00" | confirmed against the public pricing page https://platform.claude.com/docs/en/about-claude/pricing (Opus 5.5 $4/$20, Sonnet 5.5 $2/$10, Haiku 5.5 $0.10/$0.50 up to 100k-token prompts). Fable 5.2 is $8/$40 |
| S18 | https://arxiv.org/html/2603.29199v1 | AEC-Bench: A Multimodal Benchmark for Agentic Systems in AEC (Mankodiya, Gallik, Galanos, Mulyar) | 31 Mar 2026 | Rendering does not help visual tasks | "this increased use of image rendering does not lead to better performance on visually grounded tasks"; pdftotext "collapses spatial layout and geometric relationships into linear text" | confirmed: quotes, 100% vs 5%, 196 tasks, authors, 31 Mar 2026 |
| S19 | https://huggingface.co/blog/ONESTRUCTION/construction-ai-leaderboard | Construction AI Leaderboard: Overview and Evaluation Details (Kanazawa, ONESTRUCTION) | 7 Nov 2026 | 2026 model scores and cost per drawing task | Overall "Claude Opus 5.5 73.7"; drawings "Claude Opus 5.5 70.2 (1st) $0.33 1.7 min"; "Claude Sonnet 5.5 58.6 $0.14" | confirmed: 73.7, 70.2 drawings, $0.33, 1.7 min, Sonnet 5.5 58.6 / $0.14, Sol $0.12; run used a 1,800 s limit and the pi harness, not the official setup |
| S20 | https://arxiv.org/abs/2605.30794 | MechVQA (Kou et al.) | v2 7 Jul 2026, ICML 2026 | Fine-tuned small model beats closed models | "MechVL outperforms the strongest closed-source baseline by 7.57 percentage points on the MechVQA total score" | confirmed: 7.57 pp; submitted 29 May 2026, v2 7 Jul 2026; ICML 2026 |
| S21 | https://cle.togal.ai/overview.html | Construction's Last Exam (Togal.AI) | read 13 Nov 2026 | Benchmark exists; scores not loaded | "A multimodal benchmark for quantity takeoff - wall centerlines, areas, and symbol search on construction drawings" (leaderboard empty in fetch) | confirmed: page exists, 33 tasks (12 areas, 12 counting, 9 linear); leaderboard is loaded by script, so no scores in the fetch |
| S22 | https://arxiv.org/abs/2505.23941 | Vision Language Models are Biased (Vo et al.) | v4 19 Apr 2026 | Priors override counting; thinking helps then hurts | "an average of 17.05% accuracy in counting"; accuracy "initially rises with thinking tokens, reaching ~40%, before declining with excessive reasoning" | confirmed: 17.05%, ~40% peak, v4 19 Apr 2026 |
| S23 | https://arxiv.org/abs/2607.06420 | HoloCount: A Holistic Visual Counting Benchmark for MLLMs (Deng, Qiao, Wan) | 7 Jul 2026 | Counting degrades with density and reasoning | "even top-tier models degrade significantly as tasks transition from perception to complex analytical reasoning" | partly: quote confirmed; the abstract names high-density scenes as a robustness test but I did not find a statement that dense scenes are the hardest category |
| S24 | https://platform.claude.com/docs/en/build-with-claude/vision-coordinates | Coordinates and bounding boxes (Anthropic) | read 13 Nov 2026 | Pixel coordinates; crop small targets; PDF caveat | "Claude does not work well when you ask for normalized coordinates"; "for fine targets, crop the region of interest and send the crop"; "the returned coordinates can't be reliably mapped back onto the page" | confirmed: pixel coordinates, crop advice, PDF mapping caveat, resized_size helper, `transformations.oversized_image = error` |
| S25 | https://arxiv.org/abs/2602.01334 | What Does Vision Tool-Use Reinforcement Learning Really Learn? (Ma et al.) | v2 21 May 2026, ICML 2026 | Zoom-tool RL gains are mostly intrinsic | "improvements are dominated by intrinsic learning"; "learns to coexist safely with tools rather than master them" | confirmed: title is longer ("... Disentangling Tool-Induced and Intrinsic Effects for Crop-and-Zoom"); both quotes; ICML 2026 camera ready |
| S26 | https://aistudio.google.com/docs/image-understanding | Gemini image understanding docs (Google) | read 13 Nov 2026 | box_2d format; tile tokens | "The box_2d should be [ymin, xmin, ymax, xmax] normalized to 0-1000."; "Larger images are tiled into 768x768 pixel tiles, each costing 258 tokens." | confirmed (read at ai.google.dev/gemini-api/docs/image-understanding): box_2d format and 768x768 / 258-token tiles |
| S27 | https://roboflow.com/blog/gemini-4-argon-vision | Gemini 4 Argon leads our vision benchmark (Skalski, Roboflow) | 15 Oct 2026 | Argon detection mAP, latency, cost | 85.1% mAP@50 at high effort; requests average 13.4 s (low) and 19.6 s (high) | confirmed: 82.5% low, 85.1% high effort, 13.4 s and 19.6 s, 15 Oct 2026 |
| S28 | https://github.com/allenai/molmo2 and https://arxiv.org/html/2601.10611v4 | Molmo2: Open Weights and Data for VLMs with Video Understanding and Grounding (Ai2) | v4 2 Apr 2026 | Open pointing model, Apache 2.0 code | Repo licence Apache-2.0; paper: "Open weights, Open data, Open code" (I read the repo page and search summary; I did not open the weight cards: weight licence UNVERIFIED) | confirmed: repo Apache-2.0; Molmo2-4B and Molmo2-8B HF cards list apache-2.0; paper v4 2 Apr 2026 |
| S29 | https://aistudio.google.com/docs/pricing | Gemini API pricing (Google) | read 13 Nov 2026 | Gemini prices | Gemini 4 Argon input "$2.00 through November 30, 2026." / "$4.00 starting December 1, 2026."; Gemini 3.8 Flash "$0.75 through December 31, 2026." | confirmed (read at ai.google.dev/gemini-api/docs/pricing): Argon and Carbon $2/$10 then $4/$20 from 1 Dec; 3.8 Flash $0.75/$3.75; 3.5 Flash-Lite $0.30/$2.50; batch is half |
| S30 | https://developers.openai.com/api/docs/pricing | OpenAI API pricing | read 13 Nov 2026 | GPT-6 prices; no image formula | "gpt-6-astra $10.00 $50.00"; "gpt-6-luna $0.10 $0.50"; no separate image-input rate for flagship models | confirmed: Astra $10/$50, Sol $2/$10, Terra $1/$5, Luna $0.10/$0.50; batch is half |
| S31 | https://arxiv.org/abs/2608.17237 | Training-Free Agentic Computer Vision for Structural Component Detection in 2D Structural Framing Plans (Talebi-Kalaleh, Mei) | v2 26 Aug 2026 | Deterministic-first hybrid, scale by consensus, held-out discipline | "estimates scale by dimension-ratio consensus"; scale "within 0.1% of the generator reference for every drawing" | confirmed: abstract numbers; author-generated benchmark, shared generator |
| S32 | https://arxiv.org/abs/2609.25615 | Evidence-gated multimodal parsing and vectorization of architectural floor plans (Chen et al.) | 22 Sep 2026 | Evidence-gated reviewable outputs | "an evidence-gated multimodal pipeline"; 11,534 plans in a production audit | confirmed: 11,534 plans, no accuracy in abstract |
| S33 | https://arxiv.org/abs/2608.25608 | When Should a Network Emit Geometry, and When Should It Detect It? (Zhang) | 26 Aug 2026 | Fusion of two vectorisers; CubiCasa corrected labels | "deterministic fusion of the two outputs raises wall F1 by 7 points"; zero-shot Gemini 3.1 Pro 0.472 at strict tolerance is from a search snippet of the PDF: UNVERIFIED | corrected: Gemini 3.1 Pro numbers confirmed in the paper (0.811 at 0.05, 0.472 at 0.015, 200-plan ResPlan-FP subset); +7 wall F1 confirmed. No longer UNVERIFIED |
| S34 | https://github.com/roboflow/rf-detr | RF-DETR (Roboflow) | read 13 Nov 2026 | Detector licence split | "`pip install rfdetr` gives you only Apache 2.0 RF-DETR code and models"; XL and 2XL under "PML 1.0" | corrected: PML 1.0 covers Atto, Femto, Pico, XL and 2XL, not only XL and 2XL |
| S35 | https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct | Qwen3-VL-8B-Instruct model card (Qwen) | collection updated 31 Dec 2025 | Licence and OCR languages | "License: apache-2.0"; "Supports 32 languages (up from 19)" | confirmed: apache-2.0 on the model card, "Supports 32 languages (up from 19)". Collection date not checked |

## Verification

Date: 13 November 2026. Checked by an independent pass that tried to refute the report.

- Sources opened: 35 of 35 (S1 to S35). I opened arXiv abs pages and full texts (HTML or PDF text) for S1, S3, S4, S7,
  S9 to S14, S18, S20, S22 to S25, S31 to S33, and the vendor, docs and model-card pages for the rest. Every paper id
  resolves to the stated title and authors. No source is NOT FOUND, so no finding is marked UNVERIFIED for that reason.
- Counts: 28 confirmed (some with a caveat), 4 corrected (S1, S4, S33, S34), 3 partly (S8, S11, S23), 0 not found.
- Corrections made in the text:
  1. Finding 1: Qwen3-VL-8B is not the best open model on doors and windows. Open models score 0.09-0.12 on doors and
     0.03-0.18 on windows; Nemotron Nano 12B has the best open door and window scores (0.12 and 0.18).
  2. Finding 3 and S8: only two of the three open VLMs produced scorable outputs. The 1.58% is floor-plan level; room
     level is 5.68%; the plans are colour-coded.
  3. DrawingVQA: "IFC" means "Issued for Construction", not the BIM file format. This matters for our `ifc_models`
     plans.
  4. S1 date: arXiv lists 8 Jan 2026 (PDF dated 5 Jan); arXiv title says "Drawings Understanding".
  5. S33: the Gemini 3.1 Pro zero-shot number is real (0.811 at tolerance 0.05, 0.472 at 0.015) but is from a 200-plan
     ResPlan-FP subset of clean renders, not CubiCasa5K. UNVERIFIED tag removed.
  6. RF-DETR: PML 1.0 covers Atto, Femto, Pico, XL and 2XL.
  7. Molmo2 weights: the 4B and 8B model cards list apache-2.0. The "check weights" note is closed.
  8. Prior-claim check: o3 text-only drop (58.7 to 29.5) is confirmed. The S14 numbers are confirmed in Tables 1 and 2
     but come from open 3-8B models on synthetic shapes and OCID, not drawings.
  9. Blueprint-Bench 2 human baseline is 12 apartments only. S31 benchmark is author-generated with a shared generator.
- Still unsupported: AECV-Bench QA 0.854 (not in the paper text or tables; maybe a figure), S11 CVC-FP n=15 (not found in
  text), S23 "dense scenes are the hardest category", S6 date "May 2026", S35 "collection updated 31 Dec 2025".
- Not changed: findings 4 to 6 and 8 to 10 stand as written. Their numbers match the sources. Note for readers: CaseVBench
  and Blueprint-Bench 2 list Claude Fable 5.2 above Opus 5.5, and Fable 5.2 costs $8/$40 per million tokens [S17].

