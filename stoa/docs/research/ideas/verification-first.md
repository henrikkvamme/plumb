# Lens: verification first

Written 2026-11-13, late evening. One lens of several. I did not read `inputs/prior-research/` or `stoa-drawings/`.

Each figure has a mark:

- MEASURED: I measured it tonight on the local dataset. The method is given.
- SOURCED: the source is given.
- ESTIMATE: my judgement. Do not treat it as a fact.

What I looked at: 14 drawings from 8 sources (2 cubicasa5k PNG, 1 swiss_dwellings sheet as PNG, PDF and DXF,
1 ifc_models plan and 1 section, 2 opening_design sheets, 2 habs, 2 finna, 1 europeana, 1 wikimedia), about
160 questions across the 5 sources with questions, 1 IFC model with ifcopenshell, and the host conversation in
`context/stoa-drawings/2026-11-13-2308-38-conversation.md`.

Cost assumptions for this document (all ESTIMATE):

- A small hosted vision LLM costs about $1 per million input tokens and $5 per million output tokens. A frontier
  model costs about 5 times more. Check the current price list before you quote these.
- An image costs about width x height / 750 input tokens. A 1100 x 900 px plan is about 1,300 tokens.
- An A100 at $2.4 per hour (SOURCED: task brief) costs 0.067 cents per second.
- The host target (SOURCED: host conversation): about 10 cents for ingestion and query together is the good zone.
  Tens of euros per document or per question is too much.

## 1. The lens in one paragraph

An answer is a claim, and a claim without a proof object is a guess. This lens designs backward from the
moment a site engineer checks the answer in a few seconds. The system first builds evidence (numbered marks,
a polygon with its arithmetic, a table row, a model element id). Then it computes the answer FROM that
evidence with a fixed, small function. The count is the number of accepted marks, nothing else. The same
proof objects then do four more jobs: they give confidence (do independent witnesses agree?), they control
cost (spend money only where witnesses disagree), they make abstention precise ("I need a scale"), and they
make the evaluation honest (score the marks, not only the number). The belief is that on a hidden, harder
test set the team that knows WHEN it is wrong beats the team with a slightly better detector.

The strongest argument against it: accuracy is scored on the final number, and a proof does not make a wrong
detector right. If Stoa runs a file of answers through an exact-match scorer, then every hour spent on proof
objects, witnesses and abstention is an hour not spent on recall of doors in a blurry scan. An abstention
scores zero in such a scorer. A team with a plain fine-tuned detector and a good vision model can then score
higher on 25% of the judging, and the host said that accuracy on the hidden set matters most.

## 2. Facts I measured that shape this lens

These are the base for the concepts. All MEASURED unless marked.

1. **The "obvious" witness is wrong on Swiss doors.** On 150 random swiss_dwellings floors, the count of
   5-vertex polylines on DXF layer `DOOR` equals the answer on 150 of 150 floors. The count of `ARC` entities on
   the same layer (the door swings, which is what a person or a vision model counts) equals the answer on only
   81 of 150 floors. The public answer counts door openings. A double door has two arcs and is one door.
   A sliding door has no arc. A counting rule is part of every count claim.
2. **Agreement between two extractions predicted correctness.** Same 150 floors, 293 "net area of room N"
   questions. Witness A: the DXF `ROOM_OUTLINE` polygon that contains the room number. It is within 2% on 293
   of 293. Witness B: my crude parser of the filled room paths in the PDF (straight segments only), times the
   scale. It is within 2% on 229 of 293. Where A and B agreed within 1% (227 cases), B was correct in 227 of 227.
   Where they disagreed (66 cases), B was correct in 2 of 66. Note the limit: both files come from one
   geometry source, so this agreement checks OUR extraction, not the drawing.
3. **The Swiss PDF is fully structured.** One sheet has 0 images, 117 words and 404 vector paths. The room
   polygons exist as filled paths. Room 1.22 gives 10.13 m2 and room 1.07 gives 15.15 m2 from the PDF alone,
   equal to the answers. So the public Swiss score can reach about 100% without any "understanding".
   That score says nothing about a scanned or flattened sheet.
4. **Scale has more than one witness on a sheet.** On `site1104_bldg2244_floor10289.pdf` the labels "0" and "5"
   of the scale bar are 141.7 pt apart. 5 m at 1:100 is 141.73 pt. The title block says "1:100 (A3)". The
   page is A3 (1190.55 x 841.89 pt). Three witnesses agree.
5. **A schedule is a ready proof.** On opening_design sheet A-801 the 27 cells of the form "N SF" sum to 49,560.
   The answer to "total area of all rooms that have an area listed" is 49,560. The door schedule has 38 unique
   door numbers. The answer to "how many doors are listed" is 38.
6. **An IFC answer is an element set.** In `bsc-molio_molio-with-uris.ifc` there are 119 `IfcDoor` (answer 119),
   117 `IfcSpace` (answer 117), and the space "Rum nr. K06" has "Measured Net Area" 3.96 in its property set
   (answer 3.96).
7. **Scope is the trap on real sheets.** Sheet A-701 (Restrooms) asks "how many water closets are drawn in
   enlarged plan 6A?". The answer is 2. I counted about 13 drawn water closets on the sheet by eye (ESTIMATE,
   one viewing), because each toilet also appears in elevations and in other plans. A sheet-wide count is
   wrong by a factor of 6.
8. **Fixture and room answers obey relations.** On the 1,161 cubicasa5k drawings that have all the templates:
   toilet bowls <= bathrooms + WC rooms on 100%; equal on 76.1%; doors >= bedrooms + bathrooms + WC rooms on
   99.9%; sinks >= kitchens on 99.3%; saunas <= bathrooms on 99.2%.
9. **Large counts are common outside cubicasa.** Count answers: cubicasa5k median 1, p90 7, p99 21, max 92.
   swiss_dwellings median 4, p90 17, p99 55, max 157. ifc_models median 20, p90 140, p99 846, max 3,104.
10. **The public set under-tests "none".** Zero is the answer for 11.2% of cubicasa counts, 1.1% of Swiss counts
    and 0% of ifc_models counts. Only 897 of 1,040 Swiss floors have a bathtub question and 322 have a shower
    question. My reading (ESTIMATE): the generator skipped most zero questions. A system can learn "a question
    exists, so the thing exists". The hidden set can break that.
11. **Many questions per drawing.** Median 18 on cubicasa5k, 36 on swiss_dwellings, 24 on ifc_models.
12. **Redundancy is rare on the historic scans.** Of the 14 drawings I opened, 2 have a legend (the Swiss sheet
    and a HABS site plan), 2 have a schedule or title-block scale table, 9 show a scale bar or a scale text,
    and 2 hand-drawn finna sheets have handwritten dimensions and a faint scale. A europeana 1885 plan has
    room names in old German script and no scale that I could see.

## 3. Concepts

Each concept has the same fields. "Hidden" means behaviour on the hidden test set.

### 3.1 Evidence Ledger: the answer is a function of proof objects

**Pitch.** No model ever writes the number: a model proposes evidence, and a 50-line function turns accepted
evidence into the answer.

**Mechanism.**

- Once per drawing: build a ledger of typed evidence items. Each item has a geometry, a class, a provenance
  (which witness made it) and a status.
  - `Mark`: a point or box on a page, for a countable thing.
  - `Region`: a closed polygon in page units, plus a scale with its own evidence, for an area or a length.
  - `Row`: a table cell with its row and column headers, for a schedule lookup.
  - `Element`: an IFC GlobalId with class, storey and quantities.
  - `Scope`: a view, a level, an apartment or a room that limits the others.
- Per question: a small LLM compiles the question into a plan in a tiny DSL, for example
  `scope(view="6A") > select(class="water_closet", rule="one per fixture") > count`.
- A deterministic executor runs the plan on the ledger. The answer is `len(marks)`, `sum(area(region))`,
  `cell(row, column)` or `len(elements)`.
- The proof object is the plan plus the item ids plus the arithmetic. It is JSON. The UI and the harness read
  the same JSON.

**Needs.** A schema, an executor, a plan compiler prompt. No training. One small LLM call per new question
template (about 600 input and 150 output tokens, ESTIMATE). Evidence comes from the other concepts.

**Four criteria.**

- Accuracy: neutral by itself. It removes one error class: a model that sees 9 doors and writes 8.
- Verifiability: strong. Each number has a list of things to look at.
- Creativity: medium. The idea is plain, but few teams enforce it.
- Cost: good. The plan is cached per template and per language. Execution is free.

**Hidden.** The DSL is the risk and the strength. A new template in a new language compiles to the same
plan when its meaning is the same (the LLM handles language). A question outside the DSL (for example
"what is the typical room configuration?") does not compile. Then the system must say so and fall back to a
free-text answer with cited items. It does not depend on file names or sibling formats.

**Cost per question.** About 0.14 cents for an uncached plan and about 0 for a cached one (ESTIMATE).

**Evidence view.** The plan in one plain sentence ("I counted door openings inside view 6A"), the marks with
numbers, and the line "28 marks accepted, 2 rejected, 0 disputed".

**33 hours.** Fits: schema, executor, 10 to 15 operators, compile prompt, cache. Does not fit: a DSL that
covers every ifc_bench free-text question.

**Kill measurement.** Hand-write 40 questions that are harder than the public ones (the host example: "how
many m2 of tiles for the toilets"). Count how many compile to a correct plan. Below 70% (ESTIMATE of a
useful bar), the DSL is too narrow and needs a code-writing fallback.

**Main risk.** The plan is right and the evidence is poor. The ledger does not find doors.

### 3.2 Proof kernel: an untrusted solver and a trusted checker (unusual)

**Pitch.** Let any solver, also an expensive free-roaming agent, attack a tricky drawing, and accept its
answer only when a small independent checker accepts its proof.

**Mechanism.**

- The idea comes from proof-carrying code. The producer is complex and not trusted. The checker is small and
  trusted.
- The solver can be a detector, a geometry routine or a frontier model with tools. It must return a proof
  object in the ledger schema.
- The kernel is a program of a few hundred lines with no model inside. It checks:
  - each mark lies on the page and inside the scope polygon;
  - no two marks are closer than a class radius (no double count);
  - each polygon is closed and does not cross itself, and the area is recomputed from the vertices;
  - the scale has at least one evidence item, and its witnesses agree;
  - each cited table cell exists and its text parses to the cited value;
  - each IFC GlobalId exists and has the stated class and storey;
  - the answer equals the recomputed value.
- The kernel also runs cheap content checks on a sample of marks: a small crop classifier says whether crop k
  looks like the claimed class.
- A proof that fails is rejected with a reason. The solver can retry once with the reason.
- Once per drawing: nothing extra. Per question: one kernel run, in milliseconds.

**Needs.** The schema from 3.1. A crop classifier for the content check (shared with 3.5). No extra labels.

**Four criteria.**

- Accuracy: removes structural errors (double counts, marks outside scope, wrong arithmetic, wrong units).
  It does not catch a missed door.
- Verifiability: strong. "Checked by a program with no AI in it" is a sentence a site engineer understands.
- Creativity: high. It also answers "what about next year's models?". A better model is a better solver. The
  kernel stays.
- Cost: the kernel is free. It also lets us use a costly solver only as a last tier.

**Hidden.** This is the concept that ages best. For a drawing style nobody saw, the fallback solver is a
frontier model that marks things on tiles. The kernel treats its output like any other. Without the kernel a
frontier model answer on an unseen sheet is unverifiable.

**Cost per question.** 0 for the kernel. The fallback solver costs 1 to 5 cents per drawing on tiles
(ESTIMATE: 6 to 12 tiles of about 1,500 tokens plus output), and it runs only when cheaper tiers fail.

**Evidence view.** A badge per answer: "proof checked: 7 of 7 checks passed", with the list. A failed check
is shown, not hidden.

**33 hours.** Fits: the structural checks, in half a day. Does not fit: a formal guarantee, or a content
check for every class.

**Kill measurement.** Take 200 wrong answers from any baseline that returns marks. Count how many the kernel
rejects. If it rejects under 10% (ESTIMATE of a useful bar), the kernel only catches bugs, not errors, and
it is a harness tool, not a product feature.

**Main risk.** Most real errors are missed or wrong-class items. A structural check passes them. The kernel
then gives false comfort. The badge must say what it did not check.

### 3.3 Witness quorum with local disputes

**Pitch.** Two or three independent methods find the same things, agreement becomes the confidence, and
only the items they disagree on cost money.

**Mechanism.**

- Per entity class, run the witnesses that exist for the format:
  - W1 structure: IFC entities, DXF layers and blocks, PDF vector paths and text.
  - W2 geometry rules: a gap in a wall with a swing arc is a door; a closed region bounded by walls with a
    label inside is a room.
  - W3 a small learned detector on the raster.
  - W4 a vision LLM that looks at one crop or one tile.
- Match marks between witnesses by position. Each mark gets a support set, for example {W1, W3}.
- A mark with full support is accepted. A mark with no second witness is "single". A mark that one witness has
  and another explicitly lacks is "disputed".
- Disputed marks go to an adjudicator: one cheap vision call on a contact sheet of crops (see 3.5).
- Confidence for the answer comes from the support pattern, through a table fitted on held-out drawings:
  P(count exact | all marks full support), P(count exact | k disputes), and so on.
- Once per drawing: all witnesses and the matching. Per question: a lookup.

**Needs.** At least two witnesses per format. For raster, a detector (training in 3.5) and a vision LLM. A
held-out set to fit the table: about 300 drawings with mark-level truth. For cubicasa5k the public SVG
annotations give it. For Swiss the DXF gives it.

**Four criteria.**

- Accuracy: up when witnesses make different errors. Fact 1 shows the need: arcs and openings disagree on
  46% of Swiss floors, and the dispute points at exactly the double and sliding doors.
- Verifiability: the person sees which marks are solid and which are not. Checking effort goes to the few
  disputed ones.
- Creativity: medium to high.
- Cost: most marks never reach an LLM.

**Hidden.** On an unseen style, witnesses fail differently, so disagreement rises. That is the correct
signal. The danger is correlated failure: a faint door that both a detector and a vision LLM miss gives
false agreement. Agreement of two witnesses from one source (DXF and PDF of one render) is not independent
(fact 2). When a sibling format is missing, the quorum has fewer members and the confidence drops. It does
not break.

**Cost per question.** Per drawing: detector 0.01 cents on GPU (ESTIMATE), adjudication 0.3 to 1 cent when
disputes exist (ESTIMATE). Over 18 to 36 questions per drawing that is under 0.05 cents per question.

**Evidence view.** Marks in three styles: solid (agreed), ringed (single witness), flagged (disputed and
then decided, with the adjudicator's reason). A line: "26 agreed, 2 decided by review, confidence 0.83".

**33 hours.** Fits: two witnesses for vector formats and two for raster, position matching, a 6-row
confidence table. Does not fit: a learned fusion model.

**Kill measurement.** On 300 cubicasa5k plans with SVG truth, run a detector and a vision LLM. Compare
P(exact | agree) with P(exact | disagree). If the gap is under 15 points (ESTIMATE), agreement is not a
usable confidence and the second witness is not worth its cost.

**Main risk.** Correlated errors, and double work: two mediocre witnesses instead of one good one.

### 3.4 The drawing audits itself

**Pitch.** A good drawing says the same thing several times, so use the legend, the schedule, the scale bar,
the dimensions and the room labels as free checkers that need no training.

**Mechanism.**

- Legend as the class definition. Find the legend, cut each symbol with its label, and match the symbol
  across the sheet (template matching on vector shapes, or embedding match on raster). The label gives the
  class in the drawing's own language. The Swiss sheets have a legend with 8 symbols (MEASURED on one sheet).
- Schedule against plan. The door schedule lists 38 doors (fact 5). The plan sheets carry door tags. The two
  counts must agree. A difference is reported as a finding, not hidden.
- Scale triangulation. Scale text, scale bar, a printed dimension against its measured length, the paper size
  and a known object (a door leaf is about 0.7 to 1.0 m, a toilet about 0.7 m long). Agreement gives a scale
  with confidence. One witness alone gives a scale with a warning.
- Conservation laws. Room areas of an apartment sum to the apartment. Rooms plus walls fill the outline. Counts
  per zone sum to the total. A room labelled WC or Bad with no toilet mark is a flag (fact 8: toilets never
  exceed bathrooms plus WC rooms on cubicasa5k).
- Language pairs. The EN and FI versions of one question must compile to one plan. This is a free test.
- Once per drawing: find legend, schedules, scale witnesses. Per question: check the relations that touch
  the answer.

**Needs.** Table extraction from vector PDF text positions (works on A-801, fact 5). OCR for raster. A list
of about 15 relations. No training.

**Four criteria.**

- Accuracy: catches errors that a single pass does not see. It also finds real drawing errors.
- Verifiability: strong and natural. "The schedule says 38 and I found 38 tags" is how an engineer checks.
- Creativity: high for the legend part.
- Cost: almost free.

**Hidden.** Mixed. It is independent of language and of our training data, because the drawing brings its
own definitions. But redundancy is rare on the historic scans (fact 12): 2 of 14 drawings had a legend. A
relation learned on Finnish apartments ("toilets <= bathrooms + WC rooms") can be false for a school. So
relations are flags that lower confidence. They never change an answer.

**Cost per question.** About 0 after ingestion.

**Evidence view.** A "cross-checks" strip under the answer: "scale bar 5 m = 141.7 pt, title block 1:100,
agree", "schedule 38, plan tags 38, agree", "apartment C = 5 rooms = 75.26 m2".

**33 hours.** Fits: scale triangulation, table sums, zone subtotals, 10 relations. Does not fit: robust
legend matching on raster scans, schedule-to-plan matching across sheets.

**Kill measurement.** On 60 random drawings from all 9 sources, record which redundancy exists (legend,
schedule, scale text, scale bar, dimension strings). If under 30% have two or more (ESTIMATE of a useful
bar), this is a nice extra for modern sheets, not a base.

**Main risk.** Engineering time on parsers for layouts that the hidden set does not contain.

### 3.5 Verify, do not find: contact sheets and the residual view

**Pitch.** Checking a candidate is far easier than finding it, for a model and for a person, so make every
count a two-sided check: a grid of crops for precision and an "everything counted is erased" image for recall.

**Mechanism.**

- A high-recall proposer makes candidate marks. It can be a small detector, a geometry rule or a tiled vision
  LLM.
- Precision side: cut a crop around each candidate. Lay the crops on a contact sheet, 48 per image, sorted by
  confidence with the weakest first. A small classifier, or one vision call per sheet, answers "which cells
  are not a door?".
- Recall side: paint over every accepted mark. Run the proposer again at a lower threshold on this residual.
  Anything it still finds is a missed candidate. A person sees a leftover door on a mostly empty plan at once.
- The count is the number of accepted cells. The contact sheet and the residual are the proof.
- Once per drawing: proposals, crops, residual, per class. Per question: a lookup.
- The same two images are the human evidence view. One artefact serves the model and the person.

**Needs.** A proposer per raster class. Training a small detector on the public CubiCasa5K SVG annotations:
1 to 3 A100 hours (ESTIMATE). Leakage rule: these plans are in the Stoa set, so score it only on drawings held
out by id, and also on rendered Swiss PNGs and on hand-marked historic scans. A crop classifier can come from
the same labels.

**Four criteria.**

- Accuracy: precision improves cheaply. Recall is limited by the proposer, and the residual pass recovers a
  part.
- Verifiability: this is the answer to "143 doors". See 3.10.
- Creativity: medium. The residual view is unusual and makes a good demo.
- Cost: one vision call checks 48 items. That is about 2,000 tokens per sheet (ESTIMATE), 0.2 cents.

**Hidden.** Crop classification transfers better than detection, because a crop of a door looks similar
across styles while page layout does not (ESTIMATE, to measure). For a class nobody trained on ("columns",
"fire extinguishers"), the proposer is a tiled vision LLM and the verifier is the contact sheet. It still
works, at a higher cost.

**Cost per question.** 0.2 to 1 cent per drawing and class when a vision LLM verifies, about 0 with a local
classifier. Shared across the questions of the drawing.

**Evidence view.** Left: the plan with numbered pins. Right: the grid of crops with the same numbers. A
toggle shows the residual. A click on a cell jumps to its place on the plan.

**33 hours.** Fits: detector for the 6 cubicasa fixture and opening classes, crops, contact sheet, residual.
Does not fit: a detector for every class of the hidden set.

**Kill measurement.** Give a vision LLM 10 contact sheets of 48 crops with known labels and 15% wrong cells.
Measure the per-cell accuracy. Under 95% (ESTIMATE of the bar, because one wrong cell breaks an exact count),
use a trained crop classifier, or drop the idea.

**Main risk.** Exact-match scoring punishes one wrong cell in 48. The verifier must be close to perfect on
easy cells, and the rest must be flagged.

### 3.6 Canary insertion and metamorphic tests (unusual)

**Pitch.** Measure how well we see THIS drawing, with no labels, by planting known objects in it and by
checking that the answer survives changes that must not matter.

**Mechanism.**

- Canary insertion: take symbols from the drawing itself (accepted marks, or the legend) and paste K copies
  into empty areas, with the same line weight and noise. Run the detector. The share of canaries found is a
  recall estimate for this drawing and this style.
- Erasure: paint over one accepted mark. The count must drop by exactly one.
- Invariance: rotate by 90 degrees, mirror, scale by 0.8. Counts must not change. Areas must not change after
  the scale correction. Ask the question in a second language. The plan must not change.
- Each failed test lowers the confidence and is listed in the proof.
- Once per drawing: 3 to 6 extra detector runs, all local. Per question: nothing.

**Needs.** A local detector (3.5). An inpainting step that is only "paste on white". No labels. No API.

**Four criteria.**

- Accuracy: no direct gain. It decides when to escalate to a costly tier, and that raises accuracy per cent
  spent.
- Verifiability: a confidence with a reason a person can follow: "I planted 10 test toilets and found 10".
- Creativity: high. I do not expect another team to do it.
- Cost: only local compute, about 0.05 cents per drawing on GPU (ESTIMATE).

**Why it could still win.** The hidden set has styles we never saw. Every confidence fitted on public data is
then wrong in an unknown direction. A canary test is fitted on the drawing in front of us. It is the only
calibration here that does not assume the hidden set looks like the public one. It also shows the host
exactly what they asked for: a confidence for the non-deterministic step, and a method that is not tuned to
the sample questions.

**Hidden.** Good for symbol-like classes (fixtures, doors, columns, trees on a site plan). Weak for classes
with no stable symbol (rooms, kitchens). A pasted symbol is easier than a real one that touches walls, so
canary recall is an upper bound.

**Cost per question.** About 0.

**Evidence view.** A small strip: "self-test: 10 of 10 planted found, rotation stable, erase-one stable".
On failure: "self-test: 6 of 10 planted found. The count is likely too low."

**33 hours.** Fits: rotation and mirror tests in the harness (2 hours), canaries for the detector classes
(4 to 6 hours). Does not fit: realistic insertion on hand-drawn scans.

**Kill measurement.** On 200 held-out cubicasa5k plans, compute canary recall and true recall (from the SVG)
per drawing. If the correlation is under 0.3 (ESTIMATE of a useful bar), canaries do not predict real
recall. Keep only the invariance tests.

**Main risk.** Time. It is the first thing to cut, and it gives nothing if the base detector is weak.

### 3.7 Typed abstention, conditional answers and honest error bars

**Pitch.** "I do not know" becomes a typed result with the missing premise, a request, and the answer that
would follow if the person supplies it.

**Mechanism.**

- Each plan has preconditions. The executor tests them: scale known (and agreed), scope found (the view,
  level or room exists on this sheet), class defined (a symbol or label for it exists), page legible at the
  needed size, element data present in the IFC.
- A failed precondition gives a reason code and a request:
  - `NO_SCALE`: "No scale text, scale bar or dimension found. Give me the scale, or click two points with a
    known distance."
  - `SCOPE_NOT_ON_SHEET`: "This sheet shows level 2. The question is about the whole building. I need the
    model or the other sheets."
  - `RESOLUTION_LIMIT`: "Room 1.12 is 2.9 m2 and 40 px wide. One pixel of wall position changes the area by
    5%. I cannot reach 2%."
  - `AMBIGUOUS_RULE`: "28 door openings, 31 door leaves. Which one do you order?"
  - `NO_QUANTITY_IN_MODEL`: "The space has no area quantity. I computed 3.96 m2 from its geometry."
- A conditional answer always comes with it: the area in drawing units, or the value under each plausible
  scale ("12.4 m2 if 1:100, 49.6 m2 if 1:200").
- The error bar for an area on a raster is deterministic: boundary uncertainty of about 1 px times the
  perimeter, divided by the area.
- For the scorer, the system still emits its best value with a status (`proved`, `supported`, `disputed`,
  `unknown`). Silence scores zero. The status is the abstention.
- Once per drawing: scale evidence, legibility, sheet inventory. Per question: precondition tests.

**Needs.** The reason codes, the precondition tests, about 10 message templates in plain language. A click
tool for calibration in the UI. No training.

**Four criteria.**

- Accuracy: no gain under exact-match scoring. A gain if Stoa gives credit for a correct "cannot know".
- Verifiability: the host asked for exactly this (SOURCED: host conversation, "the I don't knows are super
  important", "give us a scale or calibrate").
- Creativity: medium. The conditional answer and the error bar are the new parts.
- Cost: free.

**Hidden.** This concept exists for the hidden set. The host said some drawings have no scale and that tricky
drawings have the same extensions with different content (SOURCED: host conversation). A system with typed
reasons degrades in a way a judge can respect. The risk is the opposite error: abstaining on an easy question.

**Cost per question.** 0.

**Evidence view.** An amber card in place of the green one: the reason, what was searched ("looked for
scale text, scale bar, dimension strings: none found", with the searched regions outlined), the request, and
the conditional values.

**33 hours.** Fits: 5 reason codes, conditional answers, the pixel error bar, the two-click calibration.
Does not fit: a dialogue manager.

**Kill measurement.** Ask Stoa one question: "Does a correct 'I cannot know this from this sheet' score as
correct, as zero, or better than a wrong number?" If it scores zero and wrong answers are not penalised, keep
the status flag and never withhold the number.

**Main risk.** Over-abstention. A status of `unknown` on 20% of easy questions looks like weakness.

### 3.8 Counting rules as part of the claim (unusual)

**Pitch.** Many "wrong" counts are right counts of a different thing, so the claim names its rule, and the
proof shows the nearest other rule and its number.

**Mechanism.**

- A count plan has an explicit rule slot: unit of counting (opening, leaf, symbol, tag, schedule row, IFC
  entity), scope (sheet, view, level, model) and inclusion rules (double bowl counts as one, open doorways
  do not count).
- The compiler fills the slots from the question text. The public templates state many rules ("a double-bowl
  sink counts as one", "open doorways without a door leaf do not count").
- For an unstated slot, a default comes from a short table per domain. The proof lists the default as an
  assumption.
- The executor computes the answer under the chosen rule and under the nearest alternative. When they differ,
  the proof shows both: "28 openings (31 leaves)", "2 in view 6A (13 on the sheet)".
- Once per drawing: marks carry the attributes that the rules need (leaf count, view id, has-leaf).
  Per question: slot filling.

**Needs.** Attributes on marks. A defaults table. The paired public questions are a test set for slot
filling. No training.

**Four criteria.**

- Accuracy: targets a measured error. Arcs versus openings differ on 46% of Swiss floors (fact 1). Sheet
  versus view differs by a factor of 6 on A-701 (fact 7, partly ESTIMATE).
- Verifiability: the person sees what "door" meant.
- Creativity: medium to high. It treats ambiguity as data.
- Cost: free.

**Why it could still win.** The host said the hidden questions are "much more difficult" and that answers can
be more complex (SOURCED: host conversation). Harder quantity questions are mostly harder definitions and
scopes ("tiles for the toilets": which rooms, floor or walls?). A system with rule slots can answer those by
composition. A site engineer who orders door leaves and frames needs both numbers.

**Hidden.** Good for new templates, because slots compose. The defaults can be wrong for a new domain. Then
the alternative number is still on the card.

**Cost per question.** 0 beyond the plan compile.

**Evidence view.** One line under the number: "Rule: one per door opening. Double doors count once. Sliding
doors count. Other reading: 31 door leaves." The marks that differ between the readings are highlighted.

**33 hours.** Fits: 3 slots, 2 alternatives for doors, sinks, toilets and rooms. Does not fit: a full
ontology.

**Kill measurement.** On the 150 Swiss floors, check that the default rule reproduces 150 of 150 and that the
alternative explains the vision-style count. Then write 20 questions with unstated rules and see if two
people agree on the default. If people do not agree, the fork is the only honest answer and must be shown.

**Main risk.** Two numbers on a card can read as indecision. The primary number must be clear.

### 3.9 Proof-level evaluation: score the evidence, not only the number

**Pitch.** The harness reads the same proof objects as the UI, so it can tell a correct answer from a lucky
one, and it can simulate the hidden set by degrading drawings.

**Mechanism.**

- Mark-level truth exists for free: CubiCasa5K SVG annotations (SOURCED: task brief) for 4,787 plans, DXF
  layers for 1,040 Swiss floors, IFC entities for 109 models. No hand labelling for the first version.
- Metrics per source and per template:
  - answer accuracy (the official metric);
  - mark precision and recall;
  - right-for-the-wrong-reason rate: the number is correct and the marks are not (errors that cancel);
  - proof validity rate (kernel pass);
  - calibration: accuracy by status and by confidence bin;
  - selective accuracy against coverage;
  - cost per question and per drawing.
- Degraded variants of each drawing, to imitate tricky hidden files: rasterise the PDF, drop DXF layer names,
  remove IFC property sets, rotate, lower the resolution, translate the labels, hide the sibling formats,
  crop the title block (no scale).
- Baselines that must lose on proof metrics: the mode guess per template (55.3% on cubicasa5k, SOURCED: task
  brief, with 0% valid proofs) and "the question exists so the answer is not zero" (fact 10).
- A balanced score: the mean over sources and templates, not over rows. 67% of rows are cubicasa counts.

**Needs.** The schema. Loaders for the three truth sources. About 60 hand-marked historic scans for a small
"wild" set: 2 to 3 person-hours (ESTIMATE).

**Four criteria.**

- Accuracy: indirect. It stops us from shipping a change that wins the public number by luck.
- Verifiability: it measures it. "94% of our correct answers have a valid proof" is a pitch line.
- Creativity: medium.
- Cost: it reports it.

**Hidden.** This is the direct answer to Henrik's first request (an evaluation we can trust). The gap between
the clean score and the degraded score is our best estimate of the hidden-set drop.

**Cost per question.** 0 at inference.

**Evidence view.** None for the end user. For the team: a table per source and template, clean against
degraded, with the proof metrics.

**33 hours.** Fits: answer metrics, mark precision and recall on cubicasa and Swiss, four degradations.
Does not fit: a large wild set.

**Kill measurement.** Compute the right-for-the-wrong-reason rate of the first baseline on 300 cubicasa5k
plans. If it is under 2% (ESTIMATE), answer accuracy alone is a fine metric and this harness can stay small.

**Main risk.** Building the harness instead of the solver.

### 3.10 What makes an evidence view fast to check: 3 doors and 143 doors

This is a design note, not a tenth concept. It uses 3.3, 3.5 and 3.8.

A person checks a count in two directions. Precision: is each mark a real one? Recall: is anything missing?
Numbered pins answer the first and not the second. For 3 doors the eye does both at once. For 143 it cannot.

**3 doors.**

- Zoom to the box that holds all marks. Large numbered pins. The rest of the plan is dimmed.
- One sentence with the rule. One click toggles the marks off, so the person sees the bare drawing.
- Target: a verdict in under 5 seconds (ESTIMATE, to measure with a stopwatch).

**143 doors.**

- Subtotals that sum. Split by a structure the person already knows: per apartment, per room, per grid
  square, per storey. "Whg A 9 + Whg B 10 + Whg C 9 = 28". The person checks one part and trusts the sum.
- Weakest first. Sort marks by confidence. Show the 10 weakest as large crops. If those are right, the
  rest are very likely right.
- Contact sheet. All 143 crops in a grid, grouped by look. A wrong one stands out in a grid of similar ones.
- Residual view. Erase everything counted. Leftovers are the missed ones. This is the only fast recall check.
- Sampling audit, as in quality control. The system picks 15 random marks and 4 random tiles of the residual.
  The person confirms them. The card then says what that sample supports, for example "0 errors in 15: the
  error rate is under 18% with 95% confidence" (the rule of three: 3 / 15 = 20%, ESTIMATE of the exact
  bound). Honest, and fast.
- Repetition. For repeated units or storeys: "storey 2 to 6 are the same layout: 5 x 24 + 23 on storey 1".
  The proof shows one unit and the exceptions.
- A second source. When a schedule exists, show "schedule rows 143, plan tags 143". Then nobody counts.

**Areas.** Show the polygon filled, the vertices, the scale evidence and the arithmetic: "polygon 8,139 pt2
x (0.03528 m per pt)^2 = 10.13 m2". A bad polygon is visible at once, because it leaks through a door or
cuts a corner.

**Table lookups.** Highlight the row, the column header and the cell. Quote the cell text.

**IFC.** List the GlobalIds, and highlight the elements in a 3D or plan view. The host said the 3D models are
evaluated through the team's UI (SOURCED: host conversation).

## 4. The system I would build from this lens

Working name: **Receipt**. Every answer comes with a receipt, and a small program checks the receipt.

One sentence: build a ledger of evidence once per drawing with every witness the format allows, compile each
question to a plan, compute the answer from the ledger, check the proof with a model-free kernel, and show a
card whose colour comes from witness agreement and failed preconditions.

```
                 ONCE PER DRAWING                                   PER QUESTION
 file ──> format router                                       question (any language)
           │                                                        │
           ├─ IFC ──────> W1 entities, storeys, quantities          v
           │              W2 geometry (areas, volumes)        plan compiler (small LLM, cached)
           ├─ DXF / ────> W1 layers, blocks, text, paths            │  plan = scope > select(rule) > aggregate
           │  vector PDF  W2 rooms from walls, openings             v
           └─ raster ───> OCR text                            executor (deterministic)
              (PNG, JPEG, W3 small detector + room regions          │  answer = f(ledger items)
               scanned    W4 vision LLM on crops, disputes only     v
               PDF)                                           proof object (JSON)
           │                                                        │
           v                                                        v
   sheet structure: views, legend, schedules,                 proof kernel (no model)
   scale witnesses (text, bar, dimensions, paper)                   │  structure, arithmetic, scope, scale
           │                                                        v
           v                                                  status + confidence
   EVIDENCE LEDGER  <──── witness matching, disputes,          proved / supported / disputed / unknown(reason, request)
   (marks, regions, rows, elements, scopes,                         │
    each with provenance and support set)                           v
           │                                                  ANSWER CARD
           └──────────────── same JSON ──────────────────>    number, rule, marks or polygon or row or ids,
                                                              cross-checks, self-tests, cost in cents
                                   │
                                   v
                          EVALUATION HARNESS
                 answer accuracy, mark precision and recall,
                 lucky-answer rate, calibration, cost,
                 clean files against degraded files
```

How the parts fit:

- **One ledger, three readers.** The executor, the UI and the harness read the same proof JSON. A change that
  improves the public number but breaks the marks shows up the same hour.
- **Status rules, simple on purpose.**
  - `proved`: the evidence is structural (IFC entity, schedule cell, vector polygon), the kernel passes and the
    scale witnesses agree. The card says "deterministic".
  - `supported`: learned witnesses agree and the self-tests pass. The card gives a confidence.
  - `disputed`: witnesses disagreed and an adjudicator decided, or a cross-check failed. The disputed items
    are shown first.
  - `unknown`: a precondition failed. The card gives the reason, the request and the conditional answer.
- **Cost follows doubt.** Tier 0 is parsing and geometry. Tier 1 is local models. Tier 2 is a vision LLM on
  crops of disputed items. Tier 3 is a frontier model on tiles, only for a drawing where tiers 0 to 2 give
  nothing, and only through the kernel. The card prints the tier and the cents.
- **No shortcut is a single point of failure.** Each structural shortcut (DXF layer names, PDF room fills,
  IFC property sets, a sibling file) is a witness with a fallback. The harness runs each drawing with the
  shortcut removed. A source where we are 100% clean and 40% degraded is a known hidden-set risk.
- **The rule and the scope are always on the card.** Facts 1 and 7 are the reason.
- **The system always gives a number when it has one.** The status carries the doubt. This protects the
  accuracy score if abstention scores zero.

Order of work, for 4 people and 33 hours (all hours ESTIMATE):

1. Hours 0 to 2, everyone: ask Stoa the three interface questions (section 6, items 1 to 3). Agree on the
   proof JSON schema and the status rules. This is the contract between all later work.
2. Hours 0 to 6, person A: harness with answer metrics and mark metrics on cubicasa5k (SVG truth) and Swiss
   (DXF truth), the balanced score, and four degradations.
3. Hours 0 to 8, person B: structured path. IFC with ifcopenshell (entities, storeys, quantities, geometry
   areas). Vector PDF and DXF (text, closed polygons, tables, scale witnesses). This covers ifc_models,
   ifc_bench in part, swiss_dwellings and opening_design with `proved` answers.
4. Hours 2 to 14, person C: raster path. Train the detector on Verda with a split by drawing id. OCR. Room
   regions from label seeds. Crops and the residual image.
5. Hours 4 to 12, person D: plan compiler, DSL, rule slots, cache. Test with the EN and local-language pairs
   and with 40 hand-written harder questions.
6. Hours 8 to 20, person B then D: kernel, status and confidence table, reason codes and conditional answers.
7. Hours 12 to 24, person A: the answer card. Pins, polygon with arithmetic, table row, element ids,
   subtotals, contact sheet, residual toggle, two-click scale calibration.
8. Hours 14 to 26, person C: second raster witness (vision LLM on contact sheets for disputes). Fit the
   confidence table on held-out drawings. Raster PDFs and scans of Swiss and IFC plans from the degraded set.
9. Hours 20 to 30, everyone: the wild set. 60 historic scans with hand marks. Tier 3 through the kernel.
   Canary and rotation self-tests if time allows.
10. Hours 30 to 33: freeze. Full harness run. Record the demo: one `proved` answer, one `disputed` answer
    with 143 marks, one `unknown` with a scale request that the user then resolves with two clicks.

What I would cut first, in this order:

1. Canary insertion. Keep the rotation and mirror tests in the harness only.
2. The sampling audit statistics. Keep "weakest first".
3. Legend matching on raster. Keep the legend only as text for class names.
4. Tier 3 with a frontier model on tiles. Then unseen raster classes get `unknown` with a reason.
5. The second raster witness. Then raster answers are `supported` by one witness plus cross-checks, and the
   confidence is lower.
6. The contact sheet. Keep pins, subtotals and the residual toggle.

What I would never cut: the answer computed from evidence, the proof JSON, the kernel's structural checks,
the rule and scope line, the reason codes, and the degraded runs in the harness.

## 5. Where this lens is wrong

- **When only the number counts.** If Stoa scores a file of answers by exact match and never opens our UI
  for most questions, the proof work adds to 25% of the judging and takes time from the other 25%. A direct
  count regressor or a fine-tuned vision model can then beat a marks-based count, also when its answers have
  no proof. The host said a 90% solution beats a 70% creative one (SOURCED: host conversation).
- **When the thing has no mark.** "How many kitchens, including open kitchens?" and "how many storeys does
  the plan show?" are judgements about a whole region or sheet. A pin on the letter K is weak evidence. A
  model that looks at the whole plan can be more accurate than our mark logic. 4 of the 12 cubicasa template
  pairs are of this kind (kitchens, bathrooms, storeys, balconies), by my reading (ESTIMATE).
- **When the answer is prose.** The 820 ifc_bench answers are structured text with groups and percentages.
  No scoring rule is published. A good text generator over IFC query results beats a DSL here. The proof is
  only a list of element ids.
- **When there is no redundancy.** On a hand-drawn 1885 plan there is no legend, no schedule and no clear
  scale. The audit concept gives nothing. The lens falls back to "a vision model marks things and we show
  them". That is still checkable, but it is no more accurate than the vision model.
- **When witnesses share a cause.** Two witnesses that fail on the same faint line give high confidence in a
  wrong answer. Agreement between the DXF and the PDF of one render says nothing about the drawing (fact 2).
  Calibration from public data will be too optimistic on the hidden set.
- **When abstention is weakness.** If judges see `unknown` on a question that another team answers, the
  honest design loses that point. The host also warned that site workers do not come back to software that
  refuses (SOURCED: host conversation).
- **When time decides.** This lens has more parts than a single strong model. With 33 hours, a team that
  ships one strong detector, one vision LLM and a simple overlay can be ahead of a team with a kernel and a
  weak detector. The lens only pays off when the base extractors are good enough.
- **When the solver should learn from checks.** A lens built on reinforcement learning or on synthetic
  training data uses the same automatic checks as a training signal. That can raise raw accuracy more than
  using them as a gate. The two fit together, but this lens does not improve the solver by itself.

## 6. Ten things to measure first

Ranked. Each one names the decision it settles.

1. **Ask Stoa: how is the hidden set run, and is abstention scored?** (A question, 5 minutes.) Does a
   correct "cannot know" score as correct, zero, or less bad than a wrong number? Do they read the evidence
   per question? Settles: whether status flags are enough or real abstention pays, and how much time the card
   gets.
2. **Clean against degraded on the structured sources.** Run the vector path on 100 Swiss floors with the PDF
   as given, then with the PDF rasterised at 150 dpi and no DXF. Tonight: DXF 293 of 293 areas, crude PDF
   parser 229 of 293 (MEASURED). Settles: how much of our score is the renderer being reversible, and whether
   the raster path must also handle modern sheets.
3. **Mark-level quality of the cheapest raster witnesses.** On 100 held-out cubicasa5k plans with SVG truth:
   mark precision and recall for doors, windows and toilets from (a) a vision LLM asked for coordinates, (b) a
   detector after 1 hour of training. Settles: which one is the proposer and which the adjudicator, or whether
   the vision LLM alone is enough.
4. **Does agreement predict correctness on raster?** On the same 100 plans: P(count exact | witnesses agree)
   against P(count exact | disagree). Settles: whether the quorum (3.3) is the confidence source, and what the
   `supported` threshold is.
5. **Right-for-the-wrong-reason rate.** On 300 plans, the share of exact answers whose marks do not match the
   truth. Settles: whether mark metrics are needed in the harness, and how much the public number flatters.
6. **Plan compiler on unseen questions.** 40 hand-written harder questions, plus the public templates
   translated to 5 languages that are not in the set. Share with a correct plan. Settles: DSL only, or DSL plus
   a code-writing fallback.
7. **Stopwatch test of the evidence view.** 4 people, 12 answers each, a third of them wrong on purpose, with
   3, 30 and 143 marks. Compare pins only against pins plus subtotals plus residual. Record seconds and
   catches. Settles: which view parts are built, and it gives a number for the pitch.
8. **Redundancy inventory.** 60 random drawings across all 9 sources: legend, schedule, scale text, scale
   bar, dimension strings, yes or no. My sample of 14 gives 2 legends and 9 with some scale evidence
   (MEASURED, small sample). Settles: whether 3.4 is a base or an extra, and how often `NO_SCALE` will fire.
9. **Area error against resolution.** Rasterise 100 Swiss floors at 2480 px and at 1100 px. Compute room areas
   by flood fill from the label. Share within 2%, by room size. Settles: the `RESOLUTION_LIMIT` threshold, and
   whether raster areas are worth an attempt at all.
10. **Canary recall against true recall.** 200 held-out plans, correlation per drawing. Settles: whether 3.6
    is built or cut. Run it only if items 3 and 4 are good.

Two cheap extras if someone has 30 minutes: the contact-sheet verifier accuracy (3.5), and the cost in cents
of tiers 0 to 2 on 100 drawings, against the host's 10-cent zone.

## 7. How the public score can mislead this lens

- A mode guess per template scores 55.3% on cubicasa5k (SOURCED: task brief) with no proof at all. Report the
  balanced score per source and template, and report proof validity next to accuracy.
- 100% on Swiss areas from the PDF fills, or from the DXF, is extraction of what the renderer wrote (fact 3).
  Report it as "structured files" and show the degraded number beside it.
- Public CubiCasa5K annotations are fair training data for a detector, but a score on those same plans is
  leaked. Split by drawing id, and judge the detector on other sources.
- The public set has almost no zero answers outside cubicasa5k (fact 10) and no questions on about 6,570
  historic scans (SOURCED: task brief). Add zero-answer questions and scan questions to our own set.
- The public counting rules are specific (door openings, double bowl as one). The hidden rules can differ.
  Keep the rule as a slot, not as code.
- Agreement fitted on public drawings is too optimistic for new styles. Show the confidence table per source,
  and prefer per-drawing self-tests where they exist.
