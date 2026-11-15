# Open datasets for training and for held-out tests (14 November 2026)

Scope: datasets beyond CubiCasa5K, Swiss Dwellings v3 and IFC-Bench v2. Every download was tried from this
machine on 2026-11-14. Labels: **SOURCED** (URL in the Sources table), **MEASURED** (I ran it today),
**ESTIMATE**, **UNVERIFIED** (could not open the source).

## In short

1. **Train the unseen-style detector on FloorPlanCAD, from the Voxel51 mirror.** It downloads today with no gate: 5,308 PNG tiles, 48,465 labelled instances (doors, windows, stairs, toilets, sinks, baths, furniture), CC BY-NC (fine for the hackathon, not for a product). MEASURED. Verifier: the card text says CC BY-NC 4.0, the HF metadata tag says CC BY-SA 4.0 and the card is 454 MB. The recommendation stands (see Verification).
2. **The only honest public held-out test is AECV-Bench.** It downloads today (48.6 MB): 120 plans with hand counts of doors, windows, spaces, bedrooms and toilets, plus QA on 21 drawings. It has no licence file, and the paper says the plans come from CubiCasa5K, CVC-FP and online drawings (CONFIRMED by search summary of the paper). Run a hash check against our CubiCasa images before you trust it.
3. **Fallback for the detector:** the BRIDGE symbol set (6,286 images with box labels, door and window among 20 or so classes) plus ResPlan plans (17,000 vector plans) that we render in new styles ourselves. Both download today.
4. **No public set has area or length questions.** Build that held-out suite from ResPlan or MSD geometry in a style we do not train on. Nothing else exists.
5. **Not usable tonight:** ArchCAD (gate, 401), WAFFLE (SharePoint, 403), CVC-FP (host times out), DrawingVQA (questions only, no images), LED-BENCH, MMArch (data "soon"), TakeoffBench (email request), ZInD, Structured3D, RPLAN, LIFULL (request or form).

## Candidates

HTTP result = what I got on 2026-11-14. "Today" = a download works with no manual request.

### Group A: drawings with symbol or room labels (training and style tests)

| Dataset | Labels | Size | Licence | Today? (HTTP) | Disk | Use rank (a) detector / room model |
|---|---|---|---|---|---|---|
| **FloorPlanCAD, Voxel51 mirror** `Voxel51/FloorPlanCAD` | Box and mask per instance, 30 classes: 3 door types, window, bay and blind window, opening symbol, stairs, escalator, elevator, toilet, urinal, sink, bath, tub, stove, fridge, furniture, wall, parking. Images are 1000x1000 RGBA tiles | 5,308 tiles, 48,465 instances (MEASURED from `samples.json`). One class has few labels: single_door 629 against double_door 7,808, which looks swapped (see risks) | Card: CC BY-NC 4.0. HF tag: CC BY-SA 4.0. Treat as NC. Drawings: "we do not own the copyright" | **Yes.** PNG 200, `samples.json` 200 (60.4 MB), no gate | CORRECTED by verifier: the dataset card header says 454 MB total (the earlier 0.5 to 0.8 GB figure did not match the card) | **1** |
| **FloorPlanCAD, original** (Google Drive) | Line-level SVG labels, 35 classes, 15,663 drawings | 15,663 drawings | CC BY-NC 4.0 | **Yes.** 3 files, each answers HTTP 206 on a range request: 1.456 GB, 2.127 GB, 1.843 GB (train 1, train 2, test) | 5.43 GB as xz archives | 5 (SVG, for vector work only. Contents not unpacked) |
| **BRIDGE** (`gesstalt/BRIDGE`) | Pascal VOC boxes. Classes seen in a 25-file sample: door, window, stairs, sinks, tub, bed, sofas, tables, kitchen bar. Names are not clean ("window" and "windows") | Symbol set 6,286 images: ROBIN 510, SESYD 1,000, d1 1,639, d2 3,137 (UNVERIFIED by verifier: the repo README gives no counts). Also room classification 2,452 files, captions 1,744 images | None stated (GitHub API: none) | **Yes.** Repo page 200; raw file 200. I did not pull the whole repo | Repo 635 MB; symbol set about 1.03 GB | **2** |
| **ROBIN / ROBIN++** (`gesstalt/ROBIN`) | 510 clean synthetic plans (3, 4, 5 rooms), JPG only in the zip. Boxes are in BRIDGE `ROBIN_symbol` | 510 plans, plus a hand-sketch copy | GPL-3.0 | **Yes.** 200, ROBIN.zip 15.8 MB | 16 MB, ROBIN++ 17 MB | 6 (small, clean, easy) |
| **SESYD floorplans** | Synthetic plans with symbol ground truth | 1,000 plans (copy inside BRIDGE) | Not stated | Page 200. Use the BRIDGE copy | 459 MB in BRIDGE | 7 (synthetic, known to break learned spotters) |
| **ResPlan** (`m-agour/ResPlan`) | Vector geometry in metres: walls, doors, windows, rooms, balconies, 17 classes; room graph | 17,000 plans, median 110 m2 | Data CC BY 4.0, code MIT (README) | **Yes.** `ResPlan.zip` 200, 100,106,537 bytes (zip size UNVERIFIED by verifier; the README gives none). The Kaggle API URL gives 404 (login needed) | 100 MB | **3** (we render it in our own styles; exact labels) |
| **ResPlan-FP** (`Tristan12138/resplan-fp`) | 16,998 clean renders, 256 px, wall-first JSON labels. No text, no fixtures | 14,998 / 1,000 / 1,000 | CC BY 4.0 | **Yes.** HF, no gate | 0.26 GB | 8 (too small and too clean) |
| **MSD, HF mirror** (`philippds/modified-swiss-dwellings-enriched`) | Structure images, geometry, access graph, simulations | Train 4,572, test 800 (UNVERIFIED: not readable on the card page) | CC BY 4.0 (CONFIRMED) | **Yes.** No gate | 1.27 GB (UNVERIFIED) | 4 (second geometry source; same origin as Swiss Dwellings) |
| **MSD, JSON** (Zenodo 17294451) | Room geometries and dual graphs as JSON | 4,572 plans | CC BY 4.0 | **Yes.** Zenodo API 200 | 319.9 MB | 4 (safe JSON format) |
| **MSD, 4TU original** | `struct_in`, `full_out`, graphs as pickle and npy | Train 4,167 plans; the test zip has no answers | CC BY 4.0 | Page 200. Sizes (train 4.76 GB, test 0.79 GB) are from a search summary: UNVERIFIED | 5.5 GB | skip (use the mirrors) |
| **CubiCasa5K skv4 labels** (`Tristan12138/cubicasa5k-skv4`) | Corrected wall, room and opening labels on 256 px images | 3,328 / 318 / 296 | CC BY-NC-SA 4.0 | **Yes.** No gate | 0.13 GB | 9 (only if we keep training on CubiCasa) |
| **ArchCAD-400K** (`jackluoluo/ArchCAD`) | Panoptic labels, 27 classes, auto-QA per sample, 5 modalities | 40k samples released (paper: 413,062 chunks from 5,538 drawings) | CC BY-NC 4.0, manual approval | **No.** File URL gives 401. "Up to 3 days" | 2.63 GB | not tonight |
| **WAFFLE** (`TAU-VAILab/WAFFLE`) | Wikimedia plans, many styles and eras. OCR, legends, small segmentation set | Not stated in the README | "Wikimedia Commons licence" | **No** from curl. SharePoint link gives 403. A browser may work: UNVERIFIED | UNVERIFIED | not tonight |
| **CVC-FP** (CVC, UAB) | 122 scanned plans, 6 classes (rooms, walls, doors, windows, parking doors, separations) | 122 | Free for research (per search) | **No.** `dag.cvc.uab.es`, old and new URL, timed out (HTTP 000) | UNVERIFIED | not tonight. AECV-Bench holds some CVC-FP plans |
| **RPLAN** | Room masks, about 80k | about 80k (UNVERIFIED) | Request, research only | **No.** Page opens, no direct link | n/a | skip |
| **LIFULL HOME'S** (NII) | Japanese rental plans as 120x120 JPG; high-resolution plans (5.31 million) need a second application | 83 million small files | NII agreement | **No.** Page 200, application needed | 210 GB small; 140 GB high-resolution | skip |
| **R2V** (`art-programmer/FloorplanTransformation`) | Vector labels only | n/a | MIT code | **No.** README: "We don't have the permission to share the rasterized images" | n/a | skip |
| **ZInD** (Zillow) | 360 panoramas, 2,737 floor plans (README table) | 1,575 homes | ZInD Terms of Use | **No.** Bridge registration, then approval; "two weeks" | about 40 GB | skip |
| **Structured3D** | 3D structure of synthetic houses. The page does not mention floor plans | 3.5K designs (earlier note) | Terms of Use | **No.** Agreement form | n/a | skip |
| **HouseExpo** (`TeaganLi/HouseExpo`) | Room polygons with room category from SUNCG. No doors or windows | 35,126 layouts | MIT | Repo 200. I did not test `json.tar.gz` | n/a | skip (no symbols) |
| **Floor Plan CIS** (Zenodo 17871079) | Wall segmentation, regional styles | 500 plans (search summary) | CC BY 4.0 | **Yes.** Zenodo API 200 | 23.2 MB | skip (walls only) |
| **PID2Graph** (Zenodo 14803338) | P&ID symbols as nodes with boxes (OPEN100 has 12 real plans; the rest is synthetic) | 9.3 GB | CC BY-SA 4.0 | **Yes.** Range request 206 | 9.3 GB | only if the hidden set has P&IDs |
| **PID_dataset** (Zenodo 8028570) | Industrial and web P&IDs | 6.7 GB | CC BY 4.0 | **Yes.** Range request 206 | 6.7 GB | same |
| P&ID Symbols (Roboflow Universe, PID Connect) | 1,065 images, 181 classes, 61.8% mAP50 | 1,065 | CC BY 4.0 | UNVERIFIED (page not opened; export needs an API key) | n/a | same |
| Door and window schedule datasets | None found. One vendor blog tests 20 schedule tables and does not release them | n/a | n/a | n/a | n/a | none |
| DoorDet (arXiv 2508.07714) | Door types on real plans | n/a | n/a | UNVERIFIED: the paper lists no data link | n/a | none |

### Group B: question-answer sets (held-out tests)

| Set | What it asks | Size | Licence | Today? (HTTP) | Disk | Use rank (b) held-out QA |
|---|---|---|---|---|---|---|
| **AECV-Bench** (`AECFoundry/AECV-Bench`, Jan 2026) | Counts of door, window, space, bedroom, toilet on 120 plans (hand labels). QA on 21 drawings: read area text, adjacency, access, largest room (French and English text seen) | 120 plans; 21 drawings with QA (the repo has 21 images and 21 label files; the paper reports 192 QA pairs). Label totals MEASURED: doors 1,116, windows 1,135, spaces 1,239, bedrooms 252, toilets 186 | No licence file | **Yes.** Zip 200, 48.6 MB | 50 MB | **1** |
| **AEC-Bench** (`Nomic-ai/aec-bench`, `nomic-ai/aec-bench`, Mar 2026) | Review of real US construction sets: detail technical review, cross-reference resolution and tracing, sheet index, drawing navigation, spec sync, submittals. No counts, no areas | 196 tasks, 9 task types. 271 unique asset URLs (270 PDF) | Apache-2.0 | **Yes.** 269 of 271 URLs answer 200, 1 gives 404, 1 times out (MEASURED) | 5.78 GB for the 269 | **2** (robustness, crash gate, text lookup) |
| **FloorplanQA** (`OldDelorean/FloorplanQA`, v4 May 2026) | Geometric questions, answers computed by code, 2% tolerance (5% for area tasks) | 2,000 JSON layouts, 600 each of kitchen, living room and so on, 200 from HSSD. Mostly single rooms with furniture | Code MIT. Layouts CC BY 4.0 (HF). Paper CC BY-NC-SA | **Yes.** HF no gate | 10 MB layouts | 3 (arithmetic only; no drawing style) |
| **ArchSIBench** (`ArchSIBench/ArchSIBench`, May 2026) | Spatial intelligence multiple choice: perception, reasoning, navigation, transformation, configuration | 3,000 QA, 4,950 image rows (CONFIRMED by verifier) | Apache-2.0 | **Yes.** No gate | CORRECTED: 2.27 GB (card), not 4.5 GB | 4 (wrong question type) |
| **MechVQA** (`XiaofengAlg/MechVQA`, ICML 2026) | Mechanical part and assembly drawings | Public eval subset 1,185 items (search summary of the GitHub README); 20,778 QA overall | Apache-2.0 (HF) | **Yes.** No gate | 1.67 GB | 5 (dimension reading only; not buildings) |
| DrawingVQA (`S2-MIND/DrawingVQA`, CVPR Findings 2026) | 92 expert QA on 33 construction drawings | 92 rows (MEASURED; verifier saw 92 rows, CONFIRMED). The 33 drawings count and the licence are UNVERIFIED | CC BY-NC-SA 4.0 (UNVERIFIED) | **Questions only.** Parquet has image hashes, not images. Images "not fully open" | 40 KB | **not usable** |
| LED-BENCH (arXiv 2610.19571, Oct 2026) | 107 large-format drawings, 377 questions, 3 domains | 377 | n/a | **No.** Page says "Dataset Soon". The GitHub README holds only the title | n/a | not usable |
| MMArch (arXiv 2608.09281) | 1,212 items from figures in papers, not drawings | 1,212 | n/a | **No.** "Data Coming Soon" | n/a | not usable |
| TakeoffBench (Handoff, arXiv 2608.15032) | 10 residential blueprint cases, takeoff lists | 10 cases, about 100 pages | n/a | **No.** By email (`research@handoff.ai`). The repo has no data | n/a | not usable tonight |
| ArchCAD QA | Auto-made QA per drawing | 40k samples | CC BY-NC 4.0 | **No.** Same gate as ArchCAD (401) | 2.63 GB | not usable tonight |
| ARCH-B (arXiv 2609.34047) | 354 multiple-choice items on matching one building across views | 354 | n/a | UNVERIFIED: no data link in the paper HTML | n/a | not usable |
| CaseVBench (coxit.co) | Vendor benchmark | n/a | n/a | UNVERIFIED: the page shows no download | n/a | not usable |
| Blueprint-Bench-lmms (HF) | No description in the card I read | 1 parquet, 0.5 MB | None | UNVERIFIED use | n/a | skip |

## Recommendation and recipe

### What to train on (use a)

1. **Pull FloorPlanCAD tiles** from the Voxel51 mirror. The repo has `samples.json`. Each detection has a `label` and a FiftyOne `bounding_box` of `[x, y, w, h]`, relative to the image, top-left origin (seen in the sample record).

   ```sh
   # Untested as a command. The resolve URLs it uses answered 200 today.
   uvx --from huggingface_hub hf download Voxel51/FloorPlanCAD --repo-type dataset --local-dir data/fpc
   ```

2. **Merge classes before you train.** Use `door` (single, double, sliding), `window` (window, bay, blind), `stairs`, `toilet`, `sink`, `bath`. Do not trust the single versus double split until the check in "Risks" passes. Drop `class_31`, `class_32`, `class_34`, `class_35` (unnamed in the mirror).
3. **Split by drawing, not by tile.** Tile ids look like `0734-0105`. Tiles of one drawing share the first number (ESTIMATE from the file names). Hold out 20% of drawings.
4. **Mix with CubiCasa and render ResPlan in 3 or more styles** (line weight, symbol set, with and without text). Rendering code is ours to write. Load `ResPlan.pkl` only in an isolated environment: pickle runs code on load. Prefer the Zenodo MSD JSON (safe format) for a second geometry source.
5. **Cost.** The RT-DETR-L floor-plan detector took about 2.3 h on 2 A100 for 4,200 CubiCasa images and 60 epochs (SOURCED, S13 in `floorplan-cv.md`). That is about 55k image-iterations per A100-hour. FloorPlanCAD 5,308 tiles x 30 epochs is about 160k iterations, about 3 A100-hours, about 7 USD at 2.37 USD per hour (ESTIMATE). A mixed run with CubiCasa is about 5 A100-hours, about 12 USD (ESTIMATE).
6. **Test the result on styles it never saw:** the Swiss PNGs (planned), BRIDGE d2, and the AECV-Bench plans that pass the hash check. Score exact counts, not mAP.

### What to test on (use b)

| Step | Data | What it shows | Command |
|---|---|---|---|
| 1 | **AECV-Bench counting, 120 plans** | Exact door and window counts on styles we did not train on. Best frontier model (Gemini 3 Pro) scores 39% (doors) and 34% (windows) exact match there (CONFIRMED by verifier against the AEC Foundry blog and Emergent Mind table; the arXiv abstract says "often 0.40-0.55", a looser statement) | `curl -L -o aecv.zip https://codeload.github.com/AECFoundry/AECV-Bench/zip/refs/heads/main` (48.6 MB, 200). Ground truth is `data/Use Case 1 - Object Counting/1 - Full Datasets/<id>/metadata.json` (UTF-8 BOM: read with `utf-8-sig`) |
| 2 | **AECV-Bench QA, 21 drawings** | Text lookup, adjacency, largest room. Few drawings: errors cluster by drawing | same zip, `data/Use Case 2 - Drawing Understanding/01 - Full Dataset/{images,labels}` |
| 3 | **AEC-Bench, 270 real PDFs** | Crash gate, ingest time, text lookup on US sets. Not counts or areas | Download each manifest `key` to its `dest` (see below) |
| 4 | **Own area and length suite from ResPlan or MSD** | Areas within 2%, lengths, scale handling. No public set has this | Write it. Use a render style we never trained on |
| 5 | **FloorPlanCAD held-out drawings** | Counts per tile from labels (exact, for a new style). Per tile, not per plan | The 20% hold-out from step 3 above |

AEC-Bench download (the manifests are in the repo, so fetch the repo zip first):

```sh
curl -L -o aecbench.zip https://codeload.github.com/Nomic-ai/aec-bench/zip/refs/heads/main
# each tasks/*/*/*/environment/manifest.jsonl line: {"key": "<https url>", "dest": "<file name>"}
# download key -> environment/<dest>. 269 of 271 URLs answered 200 today.
```

Other commands (all targets answered 200 or 206 today):

```sh
# ResPlan, 100,106,537 bytes. Geometry pickle: load in a sandbox.
curl -L -o ResPlan.zip https://github.com/m-agour/ResPlan/raw/main/ResPlan.zip
# MSD as JSON, 319.9 MB
curl -L -o msd_01_json.zip https://zenodo.org/api/records/17294451/files/msd_01_json.zip/content
# BRIDGE (not pulled whole; one raw file tested, 200)
curl -L -o bridge.zip https://codeload.github.com/gesstalt/BRIDGE/zip/refs/heads/main
# FloorPlanCAD original, only if SVG is needed (xz archives, 5.4 GB)
curl -L -o fpc_train1.xz "https://drive.usercontent.google.com/download?id=1HcyKt6qWeXog-tRfvEjdO3O3TN91PXGL&export=download&confirm=t"
# PID2Graph, only for P&ID work (9.3 GB)
curl -L -o PID2Graph.zip https://zenodo.org/api/records/14803338/files/PID2Graph.zip/content
```

## Risks and how to test them in 1 hour

| Risk | Test (time) | What we do on a bad result |
|---|---|---|
| FloorPlanCAD door classes look swapped in the mirror (single_door 629, double_door 7,808) | Draw 20 tiles with their boxes and class names (10 min) | Merge all door classes into `door`. Do not report door type |
| AECV-Bench counting plans overlap Stoa's CubiCasa images. Its paper says the 120 plans come from CubiCasa5K, CVC-FP and online drawings (search summary: UNVERIFIED in the paper text) | Perceptual hash of the 120 plans against our 4,787 CubiCasa images (15 min). The folder prefixes (0000, 2000 to 6000) may mark the sources: ESTIMATE | Drop matches. Report the rest as "clean n=" |
| Small sample: 120 plans from 6 groups, 21 drawings for QA. The error bar is wide | Cluster the bootstrap by drawing and by group (10 min) | Report the interval. Do not tune on this set |
| FloorPlanCAD tiles are 20 m x 20 m crops, not whole plans. A per-tile count is not a plan count | Check the card: "Cropped into 20m x 20m blocks, 50% retention" (read) | Use it for the detector and for per-tile counts only |
| Box labels join neighbouring doors or split one, so label counts differ from visual counts | Compare label counts with a hand count on 20 tiles (15 min) | Train with the labels but test counts on a hand-checked set |
| AECV label rule: windows include French doors and large glazed openings (search summary). Stoa may differ | Read 10 plans against Stoa's cubicasa rule (10 min) | State the rule next to the score |
| Licences: FloorPlanCAD, CubiCasa, ArchCAD are NC. AECV-Bench, BRIDGE have no licence. ROBIN is GPL-3.0 | Read this table | Fine for the weekend. Do not ship weights trained on NC data in a product. Flag it to the lead |
| The SESYD and ROBIN style is clean synthetic. A detector can score high there and still fail on real scans | Zero-shot the existing RT-DETR on 200 FloorPlanCAD tiles and 100 BRIDGE d2 images and score exact counts (20 min) | If it drops, the FloorPlanCAD fine-tune is worth the 5 GPU-hours. If it holds, skip the fine-tune |
| Search summaries I did not confirm in the primary source: MSD 4TU sizes, ArchSIBench size, MechVQA public subset, Floor Plan CIS size, CVC-FP licence | Open the page before you rely on the number | Treat as UNVERIFIED until then |

## Sources

All pages opened or probed on 2026-11-14 unless a date is given for the paper.

| Id | Title | URL | Date | Supports |
|---|---|---|---|---|
| D1 | Voxel51/FloorPlanCAD dataset card and files | https://huggingface.co/datasets/Voxel51/FloorPlanCAD | 2025-11-04 (repo), read 2026-11-14 | 5,308 samples, 30 classes, 20 m tile crops, not gated; `samples.json` counts (MEASURED) |
| D2 | FloorPlanCAD project page | https://floorplancad.github.io/ | read 2026-11-14 | 15,663 drawings, CC BY-NC, 3 Google Drive links (1.46, 2.13, 1.84 GB, range test 206) |
| D3 | BRIDGE repository | https://github.com/gesstalt/BRIDGE | pushed 2022-03-25, read 2026-11-14 | Symbol-spotting boxes, 6,286 images, 635 MB, no licence |
| D4 | ROBIN repository | https://github.com/gesstalt/ROBIN | pushed 2022-03-25, read 2026-11-14 | 510 plans, GPL-3.0, zip 15.8 MB |
| D5 | SESYD | http://mathieu.delalandre.free.fr/projects/sesyd/ | read 2026-11-14 | Synthetic floor plans with symbol ground truth |
| D6 | ResPlan repository | https://github.com/m-agour/ResPlan | pushed 2026-07-28, read 2026-11-14 | 17,000 plans, CC BY 4.0 data, `ResPlan.zip` 100 MB |
| D7 | ResPlan-FP | https://huggingface.co/datasets/Tristan12138/resplan-fp | 2026-10-21 | 16,998 renders, 256 px, CC BY 4.0 |
| D8 | MSD on Hugging Face | https://huggingface.co/datasets/philippds/modified-swiss-dwellings-enriched | 2026-07-14 | 4,572 train, 800 test, CC BY 4.0, 1.27 GB |
| D9 | MSD JSON on Zenodo | https://zenodo.org/records/17294451 | 2025-10-08 | 319.9 MB, CC BY 4.0 |
| D10 | MSD on 4TU | https://data.4tu.nl/datasets/e1d89cb5-6872-48fc-be63-aadd687ee6f9 | read 2026-11-14 (page 200) | Original release; sizes UNVERIFIED |
| D11 | Swiss Dwellings v3 on Zenodo | https://zenodo.org/records/7788422 | 2022-09-20 | 931.9 MB, range test 206 (already held) |
| D12 | CubiCasa5K skv4 | https://huggingface.co/datasets/Tristan12138/cubicasa5k-skv4 | 2026-10-21 | Corrected labels, NC-SA |
| D13 | ArchCAD dataset card | https://huggingface.co/datasets/jackluoluo/ArchCAD | 2025-10-14, read 2026-11-14 | Manual gate, file URL 401, CC BY-NC 4.0, 2.63 GB |
| D14 | WAFFLE repository | https://github.com/TAU-VAILab/WAFFLE | pushed 2025-04-05, read 2026-11-14 | SharePoint link gives 403; Wikimedia licence |
| D15 | CVC-FP page | https://dag.cvc.uab.es/dataset/cvc-fp-database-for-structural-floor-plan-analysis/ | probed 2026-11-14 | Host timed out (HTTP 000); content from a search summary |
| D16 | ZInD repository | https://github.com/zillow/zind | pushed 2022-12-13, read 2026-11-14 | Registration, terms, 40 GB |
| D17 | Structured3D | https://structured3d-dataset.org/ | read 2026-11-14 | Agreement form |
| D18 | LIFULL HOME'S Dataset | https://www.nii.ac.jp/dsc/idr/en/lifull/ | update 2025-05-27, read 2026-11-14 | Application needed; 140 GB high-resolution |
| D19 | RPLAN page | http://staff.ustc.edu.cn/~fuxm/projects/DeepLayout/index.html | read 2026-11-14 | Page opens, no direct link |
| D20 | PID2Graph on Zenodo | https://zenodo.org/records/14803338 | 2025-02-14 | 9.3 GB, CC BY-SA 4.0, range test 206 |
| D21 | PID_dataset on Zenodo | https://zenodo.org/records/8028570 | 2023-06-12 | 6.7 GB, CC BY 4.0, range test 206 |
| D22 | Floor Plan CIS on Zenodo | https://zenodo.org/records/17871079 | 2025-12-09 | 23.2 MB, CC BY 4.0 |
| Q1 | AECV-Bench repository | https://github.com/AECFoundry/AECV-Bench | pushed 2026-08-04, zip read 2026-11-14 | 120 counting plans, 21 QA drawings, label format and totals (MEASURED), no licence file |
| Q2 | AECV-Bench paper | https://arxiv.org/abs/2601.04819 | 2026-01-08 | 192 QA, sources, best model scores |
| Q3 | AEC-Bench repository | https://github.com/Nomic-ai/aec-bench | pushed 2026-09-03, read 2026-11-14 | 196 tasks, 9 types, Apache-2.0, manifest format |
| Q4 | AEC-Bench asset host | https://nomic-public-data.com/data/aec-bench-v1/ | probed 2026-11-14 | 269 of 271 URLs answer 200, 5.78 GB |
| Q5 | AEC-Bench paper | https://arxiv.org/abs/2603.29199 | 2026-03-31 | Task design |
| Q6 | FloorplanQA repository and layouts | https://github.com/OldDelorean/FloorplanQA , https://huggingface.co/datasets/OldDelorean/FloorplanQA-Layouts | 2026-05-25, 2025-12-02 | MIT code, 2,000 layouts, CC BY 4.0 |
| Q7 | ArchSIBench | https://huggingface.co/datasets/ArchSIBench/ArchSIBench | 2026-05-02 | Apache-2.0, 4.5 GB |
| Q8 | MechVQA | https://huggingface.co/datasets/XiaofengAlg/MechVQA , https://github.com/xiaofengShi/MechVQA | 2026-08-03 | Apache-2.0; public subset count from a search summary |
| Q9 | DrawingVQA | https://huggingface.co/datasets/S2-MIND/DrawingVQA , https://joonv2.github.io/DrawingVQA/ | 2026-02-23, read 2026-11-14 | 92 QA, 33 drawings, no images (parquet read) |
| Q10 | LED-BENCH | https://iaie-physicalai.github.io/LED-BENCH/ , https://github.com/IAIE-PhysicalAI/LED-BENCH | pushed 2026-10-17, read 2026-11-14 | "Dataset Soon", README is a title only |
| Q11 | MMArch | https://dcx-swjtu.github.io/MMArch/ | read 2026-11-14 | "Data Coming Soon" |
| Q12 | Residential takeoff benchmark (Handoff) | https://github.com/handoffai/residential-takeoff-benchmark | pushed 2026-07-21, read 2026-11-14 | Cases only on request by email |
| Q13 | ARCH-B | https://arxiv.org/abs/2609.34047 | 2026 | 354 items; no data link found |
| S1 | Earlier notes in this repository | `stoa/docs/research/sota/floorplan-cv.md`, `synthetic-data.md`, `STATE-OF-THE-ART.md` | 2026-11-13 and 2026-11-14 | RT-DETR training cost (S13 there), frontier counting scores, licence conflicts |

## Verification

Checked on 2026-11-14 by an independent verifier against the primary pages. Recommendation: it stands. FloorPlanCAD (Voxel51 mirror) exists under that id, is not gated and has the quoted tile and class counts. AECV-Bench is real and has the quoted scores. The corrections change disk sizes only.

| Claim | Verdict | Evidence URL |
|---|---|---|
| `Voxel51/FloorPlanCAD` exists, not gated, 5,308 samples, 30 classes, 20 m x 20 m crops | CONFIRMED | https://huggingface.co/datasets/Voxel51/FloorPlanCAD |
| FloorPlanCAD mirror licence: NC card text, SA tag | CONFIRMED (card says CC BY-NC 4.0, tag says CC BY-SA 4.0) | https://huggingface.co/api/datasets/Voxel51/FloorPlanCAD |
| FloorPlanCAD mirror disk size 0.5 to 0.8 GB | CORRECTED to 454 MB (card) | https://huggingface.co/datasets/Voxel51/FloorPlanCAD |
| FloorPlanCAD 48,465 instances; single_door 629 vs double_door 7,808 | UNVERIFIED (own measurement, not repeated) | https://huggingface.co/datasets/Voxel51/FloorPlanCAD |
| FloorPlanCAD original: 15,663 drawings | CONFIRMED | https://huggingface.co/datasets/Voxel51/FloorPlanCAD |
| AECV-Bench: 120 counting plans, 192 QA pairs | CONFIRMED | https://arxiv.org/abs/2601.04819 |
| AECV-Bench: no licence file | CONFIRMED | https://github.com/AECFoundry/AECV-Bench |
| AECV-Bench plans come from CubiCasa5K, CVC-FP and online (hash check needed) | CONFIRMED (search summary of the paper; the PDF text was not readable here) | https://arxiv.org/pdf/2601.04819 |
| Best model 39% doors, 34% windows | CONFIRMED (Gemini 3 Pro, exact match; abstract says "often 0.40-0.55") | https://www.aecfoundry.com/blog/can-ai-really-read-your-building-plans-aecv-bench-gets-a-major-upgrade |
| AEC-Bench: 196 tasks, 9 types, Apache-2.0 | CONFIRMED | https://github.com/Nomic-ai/aec-bench |
| ResPlan: 17,000 plans, data CC BY 4.0, code MIT | CONFIRMED | https://github.com/m-agour/ResPlan |
| ResPlan.zip 100,106,537 bytes | UNVERIFIED | https://github.com/m-agour/ResPlan |
| ResPlan-FP: 16,998 renders, 14,998/1,000/1,000, 256 px, CC BY 4.0 | CONFIRMED | https://huggingface.co/datasets/Tristan12138/resplan-fp |
| MSD JSON on Zenodo 17294451: 319.9 MB, CC BY 4.0 | CONFIRMED | https://zenodo.org/records/17294451 |
| MSD HF mirror: CC BY 4.0 | CONFIRMED | https://huggingface.co/datasets/philippds/modified-swiss-dwellings-enriched |
| MSD HF mirror: 4,572/800 split, 1.27 GB | UNVERIFIED | https://huggingface.co/datasets/philippds/modified-swiss-dwellings-enriched |
| BRIDGE: no licence | CONFIRMED | https://github.com/gesstalt/BRIDGE |
| BRIDGE: 6,286 symbol images, 635 MB | UNVERIFIED (README has no counts) | https://github.com/gesstalt/BRIDGE |
| PID2Graph: 9.3 GB, CC BY-SA 4.0 | CONFIRMED | https://zenodo.org/records/14803338 |
| ArchSIBench: Apache-2.0, about 3,000 QA | CONFIRMED | https://huggingface.co/datasets/ArchSIBench/ArchSIBench |
| ArchSIBench: 4.5 GB | CORRECTED to 2.27 GB | https://huggingface.co/datasets/ArchSIBench/ArchSIBench |
| DrawingVQA: 92 QA rows, no images in the table | CONFIRMED | https://huggingface.co/datasets/S2-MIND/DrawingVQA |
| DrawingVQA: 33 drawings, CC BY-NC-SA 4.0 | UNVERIFIED | https://huggingface.co/datasets/S2-MIND/DrawingVQA |
