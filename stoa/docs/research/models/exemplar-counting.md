# Exemplar counting: find and count a symbol from one or a few examples

Date: 2026-11-14. Scope: training-free or few-shot ways to count a symbol type that we have no detector for, when we have one to three examples (a legend crop, or one click). Read with `../sota/floorplan-cv.md` (it holds the first look at SAM 3 and CountGD++) and `../../DECISION.md`.

Labels: **SOURCED** (id in the Sources table, page opened on 2026-11-14 unless a date is given), **ESTIMATE** (my reasoning, not measured), **UNVERIFIED** (I could not open the source, or the claim is a secondary report).

## In short

0. **Verification (2026-11-14): the primary recommendation stands.** The model id, MIT licence, 0.2B size, open access and the quoted scores were confirmed. One score label was wrong: MAE 8.39 needs pseudo plus synthetic exemplars. With pseudo-exemplars only the MAE is 10.29. See the "Verification" section.
1. **Primary: benchmark CountGD++ first** (`nikigoli/CountGDPlusPlus`, CVPR 2026). MIT licence, not gated, 0.2B parameters (SOURCED, S3, S4). It takes an exemplar from another image (the legend crop) and negative exemplars (the other legend symbols). Nothing else on the list does both, and it is the only strong one we can download now.
2. **Fallback: SAM 3** (`facebook/sam3`), with a box exemplar on the same image as the sheet tile. It is the strongest on photos, but access is manual (hours to 16 days, S9), it stops at 200 objects per image, and it undercounts dense small objects (S1, S6, S7). **Ask for access now.**
3. **No method here has a published result on drawings or floor plans.** I searched for it and found none (the closest, S12, is a feature request dated 3 days ago, with no numbers). All scores below are on photos, where the best exemplar counters still miss by several objects per image (FSC-147 MAE 7.6 to 8.4, S3, S5). Treat the output as candidate marks with a score. Do not treat it as an exact count.
4. **On a vector PDF or DXF, do not use a neural model.** Match the symbol by geometry (block name, form XObject, path signature). It is exact and it handles rotation. Use the models below on raster input only.
5. **Rotation, symbols that touch walls and scale are untested for all of them.** For rotation, three papers say exemplar matchers are not invariant (S10, S11, S13). Test the four rotations in the first hour.

## Candidates

All speed and memory figures are on photos, not on drawings. "Cross-image" means the exemplar can come from another image, such as the legend.

| Method and id | Weights, licence, gate | Size, VRAM, speed | Closest published result | Known failure modes | Verdict |
|---|---|---|---|---|---|
| **CountGD++** `nikigoli/CountGDPlusPlus` (arXiv 2512.23351, CVPR 2026) | HF, **MIT, not gated**, 0.2B params. Code `niki-amini-naieni/CountGDPlusPlus` is MIT (S3, S4). FSC-147 licence for product use: UNVERIFIED | 900 queries per image (S3). VRAM and speed for ++ not given. Its predecessor CountGD: 15.47 GB reserved, 1.3 s per image, 3.3 s on dense images, on one A100 (S5, Table 5). Needs `transformers<4.50` (model card install command, S4; the GitHub `requirements.txt` does not pin it, but pins `torch<2.6`) | Text plus pseudo plus synthetic exemplars (t+p+s): FSCD-147 MAE 8.39, RMSE 27.03. Text plus pseudo-exemplars only: MAE 10.29, RMSE 33.52 (CORRECTED in verification; the earlier text said "3 pseudo-exemplars" for 8.39). CARPK MAE 2.48 (text plus 3 pseudo-exemplars). **Negatives help a lot:** blood cells MAE 11.56 to 1.73, PairTally 46.41 to 35.27 (S3) | Text-only is weak (MAE 16.55). Dense small objects were a failure case of CountGD (S5). `count()` has no adaptive cropping, so we tile ourselves (S4). One positive text prompt only. Rotation: UNVERIFIED | **Benchmark first** |
| **SAM 3** `facebook/sam3` (arXiv 2511.16719; 3.1 on 2026-03-27 is a video update) | HF, **gated, manual approval**. "SAM License": no non-commercial clause, military and export limits, same terms on redistribution, indemnity (S8). Reported waits: under 1 h to 16 days (S9) | 848M params in the README (S1). Other sources say 473.6M, 310M. Input fixed at 1008 px, patch 14. **200 queries, so 200 objects at most** (S2). 8 GB VRAM and 2.5 s per image on an A100 in HF, full resolution (S7). 30 ms on an H200 (S1), 251 ms on an L4 (S14). Python 3.12, PyTorch 2.7+, CUDA 12.6+ (S1) | One box exemplar, no text: COCO AP+ 76.8, LVIS 76.0, ODinW13 82.2 (T-Rex2: 58.5, 65.8, 61.8). CountBench acc 93.8. CARPK MAE 3.52 and OmniCount 0.44, text-only (S6). **RF-100VL: 15.2 AP zero-shot, 36.5 AP after 10-shot fine-tuning**, and the authors call those domains "out of scope" (S1) | Undercounts dense small scenes, even with a lower threshold (S6). Over-segments: 2,074 false positives against 663 for YOLO11n on apples (S7). Exemplars work on the same image only (S1, S15). Exemplar-only prompts are ambiguous (S1). Cross-image exemplar baseline on CAD parts: PQ 0.141 (S16). Negatives hurt in a collage test (S17). Plateau after about 4 clicks (S1) | **Fallback** |
| **GeCo2** `jerpelhan/GECO2` (arXiv 2511.08048, AAAI 2026) | Code MIT. Weights on an HF dataset repo (S18) | **4.98 GB, 0.2 s per image, 0.4 s dense, on one A100.** Fixed 1024 px. Exemplars scaled so the average is under 80 px (S18) | FSCD-147 test MAE 7.64, RMSE 39.39, AP 46.81 (S18). Best detection AP of the counters I read | 3 box exemplars, same image (cross-image not stated). No negative prompts. Dense >300 objects: MAE 96.92. Rotation: UNVERIFIED | **Second to try** (cheap, small, built for dense small objects) |
| **OWLv2** `google/owlv2-large-patch14-ensemble` (HF Transformers `image_guided_detection`) | HF, Apache-2.0, 0.4B, 960 px input (S19) | Small | **No exemplar counting result found.** Text-only ShanghaiTech B: MAE 81.5, against 32.2 for CountGD-Box (S3) | Weak on dense scenes, no negative prompts. Model card says "research output" | Skip. Use only as a cheap smoke test |
| **T-Rex2** (IDEA) | **API only**, IDEA License 1.0, no weights (S20) | Cloud | Beaten by SAM 3 on one-exemplar COCO, LVIS, ODinW13 (S1) | Sends our images to a third party. Pricing not stated | Skip |
| **T-Rex-Omni** (arXiv 2511.08997) | No code or weights link found | 10.45 FPS on an RTX 3090 (Swin-T) | FSC147 MAE 13.76 with 3 boxes, worse than T-Rex 8.72 and T-Rex2 10.94 (S21) | More positives hurt | Skip |
| **Rex-Omni** `IDEA-Research/Rex-Omni` | HF, IDEA License 1.0, built on Qwen2.5-VL-3B (research licence) (S22) | 3B MLLM | Task `visual_prompting` takes reference boxes. **No counting number** | Licence unclear for product use | Skip |
| **DINOv3 features + template matching** (CountingDINO style) | DINOv3: HF, **gated**, own licence, ViT-L 300M, patch 16 (S23). CountingDINO used DINOv2; no code link found (S10) | Needs 4x tiling, 16 backbone passes (S10) | CountingDINO FSC-147 test: 3 exemplars MAE 20.93 / RMSE 71.37, **1 exemplar 37.73 / 131.71** (S10). Trained counters: 7.6 to 8.4 | Rotated instances undercount. Assumes at most one object per patch. One exemplar is weak (S10). INSID3 (CVPR 2026) is one-shot segmentation, not counting (S24) | Skip as a counter. DINOv3 is still a candidate to verify a hit (second witness) |
| **Classical template matching** (OpenCV `matchTemplate`, chamfer) | OpenCV, Apache-2.0 | CPU, milliseconds per tile (ESTIMATE) | None on current drawings. Rezvanifar et al. state that rotation is a weakness of pixel-based spotters (S11). SESYD, the usual test set, has no occlusion or clutter (S11) | No rotation or scale invariance by itself (S11). Template includes wall lines when the symbol touches a wall (ESTIMATE) | Build as a **cheap second witness** with 4 rotations, mirror and 3 scales. Do not rely on it alone |
| **Fine-tuned few-shot detectors** (TFA style, Jamieson et al. 2024) | n/a | n/a | Paper exists for engineering drawings; I got a 403 and read no numbers (S25) | Needs training | UNVERIFIED. Not training-free |

Other trained-on-FSC-147 counters (LOCA, DAVE, CounTR, CountSE) are older or text-only. OCCAM (no prompts, SAM2 plus clustering) reaches FSC-147 MAE 16.92, and its code is not released (S26). I skip them.

## Recommendation and recipe

**Benchmark CountGD++ first, with the legend crop as an external exemplar and the other legend symbols as negative exemplars.** Reasons:

- It is the only candidate that is open now, takes a cross-image exemplar, takes negative exemplars, and has 900 queries (S3, S4).
- Our unseen symbols have no good noun. A legend symbol is an icon, so a text prompt cannot name it, and SAM 3 with an exemplar and no text is "quite ambiguous" in its own paper (S1).
- Drawings are full of lookalikes (door arcs, circles, hatches). The only measured fix for lookalikes is negative exemplars, and CountGD++ shows a large gain from them (S3). SAM 3 with a negative box got worse in one test (S17).
- Cost of the first test is about one hour with no access request (S4).

### Setup (CountGD++)

Use a separate virtual environment. CountGD++ pins `transformers<4.50` and SAM 3 needs a newer stack (S1, S4).

```sh
# on a Verda VM: pnpm j gpu up 1A100.22V --hours 2   (about 4.7 USD)
uv venv cgd && . cgd/bin/activate
uv pip install torch torchvision "transformers<4.50" timm addict "yapf==0.40.1" termcolor \
  scipy matplotlib opencv-python-headless pycocotools pyyaml huggingface_hub safetensors
python - <<'PY'
from huggingface_hub import snapshot_download
import sys
p = snapshot_download("nikigoli/CountGDPlusPlus"); sys.path.insert(0, p)
from countgdpp import CountGDPlusPlus, count   # names from the model card (S4)
PY
```

The card lists these inputs (S4). I did not run them, so check the exact signature in `example.py`:

- `exemplar_boxes`: pixel `[x1, y1, x2, y2]` on the exemplar image. `exemplar_image`: the legend sheet, when the exemplar is not on the tile.
- `negative_texts`, `negative_exemplar_boxes`, `negative_exemplar_images`: one list per negative text.
- Output: `result["boxes"]` as normalised `(cx, cy, w, h)` and `result["count"]`.
- Text format in the paper: `"t+ . t-1 . t-2 ."` (S3). Default threshold 0.23 (S3).
- Compiled deformable-attention kernels are optional. Without them it runs a pure PyTorch version, slower (S4).

### Pipeline around it (ESTIMATE unless marked)

1. **Candidates only on raster tiles.** Cut the plan view into tiles with 25% overlap. Scale each tile so the exemplar box is 40 to 100 px (GeCo2 scales so the average exemplar is under 80 px, S18). SAM 3 and CountingDINO both need several patches per object (S1, S10), so a symbol under 40 px at 1008 px input is too small.
2. **Exemplar size and orientation.** Crop the legend symbol tight, with no wall lines. Add the 90, 180 and 270 degree rotations as extra positive exemplars, or run each tile four times and merge. Mixed-orientation exemplars gave weaker activations in CountingDINO (S10), so test both ways.
3. **Merge.** Global NMS at IoU 0.3 across tiles. Remove the legend region from the results.
4. **Second witness.** Score each hit with a classical template match (4 rotations, mirror, 3 scales, on the distance transform of the line art). Keep hits where both agree. Mark one-witness hits as "to check", in line with `DECISION.md` rule 4.
5. **Output.** Marks with scores. A person clicks to add or remove marks, and the answer is the number of confirmed marks.
6. **One click from the user.** Click gives a box (segment the connected strokes near the click, or use SAM 3 point mode). That box is the exemplar. Same pipeline.

### Cost (ESTIMATE)

One A100 costs 2.37 USD per hour, so 0.066 cent per second. The whole document has about 10 cents (152 s of A100). If a sheet needs 40 tiles at 1.3 s (the CountGD figure, S5) that is 52 s and 3.4 cents for one symbol type. Four rotations multiply it by four. **The rotation test is the cost test.** Restrict tiles to the plan view, drop empty tiles by ink density, and batch.

### Fallback recipe (SAM 3)

- Request access to `facebook/sam3` today with a full use-case text (reports say it shortens the wait, S9). Use a token that can read public gated repos (S9).
- Image inference with Transformers: `Sam3Model`, `Sam3Processor`, `input_boxes` in pixel xyxy, `input_boxes_labels` 1 positive and 0 negative (S2). Transformers has no integration for 3.1, so use `facebook/sam3` (S4 on the 3.1 card, S2).
- Native exemplars work on the same image only (S1, S15). For the legend, either keep the legend and the plan in one tile, or paste the legend crop into a strip next to the tile and drop hits inside the strip (the collage trick of S17, shown on natural images only).
- Tile as above: SAM 3 stops at 200 queries (S2) and undercounts dense small objects (S6).
- If access does not arrive: Roboflow self-hosting says weights "download automatically" with a Roboflow API key and takes box exemplars with `box_labels` (S14). Whether it needs HF approval, and its licence, are UNVERIFIED. The hosted API sends our images out.
- Fine-tune only if the benchmark shows promise: the paper fine-tunes with 10 shots per class, 40 epochs, a tenth of the usual learning rate, batch size 2, and mask losses off. That moved RF-100VL from 15.2 to 36.5 AP (S1). Training extras are `pip install -e ".[train,dev]"` (S1). Hours on one A100: ESTIMATE under 1 h per class set. Not for this weekend unless the benchmark gates it.

### What I did not find

- No paper or repository that tests SAM 3, CountGD++, GeCo2 or T-Rex on floor plans, CAD drawings or P&IDs. Searches: floor plan, engineering drawing, technical drawing, P&ID, symbol spotting. The nearest are CAD-prompted SAM 3 on 3D-printed parts and T-LESS (S16), TMR on scanning-electron-microscope images, qualitative only (S13), and fine-tuned few-shot P&ID work (S25, not read).
- No source on SAM 3 or CountGD++ with rotated exemplars. TMR, CountingDINO and a floor-plan spotting paper say such matchers are not rotation invariant (S11, S13, S10).

## Risks and how to test them in 1 hour

Setup: use drawings with known mark positions from our own data (Swiss PNG with DXF truth, CubiCasa SVG, a few wild scans). Pick 6 symbol types the detector does not know (for example toilet, sink, stair arrow, wardrobe, radiator, fire exit). Take the exemplar from a different drawing of the same style (legend case) and from the same drawing (one-click case). Same GPU, same tiles for every method.

| Risk | Test (minutes) | Pass if (ESTIMATE) |
|---|---|---|
| Method does not work on line art at all | 15: 20 tiles, 1 exemplar, CountGD++ vs GeCo2 vs OpenCV baseline. Score exact count, count within 1, and box recall at IoU 0.3 | Exact count on at least 50% of tiles with 1 exemplar. VLM counts are 0.34 to 0.39 on whole plans (S27, `STATE-OF-THE-ART.md`) |
| Rotated symbols | 10: rotate the same tiles by 90, 180, 270. Compare to upright | Exact-count rate falls by under 15 points, or the 4-rotation merge fixes it |
| Symbols touching walls | 10: split hits by "touches a long line" using the DXF truth. Compare recall | Recall on touching marks within 15 points of free marks |
| Scale and style change | 10: exemplar from drawing A, targets on drawing B (other CAD style), and rescale tiles by 0.5x and 2x | Count error grows by under 2x. If not, scale each tile to a fixed exemplar size |
| Lookalikes | 5: run with and without negative exemplars | Negatives cut false positives by at least half |
| Dense sheets | 5: one sheet with 60 or more marks. Check for the 200-object cap and for missed marks | No cap hit. Recall at 60 marks within 10 points of recall at 10 marks |
| Cost and time | During all runs, log seconds per tile, VRAM and total A100 seconds per sheet | At most 20 s per symbol type per sheet (about 1.3 cents) |
| Legend differs from plan | 5: use a legend crop whose style differs from the plan symbol (hand-picked cases) | Report the failure rate. Fall back to a click on the plan |
| Access and licence | 0 now: request SAM 3 access, check that CountGD++ downloads without a token | Access request filed. FSC-147 and component licences read before any product use |

Decision rule: if CountGD++ passes the first row, keep it as the unseen-symbol path and add the OpenCV witness. If it fails and GeCo2 passes, switch to GeCo2. If both fail and SAM 3 access has arrived, run the same table on SAM 3. If all fail, ship the vector path plus "click to add marks", and write "cannot count this symbol type on this scan" with a request for a click.

## Sources

| Id | Title | URL | Date | Supports |
|---|---|---|---|---|
| S1 | SAM 3: Segment Anything with Concepts (arXiv 2511.16719v2); HTML opened in two parts (appendix B and C were cut off) | https://arxiv.org/html/2511.16719v2 | v2 2026-03-28 | Exemplar format, same-image use, 1-exemplar AP table, CountBench, RF-100VL 15.2 and 36.5, fine-tune setup, 30 ms on H200, "out of scope" quote |
| S2 | Transformers docs, SAM3 | https://huggingface.co/docs/transformers/en/model_doc/sam3 | read 2026-11-14 | `Sam3Model`, `input_boxes` and labels, 1008 px, 200 decoder queries |
| S3 | CountGD++: Generalized Prompting for Open-World Counting (arXiv 2512.23351, CVPR 2026) | https://arxiv.org/html/2512.23351 | 2025-12-29, v2 2026-05-30 | FSCD-147, blood cell, PairTally, CARPK tables, negative prompts, external exemplars, 900 queries, threshold 0.23, text format |
| S4 | CountGD++ model card and repository | https://huggingface.co/nikigoli/CountGDPlusPlus ; https://github.com/niki-amini-naieni/CountGDPlusPlus | read 2026-11-14 | MIT, not gated, 0.2B, usage and argument names, `transformers<4.50`, adaptive cropping not in `count()`; SAM 3.1 card (https://huggingface.co/facebook/sam3.1) says no Transformers integration |
| S5 | Generalized-Scale Object Counting with Gradual Query Aggregation (GECO2 paper, arXiv 2511.08048) | https://arxiv.org/html/2511.08048 | 2025-11-11 | CountGD memory and time on A100, dense MAE, GeCo2 numbers and resolution |
| S6 | AdaCount: Training-Free Similarity-Guided Spatial and Feature Adaptation (arXiv 2607.02139) | https://arxiv.org/html/2607.02139 | 2026-07 (arXiv id) | SAM 3 vs CountGD++ on FSC-147, CARPK, OmniCount; dense undercount; 1008 px; SAM3Count cost |
| S7 | Generalization vs. Specialization: SAM3 vs fine-tuned YOLO (arXiv 2512.11884) | https://arxiv.org/html/2512.11884v1 | 2025-12 | A100, 8 GB, 2.5 s per image, false positives. The paper has internal inconsistencies, listed in my notes; I used only the A100 time, memory and false-positive counts |
| S8 | SAM License | https://github.com/facebookresearch/sam3/blob/main/LICENSE | updated 2025-11-19 | Terms |
| S9 | facebook/sam3 discussion 53 (access approval); search summary of related threads | https://huggingface.co/facebook/sam3/discussions/53 | Dec 2025 to Jan 2026 | Waits from under 1 h to 16 days. The "token permission" and "use-case text" advice is from a search summary, UNVERIFIED |
| S10 | CountingDINO (arXiv 2504.16570) | https://arxiv.org/html/2504.16570 | 2025-04-23 | DINOv2 training-free counting, 1 vs 3 exemplars, tiling, rotation and one-per-patch failures |
| S11 | Rezvanifar et al., Symbol Spotting on Digital Architectural Floor Plans Using a Deep Learning-based Framework (CVPRW 2020), read from a downloaded copy | https://openaccess.thecvf.com/content_CVPRW_2020/papers/w34/Rezvanifar_Symbol_Spotting_on_Digital_Architectural_Floor_Plans_Using_a_Deep_CVPRW_2020_paper.pdf | 2020 | Rotation weak for pixel-based spotters; SESYD has no occlusion or clutter |
| S12 | opentakeoff issue 627, few-shot symbol detector | https://github.com/Kentucky-ai/opentakeoff/issues/627 | 2026-11-11 | A vector matcher is exact for one block and returns nothing on raster. No method, no numbers |
| S13 | Few-Shot Pattern Detection via Template Matching and Regression (TMR, arXiv 2508.17636) | https://arxiv.org/html/2508.17636 | 2025-08 | "Rotation invariance remains a challenging problem"; SEM images only qualitative; small-exemplar crowd failure |
| S14 | Roboflow docs, SAM3 | https://docs.roboflow.com/models/supported-models/sam3 | read 2026-11-14 | Exemplar payload, 251 ms on an L4, self-hosting, 16 prompt cap |
| S15 | Ultralytics docs, SAM 3 | https://docs.ultralytics.com/models/sam-3 | read 2026-11-14 | Manual HF access, no cross-image exemplars, 2,921 ms and 473.6M params on an RTX PRO 6000 |
| S16 | CAD-Prompted SAM3 (arXiv 2602.20551) | https://arxiv.org/html/2602.20551 | 2026-02 | SAM 3 exemplar baseline PQ 0.141 (3D prints), 0.171 (T-LESS), 0.415 (ITODD). Exemplars there are renders, so it is a cross-image case |
| S17 | Few-Shot Semantic Segmentation Meets SAM3 (arXiv 2604.05433) and repo `WongKinYiu/FSS-SAM3` | https://arxiv.org/abs/2604.05433 ; https://github.com/WongKinYiu/FSS-SAM3 | 2026-04-07 | Collage trick for cross-image exemplars; negatives lower mIoU (66.6 to 54.8 with 1 negative). PDF unreadable, repo README used |
| S18 | GECO2 repository | https://github.com/jerpelhan/GECO2 | read 2026-11-14 | MIT, weights links, box exemplars |
| S19 | OWLv2 Transformers docs and model card | https://huggingface.co/docs/transformers/en/model_doc/owlv2 ; https://huggingface.co/google/owlv2-large-patch14-ensemble | read 2026-11-14 | Apache-2.0, 0.4B, 960 px, `image_guided_detection` |
| S20 | T-Rex repository (IDEA Research) | https://github.com/IDEA-Research/T-Rex | read 2026-11-14 | T-Rex2 is API only; IDEA License 1.0 |
| S21 | T-Rex-Omni (arXiv 2511.08997) | https://arxiv.org/html/2511.08997 | 2025-11 | FSC147 MAE 13.76, speed, no release link |
| S22 | Rex-Omni repository | https://github.com/IDEA-Research/Rex-Omni | read 2026-11-14 | IDEA License 1.0, Qwen base, `visual_prompting` task, 2025-10-15 |
| S23 | DINOv3 ViT-L model card | https://huggingface.co/facebook/dinov3-vitl16-pretrain-lvd1689m | read 2026-11-14 | Gated, DINOv3 License (terms not read), 300M, patch 16 |
| S24 | INSID3 (arXiv 2603.28480, CVPR 2026) | https://arxiv.org/abs/2603.28480 | 2026-03 | One-shot segmentation with frozen DINOv3, not counting |
| S25 | Jamieson, Elyan, Moreno-Garcia, Few-Shot Symbol Detection in Engineering Drawings (Applied AI, vol 38) | https://doi.org/10.1080/08839514.2024.2406712 | 2024-09-29 | UNVERIFIED: publisher PDF returned 403; I read no numbers |
| S26 | OCCAM (arXiv 2601.13871) | https://arxiv.org/html/2601.13871 | 2026-01 | Prompt-free counting FSC-147 MAE 16.92; code not released |
| S27 | AECV-Bench (arXiv 2601.04819), via `STATE-OF-THE-ART.md` section 5 | https://arxiv.org/abs/2601.04819 | 2026-01 | VLM exact counts doors 0.39, windows 0.34. Not re-opened by me |

Also read, not cited above: Meta SAM 3.1 announcement (https://ai.meta.com/blog/segment-anything-model-3/, 2026-03-27; video only, no mention of a Meta API, so the "Meta Model API on 2026-09-18" claim from a search summary is UNVERIFIED); SAM 3 repository README (https://github.com/facebookresearch/sam3; 848M params, Python 3.12, PyTorch 2.7+, CUDA 12.6+, 2026-03-27 release note).

Notes on conflicting figures: SAM 3 parameter count is 848M (README), 473.6M (Ultralytics table), 310M (S7) and 0.9B (HF card, per `floorplan-cv.md`). SAM 3 latency is 30 ms to 2.9 s depending on GPU, resolution and stack (S1, S7, S14, S15). I did not run any model, so every speed and memory figure comes from a paper or a page.

## Verification

Checked on 2026-11-14 by an independent reader who opened the primary pages. The recommendation (benchmark CountGD++ first, SAM 3 as fallback) stands.

| Claim | Verdict | Evidence URL |
|---|---|---|
| `nikigoli/CountGDPlusPlus` exists, MIT, 0.2B params | CONFIRMED | https://huggingface.co/nikigoli/CountGDPlusPlus |
| CountGD++ is not gated (no token in the usage example) | CONFIRMED (page does not say "not gated" in words; the example downloads with no token) | https://huggingface.co/nikigoli/CountGDPlusPlus |
| CountGD++ code repository is MIT | CONFIRMED | https://github.com/niki-amini-naieni/CountGDPlusPlus |
| CountGD++ is arXiv 2512.23351, CVPR 2026 | CONFIRMED | https://arxiv.org/abs/2512.23351 |
| FSCD-147 MAE 8.39, RMSE 27.03 is "text plus 3 pseudo-exemplars" | CORRECTED: it is text plus pseudo plus synthetic exemplars. Text plus pseudo gives MAE 10.29, RMSE 33.52 | https://arxiv.org/html/2512.23351v2 |
| Text-only MAE 16.55; CARPK MAE 2.48; blood cells 11.56 to 1.73; PairTally 46.41 to 35.27; threshold 0.23; 900 queries | CONFIRMED | https://arxiv.org/html/2512.23351v2 |
| Needs `transformers<4.50` | CONFIRMED on the model card; the GitHub `requirements.txt` has no such pin | https://huggingface.co/nikigoli/CountGDPlusPlus/raw/main/README.md |
| Usage argument names (`exemplar_boxes`, `exemplar_image`, `negative_*`, `result["count"]`, `result["boxes"]`) | CONFIRMED | https://huggingface.co/nikigoli/CountGDPlusPlus |
| `facebook/sam3` exists and is gated | CONFIRMED (licence shown only as "other") | https://huggingface.co/facebook/sam3 |
| SAM 3 parameter count 848M | CORRECTED for the HF card: it shows 0.9B (the note at the end already lists 0.9B). The 848M figure from the README was not re-opened: UNVERIFIED | https://huggingface.co/facebook/sam3 |
| SAM 3 RF-100VL 15.2 zero-shot, 36.5 10-shot, "out of scope" quote | CONFIRMED | https://arxiv.org/html/2511.16719v2 |
| SAM 3 one-exemplar COCO 76.8, LVIS 76.0, ODinW13 82.2; T-Rex2 58.5, 65.8, 61.8; CountBench 93.8 | CONFIRMED | https://arxiv.org/html/2511.16719v2 |
| GeCo2 FSCD-147 MAE 7.64, RMSE 39.39, AP 46.81 | CONFIRMED | https://arxiv.org/html/2511.08048v1 |
| GeCo2 4.98 GB, 0.2 s, 0.4 s dense, dense MAE 96.92; CountGD 15.47 GB, 1.3 s, 3.3 s; 1024 px | CONFIRMED (the paper text says 0.4 s average; Table 5 says 0.2 s) | https://arxiv.org/html/2511.08048v1 |
| GeCo2 code is MIT | CONFIRMED | https://raw.githubusercontent.com/jerpelhan/GECO2/main/LICENSE |
| CountingDINO FSC-147 test MAE 20.93 (3 exemplars), 37.73 (1 exemplar) | CONFIRMED | https://arxiv.org/html/2504.16570v3 |
| OWLv2 `google/owlv2-large-patch14-ensemble`, Apache-2.0, 0.4B | CONFIRMED (960 px input not on the page: UNVERIFIED) | https://huggingface.co/google/owlv2-large-patch14-ensemble |
| SAM 3 wait times, 200-query cap, 8 GB and 2.5 s (S7), 251 ms on L4, DINOv3 gate, T-Rex2 API only | UNVERIFIED (not re-opened) | n/a |
