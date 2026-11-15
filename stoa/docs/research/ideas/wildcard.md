# Wildcard lens: ideas from other fields, and what stays valuable when models improve

Written 2026-11-13, late evening. One agent, one lens. I did not read `prior-research/` or `stoa-drawings/`.

Each figure has a mark:

- MEASURED: I measured it tonight on the local dataset. "By eye" means I opened the drawing and looked.
- SOURCED: the source follows in brackets.
- ESTIMATE: my judgement. Do not use it as a fact.

What I looked at: 18 drawings from 8 sources (3 cubicasa5k, 3 finna, 3 habs, 3 europeana, 3 wikimedia,
1 swiss_dwellings PNG plus its PDF and DXF, 1 ifc_models PNG, 1 ifc_models PDF, 1 opening_design PDF),
about 100 sampled questions from all 5 sources with questions, and the host conversation in `context/stoa-drawings/`.

## Facts I measured that the rest of this file uses

| # | Fact | Mark |
|---|---|---|
| F1 | cubicasa5k has 24 templates, as 12 English-Finnish pairs. The English and the Finnish answer agree on 42,757 of 42,757 pairs. | MEASURED |
| F2 | A cubicasa plan has 3 to 12 of the 12 question kinds. Only 489 of 4,787 plans have all 12. The bedroom question exists for 2,960 plans, the balcony question for 1,462. | MEASURED |
| F3 | Domain rules hold in the cubicasa ground truth. toilets <= bathrooms + WC rooms: 1 violation in 2,204 plans (0.05%). doors >= bedrooms + bathrooms + WC rooms: 1 in 1,391 (0.07%). windows >= bedrooms: 3 in 2,960 (0.10%). toilets >= WC rooms: 26 in 2,332 (1.11%). sinks >= kitchens: 37 in 3,235 (1.14%). saunas <= bathrooms: 46 in 2,193 (2.10%). showers + bathtubs >= bathrooms: 106 in 2,208 (4.80%). | MEASURED |
| F4 | Equalities do not hold. toilets = bathrooms + WC rooms fails on 27.45% of 2,204 plans. Rules must be inequalities. | MEASURED |
| F5 | cubicasa counts have a long tail: up to 92 windows, 43 doors and 30 sinks on one plan. | MEASURED |
| F6 | One swiss floor (`site1130_bldg2273_floor10477`, 34 questions). The DXF has layers WALL, DOOR, WINDOW, ROOM_OUTLINE, ROOM_TEXT, FIXTURE, ANNOTATION, UNIT_OUTLINE and `$INSUNITS` 6 (metres). 58 ARC entities on DOOR = ground truth 58 doors. 7 UNIT_OUTLINE polylines = ground truth 7 apartments. 69 WINDOW polylines = 3 x ground truth 23 windows. | MEASURED |
| F7 | Same floor, three independent witnesses of one area. DXF polygon of room 0.14: 3.570 m2. A closed vector path in the PDF, at 1:100 on the page: within 2% of 3.57 m2. Ground truth: 3.57 m2. Room 0.21: DXF 5.746, PDF path within 2%, ground truth 5.75. | MEASURED |
| F8 | Same floor, three independent witnesses of the scale. Title block text "1:100 (A3)" on an A3 page gives 28.35 pt per metre. The scale bar labels "0" and "5" are 141.7 pt apart, so 28.34 pt per metre. The DXF is in metres. | MEASURED |
| F9 | Same floor. The sum of all 45 closed ROOM_OUTLINE polygons is 359.54 m2. The ground truth net floor area is 357.29 m2. The 0.6% gap is inside the tolerance, but it shows that "which rooms count" is a semantic choice, not geometry. | MEASURED |
| F10 | Of 12 historic scans I opened (finna, habs, europeana, wikimedia, 3 each): 9 have a graphic scale bar. 11 have some scale witness (bar, ratio text or dimension strings). 9 show more than one view on the sheet. At least 4 use feet or a historic unit ("Schuch"). About 6 contain a floor plan to which a cubicasa-style count question applies. 1 is a photo of a framed drawing behind glass. 1 is a photo of a metal site sign. | MEASURED by eye, n = 12 |
| F11 | cubicasa `high_quality-3653.png` prints the Finnish apartment formula "4H+K+S 101.5". The plan shows 3 MH, 1 OH, 1 K and 1 LH (sauna room). The text and the geometry describe the same apartment. | MEASURED by eye |
| F12 | ifc_models `resbim-367_plan.png` (7572 x 4189 px) has dimension chains in millimetres and grid bubbles. It has no scale bar and no fixtures. The top chain appears to sum to the total 9280. Digits overlap, so this is not certain. | MEASURED by eye |
| F13 | opening_design sheet A-801 is a vector PDF with 9,483 characters of text and 8,950 paths. The answers are rows of a door schedule and a finish schedule. | MEASURED |
| F14 | Public set: 127,044 questions on 5,939 drawings, so 21.4 questions per drawing. | SOURCED (`stoa/docs/BRIEF.md`) |
| F15 | Claude API prices per million tokens, input / output: Haiku 5.5 $0.10 / $0.50, Sonnet 5.5 $2 / $10, Opus 5.5 $4 / $20. The Batch API is at 50%. | SOURCED (claude-api skill model table, cached 2026-11-03) |
| F16 | Host: evaluation is "one document at a time, then a series of questions". "Around 10 cents for both" ingestion and query is the target zone. Tricky drawings have the same file extensions but other structure. | SOURCED (`context/stoa-drawings/2026-11-13-2308-38-conversation.md`) |

I did not measure any model accuracy tonight. Every accuracy number below is an ESTIMATE.

---

## 1. The lens in one paragraph

A drawing is a redundant document. It states the same fact several times: a scale as text, as a bar and as
dimension strings; a room as a label, as a closed outline and as an entry in a schedule; a door as an arc, as a gap in
a wall and as a link between two rooms. Mature fields that read redundant documents do not trust one reader. Chip
verification compares the layout with the schematic. Accountants post each amount twice and reconcile. Surveyors fit a
map to control points and report the residual. Optical music recognition plays the score back. Compilers refuse a
program that does not type-check. This lens says: build the answer as a derivation over a typed model of the drawing,
derive each quantity by two independent routes, check the model against the rules of buildings, and report agreement
as the confidence. The reader of pixels is a replaceable part. The model of the drawing, the rule deck, the
reconciliation ledger, the test harness and the corrections of users are the durable assets. A better frontier model
next year makes the reader better and leaves the rest in place. The strongest argument against the lens: a verifier
does not read anything. If the reader cannot find the 7 toilets on a 660 px scan, no ledger finds them. Counts must be
exact, and the host said a 90% solution beats a 70% creative one. Thirty-three hours spent on checking machinery are
hours not spent on the reader, and a team with a plain, strong reader and no checks can score higher on accuracy.

How the public score misleads, seen from this lens:

- 67% of public questions are cubicasa counts from 24 templates. A mode guess scores 55.3% (lead's measurement). A system can gain 20 points there and learn nothing that transfers.
- F2 suggests that the generator skipped questions on some plans. ESTIMATE: it skipped plans where the annotation was ambiguous. If so, the public questions are the easy cases of cubicasa.
- F6 shows that the swiss DXF answers most swiss questions by counting entities per layer. This is a property of Stoa's renderer, not of drawings. The host said the tricky drawings keep the extension and change the structure (F16).
- The public CubiCasa5K SVG annotations are the labels behind the cubicasa answers. Training on them is fair. Looking an answer up by file name is a leak.
- F10 suggests that half of the historic scans cannot take a cubicasa-style question. The hidden questions on them must be of other kinds.

---

## 2. Concepts

### Concept 1 - Drawing Compiler: one typed model, one query language (compilers, databases)

**Pitch.** Compile each drawing once into a typed fact graph, compile each question into a typed query, and run the query without a model.

**Mechanism.**

1. A front end per format reads the file: IFC (`ifcopenshell`), DXF and DWG (`ezdxf`, DWG through a converter), vector PDF (`pymupdf` paths and words), raster (concepts 4 and 5, or a vision model).
2. Each front end emits the same intermediate representation (IR): entities with a class (room, wall, door, window, fixture, text, dimension, schedule row, frame), a geometry in sheet coordinates, a frame id, attributes, a provenance (source object, bounding box, reader) and a confidence.
3. Quantities carry a unit type: `px`, `pt`, `m`, `m2`, `ft-in`, `count`. A scale is a value of type `pt -> m`, per frame.
4. A question compiles into a small plan: `SELECT class WHERE label ~ X AND inside(room N) -> COUNT | SUM(area) | LOOKUP(column)`. A cheap model writes the plan as JSON against a fixed schema. A plan cache keyed by the normalised question removes the call for repeats.
5. The executor type-checks the plan. `SUM(area)` in `m2` needs a `pt -> m` scale in that frame. No scale means a type error. The type error is the abstention: "I need a scale for frame 2".
6. Materialised views: after ingestion, the system computes every standard aggregate once (count per class, area per room, per label, per apartment, per floor). Most questions become a lookup.
7. The output is the value, the plan, the ids of the entities that the plan touched, and the type derivation.

- **Once per drawing:** the front end, the IR, the views. **Per question:** one plan compile (or a cache hit) and one execution in microseconds.

**Needs.** No training. A schema, four front ends, about 15 plan operators. API calls: one small call per new question form.

**Effect on the criteria.**
- Accuracy: neutral for the reading step. Positive for multi-step questions ("tile area of all WCs" is a spatial join and a sum).
- Verification: strong. The plan is the reasoning, and it is exact, not a narration after the fact.
- Creativity: medium. "LLM plans, tools execute" is common this weekend. The unit type system as the source of "I do not know" is less common.
- Cost: strong. It matches the host's flow (F16): one document, then many questions.

**Hidden set.** New templates and languages only touch the plan compiler, which is the part a language model does well. A new format needs a new front end, not a new system. A question outside the operator set fails to compile, and the system says which operator is missing. The risk is a schema that cannot express a free-text question such as "what is the space breakdown per floor".

**Cost per question.** ESTIMATE: $0.0002 with Haiku 5.5 (1,500 input and 150 output tokens at F15 prices), or zero on a cache hit. Ingestion of a vector file: CPU only.

**Evidence view.** The plan as three or four boxes (select, filter, aggregate), each with its entity count. Click a box and the entities light up on the drawing.

**Fits in 33 hours.** The IR, the IFC, DXF and vector-PDF front ends, 10 operators, the plan compiler, the cache. **Does not fit:** a complete schema for MEP, structure and schedules of every kind.

**First measurement that can kill it.** Paraphrase the public templates and translate them into 10 languages, and add 50 hand-written harder questions. If under 90% compile to a plan that type-checks and returns the same answer, replace the DSL with a code-writing agent over the IR.

**Main risk.** The schema becomes the project. Keep it at 10 classes on Saturday.

---

### Concept 2 - Double-Entry Takeoff: a reconciliation ledger and an answer certificate (audit, accounting, proof assistants)

**Pitch.** Post each quantity to a ledger from two independent routes, and call an answer verified only when the routes balance.

**Mechanism.**

1. For each fact, the system lists the witnesses that can state it. Scale: ratio text, scale bar, dimension strings, sheet size, door width prior. Room area: polygon area, printed area text, schedule row, IfcSpace quantity. Door count: door arcs, gaps in walls, edges in the room adjacency graph, rows in a door schedule.
2. Each witness posts its value with its reader and its location on the sheet.
3. A reconciler compares witnesses with the scoring tolerance: exact for counts, 2% for measures.
4. The confidence is a function of the number of independent witnesses that agree. It is not a model's self-report. The team calibrates it once on public data: "two witnesses agree" maps to an observed precision.
5. An imbalance is not hidden. It becomes the "unknown" entry: "the scale bar says 1:100, the dimension string says 1:96".
6. The answer ships with a certificate: a short JSON derivation whose steps are observations (entity, box, witness) and rule applications (count, sum, convert). A separate checker of about 200 lines validates the certificate. The solver can be wrong. The checker is small enough to read.

- **Once per drawing:** all witnesses and the reconciliation. **Per question:** look up the balance of the facts that the plan used.

**Needs.** No training. One labelled calibration pass over public data. The witnesses come from the front ends of concept 1.

**Effect on the criteria.**
- Accuracy: indirect. It selects among readers and catches scale errors, which are the errors that break every area answer on a sheet at once.
- Verification: very strong. It gives the three things the host asked for: deterministic or not, a confidence, and an explicit unknown with the reason.
- Creativity: high. I expect few teams to show a balance sheet for a floor plan.
- Cost: zero at inference. Witnesses are computed during ingestion.

**Hidden set.** This is the concept that transfers best, because redundancy is a property of drawings, not of the public templates. F7 and F8 show three agreeing witnesses on a Stoa-rendered sheet. F10 shows that 11 of 12 historic scans carry a scale witness. When a tricky drawing has one witness only, the system still answers, with a lower confidence and the note "single witness".

**Cost per question.** Zero beyond concept 1.

**Evidence view.** A small ledger next to the drawing: one row per fact, one column per witness, a green tick where they balance, the gap where they do not. Each cell links to its place on the sheet.

**Fits in 33 hours.** Scale witnesses (text, bar, dimensions), two count witnesses for doors and rooms, the certificate, the checker. **Does not fit:** witnesses for every quantity type.

**First measurement that can kill it.** On 300 public questions with two available witnesses: precision when the witnesses agree against precision overall. If agreement does not lift precision by at least 5 points, the witnesses are not independent and the ledger is decoration.

**Main risk.** Correlated witnesses. Two readers that share one OCR error agree and are both wrong.

---

### Concept 3 - Design Rule Check and Layout Versus Schematic for buildings (chip verification, constraint puzzles)

**Pitch.** Run a rule deck over the extracted plan as a chip foundry runs one over a layout, and compare the geometry with what the text says.

**Mechanism.**

1. Design rule check (DRC). A deck of about 40 rules over the IR. Hard rules: each room outline is closed; each door lies on a wall; a door links at most two spaces; a fixture lies inside a room. Soft rules with a measured rate: toilets <= bathrooms + WC rooms (99.95% in F3); doors >= bedrooms + bathrooms + WC rooms (99.93%); windows >= bedrooms (99.90%); each room is reachable from an entrance; a door is 0.6 m to 1.3 m wide at the fitted scale.
2. Layout versus schematic (LVS). The "schematic" is every text on the sheet that states a fact: the apartment formula "4H+K+S 101.5" (F11), room schedules, door schedules (F13), printed areas, the legend. The "layout" is the geometry. The system extracts both and compares them.
3. A violation marks a region. It lowers the confidence of answers that depend on the region.
4. From check to repair. A small constraint solver (CP-SAT) picks the set of uncertain detections that maximises detector score under the hard rules. Example: a door candidate at 0.5 is kept when its room has no other door.
5. Only when a violation remains, a vision model looks at the crop of that region. This is the only place where an expensive call can happen, and the trigger is visible.

- **Once per drawing:** the DRC, the LVS, the repair. **Per question:** nothing.

**Needs.** No training. The priors come from public answers (F3) and from public CubiCasa5K annotations. Rule writing is fast with agents. One label-free use: run the deck on the 6,570 historic scans. The violation rate per source is a quality metric for sources with no questions.

**Effect on the criteria.**
- Accuracy: ESTIMATE of 1 to 4 points on counts through repair, more on drawings where the reader is weak. This is the weakest guess in the file.
- Verification: strong. "Room 0.36 has no door" is a sentence a site engineer understands.
- Creativity: high. DRC and LVS are a new frame for this jury, and Stoa's product finds mistakes in project data ("person X cannot build the wall if the floor does not exist"). A rule deck for drawings is the same idea one level down.
- Cost: zero at inference, except rare escalations.

**Hidden set.** The hard rules are geometry and hold for any building. The soft rules are priors of Finnish and Swiss dwellings. On a data centre, a hospital or a 1700s fortress (F10) they are wrong. Each soft rule therefore needs a scope (dwelling plan only) and must only lower confidence, never change an answer alone. F4 is the warning: an equality that looks obvious fails on 27% of plans.

**Cost per question.** Zero. ESTIMATE: one escalation crop costs about $0.01 with Sonnet 5.5, on under 10% of drawings.

**Evidence view.** DRC markers on the drawing, as in a layout editor: a red box with the rule name. A list "2 rules failed, 38 passed".

**Fits in 33 hours.** 15 to 20 rules, the apartment-formula and schedule LVS, the label-free violation report. **Does not fit:** a tuned solver for all classes.

**First measurement that can kill it.** Take reader output with known ground truth. Does a DRC violation predict a wrong answer? If the AUC is under 0.65, keep the deck for the evidence view only and drop repair.

**Main risk.** Dwelling priors applied to non-dwellings produce confident nonsense.

---

### Concept 4 - Georeference the sheet: frames, control points and a legend (GIS, map digitisation)

**Pitch.** Treat a sheet as an atlas page: split it into map frames, give each frame its own coordinate system from control points, and read symbols with the sheet's own legend.

**Mechanism.**

1. Frame segmentation. A sheet holds several views (9 of 12 historic scans in F10): plans, elevations, sections, details, a schedule, a legend, a title block. A detector or one vision call returns the frames with a type each.
2. Control points. For each frame the system collects scale evidence: ticks of a scale bar, pairs of dimension-line ends with their number, grid lines, the ratio text near the frame title, the sheet format. HABS sheet 14 of 40 prints a different scale bar under each view group (by eye).
3. Fit. A least-squares fit gives the scale and its residual, as in georeferencing a scanned map. The residual in percent is shown. A residual above 2% blocks area answers, because the scoring tolerance is 2%.
4. Units. The fit keeps the native unit (m, mm, ft-in, "Schuch"). A historic unit with no known length gives an answer in the native unit and an explicit "I cannot convert Schuch to metres".
5. Legend-driven symbols. Where a legend exists (the swiss sheet has one with WC, Lavabo, Badewanne, Dusche, Küchenzeile, Waschmaschine, Türe, Fenster), the system crops each legend symbol and matches it in the frame. The sheet teaches its own symbols. No training on that style is needed.
6. Output: GeoJSON per frame plus a world file. Area, length, point-in-polygon and adjacency are standard GIS operations.

- **Once per drawing:** frames, fits, legend, GeoJSON. **Per question:** the plan runs on the right frame.

**Needs.** OCR for numbers, a line detector for bars and dimension lines, a frame detector. One vision call per sheet is the fast path for frames. No labels exist for frames: 100 hand-labelled sheets take one person about 2 hours (ESTIMATE).

**Effect on the criteria.**
- Accuracy: decisive for areas and lengths on any raster. It is also needed for counts: "windows on this floor plan" on a sheet with two plans and two elevations has no answer before frames exist.
- Verification: strong. The scale bar with fitted ticks and the residual is a check a person does in 2 seconds.
- Creativity: medium to high. Per-frame coordinate systems and the legend as a one-shot teacher are borrowed, and I think new here.
- Cost: low. CPU plus one optional vision call per sheet.

**Hidden set.** This concept exists for the hidden set. The public questions never need frames, because cubicasa and swiss sheets hold one plan. The 6,570 scans with no public questions need them (F10). The legend method adapts to unseen symbol styles. It does nothing on sheets with no legend, which is most historic scans (ESTIMATE from the 12 I saw: 0 of 12 had a symbol legend).

**Cost per question.** Zero. Per sheet, ESTIMATE: $0.01 to $0.03 for one Sonnet 5.5 call on the full sheet.

**Evidence view.** Frames as outlined cards on the sheet with type and scale ("Plan, 1:100, residual 0.4%, 3 control points"). The control points are visible dots. A person drags one to correct the fit.

**Fits in 33 hours.** Frames through one vision call, scale from ratio text and scale bar, the residual, the two-click manual calibration, abstention with the reason. **Does not fit:** robust dimension-string parsing on hand lettering, paper distortion models, historic unit tables.

**First measurement that can kill it.** On 50 historic scans: the share where a frame list and a scale fit come out right, checked by a person. Under 50%: keep only ratio text and the manual two-click calibration.

**Main risk.** Hand-lettered numbers. OCR on 1909 ink lettering (finna) is weak, and a wrong digit gives a confident wrong scale. The ledger of concept 2 is the guard.

---

### Concept 5 - Count like a pathologist: point maps, not boxes (medical image counting) - UNUSUAL

**Pitch.** Count fixtures and openings as a cell-counting model counts cells: predict one point per object, and let the count be the number of points.

**Mechanism.**

1. A small fully convolutional network takes a plan tile and returns one heat map per class: door leaf, window, toilet bowl, sink, shower, bathtub, sauna stove, stair.
2. Peaks of the heat map are the objects. The count is the number of peaks above a threshold. Peaks near the threshold form the "uncertain" list.
3. Training labels are points, the cheapest label that exists. Sources: the public CubiCasa5K SVG annotations (split by plan id, and reported as in-distribution), the swiss DXF layers (F6: perfect labels for 1,040 floors at no cost), renders of IFC models.
4. Style randomisation makes the model survive unseen styles: line weight, blur, paper texture, blueprint inversion, rotation by any angle, hand-drawn jitter, JPEG noise, scale from 0.3x to 3x.
5. Exemplar counting covers unseen classes: the legend (concept 4), a person or a vision model gives 1 to 3 example crops, and a class-agnostic matcher counts the rest (the "count things like this" family of models).
6. The vision model becomes a second witness for the ledger, not the counter.

- **Once per drawing:** one forward pass, 8 point sets. **Per question:** a lookup.

**Needs.** Labels: free (above). Training: ESTIMATE 3 to 6 A100 hours, about $7 to $15 at $2.4 per hour, plus 4 to 8 person-hours for data plumbing. Inference: milliseconds on one GPU, seconds on CPU.

**Effect on the criteria.**
- Accuracy: ESTIMATE high on cubicasa-like scans and unknown elsewhere. Exact counts punish every miss: at a recall of 0.97 per object, a plan with 20 windows is right about 54% of the time (0.97^20, arithmetic). F5 shows plans with 92 windows.
- Verification: strong and natural. The evidence is the dots.
- Creativity: medium. A trained detector is expected. Point supervision with exemplar fallback and a counterfactual test (concept 9) is less so.
- Cost: near zero. This is the cost floor asset.

**Hidden set.** It is a model trained on two styles. It will degrade on a third. Style randomisation helps for clean CAD output and helps less for a 1926 hand drawing. It answers nothing on elevations, schedules or sites. Its honest scope is "modern floor plans, raster or rasterised".

**Why it can still win.** Small symbols on low-resolution scans are where general vision models miscount, and exactness is the scoring rule. A counter that costs nothing per question also wins the cost criterion outright, and a model trained on Verda is a plus for the track sponsor.

**Cost per question.** ESTIMATE: under $0.0001.

**Evidence view.** Numbered dots per class, solid for sure and hollow for uncertain. Keyboard: next dot, reject, add.

**Fits in 33 hours.** A U-Net-size model for 6 classes with labels from CubiCasa5K and swiss DXF. **Does not fit:** exemplar counting as a trained component (use an off-the-shelf matcher or cut it), room polygons from raster.

**First measurement that can kill it.** Before any training: the exact-count accuracy of one Sonnet 5.5 or Opus 5.5 call on 200 stratified cubicasa questions. If the vision model is above 90% exact, do not train. If it is under 75%, train tonight.

**Main risk.** It raises the public score on the 67% and teaches nothing about the hidden 60%. It is the concept most exposed to the trap this file warns about.

---

### Concept 6 - The frontier model writes the extractor, a test suite accepts it (test-driven program synthesis)

**Pitch.** Use the frontier model as a compiler author that works offline and per drawing family, never as the runtime that answers a question.

**Mechanism.**

1. A fingerprint describes a file: extension, producer metadata, layer names, text statistics, path statistics, colour histogram. F6 and F13 show how distinctive it is.
2. For each fingerprint family, a coding agent writes a small extractor: a Python function from the file to the IR.
3. Acceptance is test-driven. The extractor must pass the public questions of that family, the DRC of concept 3 and the ledger balance of concept 2.
4. Accepted extractors enter a library. At inference a router picks by fingerprint. Then the DRC and the ledger run on the new drawing.
5. If they fail, or the fingerprint is new, the system synthesises online: the model sees a render and a structural dump of the file, writes or patches an extractor, and iterates against the DRC and the ledger. Ground truth is not needed for this loop. The rules are the oracle.
6. The cost of the online loop is paid once per drawing and is shown.

- **Once per family (offline):** synthesis. **Once per drawing:** routing and extraction. **Per question:** nothing.

**Needs.** Agent time offline: the team has it. No GPU. Online synthesis, ESTIMATE: $0.05 to $0.30 per new drawing family with Sonnet 5.5 or Opus 5.5, so $0.002 to $0.015 per question at 21.4 questions per drawing (F14).

**Effect on the criteria.**
- Accuracy: strong on structured files (IFC, DXF, DWG, vector PDF). None on raster.
- Verification: strong. The extractor is code that a person can read, and every run is deterministic.
- Creativity: high. It answers "what does next year's model not make obsolete" directly: a better model writes better extractors, and the acceptance suite and the library stay.
- Cost: the lowest possible at inference for known families.

**Hidden set.** A tricky drawing with a known extension and a new structure (F16) is exactly a fingerprint miss. The system notices the miss, which a hand-written parser does not. Whether online synthesis then succeeds in under a minute is unknown.

**Why it can still win.** It is Henrik's reinforcement-learning leaning in a form that fits 33 hours: search over programs with an automatic reward, with no gradient step.

**Cost per question.** Zero for a known family. See above for a new one.

**Evidence view.** "Read with extractor `swiss-dxf-v3`, accepted on 412 tests" with a link to the code, or "new structure, extractor written now, 9 of 9 rules pass, cost $0.11".

**Fits in 33 hours.** The offline loop is what the team's agents do anyway. Add the fingerprint router and the acceptance suite. **Does not fit:** reliable online synthesis with a time limit. Show it once in the demo on a prepared tricky file, and say that it is a prototype.

**First measurement that can kill it.** Rename all layers of 20 swiss DXF files to `0`, and rasterise nothing. Does online synthesis recover the door and room counts from geometry alone within 3 iterations? If under half succeed, keep the offline library and cut the online loop.

**Main risk.** Extractors that pass public tests by fitting Stoa's renderer (count ARC on layer DOOR) and carry no knowledge of drawings.

---

### Concept 7 - Read it, redraw it, subtract: analysis by synthesis (optical music recognition, robot mapping) - UNUSUAL

**Pitch.** Redraw the drawing from the machine's own reading, lay it over the original, and treat the ink that the redraw does not explain as "what I do not know".

**Mechanism.**

1. Optical music recognition checks a result by engraving the recognised score again and comparing it with the scan. Do the same: render the IR in a clean, canonical style at the fitted scale.
2. Register the render on the original. Compute two residuals: ink in the original that the render does not explain, and render lines with no ink under them.
3. The explained-ink ratio per frame is a confidence that needs no label and no model self-report.
4. A cluster of unexplained ink is an unknown region. The answer says: "I counted 7 toilets. I did not read the area at the lower left."
5. Robot mapping adds loop closure: room outlines must close, and views of the same building must agree. A plan and an elevation on one sheet give two counts of the windows on one facade.
6. The redraw is also a model. Extrude the walls by storey height and the plan sits in the same 3D viewer as an IFC model.

- **Once per drawing:** render, register, residual. **Per question:** nothing.

**Needs.** A renderer for the IR (the evidence view needs one anyway), a registration step (trivial for vector files, a similarity transform for scans), a threshold. No training.

**Effect on the criteria.**
- Accuracy: none directly. It prevents confident answers on half-read sheets.
- Verification: the strongest idea in this file. A slider between the original and the machine's reading shows in 2 seconds what the machine saw.
- Creativity: high. It also matches the host's "could be a good idea" on building a model from the drawing, and the stacked 3D plans in Stoa's own product photo.
- Cost: CPU only.

**Hidden set.** The residual is the one signal that reacts to anything unexpected, including content the team never thought of. It does not need to know what the unexpected thing is. On a hand drawing, hatching and lettering produce a lot of unexplained ink, so the threshold needs a per-style baseline.

**Why it can still win.** The host said "the I don't knows are super important" and "tell the user which parts you don't know". Most teams will print a confidence number. This shows the unknown on the sheet.

**Cost per question.** Zero.

**Evidence view.** Three layers with a slider: original, redraw, residual heat map. Unknown regions have a dashed outline and a one-line reason.

**Fits in 33 hours.** The overlay for vector front ends and for raster entities as boxes and polygons. A coarse residual map. **Does not fit:** tuned residual statistics per style, the 3D extrusion (one prepared example at most).

**First measurement that can kill it.** Remove 10% of the entities from the IR of 50 swiss floors on purpose. Does the residual map find the removed entities at a recall above 0.8? If not, the residual is noise.

**Main risk.** Text, hatching and furniture are ink that the IR does not model. The residual then flags the whole sheet.

---

### Concept 8 - The ten-second audit as a game, and the correction flywheel (game design, active learning)

**Pitch.** Design the evidence view as a fast game with one clear action per item, and keep each correction as a label and as a regression test.

**Mechanism.**

1. A count plays back as a tally: pins appear room by room with a running number. A person watches 58 doors in about 5 seconds, and the eye catches a pin on a wardrobe.
2. One key rejects a pin. One click adds one. The answer updates at once and the answer card changes from "machine" to "machine + you".
3. Active learning orders the work: the 3 least certain pins come first. "55 of 58 doors are sure. Check these 3."
4. Missing scale is a two-click task: click both ends of a known dimension and type the number. The host proposed this (F16 conversation: "give us a scale or calibrate").
5. Each correction is stored three ways: as a point label for the counter of concept 5, as a rule exception for concept 3, and as a test case `{drawing, question, corrected answer}` for the harness of concept 9.
6. Game design rule: the cost of checking must be lower than the cost of doubting. Show the count of items checked and the time, so the engineer learns to trust the fast path.

- **Once per drawing:** nothing. **Per question:** nothing. **Per correction:** one stored record.

**Needs.** A web UI from the repository starter. No training before the deadline. The flywheel is a claim for the pitch, with a working loop for one class.

**Effect on the criteria.**
- Accuracy: none on an automatic hidden set. Large if Stoa's evaluators interact with the UI, which the host allowed for 3D models ("definitely with your UI").
- Verification: this is the criterion it targets, 25% of the score.
- Creativity: medium to high.
- Cost: a person's 5 seconds replaces a second frontier-model pass.

**Hidden set.** It does not depend on the content. It works on any drawing where the system produced located evidence. It gives nothing when the answer is a free text with no location.

**Cost per question.** Zero model cost.

**Evidence view.** It is the evidence view.

**Fits in 33 hours.** Pins, tally playback, reject and add, live recount, two-click calibration, storage of corrections. **Does not fit:** retraining from corrections during the event. Do one manual retrain as proof, or state it as the next step.

**First measurement that can kill it.** Give 3 people outside the team 10 answers, 3 of them wrong. Measure the time and the share of wrong answers they catch. If they catch under 2 of 3 or need over 20 seconds per answer, the view is not doing its job.

**Main risk.** The host put the UI at about 5% in one statement. Polishing the game while the reader is at 70% loses.

---

### Concept 9 - Metamorphic and counterfactual tests: a hidden-set simulator with no labels (software testing)

**Pitch.** Test properties that must hold on any drawing, so that the 6,570 scans with no questions and a generator of tricky files become an evaluation set.

**Mechanism.**

1. Metamorphic relations need no ground truth. Rotate the sheet by 90 degrees: every count stays. Scale the image by 0.5x and 2x: counts stay, and areas stay when the scale bar scales with it. Ask in another language: the answer stays (F1 shows the ground truth has this property on 42,757 pairs). Paste two plans on one sheet: counts add.
2. Counterfactual relations test causes. Erase one toilet symbol: the count must drop by exactly 1. Crop the scale bar and the ratio text: the system must change to "I need a scale". Remove a wall segment: two rooms must merge, and the DRC must report an open room.
3. A tricky-file generator makes hidden-set stand-ins from public files. Print a vector PDF to an image-only PDF. Rename or merge DXF layers. Strip IfcSpace from an IFC file. Rotate a page. Put two sheets in one PDF. Convert metres to feet and inches. Degrade a render with scan noise. The swiss DXF gives the ground truth for every variant.
4. A leak ladder reports each score five times: with all aids, without sibling formats, without the file name, rasterised only, and with paraphrased questions. The drop between steps is the amount of the score that does not transfer.
5. The harness runs in CI on each change and prints one table: accuracy, invariance rate, abstention correctness, cost per question.

- **Once, offline:** the transforms and the generator. **Per change:** one run.

**Needs.** Image and file transforms, an inpainting step for symbol removal (a white rectangle is enough on clean plans). No labels. No GPU beyond the system under test.

**Effect on the criteria.**
- Accuracy: indirect and large. It is the only way to see a hidden-set failure before Sunday.
- Verification: it produces evidence for the pitch ("answers are stable under rotation on 98% of sheets").
- Creativity: high. I do not expect another team to show counterfactual tests on drawings.
- Cost: none at inference.

**Hidden set.** It is the instrument for the hidden set. Its limit: it measures consistency, not truth. A system that always answers 0 passes every invariance test. It must run next to the labelled evaluation, never alone.

**Why it stays valuable.** An evaluation asset survives every model change. Next year's model runs through the same harness on day one. This is also Henrik's first request: an evaluation environment the team can trust.

**Cost per question.** Zero at inference. A full harness run costs what the system costs on a few thousand variants.

**Evidence view.** For the jury, one slide: the leak ladder as five bars. For the user, a small badge per answer: "stable under rotation and scale".

**Fits in 33 hours.** Rotation, rescale, language swap, scale-bar crop, PDF rasterisation, layer renaming, the leak ladder. **Does not fit:** realistic hand-drawn re-rendering.

**First measurement that can kill it.** Run rotation and 0.5x rescale on 100 plans with the first working reader. If over 95% of answers are stable and the labelled accuracy is far lower, invariance does not track error here, and the harness is a weaker instrument than hoped.

**Main risk.** The team optimises invariance because it is easy to measure.

---

## 3. The system I would build from this lens

Name for the pitch: **Ledger**. One sentence: "Every answer is a derivation over a compiled model of the drawing, posted twice and reconciled."

### Design

The system has one spine and three replaceable ends. The spine is the IR, the plan executor, the ledger and the
rule deck. The ends are the readers (one per format), the question compiler, and the evidence view. A drawing is
compiled once. A question costs one small model call or nothing. A frontier vision model appears in two places only:
as one of the raster readers during ingestion, and as an adjudicator on a crop when the rule deck or the ledger
reports a conflict. Both uses are counted and shown.

```
                         INGEST (once per drawing, cost shown)
 file --> fingerprint --> reader ------------------------------+
            |               IFC      (ifcopenshell)            |
            |               DXF/DWG  (ezdxf)                   |
            |               vector PDF (paths, words, tables)  |
            |               raster   (frames -> point counter, |
            |                         OCR, vision model)       |
            v                                                  v
      new structure?                              +-------------------------+
      -> say so, lower confidence                 |  IR: typed fact graph   |
                                                  |  entities, frames,      |
                                                  |  units, provenance      |
                                                  +-----------+-------------+
                                                              |
                 +--------------------+-----------------------+--------------------+
                 v                    v                                            v
        scale witnesses        rule deck (DRC, LVS)                      materialised views
        text | bar | dims      40 rules, hard and soft                   counts, areas per room,
        -> fit + residual      -> violations per region                  label, apartment, floor
                 |                    |                                            |
                 +---------> LEDGER: witnesses per fact, balance, confidence <-----+
                                      |
                                      |  conflict? -> vision model on the crop (rare, counted)
                                      v
                         QUERY (per question)
 question --> plan compiler (Haiku 5.5 or cache) --> typed plan --> executor
                                                         |              |
                                 type error: "I need a scale"           v
                                 missing operator: "I cannot           answer + certificate
                                 compute this yet"                      (value, unit, plan,
                                                                        entities, witnesses,
                                                                        confidence, unknowns)
                                                                              |
                                                                              v
                         EVIDENCE VIEW: pins and polygons on the sheet, the plan,
                         the ledger rows, the redraw overlay, reject and add, two-click scale

                         OFFLINE: metamorphic and counterfactual harness, tricky-file
                         generator, leak ladder, extractor synthesis against tests
```

Why this is one design and not a list:

- Concept 1 is the spine. Without one IR, nothing else has a place to attach.
- Concept 4 gives the raster reader frames and a scale. Without it, the IR of a scan has no units and the hidden scans have no answers.
- Concept 2 turns the several readers into a confidence. It is the reason to have more than one reader.
- Concept 3 is the test oracle for readers on drawings with no ground truth. It is also what the adjudicator trigger uses.
- Concept 9 is how the team learns whether any of it transfers.
- Concepts 5, 6, 7 and 8 are readers and views on the spine. Each can be cut without breaking the rest.

Target cost, ESTIMATE: a vector file ingests on CPU for under $0.001. A raster sheet with one Sonnet 5.5 extraction
call (about 5,000 input and 3,000 output tokens) costs about $0.04, so about $0.002 per question at 21.4 questions
per drawing. A question costs $0.0002 or zero. The total is 20 to 100 times under the host's "10 cents for both".

### Order of work

Hours count from now. Four people. The split is by disjoint files.

| Hours | Work | Why at this point |
|---|---|---|
| 0 - 2 | Measurements 1, 2 and 9 of section 5. Freeze the IR schema at 10 classes and the certificate format. | They decide whether to train and what the raster reader is. |
| 0 - 6 | IFC, DXF and vector-PDF readers into the IR. Materialised views. | The host said the vector flow is the easy start. It covers swiss, ifc_models, ifc_bench and opening_design. |
| 2 - 8 | Plan compiler, executor, unit types, type-error abstention, plan cache. | Every later part needs answers to flow end to end. |
| 2 - 10 | Harness: labelled evaluation per source and template, rotation, rescale, language swap, PDF rasterisation, layer renaming, leak ladder. | The instrument must exist before the readers improve. |
| 6 - 16 | Raster reader v0: frames by one vision call, OCR, scale witnesses (ratio text, scale bar), fit with residual, vision-model extraction into the IR. | The hidden scans. |
| 8 - 20 | Only if measurement 1 says so: train the point counter on Verda. Labels from CubiCasa5K by plan-id split and from swiss DXF. | It runs in the background on a GPU. |
| 12 - 22 | Ledger with scale and count witnesses, 15 to 20 rules, adjudicator on conflict, calibration of confidence on public data. | It needs two readers to exist. |
| 14 - 26 | Evidence view: pins, polygons, plan boxes, ledger rows, reject and add, two-click scale. Redraw overlay for vector files. | 25% of the score. |
| Saturday lunch | Read Stoa's hint on the hidden questions. Add plan operators. Re-rank the remaining work. | The host promised a direction. |
| 26 - 31 | Rehearsal on the tricky-file set. Fix the worst source. Freeze. | No new parts after hour 28. |
| 31 - 33 | Pitch numbers from the harness: leak ladder, cost table, one counterfactual demo. | |

### What I would cut first, in this order

1. Online extractor synthesis (concept 6). Keep the offline library and one prepared demo.
2. The constraint solver repair in concept 3. Keep the rule deck as a check.
3. The residual heat map of concept 7. Keep the plain overlay with a slider.
4. Exemplar counting in concept 5.
5. Historic units and dimension-string OCR in concept 4. Abstain with the reason instead.
6. Tally playback and active ordering in concept 8. Keep pins, reject and add.
7. The trained counter itself, if the vision reader passes measurement 1.

What I would not cut: the IR and the plan executor, the vector readers, the scale witnesses with type-error
abstention, the labelled evaluation with the leak ladder, and pins on the sheet.

---

## 4. Where this lens is wrong

- **When the reader is the bottleneck.** If the hidden set is mostly counts on low-resolution scans, the score equals the recall of the reader raised to the number of objects. A team that puts 33 hours into one strong detector and a plain UI beats a team with a ledger around a 75% reader. This is the most likely way the lens loses.
- **When an abstention scores the same as a wrong answer.** The ledger, the type errors and the residual map produce honest "I do not know" answers. If Stoa's script marks them as wrong, they add to the verification score only. Then a best guess with a low confidence must always accompany the abstention. Build it that way in any case.
- **When the questions are free text.** ifc_bench answers are long structured texts ("Total Doors: 198, U100: 19 doors (9.6%)"). A code-writing agent with `ifcopenshell` and no fixed schema answers these better than a 15-operator DSL. A direct model-with-tools approach wins on that source.
- **When the drawing is not a dwelling.** The soft rules come from Finnish apartments and Swiss housing. Stoa's customers build data centres. A rule deck that marks a server hall as "room with no window" hurts trust. Another approach with no priors is safer there.
- **When redundancy is absent.** A cubicasa scan has no scale bar, no ratio text and often no dimension. One witness means no ledger. For 67% of the public questions the ledger says "single witness" and adds nothing.
- **When the witnesses are not independent.** A vision model and an OCR engine that fail on the same blurred digit agree with each other. Agreement then gives false confidence, which is worse than none.
- **When time runs out.** This design has many parts. Each part is small, but integration is where hackathon projects fail. A two-part design (reader plus UI) is finished on Saturday night. This one is at risk until Sunday morning.
- **When a frontier vision model is simply good enough.** If Opus 5.5 answers 95% of everything from the image for $0.06 per question, the judges may prefer its accuracy over a 90% system at $0.002. The lens bets that exact counts and 2% areas on tricky sheets are not there yet. Measurement 1 tests the bet tonight.
- **Where the lens overreaches.** Proof certificates and a separate checker impress engineers and do nothing for a site engineer. If the jury is the construction engineer and not the tech team, the pins and the two-click scale matter and the certificate does not.

---

## 5. Ten things to measure first

Ranked by how much each changes the plan. Items 1, 2, 3 and 9 fit into the first 2 hours.

| # | Measurement | Decision it settles |
|---|---|---|
| 1 | Exact-count accuracy of one vision call (Sonnet 5.5 and Opus 5.5, image and question only) on 200 cubicasa questions stratified by template and by answer size, and on 100 swiss questions asked on the PNG. Compare with the 55.3% mode guess. Record tokens. | Whether the raster reader is a vision model, a trained counter, or both. Above 90%: do not train. Under 75%: start training tonight. It also tests the lens's bet in section 4. |
| 2 | Swiss area questions answered from the PNG only: no DXF, no PDF vectors, scale from the scale bar. Share within 2% on 100 questions. | Whether raster geometry for areas is in scope at all, or whether a raster area question gets a best guess plus "I need vector data or a calibration". |
| 3 | Leak ladder on swiss with the simplest DXF reader: all aids, then layers renamed to `0`, then PDF only, then PDF printed to an image. | How much of the swiss score is Stoa's renderer and how much is reading. It sets the priority of the vector-PDF and raster readers against the DXF reader. |
| 4 | Witness agreement precision: on 300 questions with two independent readers, the precision when they agree against the overall precision. | Whether the ledger gives a real confidence. A lift under 5 points kills concept 2 as an accuracy tool. |
| 5 | Frames and scale on 50 historic scans: share with a correct frame list, share with a scale fit under 2% residual, checked by a person. Compare with 9 of 12 and 11 of 12 in F10. | Whether to build concept 4 beyond ratio text and two-click calibration. |
| 6 | Rotation by 90 degrees and 0.5x rescale on 100 plans: share of answers that change. | Whether to add test-time voting over rotations, and how fragile the reader is on unseen styles. |
| 7 | Plan compile rate: public templates paraphrased and translated into 10 languages, plus 50 hand-written harder questions such as "tile area of all WCs". Share that type-check and return the right answer. | DSL or code-writing agent for the question side. Under 90%: use the agent, keep the IR. |
| 8 | DRC as an error detector: on reader output with ground truth, the AUC of "any rule violated" against "answer wrong". Use the rules of F3 first. | Whether the rule deck triggers escalation and repair, or serves the evidence view only. Under 0.65: view only. |
| 9 | IFC coverage: share of ifc_models and ifc_bench questions that plain `ifcopenshell` queries answer within tolerance, by question kind, and which need geometry. | How many hours IFC gets. It also shows what a free-text answer must contain before the team asks Stoa how it is scored. |
| 10 | Cost per drawing and per question for the chosen readers, from real token counts, at F15 prices, with and without the Batch API. | The model tier for ingestion and for plans, and the number the pitch states for the cost criterion. |

One question for Stoa outranks items 4 to 10, and it is not a measurement: **does an explicit "I do not know, I need a
scale" score better than a wrong number, and may an answer carry both a best guess and the reason?** The value of the
abstention work in concepts 1, 2 and 7 depends on the answer.
