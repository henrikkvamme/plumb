# Base models: what we train or run, and what we test tonight

Date: Saturday 14 November 2026. For the lead. This file sits under `DECISION.md` and does not change its
direction. It names the model for each part of the fact compiler, and the one-night experiments.

Sources: the seven verified reports in `research/models/`: `detectors.md`, `small-vlms.md`,
`exemplar-counting.md`, `room-geometry.md`, `ocr-text.md`, `datasets.md`, `agent-models.md`. Numbers are copied
from them, with the corrections from each "Verification" section. Hours, costs and speeds are the authors'
estimates unless a row says measured. The A100 is `1A100.22V` at $2.37 per hour. The credit is about $200
(`detectors.md`), so about 84 A100 hours.

## In short

1. Planner: run `claude-haiku-5-5` with strict JSON plans tonight. Escalate to `claude-sonnet-5-5` after two rejected plans. No GPU.
2. Open planner: `Qwen/Qwen3.5-9B`, LoRA SFT, then rejection-sampled SFT. It replaces Haiku only if it passes the gate in `agent-models.md` 3.1.
3. Text: PP-OCRv6 medium with the orientation classifier ON on every raster. PaddleOCR-VL-1.6 on hard crops. No OCR training.
4. Unseen symbols: benchmark CountGD++ first (MIT, no gate). Ask for SAM 3 access now, as the fallback.
5. Symbol detector: RF-DETR Large at 1024 (Apache-2.0). Train only if `DECISION.md` measurement 1 asks for it.
6. Pointing VLM: `tencent/WeVisOne-VL-4B`, zero-shot first, as a second witness for marks. SFT only after the zero-shot test passes.
7. Room areas: a printed m2 label first, then our own U-Net masks times a confirmed scale. Polygon models are a count witness only.
8. Reinforcement learning stays off the critical path. The only candidate is a short GRPO run on the planner after SFT.

## What we train or run

"Hours" means A100 hours. "1-hour test" is the first check, with its pass line from the named report.

| Component | Primary (exact id, licence) | Fallback | Data to train on | Recipe in one line | Hours | 1-hour test |
|---|---|---|---|---|---|---|
| Symbol detector | RF-DETR Large, `rfdetr` 1.12.1, class `RFDETRLarge`, Apache-2.0 code and weights (`detectors.md`) | Ultralytics YOLO26-M at imgsz 1280, AGPL-3.0; YOLO11-M if YOLO26 trails | CubiCasa5K train (4,200 images), then about 6,000 Swiss tiles; FloorPlanCAD Voxel51 tiles as the new style (`datasets.md`) | `RFDETRLarge(resolution=1024)`, square-padded COCO, batch 8 x accum 2, lr 1e-4, about 25 epochs, stage A CubiCasa then stage B with Swiss tiles | 3 to 6 for stage A (estimate); YOLO26-M control on a second VM | Export 50 plans, train 1 epoch: eight classes, names match ids. 100 steps at 1024 and 1280: drop to 896 if a step takes over 2 s at batch 8 |
| Pointing VLM | `tencent/WeVisOne-VL-4B`, Apache-2.0, Qwen3-VL base (`small-vlms.md`) | `allenai/Molmo2-4B`, Apache-2.0 (card adds research and educational use) | Door centres from Swiss DXF and CubiCasa labels, about 3,000 tiles at 1,400 px, plus negative tiles with `None` | ms-swift LoRA rank 32, 3 epochs, lr 1e-4, `IMAGE_MAX_TOKEN_NUM=1960`; count = `len(points)` | 0 zero-shot; 2 to 4 for SFT (estimate) | `point to: door` on 5 labelled tiles: some points land on doors. `swift sft` with 20 samples, 5 steps: loss is finite |
| Exemplar counter | `nikigoli/CountGDPlusPlus`, MIT, not gated, 0.2B (`exemplar-counting.md`) | GeCo2 `jerpelhan/GECO2` (MIT code), then `facebook/sam3` (gated, SAM License) | None. Training-free. Exemplar is the legend crop or one click; the other legend symbols are negatives | Separate venv with `transformers<4.50`; tile with 25% overlap; exemplar 40 to 100 px; NMS at IoU 0.3; OpenCV template match as a second witness | 0 training; a 2-hour VM (about $4.7) for the benchmark | 20 tiles, 1 exemplar, CountGD++ against GeCo2 against OpenCV: exact count on at least 50% of tiles |
| Room polygons | Own U-Net: `segmentation-models-pytorch` 0.6.0 (MIT), `smp.Unet("resnet50")`, 4 mask channels, own polygonisation (`room-geometry.md`) | Raster2Seq `hf:cubicasa5k`, no training, as a room-count and adjacency witness only (weights CC BY-NC 4.0) | 1,040 Swiss sheets (800 / 120 / 120 by `site_id`) plus CubiCasa5K, strong style augmentation | 1024 px crops, batch 8, bf16, BCE plus Tversky, 40 epochs; about 150 lines of our own PyTorch | 3 to 5 (estimate) | Test 1: self-calibration on Swiss sheets with printed areas, at least 50% of rooms within 2% (now 20.8%). Test 2: overfit 100 sheets in 20 min, at least 60% of rooms of 10 m2 or more within 2% |
| OCR | PP-OCRv6 medium (`PP-OCRv6_medium_det` + `_rec`), 34.5M, Apache-2.0 (`ocr-text.md`) | `PaddlePaddle/PaddleOCR-VL-1.6`, 0.9B, Apache-2.0, for hard crops; Chandra 2 (OpenRAIL-M) for handwriting only | None tonight | `use_textline_orientation=True`, ONNX Runtime, line quads; cut word boxes from the quad ourselves | 0; inference only | Rotate 20 plans by 0, 90, 180, 270 and 15 degrees: recall within 10 points of 0 degrees. VL `Spotting:` through vLLM: 20 labels in under 5 s |
| Planner, API | `claude-haiku-5-5`, $0.10 / $0.50 per million tokens, strict JSON (`agent-models.md`) | `claude-sonnet-5-5` ($2 / $10) for one retry; `gemini-3.5-flash-lite` as the cross-vendor spare | None. GEPA on the prompt, 150 to 500 metric calls | Flat schema: one `op` enum, all fields required, no nulls; adaptive thinking at `low` or `medium` | 0 (GEPA about $1.5 API) | Measurement 2: 40 questions, 5 languages: at least 80% valid plans. Real schema to `output_config.format`: no 400 "Schema is too complex" |
| Planner, open | `Qwen/Qwen3.5-9B`, 9.65B dense, Apache-2.0 | `Qwen/Qwen3.8-27B`, Apache-2.0, SFT only | 3,000 gold plans from the 24 public templates and the parsers; paraphrases from an Apache-2.0 model, not from Claude | Unsloth LoRA r 32 on all linear layers, lr 2e-4, 2 epochs, thinking off, bf16 (no 4-bit); serve with vLLM and an EBNF grammar | 1 to 1.5 SFT; 7 to 9 for the full path with GRPO (estimate) | 20 SFT steps on 50 examples, merge, serve with vLLM, one request answers. Base 9B: 250 tokens in under 4 s at concurrency 1 |
| Datasets to download | FloorPlanCAD Voxel51 mirror (5,308 tiles, 454 MB, treat as CC BY-NC); AECV-Bench (48.6 MB, no licence) as the held-out test (`datasets.md`) | BRIDGE symbol set (no licence) and ResPlan (17,000 vector plans, CC BY 4.0) rendered in our own styles; MSD JSON on Zenodo (319.9 MB, CC BY 4.0) | - | `hf download Voxel51/FloorPlanCAD`; AECV-Bench repo zip; merge door and window types; split FloorPlanCAD by drawing | 0 | Draw 20 FloorPlanCAD tiles with class names (door classes may be swapped). Perceptual hash of the 120 AECV plans against our 4,787 CubiCasa images |

## Experiments worth one night

Ranked by expected gain per A100 hour. The ranking is my judgement from the reports, not a measurement. Run
rows 1 to 4 before Stoa's hint at about midday. Rows 5 onward wait for the hint and for the first trusted
number from the harness.

| # | Experiment | Hours | Why it ranks here | Pass rule | Stop rule |
|---|---|---|---|---|---|
| 1 | Planner bake-off on measurement 2 (Haiku, Sonnet, Flash-Lite, GPT-6 Luna, zero-shot Qwen3.5-9B), then GEPA on the Haiku prompt | 0 (about $0.30 plus about $1.5) | Every question passes through the planner. No GPU (`agent-models.md` section 4) | Haiku at least 80% valid plans. Pick the cheapest model within 3 points of the best | Under 80%: the code session becomes the main path (`DECISION.md` section 6) |
| 2 | Room-area self-calibration: one area factor per sheet from printed m2 labels, leave-one-room-out | 0 (CPU) | It can lift the 20.8% within-2% baseline with no model (`room-geometry.md` test 1) | At least 50% of rooms within 2% | Below 50%: drop step 5 and answer with a range |
| 3 | CountGD++ benchmark on 6 unseen symbol types, with the rotation and negative-exemplar rows | 1 to 2 | Covers any symbol with a legend, with no training (`exemplar-counting.md`) | Exact count on at least 50% of tiles with 1 exemplar; rotation costs under 15 points; negatives cut false positives by at least half | Fails: try GeCo2, then SAM 3 if access came. All fail: vector path plus "click to add marks" |
| 4 | WeVisOne-VL-4B zero-shot pointing on tiles, as part of measurement 1 | under 1 | Decides whether a pointer can be the second witness without training (`small-vlms.md`) | Points land on doors; tiles find more doors than the full sheet; under 10 s per tile | Empty or garbage output: swap to Qwen3-VL-4B-Instruct or Molmo2-4B, or drop the pointer |
| 5 | RF-DETR Large stage A at 1024, YOLO26-M control on a second VM | 3 to 6, plus the control | Exact counts on rasters, if measurement 1 says a frontier model is not enough (`detectors.md`) | On the val split, count-optimal thresholds beat F1-optimal ones or agree; door and window recall at IoU 0.3 at least 0.7 on 100 Swiss tiles | Measurement 1 gives at least 90% exact counts from a frontier model: do not train (`DECISION.md`). Also skip if the zero-shot RT-DETR holds on FloorPlanCAD and BRIDGE d2 (`datasets.md`) |
| 6 | U-Net room masks, after the 20-minute overfit (test 2) and the speed smoke (test 6) | 3 to 5 | The only path toward 2% room area on unlabelled rasters (`room-geometry.md`) | Test 2 passes; test 6 gives at least 20 images per second | Test 2 fails after the boundary-weighted loss: cut, and answer raster areas with a range |
| 7 | Qwen3.5-9B LoRA SFT, then rejection-sampled SFT | about 4 with smoke test and evaluations | The open planner and the "small fine-tuned model" story. Haiku already works, so the score gain is small (`agent-models.md`) | The gate: valid plans and executed accuracy within 2 points of Haiku, p95 under 10 s, no loss on the 5-language set | Gate fails: ship Haiku, and show the 9B only as a second witness |
| 8 | WeVisOne-VL-4B SFT on door tiles | 2 to 4 | Only worth it if row 4 is close and row 5 is not trained (`small-vlms.md`) | Count error within one door on 3 sheets; no large drop on 10 label questions | OCR or reading drops: mix in 20% general samples once, then stop |
| 9 | GRPO on the 9B planner with the executor as reward | 3 to 4 | Last: smallest expected gain per hour (see the next section) | Beats rejection-sampled SFT on held-out templates, and beats the random-reward control | Random plans score 0.3 or more, or the gain is under 1 point: stop |

Not worth tonight: Raster2Seq or other polygon fine-tunes (256 x 256 input, 19.4 h plus 16.0 h on an A6000 in
`room-geometry.md`), PP-OCRv6 training (95 to 98% recall on printed text, measured in `ocr-text.md`), a
PaddleOCR-VL-1.6 fine-tune unless foot and inch marks stay wrong after the rule "trust PP-OCRv6 on marks", and
any DEIMv2, EdgeCrafter or RT-DETRv4 detector.

## Reinforcement learning: where it fits tonight and where it does not

`DECISION.md` says: no reinforcement learning this weekend. The reports agree for perception, and leave one
narrow opening for the planner.

Where it does not fit:

- Detector, room masks, OCR and exemplar counting. No report proposes RL for them. Their errors are perception
  errors, and the fixes are resolution, tiling, thresholds and labels (`detectors.md`, `room-geometry.md`).
- Pointing VLM. GRPO tooling exists for the Qwen3-VL class (ms-swift, EasyR1/verl, TRL), but it is UNVERIFIED on
  WeVisOne, and Molmo2 has no GRPO path. RL takes 4 to 8 hours for a few hundred steps (estimate) and "does not
  fit" next to SFT. A 0/1 "count is right" reward did worse than SFT in prior work (`small-vlms.md`).
- Any task with a few hundred examples. A group of 8 samples that all pass or all fail gives zero gradient
  (`agent-models.md` section 2).

Where it could fit:

- The 9B planner, after SFT, as stage 3 of `agent-models.md`: about 3 to 4 A100 hours, 80 steps (estimate).
  The executor gives an exact and cheap reward. The report sets four conditions: an exact reward, SFT has
  plateaued on decision errors and not on syntax, at least about 1,000 distinct tasks with mixed outcomes per
  group, and a person reads the outputs.

The evidence (all from `agent-models.md`):

- A controlled study (arXiv 2609.17848): LoRA SFT is best in distribution in 15 of 18 settings. GRPO wins 29 of
  54 transfer settings, by under 1 point on average. SFT then GRPO is rarely best.
- GEPA (arXiv 2507.19457, ICLR 2026 oral) beats GRPO by 6% on average, up to 20%, with up to 35 times fewer
  rollouts. A secondary review says the 35 times is one case and the average budget was about 3,900 rollouts.
- ToolRL (arXiv 2504.13958) claims +17% over base and +15% over SFT, but its SFT baselines look weak. Its four
  BFCL percentages are UNVERIFIED.
- ART-E (OpenPipe) shows reward hacking: the model repeated its last tool call to the turn limit. Source is a
  secondary summary, UNVERIFIED.
- The reward must punish a confident wrong answer and pay for a correct `ask_user`. A plain 0/1 reward invites
  the mode answer, which scores 55.3% on cubicasa without looking at the drawing.

My reading: keep GRPO as row 9, after the hint, on a separate VM, and never on the path to the demo. That
respects `DECISION.md` for the product, and it gives the RL claim a measured control if it runs.

## Licence flags

Fine for the weekend. Each one blocks or limits a later product.

| Item | Licence | Effect |
|---|---|---|
| Ultralytics YOLO26, YOLO11, its RT-DETR build | AGPL-3.0 or Enterprise | Fallback detector only |
| RF-DETR Atto, Femto, Pico, XL, 2XL | PML 1.0 | Use Nano to Large only (Apache-2.0) |
| DEIMv2, EdgeCrafter | Non-commercial only (licence text read) | Rejected |
| DINOv3 (RT-DETRv4 teacher, DINOv3 features) | Custom, with conditions | Avoid tonight |
| CubiCasa5K data and weights trained on it | CC BY-NC-SA 4.0 (`DECISION.md`) | No cubicasa-trained weights in a product |
| FloorPlanCAD Voxel51 mirror | Card CC BY-NC 4.0, tag CC BY-SA 4.0 | Treat as non-commercial |
| Raster2Seq weights, MitUNet weights | CC BY-NC 4.0; Raster2Seq bars inference in a commercial SaaS | Witness and recipe only |
| SAM 3 | SAM License, gated, manual approval (waits under 1 h to 16 days, UNVERIFIED) | Request access today |
| Molmo2-4B | Apache-2.0; card adds research and educational use, third-party data non-commercial | Read before a product |
| Chandra 2, Surya 2.5 | OpenRAIL-M, $2M and $5M caps | Hackathon only |
| HunyuanOCR-1.5 | Licence does not apply in the EU, UK and South Korea | Do not use |
| AECV-Bench, BRIDGE | No licence file | Test use only |
| ROBIN | GPL-3.0 | Test use only |
| PyMuPDF | AGPL (`DECISION.md`) | pypdfium2 is the permissive choice |
| Training on Claude outputs | Anthropic Commercial Terms D.4 (reading UNVERIFIED) | Use template gold plans and open-model paraphrases |

Clean: Swiss Dwellings, ResPlan and MSD (CC BY 4.0), `smp` (MIT), CountGD++ (MIT), PP-OCRv6 and
PaddleOCR-VL-1.6 (Apache-2.0), Qwen3.5-9B, Qwen3.8-27B and Gemma 4 (Apache-2.0). A Swiss-only room model with
rendered styles is CC BY 4.0 clean (`room-geometry.md`).

## Where reports disagree or stayed unverified

Disagreements:

- **RL.** `DECISION.md` says no RL this weekend. `agent-models.md` proposes about 8 A100 hours including GRPO.
  This file keeps GRPO last and off the critical path.
- **Detector.** `DECISION.md` lists a trained detector in "cut first" and gates it on measurement 1.
  `detectors.md` and `datasets.md` recommend training. They also differ on data (CubiCasa plus Swiss against
  FloorPlanCAD first) and on time: 3 to 6 h for RF-DETR-L at 1024 on CubiCasa, against about 3 h for FloorPlanCAD
  and about 5 h mixed (scaled from RT-DETR-L). All are estimates. The 100-step speed test settles it.
- **Best dense pointer.** LocateAnything-3B is slightly ahead of WeVisOne-VL-4B on Dense200 pointing (87.6
  against 87.0). WeVisOne leads on detection and rejection, and its licence is read (`small-vlms.md`).
- **Raster2Seq score.** The paper says room F1 88.7. An independent rerun (SALI-FP) got 0.7626. Plan on 75 to 89.

Corrected in verification (use only the corrected value):

- Dense200: 13.8, 18.0 and 71.3 are box-detection mean F1. Pointing F1 is 42.2 (Qwen3-VL-8B), 10.5
  (Qwen3.5-9B) and 87.0 (WeVisOne).
- CountGD++ FSCD-147 MAE 8.39 needs pseudo plus synthetic exemplars. Pseudo-exemplars only: MAE 10.29.
- `google/gemma-4-E4B-it` is Apache-2.0. FloorPlanCAD mirror is 454 MB. ArchSIBench is 2.27 GB. SAM 3 is 0.9B
  on the HF card. SALI-FP's $0.818 per plan is a rate-card calculation. MitUNet 87.91 is before CubiCasa
  fine-tuning (88.53 after).

UNVERIFIED (do not treat as fact):

- "Qwen3-VL loops above 40 to 50 objects" (the paper shows only a 50-point cap in stage 1 data).
- WeVisOne loading in ms-swift, TRL, Unsloth or vLLM; all tool versions in `small-vlms.md`; whether the
  library pins in `agent-models.md` work in one environment.
- PaddleOCR-VL-1.6 "109 languages", and its `Spotting:` prompt through vLLM.
- Lv et al. scale recovery (72% within 2%, 83% within 5%): the verifier got a 403.
- FloorPlanCAD 48,465 instances and the swapped door classes; BRIDGE 6,286 images; MSD 4,572 / 800 split;
  13,905 Swiss floors; ResPlan zip size.
- D-FINE-M RF100-VL 60.6 and the YOLO11-M numbers; the RF-DETR weights URL and `multi_scale` default.
- SAM 3 wait times, the 200-object cap, 8 GB and 2.5 s per image; 848M parameters from the README.
- Every local measurement: symbol sizes, the 20.8% and 26% flood-fill results, OCR runs M1 to M8. The verifiers
  did not rerun them.
- Every training hour, throughput and VRAM figure in this file. They are estimates until the 1-hour tests run.
