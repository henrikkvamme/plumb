# Stoa "Make Blueprints Talk" - 12 concepts and 10 research questions

All accuracy and cost figures below are my estimates, not measurements. I read the brief and the repo status only. CubiCasa5K facts (4,200/400/400 split, SVG classes, CC BY-NC licence) and model names are from memory and need a check.

Three facts shape every concept:
- 53% of preview questions are CubiCasa counts, and their classes match the public SVG annotation classes. A detector trained on those annotations learns Stoa's exact label convention.
- About 21 questions exist per drawing. Work done once per drawing is amortized, so per-question cost can be near $0.
- Swiss Dwellings and IFC have exact geometry. They need no model at inference, only the right program.

## Concepts

### 1. Tally - a trained symbol detector where every count is a set of numbered marks
- **Pitch:** A 20M-parameter detector replaces Opus pointing for 76% of the questions.
- **How:** Parse CubiCasa5K SVG into boxes: door with leaf, door without leaf, window, toilet, sink, shower, bathtub, sauna bench, and room instances (kitchen, bedroom, bath, sauna, WC). Run tiled inference at high resolution. Count = number of boxes above a per-class threshold tuned for exact-count accuracy, not mAP.
- **Train on Verda:** YOLO11m or RT-DETR at 1280 px with tiles. About 4,000 plans with the Stoa question drawings held out. 1A100, 2-3 h per run, 3 runs, about $20.
- **Effect:** Accuracy - large gain, my guess is 60-85% exact per class, with windows the weakest. Verify - each box is a mark. Creativity - low alone. Cost - about 50 ms on CPU, $0.
- **Demo:** "How many windows?" returns 14 numbered marks in under a second, next to Opus taking 40 s and missing two.
- **Risk:** Exact match is harsh, because one missed window fails the question. If the hidden drawings are in the public training split, the held-out number is the only honest one.

### 2. Recipe Foundry - induce one program per question template from the answer key
- **Pitch:** Opus works once, offline, to write the program, and the program then answers every question of that template at no cost.
- **How:** Cluster the 120,000 questions into templates. For each template on DXF or IFC, Opus proposes candidate programs (which layer, which Qto quantity, net or gross, exclude balconies). A harness scores each candidate against the reference answers. The winner is frozen as a recipe with its measured accuracy.
- **Train on Verda:** Nothing required. Optional: embed all questions on 1V100 for clustering, under 1 h.
- **Effect:** Accuracy - close to 100% on vector templates when the key came from the same geometry. Verify - the recipe is readable and prints its steps. Creativity - high ("the answer key is the supervisor"). Cost - $0 per question.
- **Demo:** A table of templates, each with its recipe and "reproduces 1,612 of 1,614 reference answers".
- **Risk:** It overfits to this generator. A new phrasing needs concept 3 as fallback.

### 3. Question Compiler - a tiny multilingual model that writes the query, trained by reward from the executor
- **Pitch:** A model of about 1B parameters turns a question in any of 30 languages into a typed query, with no frontier model in the loop.
- **How:** Output is a small DSL: `count(door, leaf=true)`, `area(room="Zimmer", net=true)`, `volume(IfcSlab, storey="4. Sal")`. Stage A: supervised training on pairs from Recipe Foundry. Stage B (stretch): GRPO, where reward = the executed result matches the reference answer within 2%. No program labels are needed.
- **Train on Verda:** Qwen-class 0.6-1.7B text model with LoRA. Stage A: 1A100, 1-2 h. Stage B: 1A100, 6-8 h, with cached per-drawing fact tables so the executor is fast.
- **Effect:** Accuracy - holds on paraphrases and rare languages. Verify - the query is shown in one line. Creativity - high, since GRPO with a geometry executor as reward is new. Cost - one small-model call, under $0.0001.
- **Demo:** Type the question in Estonian, then in Italian. The same query appears and the same polygons light up.
- **Risk:** GRPO may not converge in time. Stage A alone must be enough to ship.

### 4. Plan Lifter - compile each raster plan once into a scene graph
- **Pitch:** Read the drawing once, then answer every question about it from a fact sheet.
- **How:** Segment walls and rooms, vectorize them to polygons, attach detected fixtures and openings to rooms, and OCR the room labels (MH, KH, PH, S, WC). Store a graph per drawing. "Separate WC rooms" becomes a graph query: a room with a toilet and no shower. "Storeys" becomes the number of separate plan bodies.
- **Train on Verda:** Room and wall segmentation on CubiCasa SVG polygons (YOLO-seg or SegFormer-B2). 1A100, 3-4 h. Optional small OCR fine-tune for plan abbreviations, 1V100, 2 h.
- **Effect:** Accuracy - room-type counts become reliable, and it enables areas on rasters when a scale exists. Verify - rooms are shown as coloured polygons. Creativity - medium-high. Cost - one pass per drawing, then $0 for all its questions.
- **Demo:** Drop a PNG. In 2 s the plan becomes a clickable graph, and 20 questions are answered at once.
- **Risk:** Vectorization is brittle on unusual plans. Limit it to room polygons and containment, not full wall topology.

### 5. Rosetta Triplets - PDF, DXF and PNG of the same drawing supervise each other
- **Pitch:** The vector file labels its own raster, so the dataset trains the model for free.
- **How:** In Swiss Dwellings, DXF blocks and layers give exact door, window and toilet positions. Project them onto the PNG as labels. Do the same from IFC elements to their rendered SVG plans. Add scan-style augmentation (blur, skew, noise, ink bleed). At inference on a triplet, run both paths and flag any disagreement.
- **Train on Verda:** Fine-tune the Tally detector on these auto-labels. 1A100, 2 h.
- **Effect:** Accuracy - carries the detector beyond the CubiCasa style. Verify - a "vector says 6, pixels say 6" badge. Creativity - high. Cost - $0.
- **Demo:** A side-by-side of a DXF and its PNG with the same six marks, plus one disagreement the system caught itself.
- **Risk:** Registration between DXF coordinates and PNG pixels needs a per-file transform. Rendered plans may still be far from scans.

### 6. Two Witnesses - an answer is confident only when two independent methods agree
- **Pitch:** The system knows when it is wrong, and it says so.
- **How:** Witness A is the detector. Witness B is a different method: a density-map counter, the pointing VLM, or the same detector on flipped, rotated and re-tiled input (the count must not change). A small verifier classifies each crop as a true or false object. Agreement gives a green badge. Disagreement gives amber, plus escalation to one focused Opus call on only the disputed crops.
- **Train on Verda:** Crop verifier (ConvNeXt-tiny) on detector hits and misses. 1V100, 1-2 h. Calibrate thresholds on held-out data.
- **Effect:** Accuracy - gains on the hard tail. Verify - disputed objects are the only things a human must check. Creativity - high. Cost - Opus is used on a small fraction of questions, and only on crops.
- **Demo:** "13 or 14 windows. One mark is disputed. Here it is." The human settles it in one click.
- **Risk:** Witnesses trained on the same data make the same mistakes, so agreement overstates confidence.

### 7. Contact Sheet - a verification UI built for a 5-second check
- **Pitch:** Verify 14 windows without panning the drawing.
- **How:** Every count shows numbered marks and a grid of crops, one per object, with keyboard stepping. Below it is a "not counted" row: the nearest rejected candidates with the reason. Every area shows highlighted polygons and an arithmetic tape: each room's area, excluded parts hatched and struck through, the sum, and the 2% tolerance band. A click on a mark removes or adds it and updates the answer.
- **Train on Verda:** Nothing. It consumes the outputs of concepts 1, 4 and 6.
- **Effect:** Accuracy - none directly. Verify - the largest gain of all concepts. Creativity - high, because showing the rejected candidates is rare. Cost - $0.
- **Demo:** A judge verifies an answer with a stopwatch on screen.
- **Risk:** UI time competes with model time. It needs one dedicated person.

### 8. Pointer - a small pointing VLM, tuned with LoRA and then with a count reward
- **Pitch:** A 2B model that points at "every door with a leaf" in any language, for open vocabulary where the detector has no class.
- **How:** Convert SVG and DXF labels to point targets. Fine-tune a small VLM with a pointing skill (Moondream, PaliGemma 2 or a small Qwen-VL). Stretch: GRPO with reward = Hungarian-matched point F1 minus count error.
- **Train on Verda:** LoRA: 1A100, 4-6 h. GRPO: 2A100, 8-10 h, about $45.
- **Effect:** Accuracy - probably below the detector on closed classes, but better on unseen symbols. Verify - points are marks. Creativity - high, and it matches Stoa's "small fine-tuned models" request. Cost - about 1 s on a V100, around $0.0001.
- **Demo:** Ask for something the detector never saw, such as "fireplaces" on a historic scan.
- **Risk:** The highest of the trained models. Dense small symbols at plan resolution are hard for VLMs, and the time budget is tight.

### 9. Symbol Twin - click one symbol, find all its copies
- **Pitch:** One-shot counting from a legend entry or one user click.
- **How:** Train a symbol embedding so that copies of one symbol are close. DXF gives free labels: every INSERT of the same block is the same symbol. CubiCasa icons add more. At query time, the exemplar comes from the legend or a click, and a sliding-window match returns all instances as marks.
- **Train on Verda:** Siamese ConvNeXt-tiny with contrastive loss on block renders with rotation, scale and scan noise. 1A100, 2-3 h.
- **Effect:** Accuracy - covers the long tail (US sets, historic scans). Verify - the exemplar and its matches are shown side by side. Creativity - very high. Cost - $0, CPU.
- **Demo:** Click one sprinkler head on a US sheet. 37 marks appear.
- **Risk:** Few preview questions need it, so the measured accuracy gain is small. Its value is in the pitch and in robustness.

### 10. Building Twin - the answer as highlighted 3D elements with a ledger
- **Pitch:** "Total slab volume on storey 4" lights up the slabs in 3D and lists each one in the sum.
- **How:** A web IFC viewer (web-ifc or That Open) isolates the storey, colours the elements that enter the answer, and shows a ledger row per element with its GlobalId and quantity. A click on a row flies the camera to the element. For ifc_bench free-text answers, the text is rendered from a group-by table, so every number is traceable.
- **Train on Verda:** Nothing.
- **Effect:** Accuracy - none directly, but it exposes wrong selectors fast. Verify - excellent for IFC (about 13% of questions). Creativity - medium, visually strong. Cost - $0.
- **Demo:** An exploded-storey view with one storey lit and the sum counting up.
- **Risk:** Large IFC files load slowly in the browser. Pre-convert them to fragments.

### 11. Penny Cascade - a learned router with a live cost meter
- **Pitch:** Each question takes the cheapest path that is still correct, and the UI shows the price.
- **How:** Levels: fact-sheet lookup, geometry recipe, detector, small VLM, Haiku on crops, Opus tool loop. A gradient-boosted router picks the entry level from question type, file format and witness agreement. Each answer shows its path and cost. A chart shows accuracy against cost for each level and for the cascade.
- **Train on Verda:** Router training is CPU only. The GPU work is the batch run of every level over the full 120,000 questions to get router labels: 4V100 or 1A100, 3-5 h.
- **Effect:** Accuracy - equal to the best level. Verify - the path is part of the proof. Creativity - medium. Cost - directly targets the 25% criterion with a measured number.
- **Demo:** A counter: "120,000 questions answered for $X. Opus alone would cost $Y."
- **Risk:** It is infrastructure, not a feature. It impresses only with real measured numbers.

### 12. Apprentice - Opus teaches a small model on the 14,000 unlabeled drawings
- **Pitch:** The frontier model is a teacher at training time and absent at inference time.
- **How:** Run Opus with zoomed tiles plus the Tally detector on the unlabeled and historic drawings. Keep only the labels where both agree. Retrain the detector on them. Each human correction in the Contact Sheet becomes a new label. Optional: DINO-style self-supervised pretraining of the backbone on all drawing tiles.
- **Train on Verda:** Pseudo-label retrain: 1A100, 3 h. Optional SSL pretrain of ViT-S on about 1M tiles: 2A100, 8-10 h, about $45.
- **Effect:** Accuracy - gains on scans and unseen styles, uncertain on CubiCasa. Verify - none directly. Creativity - high, and it answers the "not obsolete next year" request: better teachers make better students. Cost - inference stays $0, with a one-time Opus cost.
- **Demo:** A chart of student accuracy before and after one night with the teacher.
- **Risk:** Teacher errors go into the student. The SSL payoff in 36 h is unproven. The Opus labelling bill needs a cap.

## How they fit together
- **Core:** 1 + 2 + 7 + 11 cover about 90% of the questions with marks, recipes, a proof UI and a cost number.
- **Second layer:** 4 and 6 add accuracy on room types and the hard tail.
- **Creative headline:** pick one of 3 (GRPO with executor reward), 5 (Rosetta) or 9 (Symbol Twin).
- **Stretch only:** 8 and the SSL part of 12.

## 10 open research questions
1. Were the CubiCasa answers generated from the public SVG annotations, and in which public split are the question drawings? This decides the hold-out set and whether the Tally numbers are honest.
2. What is the current Drawing Desk baseline per source and question type, in exact-match accuracy and in dollars per question? Nothing can be ranked without it.
3. What exact-count accuracy per class does a detector reach on held-out CubiCasa, and at what resolution? Is the failure mostly windows, and is it misses or duplicates?
4. How does Stoa judge: a hidden test set with automatic scoring, or the demo only? How is "inference cost" counted: API dollars, GPU time, or per-drawing precompute? How are free-text answers scored?
5. Do fixed DXF and IFC programs reproduce the reference answers within 2%? Which definitions did the generator use: net or gross, Qto or computed geometry, which layers count as a room, a door or a balcony?
6. How many distinct templates are in the 120,000 questions, and how are the 30 languages spread? Can a rule or embedding parser reach 99% slot accuracy without any LLM?
7. Does the full set have questions on the historic scans (habs, finna, europeana, wikimedia)? If yes, of which types? This decides the value of concepts 8, 9 and 12.
8. How far does a CubiCasa-trained detector transfer to Swiss Dwellings PNGs, IFC-rendered plans and US sheets, before and after adding the DXF-derived labels of concept 5?
9. Does disagreement between witnesses predict errors well enough to route on? What AUROC does it reach, and what fraction of questions needs escalation for a target accuracy?
10. Which small open VLM points best on floor plans, zero-shot and after LoRA, and does it beat the detector on any class? Is GRPO stable within 8 GPU hours on either the pointing task or the query-writing task?

Two side checks are needed before the pitch:
- **Licence:** CubiCasa5K is CC BY-NC as I remember it. Confirm that this is acceptable to Stoa.
- **Stoa's own view:** Ask the Stoa construction engineer what "verified in seconds" means to them. No host conversation is recorded yet in `./context/`.