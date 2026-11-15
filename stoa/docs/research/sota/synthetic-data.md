# Synthetic data for floor plans and construction drawings

Track: synthetic data for training and for evaluation. Written 2026-11-13 for the Stoa "Make Blueprints Talk" challenge.

Labels used in this file:

- **[SRC Sx]**: read in source Sx (see the Sources table). I opened the page and read the quote myself.
- **[MEAS]**: measured by me on this machine (Apple M4 Max) on 2026-11-13. The scripts are in the scratchpad, not in the repo.
- **[EST]**: my estimate. Not a measurement.
- **[UNVERIFIED]**: seen only in a search snippet. I could not open the page (HTTP 403 or the fetch quota ran out).

## Findings that change decisions

1. **Synthetic data helps as pre-training or as a supplement. It is weak as the only training data on real images.** On ChartQA, VL-T5 trained only on template-based PlotQA gets 20.96%. Trained on ChartQA it gets 41.56%. PlotQA pre-training followed by ChartQA fine-tuning gets 51.84% [SRC S3]. SynthPID (arXiv preprint; the "CVPR 2026 workshop" venue is not stated in the preprint) shows the same shape on real P&IDs: synthetic only gives 63.8 edge mAP, real only 69.4, mixed 72.6 [SRC S2]. Decision: do not plan a model that sees only synthetic drawings. Use synthetic data for pre-training, for the parts with no real labels (habs, finna, europeana, wikimedia styles) and above all for tests. Moves accuracy.
2. **Generator realism of structure matters more than volume.** SynthPID seeds topology from real drawings and gets about 64% edge mAP. Older random-placement templates got about 33% [SRC S2]. Gains flatten after about 400 images [SRC S2]. The ECD chart paper also says synthetic charts failed because of "inadequate similarity to the real charts" [SRC S5]. Decision: seed our generator with real layouts (Swiss Dwellings geometry, ResPlan, IFC models) and randomise the style around them. Do not invent random boxes and expect transfer. Moves accuracy.
3. **Counting does not extrapolate past the counts seen in training.** A model fine-tuned on synthetic counts 1 to 9 scores 93-100% in distribution. On real OCID images with 11 to 20 objects (the real OOD split) it drops to 16-34% with the best method (counting predicted points), and 2-19% with a stated direct count [SRC S6]. (Corrected by fact check: the report said 97-100%, 10 to 18 and 19-34%. The 10 to 18 range is the synthetic OOD split.) Counting predicted points beats a stated count (InternVL3.5-8B: 97.94% vs 45.52% on synthetic OOD) [SRC S6]. Decision: any learned counter must output points or boxes, the count must be len(points), and the synthetic set must cover counts well above the public maximum. The hidden set can have larger buildings. Moves accuracy and verifiability.
4. **The Swiss Dwellings source geometry is public and CC BY 4.0.** Zenodo record 7788422 holds WKT polygons in metres for about 45,176 apartments, with areas, walls, doors, windows and features [SRC S17]. MSD (over 5.3K plans) derives from it [SRC S18]. Two consequences: (a) it is the best seed for a realistic generator, with exact labels; (b) a lookup of public answers from this file is leakage. It will not transfer to hidden drawings, and judges will ask. Use it as a seed and as a check of our area extractor, never as an answer source at inference.
5. **The default Augraphy pipeline breaks geometric ground truth.** [MEAS] The default pipeline folded and warped a rendered plan: straight walls became bent, so area and length labels no longer hold. Use only ink, paper and noise stages for area questions, or record the warp and transform the labels. Counts survive warping, areas do not. Moves accuracy of the eval set itself.
6. **A full DXF to PDF to PNG generator with exact labels is cheap to build.** [MEAS] A 90-line prototype with ezdxf 1.4.2 and the PyMuPDF backend wrote DXF, PDF, PNG and a JSON scene graph with questions at 0.072 s per drawing. Augraphy 8.2.6 added 1.2 s per 2000x1700 image (mean, max 4.1 s). Augraphy 8.2.6 crashed on Python 3.14 with numpy 2 (TypeError); it ran on Python 3.11 with numpy<2. So 10,000 degraded drawings take about 3.5 CPU hours on one core [EST from MEAS], minutes on all cores.
7. **Template question generators create shortcuts, and our public set has them.** CLEVR used rejection sampling per question family to reduce answer bias [SRC S8], yet a blind mode guess per template already scores 55.3% on cubicasa5k (lead's measurement). Super-CLEVR found that "disentangling reasoning and perception, combined with probabilistic uncertainty" makes VQA robust to domain shift [SRC S9]. Decision: the synthetic test suite must balance answers per template, report a blind baseline, and phrase questions in ways the public set does not use. Moves accuracy on the hidden set and supports the abstain design.
8. **Metamorphic tests are the cheapest way to find failures without labels, and they work on real hidden-like drawings too.** Rotation, flip and re-render must not change a count. Scaling a drawing by s must scale an area by s squared, or the system must ask for the scale. These checks run on the 6,570 unlabelled historic scans, where we have no answers. MetaVQA used this idea to find over 4.9 million perception failures in VQA models [SRC S10, page opened in the fact check]. Moves verifiability and the "I do not know" behaviour.
9. **Learned floor plan generators are a poor fit this weekend.** HouseDiffusion (research-only terms with GPL v3, only a "temporary" checkpoint) and House-GAN++ (GPL v3 text, marked "research purposes only") need RPLAN, which is hard to download [SRC S20, S21]. They output room polygons, not drawings with symbols, text, scale bars or hatches. ProcTHOR (Apache-2.0) and Infinigen Indoors (BSD) target 3D embodied scenes [SRC S22, S23]. Decision: write a procedural generator seeded from real vector plans. Saves 6 to 10 hours [EST].

## Landscape

### Floor plan layout sources and generators

| Name | What it gives | Size | Licence | Download today | Fit for us |
|---|---|---|---|---|---|---|
| Swiss Dwellings v3.0.0 | WKT polygons in metres: areas, walls, railings, columns, windows, doors, features | ~45,176 apartments, ~3,100 buildings [SRC S17] | CC BY 4.0 [SRC S17] | Yes, one 931.9 MB zip [SRC S17] | Best seed. Same family as `swiss_dwellings`: leakage risk if used as answer source. |
| MSD (Modified Swiss Dwellings) | ML-ready floor plans from Swiss Dwellings | "over 5.3K floor plans" (paper abstract; exact 5,372 not found on any page I opened); 4,167 in the train split, test split not public on the 4TU page [SRC S18] | CC BY 4.0 [SRC S18] | Yes | Same leakage note. |
| ResPlan | Vector walls, doors, windows, rooms, balconies in metres, 17 classes, room graph | 17,000 plans, median 110 m2 [SRC S19] | CC BY 4.0 data, MIT code [SRC S19] | Yes (GitHub zip, Kaggle) | Good second seed, different region ("South Asian residential markets") [SRC S19]. Adds style shift. |
| RPLAN | 80k raster apartments | ~80k | Request form; not open | Hard ("many requests regarding issues with downloading") [SRC S20] | Skip. |
| HouseDiffusion (CVPR 2023) | Graph-conditioned room polygons | trained on RPLAN | LICENSE: code and weights "not allowed for commercial usage"; for research, GPL v3 (file LICENSE_GPL) [SRC S20, fact check] | Temporary checkpoint on Google Drive [SRC S20] | Skip: no symbols, needs RPLAN. |
| House-GAN++ (CVPR 2021) | Graph-conditioned layouts | RPLAN | LICENSE file is GPL v3 text with a banner "THIS CODE CAN ONLY BE USED FOR RESEARCH PURPOSES" [SRC S21, fact check] | `python test.py` [SRC S21] | Skip. |
| Graph2Plan, ChatHouseDiffusion | Graph or text to layout | RPLAN | Graph2Plan: no licence seen; ChatHouseDiffusion: Apache-2.0 [SRC S30, confirmed by GitHub API in the fact check] | Code on GitHub | Skip. |
| Ospici et al. 2026 procedural generator | 135k synthetic layouts from RPLAN room shapes, packed with doors | 135k [SRC S1] | Paper CC BY-SA 4.0; no code release seen [SRC S1] | No | Method worth copying: give up realism, keep validity. |
| ProcTHOR | 3D houses for AI2-THOR | 10k sample houses [SRC S22] | Apache-2.0 [SRC S22] | `pip install procthor` | Low fit: no drawing conventions. |
| Infinigen Indoors (CVPR 2024) | Procedural photoreal indoor scenes, constraint solver | n/a | BSD [SRC S23] | Yes (infinigen.org) | Low fit, heavy Blender stack. |
| FloorplanQA (2025-2026) | 2,000 layouts, 16k questions, answers computed by geometry | 2,000 layouts [SRC S24] | Paper CC BY-NC-SA 4.0 | Project page | Template for an exact-answer QA generator. Default tolerance 2%, but 5% for area-computation tasks such as Free Space [SRC S24]. The 2,000 layouts are single-room furniture layouts (200 from HSSD real floors, the rest synthetic kitchens, living rooms and bedrooms), not building plans. The "same as Stoa" claim is not checked by me. |

### Real drawing datasets with exact labels (useful for style, symbols and as a sanity test)

| Name | Content | Licence | Notes |
|---|---|---|---|
| FloorPlanCAD | 15,663 CAD drawings, 30 classes, SVG with line-grained labels [SRC S27] | Card text says CC BY-NC 4.0; HF tag says CC BY-SA 4.0 [SRC S27] | Says SESYD (1,000 synthetic plans) and FPLAN-POLY (42) "were too small for deep learning" [SRC S27]. Chinese CAD style. |
| ArchCAD-400K | 413,062 chunks from 5,538 drawings; labels from CAD layer and block attributes [SRC S26] | CC BY-NC 4.0 [UNVERIFIED: no licence line found in the HF card jackluoluo/ArchCAD]; gated (manual approval) and 40k samples [confirmed on the HF listing] | Shows the "labels from CAD layers" trick works at scale. |

### Renderers that give exact labels

| Tool | Use | Licence | Evidence |
|---|---|---|---|
| ezdxf drawing add-on | DXF to SVG, PDF, PNG through `Frontend` + `PyMuPdfBackend` / `SVGBackend` | ezdxf: MIT [GitHub API, fact check]; PyMuPDF: AGPL [not checked] | API: `backend.get_pdf_bytes(page)`, `backend.get_pixmap_bytes(page, fmt="png", dpi=96)` [SRC S15]. [MEAS] 0.072 s per drawing. |
| IfcConvert (IfcOpenShell) | IFC to SVG floor plans | LGPL-3.0 (IfcOpenShell repo, GitHub API, fact check) | `IfcConvert input.ifc -yv output.svg -j 7 --exclude entities IfcOpeningElement IfcSpace`; flags `--section-height`, `--print-space-names`, `--print-space-areas`, `--door-arcs`, `--scale`, `--bounds`, `--auto-section` [SRC S16]. |
| Bonsai (Blender) drawings | Sheets with dimensions and annotations from IfcAnnotation cameras | GPL [EST] | Not opened in depth. Heavier than IfcConvert. |

### Symbol libraries

| Library | Licence | Notes |
|---|---|---|
| Innerscene Free Parts Library | "Everything is public domain (CC0)" [SRC S28] | "over 1,600 drawings", DXF, "drawn at 1:1 in millimetres with named layers" [SRC S28]. Door blocks confirmed; window and furniture 2D blocks not confirmed. The "October 2026" date is not on the page I opened. The page text lists "Doors and windows. Kitchens and baths. Furniture." as contents, so 2D window and sanitary blocks are likely, but I did not open the files. |
| GSStnb/dxfBlocks (GitHub) | Conflict: LICENSE file is CC0 1.0, README says CC BY-NC-SA 4.0 [confirmed in the fact check] | LibreCAD block set. Check before use. |
| FloorPlanCAD symbol instances | NC | Can be cropped out as symbol sprites with labels. NC is fine for the hackathon per the brief. |
| Our own `cubicasa5k`, `swiss_dwellings`, `opening_design` drawings | per source (CC BY-NC-SA, CC BY, CC BY-SA) | Crop real symbols to build per-country symbol sets. Keep credit. |

### Scan degradation

| Tool | Licence | State | Notes |
|---|---|---|---|
| Augraphy 8.2.6 | MIT [SRC S12] | Works on Python 3.11 + numpy<2; fails on Python 3.14 [MEAS] | Ink, Paper, Post stages; "printing, scanning, and faxing through old or dirty machines" [SRC S11]. Intended for training data and "challenging test data" [SRC S11]. Default pipeline includes geometric warps [MEAS]. |
| ocrodeg | No licence file in the repo root (GitHub API shows no licence); treat as unlicensed until checked [SRC S13] | Small numpy/scipy library | `random_transform`, `distort_with_noise`, `binary_blur`, `printlike_multiscale`, `printlike_fibrous` [SRC S13]. Good for controlled, parameterised degradations. |
| DocCreator | LGPL-3.0 [SRC S14] | C++/Qt source build, README dates from about 2019 [SRC S14] | Skip this weekend: install friction. |

### Evidence that synthetic or rendered data transfers

| Domain | Result | Source |
|---|---|---|
| Chart QA | PlotQA only: VL-T5 20.96%, VisionTaPas 31.96% on ChartQA. Real only: 41.56%, 45.52%. Pre-train + fine-tune: 51.84%, 47.08%. | [SRC S3] Table 6 |
| Chart QA | Template datasets give "an over-optimistic measure of progress"; a stress test with "slightly different charts or questions can deteriorate performance by up to 34.5%" | [SRC S4] |
| Chart QA | ECD (10k+ synthetic charts, 300k+ QA) "consistently improves the performance of various MLLMs on a range of real-world and synthetic test sets" | [SRC S5] |
| P&ID digitisation | Synth only 64.2 node mAP / 63.8 edge mAP; real (12 images, CV) 67.8 / 69.4; mixed 71.3 / 72.6. Caveat: seeds come from the same 12 test images. | [SRC S2] Table 3 |
| Floor plan generation | Cross-domain transfer degrades "up to an order of magnitude". Synthetic prior: OOD average MPE 36.98 vs 50.83 (RPLAN prior) and 58.18 (MagicPlan prior) for DPFM. Low-data fine-tune: 7.05 vs 12.1 MPE (41.7% less error). | [SRC S1] Tables 2-4 |
| Counting with VLMs | Synthetic fine-tune ID: DC 93.0-99.8%, PtC 99.8-100%. Real OCID ID: 69-82%. Real OCID OOD (11 to 20 objects): # Coord. 16.3-33.5%, PtC 1.0-25.9%, DC 2.2-18.8%. | [SRC S6] Tables 1-3 |
| RL on synthetic counting | R1-V: Qwen2VL-2B 48.0% to 82.5% on a SuperCLEVR subset after 100 GRPO steps; but answering directly without the think format already gives 86% | [SRC S7] |
| Drawing literacy of frontier VLMs | Door and window counting "often 0.40-0.55 accuracy"; OCR-style QA "up to 0.95" | [SRC S25] |
| Floor plan reasoning, image vs structure (single-room furniture layouts, not building plans) | Image only: 19-40%. JSON layout: 59-81%. "The structured JSON is the dominant signal" | [SRC S24] Table 3 |

## What we can use this weekend

### A. Generator: one drawing in DXF, PDF and PNG with a full scene graph and questions (about 6 hours)

Budget [EST]: 1 h seeds, 1.5 h renderer and styles, 1 h questions, 1 h degradation and shifts, 1.5 h metamorphic harness and report. A working skeleton exists [MEAS]: ezdxf + PyMuPDF backend + JSON scene graph, 0.072 s per drawing.

Stack:

```sh
uv run --no-project --python 3.11 \
  --with ezdxf==1.4.2 --with pymupdf --with pillow --with shapely \
  --with augraphy --with "numpy<2" --with opencv-python-headless \
  python -I gen.py out 1000
```

Steps:

1. **Seed layouts (1 h).** Load real room polygons: Swiss Dwellings `geometries.csv` (WKT in metres) [SRC S17] and ResPlan pickle [SRC S19]. Keep only floors whose `site/building/floor` id is not in the public `swiss_dwellings` question set, so the generator does not memorise test drawings. Add a procedural fallback (recursive split or the room-packing method of [SRC S1]) for shapes neither seed has.
2. **Scene graph (part of 1).** One JSON per drawing: rooms (polygon, type, net area), walls (centre line, thickness), openings (type, host wall, width, swing), fixtures (toilet, sink, bath, stove), text items (string, language, position), scale (1:50, 1:100, 1:200, or "no scale"), units, north arrow, title block fields. Every question answer is computed from this JSON with shapely, never typed by hand.
3. **Renderer (1.5 h).** Write DXF with layers WALL, DOOR, WINDOW, FIXTURE, TEXT, DIM, HATCH. Insert symbol blocks from a CC0 library [SRC S28] and from crops of our own sources. Render PDF and PNG through ezdxf [SRC S15]. For IFC-shaped questions, render real IFC models with `IfcConvert -yv ... --print-space-areas --scale` [SRC S16] and read answers from IfcOpenShell.
4. **Style randomisation (part of 3).** Vary: wall style (solid fill, double line, hatch at 45 degrees, poché grey); line weights (0.1 to 0.7 mm); door symbol (quarter arc, half arc, no arc, sliding, double); window symbol (three lines, two lines, filled); fonts (CAD stroke font, sans, condensed, handwritten-like); label language and abbreviations (EN, FI "MH, KPH, WC", DE "Zi., Bad", FR "Ch., SdB", IT "Camera, Bagno", plus the other ~25 languages through Haiku translation of the room-type list); area text in the room or not ("12.4 m2", "12,4 m²", none); dimension style (arrow, tick, dot; mm, cm, m; chains or none); furniture clutter (none to dense); title block (none, simple, full with scale field); scale bar present or absent; colour fills (cubicasa-like) or black and white.
5. **Questions (1 h).** One generator function per concept: count of room type, count of doors and windows, count of fixtures, area of room type, total area, length of a wall, number of apartments. Phrase each concept in many forms and in the 30 languages. Balance answers per template by rejection sampling, as CLEVR did [SRC S8]. Add a deliberate "not answerable" class: no scale and no dimensions for an area question; a symbol that is cut off; a whole-model question on a single sheet. The correct answer there is "I do not know" plus what is missing.
6. **Degradation (1 h).** Use Augraphy ink and paper stages only for area and length sets; allow its warps only for count sets [MEAS]. Add ocrodeg `printlike_multiscale` and `binary_blur` for parameterised noise [SRC S13]. Add JPEG at quality 30 to 90, downscale to 72 to 300 dpi, skew up to 3 degrees, yellow paper tone, stamps and pencil marks. These copy the habs, finna, europeana and wikimedia look.
7. **Shift suites and metamorphic harness (1.5 h).** See section C.

Cost to generate [EST from MEAS]: 10,000 drawings at about 1.3 s each, one core, about 3.6 h; on 12 cores about 20 minutes. No GPU. No API cost except the one-off translation of room labels and question templates.

### B. What the generator must vary to be a proxy for a harder hidden set

Ranked by my judgement of risk [EST], with the reason:

1. **Source style the public set does not have.** Historic hand drawings, US practice sheets, CAD exports without colour. 60% of drawings have no public questions (dataset README); the hidden set can ask about them.
2. **Scale availability.** With scale bar, with dimension chain, with "1:100" text only, with none. Stoa asked for "ask for a scale" behaviour.
3. **Count range.** Counts above the public maximum. [SRC S6] shows learned counters fail above the trained range.
4. **Language and abbreviation.** Room labels and questions in languages outside EN, FI, DE, FR, IT.
5. **Symbol set.** Door, window and sanitary symbols of other countries and firms. FloorPlanCAD notes that symbol variation across firms was missing from earlier data [SRC S27].
6. **Rotation and page layout.** Plan rotated 90 or 180 degrees, several plans on one sheet, title block and legend clutter.
7. **Degradation.** Low dpi, JPEG, skew, stains.
8. **Question phrasing.** Paraphrases and compositional forms ("bathrooms excluding WC", "rooms larger than 10 m2").

### C. Synthetic data as a test suite

Controlled shifts, each a separate report column, one factor changed at a time (the Super-CLEVR design [SRC S9]):

| Suite | Change | Pass rule |
|---|---|---|
| base | default style | accuracy per concept |
| symbol | new door, window and WC symbols | accuracy drop vs base |
| language | label and question language held out | accuracy drop |
| rotation | 90, 180, 270 degrees, small skew | count identical to base |
| scale | render at 1:50, 1:100, 1:200 | area identical in m2 when a scale is given |
| no-scale | remove scale bar, scale text and dimensions | abstain on area questions |
| clutter | furniture, hatches, overlapping text | accuracy drop |
| scan | Augraphy paper and ink, low dpi | accuracy drop |
| count-range | 2 to 5 times more instances | accuracy drop |

Metamorphic relations (they need no labels, so they also run on real unlabelled scans):

- Count(rotate(d)) = Count(d); Count(flip(d)) = Count(d); Count(PNG) = Count(PDF) = Count(DXF) for the same drawing.
- Area(scale s) = s^2 x Area in drawing units; Area in m2 is invariant when the scale annotation changes with it.
- Area(room A) + Area(room B) = Area(A union B) after a wall is removed in the scene graph.
- Adding one door symbol increases the door count by exactly one.
- Changing the question language does not change the answer.
- Blank out the scale bar: the answer must change to "I do not know" or the confidence must drop.

Report per suite: accuracy, abstention rate, accuracy on non-abstained, cost per question, and the blind baseline (mode per template).

### D. Training uses (only if time permits)

- Pre-train or fine-tune a small detector or pointer (counts as len(points)) on synthetic plans, then fine-tune on cubicasa5k and swiss_dwellings PNGs. Evidence for pre-training then fine-tuning: [SRC S1], [SRC S3]. [EST] 4 to 8 h including a Verda run.
- RL with verifiable rewards on synthetic questions is plausible, but the R1-V gain is partly a format effect [SRC S7]. Measure the base model without the reasoning format first.

## What does not work

- **Synthetic only, then test on real.** ChartQA: 20.96% vs 41.56% [SRC S3]. P&ID: 5.6 pp below 12 real images [SRC S2]. Real OOD counting: 16-34% at best [SRC S6].
- **Random placement without real structure.** About 33% edge mAP vs about 64% for topology seeded from real drawings [SRC S2].
- **More of the same synthetic data.** SynthPID gains flatten beyond roughly 400 images; "seed diversity" is the limit [SRC S2].
- **Template QA as proof of skill.** Template chart sets over-estimate progress; small changes drop performance by up to 34.5% [SRC S4]. Our cubicasa5k mode baseline at 55.3% shows the same risk.
- **Stated counts from VLMs.** InternVL3.5-8B direct count 45.52% vs 97.94% by counting points on synthetic OOD [SRC S6]. Frontier models count doors and windows at "often 0.40-0.55" [SRC S25].
- **Images instead of structure for geometry.** FloorplanQA: 19-40% from images vs 59-81% from JSON [SRC S24]. Extract structure (vectors, scene graph) first; reason on structure.
- **Default Augraphy pipeline for area labels** [MEAS], and **Augraphy on Python 3.14** [MEAS].
- **RPLAN-based learned generators** for this weekend: data access problems and GPL code [SRC S20].
- **DocCreator**: source build with dated macOS steps [SRC S14].

## Open questions

1. Does a generator seeded from Swiss Dwellings floors outside the public set reproduce the public answer rules (net vs gross area, which rooms count as "rooms")? Test: run our exact-geometry solver on 200 public swiss_dwellings rows and compare.
2. What does the hidden set look like for the historic sources? Ask Stoa whether hidden questions cover habs, finna, europeana and wikimedia, and which concepts.
3. Is free text (ifc_bench) scored by exact match or by a judge? A synthetic generator for free text needs that rule.
4. How large is the gap between our synthetic suite score and the public score per concept? If the two rank system changes the same way, the suite is a valid proxy. Measure with 3 to 5 system variants.
5. Licence of ezdxf and IfcOpenShell: checked in the fact check, MIT and LGPL-3.0 per the GitHub repositories. PyMuPDF AGPL is not checked.
6. Do the CC0 Innerscene blocks include 2D window and sanitary symbols? The page lists doors, windows, kitchens and baths as categories, but the 2D files are not opened [SRC S28].

## Check of the prior research

The prior pass (`inputs/prior-research/research-tracks.json`) has little on synthetic data. Its claims that touch this track:

- **Point-then-Count numbers [arXiv 2603.21746].** Confirmed: synthetic ID about 100%; real OCID ID 76-82% (PtC) vs 69-75% (direct); InternVL3.5-8B synthetic OOD 97.9% by counting points vs 45.5% direct; Molmo-7B zero-shot 99.95% vs 53% [SRC S6]. **Omitted and important:** on real OCID with counts above the training range, accuracy falls to 16-34% even with points [SRC S6]. Also the synthetic images are a 9x9 grid of coloured shapes on a uniform black background, far simpler than a floor plan [SRC S6]. The prior pass over-states how well this transfers to drawings.
- **Swiss Dwellings and MSD as CC BY 4.0 with WKT polygons in metres; MSD 5,372 plans.** Confirmed [SRC S17, S18]. Add: MSD train split is 4,167 plans [SRC S18], and the leakage risk of using it as an answer source.
- **Synthetic multilingual question pairs (translate templates with Haiku, fill slots).** Not checked in depth here (it belongs to the parsing track). It agrees with section A.5 of this file.
- `weekend-plan.md` has no claim on synthetic data.

## Sources

| id | URL | title | date | claim it supports | exact supporting quote | check |
|---|---|---|---|---|---|---|
| S1 | https://arxiv.org/abs/2607.06483 (and /html/) | Mitigating Domain Shift in Conditioned Floor Plan Generation: Synthetic Pre-training for Data-Efficient Adaptation (Ospici, Gueze, Bourrat, Bernhardt) | v1 2026-07-07, v2 2026-09-21 | Cross-domain degradation; synthetic pre-training helps; 135k scenes; method | "up to an order of magnitude performance degradation when transferred across domains"; "outperforming real-world initialization baselines by up to 40% in a low-data regime"; "The synthetic dataset comprises 135k scenes." | partly: title, authors, dates, the "order of magnitude", "up to 40%" and 135k quotes, CC BY-SA 4.0, Table 2 OOD averages 36.98, 50.83, 58.18 and the 7.05 vs 12.1 (41.7%) confirmed. The 41.7% is on RPLAN with 1k samples vs MagicPlan init, not general. Title ends "Synthetic Pre-training for Data-Efficient Adaptation". |
| S2 | https://arxiv.org/html/2604.16513 | SynthPID: P&ID digitization from Topology-Preserving Synthetic Data (CVPR 2026 workshop) | 2026 | Synth only vs real vs mixed; seeding from real; flattening | "achieves 63.8 ± 3.1% edge mAP on PID2Graph OPEN100 without seeing a single real P&ID during training"; Template generators "yield only ∼33% edge detection accuracy under synth-only training"; "gains flatten beyond roughly 400 synthetic images, pointing to seed diversity as the binding constraint"; Table 3: E1 Oracle 67.8 / 69.4, E2 SynthPID 64.2 / 63.8, E3 Mixed 71.3 / 72.6 | partly: title, authors (Prasad, Mahapatra), 63.8, ~33, 400 images, Table 3 and the seeds-from-same-12-images caveat confirmed. "CVPR 2026 workshop" is not stated in the preprint. 12 real images and 665 synthetic images in the main run. |
| S3 | https://arxiv.org/abs/2203.10244 (PDF v1, Table 6) | ChartQA: A Benchmark for Question Answering about Charts with Visual and Logical Reasoning (Masry et al., ACL Findings 2022) | 2022 | Synthetic-only vs real vs pre-train then fine-tune | "VisionTaPas⋆and VL-T5⋆are trained on PlotQA and evaluated directly on ChartQA." Table 6 Overall: VL-T5 41.56%, VL-T5⋆ 20.96%, VL-T5 Pretrained 51.84%, VisionTaPas 45.52%, VisionTaPas⋆ 31.96%; "large datasets like PlotQA can be useful for pretraining the model even if the questions are generated from a small number of templates" | confirmed (PDF Table 6, all five numbers, ACL Findings 2022) |
| S4 | https://arxiv.org/abs/2406.18521 | CharXiv: Charting Gaps in Realistic Chart Understanding in Multimodal LLMs (Wang et al., NeurIPS 2024 D&B) | 2024-06-26 | Template data over-estimates progress | "existing datasets often focus on oversimplified and homogeneous charts with template-based questions"; "a simple stress test with slightly different charts or questions can deteriorate performance by up to 34.5%" | confirmed (abstract quotes; NeurIPS 2024 D&B not checked) |
| S5 | https://arxiv.org/abs/2508.06492 | Effective Training Data Synthesis for Improving MLLM Chart Understanding (Yang et al., ICCV 2025) | 2025-08-08 | Realism of synthetic data matters | synthetic charts "often restricted by their inadequate similarity to the real charts"; "ECD consistently improves the performance of various MLLMs on a range of real-world and synthetic test sets." | confirmed (ICCV 2025 poster; ECD 10k+ charts, 300k+ QA) |
| S6 | https://arxiv.org/html/2603.21746v2 | Getting to the Point: Pointing Improves LVLMs at Counting (Alghisi, Rizzoli, Mousavi, Riccardi) | v2 2026-05-28 | Counting transfer and range limits; points beat stated counts | Table 2 InternVL3.5 8B synthetic OOD: DC 45.52, PtC 97.33, # Coord. 97.94; Table 3 real OCID OOD # Coord.: 30.98, 33.53, 31.18; "deriving the final count from the number of coordinates (# Coord.) increases accuracy substantially" | corrected: ID 93-100% not 97-100%; real OOD split is 11 to 20 objects (10 to 18 is synthetic OOD); real OOD fine-tuned accuracy 16-34% with # Coord., 2-19% with DC. Table 2 InternVL3.5 8B 45.52 / 97.33 / 97.94 confirmed. Table 3 values 30.98, 33.53, 31.18 are three of four models; the fourth (LLaVA-OneVision) is 16.27. |
| S7 | https://github.com/StarsfieldAI/R1-V | R1-V (GitHub) | 2025 | RL on synthetic CLEVR counting; format caveat | "Qwen2VL-2B-Instruct: 48.0%"; "Qwen2VL-2B-Instruct-GRPO-100step: 82.5%"; direct answering gives "a much higher score (86%) on SuperClevr" | confirmed (README has 48.0%, 82.5%, 86% SuperClevr) |
| S8 | https://arxiv.org/abs/1612.06890 | CLEVR: A Diagnostic Dataset for Compositional Language and Elementary Visual Reasoning (Johnson et al., CVPR 2017) | 2016-12 | Bias in VQA benchmarks; CLEVR aims at minimal bias | existing benchmarks "have strong biases that models can exploit to correctly answer questions without reasoning"; "It contains minimal biases and has detailed annotations describing the kind of reasoning each question requires." (Rejection sampling per family: read in search summary only, [UNVERIFIED]) | confirmed (abstract; rejection sampling for a near-uniform answer distribution per question family is in the paper text, sec. 3) |
| S9 | https://arxiv.org/abs/2212.00259 | Super-CLEVR: A Virtual Benchmark to Diagnose Domain Robustness in Visual Reasoning (Li et al., CVPR 2023) | 2022-12 | One-factor shift suites; disentangle perception and reasoning | "Four factors are considered: visual complexity, question redundancy, concept distribution and concept compositionality."; "disentangling reasoning and perception, combined with probabilistic uncertainty, form a strong VQA model" | confirmed (CVPR 2023 Highlight; quotes in abstract) |
| S10 | https://openaccess.thecvf.com/content/CVPR2021/html/Yuan_Perception_Matters_Detecting_Perception_Failures_of_VQA_Models_Using_Metamorphic_CVPR_2021_paper.html | Perception Matters: Detecting Perception Failures of VQA Models Using Metamorphic Testing (Yuan, Wang, Jiang, Chen, CVPR 2021) | 2021 | Metamorphic testing finds VQA failures | [UNVERIFIED: page returned HTTP 403] Search summary: over 4.9 million perception failures found. | confirmed (page opens, HTTP 200 for me; 4.9 million perception failures in the abstract; authors match). Earlier 403 did not repeat. |
| S11 | https://arxiv.org/abs/2208.14558 | Augraphy: A Data Augmentation Library for Document Images (Groleau et al.) | v2 2023-03-24 | Purpose of Augraphy | "standard office operations, such as printing, scanning, and faxing through old or dirty machines"; "generating challenging test data to evaluate model robustness on document image modeling tasks." | confirmed (v2 date 2023-03-24; quotes in abstract) |
| S12 | https://github.com/sparkfish/augraphy | Augraphy repository | read 2026-11-13 | Licence, default pipeline | "Augraphy is free and open-source software distributed under the terms of the **MIT** license."; `pipeline = default_augraphy_pipeline()` | confirmed (GitHub API licence MIT; version 8.2.6 is current on PyPI) |
| S13 | https://github.com/NVlabs/ocrodeg | ocrodeg repository (NVIDIA) | read 2026-11-13 | Degradation functions | "a small Python library implementing document image degradation for data augmentation for handwriting recognition and OCR applications."; "large 1D random distortions model paper curl." | confirmed (README quotes; no licence file in repo) |
| S14 | https://github.com/DocCreator/DocCreator | DocCreator repository | read 2026-11-13 | Licence and install friction | Badge "License: LGPL v3"; dependencies "OpenCV (3.x or 4.x)", "Qt 5" | confirmed (LGPL-3.0, OpenCV, Qt 5; README date 2019 not checked) |
| S15 | https://ezdxf.readthedocs.io/en/stable/tutorials/image_export.html | ezdxf Tutorial for Image Export | ezdxf 1.4.x docs | DXF to PDF/PNG/SVG API | `pdf_bytes = backend.get_pdf_bytes(page)`; `png_bytes = backend.get_pixmap_bytes(page, fmt="png", dpi=96)` | confirmed (both API calls in the page) |
| S16 | https://docs.ifcopenshell.org/ifcconvert/usage.html | IfcConvert Usage (IfcOpenShell 0.9.0post1 docs) | read 2026-11-13 | IFC to SVG plan with areas and scale | `IfcConvert /path/to/input.ifc -yv /path/to/output.svg -j 7 --exclude entities IfcOpeningElement IfcSpace`; `--print-space-areas`: "Prints calculated IfcSpace areas in square meters."; `--scale`: "Interprets SVG bounds in mm, centers layout and draw elements to scale." | confirmed (flags and example command in the page; docs version label 0.9.0post1 not checked) |
| S17 | https://zenodo.org/records/7788422 | Swiss Dwellings v3.0.0 (Archilyse AG) | 2023-03-31 | Public exact geometry, CC BY 4.0 | "increasing the total number of apartments to 45176"; `geometries.csv` "contains the geometries of all areas, walls, railings, columns, windows, doors and features"; licence "Creative Commons Attribution 4.0 International" | partly: page returned HTTP 403 to me. Confirmed through the DataCite record for the DOI: title, Archilyse/Standfest authors, v3.0.0 dated 2023-03-31 in the changelog, 45176 apartments, ~3,100 buildings, CC BY 4.0. Not seen: the geometries.csv sentence, WKT and the 931.9 MB size. |
| S18 | https://data.4tu.nl/datasets/e1d89cb5-6872-48fc-be63-aadd687ee6f9 | Modified Swiss Dwellings: a Machine Learning-ready Dataset for Floor Plan Auto-Completion at Scale | read 2026-11-13 | MSD size, licence, derivation | "The MSD dataset is derived from the Swiss Dwellings database (v3.0.0)."; "contains 4167 floor plans" (train); "CC BY 4.0" | partly: derived from Swiss Dwellings v3.0.0, 4167 train floor plans and CC BY 4.0 confirmed; the paper (arXiv 2407.10121) says "over 5.3K floor plans", exact 5,372 not found. |
| S19 | https://github.com/m-agour/ResPlan | ResPlan: A Large-Scale Vector-Graph Dataset of 17,000 Residential Floor Plans | v2 2026-08 | Second seed, licence, region | "LICENSE ← CC BY 4.0 (data) and MIT (code)"; "Metric-scale coordinates in metres"; "All plans come from South Asian residential markets" | confirmed (README badges CC BY 4.0 data, MIT code; South Asian; metric coordinates; median 110 m2). GitHub API shows no licence file. |
| S20 | https://github.com/aminshabani/house_diffusion | HouseDiffusion repository (Shabani, Hosseini, Furukawa, CVPR 2023) | read 2026-11-13 | GPL, RPLAN access problems | "License, GPL-3.0 licenses found"; "We have recently received many requests regarding issues with downloading the RPLAN dataset."; "We have provided a temporary model that you can download from Google Drive." | corrected: LICENSE text says code and weights are not for commercial use and, for research, terms follow GPL v3 (separate LICENSE_GPL). Temporary Google Drive model and RPLAN download note confirmed. |
| S21 | https://github.com/ennauata/houseganpp | House-GAN++ repository | read 2026-11-13 | Pretrained use; licence type not visible | "For running a pretrained model check out the following steps:" "Run python test.py." | corrected: LICENSE file is GPL v3 text with a "research purposes only" banner (the report said type not visible). "Run python test.py" not re-checked. |
| S22 | https://arxiv.org/abs/2206.06994 ; https://github.com/allenai/procthor | ProcTHOR: Large-Scale Embodied AI Using Procedural Generation (NeurIPS 2022) | 2022-06-14 | Scope and licence | "a framework for procedural generation of Embodied AI environments"; "a sample of 10,000 generated houses"; repo licence Apache-2.0 | confirmed (Apache-2.0 by GitHub API; 10,000 houses in the paper; pip install not checked) |
| S23 | https://arxiv.org/abs/2406.11824 | Infinigen Indoors: Photorealistic Indoor Scenes using Procedural Generation (CVPR 2024) | 2024-06-17 | Scope and licence | "Infinigen Indoors is open-sourced under the BSD license." | confirmed (abstract: BSD licence; CVPR 2024) |
| S24 | https://arxiv.org/html/2507.07644v4 | FloorplanQA: A Benchmark for Spatial Reasoning in LLMs using Structured Representations | v4 2026-05 | Exact answers from geometry; 2% tolerance; image vs JSON | "all ground-truth answers are computed deterministically using geometric algorithms (not model outputs)"; "Scalar outputs (N) are scored by relative error with a default tolerance of 2%"; "The structured JSON is the dominant signal" | corrected: 2% is the default; area tasks use 5%. Layouts are single-room furniture layouts. Date v4 2026-05-25, ICML 2026, 2,000 layouts, 16,000 questions, JSON-only 59-81 and image-only 19-40 confirmed. |
| S25 | https://arxiv.org/abs/2601.04819 | AECV-Bench: Benchmarking Multimodal Models on Architectural and Engineering Drawings Understanding (Kondratenko et al.) | 2026-01-08 | Frontier VLMs weak on symbol counting | Door and window counting "remains unsolved (often 0.40-0.55 accuracy)"; text-centric "up to 0.95 accuracy" | confirmed (abstract quotes; authors Kondratenko et al.) |
| S26 | https://arxiv.org/abs/2503.22346 | ArchCAD-400K (Luo et al.) | v3 2025-11-12 | Labels from CAD attributes at scale | "413,062 chunks from 5538 highly standardized drawings"; "leverages intrinsic attributes from systematically archived CAD drawings to automatically generate high-quality annotations". HF licence CC BY-NC 4.0 and 40k release: [UNVERIFIED] | partly: arXiv numbers, v3 date and quote confirmed. HF licence not found in the card; 40k gated release confirmed on the HF listing (jackluoluo/ArchCAD). |
| S27 | https://huggingface.co/datasets/Voxel51/FloorPlanCAD | FloorPlanCAD (Voxel51 card) | read 2026-11-13 | Real CAD set; synthetic SESYD too small | "Previous datasets (SESYD with 1,000 synthetic plans, FPLAN-POLY with 42 plans) were too small for deep learning"; prior datasets "lacked the symbol variation seen across different architectural firms and building types"; "Creative Commons Attribution-NonCommercial 4.0 License" | confirmed (card text non-commercial 4.0; HF tag cc-by-sa-4.0; SESYD, FPLAN-POLY, symbol variation quotes; 15,663 drawings, 30 classes) |
| S28 | https://www.innerscene.com/tools/videos/parts-library | Innerscene Free Parts Library | read 2026-11-13 | CC0 DXF symbol blocks | "Everything is public domain (CC0), free for client and commercial work, with no sign-up and no credit required."; "drawn at 1:1 in millimetres with named layers" | partly: CC0, over 1,600 drawings (DWG and DXF), 1:1 millimetres, named layers confirmed. "October 2026" date not on page. Page is a video tutorial page. |
| S30 | https://github.com/ChatHouseDiffusion/chathousediffusion | ChatHouseDiffusion repository | 2024 | Apache-2.0, trained on RPLAN | [UNVERIFIED: fetch quota ran out; licence from search snippet only] | partly: Apache-2.0 confirmed via GitHub API. "Trained on RPLAN" not checked. |
| MEAS | scratchpad `gen/gen.py`, `gen/aug.py` (not in repo) | own prototype | 2026-11-13 | Generator speed, Augraphy speed, warp, Python 3.14 failure | ezdxf 1.4.2: `{"n":20,"sec_per_drawing":0.072}`; Augraphy 8.2.6 at 2000x1700: `{"n":10,"mean_s":1.229,"max_s":4.108}`; Python 3.14: `TypeError: 'numpy.float64' object cannot be interpreted as an integer` | not checked by me (local measurement). Versions are plausible: Augraphy 8.2.6 is on PyPI; ezdxf current is 1.4.5, 1.4.2 is older. |

## Verification

- Date: 2026-11-13. Checker: independent fact check, not the author.
- Sources opened: 29 of 30 rows (S1 to S28 and S30). The MEAS row is a local measurement and was not re-run. Extra pages opened: Augraphy and ezdxf on PyPI, GitHub API for licences of Augraphy, ocrodeg, DocCreator, ResPlan, HouseDiffusion, House-GAN++, ProcTHOR, ChatHouseDiffusion, dxfBlocks, ezdxf, IfcOpenShell. The WebFetch tool was out of quota, so I used curl and read the pages and PDFs myself.
- Result: confirmed 18, corrected 4 (S6, S20, S21, S24), partly 7 (S1, S2, S17, S18, S26, S28, S30), not found 0, MEAS not checked (1). No source is missing: every arXiv id and URL resolves and the title matches.
- Corrections:
  1. S6 and finding 3: in-distribution accuracy is 93-100%, not 97-100% (and not 99.8-100% in the evidence table). Real OOD counts are 11 to 20 objects, not 10 to 18. Real OOD accuracy is 16-34% with points (16.27 for LLaVA-OneVision), 2-19% with direct count, not 19-34%.
  2. S20 and finding 9: HouseDiffusion is not plain GPL-3.0. Its LICENSE bars commercial use of code and weights and applies GPL v3 only for research.
  3. S21: House-GAN++ licence is visible: GPL v3 text with a "research purposes only" banner.
  4. S24: the 2% tolerance is the default. Area tasks use 5%. FloorplanQA layouts are single-room furniture layouts, not building plans.
  5. S18: the 5,372 figure is not on any page I opened. The paper says "over 5.3K". 4,167 train plans is confirmed. The test split is not public on the 4TU page.
  6. S2: "CVPR 2026 workshop" is not in the preprint. The numbers are right.
  7. S10: the page opened and the claim is supported. The UNVERIFIED mark on finding 8 is removed.
  8. S30: Apache-2.0 confirmed. dxfBlocks conflict confirmed (LICENSE CC0, README CC BY-NC-SA 4.0). ezdxf MIT and IfcOpenShell LGPL-3.0 confirmed. ocrodeg has no licence file, not "BSD-style".
  9. S28: the "October 2026" date is not on the page. The page lists doors, windows, kitchens and baths as categories.
  10. S17: HTTP 403 on Zenodo. Facts confirmed through DataCite, except the quote about geometries.csv and the 931.9 MB size.
- Still UNVERIFIED: ArchCAD HF licence (CC BY-NC 4.0); Graph2Plan licence; ChatHouseDiffusion "trained on RPLAN"; PyMuPDF AGPL; the MEAS numbers; the claim that Stoa uses a 2% tolerance; the lead's 55.3% blind baseline on cubicasa5k.
- No finding rests on a source that was not found, so no finding is marked UNVERIFIED in bold.

