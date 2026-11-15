# Night run results: Make Blueprints Talk

Date: Saturday 14 November 2026, about 06:30. For Henrik. Every number here is from a sealed run in
`experiments/LEDGER.md`, or from a tool benchmark in `experiments/tools/`. Scores are the challenge rule:
+1 right, 0 abstained, -1 wrong. Intervals are 95% cluster bootstrap intervals.

## In short

1. The harness is trustable. `experiments/TRUST.md` has 15 checks and all pass. The oracle scores +1.000, a
   spoiled oracle scores -1.000, and a solver in the sandbox cannot read the labels.
2. The architecture you proposed works: an agent on the bottom that composes answers from benchmarked tools.
   It scores **+0.743 [+0.648, +0.825]** on our hard suite (val, 210 items) with 1.9% wrong. The agent may only
   submit a number that a tool or the calculator produced. This rule is a state machine, not a prompt.
3. Vector inputs are solved for the public question types. Swiss PDF: +0.9995 on all of val. The agent on the
   same sheets: +0.995.
4. Raster inputs are the open problem. Whole-plan counts on CubiCasa: +0.69 with the new detector. Room areas on raster sheets: 81% of
   rooms within 2%. Counts per room on a raster: no tool yet.
5. A direct VLM with no tools is far behind: +0.16 with no threshold, about +0.35 with the best confidence
   threshold. Tools win by a large margin.
6. Cost of the night: about 21 USD of Verda credit (balance 199.98 USD, no VM runs) and 956 router credits
   (about 8 to 10 USD, see "Spend").
7. One decision for you: the best detector is YOLO26-M, which is AGPL-3.0 (section 6).

## 1. The harness

Code: `src/bp/`. Gate: `uv run ruff check src tests && uv run ty check && uv run pytest -q` (239 tests pass).

- A frozen contract (pydantic), a pure scorer, and a generic state machine that is checked at import.
- Each document runs in a sealed session: the file gets a neutral name (`doc-<hash>`), and the solver runs in a
  worker process under `sandbox-exec`, which denies reads of the dataset, the suites, the analysis and git.
- Two canary solvers prove the seal: one tries to read forbidden paths, one tries to use the file name.
- Statistics: cluster bootstrap by building or plan, paired difference between two runs (`bp diff a b`).
- Every run writes `experiments/runs/<id>/` and one row in `experiments/LEDGER.md` (59 rows now).
- Suites: `stoa` (64,110 items from the 127,044 public rows, language twins merged) and `hard` (1,038 derived
  items). Partitions dev, val and lock. The lock partition was opened once, for the IFC solver.

## 2. Results per solver

| Solver | Suite and items | Score | Right | Wrong |
|---|---|---|---|---|
| null (always abstains) | hard, all 1,038 | +0.095 | 19.1% | 0% |
| prior (most frequent answer) | CubiCasa val | +0.118 | 55.9% | 44.1% |
| direct VLM, haiku, no threshold | CubiCasa 40 + Swiss 15 docs, val | +0.161 | 55.8% | 39.7% |
| direct VLM, haiku, threshold 0.5 (in sample) | same | +0.352 | 47.4% | 12.2% |
| Swiss solver (vector PDF) | Swiss val, all | +0.9995 | 99.95% | 0% |
| IFC solver (model and BIM sheet) | ifc_models val, all | +0.682 | 68.2% | 0% |
| count head E1 (ConvNeXt, DINOv3 weights) | CubiCasa val, 8,549 items | +0.568 | 64.8% | 8.0% |
| count head, 8 views | same | +0.572 | 64.4% | 7.2% |
| RF-DETR Large detector | CubiCasa val, 80 plans, 737 items | +0.607 | 73.3% | 12.6% |
| YOLO26-M detector | same 80 plans | +0.687 | 79.1% | 10.5% |
| count head E1 | same 80 plans | +0.577 | 65.5% | 7.9% |
| **agent v4** | **hard val, 210 items** | **+0.743** | 78.6% | 1.9% |
| agent v3 | public Swiss val, 25 sheets, 420 items | +0.995 | 99.8% | 0.2% |
| agent v3 | public IFC val, 25 docs, 308 items | +0.688 | 69.8% | 1.0% |
| agent v4 | public CubiCasa val, same 80 plans | +0.688 | 79.8% | 11.0% |
| agent, sheet tools v2 | large sheets dev (USACE), 91 sheets, 550 items | +0.749 | 82.2% | 7.3% |
| agent, sheet tools v2 | large sheets lock (held-out USACE), 30 sheets, 160 items | +0.675 | 77.5% | 10.0% |

Large sheets (14 November). The lock sheets are held out: one run, read as totals per question kind only.
Printed areas and scales: 80 of 82 right, 0 wrong. Room area from the wall lines: 16 right, 1 wrong, 17 abstained
(dev: 28 right, 0 wrong, 47 abstained). Door count: 4 right, 12 wrong on lock, and right within 3% on 31 of 60 dev
sheets. So the door count is an estimate: after this run the agent abstains on a door count and gives the count as
its best estimate. With that rule the same lock run is about +0.73 with 2.5% wrong. The target is +0.80.

Large sheets (15 November). A door detector (YOLO pose, 3 keypoints) trained on vector PDF renders of the dev
building types counts the door leaves, with a leaf size filter of 0.58 to 1.40 m. At tool level on dev the count is
right within 3% on 53 of 64 sheets (arc finder: 31), and on 14 of 18 sheets of the two building types that the
detector did not train on. The agent answers a door count only when the detector and the arc finder agree within
3%: on dev 31 right, 1 wrong, 32 abstained. Agent on dev: +0.809 with 2.2% wrong (was +0.749 with 7.3%). Lock run 2
of 3: +0.731 with 3.1% wrong (run 1: +0.675 with 10.0%). Per kind on lock: printed areas and scales 80 right,
0 wrong of 82; area sum 12, 1 wrong of 14; label count 12, 2 wrong of 14; room area 15 right, 1 wrong, 18 abstained
of 34; door count 3 right, 1 wrong, 12 abstained of 16. The two methods agree on only 4 of the 16 lock sheets, so
the door rule gives less on lock than on dev. The target of +0.80 is not reached. A stronger planner does not help:
on 30 dev sheets Haiku 5.5 scores +0.782, Opus 5.5 +0.796 and GPT-6 Luna +0.640.

Historic scans (15 November). Baseline on 25 hand-checked questions on habs, finna, europeana and wikimedia scans:
+0.16 (1 right, 2 wrong, 5 right abstains, 17 abstains). The agent has no text, scale or vision tools for them yet.

Scanned twins of the large sheets (15 November). `jobs/sheet-scans/make.py` makes a scanned twin of each sheet: skew
up to 1.2 degrees, grey paper, blur, noise and JPEG. Tool level, the 91 dev sheets, right / wrong / abstained:

| | door count (64) | room area (75) |
|---|---|---|
| clean sheets | 55 / 7 / 2 | 30 / 0 / 45 |
| scanned twins, before the fix | 2 / 1 / 61 | 0 / 0 / 75 |
| scanned twins, after the fix | 52 / 9 / 3 | 23 / 3 / 49 |

The cause was the scale. A printed scale counts only when door sizes confirm it, and the arc finder finds no doors
on a scan. Now the trained door detector confirms the scale when the arc finder cannot. Open: the dimension lines
are not read on a scan, the 3 wrong room areas are 5% to 12% too small (blur makes the walls thicker), and the
agent still abstains on door counts on a scan, because the agree rule needs the arc finder.

Agent progress on hard val: v0 +0.555, v1 +0.607, v3 +0.733, v4 +0.743. The steps to v1 and to v3 are
significant in the paired test. The step to v4 is not (+0.010): the hard suite has few whole-plan raster counts.

Reading:

- The agent matches the dedicated solvers on public data. On IFC it is equal (+0.007, not significant). On
  CubiCasa counts it equals the best count tool (+0.688 against +0.687 for the detector alone). On Swiss it is 0.005 under the solver.
- The agent costs about 0.1 cent per question with `claude-haiku-5.5` and takes 5 to 6 seconds.
- The direct VLM is wrong on 37 to 44% of answers. Swiss areas are a lost cause for it (10 to 20% right).

## 3. The agent

Code: `src/bp/agent/` (loop and rules), `src/bp/solvers/agent.py` (tool sets), `src/bp/solvers/raster_tools.py`.

- States: START, THINKING, TOOL, CHECK, DONE. The CHECK state refuses an answer whose number is not a tool
  result or a calculator result built from tool results. After two refusals the agent abstains.
- At ingest the solver detects the document kind and gives the agent only the tools for it:

| Document | Tools |
|---|---|
| vector plan PDF | rooms (area, apartment, outdoor, windows and doors per room), symbol counts, apartments |
| BIM sheet PDF | room regions with areas at the sheet scale, find a room by tag |
| IFC model | project info, spaces, element counts, quantity sums |
| DXF | rooms (same fields as the PDF), layers |
| raster plan | OCR rooms with areas from U-Net masks and the measured scale, apartments, whole-plan counts |

Hard val by input (agent v4):

| Input | Items | Score | Wrong |
|---|---|---|---|
| IFC, model and sheet | 35 | +1.000 | 0% |
| Swiss PDF, DXF and raster | 145 | +0.800 | 2.1% |
| CubiCasa raster | 30 | +0.167 | 3.3% |

Hard val by family, weakest first (score, from the v3 run): bedrooms_with_window 0.00, compare_rooms 0.00, rooms_with_window
+0.22, bathrooms_without_window +0.27, bath_tiles +0.33, doors_to_room +0.40, wall_material +0.56,
apartment_area_sqft +0.57, apartment_area +0.60. The other 19 families are at +0.67 or more, and 14 are at
+1.00. The weak families are all raster items: they need windows and doors per room, or room sizes on a plan
with no scale.

## 4. Tool benchmarks

A tool is trusted when its benchmark says so. Files: `experiments/tools/*.json`, code: `src/bp/toolbench/`.

| Tool | Checked against | Result |
|---|---|---|
| Swiss PDF rooms | DXF, 22,966 rooms on 833 floors | recall 1.0, precision 1.0, labels 1.0, area error max 0.05% |
| Swiss PDF counts | source data, 833 floors | toilets, basins, tubs, showers, apartments, distinct doors: all exact |
| Swiss PDF windows | DXF | exact on 99.9% of floors |
| Swiss scale | scale bar against scale text | agree on 833 of 833 |
| BIM sheet room area | public answers, dev, 691 items | 691 right |
| IFC model counts, volumes, lengths | public answers, dev | all right where the question goes to the model |
| raster OCR (PP-OCRv6) | Swiss val, 210 sheets | room numbers 92.5% right, labels 89.4%, printed areas 89.3% |
| raster scale | DXF fit, 210 sheets | found on 210, error under 1% on 210 |
| raster room area (U-Net) | true areas, 5,577 rooms | 81.2% within 2%, 89.4% within 5%; high confidence: 96.6% within 2% |
| raster room area, no model | same | 26.1% within 2% |
| count head, per family | CubiCasa val | floors 97%, kitchens 97%, saunas 96%, bathrooms 89%, balconies 86%, WC rooms 85%, toilets 82%, showers and tubs 79%, sinks 73%, bedrooms 70%, doors 32%, windows 23% |

The raster room numbers are from the 15-minute U-Net. The 85-minute U-Net is now the default model. It did not
change the agent result in a measurable way (+0.025 on 80 raster items, not significant). Its tool benchmark
was not run again.

The count head cannot count doors and windows. This is why we trained a detector (section 6).

**Tools added in the night to 15 November (tool level, no agent run: the model router had no credit).**

- **Door pair on large sheets.** A second detector (RF-DETR keypoints, Apache 2.0) is the witness of the first (YOLO pose) when it has seen the sheet; the answer is the lower count when they agree within 3%. Agreed and right / agreed and wrong / not agreed: clean dev 31/1/32 to 51/3/10, scan dev 0/0/64 to 49/3/12. The 3 wrong sheets are the same on clean and scan and both detectors count too high there; the truth of those sheets is not checked by eye. On 100 val renders the pair agreed on 77% and was right on 95% of those. Uploads have no RF-DETR cache and keep the arc finder rule.
- **Scans of large sheets.** Deskew at read time, ink relative to the local paper level, and solid wall ink only. Dimension-line scale on 57 of 58 dev scans (was 1). Room area on scan dev 23/3/49 to 22/0/53; clean dev unchanged at 30/0/45. Still wrong: photos with perspective (8 wrong room areas) and bleed-through (door counts).
- **Contractor quantities on Swiss plans and DXF.** Perimeter, baseboard, doors and windows per room: right on 5,577 of 5,577 val rooms against the DXF of the same floor. Wall centre line within 2% on 207 of 210 floors. No public question checks the baseboard rule.
- **IFC.** Pipes, ducts, fittings, valves, terminals and systems: tool bench dev 277 and val 192 right, 0 wrong, against a separate STEP reader; counts are a weak test and lock is not clean. Wall length against public keys: 12 right, 2 wrong, 1 abstained; the 2 wrong came from the Axis fallback, which now abstains.
- **Historic scans.** Own route with title block, scale bar, drawing size and a two-model look tool. Not scored: the rerun got 25 errors from the router. Baseline +0.16.
- **Fixtures and windows on large sheets.** A first model is not good enough to use: toilets right on 7 of 10 sheets by eye, sinks 2 of 10, windows not usable. Not wired in.

**Lock run 3 of 3 (15 November, 04:27 UTC), the last one.** The agent with the door pair, the conflict fix and the scan fixes, through OpenRouter (the Hostinger router had no credit). Dev: +0.831 with 2.73% wrong (run `20261115-042341-625`; before the night +0.809 with 2.18%). Lock: **+0.719 with 4.38% wrong** (run `20261115-042744-432`; run 2 was +0.731 with 3.12%). The target of +0.80 with at most 3% wrong is not met. Totals per question kind on lock, right / wrong / abstained, run 2 to run 3: door count 3/1/12 to 6/3/7; sum of printed areas 12/1/1 to 10/1/3; room area 15/1/18 to 14/1/19; label count 12/2/0, printed area 58/0/2 and scale 22/0/0 unchanged. So the door pair gave 3 more right and 2 more wrong door counts on lock: when the pair agrees it is right on 6 of 9 lock sheets, against 51 of 54 on dev. The dev number overstated the pair; the lock sheets are other building kinds. The changes in area sums and room areas are 3 questions, with no change in the tools: the planner differs from run to run.

## 5. Honest findings

- **IFC questions are mostly PDF questions.** 2,694 of the 3,062 `ifc_models` rows give a PDF sheet, not the
  model. A sheet shows one storey, so questions about the whole model (counts, volumes, wall lengths) cannot be
  answered from it. Our IFC score of +0.68 with zero wrong is close to the ceiling for an honest solver.
  A question for Stoa: is the IFC file given together with the sheet?
- **`ifc_bench` free text cannot be scored by number rules.** 128 items have no number in the key. They need a
  judge. Not built.
- **Door counts have two conventions.** The Swiss source counts one door per side of a shared wall. The agent
  first picked the distinct count on 16 of 25 sheets. A sentence in the tool output fixed it (+0.919 to +0.995).
  Small wording in a tool matters more than the model.
- **Dev overlaps training for the CubiCasa models.** Use val numbers only for the count head and the detector.
- **The hard suite is ours.** Keys come from labels and geometry with a second path as a check, and I checked
  some by eye. No person has reviewed the keys at scale. `experiments/hard-cases-sample.md` has 30 items to read.
- **The Gemini planner run is not a result.** The router drops Gemini's thought signature, so the second
  tool turn fails with status 400. Ignore ledger row `20261114-033323-514-agent-hard`.
- **The server restarted at about 05:00** and cancelled the three builder workflows. Their code and models were
  on disk. I finished the integration in the main loop. Missing because of it: the notes files for the count
  head, the detector and the raster tools.

## 6. Symbol detector (CubiCasa)

RF-DETR Large and YOLO26-M, both at 1024 px, trained on boxes from the CubiCasa SVG labels (2,452 plans, 421
held out for calibration). Thresholds are tuned for the count score on the held-out dev plans.

Tool benchmark on 300 val plans (share of plans with the exact count):

| Class | Count head | RF-DETR Large | YOLO26-M |
|---|---|---|---|
| doors | 32% | 69% | 71% |
| windows | 23% | 64% | 61% |
| toilets | 82% | 92% | 92% |
| sinks | 73% | 81% | 85% |
| bedrooms | 70% | 84% | 87% |
| bathrooms | 89% | 81% | 86% |
| kitchens | 97% | 82% | 82% |

Box quality for YOLO26-M: doors precision 0.96 and recall 0.96, windows 0.93 and 0.92. About 0.5 s per plan on
the laptop CPU.

Sealed, on the same 80 val plans: count head +0.577, RF-DETR +0.607 (not significant), YOLO26-M +0.687
(+0.110 [+0.044, +0.173], significant). This goes against the research pick of RF-DETR.

On all 957 CubiCasa val plans (8,549 items), sealed: count head +0.568, RF-DETR +0.649 [+0.629, +0.669],
YOLO26-M +0.696 [+0.678, +0.715]. YOLO26-M is above RF-DETR by +0.048 [+0.032, +0.063] and above the count head
by +0.129 [+0.109, +0.149]. Both differences are significant. The gap to RF-DETR on the full set is smaller than
on the 80 plans (+0.080). Each model was trained once, and RF-DETR got 24 epochs against 55 for YOLO26-M on a
shared GPU, so RF-DETR may not be at its best.

The agent uses the YOLO26-M counts first and the count head for a family that the detector doubts. I chose this
on a separate set of 60 val plans (+0.672 against +0.661 for the detector alone, not significant).

**Decision for you:** YOLO26-M is AGPL-3.0. RF-DETR is Apache-2.0. The default is now YOLO26-M
(`artifacts/cubicasa-detect/DEFAULT`). To switch: `echo rfdetr-l > artifacts/cubicasa-detect/DEFAULT`. The cost is
about 0.05 score on raster counts.

Wrong answers are still 10 to 11% on raster counts. Doors and windows are exact on only 60 to 70% of plans, and
the doubt rule does not catch all of the misses.

## 7. What was not done

- Counts per room on rasters (windows and doors per room). The U-Net has an opening class, so the data is
  there; the link to rooms is not written.
- The open planner (Qwen3.5-9B with LoRA). The agent with haiku already works, so the gain is small.
- A planner comparison with `claude-sonnet-5.5` and a second vendor.
- CountGD++ and the pointing VLM from `docs/BASE-MODELS.md`.
- A labelling interface. No experiment needed hand labels: every key came from vector labels.
- Calibration items in the hard suite (a raster with the scale cropped out).

## 8. Recommendation

1. Build the demo on the agent with the tool sets. It is the same code path for every input, it abstains
   instead of guessing, and it returns evidence (polygons, marks, element ids) for each answer.
2. Next work, by expected gain: windows and doors per room on rasters, then a better doubt rule for the
   detector (10% wrong on raster counts), then a second witness for raster room areas with low confidence.
3. Ask Stoa the open questions: IFC with the sheet or not, the door count convention, and how free text is
   scored.

## Spend

- Verda: balance 221.04 USD before the night, 199.98 USD now. About 21 USD on A100 VMs (count head, detector,
  U-Net). All VMs are deleted.
- Hostinger AI Router: 956 credits in `experiments/llm_spend.jsonl`. The unit is not certain. By the price list
  it is about 120 credits per USD (about 8 USD). The setup document says 100 credits per USD (about 10 USD). I did
  not check the balance on hpanel. It is the shared team budget.

## How to reproduce

```sh
cd stoa
uv run bp selftest                                   # writes experiments/TRUST.md
uv run bp build && uv run python -m bp.hardcases.build
set -a; . ../infra/hostinger/secrets.env; set +a
uv run bp run agent --suite hard --partition val --jobs 6 --note "..."
uv run bp diff <run a> <run b>
uv run bp ledger
```

The models are in `artifacts/` (git-ignored): `cubicasa-count/`, `cubicasa-detect/`, `raster-rooms/`.
