# Ideas through one lens: agents with tools first

Date: 2026-11-14. Labels: **[M]** measured by me, **[S: file]** sourced from a report in
`stoa/docs/research/` or from the Claude price table (claude-api skill, cached 2026-11-03), **[E]** my estimate.
I opened 12 drawings and read about 100 questions.

## 1. The lens in one paragraph

Belief: the hidden set is a few tens of compound questions on unknown sheets, asked one document at a time
[S: HOST.md]. No fixed pipeline knows these sheets or these questions in advance. A strong model that plans
and calls exact tools is the only component that adapts to both. But the model must not perceive and must not
compute. It reads text, selects, and writes a small typed plan. Deterministic tools produce every number and
every mark. The agent runs once per document (a "notebook"), not once per question. Strongest argument
against: the agent adds nothing where perception fails. Frontier models count doors and windows exactly on 16%
to 39% of plans, more agent steps make counting worse, and crop and zoom loops give marginal or negative gains
[S: sota/vlm-on-drawings.md, sota/agentic-program-synthesis.md]. A naive loop is also slow, not repeatable
without a record, and costs $0.16 to $0.31 per question [E, from the second report, section E]. With weak
tools, the agent is a costly way to be wrong with good prose.

## Prices and the cost arithmetic used below

| Item | Value | Label |
|---|---|---|
| Opus 5.5 in / out / cache read per MTok | $4 / $20 / $0.20 | S: price table |
| Sonnet 5.5 | $2 / $10 / $0.10 | S |
| Haiku 5.5 (prompt up to 100k) | $0.10 / $0.50 / $0.01 | S |
| Batch discount | 50%, not usable in a live session | S |
| Image tokens | ceil(w/28) x ceil(h/28), max 4,784 at 2,576 px | S |
| `temperature` | rejected on current models, so replay needs a record | S |
| Naive Opus loop, 15 tool calls, cached | $0.31 per question | E (S: report) |
| Naive Sonnet loop, 10 calls, cached | $0.11 per question | E (S: report) |
| One Sonnet "read the sheet" call: 11k in, 2.5k out | $0.047 per document | E |
| Haiku plan call: 8k cached notebook, 300 out | $0.0003 per question | E |
| Sonnet plan call, same sizes | $0.005 per question | E |
| A 42 x 30 in sheet at 150 dpi as tiles: about 36k image tokens | $0.072 Sonnet, $0.0036 Haiku | E |

A 2,576 px overview of a 42 x 30 in sheet has 61 px per inch, so 3/32 in text is about 6 px high [E]. The
overview is for layout only. Text comes from the vector text layer or from Haiku tiles. One document with 20
questions costs about $0.056 (Sonnet compile, Haiku planner), or $0.003 per question [E]: about 100 times
below the naive Opus loop.

## 2. Concepts

### C1. Drawing Notebook (compile once, then answer from facts)

Pitch: one agent pass per document writes a typed, replayable fact store; every question reads it.

- Mechanism: (1) free probes: file type by content, text layer, vector path count, page rotation, image size.
  (2) deterministic extractors by format fill tables: `texts(id, string, bbox, angle)`, `regions(id, polygon,
  label)`, `symbols(id, class, bbox)`, `tables(id, cells)`, `dims(id, value, unit, endpoints)`,
  `scales(id, kind, value, bbox)`, `views(id, kind, bbox, scale_id)`. (3) one Sonnet 5.5 call sees the overview
  image plus a digest of the tables. It names the views, links labels to regions, reads the legend, picks the
  scale per view, and lists what is missing. It writes ids only, never coordinates or numbers. (4) the notebook
  is stored with a hash of the file. Per question: only C2.
- Needs: extractors (PyMuPDF, ezdxf, IfcOpenShell, OpenCV). No labels. No training. One API call per document.
- Criteria: accuracy up where structure exists (81% with JSON against 31% with the image [S:
  sota/vlm-on-drawings.md]). Evidence: every fact has a bbox. Creativity: medium. Cost: best case.
- Hidden set: unseen templates and languages are fine, because nothing is keyed on templates. Unseen styles
  depend on the extractors. A scan gives a thin notebook, and the notebook says so. No sibling formats are used.
- Cost: $0.03 to $0.06 per document, then C2 [E].
- Evidence view: the sheet with toggles per table: views, scale, labels, regions, symbols, and an "unknown" list.
- 33 hours: PDF vector, raster and IFC extractors at basic level: yes. DWG: only through a converter, cut first.
- Kill measurement: compile 20 sheets with no public questions (5 opening_design, 5 resbim, 10 scans). Check
  by eye whether scale, views and room labels are right. Below 70% of sheets correct: the notebook is not a base.
- Main risk: wrong facts look certain. Errors follow the extractor quality [S: sota report, P&ID graph F1 0.742].

### C2. Plans, not answers (the model writes a typed program)

Pitch: the model never states a value; it emits a short plan over the notebook, and an executor computes it.

- Mechanism: a closed DSL of about 15 operators: `select(table, where)`, `match_label(concept)`, `inside(a, b)`,
  `adjacent`, `count`, `sum`, `area(region, scale)`, `length`, `perimeter`, `lookup(table, row, col)`,
  `convert(unit)`, `minus`, `require(fact)`, `ask_user(what)`. Haiku 5.5 fills it with strict structured
  output. The notebook is the cached prefix. "Square meters of tiles for the toilets" becomes
  `sum(area(select(regions, concept=toilet)), scale=view.scale)`, with `require(scale)` first. `match_label`
  maps "toilet" to WC, KPH, Bain, TUALETTRUUM through a model-made list that is stored in the notebook.
- A count is `len(selected ids)`, so the count is the number of marks on the sheet [S: lead brief].
- Needs: the DSL, an executor, about 60 hand-written compound questions for testing. No training.
- Criteria: accuracy on compound questions is the main gain. Evidence: the plan is the explanation, each step
  has a method tag ("deterministic" or "model"). Cost: $0.0003 per question (Haiku) or $0.005 (Sonnet) [E].
- Hidden set: new templates and new languages work when the operation exists. A question outside the DSL
  returns `no_operation` and goes to C7. It does not guess.
- 33 hours: yes. This is small code.
- Kill measurement: 40 compound questions in 8 languages against hand-made notebooks with perfect facts.
  If Haiku writes a correct plan on less than 85%, use Sonnet. If Sonnet is below 85%, the DSL is wrong.
- Main risk: ambiguity. "Doors in room 128" has two readings on A-801 [S: data/wild.md]. Fix: the plan
  lists the reading it chose, and the view shows the other reading with its value.

### C3. Skills by content, not by extension

Pitch: the agent loads one short skill per document kind, chosen by probes, so a "tricky" file gets the right tools.

- Mechanism: probes decide the kind: vector plan, schedule sheet, multi-view sheet, raster plan, historic
  scan, IFC, "not a drawing". A PDF with no text layer is treated as a scan (74 opening_design PDFs have none
  [S: data/wild.md]). Each skill is about 400 tokens: extractor, traps, conventions.
  Traps I saw: page rotation 90 on a site plan with 24,667 vector paths [M]; a physical ruler inside a museum
  scan next to a drawn "5 MTR" bar [M, by eye]; a restoration report, not a drawing [M, by eye]; two buildings
  and struck-out handwritten levels on one cubicasa image [M, by eye]; a note "116 parking stalls total" next
  to countable stall groups [M, by eye].
- Needs: writing the skills from the data reports. No training.
- Criteria: accuracy and robustness on the hidden set. Cost: skills add 400 cached tokens.
- Hidden set: this is the concept that targets "same extension, other structure" [S: HOST.md].
- 33 hours: 6 skills: yes. Evidence view: a badge "treated as: scanned multi-view sheet, because ...".
- Kill measurement: classify 60 unlabeled files by probes plus one Haiku look. Below 90% right kind: router fails.
- Main risk: a wrong kind starts the wrong extractor. Fix: the compile call can override the kind once.

### C4. Unknowns ledger and the calibrate tool

Pitch: "I do not know" is a tool result with a reason and a request, made by checks, not by model confidence.

- Mechanism: each operator declares preconditions. `area` needs a closed region and a scale for that view.
  The notebook holds every scale witness: a ratio text with a paper size, a scale bar measured in pixels, a
  dimension chain, a grid spacing. Two witnesses that agree within 2% give "scale confirmed". One witness gives
  "single source". None gives `ask_user("click two points of a known length, or type the scale")`. The answer
  after calibration is tagged "user calibrated". A resbim plan has no scale bar and no printed areas, but has
  dimension chains in mm such as 9840 and 9680 [M, by eye, one file]: there the chain is the scale.
- Confidence is a table lookup on check outcomes (witness count, extractor kind, plan tier), fit on our dev set.
  Models do not know when they do not know [S: sota/agentic-program-synthesis.md].
- Criteria: this is what the host asked for by name. Cost: zero model calls.
- Hidden set: strong. About half of europeana and wikimedia sheets have no scale [S: data/wild.md].
- Evidence view: the two witnesses drawn on the sheet with their values, or the click-two-points prompt.
- 33 hours: yes. Kill measurement: on 30 sheets, compare scale from the bar with scale from a dimension
  chain. If they disagree by more than 2% on over 30% of sheets with both, pixel measurement is too weak for
  areas, and areas on rasters become "about X, outside tolerance".
- Main risk: too many abstentions on questions we could answer. Track abstention rate per skill.

### C5. Marks by id: the model judges, the tool counts (unusual)

Pitch: turn counting into yes or no decisions on numbered candidates, because models classify well and count badly.

- Mechanism: a high-recall proposer finds candidates: vector block instances and repeated path groups in a
  PDF or DXF, template matches of the legend symbols (the legend crop is the exemplar), connected components
  near wall gaps on rasters, or a small detector if another lens trains one. Each candidate gets an id and a
  crop. Haiku sees a contact sheet of 20 to 30 crops with ids and returns the ids that are the asked class.
  The count is the number of accepted ids. The run happens once per class per document and is stored.
- Why it could still win: no training, any symbol the question names ("parking stalls", "columns"), and
  each accepted mark is visible. A fine-tuned counter collapses out of distribution [S: lead brief].
- Needs: a proposer per format. About 6 contact sheets per document for the common classes: $0.003 [E].
- Criteria: accuracy on counts of unseen symbol types; evidence is native; creativity high; cost low.
- Hidden set: depends on proposer recall. A missed candidate cannot be accepted.
- 33 hours: vector proposer and legend matching: yes. A raster proposer good enough for cubicasa doors: uncertain.
- Kill measurement: on 30 cubicasa plans and 20 vector sheets, measure proposer recall for doors, windows and
  toilets against the public SVG and the swiss geometry, then the exact-count rate after Haiku. Recall under
  95% or exact counts under 70%: use it for vector files only.
- Main risk: conventions. The swiss reference counts a shared door once per apartment [S: lead brief]. Show
  both counts and state the rule used.

### C6. Second derivation (self-verification by invariants)

Pitch: the agent's verification job is to find another route to the same number, not to re-read its own answer.

- Mechanism: a fixed list of invariants that the executor checks for free: printed total against the sum of
  rows; overall dimension against the sum of its chain; polygon area against a printed area label; room count
  by labels against room count by regions; apartment area against the sum of its rooms; schedule count
  against plan tags. Agreement raises the confidence class. Disagreement is shown, with a rule for which
  value is reported (printed total first [S: data/wild.md]). Only a disagreement, or a failed precondition,
  triggers the one escalation in C7.
- Criteria: accuracy (catches off-by-one row merges), evidence (two routes side by side), cost zero.
- Hidden set: invariants are properties of drawings in general, not of templates.
- 33 hours: 6 invariants: yes. Kill measurement: on the 25 opening_design probe questions [S: data/wild.md],
  count how many wrong answers of the base path an invariant flags. Under 50%: it is decoration.
- Main risk: both routes share one extractor error and agree.

### C7. One capped escalation, recorded for replay

Pitch: a single Sonnet code-and-tools session for a question the plan path cannot serve, with a hard budget.

- Mechanism: triggers are `no_operation`, a failed precondition that a tool can perhaps fix, or a C6
  disagreement. Tools: `crop(view, bbox, dpi)`, `text_in(bbox)`, `vector_query(bbox, kind)`,
  `measure(p1, p2)`, `run_python` over the notebook tables, `ifc(code)`, `add_fact`, `ask_user`. Cap: 8 calls.
  New facts go into the notebook, so later questions on the document reuse them. Two tiers only [S: sota report].
  Every model output is stored under a hash of its input. A replay runs the stored outputs through the tools.
- Cost: about $0.07 to $0.11 per escalation [E]. Budget rule: one per document inside the 10 cent zone.
- Criteria: accuracy on the long tail; evidence: the trace as a step list with crops; cost: the worst tier.
- Hidden set: the only path for questions nobody planned for. Weak for dense visual tracing (5% on AEC-Bench
  visual tasks [S: sota report]).
- 33 hours: yes, as a thin loop. Kill measurement: run it on 30 questions that the plan path failed. If it
  fixes under 25%, replace it with a clear abstention and save the cost.
- Main risk: a fluent wrong answer. Rule: an escalated value without marks on the sheet is reported as "unverified".

### C8. IFC code cells with a schema card

Pitch: for a model file, the notebook is a schema card, and each question is one executed code cell with GUIDs.

- Mechanism: compile with IfcOpenShell, no model call: units, storeys, entity counts, property sets and
  quantity sets present, spaces with names and areas, a note when quantities are missing and geometry is needed.
  Per question: Haiku or Sonnet writes one code cell against the card, the sandbox runs it, and the result
  carries the GUIDs it used. One retry on error. Free-text answers list the convention used ("sum of stored
  NetFloorArea").
- An iterating code agent beat single-pass generation by about 37 points, and hand-made tools did not help
  [S: sota/agentic-program-synthesis.md]. So: a card and a retry, not a tool library.
- Criteria: accuracy on unseen IFC questions; evidence: the 3D viewer highlights the GUIDs, which Stoa judges
  through our UI [S: HOST.md]; cost $0.001 to $0.02 per question [E].
- Hidden set: good across schemas and languages. The best published agent scores about 56% with a judge [S].
- 33 hours: yes. Kill measurement: 40 ifc_bench questions on 5 held-out buildings, graded by a person on
  the key numbers. Under 60% with Sonnet: ship templates only and abstain on the rest.
- Main risk: volumes and side areas from geometry are slow or wrong on large models. Set a time limit.

### C9. Agents write the exam and the frozen programs (unusual)

Pitch: use agent time before the deadline, not at query time, to make hidden-like tests and to freeze traces into code.

- Mechanism A, exam: where a structured twin exists (IFC with its plan PDF, swiss DXF with its PNG), an agent
  writes compound questions and computes the answers from the structured file. We ask them on the raster or
  PDF twin only. This gives exact keys and uses no public answer. For scans, a person confirms 2 per sheet.
- Mechanism B, freezing: after each dev run, group successful C7 traces by plan shape. A coding agent turns a
  frequent shape into a new DSL operator or extractor rule. It must pass on drawings from other buildings and
  must hold no literal constant. Frozen workflows kept 93.8% completion against 96.8% for the agent at lower
  cost [S: sota report].
- Why it could still win: it produces hidden-like tests in hours, and it moves cost from inference to build
  time, which the judges do not count.
- Needs: Batch API runs with Sonnet: about 300 exam items for under $20 [E]. No GPU.
- Risk: induced programs learn the generator's conventions; 34% of test-passing agent solutions violate the
  task [S: sota report]. Kill measurement: an exam of 50 items; if a person rejects more than 20% of the
  agent-made items as wrong or trivial, write the exam by hand.

## 3. The system I would build from this lens

The system compiles a document once, shows what it knows, then answers each question with a replayable plan.

```
file
  -> probes (free): kind by content, text layer, vectors, rotation, pages
  -> skill for that kind (C3)
  -> extractors (free): texts, regions, symbols, tables, dims, scales, views
  -> ONE Sonnet call: link ids, name views, read legend, list unknowns  (C1)   ~$0.05
  -> marks by id for the common classes, Haiku contact sheets          (C5)   ~$0.003
  => NOTEBOOK (typed tables + bboxes + file hash)  -> shown as a "what I can answer" card

question
  -> Haiku plan in the DSL over the cached notebook                    (C2)   ~$0.0003
  -> executor (deterministic): preconditions (C4), result, marks, invariants (C6)
       ok            -> answer record
       no scale      -> ask_user: click two points or type the scale
       no_operation or disagreement -> ONE Sonnet session, max 8 calls (C7)   ~$0.09
  => RECORD: value, unit, marks on the sheet, plan steps with method tags,
             confidence class, unknowns, cost, replay hash
IFC file: same shape, the notebook is a schema card and the plan is a code cell (C8)
```

Order of work:

1. Hours 0 to 3: the answer record, the notebook schema, the DSL and the executor. Run the C2 kill measurement.
2. Hours 3 to 10: extractors for vector PDF (rotated text, tables by cell geometry, dimensions, scales) and
   IFC. The compile call. C4 scale witnesses.
3. Hours 10 to 16: raster path: Haiku tiles for text with boxes, regions where walls are clean, C5, C6.
4. Hours 16 to 22: C7 with the replay cache. The C9 exam runs in batch, in parallel.
5. Hours 22 to 30: fix by exam results, freeze frequent traces, crash tests on 100 random files.
6. Saturday midday: read the host hint and move hours between steps 2, 3 and 4.

Cut first, in this order: C9 freezing (keep the exam), DWG, raster region areas on damaged scans (answer with
"outside tolerance" and offer calibration), C7 for rasters. Never cut: the record, C4, the compile card.

## 4. Where this lens is wrong

- Exact counts of small symbols on low-resolution rasters such as cubicasa. A trained detector with marks
  beats any agent. C5 is only as good as its proposer.
- Room areas on scans. They need wall segmentation and a scale. A model cannot plan around missing polygons.
- The public templates. Simple parsers already score 99% [S: lead brief]. An agent adds cost and risk there.
- Hand-drawn and damaged scans. Every OCR model is weak there [S: lead brief], so the notebook is thin and
  the honest result is often an abstention.
- Latency. A compile of 20 to 60 seconds and a 30 second escalation are long in a live session [E].
- Determinism. The plan step is a model output. It repeats only through the record. A parser repeats by itself.
- If the hidden set is mostly more templates (0.20 in data/wild.md, an estimate there), a parser and
  detector team wins on cost and equals this design on accuracy.

## 5. Ten things to measure first

1. Plan accuracy of Haiku and Sonnet on 40 compound multilingual questions with perfect notebooks. Settles
   the planner model and whether the DSL holds (C2).
2. Notebook correctness on 20 unlabeled sheets: scale, views, labels. Settles whether compile-once is the base (C1).
3. Agreement of scale witnesses (bar, ratio, dimension chain) on 30 sheets. Settles whether raster areas can
   meet 2% or must be flagged (C4).
4. Proposer recall and exact-count rate of marks by id on 50 plans. Settles agent-judged counts against a
   trained detector (C5).
5. Real cost and time per document and per question on 10 documents, from `usage` fields, with cache reads
   checked above zero. Settles the model per tier inside 10 cents.
6. Share of the 50 wild probe questions [S: data/wild.md] that the plan path answers, abstains on with the
   right reason, or gets wrong. Settles how much C7 is needed.
7. Fix rate of the capped escalation on 30 failed questions. Settles keep or replace by abstention (C7).
8. Text reading with boxes from Haiku tiles against vector text on 10 sheets rendered to images, and on 10
   historic scans by eye. Settles Haiku tiles against a local OCR model.
9. IFC code cells on 40 questions from 5 held-out buildings. Settles agent against templates only (C8).
10. Crash and timeout rate on 100 random files from all sources. Settles the fallbacks: a crash is a zero
    for the whole document.
