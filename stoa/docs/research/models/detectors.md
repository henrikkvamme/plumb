# Detectors for small symbols on floor-plan rasters

Date: Saturday 14 November 2026. Scope: which object detector we fine-tune for doors, windows, toilets, sinks,
showers, bathtubs and stairs on raster plans, and how we make the counts exact.

Labels: **SOURCED** (a source I opened, id in brackets, table at the end), **MEASURED** (I ran it on our data
this session; the scripts are in the session scratchpad, not in the repository), **ESTIMATE** (my reasoning),
**UNVERIFIED** (seen only in a search snippet, or the page did not open).

Earlier work is not repeated. `research/sota/floorplan-cv.md` and `STATE-OF-THE-ART.md` section 2.2 hold the
dataset facts, the contamination finding and the first RF-DETR plan. This file changes four things in that plan:
the exact model and its settings, the finding that the label geometry needs a per-plan scale, the finding that
symbol size (not model family) decides the result, and the count-calibration method.

## In short

1. **Primary: RF-DETR Large** (`rfdetr` 1.12.1, class `RFDETRLarge`, Apache-2.0 code and weights, 33.9 M
   parameters, DINOv2-S windowed encoder). Fine-tune it at **resolution 1024** on square-padded images, with
   COCO labels. All of Nano, Small, Medium and Large share one encoder, so Large costs the same as Medium and
   has the best pretrained weights of the Apache sizes. [S1][S2][S7]
2. **Fallback: Ultralytics YOLO26-M at imgsz 1280** (AGPL-3.0: fine for the weekend, flag it for a product). It
   has a stride-8 head, a one-line train command and published floor-plan precedent. Use YOLO11-M if YOLO26 trails
   in the one-hour test. [S17][S19][S20][S21]
3. **Symbol size decides, not model family.** MEASURED on CubiCasa originals: median long side is 17 px for
   showers, 30 px for sinks, 36 px for toilets, 39 px for doors. The RF-DETR feature map is one scale at stride
   16. Small-object AP is flat across DETR families (36 to 39 on COCO) [S12]. So we raise the input scale and tile
   large sheets. No paper reports exact-count accuracy for any detector.
4. **Do not pick DEIMv2 or EdgeCrafter (ECDet):** I read both licence files. Both grant non-commercial use only.
   RT-DETRv4 needs a DINOv3 teacher and gives no small-object gain in its tables. YOLO27 is not released. [S11][S13][S15][S18]
5. **Labels need a per-plan scale.** MEASURED: Stoa's PNG is `F1_original.png` (4,018 of 4,018 sizes match).
   The `model.svg` coordinates live in `F1_scaled.png` pixels, not in the SVG viewBox. Multiply by
   `W_original / W_scaled`. A conversion that uses the viewBox is wrong on most plans.

## What the lead asked, answered

| Question | Answer |
|---|---|
| Which base model? | RF-DETR Large, resolution 1024. Fallback YOLO26-M, imgsz 1280. |
| Newest releases to November 2026? | RF-DETR 1.12.1 (2026-11-12), YOLO26 (January 2026), YOLO27 (waitlist only), DEIMv2 (2025-09-26, EdgeCrafter 2026-03), RT-DETRv4 (ECCV 2026), D-FINE (last news 2024-11). No "RF-DETR 2". No DINOv3 backbone in the official RF-DETR (community forks only). [S1][S2][S6][S11][S14][S15][S17][S18] |
| Small objects? | DETRs are weak. Raise resolution, tile above the trainable size. Native high resolution beats tiling when you can train at it. [S8][S9][S12][S24] |
| Licence flags? | AGPL: Ultralytics. Non-commercial: DEIMv2, EdgeCrafter, CubiCasa5K data, FloorPlanCAD. PML 1.0: RF-DETR Atto, Femto, Pico, XL, 2XL. Custom with conditions: DINOv3. [S1][S11][S13][S17][S28] |
| Published floor-plan results? | RT-DETR-L on CubiCasa at 1024: door AP50 89.8, window 89.3. YOLOv8s on 1,500 plans at 1024: toilet 63.2, sink 60.8, bathtub 39.8, shower 18.4. None with exact counts. [S20][S21] |
| Exact counts? | Per-class thresholds tuned on exact-count rate, seam dedupe, count-stability check. See section 4. |

## Candidates

Scores are COCO val2017 AP50:95 unless said. APs is small-object AP. "RF100-VL" is the mean AP50:95 over 100
fine-tuning datasets, from Roboflow's own benchmark page, so treat it as vendor-run. [S4]

| Model, exact id | Licence (code / weights) | Params | COCO AP (APs) | RF100-VL | Small objects and resolution | Fine-tune from COCO labels | Floor-plan evidence | Verdict |
|---|---|---|---|---|---|---|---|---|
| **RF-DETR Large**, `RFDETRLarge`, weights `rf-detr-large-2026.pth`, rfdetr 1.12.1 | Apache-2.0 / Apache-2.0 [S1][S2] | 33.9 M | 56.5 (APs not published) [S1] | 62.2 [S4] | One scale, stride 16 (`projector_scale=["P4"]`, patch 16). Default 704. Maintainer: DETRs weak on small objects, upscale to help, costs latency [S7][S8] | `pip install "rfdetr[train,augment]"`, COCO folder, one `train()` call [S3] | An AEC layout study ranks RF-DETR first, mAP50 0.949, on page layout, not symbols [S22]. A May 2026 journal paper fine-tunes RF-DETR-L on FloorPlanCAD, no numbers in the snippet (UNVERIFIED) [S31] | **Primary** |
| RF-DETR Medium / Small / Nano | Apache-2.0 [S1] | 33.7 / 32.1 / 30.5 M | 54.7 / 53.0 / 48.4 | 61.2 / 60.2 / 57.7 | Same ViT-S encoder as Large. Large has the same decoder depth as Medium (4 layers) [S7] | Same | none | Use only to save time. No cost saving at equal resolution |
| RF-DETR XL / 2XL | PML 1.0, `rfdetr[plus]`; commercial self-hosting needs the Enterprise add-on [S1][S2] | 126 M | 58.6 / 60.1 | 62.9 / 63.2 | 700 / 880 px default | Same | none | Skip: licence and 4x parameters |
| RF-DETR Atto / Femto / Pico | PML 1.0 [S1] | 7.4 to 8.4 M | 30.5 to 41.6 | 48 to 56 | PE-Core-T backbone, 380 to 560 px | Same | none | Skip |
| RF-DETR Seg (N to 2XL) | Apache-2.0 [S1] | 33.6 to 38.6 M | 40.3 to 49.9 (mask) | - | 312 to 768 px | COCO with polygons | none | Not needed for counts |
| D-FINE L / M | Apache-2.0 [S14] (Objects365 checkpoints may carry Objects365 terms) | 31 / 19 M | 54.0 (36.5) / 52.3 [S12][S14] (the S4 page re-evaluates D-FINE-L at 57.2, likely an Objects365 checkpoint) | 61.6 / 60.6 [S4] (M value UNVERIFIED) | HGNetv2 CNN backbone, multi-scale, 640 default [S14] | Config files, `torchrun train.py -c ...`, edit `custom_detection.yml` [S14] | none found | **Alternative if the licence must stay clean and RF-DETR fails** |
| DEIM L / X (D-FINE with better matching) | Apache-2.0 [S16] | 31 / 62 M | 54.7 (36.9) / 56.5 (38.8) [S12] | not in [S4] | CNN backbone | Same layout as D-FINE | none | No gain over D-FINE for us |
| DEIMv2 S/M/L/X (DINOv3 features) | **DEIMv2 License: non-commercial only** (text read); commercial by contact [S11] | 9.7 to 50 M | L 56.0 (37.5), X 57.8 (39.2) [S12] | not in [S4] | Paper: small-object AP "largely unchanged" over DEIM; DINOv3 "limited ability to represent fine-grained details" [S12]. Input 640 | Same layout as D-FINE | none | **Reject**: licence, no small-object gain |
| EdgeCrafter ECDet S/M/L/X | **EdgeCrafter License: non-commercial only** (text read) [S13] | 10 to 49 M | 51.7 to 57.9 (59.9 with Objects365) [S13] | - | 640 only documented | Fine-tuning steps not on the README page | none | **Reject**: licence |
| RT-DETRv4 S/M/L/X | Apache-2.0 code [S15]. Needs DINOv3 ViT-B/16 teacher weights under the DINOv3 licence [S15][S28] | not given on the page | 49.8 / 53.7 / 55.4 / 57.0 (APs not given) [S15] | - | Teacher only at training. No small-object result | D-FINE-style configs | none | Skip: extra setup, no evidence for small symbols |
| RT-DETRv2, RT-DETR (Ultralytics build) | Apache-2.0 repo [S16]. The Ultralytics build is AGPL-3.0 [S17] | 42 M (v2-L) | 53.4 (36.1) [S12] | - | - | - | RT-DETR-L on CubiCasa, door 89.8, window 89.3 (Ultralytics build, AGPL) [S20] | Reference point only |
| LW-DETR T to X | Apache-2.0 [S16] | 12 to 118 M | 42.9 to 58.3 [S4] | 57.1 to 62.1 [S4] | 640 | Own repo | none | Not better than RF-DETR on RF100-VL (L 61.5 against 62.2) |
| **Ultralytics YOLO26 N/S/M/L/X** | **AGPL-3.0** or Enterprise [S17] | 2.4 to 55.7 M (M 20.4 M on the docs page, 20.1 M on S4) | M 52.5 end to end (53.1 non-e2e), X 56.9 end to end (57.5 non-e2e) [S17][S4] | M 58.7, X 60.0 [S4] | STAL and ProgLoss aimed at small targets. P2 head: YAML only, no pretrained weights [S17] | One command, `yolo train data=... imgsz=1280` [S17] | YOLOv26n scored below YOLO11n on SESYD mAP50-95 (0.920 against 0.975, n size, 30 epochs) [S19] | **Fallback** |
| Ultralytics YOLO11 / YOLOv8 | AGPL-3.0 [S4][S21] | 20 M (M) | YOLO11-M 48.6 [S4] | 56.5 [S4] | stride 8 head | Same | YOLOv8s on 1,500 CubiCasa plans at 1024: mAP50 67.1 over 10 classes [S21] | Swap-in if YOLO26 trails |
| YOLOX-s | Apache-2.0 [S21] | - | - | - | - | MMDet or YOLOX repo | Same 1,500-plan test: mAP50 65.7; sink 74.8 (better than YOLOv8s), shower 7.8 [S21] | Licence-clean CNN, older |
| YOLO27 | not released: "coming soon", waitlist, licence "confirmed at launch" [S18] | - | - | - | - | - | - | Ignore |
| RF-DETR on a DINOv3 encoder | Community forks only (`Sompote/DinoV3-DETR`, a fork PR of 2026-10-22). No official release, no scores (UNVERIFIED) | - | - | - | - | - | - | Ignore |
| Le-DETR (CVPR 2026 Findings) | Code and weights promised, not seen (UNVERIFIED) | - | +0.6 over D-FINE-M | - | - | - | - | Ignore |
| Open-vocabulary (Grounding DINO, SAM 3) | Apache-2.0 / gated | 0.9 B (SAM 3) | - | SAM 3: 15.2 AP zero-shot | Grounding DINO zero-shot mAP50 0.0 on CubiCasa symbols [S21] | - | - | Not for symbols |

Reading the table:

- On COCO, APs sits between 36 and 40 for every real-time family [S12]. The newest, largest models do not fix
  small objects. The choice between RF-DETR, D-FINE and YOLO is a second-order effect next to input scale.
- RF-DETR Large and Medium differ only in the checkpoint and the default resolution (704 against 576).
  MEASURED from the config source [S7]. That is why Large is free to choose.
- The RF-DETR paper makes accuracy depend on the token grid (resolution divided by patch size), so more pixels
  mean more tokens [S5]. A maintainer says that for small objects a larger variant beats a resolution bump on
  Nano or Small, because the larger variants already run at higher resolution [S9]. For us all variants share
  the encoder, so the resolution bump is on the table for Large.

## Our data, measured

### Symbol size on the CubiCasa originals (MEASURED)

I parsed 1,500 train plans from `model.svg` and scaled to the original PNG (the image Stoa serves). One box per
SVG element, by Stoa's counting rules (`research/data/cubicasa.md`).

| Class (SVG element) | Instances | Long side, px: p10 / median / p90 | Share of image width, median | Per plan, mean | Plans with zero |
|---|---|---|---|---|---|
| door (`Door *`) | 14,816 | 22 / 39 / 83 | 4.6% | 9.9 | 0% |
| window (`Window *`) | 13,114 | 22 / 54 / 140 | 5.6% | 8.7 | 1% |
| toilet (`FixedFurniture Toilet`) | 1,530 | 21 / 36 / 71 | 4.3% | 1.0 | 27% |
| sink (Sink, RoundSink, DoubleSink, ...) | 3,891 | 16 / 30 / 61 | 3.6% | 2.6 | 2% |
| shower (`Shower`) | 1,344 | 10 / 17 / 35 | 2.1% | 0.9 | 28% |
| bathtub (`Bathtub`) | 120 | 52 / 82 / 141 | 10.3% | 0.08 | 92% |
| stairs (`Stairs`, union of flights) | 1,336 | 43 / 88 / 199 | 8.4% | 0.9 | 68% |

- Median plan width is 785 px (p10 430, p90 1,677). The Stoa PNG widths are the `F1_original` widths.
- Bathtubs are rare: about 0.08 per plan, so about 330 train instances. The earlier gdino result shows the
  same pattern: bathtub AP50 40 to 45 and shower 8 to 18 [S21]. Swiss Dwellings adds bathtubs (897 of 1,040 floors
  have at least one, `research/data/swiss.md`). Train on both.
- `ShowerScreen` (1,253 in 1,500 plans) and `ShowerCab` are not showers by Stoa's rule. Give `ShowerCab` its own
  class so the model does not mix it with `Shower`.
- Stairs and bathtubs are large. Showers, sinks and toilets are 17 to 36 px. At stride 16 a 17 px shower covers
  about one token at native scale. This is the failure to expect.

### The label geometry pitfall (MEASURED)

| Check | Result |
|---|---|
| Stoa PNG size equals `F1_original.png` size | 4,018 of 4,018 train plans with a PNG |
| `F1_scaled.png` aspect ratio equals the original | p5 to p95: 0.999 to 1.001 |
| Median width, original / scaled | 775 px / 1,415 px |
| SVG viewBox ratio equals PNG ratio | 149 of 575 plans within 2% only |

The CubiCasa loader reads `F1_scaled.png` with `model.svg` and uses SVG coordinates as pixels of the scaled
image [S29]. The viewBox only bounds the drawn content. So the box in original pixels is
`svg_xy * (W_original / W_scaled)`. Take `W_scaled` from the zip (`cubicasa/<group>/<id>/F1_scaled.png`). Skip
`<defs>` when you collect polygon points: the arrow markers sit at the origin and stretch every stairs box
(this cost me one wrong first measurement).

## Recommendation and recipe

### 1. Classes and labels

- Classes: `door`, `window`, `toilet`, `sink`, `shower`, `bathtub`, `stairs`, `shower_cab`. Ignore `shower_cab` at
  inference. One box per SVG element, as Stoa counts: a double door is one box, a double sink is one box.
- Box = bounding box of all descendant polygons of the element, with nested `matrix()` transforms, then the
  scale above. Drop boxes under 6 px on the long side.
- Swiss Dwellings: one box per drawn symbol from the geometry, not from the Stoa answer. The Swiss door answers
  follow a database rule with stacked copies (`research/data/swiss.md`), so they cannot be read from pixels and
  are not a label source.
- Export a COCO folder as RF-DETR wants it: `train/_annotations.coco.json`, `valid/_annotations.coco.json`,
  images next to the JSON, `bbox` as `[x, y, w, h]`. [S3]
- Mimic a Roboflow export: category `0` is a dummy root ("plans", supercategory "none"), the real classes are
  `1..8`. RF-DETR 1.11.2 fixed a bug where a root category shifted class names by one [S6]. The docs do not state
  the id rule (UNVERIFIED). Test it first (risk 1).

### 2. Images

- Pad each image with white to a square. Do not let the loader squash it: the pretraining is square-only
  (maintainer, via a search snippet, UNVERIFIED) and the squash changes symbol shapes.
- Rule to test (ESTIMATE): plans with a long side from about 700 to 1,400 px go to 1,024 by one resize. Smaller
  plans go up by at most 2x. Larger sheets are cut into 1,024 px tiles at native scale, step 768 px (overlap
  256 px, more than the largest door or toilet).
- Swiss PNG sheets are 2,480 x 1,753 px at 150 dpi, scale 1:100 or 1:200 (`research/data/swiss.md`). One sheet is
  6 tiles (3 columns, 2 rows). A fixture is about 15 to 20 px at 1:200 and 30 to 40 px at 1:100 (ESTIMATE from
  the paper size of a 0.5 to 0.7 m fixture). A full-sheet resize to 1,024 would shrink fixtures to 6 to 8 px, so
  tile.
- Large objects (stairs, bathtubs) get cut by tiles. Run a second pass on the whole sheet at 1,024 to 1,280 for
  `stairs` and `bathtub`. Take small classes from the tile pass. (ESTIMATE; the design follows the evidence that
  tiling pays off only above the trainable size [S24].)

### 3. Training

```sh
pip install "rfdetr[train,augment,loggers]==1.12.1"      # Python >= 3.10 [S2]
```

```python
from rfdetr import RFDETRLarge

model = RFDETRLarge(resolution=1024)          # multiple of 32; pretrained rf-detr-large-2026.pth downloads on first use [S3][S7]
model.train(
    dataset_dir="/data/plans_coco",
    epochs=25,                                # set from the 100-step speed test, see below
    batch_size=8, grad_accum_steps=2,         # effective 16; A100 80 GB
    lr=1e-4,                                  # defaults: lr 1e-4, lr_encoder 1.5e-4, EMA on [S3]
    multi_scale=False,                        # first run: fixed scale, lower OOM risk (ESTIMATE; see [S6] and RF-DETR issue 782, UNVERIFIED)
    scale_jitter=False,                       # keeps border boxes whole [S3]
    aug_config={
        "HorizontalFlip": {"p": 0.5},
        "VerticalFlip": {"p": 0.5},
        "RandomRotate90": {"p": 0.5},         # check box handling first (risk 5)
        "ImageCompression": {"p": 0.3},       # JPEG scans in the hidden set
        "GaussianBlur": {"p": 0.2},
        "ToGray": {"p": 0.3},
    },
    early_stopping=True, early_stopping_patience=6, early_stopping_use_ema=True,
    output_dir="/data/runs/rfdetr_l_1024",
    devices=1,
)
```

| Item | Value | Status |
|---|---|---|
| Library, version | `rfdetr` 1.12.1, 2026-11-12, Python 3.10 to 3.14 | SOURCED [S2] |
| Weights | auto-download at model creation; file `rf-detr-large-2026.pth`; URL not stated in the docs | SOURCED [S3][S7], URL UNVERIFIED |
| Backbone and head | DINOv2-S windowed, patch 16, 2 windows, 4 decoder layers, one projector scale (P4), 300 queries, `num_select` 300 | SOURCED [S7] |
| Training defaults | batch 4, `grad_accum_steps` 1, lr 1e-4, lr_encoder 1.5e-4, weight decay 1e-4, EMA 0.993, 100 epochs, early stopping off | SOURCED [S3] |
| Resolution rule | multiple of 32 for detection (patch 16 x 2 windows); pass `resolution=` again when you load a checkpoint | SOURCED [S3] |
| Memory help | `RFDETRLarge(gradient_checkpointing=True)`: 30 to 40% less memory, 20% slower | SOURCED [S3] |
| Docs memory table | 40 GB+: batch 16, resolution 768 | SOURCED [S3] |
| VRAM at 1,024, batch 8 | 30 to 50 GB | ESTIMATE |
| Inference VRAM | under 4 GB | ESTIMATE |
| Multi-GPU | `torchrun --nproc_per_node=N train.py` with `devices="auto"` | SOURCED [S3] |
| Checkpoints | `checkpoint_best_total.pth` for inference; `last.ckpt` to resume | SOURCED [S3] |
| Data size | CubiCasa train 4,200 images; plus about 6,000 Swiss tiles for stage B | MEASURED / ESTIMATE |

**Expected time (ESTIMATE, wide).** I found no clean RF-DETR timing on a dedicated A100. Data points: a Medium
fine-tune at about 576 px ran at 10 to 17 images per second on a shared A100 before optimisation and reached 33.6
images per second on another GPU after profiling [S32, search snippet only]. Release 1.10.0 reports 10 minutes per
COCO epoch on an RTX 6000 for an unstated size [S6]. At 1,024 px the token count is 3.2 times that of 576 px. My
range for Large at 1,024: 5 to 10 images per second. So 4,200 CubiCasa images take 7 to 14 minutes per epoch, and
25 epochs take **3 to 6 hours** (about 7 to 14 USD at 2.37 USD per hour). With the Swiss tiles added (about 10k
images) the epoch time doubles to triples. Do not guess: run 100 steps, read seconds per step, then set
`epochs = floor(budget_seconds * images_per_second / n_images)`. Plan stage A (CubiCasa, about 20 epochs), then
stage B (add Swiss tiles, 5 to 8 epochs from the stage A checkpoint).

**Run a control in parallel.** A second A100 costs 2.37 USD per hour and the credit is about 200 USD. Train YOLO26-M
on the same data at imgsz 1280 as the control:

```sh
pip install ultralytics                     # AGPL-3.0; check the version you get
yolo detect train model=yolo26m.pt data=plans.yaml imgsz=1280 epochs=80 batch=16 flipud=0.5 degrees=0
```

(Command shape from the Ultralytics docs [S17]; `flipud` and the epoch count are my choices, ESTIMATE. The
docs page showed only the Python form and a custom-YAML CLI line.)

### 4. Exact counts: thresholds and calibration

No benchmark scores exact counts from a detector. Published detector papers report mAP only (RT-DETR-L, YOLOv8s
above). If each object has an independent 3% chance of a miss or a false hit, the exact-count rate is 0.97^n:
77% for 8.8 windows, 39% for 30.7 Swiss doors (ESTIMATE, from `floorplan-cv.md`). So a detector at AP50 85 will
not give exact counts by itself. The method has six steps.

1. **Save raw output.** Run inference at a low floor (score 0.05, `num_select` 300) and store boxes, scores and
   tile ids for the CubiCasa val and test splits and a held-out Swiss set. Split Swiss by site, so a building
   does not sit on both sides.
2. **Merge tiles with a seam rule.** A DETR gives no duplicates inside one pass, only across tiles. Plain NMS misses
   a fragment that is clipped by a seam, because the IoU is low. Use: drop a box if more than 80% of its area sits
   inside a higher-scoring box (the intersection over the smaller box), or if its centre lies in the overlap band
   and within half a box size of a kept centre. This containment rule follows a pull request in another project
   [S34, UNVERIFIED as a method]. Roboflow's `supervision.InferenceSlicer` offers NMS or non-max merging
   (UNVERIFIED, search snippet) [S27]. Then compare the count from tiles against the count from a full-image
   pass on the small sheets.
3. **Tune one threshold per class on the exact-count rate.** Grid 0.05 to 0.95 in steps of 0.01. Score each value
   by the share of plans with the exact count, tie-break by mean absolute count error. Report a bootstrap
   interval by plan, not by object. Compare with the F1-optimal threshold. The two can differ much: one
   YOLOv8 counting study found its best count at confidence 0.025, ten times below the default 0.25, with
   accuracy 90.8% to 99.3% on a test region and 98.6% overall [S25]. A review in the same literature suggests the
   F1 peak (not opened, so UNVERIFIED). Our data decides.
4. **Calibrate confidence by box size.** Scores are biased by box size (small boxes score lower), and a
   histogram-binning fix per size group helped detectors by up to 0.6 mAP and 0.8 mAP50 [S26]. Showers and sinks
   are small, so they gain most. Fit the bins on the val split.
5. **Correct a systematic bias, only if it holds out.** Fit a per-class map from the raw count at the tuned
   threshold to the true count (a shift for small counts, isotonic for large). Fit it on out-of-fold counts.
   Keep it only if the exact-count rate improves on test and on the Swiss holdout. This is the classify-and-count
   correction from the quantification literature (from memory, no source opened: UNVERIFIED).
6. **Report a count with a stability grade.** Recount at `t - 0.1` and `t + 0.1`, and on a flipped and a
   rotated copy. If the counts agree, grade "stable". If not, give the range, and let the executor ask for a
   check or abstain. Count the scores inside the band `[t - 0.1, t + 0.1]` as the doubt. Confidence then is a
   table lookup on these checks, as `DECISION.md` rule 6 says.

Style shift breaks the thresholds. The RT-DETR floor-plan repo reports window confidence 0.9 and above on line art
and 0.3 to 0.5 on rendered styles, and faint door arcs needing 0.15 [S20]. So a CubiCasa threshold will not
carry to Swiss PNG sheets or scans. Options, in order: train on both styles with the augmentations above; keep
a separate threshold set per style, picked by a cheap style classifier (CubiCasa group, line-art against rendered);
and re-tune from a few labelled sheets of the hidden-like kind when we get them (ESTIMATE).

One idea I looked at and dropped: a "soft count" that sums temperature-scaled scores over several detectors.
The only source I found (NumBench, arXiv 2608.28206) is about text-to-image evaluation and its abstract does not
describe such a method, so I do not use it [S33].

### 5. What to use at inference, and what it costs

- Per sheet: 1 global pass plus tiles (6 tiles for a Swiss sheet). RF-DETR Large at 704 runs in 6.8 ms on a T4 with
  TensorRT FP16 [S4]. At 1,024 the tokens are 2.1 times more, so about 15 to 20 ms per tile (ESTIMATE). A Swiss
  sheet takes about 0.15 s on a GPU. The cost is under 0.001 USD per sheet at 2.37 USD per hour.
- On CPU only, expect seconds per tile: RF-DETR Small at 512 px ran 374 ms on an x86 CPU with OpenVINO FP32 [S6].
  At 1,024 with Large, I estimate 2 to 4 s per tile, so 15 to 25 s per Swiss sheet (ESTIMATE). Ask Stoa whether our
  service may use a GPU.

## Risks and how to test them in 1 hour

| # | Risk | One-hour test | Pass rule |
|---|---|---|---|
| 1 | The COCO export shifts class names or ids | Export 50 plans. Train 1 epoch. Run `model.evaluate` and print per-class AP and the class names in `training_config.json` | Eight classes, names match ids, no class at AP 0 for a real reason |
| 2 | Boxes do not sit on the symbols | Draw boxes on 30 originals (all 7 classes) across the three CubiCasa groups | No visible offset on at least 29 of 30 |
| 3 | Time and memory at 1,024 and 1,280 | 100 training steps at each size. Record seconds per step and peak VRAM | Pick the epoch count from the numbers. Drop to 896 if a step is over 2 s at batch 8 |
| 4 | Showers and sinks stay below usable recall | Train 3 epochs at 1,024 and at 1,280 on 1,000 plans. Read per-class recall at IoU 0.3 and AP50 on 400 val plans | 1,280 helps shower recall by at least 5 points, or else keep 1,024 |
| 5 | A rotation augmentation moves images but not boxes | Dump 20 augmented samples with boxes drawn. Custom geometric transforms must be registered in `rfdetr/datasets/transforms.py` [S3] | Boxes follow the symbols. If not, write rotated copies to disk |
| 6 | Style shift: CubiCasa model on Swiss sheets | Run the stage A checkpoint on 100 Swiss tiles. Plot score histograms per class | Doors and windows recall at IoU 0.3 at least 0.7 before any retrain. If not, mix Swiss in from the start |
| 7 | Seam double counts | Tile 50 Swiss sheets with and without the containment rule. Count objects that straddle a seam | Fewer than 1% of objects change count |
| 8 | Thresholds do not give exact counts | On the val split compute the exact-count rate at F1-optimal and at count-optimal thresholds, per class | Count-optimal beats F1-optimal by a clear margin, or the two agree |
| 9 | The control beats the primary | YOLO26-M and RF-DETR-L on the same 400 test plans: exact-count rate for door, window, toilet, sink | Take the better one. Check the licence note before a product |
| 10 | The licence blocks the product | Read this table before any demo claim | Weights trained on CubiCasa5K stay research only. RF-DETR code and base weights are Apache-2.0. Ultralytics output is AGPL-3.0 |

Failure modes already known:

- DETRs are weak on small objects, and upscaling costs latency (maintainer, April 2025) [S8]. A user who raised
  RF-DETR Small to 1,200 px saw better results and much longer training and inference [S9].
- RF-DETR gives one feature scale at stride 16. DEIM, D-FINE and YOLO give three scales, but they do not do much
  better on COCO small-object AP [S12].
- Native higher resolution beat tiling with box fusion on VisDrone for every detector that could be trained at that
  resolution. Tiling pays off only on sheets far above the trainable size (DOTA, 2,048 px) [S24]. Slicing at
  inference alone gave +5 to +7 AP on FCOS, VFNet and TOOD, and slicing plus sliced fine-tuning gave +13 to +15
  AP, measured against low-resolution baselines [S23][S24]. So train on tiles that look like inference tiles.
- Confidence drops on other drawing styles [S20]. Bathtubs and showers are the weakest classes in any CubiCasa
  result [S21].
- Pre-training on general documents hurt on AEC drawings ("domain interference") [S22]. Start from COCO weights, not
  from a layout model.
- Detector output does not know the Stoa counting rule. Doors in a Swiss DXF are counted by a database rule.
  Use the detector for rasters only, and keep the DXF path for DXF.

## What I could not verify

- Any score of RF-DETR, D-FINE or YOLO26 on CubiCasa5K or FloorPlanCAD with per-class AP or exact counts. I found
  none. A May 2026 journal paper on RF-DETR-L with FloorPlanCAD exists, but only the snippet was visible [S31].
- RF-DETR APs on COCO. The repository and docs do not list it. The RF-DETR issue 112 reply of 2026-02-11 says the
  paper reports small-subset results [S8]. I did not find them in the abstract.
- The training-time numbers. They are estimates from other GPUs and sizes [S6][S32].
- The RF-DETR weights URL, whether `RandomRotate90` is registered as a geometric transform, and the `multi_scale`
  default in 1.12.1 (the docs list `multi_scale` only as an enum).
- The EdgeCrafter fine-tuning steps (not on the README page) and the DINOv3 licence effect on RT-DETRv4. The
  DINOv3 licence permits commercial use under conditions (royalty-free, redistribution terms, export-control
  clauses) [S28]. I did not weigh it further.

## Sources

Read date for every URL below: 2026-11-14, unless a different date is given.

| Id | Title | URL | Date | What it supports |
|---|---|---|---|---|
| S1 | RF-DETR repository README | https://github.com/roboflow/rf-detr | 2026-11-14 | Sizes, parameters, COCO AP, licences (Apache-2.0 for Nano to Large, all Seg; PML 1.0 for Atto, Femto, Pico, XL, 2XL), DINOv2 backbone, no DINOv3 |
| S2 | rfdetr on PyPI | https://pypi.org/project/rfdetr/ | 1.12.1 released 2026-11-12 | Version, Python 3.10 to 3.14, Apache-2.0 metadata, extras |
| S3 | RF-DETR docs: train, training parameters, advanced, augmentations, dataset formats | https://rfdetr.roboflow.com/latest/learn/train/ (and `/training-parameters/`, `/advanced/`, `/augmentations/`, `/dataset-formats/`) | 2026-11-14 | COCO layout, `train()` arguments and defaults, resolution rule, multi-GPU, memory table, checkpoints, augmentation syntax, geometric transform registration |
| S4 | RF-DETR benchmarks page | https://rfdetr.roboflow.com/latest/learn/benchmarks/ | page timestamp 2026-11-09 | COCO and RF100-VL AP, latency on T4, params, licences for RF-DETR, YOLO11, YOLO26, LW-DETR, D-FINE. Vendor-run |
| S5 | RF-DETR: Neural Architecture Search for Real-Time Detection Transformers (ICLR 2026) | https://arxiv.org/abs/2511.09554 | v1 2025-11-12, v2 2026-02-03 | Method, 48.0 AP nano, over 60 AP for 2XL. Token-grid claim from a search summary of the full text (UNVERIFIED) |
| S6 | rf-detr releases | https://github.com/roboflow/rf-detr/releases | 1.10.0 (2026-09-04) to 1.12.1 (2026-11-12) | Training changes, the 1.11.2 COCO class-name fix, speed figures, no DINOv3, `register_backbone` |
| S7 | `src/rfdetr/config.py` (develop branch) | https://raw.githubusercontent.com/roboflow/rf-detr/develop/src/rfdetr/config.py | 2026-11-14 | Large and Medium config: ViT-S windowed, patch 16, 2 windows, 4 decoder layers, P4 only, 300 queries, `rf-detr-large-2026.pth`, resolution 704 |
| S8 | RF-DETR issue 112, small objects | https://github.com/roboflow/rf-detr/issues/112 | replies 2025-04-04 to 2026-02-11 | Maintainer: DETRs weak on small objects, upscale for better results at a latency cost |
| S9 | RF-DETR issue 852, other trained models | https://github.com/roboflow/rf-detr/issues/852 | 2026-03-22, reply 2026-03-23 | 1,200 px worked for a small-hole use case at higher cost; maintainer prefers larger variants over a resolution bump on small ones |
| S11 | DEIMv2 repository and `LICENSE.md` | https://github.com/Intellindust-AI-Lab/DEIMv2 | news to 2026-10-22; licence read 2026-11-14 | Model table, training command, custom-dataset steps, "DEIMv2 License" grants non-commercial use only |
| S12 | Real-Time Object Detection Meets DINOv3 (DEIMv2) | https://arxiv.org/html/2509.20787v2 | v2, 2025 | Table 3 with AP and APs for DEIMv2, D-FINE, DEIM, RT-DETRv2, YOLO; small-object statements; 640 px input |
| S13 | EdgeCrafter repository and `LICENSE.md` | https://github.com/Intellindust-AI-Lab/EdgeCrafter (paper https://arxiv.org/abs/2603.18739) | paper 2026-03; TMLR acceptance 2026-08-11 | ECDet table; "EdgeCrafter License" grants non-commercial use only |
| S14 | D-FINE repository | https://github.com/Peterande/D-FINE | news to 2024-11-07 | Apache-2.0, model table, training commands, custom-dataset steps, Objects365 caveat |
| S15 | RT-DETRv4 repository | https://github.com/RT-DETRs/RT-DETRv4 (paper https://arxiv.org/abs/2510.25257) | accepted ECCV 2026 (news 2026-06-18) | Apache-2.0, AP table, DINOv3 ViT-B/16 teacher needed for training |
| S16 | Licence files of D-FINE, DEIM, LW-DETR, RT-DETR, RT-DETRv4, RF-DETR, SAHI | `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/LICENSE` | 2026-11-14 | Apache-2.0 for all except SAHI (MIT) |
| S17 | Ultralytics YOLO26 docs | https://docs.ultralytics.com/models/yolo26 | updated within a week of 2026-11-14 | Model table, STAL and ProgLoss, P2 YAML without weights, AGPL-3.0 or Enterprise, train example |
| S18 | Ultralytics YOLO27 page | https://www.ultralytics.com/yolo/yolo27 | 2026-11-14 | Not released, waitlist, licence set at launch |
| S19 | FloorYOLO (Frontiers in AI 9) | https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2026.1911589/full | 2026-09-15 | YOLO variants on SESYD and CVC-FP, RT-DETR-L 0.9911 mAP50-95, YOLOv26n below YOLO11n. SESYD is saturated and synthetic |
| S20 | rtdetr-floorplan-detector (Architect-Ant, arXiv 2606.10953) | https://github.com/OldDeLorean/rtdetr-floorplan-detector | 2026 | RT-DETR-L on CubiCasa at 1024 px, door 89.8, window 89.3 AP50, 2 x A100 for 2.3 h, style-dependent confidence |
| S21 | Grounding DINO on CubiCasa5K | https://github.com/heypaprika/gdino | 2026 | YOLOv8s and YOLOX-s on 1,500 plans at 1024 px: per-class AP50, detection rate at IoU 0.1; zero-shot 0.0 |
| S22 | Benchmarking Deep Learning Approaches for AEC Engineering Drawing Layout Detection | https://arxiv.org/abs/2607.18997 | 2026-07-21 | RF-DETR mAP50 0.949 on layouts; domain interference |
| S23 | Slicing Aided Hyper Inference and Fine-tuning | https://arxiv.org/abs/2202.06934 | 2022-02-14, v5 2022-10-24 | SAHI gains: +5 to +7 AP inference only, +13 to +15 with sliced fine-tuning (FCOS, VFNet, TOOD) |
| S24 | When Does Sliced Inference Pay Off? | https://arxiv.org/abs/2611.12657 | 2026-11-09, v3 2026-11-11 | Native higher resolution beats tiling when trainable; tiling helps on sheets far above the trainable size |
| S25 | Automated Dislocation Detection in ECCI (YOLOv8 counting) | https://arxiv.org/abs/2608.28495 | 2026-08-28 | Count-tuned threshold 0.025 against default 0.25: counting accuracy 90.8% to 99.3% on a region, 98.6% overall |
| S26 | The Box Size Confidence Bias Harms Your Object Detector | https://arxiv.org/abs/2112.01901 | 2021-12-03 | Size-conditional histogram-binning calibration, up to +0.6 mAP, +0.8 mAP50 |
| S27 | supervision `InferenceSlicer` docs | https://supervision.roboflow.com/detection/tools/inference_slicer/ | not opened | UNVERIFIED (search result only): `slice_wh`, `overlap_ratio_wh`, merge threshold |
| S28 | DINOv3 licence | https://raw.githubusercontent.com/facebookresearch/dinov3/main/LICENSE.md | last updated 2025-08-19 | Custom licence, royalty-free with redistribution and export-control terms |
| S29 | CubiCasa5K `house.py` and `svg_loader.py` | https://raw.githubusercontent.com/CubiCasa/CubiCasa5k/master/floortrans/loaders/house.py | 2026-11-14 | SVG coordinates used as pixels of `F1_scaled.png`; class lists; stairs code commented out |
| S31 | Journal paper on RF-DETR-L with FloorPlanCAD | https://ijsdr.org/papers/IJSDR2605139.pdf | 2026-05 | UNVERIFIED (search snippet only), no metrics seen |
| S32 | RF-DETR training throughput write-up | https://github.com/tuan3w/rfdetr-training-throughput | 2026 | UNVERIFIED (search snippet only): Medium 10.4 to 33.6 images per second, A100 caveats |
| S33 | NumBench | https://arxiv.org/abs/2608.28206 | 2026-08-28 | Opened: about text-to-image counting. Does not support a detector soft-count method |
| S34 | matchline pull request 1132 | https://github.com/anchapin/matchline/pull/1132 | 2026 | UNVERIFIED (search snippet only): containment test for tile-seam duplicates |
| L1 | Local: `docs/research/data/cubicasa.md`, `swiss.md`, `docs/research/sota/floorplan-cv.md`, `STATE-OF-THE-ART.md` | `stoa/docs/...` | 2026-11-13 | Counting rules, Swiss PNG size and scale, contamination finding, earlier plan |
| L2 | Local data: `stoa/data/external/cubicasa5k/` (`svg/`, `splits/`, `cubicasa5k.zip`) and `stoa/data/junction-dataset/data/cubicasa5k/*.png` | - | read 2026-11-14 | MEASURED symbol sizes, PNG equals `F1_original` (4,018 of 4,018), scaled to original width ratio |

## Verification

Independent check on 2026-11-14. Each primary source was opened again. The primary recommendation (RF-DETR Large, Apache-2.0, 33.9 M, 56.5 COCO AP, resolution 1024 fine-tune) stands. Items I did not open stay UNVERIFIED.

| Claim | Verdict | Evidence URL |
|---|---|---|
| RF-DETR Large: 33.9 M params, COCO AP50:95 56.5, Apache-2.0, 6.8 ms T4 at 704 | CONFIRMED | https://github.com/roboflow/rf-detr |
| RF-DETR licences: Nano to Large and Seg Apache-2.0; Atto, Femto, Pico, XL, 2XL PML 1.0; XL 126 M, 2XL 126.9 M | CONFIRMED | https://github.com/roboflow/rf-detr |
| `rfdetr` 1.12.1, released 2026-11-12, Python 3.10 to 3.14, Apache-2.0 | CONFIRMED | https://pypi.org/project/rfdetr/ |
| `RFDETRLarge` config: `rf-detr-large-2026.pth`, res 704, dinov2_windowed_small, patch 16, 2 windows, 4 dec layers, P4, 300 queries; Medium 576 | CONFIRMED | https://raw.githubusercontent.com/roboflow/rf-detr/develop/src/rfdetr/config.py |
| RF100-VL AP50:95: RF-DETR-L 62.2, YOLO26-M 58.7, YOLO26-X 60.0, D-FINE-L 61.6 | CONFIRMED | https://rfdetr.roboflow.com/latest/learn/benchmarks/ |
| YOLO26 is AGPL-3.0, January 2026; M 52.5 end to end, X 56.9 | CONFIRMED (also lists 53.1 and 57.5 non-e2e; M params 20.4 M on docs, 20.1 M on S4; text amended) | https://docs.ultralytics.com/models/yolo26 |
| DEIMv2 licence is non-commercial only | CONFIRMED | https://github.com/Intellindust-AI-Lab/DEIMv2/blob/main/LICENSE.md |
| EdgeCrafter licence is non-commercial only; ECDet AP 51.7 to 57.9 (59.9 with O365), 10 to 49 M | CONFIRMED | https://github.com/Intellindust-AI-Lab/EdgeCrafter/blob/main/LICENSE.md |
| DEIMv2 L 56.0 (APs 37.5), X 57.8 (39.2); DEIM-L 54.7 (36.9), X 56.5 (38.8); D-FINE-L 54.0 (36.5); RT-DETRv2-L 53.4 (36.1); small-object AP "largely unchanged" | CONFIRMED | https://arxiv.org/html/2509.20787v2 |
| D-FINE L 54.0 / M 52.3, 31 / 19 M, Apache-2.0, Objects365 caveat | CONFIRMED (S4 shows 57.2 for D-FINE-L; note added) | https://github.com/Peterande/D-FINE |
| RT-DETRv4 S/M/L/X AP 49.8 / 53.7 / 55.4 / 57.0, Apache-2.0, DINOv3 ViT-B/16 teacher for training | CONFIRMED | https://github.com/RT-DETRs/RT-DETRv4 |
| RF-DETR paper: ICLR 2026, Nano 48.0 AP, first real-time detector above 60 AP | CONFIRMED (token-grid claim not checked, stays UNVERIFIED) | https://arxiv.org/abs/2511.09554 |
| RT-DETR-L on CubiCasa at 1024: door AP50 89.8, window 89.3, 2 x A100, 2.3 h | CONFIRMED | https://github.com/OldDeLorean/rtdetr-floorplan-detector |
| YOLOv8s / YOLOX-s on 1,500 plans at 1024: toilet 63.2, sink 60.8, bathtub 39.8, shower 18.4; mAP50 67.1 / 65.7; YOLOX sink 74.8, shower 7.8 | CONFIRMED (YOLOX toilet 62.9, bathtub 44.7 also given; the repo README flags its own shower GT count as inconsistent) | https://github.com/heypaprika/gdino |
| D-FINE-M RF100-VL 60.6, LW-DETR numbers, YOLO11-M 48.6 / 56.5 | UNVERIFIED (not opened separately; S4 fetch did not list them) | https://rfdetr.roboflow.com/latest/learn/benchmarks/ |
| MEASURED claims (symbol sizes, F1_original match) | UNVERIFIED (local measurement, not re-run) | - |
