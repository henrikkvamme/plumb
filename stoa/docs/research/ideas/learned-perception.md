# Lens: learned perception first

Written 2026-11-14, about 01:00. About 33 hours remain before the submission on Sun 2026-11-15 10:00.
This file replaces an earlier draft of the same lens from 2026-11-13. I kept its good parts and checked them again.

Each figure has a mark:

- MEASURED: I measured it on the local dataset in this session.
- SOURCED: it comes from a named file or source. I did not measure it again.
- ESTIMATE: my judgment, or the output of a simple model. Do not treat it as a fact.

I did not read `docs/inputs/prior-research/` or `stoa-drawings/`. I did not read the other idea files.
I read the brief, `docs/HOST.md`, 106 questions, 15 drawings at full size and 96 scans on four contact sheets.
I also read the team's research notes in `docs/research/data/` and `docs/research/sota/`. Where I use them, I name the file.

## 1. The lens in one paragraph

Every drawing can become pixels. A PDF, a DXF, an IFC model, a scan and a phone photo of a hand drawing all render to
an image, and a person reads all of them the same way. So this lens says: the hard part is seeing. Train small vision
models that find each symbol, each room, each text label and each scale mark on any style. Make them say how sure
they are. Let cheap deterministic code do the arithmetic on what they saw. The labels are almost free, because a
vector file labels its own raster (MEASURED below: a Swiss DXF maps to its PNG with a median error of 0.03 px).
The strongest argument against the lens is the scoring rule together with the data. Counts must be exact, and the
large counts are doors and windows. A detector needs about 98.8% per-object accuracy to get 90% of the cubicasa door
and window counts right (ESTIMATE from MEASURED count distributions). No published detector shows that on an unseen
style (SOURCED: `sota/floorplan-cv.md`). On files with structure, a parser is exact and free: the team's PDF parser
already answers 99.6% of the public Swiss questions with no model (SOURCED: `data/swiss.md`). And where a text label
marks the thing, a frontier model or plain OCR already reads it (MEASURED below: bedrooms 34 of 40 with untrained
OCR). So learned perception is the right first tool in a narrow place only: symbols without labels on rasters, and
sheets whose structure is missing or broken. That narrow place is small in the public set. It is probably large in
the hidden set.

## What I measured tonight

| Fact | Value | Mark |
|---|---|---|
| Files per source | cubicasa5k 4,787 PNG. swiss_dwellings 1,040 each of PDF, DXF, PNG. ifc_models 533 IFC, 500 PNG, 107 PDF, 107 SVG. ifc_bench 30 IFC. opening_design 678 PDF, 271 DWG, 48 IFC, 9 DXF. habs 1,506 JPG. finna 1,800 JPG. europeana 1,085 JPG. wikimedia 2,175 JPG and 135 SVG. | MEASURED |
| Long side of the images, 60 random files per source (p10 / p50 / p90) | cubicasa 583 / 973 / 1,896 px. europeana 786 / 1,200 / 3,000. wikimedia 658 / 1,833 / 2,500. finna and habs 3,000 for all three. | MEASURED |
| cubicasa question rows per image group | colorful 4,674. high_quality 17,352. high_quality_architectural 63,488. | MEASURED |
| cubicasa counts (mean, p90, max) | Windows 8.78, 19, 92. Doors 8.74, 15, 43. Sinks 2.61, 4, 30. Toilet bowls 1.39, 2, 20. Bedrooms 1.66, 3, 9. | MEASURED |
| Swiss counts (mean, p90, max) | Doors 30.7, 56, 157. Windows 17.8, 32, 137. Toilets 4.1, 8, 38. | MEASURED |
| Swiss DXF layers, one file | `ROOM_OUTLINE`, `WALL`, `WINDOW`, `DOOR`, `FIXTURE`, `UNIT_OUTLINE`, `ROOM_TEXT`, `ANNOTATION`. No block inserts. Fixtures are plain polylines and circles on one layer. | MEASURED |
| DXF to sheet alignment, 25 random Swiss sheets | One affine map per sheet, fitted on the room number texts (median 26 texts per sheet). Median residual 0.03 px, worst 0.50 px, at the 2,480 px PNG size. Scale 28.35 pt per metre on 21 sheets (1:100) and 14.17 on 4 sheets (1:200). | MEASURED |
| Swiss PNG against a render of its PDF, 4 sheets | Mean absolute grey difference 2.4 to 4.3 of 255. The PNG is the PDF page at 2,480 x 1,753 px. Some sheets are portrait. | MEASURED |
| Swiss raster resolution | 59.1 px per metre at 1:100 and 29.5 px per metre at 1:200 (computed from A3 and 2,480 px). A toilet of about 0.4 m by 0.7 m is about 24 by 41 px at 1:100 and 12 by 21 px at 1:200 (ESTIMATE of the toilet size). | MEASURED, part ESTIMATE |
| resbim | 500 PNG plans with 500 IFC models. No question on any of them. `resbim-19_plan.png` is 7,572 x 4,189 px. It has dimension chains in mm, grid bubbles and English room names. It has no scale bar, no printed areas and no fixtures. Its IFC has no `IFCSPACE`. | MEASURED |
| Files with questions in ifc_models | 84: 69 PDF and 15 IFC. | MEASURED |
| opening_design PDFs, first page, 80 random files | 65 have a text layer. 10 are a scan or an image only. 5 are vector lines with no text. | MEASURED |
| 96 scans on contact sheets, 24 per source, by eye | A floor plan is on the sheet in about 13 of 24 finna, 7 of 24 habs, 8 of 24 europeana and 20 of 24 wikimedia files. About 9 of 96 are not drawings (letters, photos, a book cover, a painting). The plans are ink or pencil with solid or hatched walls. I saw no modern fixture symbol set and no symbol legend. Many sheets hold several views. | MEASURED, small sample |
| OCR probe on cubicasa bedrooms | 40 random plans. RapidOCR with default models on a CPU, 4 rotations, a pattern for `MH`, `MH1`, `MAKUUHUONE`. Exact bedroom count on 30 of 40 at native size and on 34 of 40 after a 2x upscale. The mode guess gets 16 of 40. About 0.9 s per plan for one size. | MEASURED |
| What one public sheet already needs | opening_design A-701 shows the same restroom as a plan and as four elevations. A toilet is drawn about 12 times for 4 real toilets. The public question names one view: "enlarged plan 6B". | MEASURED by eye |
| cubicasa crops | `high_quality_architectural-10139.png` shows one flat and parts of two neighbour flats. Text runs upside down on `high_quality-10568.png`. | MEASURED by eye |

Facts from the team's notes that this lens depends on (all SOURCED, not measured by me):

- The public cubicasa answers are counts of CubiCasa5K SVG classes, 100% on all 12 templates. Stoa's 4,787 plans are
  4,018 of the public train split, 382 of val and 387 of test. 213 public plans are not in Stoa's release
  (`data/cubicasa.md`).
- Stoa drops a cubicasa question when the annotation is ambiguous. Doors are not asked on 1,268 plans, mostly because
  an open doorway exists (`data/cubicasa.md`).
- An informal probe of a frontier model on 8 cubicasa plans: windows 1 of 8, doors 2 of 5, all other templates 56 of
  59 (`data/cubicasa.md`). A published benchmark on 120 plans: best exact door count 39%, windows 34%; bedrooms and
  toilets up to 91% and 82% (`sota/vlm-on-drawings.md`, AECV-Bench, models up to January 2026).
- The Swiss reference door count is the number of database rows. A count of the distinct doors that a person sees
  matches on 74 of 1,040 floors, 7.1%. Windows match on 73.6% (`data/swiss.md`).
- From a Swiss PNG alone, a flood-fill room area is within 2% for 20.8% of rooms (`data/swiss.md`).
- RT-DETR-L trained on CubiCasa5K reaches AP50 89.8 for doors and 89.3 for windows in 2.3 hours on 2 A100
  (`sota/floorplan-cv.md`). Zero-shot Grounding DINO scores about 0.0 mAP50 on plan symbols (same file).
- The host tests one document at a time, then a series of questions, through our interface. Cost covers ingestion
  and query. About 10 cents for both is the target (`docs/HOST.md`).

### The exact-count budget

Model: each real object is counted correctly with probability r, independently. No false detections cancel a miss.
The exact rate of a template is the mean of r to the power n over the MEASURED answers. All cells are ESTIMATES.

| Template | r needed for 90% exact | Exact at r = 0.95 | Exact at r = 0.98 | Exact at r = 0.995 |
|---|---|---|---|---|
| cubicasa windows | 0.988 | 67% | 85% | 96% |
| cubicasa doors | 0.988 | 65% | 84% | 96% |
| cubicasa sinks | 0.960 | 88% | 95% | 99% |
| cubicasa toilet bowls | 0.926 | 93% | 97% | 99% |
| cubicasa bedrooms | 0.937 | 92% | 97% | 99% |
| Swiss windows | above 0.995 | 45% | 72% | 92% |
| Swiss doors | above 0.995 | 26% | 58% | 86% |

What the table decides. A learned counter alone reaches 90% exact on small counts only. For doors and windows it
needs a second source: structure, a self-check, or a person's click. So every concept below pairs the detector with
a posterior, a check and an honest "not sure".

### Prices used below

SOURCED: the model table of the Claude API skill in this harness, cached 2026-11-03. Per million tokens, input and
output: `claude-haiku-5-5` $0.10 and $0.50. `claude-sonnet-5-5` $2 and $10. `claude-opus-5-5` $4 and $20.
`claude-fable-5-2` $8 and $40. SOURCED: an image is capped at 4,784 visual tokens (`sota/vlm-on-drawings.md`).
Then one full image costs about $0.0005 on Haiku 5.5, $0.010 on Sonnet 5.5, $0.019 on Opus 5.5 and $0.038 on
Fable 5.2 (computed). A100 time at $2.4 per hour is $0.00067 per second (computed).
The consequence for this lens: money is not the reason to train a model. Ten cents per document buys several strong
model calls. The reasons that remain are exact counts, repeatable output, and a box on the drawing for each object.

## 2. Concepts

### Concept 1: The vector teaches the raster

**Pitch.** Each DXF, SVG and IFC file labels its own image, so one detector and one room model get thousands of
pixel-exact labels without a person drawing a box.

**Mechanism.**
1. Parse the labelled vectors: Swiss DXF layers, the `Ifc*` classes of the 107 SVG sheets, the public CubiCasa5K
   SVG (train split only), and the door and window placements of the resbim IFC models.
2. Map vector coordinates to pixels. For Swiss sheets this is one affine map per sheet (MEASURED: 0.03 px median).
3. Write one schema: door, window, toilet, washbasin, bathtub, shower, kitchen unit, stair, wall segment, room
   polygon, room label. Swiss fixture types come from simple shape rules on the `FIXTURE` layer.
4. Train one symbol detector on 1,024 px tiles (RF-DETR-M, Apache 2.0, SOURCED: `sota/floorplan-cv.md`).
5. For rooms and walls do not train. Use Raster2Seq weights as they are (SOURCED: room F1 88.7 on CubiCasa, interior
   IoU 73.9 zero-shot on Wikimedia plans). Snap its polygons to the wall ink.
6. Once per drawing: render, tile, detect, merge, store every object with a score. Per question: map the noun to a
   class and a counting policy, then count from the stored list. No model runs per question.

**Needs.** Label code: about 4 hours for one person with agents. Training: 4 to 6 A100 hours per round, about $10 to
$15 (SOURCED: the team's estimate in `sota/floorplan-cv.md`). No API calls. CubiCasa labels are CC BY-NC-SA.

**Effect on the criteria.** Accuracy: the only known fix for cubicasa doors and windows, 19.4% of cubicasa rows,
where a frontier model fails (SOURCED above). Evidence: strong, each object is a box with a score. Creativity:
medium. Cost: very low.

**Hidden set.** Good on held-out cubicasa. Unknown on other styles: the same public detector gives window scores of
0.9 on line art and 0.3 to 0.5 on rendered styles (SOURCED). It uses no file name, no template and no sibling file
at test time. The sibling is a training label only. It does not help on historic scans: I saw no fixture symbols
there, and old doors and windows are gaps in a thick wall, not arcs.

**Inference cost per question.** ESTIMATE: 1 to 2 s of A100 per drawing with 8 views, about $0.001. With 18 to 36
questions per drawing, under $0.0001 per question. It also runs on a CPU in a few seconds.

**Evidence view.** The drawing with one numbered marker per counted object. Weak objects are dashed. A click shows
the crop and the score.

**33 hours.** Fits: labels from CubiCasa and Swiss, two training rounds, the overlay. Does not fit: a detector that
is good on hand drawings.

**Kill measurement.** Train on the cubicasa train split. Test on Swiss PNGs against the distinct visible objects of
the DXF (not Stoa's reference, which counts stacked doors twice). If door recall is under 60%, the detector is a
cubicasa tool and not a general one.

**Main risk.** The exact-count budget. A good detector still loses many door and window questions.

### Concept 2: A count that knows its own odds

**Pitch.** Do not give one number: give a probability for each possible count, and answer only when one count wins.

**Mechanism.**
1. Calibrate detection scores on held-out drawings, per class, with isotonic regression.
2. The count is a sum of yes-or-no events. Its distribution is a Poisson binomial. Compute it exactly.
3. Run the detector on 8 views: 4 rotations, each mirrored. Match objects across views. An object seen in 8 of 8
   views is near certain. An object seen in 3 of 8 goes to the uncertain list.
4. Add a second estimator that makes other mistakes: a detector trained with another seed and another tile size.
   Two estimators that agree are worth more than one high score.
5. Add a style novelty score. Embed the sheet with a frozen backbone. Measure the distance to the nearest training
   sheets. A far sheet lowers every confidence and adds the sentence "this drawing style is new to me".
6. Tune thresholds on exact-count accuracy, not on mAP. Report "17 doors, 81% sure. 2 marks may be doors."
7. Abstain under a threshold. Tune the threshold on a source the model did not train on.

**Needs.** Concept 1. A split by drawing and a leave-one-source-out run. No extra training except the second seed.

**Effect on the criteria.** Accuracy: a few points from the 8 views (ESTIMATE). Its main effect is that wrong
answers become flagged answers. Evidence: very strong. The host asked for a confidence score and explicit unknowns.
Creativity: medium to high. No drawing benchmark scores calibration or abstention (SOURCED:
`sota/vlm-on-drawings.md`). Cost: 8 to 16 times a tiny number.

**Hidden set.** Calibration from one style is too confident on another. That is the known failure, and step 5 exists
for it. View disagreement needs no labels, so it works on any style.

**Inference cost per question.** ESTIMATE: under $0.0001.

**Evidence view.** A small bar chart of the count distribution. Solid markers for sure objects, hollow markers for
uncertain ones. A person resolves a hollow marker with one click and the count updates.

**33 hours.** Fits fully. It is a few hundred lines on top of concept 1.

**Kill measurement.** A reliability curve on a held-out source. If answers with a stated 90% are right less than 70%
of the time, do not show a percentage. Show three levels.

**Main risk.** Errors are not independent. An unseen style fails on every door at once. The posterior is then narrow
and wrong. Only the novelty score and concept 9 protect against that.

### Concept 3 (unusual): The sheet is its own training set

**Pitch.** A drawing is drawn by one hand in one style, so its own legend and its own sure objects are the best
examples of what to count on that sheet.

**Mechanism.**
1. Get examples from three places: the legend rows (a symbol picture next to a text), the most certain detections of
   concept 1, or one click of the user.
2. Compute dense features of the sheet once with a frozen backbone. Also keep the binarised line pixels.
3. Fit a tiny per-sheet classifier on the examples against random background. This takes about a second.
4. Score every candidate place at 8 poses and a small range of sizes. Confirm each hit with a strict line-pixel
   correlation at the matched pose.
5. Use it in two ways. First, to recover weak detections that look like the sure ones. Second, to count a symbol
   type that no detector class covers.
6. Map the question noun to a legend row or an example cluster with one cheap text call, in any language.
7. Once per drawing: features and legend rows. Per question: a lookup, or one pass for a new example.

**Needs.** No training for a first version. A frozen backbone. A legend finder (concept 7). The Swiss sheets have a
legend with 8 rows: WC, Lavabo, Badewanne, Dusche, Küchenzeile, Waschmaschine, Türe, Fenster (MEASURED on one sheet).

**Effect on the criteria.** Accuracy: high on CAD sheets where each symbol is an exact copy (ESTIMATE). Low on hand
drawings. Evidence: the best of all concepts: "this is the legend entry, these 10 marks match it". Creativity: high.
It reads the sheet the way a site engineer does. Cost: one backbone pass per drawing.

**Hidden set.** This is the one perception concept built for unseen symbol sets. A floor drain, a fire extinguisher
or a socket works if the sheet shows one example. When no example exists it says so: "this sheet has no legend,
click one example". The host accepts that kind of dialogue for a missing scale.

**Why it could still win.** The hidden set has "tricky drawings" from real projects. Real sheets carry legends, tags
and keynotes. A class list trained on Finnish flats does not contain them. Template fitting was also the best
zero-shot method in one published transfer test, at a low absolute level: 24.67 PQ (SOURCED:
`sota/floorplan-cv.md`). So the evidence is weak but points the right way, and the count is near deterministic.

**Inference cost per question.** ESTIMATE: $0.0005 per drawing for the backbone. Near zero per question.

**Evidence view.** The example on the left. The matches on the right, sorted from weakest to strongest, so a person
checks the doubtful ones first.

**33 hours.** Fits: line-pixel correlation with rotations on sheets with a legend, and "click one, find all" in the
interface. Does not fit: a trained matcher for hand-drawn variation.

**Kill measurement.** On 30 Swiss PNGs, count WC and Lavabo from the legend crop with no training. Compare with the
DXF fixtures. Under 80% exact: keep only "click one, find all".

**Main risk.** Doors and windows are not fixed symbols. They stretch with the opening. This works for fixtures and
tags, not for openings.

### Concept 4: A sheet factory with exact answers

**Pitch.** Take real building geometry, draw it again in many styles with a known answer to each question, and use
it to train and to test.

**Mechanism.**
1. Geometry: the 1,040 Swiss DXF files, the resbim IFC models and the cubicasa train SVGs. Real layouts, not random
   boxes: structure realism matters more than volume (SOURCED: `sota/synthetic-data.md`).
2. A renderer with random style: line weight, wall fill (solid, hatch, hollow, grey), door and window variants,
   fixture symbol sets, fonts, label language, with or without a legend, a scale bar, printed areas, dimensions.
3. A sheet composer: several views, a title block, a legend and a schedule table on one sheet.
4. A scan stage: paper texture cut from empty parts of the 6,570 scans, blur, skew, stamps, JPEG noise, low
   resolution. Use only stages that keep geometry when the label is an area (SOURCED: the default Augraphy pipeline
   bends walls).
5. Counts in the set go well above the public maximum, because learned counters fail above their training range
   (SOURCED: `sota/synthetic-data.md`).
6. Use it twice: training data for concepts 1, 7 and 8, and a test set in styles that no model trained on.

**Needs.** The team's prototype writes DXF, PDF, PNG and a scene graph in 0.07 s per drawing (SOURCED). The style
switches and the composer are about 6 hours for one person with agents (ESTIMATE). CPU only.

**Effect on the criteria.** Accuracy: indirect. Synthetic data helps as a supplement and is weak as the only data
(SOURCED). Evidence: none by itself. Creativity: medium. Stoa made the Swiss sheets the same way. Cost: zero at
inference.

**Hidden set.** It is our only labelled data in styles Stoa did not publish. It can ask what no public template
asks: "how many doors open into room 3.04", "is there a bathtub" with the answer no. Its weakness is the gap between
drawn by code and drawn by hand.

**Inference cost per question.** None.

**Evidence view.** Not shown to the user. For the judges: one real sheet and five redrawn versions of it.

**33 hours.** Fits: restyled Swiss geometry with 5 to 10 switches, the scan stage, the test set. Does not fit: a
building generator, hand-drawn strokes.

**Kill measurement.** Two detectors, one hour each: cubicasa only, and cubicasa plus restyled sheets. Test both on
original Swiss PNGs. If the second is not at least 5 points better in recall, the factory is a test tool only.

**Main risk.** Time. A renderer is pleasant to build and can eat a day.

### Concept 5: A frontier teacher and a small student on the scans

**Pitch.** Let a strong frontier model label a few hundred scans once, keep only the labels that survive an
agreement check, and train the small models on them.

**Mechanism.**
1. Embed all 6,570 scans with a frozen backbone. Cluster them. Take a few per cluster, so 400 scans cover the styles.
2. Hold out 20% of each source by collection prefix. No step may touch them.
3. Ask the teacher for structure per scan: view regions with a type, the scale text and scale bar, room names with a
   point, wall openings on plan regions. Use the Batch API at half price (SOURCED: Claude API skill).
4. Ask twice with different tilings. Keep a label only when both runs agree. Agreement is the filter.
5. Train the layout model of concept 7 on these labels. Add the opening labels to the detector as a second domain.
6. At test time only the students run.
7. I would not do self-supervised pretraining on the scans. 6,570 images are few, a run takes many GPU hours, and
   the gain cannot be measured before Sunday (ESTIMATE). The scans still serve three cheap uses: the clusters above,
   paper textures for concept 4, and the novelty score of concept 2.

**Needs.** ESTIMATE: 400 layout calls and about 600 tile calls to Opus 5.5 at about $0.05 per call, about $50, less
with batches. One more training round.

**Effect on the criteria.** Accuracy: the only way a student sees historic styles with labels. Label noise limits
it. Evidence: same as concepts 1 and 7. Creativity: it is Stoa's own sentence, "frontier models" plus "small
fine-tuned models". Cost: moves cost from each question to a one-time bill.

**Hidden set.** The scans are in the release with no questions, so they are likely test material. Machine labels use
none of Stoa's answers. That is not label leakage. It is still fitting to probable test images. Declare it, and
report the score on the 20% that no step saw.

**Inference cost per question.** Same as concept 1.

**Evidence view.** For the judges: teacher labels, the agreement filter and the student output on one scan.

**33 hours.** Fits: 300 to 400 labelled scans and one round. Does not fit: self-supervised pretraining.

**Kill measurement.** Check the teacher by hand on 20 scans. If fewer than 85% of its region boxes and scale
readings are right, there is nothing to distil.

**Main risk.** The teacher boxes large regions well (SOURCED: Fable 5.2 scores 85 and Opus 5.5 scores 79 on
CaseVBench boxes) and small symbols badly (SOURCED: door and window counts). So this concept can teach layout. It
probably cannot teach symbols.

### Concept 6: A small model that points

**Pitch.** Fine-tune a small open vision-language model to answer "point to every X" in any language, so a noun we
never listed still gets a located answer.

**Mechanism.**
1. Start from Qwen3-VL-4B or Qwen2.5-VL-7B. Both are Apache 2.0 and have working fine-tune tools (SOURCED:
   `sota/small-models-rl.md`). Molmo2-4B points best but has no public training code (SOURCED).
2. Turn the labels of concepts 1, 4 and 5 into prompts in many languages: "point to every toilet bowl", "Zeige jede
   Tür", "osoita kaikki ikkunat". The answer is the list of points.
3. Fine-tune with LoRA on tiles of about 1,000 px. Plain supervised training. If RL is added later, the reward must
   score the points, not the final number (SOURCED).
4. Per question: write one pointing prompt, run it on each tile, merge the points. The count is the number of
   points. Never use the number the model states (SOURCED: points and stated number often disagree).
5. Cache the result per noun and drawing.
6. Use it only when the detector has no class and the sheet gives no example.

**Needs.** 4 to 6 A100 hours (ESTIMATE). A GPU at test time.

**Effect on the criteria.** Accuracy: under a detector on known classes (SOURCED: no small model comes near a
detector on doors and windows). Better than nothing on new nouns. Evidence: points on the drawing. Creativity:
medium. It is the fashionable answer. Cost: one pass per noun per tile.

**Hidden set.** Good on new nouns and languages. Bad on large counts: fine-tuned counters fall to 16 to 34% on
counts above their training range (SOURCED). Tiling keeps the count per tile small and reduces this.

**Inference cost per question.** ESTIMATE: 2 to 5 s of A100 for a new noun, $0.001 to $0.003. Near zero when cached.

**Evidence view.** The points, and the exact prompt, so a person sees how the question was read.

**33 hours.** A first fine-tune fits. Proving that it beats a zero-shot call to a strong API model does not fit.

**Kill measurement.** Before any training: zero-shot pointing with the base model, with Opus 5.5 and with Fable 5.2,
on 100 cubicasa test plans for toilets and doors. If an API model wins at under 4 cents per image, do not fine-tune.

**Main risk.** Next year's frontier model replaces it. That is the opposite of what Stoa asked for. I would cut it.

### Concept 7: A model of the sheet before a model of the building

**Pitch.** Before any counting, split the sheet into its parts: plan, elevation, section, detail, schedule table,
legend, title block, scale bar, or "not a drawing".

**Mechanism.**
1. A layout detector with about ten region classes on a 1,024 px overview (RF-DETR: mAP50 0.949 on AEC sheet layout,
   SOURCED: `sota/floorplan-cv.md`).
2. Labels: composed sheets from concept 4 (exact), teacher labels from concept 5, and the fixed layout of the Swiss
   and IFC sheets.
3. A sheet class: building drawing or not. About 9 of the 96 scans I saw are not drawings (MEASURED by eye).
4. Find the text direction per region. Text is sideways or upside down on 13 of 33 cubicasa plans (SOURCED:
   `data/cubicasa.md`).
5. Read text once per region with its position: vector text when it exists, OCR when not, a cheap model call on the
   crops that OCR cannot read.
6. Give each view its own scale: the nearest scale text or scale bar in or under the region.
7. Per question: choose the regions the question is about. "How many toilets" must not count the elevations.

**Needs.** 300 to 600 labelled sheets. About 1 A100 hour (ESTIMATE). An OCR engine. My probe shows a default engine
works on cubicasa labels after a 2x upscale.

**Effect on the criteria.** Accuracy: almost no gain on the public set, where one file is one plan. A large gain on
multi-view sheets. Evidence: strong. The first thing the user sees is "I read this sheet as 3 plans, 2 elevations,
1 section, scales 1:100 and 1:200". Creativity: medium to high. It is the step the public set never rewards.
Cost: one small pass per drawing.

**Hidden set.** This is where the public set misleads the most. Almost every public question sits on a single-view
file. A system with 95% there can count each toilet three times on sheet A-701 (MEASURED by eye). A multi-view sheet
is the plainest case of "same extension, different structure".

**Inference cost per question.** ESTIMATE: $0.0002 per drawing for layout. OCR: 1 to 4 s of CPU per sheet. A Haiku
5.5 call per unreadable crop: about $0.0002.

**Evidence view.** The sheet with one coloured frame per region, each with its type and scale. The answer view zooms
to the regions that were used and greys out the others.

**33 hours.** Fits: region classes, the not-a-drawing class, text direction, OCR. Does not fit: reliable reading of
handwriting from 1900.

**Kill measurement.** Run a strong API model on 40 mixed sheets for region boxes only. If it is right on 90% of the
regions for under 2 cents, use the API call at ingestion and do not train this model.

**Main risk.** Honest answer to that measurement: the API model probably wins here. Large region boxes are the thing
frontier models do well. Then this concept stays, but its model is not ours.

### Concept 8 (unusual): Scale by vote of the dimension chains

**Pitch.** Do not trust one scale note: let every dimension on the drawing vote for a pixels-per-metre value, and
give an area only when the votes agree.

**Mechanism.**
1. Find dimension lines and their end marks, and scale bar ticks. Start with classic line detection. Train a small
   keypoint model only if that fails. Labels would come from resbim, where the IFC gives the true wall positions.
2. Read the number at each dimension line. Handle mm, m, and feet and inches.
3. Each dimension gives one vote: pixel length divided by the written length. A scale bar gives one vote. A printed
   "1:100" gives a vote only when the paper size is known.
4. Take the consensus with a robust fit. The spread of the inliers is the uncertainty of the scale.
5. Room polygons come from concept 1 and are snapped to the wall ink.
6. Area is polygon pixels times the scale squared. A 1% scale error is a 2% area error, so carry the error through.
7. No votes, or votes that disagree: no number. "I found no scale. Click two points of a known length."

**Needs.** OCR for numbers. Line detection. 1 to 2 A100 hours only if the keypoint model is needed (ESTIMATE).

**Effect on the criteria.** Accuracy: it opens area and length questions on rasters. Evidence: very strong: "23
dimensions agree on 59.1 px per metre within 0.4%". Creativity: high. Cost: one pass per drawing.

**Hidden set.** The 500 resbim PNG plans have no questions, no scale bar and many dimension chains (MEASURED on one
file). They look like hidden test material. For an area question on them this is the only raster route. A scale mark
exists on 84 of 120 sampled scans (SOURCED: `data/wild.md`). Marketing plans often say "not to scale" (SOURCED:
`data/cubicasa.md`). There the right answer is the abstain sentence.

**Why it could still win.** The host's hard example is tile area for the toilets: room finding plus scale plus area.
Most teams will read one scale note and trust it. A resized scan or a wrong note breaks them silently. A vote does
not break silently. The host also asked for exactly this dialogue: "give us a scale or calibrate".

**Inference cost per question.** ESTIMATE: $0.0005 per drawing. Zero per question.

**Evidence view.** Each used dimension in green, each rejected one in red, the consensus value, and the room polygon
with its area and error bar.

**33 hours.** Fits: votes from vector text on PDFs, votes from OCR on clean rasters, scale bars, the abstain path,
the two-click calibration. Does not fit: handwritten dimensions, photos taken at an angle.

**Kill measurement.** On 50 resbim PNG plans, recover the scale from the dimension chains and compare with the IFC.
If fewer than 80% are within 1%, raster areas cannot meet the 2% rule. The concept then becomes "detect that a scale
exists, else ask".

**Main risk.** The room boundary, not the scale. Flood fill on a Swiss PNG is within 2% for only 20.8% of rooms
(SOURCED). A right scale with a wrong polygon is still a wrong area.

### Concept 9 (unusual): An ink ledger and a second witness

**Pitch.** Check the answer without labels: every stroke of ink must be explained by something the system found,
and where a file has structure, the pixels must tell the same story as the structure.

**Mechanism.**
1. Ink ledger. Binarise the sheet. Each found item claims its ink: text boxes, walls, door arcs, window lines,
   fixtures, dimension lines, hatches, the frame.
2. The ink that nothing claims is the unexplained ink. Group it by shape. Many copies of one shape mean "a symbol
   type I do not know, 17 copies". Unexplained ink in a wall gap means "maybe a door or window I missed".
3. The reverse check: a detection with too little ink under it is a likely false hit.
4. Second witness. When a file has structure, read it with the parser (not this lens) and also run the perception
   stack on a render. The perception stack never sees layers or names.
5. Agreement raises the confidence. Disagreement lowers it, and the view shows the objects that one witness missed.
6. During development each disagreement is a free hard example or a parser bug found without a person.
7. Metamorphic checks run on the same data: a rotation or a mirror must not change a count (SOURCED: recommended in
   `sota/synthetic-data.md`). All of this runs once per drawing.

**Needs.** Concepts 1 and 7 for the ledger. Both pipelines for the witness. No training.

**Effect on the criteria.** Accuracy: it protects right answers and flags wrong ones. Evidence: strong and honest:
"92% of the ink on this plan is explained. These 3 marks are not." Creativity: high. Cost: image operations only.

**Hidden set.** Both checks need no labels and no known style, so they work on what we never saw. A parser tuned to
Stoa's Swiss renderer looks for the layer `DOOR`. A DWG from a real practice uses its own layer names. opening_design
alone has 271 DWG files (MEASURED). The parser then returns 0 with full confidence, and the pixel witness catches
it. The witness also shows a convention problem: the Swiss reference counts stacked doors twice (SOURCED). The
system can then say which count it gives and why.

**Why it could still win.** It answers the judge's question "how do you know when you are wrong" with a mechanism.
"Here is the ink I could not explain" is the visual form of "these are the parts I do not know".

**Inference cost per question.** ESTIMATE: under $0.0001.

**Evidence view.** A switch that colours the sheet by claimant: walls, openings, fixtures, text, dimensions, and
bright orange for unexplained ink. For files with structure: two columns with matched objects joined by a line.

**33 hours.** Fits: the ledger with connected components and the witness comparison on Swiss. Does not fit: a
learned model of what each stroke is.

**Kill measurement.** On the cubicasa test split, relate the unexplained ink share near walls to door and window
count errors. If it does not separate right from wrong counts (AUC under 0.65), keep the ledger as a view only.

**Main risk.** Furniture, hatches and decoration are legitimate ink that is not ours to explain. On a rich sheet the
ledger can cry wolf on every plan.

### An idea I reject: the answers as labels

A network can regress the 12 cubicasa counts from the whole image, trained on the 85,514 public answers. It needs no
SVG and no boxes. I expect a high public cubicasa score from it (ESTIMATE). It learns the answer distribution (a
mode guess already gets 55.3%) and CubiCasa's annotation habits. It gives no box as evidence. It transfers to
nothing. It is the purest form of the trap in the brief, so it gets no concept.

## 3. The system I would build from this lens

### The idea

Perception is a compiler, not an oracle. Each drawing compiles once into a typed scene graph: regions, objects,
rooms, texts and scales. Each item keeps its source, its score and its place on the sheet. The graph has the same
schema as the output of the structure reader for DXF, IFC and vector PDF. So a question never touches pixels. It
becomes a small deterministic query. The models propose. Checks without labels decide how much to trust them. A
strong API model is a paid expert for the few crops that stay unclear, inside the 10 cent budget. A person is the
last resort, with one click.

### Diagram

```
 file bytes (random name, no sibling file)
        |
        v
 [ render all pages to pixels ] ---------------------------+
        |                                                  |
        v                                                  v
 [ sheet model, concept 7 ]                      [ structure reader ]
   regions: plan / elevation / section /           vector layers, PDF text,
   table / legend / title / scale bar /            IFC entities (another lens)
   not a drawing; text direction                           |
        |                                                  |
        v                                                  |
 [ text ]  vector text, else OCR at 2x and 4 rotations,    |
           else a cheap model call on the crop             |
        |                                                  |
        v                                                  |
 [ symbols ]  detector, 8 views, 2 seeds (1, 2)            |
              examples from the sheet itself (3)           |
 [ geometry ] walls and room polygons, snapped (1)         |
 [ scale ]    votes from dimensions and bars (8)           |
        |                                                  |
        +---------------> [ scene graph ] <----------------+
                           same schema for both sources:
                           item, class, pixels, source, score
                                  |
                 [ checks without labels, concept 9 ]
                   ink ledger, view agreement, witness
                   comparison, style novelty
                                  |
                 [ adjudication ] at most N unclear crops go to
                   a strong model: "is this a door with a leaf?"
                                  |
 question --> [ parser ] noun, class or label filter, policy, unit, regions
                                  |
                 [ deterministic query on the graph ]
                                  |
   answer record: value, count distribution, used items, method per step,
   cost, or "I do not know, because: no scale / no plan on this sheet /
   style is new and 3 marks are unexplained" plus what the user can do
```

### How the parts work together

- Ingestion runs once per drawing. Stoa tests one document, then a series of questions (SOURCED: `docs/HOST.md`).
  Every question after the first costs almost nothing.
- The question parser reads the counting policy from the question. The public questions state it: "open doorways
  without a door leaf do not count", "a double sink counts as one". The policy is a parameter of the query. No rule
  depends on the source.
- Room types come from three cues, in this order: the text label in any language, the fixtures inside the room, the
  shape and place. The answer says which cue decided. This is what the tile question of the host needs: find the
  toilet rooms, then take their areas.
- Each model keeps to what it is good at. The detector counts symbols without labels. OCR and the cheap model read
  text. The strong model draws large regions and judges single crops. No model states a count.
- The cost stays under the target. ESTIMATE per document: local models $0.002, layout call $0.02, up to 10 crop
  calls $0.02, question parsing with Haiku 5.5 under $0.001 per question. About 5 cents for a document with 20
  questions.

### What to train on Verda

| Model | Labels | Split rule | A100 hours (ESTIMATE) |
|---|---|---|---|
| Symbol detector, round 1 | CubiCasa5K SVG, public train split only, and only plans in Stoa's release (4,018) | Validate on the 382 val plans. Report on the 387 test plans. | 4 to 6 |
| Symbol detector, round 2 | Round 1 plus Swiss DXF labels (80% of sites), restyled Swiss sheets, the 107 IFC SVG sheets | Swiss by site. Report on the 20% held-out sites and leave-one-source-out. | 4 to 6 |
| Second seed for the ensemble | Same as round 2 | Same | 4 |
| Sheet layout model, only if the API test says so | Composed sheets, teacher labels on scans | 20% of scans held out by collection prefix | 1 |

Total: 9 to 17 A100 hours, about $22 to $41 at $2.4 per hour. One `1A100.22V` at a time is enough. Nothing needs a
machine above $10 per hour. I would not train the room model, the pointing model, the scale keypoints or any
self-supervised backbone this weekend.

### How to avoid training on drawings that can be in the hidden set

1. The 213 public CubiCasa plans that Stoa left out are the likeliest hidden cubicasa set (SOURCED). Never train on
   them, even though 182 are in the public train split. Keep them as a locked test. Open it twice at most.
2. Do not use public CubiCasa weights for a reported score. They have seen the labels of 84% of Stoa's plans
   (SOURCED). Our own detector trains on the train split and reports on the test split.
3. Swiss: use only the 1,040 released DXF files, split by site. Do not download other floors of Swiss Dwellings
   v3.0.0 for training. They are the likeliest hidden Swiss set, and a sibling floor has the same door count 43% of
   the time (SOURCED: `data/swiss.md`).
4. resbim: 500 plans with exact IFC labels and no questions. Training on them is fitting to probable test files. If
   we use them, use 300 and lock 200. Report on the 200.
5. Scans: machine labels only, 20% held out by collection prefix, and say so in the pitch.
6. At inference the pipeline gets bytes under a random name. No file name, no id from a title block, no sibling
   file, no `LICENSE.md` row, no lookup in any public table.
7. The headline number for every model is its score on a source it did not train on.

### Order of work

| Hours from now | Work | Output |
|---|---|---|
| 0 to 3 | Label code for CubiCasa SVG and Swiss DXF. Measurements 1, 3 and 5 below start in parallel. | Labels checked by overlay. A go or no-go on the layout model. |
| 3 to 8 | Detector round 1 on Verda. Scene graph schema, agreed with the structure lens. OCR stage. | Exact-count rates on the cubicasa test split and on Swiss PNGs. |
| 8 to 12 | Count posterior with 8 views. Ink ledger. Witness comparison on Swiss. | Concepts 2 and 9 working. |
| About 11 | Stoa's hint on the hidden questions, expected Saturday midday. Plan again. | |
| 12 to 18 | Detector round 2 and the second seed. Scale votes on PDFs and resbim PNGs. Region choice per question. | Concepts 7 and 8 on clean inputs. |
| 18 to 26 | Hard sheets: scans, multi-view sheets, PDFs with no text layer. Abstain reasons. Crop adjudication. | Scores on the hand-made hidden-like set. |
| 26 to 33 | Freeze. Cost report. Evidence data for the interface. Demo. | |

### What I would cut first

1. The pointing model (concept 6).
2. Self-supervised pretraining and the student for symbols on scans (parts of concept 5).
3. Our own layout model, when a strong API model draws the regions well enough (concept 7).
4. The sheet factory beyond restyled Swiss geometry (concept 4).
5. Automatic legend matching. Keep "click one, find all" (concept 3).
6. Raster areas from learned polygons. Keep the scale vote and the calibration dialogue (concept 8).

What I would not cut: the detector for doors and windows, the count posterior with the uncertain list, the ink
ledger view, and the region choice per question. These four give exact counts where nothing else does, and the
confidence and the "I do not know" that the host named.

## 4. Where this lens is wrong

- **Files with structure.** One third of the public questions sit on Swiss sheets, IFC models and schedule tables.
  A parser answers 99.6% of the public Swiss questions with no model (SOURCED). The host said vector PDF is "a lot
  easier" and "we appreciate deterministic as much as possible". A detector there is slower, less exact and less
  deterministic.
- **Swiss doors against the public reference.** The reference counts database rows. What a person sees matches on
  7.1% of floors (SOURCED). The best possible eye, human or model, loses this template. Only a reader of stacked
  vector copies wins it.
- **Areas on rasters.** 20.8% of rooms within 2% by flood fill (SOURCED). Learned polygons with snapping may do
  better, but nobody has shown 2% on small rooms.
- **Things with a text label.** Bedrooms, kitchens, saunas, room names. Untrained OCR with a word pattern gets 34 of
  40 bedroom counts (MEASURED). A frontier model gets rooms and fixtures right on cubicasa (SOURCED, 8 plans). No
  training is needed there. A trained room classifier would only learn CubiCasa's habits.
- **Schedule lookups, IFC queries and free text.** "What is the width of door 121.A" is table reading. "What is the
  space breakdown per floor" is a model query. No detector helps.
- **Historic scans.** I saw no fixture symbols on 96 scans. Old doors and windows are wall gaps. Our labelled
  sources contain none of this. The questions there are more likely about scale, dimensions, room names, storeys
  and views. A frontier model that has seen many old drawings probably reads them better than anything we can train
  by Sunday (ESTIMATE).
- **Conventions.** A detector trained on CubiCasa SVG learns that a shower cabin is not a shower and that a room
  without a label is not a bedroom (SOURCED). That raises the public score. It can lower the score on a tricky
  drawing whose answer a Stoa engineer wrote by eye.
- **The form of the test.** The hidden test is a few documents and a few tens of questions, run by people (SOURCED:
  `docs/HOST.md`). One sheet in a style the detector never saw is a zero for that document. A general reader that
  is a little worse on average and never collapses beats a specialist.
- **Time.** Each hour of training is an hour not spent on the parser, on the hand-made hidden-like set, or on the
  evidence view.

How the public score misleads this lens in particular. 67% of the public rows are cubicasa. A detector trained on
all 5,000 CubiCasa SVGs would look excellent there and would have seen the test labels. Even a clean detector is
tested only on the cases Stoa found unambiguous: the plans with an open doorway have no door question. And the
public set has no multi-view sheet, no missing scale, and almost no answer of zero or "not on this sheet". A system
tuned on it learns to always answer, on one view, in one style.

My honest ranking for 33 hours. The structure lens owns every file with structure. A frontier model with good
tiling owns text, layout and labelled things. This lens owns four things: door and window counts on rasters, the
confidence and abstention layer, the label-free checks, and the scale vote. The first is the only one that needs a
GPU.

## 5. Ten things to measure first

Ranked by how much each one changes the plan.

1. **Detector against frontier model on the clean cubicasa test split.** Train round 1. On the 387 test plans,
   report exact counts per template for the detector, for Opus 5.5 and for Fable 5.2 with tiles, and for the mode
   guess. Settles: which templates need the detector at all. I expect doors and windows only. If the frontier model
   is within 5 points on those two, stop training.
2. **Cross-style transfer.** The round 1 detector on 200 Swiss PNGs against the distinct visible objects from the
   DXF. Per-class recall, precision and exact count. Settles: general tool or cubicasa tool. It decides round 2 and
   the sheet factory.
3. **A hand-made hidden-like set.** 30 sheets, 4 questions each, answers by two people: 10 opening_design plan
   sheets with some PDFs that have no text layer, 10 scans with a plan, 10 resbim PNGs. Start from the lead's
   `data/wild-probe-questions.jsonl`. Settles: where the Saturday hours go. It is the only test that looks like the
   real one.
4. **Honesty of the confidence on an unseen source.** Reliability curve of the count posterior when the detector
   did not train on that source, with and without the novelty score. Settles: a percentage, three levels, or
   nothing, and the abstain threshold.
5. **Layout by API call.** Region boxes and view types from Opus 5.5 and Fable 5.2 on 40 mixed sheets, checked by
   eye. Settles: whether we train a layout model or pay 2 cents per document.
6. **Text reading by source.** Extend my OCR probe: all room types, Swiss PNGs, 40 scans, at native size and 2x,
   against Haiku 5.5 on crops. Settles: the OCR engine, whether room templates need any model, and the size of the
   handwriting gap.
7. **Scale from dimension chains.** 50 resbim PNGs against the IFC, and 30 scans with a scale bar against a hand
   measurement. Settles: raster areas within 2% are possible, or the area path on rasters is "ask for a
   calibration".
8. **Room polygon area error.** Raster2Seq polygons with wall snapping on 100 Swiss PNGs against the DXF room
   areas, by room size. The number to beat is 20.8% within 2%. Settles: whether any learned geometry may answer an
   area, or only the vector path may.
9. **Does the ink ledger predict errors.** On the cubicasa test split, relate unexplained ink near walls to door
   and window count errors. Settles: ledger as a confidence input, or as a view only.
10. **Examples from the sheet.** Legend matching with no training on 30 Swiss PNGs for WC and Lavabo against the
    DXF. Settles: automatic concept 3, or "click one, find all" only.

Two more if time allows. Ingestion time and cost for a 3,000 px scan and for a 20-page PDF on a CPU and on a GPU:
this decides whether the demo needs a GPU and whether a person waits too long. And the teacher check on 20 scans
from concept 5.
