# Computer vision for floor plans and CAD drawings

Track: recognition, symbol spotting, vectorization and counting. Research date: 2026-11-13.

Labels used in this file:

- **MEASURED**: I ran it on our local dataset. The script and the numbers are in this file.
- **READ**: the claim is in a source that I opened. The source id is given, for example [S1].
- **ESTIMATE**: my own reasoning. It is not a measurement.
- **UNVERIFIED**: I saw it only in a search snippet, or the page did not open.

A note on the method: the web fetch tool reached its usage limit near the end of the first pass. The fact check
re-opened the sources with curl. See the "Verification" section at the end.

## Findings that change decisions

1. **Frontier VLMs cannot count door and window symbols exactly.** On 120 floor plans, partly from CubiCasa5K,
   Claude Opus 4.5 got the exact door count on 16% of plans and the exact window count on 16%. The best model,
   Gemini 3 Pro, got 39% and 34%. Bedrooms and toilets were much easier (0.76 to 0.91 across these four models). READ [S1].
   For us: the 53% of cubicasa questions on symbols need a trained detector, not a prompt. This moves accuracy
   and cost.
2. **Exact counts punish small per-object errors, and the counts are large.** MEASURED on the public set: mean
   cubicasa window count 8.78 (max 92), door count 8.74 (max 43); mean Swiss door count 30.7 (max 157), window
   count 17.8 (max 137). ESTIMATE: if each object has an independent 3% chance of a miss or a false hit, the
   exact-count rate is about 0.97^8.8 = 77% for a cubicasa window question and 0.97^30.7 = 39% for a Swiss door
   question. At 1% it is 92% and 73%. For us: use vector data wherever it exists (Swiss DXF, IFC), and tune
   raster detectors on exact-count accuracy, not on mAP. No paper I found reports per-plan exact-count accuracy
   for a detector; mAP is the only published metric [S13][S14].
3. **Every public CubiCasa-trained weight file has seen Stoa's cubicasa images.** MEASURED: Stoa's folder holds
   4,787 images named after the CubiCasa5K folders (3,578 `high_quality_architectural`, 943 `high_quality`,
   266 `colorful`). CubiCasa5K has 5,000 images [S12], so Stoa holds 95.7% of it. The RT-DETR weights were
   trained on the official 4,200-image train split [S13]. Raster2Seq and the CubiCasa model also train on it
   [S15][S11]. For us: any score of these weights on Stoa's cubicasa questions is contaminated. The prior plan's
   "train only on CubiCasa plans without a Stoa question" leaves about 213 images, which is too few.
4. **We have a free, exact, cross-style test set for a raster detector: the Swiss PNG renders.** MEASURED:
   1,040 Swiss floors have a PNG, a DXF and exact answers for doors, windows, toilets, washbasins, bathtubs and
   showers. Their drawing style is not CubiCasa's. For us: train on CubiCasa, then test on Swiss PNGs. This is
   the best proxy we have for "a harder hidden set with other drawings". It moves the trust in our evaluation.
5. **Learned vector symbol spotters do not transfer, and they cost 8 GPUs.** VecFormer, the best FloorPlanCAD
   model (PQ 91.1), scored PQ 8.43 zero-shot on the SESYD floor plans [S5]. SymPoint fell from PQ 83.3 on
   FloorPlanCAD to 33.2 on large CAD plans [S6]. VecFormer trained on 8 A100 GPUs for 500 epochs [S2].
   For us: do not train a vector spotter this weekend. Parse DXF layers with rules instead (finding 6).
6. **The Swiss DXF files carry semantic layers, but naive layer counts are not enough.** MEASURED on 150 random
   Swiss floors: WINDOW polylines divided by 3 match the window answer on 150 of 150. UNIT_OUTLINE count matches
   the apartment answer on 135 of 150. DOOR arcs match the door answer on only 82 of 150 (arcs overcount by 1
   to 14). DOOR polylines divided by 2 match on 98 of 150. For us: the Swiss path is a geometry-grouping
   problem on known layers. It is deterministic and checkable, but needs door rules (double leaves, sliding
   doors).
7. **Zero-shot open-vocabulary detectors fail on small drawing symbols.** Grounding DINO scored mAP50 of about
   0.0 zero-shot on 10 CubiCasa classes; its boxes were 100 to 330 times too large [S14]. Even fine-tuned, it
   reached 39.3 against 67.1 for a small YOLOv8s trained on 1,500 plans [S14]. SAM 3 scored 15.2 AP zero-shot on
   RF-100VL, and its authors write that such specialized domains are "out of SAM 3's current scope" [S18].
   For us: use SAM 3 or CountGD++ only as an exemplar-prompted fallback for symbol types we have no detector
   for, and measure it first.
8. **A small supervised raster detector is cheap and accurate in-domain, but its confidence drops on other
   styles.** RT-DETR-L reached AP50 89.8 (door) and 89.3 (window) on the CubiCasa test split after about 2.3 h on
   2 A100 GPUs [S13]. The same repository reports window confidence of 0.9+ on line art and only about 0.3 to
   0.5 on rendered styles [S13]. In a Buro Happold study, RF-DETR was best on AEC drawing layout (mAP50
   0.949), and models pre-trained on general documents degraded ("domain interference") [S26].
   For us: one detector, trained on CubiCasa with style augmentation, with per-class thresholds tuned on exact
   counts and checked on Swiss PNGs.
9. **Room polygon models transfer partly to plans "in the wild".** Raster2Seq, trained on CubiCasa5K, reached
   interior IoU 73.9 zero-shot on WAFFLE (Wikimedia plans), against 60.5 for RoomFormer and 46.1 for the
   original CubiCasa model [S16]. Its weights are CC BY-NC 4.0 [S15]. For us: a usable room-polygon witness for
   room counts on raster plans, and the only measured transfer evidence toward the historic sources.
10. **Licences split cleanly.** Apache 2.0: RF-DETR N/S/M/L code and weights [S23], PaddleOCR [S27].
    MIT: CountGD++ code [S21], Raster2Seq code [S15]. AGPL-3.0: Ultralytics YOLO and RT-DETR training [S25].
    Non-commercial: CubiCasa5K data [S11], FloorPlanCAD annotations [S9], ArchCAD data [S4], Raster2Seq
    weights [S15]. Custom or gated: SAM 3 [S19], DEIMv2 [S24], T-Rex2 (API only) [S22]. For the hackathon all are
    usable. For Stoa's product story, RF-DETR plus our own data is the clean path.

## Landscape

### Datasets

| Dataset | Content | Labels | Size | Licence | Access today | Source |
|---|---|---|---|---|---|---|
| CubiCasa5K | Finnish real-estate raster plans | SVG polygons, 80+ categories; 11 reduced icon classes; raw names include Shower, ShowerCab, SaunaBench, Toilet, Sink | 5,000 | CC BY-NC 4.0 (repo); Stoa applies CC BY-NC-SA | Zenodo 2613548 | READ [S11][S12] |
| FloorPlanCAD | Residential and commercial CAD plans, vector | Line-level panoptic labels, 35 classes (30 thing, 5 stuff) | 15,663 drawings (Nov 2021 release) | Annotations CC BY-NC 4.0; "We do not own the copyright of the drawings" | Google Drive links; project shut down 2022 | READ [S9] |
| ArchCAD-400K | Mostly commercial and public building CAD | Panoptic, 27 categories, auto-labelled from layers and blocks, then corrected by drafters | 413,062 chunks from 5,538 drawings (paper); HF release says 40k samples | cc-by-nc-4.0, gated, manual approval up to 3 days | HF `jackluoluo/ArchCAD` | READ [S3][S4] |
| Swiss Dwellings v3.0.0 | Swiss apartment geometry (Archilyse) | WKT geometry for areas, walls, doors, windows, features; site/building/floor ids | 45,176 apartments, ~3,100 buildings | CC BY 4.0 | Zenodo 7788422 | READ [S29] |
| Modified Swiss Dwellings (MSD) | Derived from Swiss Dwellings, ML-ready graphs and images | Room graphs and structure images | 4,167 train plans | CC BY 4.0 (4TU) | 4TU.ResearchData | READ [S28] |
| ResPlan | Residential vector plans with room graphs | Vector geometry, graphs | 17,000 (paper confirmed) | Paper: CC BY 4.0; the Kaggle conflict (CC BY-NC-SA) is UNVERIFIED | Kaggle, GitHub | READ [U1] (size, paper licence) |
| WAFFLE | Wikimedia Commons plans, many styles and eras | OCR text, grounded legends, a small segmentation benchmark | ~18,556 (snippet); ~100 annotated for segmentation [S16] | "Wikimedia Commons license" for code; per-image licences | SharePoint links | READ [S30], size UNVERIFIED |
| R2V (LIFULL) | Japanese real-estate plans | Vector annotations only | Not stated | Repo MIT; "We don't have the permission to share the rasterized images" | GitHub | READ [S32] |
| RPLAN | Chinese residential plans | Room masks | ~80k (memory) | Request form, research use | Not checked | UNVERIFIED (page did not open) |
| Structured3D | Synthetic house designs, 3D | 3D structure; floor plans not stated on the page | 3.5K designs | Structured3D Terms of Use, gated form | Form | READ [S31] |
| AntPlan | Professional plans with furniture | 92 object classes, 10 room types | 505 | Not stated | Not checked | READ [S35] |
| SESYD | Synthetic symbol floor plans | Symbol instances | Not checked | Not checked | Used as a zero-shot test in [S5] | READ [S5] |

### Symbol spotting on vector drawings (FloorPlanCAD PQ)

| Method | Year | PQ without layer prior | PQ with layer prior | Out-of-domain evidence | Code / weights | Source |
|---|---|---|---|---|---|---|
| CADTransformer | 2022 | 68.9 | - | - | - | READ [S2] |
| SymPoint | 2024 | 83.3 | - | 33.2 PQ on LS-CAD after FloorPlanCAD training | - | READ [S2][S6] |
| SymPoint-V2 | 2024 | 83.2 | 90.1 | 16.23 PQ zero-shot SESYD | Weights on Google Drive, no licence file | READ [S2][S5][S10] |
| CADSpotting | 2024-26 | 87.4 (point cloud, no layer or type input) | 88.9 | 52.9 PQ on LS-CAD (60.1 with SWA) | No code link | READ [S6][S2] |
| DPSS (ArchCAD) | 2025 | 86.2 | 89.5 | Pre-training on ArchCAD speeds FloorPlanCAD training (figure only) | GitHub ArchiAI-LAB/ArchCAD | READ [S3] |
| VecFormer | 2025 | 88.4 | 91.1 | 8.43 PQ zero-shot SESYD | GitHub WesKwong/VecFormer, licence not stated | READ [S2][S5] |
| TextCAD | 2026-07 | Claims SOTA; no numbers on the abstract | - | - | No code link | READ [S8] |
| PolarSym | 2026-08 | +1.73 PQ over a reproduced SymPoint-V2 | - | - | No code link | READ [S7] |
| TempFit (template fitting) | 2026-10 | 86.2 (greedy), 80.1 (Hungarian) | - | 24.67 PQ zero-shot SESYD, best in its table | Project page only | READ [S5] |

All of these use per-primitive labels from CAD layers or human annotators. Training cost: VecFormer 8 A100 x 500
epochs [S2], DPSS 8 A800 [S3]. The Stoa-relevant point: our DXF files already have the layer prior (DOOR, WINDOW,
FIXTURE, ROOM_OUTLINE, UNIT_OUTLINE), which is the "with prior" setting where rules alone go far (MEASURED,
finding 6).

### Raster detectors

| Model family | Licence | Floor-plan evidence | Source |
|---|---|---|---|
| RT-DETR-L (Ultralytics) | AGPL-3.0 (training library) | CubiCasa test AP50 door 89.8, window 89.3, wall 82.3; 2 A100, ~2.3 h, 60 epochs, 1024 px | READ [S13] |
| YOLOv8s (Ultralytics) | AGPL-3.0 | 1,500 CubiCasa plans: mAP50 67.1 on 10 classes; detection rate 97% at IoU >= 0.1 for door, window, closet | READ [S14] |
| YOLOX-s | Apache 2.0 | Same protocol: mAP50 65.7 | READ [S14] |
| YOLO26 | AGPL-3.0 | Listed as "the latest" in the Ultralytics docs text; the repo title also lists a newer YOLO27; no floor-plan result found | READ [S25] |
| RF-DETR N/S/M/L | Apache 2.0 | AEC drawing layout mAP50 0.949 [S26]; RF100-VL AP50:95 57.7 to 62.2 [S23] | READ [S23][S26] |
| DEIMv2 | Custom licence, commercial use by contact | No floor-plan result found | READ [S24] |
| D-FINE | Not checked | Not checked | - |
| Community weights | AGPL (floorcad-yolov8n, FloorPlanCAD, val mAP50 0.770); non-commercial (2dplan2strct RF-DETR-M, val mAP50 94.5, training data not named) | Validation only, not independent | READ [S33][S34] |

### Raster-to-vector reconstruction and room segmentation (CubiCasa5K F1)

| Method | Room F1 | Corner F1 | Angle F1 | Room semantic F1 | Window and door F1 | Source |
|---|---|---|---|---|---|---|
| HEAT | 78.2 | 53.7 | 32.3 | - | - | READ [S16] |
| PolyRoom | 54.1 | 37.1 | 23.0 | - | - | READ [S16] |
| FRI-Net | 77.1 | 50.8 | 38.0 | - | - | READ [S16] |
| RoomFormer | 83.5 | 55.5 | 34.1 | 63.0 | 78.5 | READ [S16] |
| Raster2Seq (SIGGRAPH 2026) | 88.7 | 59.4 | 37.4 | 63.8 | 77.8 | READ [S16] |
| Raster2Graph | Own dataset only: 95.0 room F1 vs 97.0 for Raster2Seq | | | | | READ [S16] |
| FloorplanVLM (Beike, Qwen2.5-VL-3B) | Own FPBench-2K only: room IoU 0.892, opening F1 0.733; no public-set result; weights not mentioned in the paper | | | | | READ [S17] |
| SALI-FP (evidence-gated pipeline) | 11,534 plans in a production audit; no code | | | | | READ [S36] |

### Open-vocabulary and class-agnostic counting

| Model | What it takes | Evidence | Licence and access | Source |
|---|---|---|---|---|
| SAM 3 | Noun phrase and/or positive and negative exemplar boxes | CountBench accuracy 93.8; RF-100VL zero-shot 15.2 AP, 10-shot 36.5 AP; no drawing results | Gated HF, "License: other", 0.9B params | READ [S18][S19] |
| CountGD++ (CVPR 2026) | Text, exemplars, negative prompts, synthetic exemplars; usable as an LLM tool | Natural-image benchmarks only | MIT code, 1.25 GB weights | READ [S20][S21] |
| Grounding DINO | Text | 0.0 mAP50 zero-shot on CubiCasa symbols | Apache 2.0 | READ [S14] |
| T-Rex2, Grounding DINO 1.5, DINO-X | Text and visual prompts | No drawing results found | T-Rex2 API only, IDEA License 1.0; Rex-Omni "fully open-sourced" | READ [S22] |
| OWLv2, CountZES, CountSE, SAM3Count | - | Not opened; no drawing results seen in snippets | - | UNVERIFIED |

### Scale, dimensions and text

- OCR: PaddleOCR 3.7.0 (2026-06-11) with PP-OCRv6, 50 languages in one model; PaddleOCR-VL-1.5 lists 111
  languages; Apache 2.0. READ [S27].
- AECV-Bench found text extraction the strongest VLM skill (up to 0.95) and symbol understanding the weakest.
  READ [S1]. ESTIMATE: room labels (MH, KH, WC, Küche) and printed areas are best read by OCR or a VLM, and
  symbols are best counted by a detector.
- I found no open model that reads a scale bar or dimension chain on architectural plans with a published
  accuracy. A hybrid method (YOLO for dimension regions, OCR for values, scale from dimension text) exists in
  MDPI Buildings 16(5):1043 (Crossref confirms the paper; the abstract lists dimension detection, text recognition and scale recovery; the YOLO detail is UNVERIFIED) [U4].
- Text and symbol separation: TextCAD treats text as a second modality in vector spotting [S8]. For rasters,
  ESTIMATE: mask OCR boxes before detection, so letters such as "o" or "WC" do not trigger symbol hits.

### Transfer across drawing styles (the evidence that exists)

| From | To | Result | Source |
|---|---|---|---|
| CubiCasa5K (raster) | WAFFLE (Wikimedia, mixed eras) | Raster2Seq interior IoU 73.9; CubiCasa model 46.1 | READ [S16] |
| CubiCasa5K (raster) | AntPlan line-art plans | Walls transfer well; window confidence 0.9+ on line art, 0.3 to 0.5 on rendered styles; furniture false hits | READ [S13] (qualitative) |
| FloorPlanCAD (vector) | LS-CAD large buildings | SymPoint 33.2 PQ, CADSpotting 52.9 PQ | READ [S6] |
| FloorPlanCAD (vector) | SESYD | VecFormer 8.43 PQ, SymPoint-V2 16.23, TempFit 24.67 | READ [S5] |
| General documents (DocLayNet) | AEC drawings | "domain interference", worse than general detectors | READ [S26] |
| Any detector | US construction sets, historic hand drawings | No quantitative evidence found | - |

ESTIMATE for our four styles:
- Finnish real-estate plans: in-domain for CubiCasa-trained models. High accuracy, but contaminated evaluation.
- Swiss CAD output: use the DXF. For the PNG, a CubiCasa detector is a cross-style test (finding 4).
- US construction sets (opening_design): dense sheets with schedules and tags. Expect symbol detectors to
  fail; schedules and tags are the reliable source.
- Historic hand drawings: no counting questions exist in the public set. Room polygons (Raster2Seq) and OCR are
  the only parts with any transfer evidence. Abstain on symbol counts with low detector confidence.

## What we can use this weekend

| # | What | Model / repo / weights | Licence | Effort | Notes |
|---|---|---|---|---|---|
| 1 | Swiss DXF counter | `ezdxf` + `shapely` on layers DOOR, WINDOW, FIXTURE, ROOM_OUTLINE, UNIT_OUTLINE, ROOM_TEXT | MIT libraries; data CC BY 4.0 | 4-6 h (ESTIMATE) | Windows already 150/150 (MEASURED). Doors need grouping rules. Fixture classes (WC, washbasin, bathtub, shower) need a small geometry classifier or rules on FIXTURE circles and polylines. |
| 2 | Tonight's raster baseline | `OldDeLorean/rtdetr-floorplan-detector`, `weights/rtdetr_l_autoresearch_60ep.pt` (66 MB) | Repo licence not stated; Ultralytics AGPL-3.0 | 1 h | Doors and windows only. Use it on Swiss PNGs as an honest test; its CubiCasa scores are contaminated. Input 1024 px. Lower `--conf` to 0.15 for faint door arcs [S13]. |
| 3 | Our own CubiCasa symbol detector | `rfdetr` (RF-DETR-M or L), COCO export from CubiCasa SVG via `house.py` logic | Apache 2.0 code and weights; CC BY-NC-SA data | 3-4 h converter, 4-6 h training on 1 A100 (ESTIMATE from 2.3 h on 2 A100 for RT-DETR-L [S13]), about $10-15 at $2.37/h | Classes from raw SVG names: window, door, toilet, sink, bathtub, shower, sauna bench. The default 11-class map drops Shower [S11]. Use k-fold splits by drawing for honest numbers. Augment with grayscale, line thinning, blur and JPEG to widen style. |
| 4 | Exact-count calibration | Our harness | - | 2 h | Tune per-class confidence on exact-count accuracy. Report a confidence from flip and rotation agreement (count must not change). |
| 5 | Room polygons on rasters | `Cornell-VAILab/Raster2Seq`, HF `haopt/Raster2Seq`, key `cubicasa5k` | MIT code, CC BY-NC 4.0 weights | 3-4 h | 0.52 s per image on an A6000 [S15]. A witness for bedroom, kitchen and bathroom counts. It does not read text, so pair with OCR. |
| 6 | OCR for room labels, area labels, dimensions | PaddleOCR 3.7 (PP-OCRv6) | Apache 2.0 | 2-3 h | Finnish abbreviations (MH, KH, PH, WC, S) and Swiss labels. Mask text boxes before symbol detection. |
| 7 | Fallback for unknown symbol types | SAM 3 (exemplar boxes) or CountGD++ (exemplars plus negative prompts) | SAM License (gated) / MIT | 3-4 h | Unproven on drawings [S18]. Measure on Swiss PNG fixtures before use. Low expected gain (ESTIMATE). |
| 8 | Scale | OCR of dimension strings and scale text, then a pixel-per-metre fit; abstain if no scale | - | 3-4 h | No published open model found. "I do not know: no scale" is the honest output the host asked for. |

Commands (READ from the repos, not yet run by me):

```sh
pip install rfdetr          # Apache 2.0, Python >= 3.10 [S23]
# Raster2Seq: scripts accept hf:cubicasa5k and download on first use [S15]
# RT-DETR weights: weights/rtdetr_l_autoresearch_60ep.pt in the repo [S13]
```

## What does not work

- **Prompting a frontier VLM to count doors and windows.** Best exact match 0.39 door and 0.34 window; Claude
  Opus 4.5 0.16 and 0.16 [S1]. VLMs also fail when shape types mix [S37].
- **Zero-shot Grounding DINO on plan symbols.** mAP50 about 0.0 [S14].
- **Fine-tuning a general open-vocabulary detector instead of a specialist.** Grounding DINO fine-tuned: 39.3
  mAP50; plain fine-tuning 7.5; YOLOv8s specialist 67.1 [S14].
- **Vector panoptic spotters outside their training set.** 8.43 to 33.2 PQ out of domain [S5][S6].
- **Training a vector spotter in a weekend.** 8 A100 GPUs for 500 epochs [S2]; 8 A800 [S3].
- **Document-layout pre-training for drawings.** "domain interference" [S26].
- **Waiting for FloorplanVLM.** The paper mentions no weights; trained on 32 H200 GPUs with 2M plans sampled from 20M vector plans of an industrial design platform [S17]. FPBench-2K is open-source.
- **Using mAP or detection rate as a proxy for count accuracy.** "97% detection" in [S14] is recall at IoU >= 0.1
  and says nothing about exact counts. ESTIMATE in finding 2 shows why.
- **Evaluating public CubiCasa weights on Stoa cubicasa images.** Contaminated (finding 3).

## Open questions

1. Did Stoa derive the cubicasa answers from the CubiCasa5K SVGs? A calibration run (SVG counts vs Stoa answers
   per template) settles it, and it sets the class mapping. If yes, the public-set ceiling for a detector is
   the SVG label noise.
2. Does the hidden set reuse the CubiCasa images? If yes, contamination helps the score but is a pitch risk. If
   no, the Swiss-PNG transfer test (finding 4) is the number to trust.
3. Will the hidden set ask counting questions about historic scans (habs, finna, europeana, wikimedia)? No
   public labels exist. We should hand-label 30 to 50 of them for a small transfer test.
4. How does Stoa score "I do not know"? This decides the abstention threshold on low-confidence counts.
5. Which door rules did Stoa use for Swiss doors (double leaves, sliding doors)? MEASURED naive rules reach only
   55% to 65%.

## Check of the prior research

I read `weekend-plan.md` (sections 1 to 5) and searched `research-tracks.json` after my own search.

| Prior claim | Verdict | Evidence |
|---|---|---|
| "Frontier models get door and window counts exactly right on at most about 0.55 of plans" | **Correct it.** 0.40 to 0.55 is the *mean over four classes*. Door and window exact match is 0.39 and 0.34 at best, and 0.16 and 0.16 for Claude Opus 4.5. | [S1] Table 1 |
| "Small supervised detectors reach 97% per-object detection on doors and windows with only 1,500 training plans" | **Misleading.** 97% is detection rate at IoU >= 0.1, a very loose match. The same model has mAP50 67.1 over 10 classes. It is not a count metric. | [S14] |
| "RT-DETR-L reaches about 90 AP50 in 2.3 h on 2xA100" | **Confirmed** for doors (89.8) and windows (89.3). Add: trained on the split that contains Stoa's images, so its Stoa scores are contaminated. | [S13], MEASURED |
| "Grounding DINO scores 0.0 mAP50 zero-shot on CubiCasa symbols" | **Confirmed.** | [S14] |
| VecFormer: 8 A100, 500 epochs; do not train vector spotters | **Confirmed.** Add the transfer failure (8.43 PQ on SESYD). | [S2][S5] |
| SAM 3: no published evaluation on floor plans | **Agree.** I found none either. Add: 15.2 AP zero-shot on RF-100VL and "out of SAM 3's current scope". | [S18] |
| Train on "the CubiCasa train split minus every id in Stoa's question file" | **Does not work.** Stoa holds 4,787 of 5,000 CubiCasa images, so about 213 remain. Use k-fold by drawing, plus the Swiss PNG test. | MEASURED, [S12] |
| "Do not use the default 11-class mapping. It merges Toilet with Urinal and drops showers." | **Confirmed.** Shower and ShowerCab map to no class in `icons_selected`; Urinal merges into Toilet. | [S11] |
| Expected accuracy: doors and windows 60-80%, toilets and sinks 80-90%, showers and bathtubs 40-70% | **Unsupported estimate.** No source reports per-plan exact counts for detectors. Finding 2 gives a model for it. | - |
| Licence notes: CubiCasa CC BY-NC-SA, Ultralytics AGPL, RF-DETR-M Apache 2.0 | **Confirmed.** CubiCasa repo says CC BY-NC 4.0; Stoa applies the stricter SA. | [S11][S23][S25] |

## Local measurements

All on `stoa/data/junction-dataset/` (full set). Scripts were in the session scratchpad.

- M1: cubicasa folder prefixes: 3,578 `high_quality_architectural`, 943 `high_quality`, 266 `colorful` (4,787).
- M2: count distributions per template (mean, median, max): cubicasa windows 8.78 / 6 / 92, doors 8.74 / 8 / 43,
  toilets 1.39 / 1 / 20, sinks 2.61 / 2 / 30, showers and bathtubs 1.19 / 1 / 22; Swiss doors 30.7 / 26 / 157,
  windows 17.77 / 15 / 137, toilets 4.11 / 3 / 38, washbasins 4.33 / 4 / 33, apartments 3.2 / 3 / 16.
- M3: Swiss DXF `site1000_bldg2082_floor9385.dxf`: layers DOOR (36 ARC, 72 LWPOLYLINE), WINDOW (84 LWPOLYLINE),
  FIXTURE (40 CIRCLE, 75 LWPOLYLINE), ROOM_OUTLINE 79, UNIT_OUTLINE 4, ROOM_TEXT 85, WALL; `$INSUNITS` 6 (metres);
  no symbol blocks. Answers: doors 36, windows 28, apartments 4.
- M4: 150 random Swiss floors (seed 0): windows = WINDOW polylines / 3 on 150/150; apartments = UNIT_OUTLINE
  count on 135/150; doors = DOOR arcs on 82/150; doors = DOOR polylines // 2 on 98/150.
  Answer minus arc count: 0 on 82 floors, negative on all others (-1 to -14).

## Sources

| id | URL | title | date | claim it supports | exact supporting quote | check |
|---|---|---|---|---|---|---|
| S1 | https://arxiv.org/abs/2601.04819 (PDF read) | AECV-Bench: Benchmarking Multimodal Models on Architectural and Engineering Drawings Understanding (Kondratenko, Birhane, Hsain, Maciocci) | 2026-01-08 | VLM exact-count accuracy on doors and windows | "Even the strongest models plateau around 0.4–0.55 mean exact-match accuracy, with large and systematic errors for symbol-heavy classes such as doors and windows." Table 1: "Claude Opus 4.5 0.42 0.16 0.16 0.91 0.76"; "(e.g., Gemini: 0.39 door, 0.34 window)" | confirmed (Table 1 columns are Mean, Door, Window, Bedroom, Toilet; Claude Opus 4.5 toilet is 0.76, not above 0.82) |
| S2 | https://arxiv.org/html/2505.23395 | Point or Line? Using Line-based Representation for Panoptic Symbol Spotting in CAD Drawings (VecFormer; Wei et al.) | v3 2025-10-17 | FloorPlanCAD PQ table; training cost | Table 1a: VecFormer "88.4 ... 91.1"; "500 epochs with a batch size of 2 per GPU on 8 NVIDIA A100 GPUs" | confirmed |
| S3 | https://arxiv.org/html/2503.22346v1 | ArchCAD-400K (Luo, Liu et al.) | 2025-03-28 | Dataset size, DPSS results, cost | "413,062 chunks from 5538 highly standardized drawings"; "The model is trained on 8 NVIDIA A800 GPUs" | confirmed (v1 title as cited; the latest arXiv title reads "ArchCAD-400K: A Large-Scale CAD drawings Dataset and New Baseline for Panoptic Symbol Spotting", updated 2025-11-12; the paper says 27 categories) |
| S4 | https://huggingface.co/datasets/jackluoluo/ArchCAD | ArchCAD dataset card | read 2026-11-13 | Licence and gating | "cc-by-nc-4.0"; "Access is restricted to non-commercial use."; "40k Samples" | confirmed |
| S5 | https://arxiv.org/html/2610.17776 | TempFit: Panoptic Symbol Spotting via Template Fitting (Xu et al.) | 2026-10-13 | Zero-shot transfer failure of vector spotters | Table 6, zero-shot SESYD PQ: "VecFormer 8.43", "SymPointV2 16.23", "TempFit 24.67" | confirmed (numbers; submission date not separately checked) |
| S6 | https://arxiv.org/html/2412.07377v5 | CADSpotting: Robust Panoptic Symbol Spotting on Large-Scale CAD Drawings (Yang et al.) | v5 2026-08-07 | Cross-dataset PQ | Supplementary Table 8, trained on FloorPlanCAD: "SymPoint ... 33.2", "CADSpotting ... 52.9" | confirmed (the 60.1 SWA cell sits in the LS-CAD columns of a table with a missing header) |
| S7 | https://arxiv.org/abs/2608.11793 | PolarSym: Polar Geometry-aware Attention for CAD Floorplan Parsing (Chen et al.) | 2026-08-12 | Newest vector-spotting gain | "+1.73% PQ, +1.54% RQ" over a reproduced SymPoint V2 | confirmed |
| S8 | https://arxiv.org/abs/2607.12678 | Text-Aided Multi-Modal Panoptic Symbol Spotting for CAD Floor Plan Drawings (TextCAD; Gong et al.) | 2026-07-14 | Text as a modality in spotting | Abstract: TextCAD "effectively improves symbol spotting performance and achieves state-of-the-art results" (no numbers on the page) | confirmed |
| S9 | https://floorplancad.github.io/ | FloorPlanCAD project page (Fan et al., ICCV 2021) | 2021, read 2026-11-13 | Dataset size and licence | "licensed under a Creative Commons Attribution-NonCommercial 4.0 License"; "We do not own the copyright of the drawings."; "15,663 CAD drawings" | confirmed ("This project was shutdown in early 2022") |
| S10 | https://github.com/nicehuster/SymPointV2 | SymPointV2 repository | read 2026-11-13 | Weights exist, no licence | "I uploaded the weight in google drive, you can download from this url" | confirmed (no licence file or licence text on the page) |
| S11 | https://github.com/CubiCasa/CubiCasa5k (+ LICENSE, floortrans/loaders/house.py) | CubiCasa5K repository | 2019, read 2026-11-13 | Licence, weights, class map | "CubiCasa5K is licensed under a Creative Commons Attribution-NonCommercial 4.0 International License."; "Our model weights file can be downloaded here"; house.py maps "Shower", "ShowerCab" to None and "Urinal" to "Toilet" | corrected (LICENSE file and house.py confirmed; the README sentence is "model weights file can be downloaded here" under Evaluation, not "Our model weights file...") |
| S12 | https://arxiv.org/abs/1904.01920 | CubiCasa5K: A Dataset and an Improved Multi-Task Model for Floorplan Image Analysis (Kalervo et al.) | 2019-04-03 | Dataset size | "a large-scale floorplan image dataset containing 5000 samples annotated into over 80 floorplan object categories" | confirmed |
| S13 | https://github.com/OldDeLorean/rtdetr-floorplan-detector | RT-DETR-L structural floor-plan detector (part of arXiv 2606.10953) | 2026, read 2026-11-13 | Detector accuracy, cost, style drop | "CubiCasa5K official split (4200 train), 60 epochs, 2×A100 (~2.3 h)"; door AP50 "89.8", window "89.3"; "0.9+ on line-art glyphs, ~0.3–0.5 on rendered styles" | confirmed (no licence on the page; repo says it is part of Architect-Ant, arXiv 2606.10953) |
| S14 | https://github.com/heypaprika/gdino | Zero-shot Grounding DINO on CubiCasa5K | read 2026-11-13 | Open-vocab failure; specialist strength; detR meaning | "Zero-shot mAP@0.5 ≈ 0.0 on 10 classes (400 test plans)."; "a small in-domain detector (YOLOv8s, 1500 plans) reaches mAP@0.5 = 67.1"; header "detR (IoU≥0.1)" | confirmed (also 100-330x box size, 7.5 plain fine-tune, YOLOX-s 65.7) |
| S15 | https://github.com/Cornell-VAILab/Raster2Seq | Raster2Seq repository (Phung, Averbuch-Elor) | 2026, read 2026-11-13 | Licences, checkpoints, training time | "Raster2Seq source code is licensed under the MIT License."; weights "CC BY-NC 4.0"; CubiCasa5K "19.4 h" + "16.0 h" on 1 A6000; "0.52 seconds per image" | confirmed |
| S16 | https://arxiv.org/html/2602.09016v2 | Raster2Seq: Polygon Sequence Generation for Floorplan Reconstruction (SIGGRAPH 2026) | v2 2026-05-11 | CubiCasa F1 table; zero-shot WAFFLE | Table 1: "Raster2Seq 88.7 59.4 37.4 63.8 77.8", "RoomFormer 83.5 55.5 34.1 63.0 78.5"; Table 6: "Raster2Seq 73.9", "RoomFormer 60.5", "CubiCasa5K pretrained 46.1" | confirmed (numbers; arXiv shows an update on 2026-08-07, so the v2 date 2026-05-11 was not checked) |
| S17 | https://arxiv.org/html/2602.06507v1 | FloorplanVLM: A Vision-Language Model for Floorplan Vectorization (Liu et al., Beike) | 2026-02-06 | VLM vectorization, no weights | Base "Qwen2.5-VL-3B", "trained on 32×H200 GPUs"; FPBench-2K overall "IoU_room 0.8920", "F1_op 0.7333" | partly (Qwen2.5-VL-3B, 32 H200, IoU_room 0.8920 and F1_op 0.7333 confirmed; the paper says Floorplan-2M is sampled from 20M vector plans of an industrial interior-design platform, it does not say "private"; it does not state whether weights exist) |
| S18 | https://arxiv.org/html/2511.16719v2 | SAM 3: Segment Anything with Concepts (Meta) | v2 2026-03-28 | Counting and domain-transfer numbers | CountBench "SAM 3 0.12 93.8"; RF-100VL "SAM 3 ... 15.2 ... 36.5"; "RF-100VL contains domains with specialized prompts that are out of SAM 3's current scope" | confirmed |
| S19 | https://huggingface.co/facebook/sam3 | facebook/sam3 model card | read 2026-11-13 | Gating, licence, size | "You need to agree to share your Hugging Face information to access this model"; "License: other"; "0.9B params" | confirmed (gated: manual; license:other; 0.9B params) |
| S20 | https://arxiv.org/abs/2512.23351 | CountGD++: Generalized Prompting for Open-World Counting (Amini-Naieni, Zisserman), CVPR 2026 | 2025-12-29 | Prompt types | "extend the prompt to enable what not to count to be described with text and/or visual examples" | confirmed (revised 2026-05-30, v2) |
| S21 | https://github.com/niki-amini-naieni/CountGDPlusPlus | CountGD++ repository | read 2026-11-13 | Licence and weights | "MIT license"; "Download the pretrained CountGD++ model available here (1.25 GB)" | confirmed |
| S22 | https://github.com/IDEA-Research/T-Rex | T-Rex repository (IDEA Research) | read 2026-11-13 | T-Rex2 is API-only | "API code for T-Rex2"; "We use IDEA License 1.0"; Rex-Omni "fully open-sourced" | confirmed |
| S23 | https://github.com/roboflow/rf-detr | RF-DETR repository (Roboflow), ICLR 2026 | read 2026-11-13 | Licence per size; RF100-VL AP | Nano to Large "Apache 2.0"; XL and 2XL "PML 1.0"; Medium RF100-VL AP50:95 "61.2" | confirmed (also: Atto, Femto, Pico, XL, 2XL are PML 1.0 under rfdetr[plus]; Nano is Apache 2.0 with AP50:95 57.7) |
| S24 | https://github.com/Intellindust-AI-Lab/DEIMv2 | DEIMv2 repository | 2025-09-26, read 2026-11-13 | Custom licence | "This project is released under the DEIMv2 License." | confirmed (LICENSE.md is non-commercial only, commercial use by contact; the 2025-09-26 date was not found on the page) |
| S25 | https://github.com/ultralytics/ultralytics | Ultralytics repository | read 2026-11-13 | AGPL, latest model | "AGPL-3.0 License"; "the latest YOLO26" | corrected (the repo title lists "YOLO27, YOLO26, YOLO11, YOLOv8"; its docs text calls YOLO26 "the latest", so YOLO27 exists and is newer in the repo) |
| S26 | https://arxiv.org/pdf/2607.18997 (PDF read) | Benchmarking Deep Learning Approaches for AEC Engineering Drawing Layout Detection and Information Extraction (Huang et al., Buro Happold, EC3 2026) | 2026-07 | RF-DETR on AEC drawings; document pre-training hurts | "RF-DETR achieves state-of-the-art performance with an mAP50 of 0.949"; "models pre-trained on general document datasets suffer from "domain interference"" | confirmed (authors Huang, Lombardi et al., EC3 2026 Corfu, July 2026) |
| S27 | https://github.com/PaddlePaddle/PaddleOCR | PaddleOCR repository | 3.7.0 2026-06-11 | OCR licence and languages | "This project is released under the Apache 2.0 license"; PP-OCRv6 "supports 50 languages with a single unified model" | confirmed |
| S28 | https://data.4tu.nl/datasets/e1d89cb5-6872-48fc-be63-aadd687ee6f9 | Modified Swiss Dwellings (dataset) | v2 2023-07-11 | Licence and origin | "CC BY 4.0"; "derived from the Swiss Dwellings database (v3.0.0)"; train split "contains 4167 floor plans" | confirmed |
| S29 | https://zenodo.org/record/7788422 | Swiss Dwellings v3.0.0 (Archilyse AG) | 2023-03-31 | Public geometry with doors, windows, features | "the geometries of all areas, walls, railings, columns, windows, doors and features (sinks, bathtubs, etc.) of an apartment"; CC BY 4.0 | confirmed (page returned 403 to curl; confirmed through the Zenodo API: v3.0.0 2023-03-31, CC BY 4.0, original record 2022-09-20) |
| S30 | https://github.com/TAU-VAILab/WAFFLE | WAFFLE repository (Ganon et al., WACV 2025) | read 2026-11-13 | Licence, annotations, checkpoints | "We release our code under the Wikimedia Commons license" | confirmed (licence sentence; the README has no image count or annotation count) |
| S31 | https://structured3d-dataset.org/ | Structured3D | read 2026-11-13 | Terms and gating | "The data is released under the Structured3D Terms of Use, and the code is released under the MIT license." | confirmed |
| S32 | https://github.com/art-programmer/FloorplanTransformation | Raster-to-Vector (R2V) repository | read 2026-11-13 | Images not shared | "We don't have the permission to share the rasterized images" | confirmed |
| S33 | https://huggingface.co/mudasir13cs/floorcad-yolov8n-detect | floorcad-yolov8n-detect | read 2026-11-13 | Community FloorPlanCAD weights | "YOLOv8 weights are released under AGPL-3.0"; val "mAP50 0.770" | confirmed |
| S34 | https://huggingface.co/OsamaMo/2dplan2strct | 2dplan2strct (RF-DETR-M) | read 2026-11-13 | Community raster weights, NC | "License: non-commercial-research-only"; "COCO box mAP@0.5: 94.52%" (validation) | confirmed |
| S35 | https://arxiv.org/abs/2606.10953 | Architect-Ant: Editable Automatic Furnishing of Architectural Floor Plans (Rodionov et al.) | v2 2026-09-30 | AntPlan dataset | "505 real professional architectural floor plans" with "92 object classes" | confirmed |
| S36 | https://arxiv.org/abs/2609.25615 | Evidence-gated multimodal parsing and vectorization of architectural floor plans (Chen et al.) | 2026-09-22 | Evidence-gated reviewable outputs | "an evidence-gated multimodal pipeline"; "including 752,510 valid polygon-bearing objects" | confirmed |
| S37 | https://arxiv.org/abs/2510.04401 | Your Vision-Language Model Can't Even Count to 20 (Guo et al.) | 2025-10-06 | VLM compositional counting failure | Models "can count reliably when only one shape type is present" but "exhibit substantial failures when multiple shape types are combined" | confirmed |
| U1 | https://arxiv.org/html/2508.14006 | ResPlan | 2025-08 | Size and licence | opened in the fact check | partly (opened: arXiv paper says 17,000 plans and "CC BY 4.0"; the Kaggle licence conflict was not checked) |
| U2 | https://www.aecfoundry.com/blog/can-ai-really-read-your-building-plans-aecv-bench-gets-a-major-upgrade | AECV-bench upgrade blog | - | Newer model results | opened in the fact check | confirmed (page opens; GPT-5 doors 12%; newer model results not read in detail) |
| U3 | https://www.kreo.net/news-2d-takeoff/floor-plan-recognition-technologies | Kreo floor plan recognition | - | Gemini 2.5 Pro doors 26%, windows 14% | opened in the fact check | confirmed (Gemini 2.5 Pro doors 26%, windows 14%, average 41%) |
| U4 | https://www.mdpi.com/2075-5309/16/5/1043 | Hybrid DL and rule-based architectural drawing vectorization | 2026 | Scale from dimension text | see check column | partly (MDPI page returns 403; Crossref confirms it exists: "A Hybrid Deep Learning and Rule-Based Method for Architectural Drawing Vectorization and CAD Reconstruction", Buildings 16(5), 2026-03-06, Lin, Wang; abstract lists dimension detection, text recognition and scale recovery; the use of YOLO is not confirmed) |

## Verification

- Date: 2026-11-13. Method: pages fetched with curl (the web fetch tool was at its usage limit); arXiv HTML and PDF text,
  GitHub pages and raw files, Hugging Face pages, the Zenodo API and Crossref. Not run: the local MEASURED scripts.
- Sources opened: 41 of 41 (S1 to S37 and U1 to U4). S29 came through the Zenodo API and U4 through Crossref, because the
  pages returned 403.
- Results: 36 confirmed, 2 corrected (S11, S25), 3 partly (S17, U1, U4), 0 not found.
  (S30 is confirmed for its licence sentence; the "~18,556" size in the dataset table stays UNVERIFIED.)
- No finding rests on a source that was not found, so no finding is marked **UNVERIFIED**.
- Corrections made in the text:
  1. Finding 1: bedroom and toilet exact-match range is 0.76 to 0.91 across the four models, not 0.82 to 0.91 (Claude Opus 4.5 toilet is 0.76).
  2. Finding 2: 0.99^30.7 is 73%, not 74%. The other numbers (77%, 39%, 92%) hold.
  3. S25 and the YOLO26 row: the repo title also lists YOLO27, so YOLO26 is not the newest model there.
  4. S17: "2M private plans" is not in the paper. Floorplan-2M is sampled from 20M vector plans of an industrial design platform. The paper does not mention weights, so "no weights" is now "not mentioned".
  5. S11: the quoted README sentence was reworded in the table.
  6. U1, U2, U3 and U4 were opened. U2 and U3 are confirmed, U1 is partly confirmed (17,000 plans, paper licence CC BY 4.0), U4 is partly confirmed.
  7. The method note at the top no longer says three sources are unverified.
- Remaining UNVERIFIED: the WAFFLE size "~18,556" (not in the README), the Kaggle licence conflict for ResPlan, the YOLO detail in U4, the RPLAN row, and the version dates of S5 and S16 (S16 shows a later update on 2026-08-07).
- Checked and held: all numbers in findings 1, 5, 7, 8 and 9, the PQ tables, the F1 table, the licence claims in finding 10 and the "What we can use this weekend" table (RF-DETR Apache 2.0 N/S/M/L, rfdetr needs Python 3.10 or newer, Raster2Seq MIT code and CC BY-NC 4.0 weights, RT-DETR weights file name and 66 MB, `--conf 0.15`, 0.52 s per image).
