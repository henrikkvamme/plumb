# Room polygons and walls from rasters: models, methods and scale

Track: models and algorithms that turn a floor-plan raster into room polygons and walls. Research date: 2026-11-14.
Prior work read first: `DECISION.md`, `STATE-OF-THE-ART.md`, `research/sota/floorplan-cv.md`, `research/data/swiss.md`.
This report goes deeper on room geometry and scale. It does not repeat their tables.

Labels:

- **SOURCED**: I opened the source. URL and date are in the Sources table.
- **MEASURED**: I ran it on our local data. The script is named. It is in the session scratchpad, not in the repository.
- **DERIVED**: arithmetic on SOURCED or MEASURED numbers.
- **ESTIMATE**: my reasoning. Not a result.
- **UNVERIFIED**: I saw it only in a search snippet, or the page did not open.

## In short

Verification (2026-11-14): the recommendation stands. The primary is our own U-Net recipe, so its hours, throughput and accuracy stay ESTIMATE until tests 1, 2 and 6 run. All quoted third-party scores and licences that I could open match. Three items are UNVERIFIED (Lv et al. scale figures, the 13,905 Swiss floors, the exact wording of the Raster2Seq licence on the HF card). See the "Verification" section at the end.

1. **Primary: fine-tune one U-Net for masks, then polygonise ourselves.** Use `segmentation-models-pytorch` 0.6.0, `smp.Unet("resnet50", encoder_weights="imagenet")`, 4 mask channels (room interior, wall, room boundary, door/window opening), 1024 px crops, trained on the 1,040 Swiss sheets plus CubiCasa5K with strong style augmentation. About 3 to 5 h on one A100 (ESTIMATE). Masks beat polygon decoders: on CubiCasa5K test the original model scores room IoU 0.9006 as masks and a 4-class mIoU of 0.7390 as masks against 0.6612 as polygons (SOURCED, SALI-FP).
2. **Fallback: Raster2Seq `hf:cubicasa5k` with no training, only as a room-count and topology witness.** It is the only released CubiCasa-trained polygon model with a 2026 score (room F1 88.7, WAFFLE zero-shot interior IoU 73.9). Its input is fixed at 256 x 256 px and its weights are CC BY-NC 4.0. Do not use it for areas.
3. **No learned polygon model reaches 2% on room area, and none publishes an area error.** Raster2Seq, RoomFormer, PolyRoom and FRI-Net report F1 at room IoU above 0.5, not area. On WAFFLE, Raster2Seq has precision 81.6 and recall 88.6 (SOURCED), which implies about +8.6% net area (DERIVED). Our own flood fill on Swiss PNGs gets 20.8% of rooms within 2%, and 26% with a fitted boundary offset (MEASURED).
4. **Area is scale squared, so scale must be within 1%.** A 1% scale error gives 2% area error (DERIVED). The best published scale recovery is Lv et al., CVPR 2021: 72% of plans within 2%, 83% within 5% (UNVERIFIED by the verifier: the supplement PDF returned 403). The authors do not release it as far as I can see (UNVERIFIED). Use two witnesses (ratio text with a known dpi, scale bar, dimension chain, a printed m2 label). If they disagree, answer with a range and ask for a scale.
5. **Order of trust for a raster area:** printed m2 label, then vector sibling if one exists, then model mask times a confirmed scale, then a range. Floor totals are safer than single rooms: pixel counting gets 1.58% error per floor plan and 5.68% per room (SOURCED, carried from `vlm-on-drawings.md`, not opened again).

## Candidates

### A. Learned models

| Candidate | Exact id and weights | Licence | Size | Input limit | Trained on | Published score | Transfer evidence | Verdict |
|---|---|---|---|---|---|---|---|---|
| Raster2Seq (SIGGRAPH 2026) | HF `haopt/Raster2Seq`, subfolders `cubicasa5k`, `raster2graph`, `raster2graph-512`, `s3d-bw`, `s3d-density`. Code `Cornell-VAILab/Raster2Seq` | Code MIT. Weights CC BY-NC 4.0, "commercial use ... including inference in a commercial SaaS product, is not authorized" | ResNet-50 plus deformable transformer, 6+6 layers, hidden 256 | Fixed 256 x 256. 512 anchors, 32 x 32 bins. Raster2Graph has a 512 px model | CubiCasa5K 4,199 / 399 / 399, 11 classes | CubiCasa5K room / corner / angle F1 88.7 / 59.4 / 37.4. Room semantic F1 63.8 | WAFFLE (100 annotated plans), interior IoU 73.9, precision 81.6, recall 88.6 | **Fallback.** Witness for room count and room adjacency. Not for area |
| RoomFormer (CVPR 2023) | `ywyue/RoomFormer`, checkpoints on ETH polybox. Structured3D and SceneCAD only | Code MIT. Weights: no licence stated | Deformable DETR, two-level queries | Density map of a point cloud. Resolution not on the page | Structured3D, SceneCAD | CubiCasa5K F1 83.5 (retrained by the Raster2Seq authors). WAFFLE IoU 60.5 | No public CubiCasa checkpoint found | **Skip.** Raster2Seq is the same family and newer |
| PolyRoom (ECCV 2024) | `3dv-casia/PolyRoom`. Checkpoints on Google Drive (Structured3D, SceneCAD) | No licence file | Mask2Former proposals plus transformer. Polygon count set to 20 | Point cloud input | Structured3D, SceneCAD | CubiCasa5K room F1 54.1 (Raster2Seq table) | No public CubiCasa checkpoint found | **Skip** |
| FRI-Net (ECCV 2024) | `Daisy-1227/FRI-Net`. `pretrained_ckpt.pth` on Google Drive | No licence file | BSP-Net style room-wise implicit decoder | Point cloud input | Structured3D, SceneCAD | CubiCasa5K room F1 77.1. WAFFLE IoU 56.7 | No public CubiCasa checkpoint found | **Skip** |
| CubiCasa5K multi-task model (2019) | Google Drive file `model_best_val_loss_var.pkl`, repo `CubiCasa/CubiCasa5k` | CC BY-NC 4.0 (carried from `floorplan-cv.md` S11) | Pose-network backbone, multi-task uncertainty loss | Trained on 256 px crops, then 400 more epochs without the resize. Env: Python 3.6.5, PyTorch 1.0.0 | CubiCasa5K | Test mean IoU: rooms 57.5 as masks, 49.3 as polygons. Icons 55.7 / 41.6 | WAFFLE IoU 46.1, precision 79.9, recall 52.1 | **Use as a baseline only.** Old environment. Contaminated on our cubicasa images |
| MitUNet (walls only) | `aliasstudio/mitunet`, file `mitunet_finetune_a6_mit_b4_tversky_8864_28E.pth`. arXiv 2512.02413 | Code MIT. Weights CC BY-NC 4.0 | SegFormer MiT-b4 encoder, U-Net decoder with scSE | 512 x 512 | CubiCasa5K, then a regional set of 500 plans | Wall mIoU 87.91 on its regional set (Table 1, before CubiCasa fine-tuning; 88.53 after). Wall IoU 0.7721 on CubiCasa test (SALI-FP) against 0.7482 for the original model | None beyond its own sets | **Recipe to copy.** Shows a U-Net beats the 2019 model on walls |
| Yytsi `floorplan-to-3d-walls` | HF `Yytsi/floorplan-to-3d-walls` | CubiCasa-derived (NC) | ResNet-34 U-Net, 4 classes (floor, wall, door, window) | 512 letterboxed | CubiCasa5K | None found | None | Skip. Not checked beyond the search snippet (UNVERIFIED) |
| SAM 3 (Nov 2025) and SAM 3.1 (2026-03-27) | HF `facebook/sam3`, `facebook/sam3.1`, repo `facebookresearch/sam3` | "SAM License" (gated, manual approval) | 848M (repo) or 0.9B (HF card) | Resolution not stated | SA-Co | RF-100VL zero-shot 15.2 AP, 10-shot 36.5. SA-Co/Gold cgF1 54.1 | No floor-plan result found. The authors call specialised domains "out of SAM 3's current scope" | **Test only (1 h).** SAM 3.1 adds video tracking (Object Multiplex), no image change stated. Needs Python 3.12, PyTorch 2.7+, CUDA 12.6+: a GPU box, not the Mac |
| RF-DETR Seg | `rfdetr` 1.12.1 (PyPI 2026-11-12), `RFDETRSegMedium` etc. | Apache 2.0, all Seg sizes | 33.6 to 38.6 M params | 312 to 768 px by size | COCO | COCO AP50:95 40.3 (Nano) to 49.9 (2XL) | No floor-plan result | **Skip for rooms.** Too low resolution for sheet-scale boundaries. Good for symbols |
| Mask2Former | HF `facebook/mask2former-swin-large-coco-instance` | "other" on the card | 0.2B | Not stated | COCO instance | No floor-plan result found | PolyRoom builds on it | Skip. Heavier than a U-Net with no boundary advantage that I can source |
| SegFormer | HF `nvidia/segformer-b3-finetuned-ade-512-512` | NVIDIA licence ("other"), non-commercial in practice (UNVERIFIED) | b3-sized | 512 | ADE20k | n/a | none | Skip. The encoder is usable inside smp (`mit_b*`) |
| FloorplanVLM (Beike, Feb 2026) | Paper only. Community LoRA adapters `mudasir13cs/qwen25-vl-3b-floorplan-sft` and `-grpo` on CubiCasa5K | Tag Apache 2.0, card says non-commercial | Qwen2.5-VL-3B | Longer edge normalised to 1024 | Paper: 2M plans, 32 H200. Adapters: CubiCasa5K | Paper, own FPBench-2K: room IoU 0.892. Adapters: no metric on the card | None | **Skip.** No official weights. Generated JSON polygons have no area guarantee |
| SALI-FP (Sep 2026) | No weights. Uses `gpt-image-2` and `gpt-5.5` APIs | n/a | n/a | 1024 x 1024 | n/a | CubiCasa5K 4-class mIoU 0.3596, room F1 0.445 | None | **Do not copy.** Costs $0.818 per plan and loses to the 2019 model. Its baseline tables are useful evidence |

### B. Classical methods and scale tools

No paper that I found reports a room-area error for any classical method. All "expected" figures below are ESTIMATE unless a row says otherwise.

| Method | What it does | Evidence | Failure mode | Verdict |
|---|---|---|---|---|
| Flood fill of light pixels under a seed, holes filled | Room region from wall and line ink | Swiss PNG, perfect seeds: 4.0% within 2% (threshold 200), 20.8% with a 1 px dilation (MEASURED, `swiss.md` `probe_png.py`). With a fitted offset: 26% (MEASURED, below) | Door swing arcs, fixture lines and text cut the room. 25% of rooms have error above 20% (MEASURED, below) | Keep as a cross-check and a witness. Not the area source |
| Door-gap closing | Close openings so rooms do not merge | No published error. Needs a door width in px, so it needs a scale | A wrong scale closes real openings or leaves gaps. Open plans merge rooms | Use the model's opening channel instead of a fixed kernel |
| Wall-line extraction, Hough lines, skeleton | Wall centrelines and lengths | No published area error | Hatched walls, curved walls, thin double lines | Use for wall length only. Needs the wall mask first |
| Colour-mask pixel counting | Count pixels of a colour-coded room | MAPE 5.68% per room, 1.58% per floor plan (SOURCED, VLM-S8) | Only for clean colour-coded plans | Good for floor totals on coloured plans |
| Scale from wall thickness | Assume a fixed wall width | Lv et al. use it for wall width in px, not for scale | A 0.12 m or 0.24 m assumption is wrong across countries | Sanity prior only. 60 cm against 80 cm doors changes a 31 m2 flat to 23 and 41 m2 (UNVERIFIED, blog) |
| Scale from dimension chains (Lv et al., CVPR 2021) | Detect dimension-line ends, OCR the numbers, match, cluster with k-means, average | Positive rate 0.72 / 0.83 / 0.86 within 2% / 5% / 10%. Mean error 4.6 mm. Own RFP dataset. Without the k-means and digit-count checks: 0.45 / 0.58 / 0.66 | Code and weights not found (UNVERIFIED). Cluster check is the useful idea | Copy the idea: many (line, number) pairs, keep the biggest cluster, reject the rest |
| PlanMetric | Per-axis scale fit from dimension boxes, rejects inconsistent pairs, MIT | Demo accepts 8 pairs, rejects 2. No accuracy claim. v0.2.1, 1 star | "Consistently wrong dimensions can still produce an accepted wrong scale" | Read for the idea. Early stage. Do not depend on it |
| Scale bar by pixel measure | Measure the bar, read its label | Team measure: about +-1 to 2% on two scans (MEASURED, `wild.md`) | Faded bars, bars missing on about half of europeana and wikimedia sheets | Primary scale witness where a bar exists |
| LMM scale reading | A large multimodal model reads the scale | "Accuracy 0.707, better than conventional OCR" (Automation in Construction 2026, UNVERIFIED, page returned 403) | Unknown | Not enough to rely on |

## Findings that decide the choice

1. **Every released polygon model works at 256 px.** Raster2Seq says "a fixed resolution of 256 x 256 for all datasets in all experiments" (SOURCED). A Swiss sheet is 2480 x 1753 px. One model pixel covers about 9.7 sheet pixels, which is 16 cm at 1:100 and 33 cm at 1:200 (DERIVED from 1.69 cm and 3.39 cm per px in `swiss.md`). A half-pixel boundary error on a 3 x 3 m room is about 11% of its area at 1:100 (DERIVED). The 256 px limit alone rules these models out for 2% room area.
2. **The papers do not measure area.** Raster2Seq reports no area error and no per-room IoU. IoU only decides whether a room counts as matched (above 0.5) (SOURCED). The same holds for the other three polygon papers in the table (checked on Raster2Seq's tables; I did not open the other three papers' result sections).
3. **WAFFLE precision and recall expose the area bias.** Interior segmentation, trained on CubiCasa5K (SOURCED, Raster2Seq Table 6):

   | Method | IoU | Precision | Recall | Recall / precision (DERIVED, about the net area ratio) |
   |---|---|---|---|---|
   | CubiCasa5K pretrained | 46.1 | 79.9 | 52.1 | 0.65 |
   | FRI-Net | 56.7 | 63.4 | 84.2 | 1.33 |
   | RoomFormer | 60.5 | 65.7 | 88.3 | 1.34 |
   | Raster2Seq | 73.9 | 81.6 | 88.6 | 1.09 |

   The ratio is only a rough guide, because the paper does not say whether the means are per plan or per pixel. It shows that no model is near a 2% net area on unseen styles.
4. **An independent rerun scores Raster2Seq lower.** SALI-FP loaded the released EMA checkpoint on the 400 CubiCasa5K test plans with 256 px bicubic input and got room F1 0.7626, corner 0.5458, angle 0.3681 (SOURCED). The paper says 88.7, 59.4, 37.4. The protocols differ (room IoU above 0.5, corner tolerance 10 px at 256, CPU run), so I do not call it an error. Plan on 75 to 89 room F1, not 89.
5. **Masks beat polygons.** On the same 400 plans the original CubiCasa5K model gets 4-class mIoU 0.7390 as masks and 0.6612 as polygons, room IoU 0.9006, wall IoU 0.7482. A wall-only MiT-UNet gets wall IoU 0.7721 and clDice 0.9302 (SOURCED, SALI-FP Table C.1 and C.8). The CubiCasa5K paper agrees: room mean IoU 57.5 as masks, 49.3 as polygons (SOURCED). The polygon step loses points when a junction is missed. So we produce masks and polygonise with code we control.
6. **Our own flood-fill measurement shows a convention gap.** I reran the Swiss PNG probe with the same 200 floors, seed 7 and 400 room-area questions (MEASURED, `probe2.py` in the scratchpad: `/private/tmp/claude-501/-repo/d76b56b4-2c8d-49ae-95bb-bbb65c392808/scratchpad/exp/probe2_keep.py`). I added the region perimeter P and fitted one boundary offset d (reference area minus region area, divided by P).

   | Measure | Value |
   |---|---|
   | Median d | 3.38 px (3.63 px at 1:100, 2.48 px at 1:200). Quartiles 2.0 to 8.1 px. The offset is not constant |
   | Fit d on even rows (3.33 px), test on odd rows: within 2% | 26% |
   | Same test: within 5% | 46% |
   | Same test: median error | 6.1% |
   | Rooms with error above 20% | 24.75% |
   | By room size, within 2% | under 5 m2: 5%. 5 to 10 m2: 12%. 10 to 20 m2: 45%. over 20 m2: 43% |

   The reference polygon is larger than the visible white region by a median of 3.4 px of perimeter. I did not check the cause. A model trained on the exact Swiss polygons learns this convention. A flood fill cannot. That is the case for fine-tuning.
7. **Scale error doubles in the area.** Area scales with the square of the scale. A 1% scale error is a 2.01% area error (DERIVED). Length needs scale within 2%. For area, the scale witness must be within about 1%, and then the mask must add no error. Lv et al. reach 72% within 2% on their own data, so a single recovered scale will often break the tolerance.
8. **Transfer to our other styles has no evidence.** The only measured transfer is CubiCasa5K to WAFFLE (above). For US construction sets and historic hand drawings I found no number (as in `floorplan-cv.md`). The team's scan survey shows a scale ratio or bar on 28 of 30 habs, 24 of 30 finna, 15 of 30 europeana and 17 of 30 wikimedia sheets (MEASURED, `wild.md`). Where no scale exists, no model gives an area.

## Recommendation and recipe

### The approach for unseen raster styles tonight

```
raster
  -> 1. scale witnesses: ratio text + dpi, scale bar, dimension chain (cluster check), printed m2 labels
  -> 2. mask model (below): interior, wall, boundary, opening
  -> 3. rooms: interior minus wall, door gaps closed with the opening channel,
        split open plans with the boundary channel (watershed), connected components, holes subtracted
  -> 4. polygon: cv2.findContours + shapely, area in px, times (m per px)^2
  -> 5. self-calibration: where a room carries a printed m2 label, fit ONE area factor per sheet
        (ratio of printed to computed), apply it to the rooms without a label,
        and use the spread of those ratios as the confidence
  -> 6. answer: value, polygon, scale witnesses used, spread
        two scale witnesses within 1%  and spread under 2%   -> confirmed
        else                                                  -> a range, and a request for a scale or a calibration click
```

Step 5 is an ESTIMATE of mine. It is not published. It fixes both a small scale error and the systematic boundary offset, because both are one factor per sheet. It works only on sheets with some printed areas (29.5% of Swiss sheets print them; many CubiCasa plans too). Test it first (test 1 below).

Use Raster2Seq `hf:cubicasa5k` only for a room count and adjacency check on whole plans. The inference command is in the repository's `tools/predict_waffle.sh` (SOURCED). It takes a folder of images:

```sh
python predict.py --dataset_root=<folder of images> --checkpoint=hf:cubicasa5k \
  --output_dir=<out> --semantic_classes=12 --input_channels 3 --poly2seq \
  --seq_len 512 --num_bins 32 --disable_poly_refine --dec_attn_concat_src \
  --use_anchor --ema4eval --per_token_sem_loss --drop_wd --save_pred --one_color
```

Setup (SOURCED): Python 3.10, PyTorch 2.3.1 with CUDA 11.8, then compile the deformable-attention ops (`cd models/ops; sh make.sh`) and the differentiable rasteriser (`cd diff_ras; python setup.py build develop`). Speed: 0.52 s per image on an A6000. Expect setup to take 1 to 2 h on a fresh box (ESTIMATE).

### What to fine-tune: one U-Net on masks

**Why a U-Net and not a polygon model.**

- Raster2Seq fine-tuning took 19.4 h plus 16.0 h on one A6000 for CubiCasa5K (SOURCED). That is about 10 to 12 h on an A100 (ESTIMATE). It would still output 256 px polygons.
- A U-Net runs at 1024 px or more and keeps full-resolution features, which the 2% tolerance needs.
- `smp` is MIT. ImageNet encoders are free to use. The only non-commercial inputs are the CubiCasa5K data, and the Swiss data are CC BY 4.0 (SOURCED in `floorplan-cv.md` S29).
- Encoder choice: `resnet50`. ResNet gives features at 1/2, 1/4, 1/8, 1/16 and 1/32. smp states that transformer-style encoders start at 1/4 (SOURCED, smp docs). The MitUNet code builds `smp.Unet` with `mit_b4`, then replaces its encoder with the one from `smp.Segformer` (SOURCED). So `smp.Unet("mit_b4")` may not work as is (UNVERIFIED). On MitUNet's own wall data, U-Net++ with ResNet-50 reaches mIoU 87.25 and boundary IoU 84.68, against 87.91 and 85.01 for MitUNet (SOURCED, one dataset). The gap is small. ResNet-50 is the low-risk start. Upgrade to the MitUNet pattern only if test 6 shows a gap.

**Data.**

| Source | Images | Labels | Notes |
|---|---|---|---|
| Swiss sheets | 1,040 PNG, 2480 x 1753, 150 dpi | DXF layers: `ROOM_OUTLINE` (interior, holes subtracted), `WALL`, `DOOR` plus `WINDOW` (opening), polygon edges drawn 3 px wide (boundary) | One affine map per sheet from DXF metres to pixels (0.03 px median, M-R in `ideas/learned-perception.md`). Split by `site_id`: 800 train, 120 val, 120 test. Sites are already unique per floor |
| CubiCasa5K | 4,200 train plus 400 val of the official split | From `model.svg` with `floortrans/loaders/house.py` logic: `Space` polygons, `Wall`, `Door`, `Window` | Stoa holds 95.7% of these images. Fine for training. Evaluate only on Swiss and on held-out styles |
| Extra Swiss floors (optional, 3 to 4 h of code) | Render from public geometry `geometries.csv` (Zenodo 7788422, CC BY 4.0, v3.0.0; the floor count 13,905 is UNVERIFIED, the page gives 45,176 apartments and about 3,100 buildings) | Exact | Draw in 3 other styles: CubiCasa-like black walls with no hatch, colour-filled rooms, thin line art. Keep the test split disjoint by `site_id`, because the hidden set may reuse sibling floors |

**Augmentation.** Scale 0.5 to 1.5 (so px per metre varies), rotate by multiples of 90 degrees, grayscale, colour inversion, line thinning and thickening, Gaussian blur, JPEG quality 30 to 95, random paper texture and slight skew for a scan look, random erasing of text blocks. Do not use perspective warp (it changes areas).

**Model and training (library, version, config).**

```sh
uv pip install "segmentation-models-pytorch==0.6.0" "timm==1.0.31" "torch==2.15.0" torchvision \
  "albumentations==2.0.8" "opencv-python-headless" "shapely==2.2.0" ezdxf
```

Versions come from PyPI on 2026-11-14 (SOURCED). `smp` 0.6.0 is dated 2026-10-26. I did not run it.

```python
import segmentation_models_pytorch as smp
model = smp.Unet(encoder_name="resnet50", encoder_weights="imagenet", in_channels=3, classes=4)
# channels: 0 room interior, 1 wall, 2 room boundary, 3 door/window opening (multi-label, sigmoid)
```

| Setting | Value |
|---|---|
| Crop | 1024 x 1024 random crops, full sheet at test time (pad to a multiple of 32), 4-rotation test-time average |
| Batch | 8, bf16, channels_last |
| Optimiser | AdamW, lr 3e-4 for the decoder, 1e-4 for the encoder, weight decay 1e-2, 1 epoch warm-up, cosine to 1e-6 |
| Loss | BCE plus Tversky (alpha 0.6, beta 0.4, from MitUNet) on each channel. BCE weight 5 on pixels within 3 px of a boundary |
| Epochs | 40 over about 12,000 crops per epoch (4 per Swiss sheet, 1 to 2 per CubiCasa image) |
| Sampling | Half Swiss, half CubiCasa and rendered styles in each batch |
| VRAM | MitUNet at 512 px and batch 4 uses 1.75 GB (SOURCED). Expect 15 to 25 GB at 1024 px and batch 8 (ESTIMATE). It fits an A100 80 GB with room for batch 16 |
| Time | 25 to 35 images per second on one A100 (ESTIMATE from ResNet-50 throughput and a full-resolution decoder), so 6 to 8 min per epoch, 3 to 5 h in all. About $7 to $12 at $2.37 per hour. Data loading with 8 or more workers is the likely limit |
| Image size at inference | Whole sheet up to about 3000 px on the long side. Tile at 1536 px with 128 px overlap above that. Rescale low-resolution scans (under 1000 px) by 2 before the model |

Training is in-house code: about 150 lines of PyTorch. No ready command exists. `pnpm j gpu run <vm> ../stoa/<dir> -- python train.py ...` fits the repository's GPU rule.

**Evaluation (leave-style-out, by site).**

| Run | Train | Test | Reads as |
|---|---|---|---|
| Cross-style A | CubiCasa5K only | Swiss test PNGs | How far a CubiCasa model travels to a clean CAD style |
| Cross-style B | Swiss only | CubiCasa5K val | The reverse |
| Final | Swiss plus CubiCasa5K plus rendered styles | Swiss test, plus 30 hand-measured scans | The number we ship |

Metrics: share of rooms within 2% and within 5% (using the `swiss.md` conventions: holes subtracted), median absolute error by room size, floor total error, room count F1, and the same with step 5 (self-calibration) on and off. The number to beat is 20.8% within 2% (flood fill).

### Scale recovery on rasters

Build the scale from witnesses and keep each witness with its place on the sheet.

| Witness | How | Expected accuracy | Source of the figure |
|---|---|---|---|
| Ratio text (for example "1:100 (A3)") | PaddleOCR 3.7 (PP-OCRv6, Apache 2.0). Needs the paper size and the scan dpi, or the image size and the paper size | The ratio is exact. The pixel scale is exact only if the dpi is known | Swiss: the ratio is on all sheets (MEASURED, `swiss.md`). Raster dpi is often unknown (MEASURED: CubiCasa has no dpi tag) |
| Scale bar | Detect ticks, measure the bar in px, OCR its labels | About +-1 to 2% | MEASURED on two scans (`wild.md`) |
| Dimension chain | Detect the dimension lines and ends, OCR the numbers, one scale per pair, cluster, keep the largest cluster | 72% of plans within 2% (best published, own data) | Lv et al. 2021, SOURCED |
| Printed room area (m2) | OCR "12.34 m2", divide by computed px area. Gives a pixel-per-metre value | Needs the model mask. A bias in the mask goes into the scale. Use it as a calibration, not as a scale | ESTIMATE |
| Door or wall width prior | Standard door about 0.9 m | +-10 to 30% | Sanity check only |

Rules:

1. Two independent witnesses within 1% give "scale confirmed". One witness gives "scale from one source".
2. Fit x and y separately. If they differ by more than 2%, flag a stretched scan (the idea is in PlanMetric).
3. For area, say what the scale error does: area error is about twice the scale error.
4. No witness, then no area. Return a typed unknown with the request "give a scale or click two points".
5. Dimension text under 1000 px width is often unreadable (MEASURED, `wild.md`). Rescale by 2 and try again, then give up.

### What not to do tonight

- Do not fine-tune Raster2Seq, RoomFormer, PolyRoom or FRI-Net. 256 px input, 10 to 35 h of training, no area gain.
- Do not use a VLM or a frontier model for room area. Open VLMs reach about 43% MAPE (SOURCED, VLM-S8). A vendor post reports room-instance F1 of 0.078 to 0.227 for frontier models on its geometric benchmark (UNVERIFIED: the page returned 403, snippet only).
- Do not publish a number as "within 2%" from one scale witness and one mask.

## Risks and how to test them in 1 hour

Each test has a pass line. Run 1, 2 and 6 first; they decide whether the primary stands.

| # | Risk | Test (about 1 h) | Pass line | If it fails |
|---|---|---|---|---|
| 1 | Self-calibration does not help | On the 307 Swiss sheets with printed areas, use the existing flood-fill region, fit one factor from the labelled rooms, predict the other rooms on the same sheet (leave-one-room-out) | At least 50% of rooms within 2%. The current number is 20.8% | Drop step 5. Answer with a range |
| 2 | The U-Net does not learn the Swiss convention | Overfit 100 Swiss sheets for 20 min with the recipe. Score 20 held-out sheets | At least 60% of rooms of 10 m2 or more within 2% | Add the boundary-weighted loss. Train longer. Check the DXF to PNG map |
| 3 | Raster2Seq fails to build or run on the A100 | Build the ops on a Verda VM (`pnpm j gpu up`), run the WAFFLE command on 30 Swiss PNGs and 30 wild scans | Room count F1 against the DXF at least 0.75. Runs without crash | Drop it. Use the U-Net room count |
| 4 | SAM 3 does anything useful | `Sam3Model` with the text prompt "room" on 20 Swiss PNGs. Needs the gated checkpoint on the box | Rooms found on at least 15 sheets with IoU above 0.8 | Drop it. No time to tune |
| 5 | Scale bar and chain reading below 1% | `measure_scale.py` on 30 scans with a hand measurement. Add OCR of the ratio text | At least 24 of 30 within 1% | Report ranges. Lean on the user calibration click |
| 6 | The throughput and hours are wrong | One smoke run of `smp.Unet("resnet50")` at 1024 px, batch 8, bf16, 50 steps. Also try `smp.Unet("tu-convnext_small")` and the MitUNet swap, to see which build | Images per second at least 20. No shape error | Use the encoder that runs. Cut crops to 768 px. Cut epochs |
| 7 | Style gap is larger than the Swiss test shows | Score the cross-style A and B runs on 100 plans each | Cross-style room IoU at least 0.80 | Add the rendered styles. Add a per-style flag in the confidence |
| 8 | Door gaps merge rooms | Count rooms against the DXF on 100 Swiss sheets, with and without the opening channel | Room count exact on at least 85% of sheets | Raise the opening-channel weight. Split with the boundary channel |
| 9 | Licence blocks a product | Not tested | Weights from CubiCasa5K, Raster2Seq and MitUNet are non-commercial | A Swiss-only model with rendered styles is CC BY 4.0 clean. Retrain on it before any product use |

Hours at risk: 1 to 2 h for the tests, 3 to 5 h of training, in the background. Total fits the 28 h left.

## Open questions

1. Does the hidden set ask raster area questions on drawings that print no m2 label? If not, step 5 is enough and the mask model matters less.
2. Which area convention does Stoa use for rasters (inner wall face, centreline, with or without balconies)? Swiss uses net area with holes subtracted (MEASURED, `swiss.md`). The model learns the convention of its training labels, so a different convention needs a different label.
3. What is the reference scan resolution? CubiCasa images are about 700 to 780 px wide (MEASURED, `cubicasa.md`). At that size 1 px is about 2 cm, so 2% on a 9 m2 room is under 1 px of boundary (DERIVED). Rooms that small cannot pass at that resolution for any model.

## Sources

| id | Title | URL | Date | What it supports |
|---|---|---|---|---|
| R1 | Raster2Seq: Polygon Sequence Generation for Floorplan Reconstruction (Phung, Averbuch-Elor) | https://arxiv.org/abs/2602.09016 (HTML v3 read: https://arxiv.org/html/2602.09016v3) | v1 2026-02-09, v3 2026-08-07, read 2026-11-14 | 256 x 256 input, 512 anchors, 32 bins, hyperparameters, training hours, WAFFLE Table 6, no area metric, VLM refinement |
| R2 | Raster2Seq repository | https://github.com/Cornell-VAILab/Raster2Seq (`tools/predict_waffle.sh`, `tools/finetune_cc5k.sh` read) | pushed 2026-10-26, read 2026-11-14 | MIT code, checkpoint aliases, setup, inference command, 0.52 s per image |
| R3 | haopt/Raster2Seq model card | https://huggingface.co/haopt/Raster2Seq | read 2026-11-14 | Checkpoint subfolders, CC BY-NC 4.0 |
| R4 | RoomFormer repository | https://github.com/ywyue/RoomFormer | read 2026-11-14 | MIT code, Structured3D and SceneCAD checkpoints on polybox, no CubiCasa |
| R5 | PolyRoom: Room-aware Transformer for Floorplan Reconstruction | https://arxiv.org/abs/2407.10439 and https://github.com/3dv-casia/PolyRoom | ECCV 2024, repo read 2026-11-14 | Point-cloud input, Google Drive checkpoints, no licence, polygon count 20 (search snippet of the supplement) |
| R6 | FRI-Net: Floorplan Reconstruction via Room-wise Implicit Representation | https://arxiv.org/abs/2407.10687 and https://github.com/Daisy-1227/FRI-Net | 2024-07-15, repo read 2026-11-14 | Checkpoints on Google Drive, Structured3D and SceneCAD, no licence file |
| R7 | CubiCasa5K: A Dataset and an Improved Multi-Task Model | https://arxiv.org/abs/1904.01920 (PDF read) and https://github.com/CubiCasa/CubiCasa5k | 2019-04-03, read 2026-11-14 | Test mean IoU rooms 57.5 (49.3 polygonised), 256 px training, weights on Google Drive, old environment |
| R8 | Evidence-gated multimodal parsing and vectorization of architectural floor plans (SALI-FP) | https://arxiv.org/html/2609.25615 | 2026-09-22, read 2026-11-14 | Independent CubiCasa5K test scores for Raster2Seq, the 2019 model and MiT-UNet, mask against polygon, $0.818 per plan. First 100,000 characters read; appendices E and F not read |
| R9 | MitUNet: Enhancing Floor Plan Recognition (Parashchuk et al.) | https://arxiv.org/abs/2512.02413 and https://github.com/aliasstudio/mitunet | v3 2026-04-01, read 2026-11-14 | Encoder swap recipe, checkpoint name, NC weights, metrics table, VRAM |
| R10 | WAFFLE: Multimodal Floorplan Understanding in the Wild | https://arxiv.org/abs/2412.00955 and https://github.com/TAU-VAILab/WAFFLE | 2024-12-01, read 2026-11-14 | About 20K images, repository checkpoints (CLIPSeg, ControlNet wall detection) |
| R11 | SAM 3: Segment Anything with Concepts | https://arxiv.org/html/2511.16719v2 | v2 2026-03-28, first 100,000 characters read | RF-100VL 15.2 and 36.5 AP, "out of SAM 3's current scope", 30 ms on H200 |
| R12 | facebook/sam3 model card and repository | https://huggingface.co/facebook/sam3 and https://github.com/facebookresearch/sam3 | read 2026-11-14 | Gated, SAM License, 0.9B (card) and 848M (repo), requirements, `Sam3Model` |
| R13 | SAM 3.1 release notes | https://github.com/facebookresearch/sam3/blob/main/RELEASE_SAM3p1.md | 2026-03-27, read 2026-11-14 | Object Multiplex, video only changes stated |
| R14 | RF-DETR repository | https://github.com/roboflow/rf-detr | read 2026-11-14 | Seg sizes, resolutions, Apache 2.0 for all Seg models |
| R15 | segmentation-models-pytorch docs and repository | https://smp.readthedocs.io/en/latest/encoders.html, https://smp.readthedocs.io/en/latest/encoders_timm.html, https://github.com/qubvel-org/segmentation_models.pytorch | read 2026-11-14 | MIT, `mit_b0` to `mit_b5` with ImageNet weights, transformer-style features start at 1/4, `tu-` prefix |
| R16 | PyPI JSON API (segmentation-models-pytorch, timm, torch, rfdetr, albumentations, shapely, paddleocr, opencv-python-headless, transformers) | https://pypi.org/pypi/segmentation-models-pytorch/json and the same path for the other packages | queried 2026-11-14 | smp 0.6.0 (2026-10-26, MIT), timm 1.0.31, torch 2.15.0, rfdetr 1.12.1 (2026-11-12), shapely 2.2.0, paddleocr 3.7.0 |
| R17 | Lv et al., Residential Floor Plan Recognition and Reconstruction, supplement | https://openaccess.thecvf.com/content/CVPR2021/supplemental/Lv_Residential_Floor_Plan_CVPR_2021_supplemental.pdf (PDF read) | CVPR 2021, read 2026-11-14 | Scale pipeline, Table 2: positive rate 0.72 / 0.83 / 0.86, mean error 4.6 mm |
| R18 | PlanMetric | https://github.com/crown-sports/planmetric | v0.2.1, read 2026-11-14 | Per-axis fit with rejection, MIT, no accuracy claim |
| R19 | Evaluating Vision-language Models for Zero-shot Room Area Estimation in Floor Plan Images (Aliyev, Barsi) | https://pp.bme.hu/ci/article/view/44138 | 2026-08-05 | MAPE 43% for VLMs, 5.68% per room and 1.58% per plan for pixel counting. Carried from `vlm-on-drawings.md`; not opened again |
| R20 | mudasir13cs/qwen25-vl-3b-floorplan-grpo and FloorplanVLM paper | https://huggingface.co/mudasir13cs/qwen25-vl-3b-floorplan-grpo and https://arxiv.org/abs/2602.06507 | paper 2026-02-06, card read 2026-11-14 | Community LoRA on CubiCasa5K, no metric, non-commercial intent. Paper numbers from `floorplan-cv.md` S17 |
| R21 | Mask2Former HF card | https://huggingface.co/facebook/mask2former-swin-large-coco-instance | read 2026-11-14 | 0.2B params, licence "other" |
| R22 | SegFormer HF card | https://huggingface.co/nvidia/segformer-b3-finetuned-ade-512-512 | read 2026-11-14 | Licence "other", 512 px, ADE20k |
| R23 | Search results only (not opened): Raster Image-Based House-Type Recognition, Buildings 15(7):1178 | https://www.mdpi.com/2075-5309/15/7/1178 | 2025 | YOLOv8 plus Shi-Tomasi plus OFA-OCR for dimension ends. Page returned 403. UNVERIFIED |
| R24 | Search results only (not opened): Automated BIM generation from inconsistent multi-view raster architectural drawings with missing dimensions | https://www.sciencedirect.com/science/article/abs/pii/S0926580526002128 | 2026 | LMM scale reading, accuracy 0.707. Page returned 403. UNVERIFIED |
| R25 | Search results only (not opened): AEC-Geometric-Bench (Kamai, vendor) | https://kamai.io/blog/aec-geometric-bench | 2026 | Area pixel F1 0.61 to 0.80 and room-instance F1 0.078 to 0.227 for frontier models. Page returned 403. UNVERIFIED |
| R26 | Swiss Dwellings v3.0.0 | https://zenodo.org/record/7788422 | 2023-03-31 | CC BY 4.0, public geometries for rendering extra floors (carried from `floorplan-cv.md` S29) |
| M1 | Local: Swiss PNG area probe, existing | `stoa/analysis/swiss/probe_png.py`, result in `stoa/docs/research/data/swiss.md` | 2026-11-13 | 4.0% and 20.8% within 2% |
| M2 | Local: Swiss PNG offset probe, new | `/private/tmp/claude-501/-repo/d76b56b4-2c8d-49ae-95bb-bbb65c392808/scratchpad/exp/probe2_keep.py` (same 200 floors, seed 7, 400 questions) | 2026-11-14 | Median offset 3.38 px, 26% within 2% on held-out half, 24.75% of rooms above 20% error |
| M3 | Local: scale and scan notes | `stoa/docs/research/data/wild.md`, `swiss.md`, `cubicasa.md` | 2026-11-13 | Scale presence per source, bar measure of +-1 to 2%, CubiCasa image sizes |

## Verification

Checked on 2026-11-14 by an independent verifier who opened each source. 15 claims.

| Claim | Verdict | Evidence |
|---|---|---|
| HF `haopt/Raster2Seq` exists, subfolders cubicasa5k, raster2graph, raster2graph-512, s3d-bw, s3d-density, weights CC BY-NC 4.0 | CONFIRMED (the card lists the licence and points to a LICENSE file) | https://huggingface.co/haopt/Raster2Seq |
| Raster2Seq code MIT, weights NC, "inference in a commercial SaaS product, is not authorized", Python 3.10 / PyTorch 2.3.1 / CUDA 11.8, `hf:cubicasa5k`, 0.52 s per image on A6000 | CONFIRMED (the SaaS quote is in the GitHub README, not on the HF card) | https://github.com/Cornell-VAILab/Raster2Seq |
| Raster2Seq CubiCasa5K room / corner / angle F1 88.7 / 59.4 / 37.4, room semantic 63.8; RoomFormer 83.5, PolyRoom 54.1, FRI-Net 77.1; fixed 256 x 256 input | CONFIRMED | https://arxiv.org/html/2602.09016v3 |
| WAFFLE Table 6 (IoU / precision / recall for CubiCasa5K, FRI-Net, RoomFormer, Raster2Seq) | CONFIRMED | https://arxiv.org/html/2602.09016v3 |
| Raster2Seq fine-tune hours on CubiCasa5K, 19.4 h plus 16.0 h on one A6000 | CONFIRMED (the paper text is inconsistent on GPU counts for another dataset, not this one) | https://arxiv.org/html/2602.09016v3 |
| SALI-FP exists (arXiv 2609.25615, 2026-09-22); Raster2Seq rerun room 0.7626 / corner 0.5458 / angle 0.3681 | CONFIRMED | https://arxiv.org/html/2609.25615 |
| SALI-FP: original model mask mIoU 0.7390, polygon 0.6612, room IoU 0.9006, wall IoU 0.7482; MiT-UNet wall IoU 0.7721, clDice 0.9302; SALI-FP mIoU 0.3596, room F1 0.445 | CONFIRMED | https://arxiv.org/html/2609.25615 |
| SALI-FP cost $0.818 per plan | CORRECTED: it is a rate-card calculation, not billing | https://arxiv.org/html/2609.25615 |
| MitUNet (arXiv 2512.02413): mIoU 87.91, boundary IoU 85.01, UNet++ ResNet-50 87.25 / 84.68, 1.75 GB VRAM, 512 px, 500 regional plans, Tversky 0.6/0.4 | CONFIRMED. CORRECTED in the text: 87.91 is before CubiCasa fine-tuning (88.53 after) | https://arxiv.org/html/2512.02413v3 |
| MitUNet repo: code MIT, weights CC BY-NC 4.0, file `mitunet_finetune_a6_mit_b4_tversky_8864_28E.pth`, encoder swap from `smp.Segformer` | CONFIRMED | https://github.com/aliasstudio/mitunet |
| `segmentation-models-pytorch` 0.6.0 dated 2026-10-26, MIT; `rfdetr` 1.12.1 dated 2026-11-12, Apache 2.0 for Seg sizes | CONFIRMED (other versions in the pip line - timm, torch, albumentations, shapely - not checked) | https://pypi.org/pypi/segmentation-models-pytorch/json , https://pypi.org/pypi/rfdetr/json |
| `facebook/sam3` gated, licence "other", 0.9B; `facebook/sam3.1` exists, adds Object Multiplex, no Transformers integration | CONFIRMED (848M from the GitHub repo not checked) | https://huggingface.co/facebook/sam3 , https://huggingface.co/facebook/sam3.1 |
| RoomFormer repo: MIT code, no CubiCasa5K checkpoint | CONFIRMED (checkpoint contents inferred from scripts) | https://github.com/ywyue/RoomFormer |
| `mudasir13cs/qwen25-vl-3b-floorplan-grpo`: Apache tag, card says non-commercial, no metrics; Mask2Former card 0.2B, licence "other" | CONFIRMED | https://huggingface.co/mudasir13cs/qwen25-vl-3b-floorplan-grpo , https://huggingface.co/facebook/mask2former-swin-large-coco-instance |
| Swiss Dwellings v3.0.0, CC BY 4.0, 13,905 floors | CONFIRMED for id, version and licence. UNVERIFIED for 13,905 floors (the page gives apartment and building counts only) | https://zenodo.org/record/7788422 |
| Lv et al. CVPR 2021: 72% / 83% / 86% within 2 / 5 / 10%, mean error 4.6 mm | UNVERIFIED (supplement PDF returned 403 to the verifier) | https://openaccess.thecvf.com/content/CVPR2021/supplemental/Lv_Residential_Floor_Plan_CVPR_2021_supplemental.pdf |

Not checked: the local MEASURED numbers, the training-time and throughput ESTIMATEs, and the unopened paper sources (R19, R23 to R25).

Verdict: the primary recommendation (U-Net on masks, own polygonisation) stands. It rests on confirmed evidence that masks beat polygons and that polygon models run at 256 px. Its own accuracy is untested until tests 1, 2 and 6.
