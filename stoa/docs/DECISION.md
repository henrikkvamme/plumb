# Decision: the direction for "Make Blueprints Talk"

Date: Saturday 14 November 2026, early morning. Author: the lead. The submission closes on Sunday 15 November
at 10:00. This file is the short version. Each claim points to the document that carries the evidence.

Labels: **M** measured, **S** sourced, **E** estimate.

## In short

1. **The target is the hidden set, and the public score does not predict it.** Public originals and short
   scripts with no model reproduce 99% of the public answers (M, `DATASET.md`). The host said that the hidden
   questions are "much more difficult", on "tricky drawings", asked one document at a time through our
   interface (S, `HOST.md`).
2. **Build the measuring instrument first.** `EVALUATION.md` is the design: sealed sessions, 9 cells of skill
   by kind of input, a penalty for a wrong answer, credit for a useful "I do not know", cost per document. A
   first trusted number takes about 5 hours.
3. **Recommended direction: a fact compiler.** Read each document once into typed facts that keep their place
   on the sheet, their method and a confidence. A small model turns a question into a short plan. Deterministic
   code computes the answer from the facts. A missing fact becomes a request to the user.
4. **Use models to read, not to answer.** One model call per raster document reads text, views and tables.
   One capped code session per document handles a question outside the plan language.
5. **Do not train with reinforcement learning, and do not write a Rust core, this weekend.** Use synthetic
   data first as a test suite. `SOLUTIONS.md` has the evidence for each.
6. **Three measurements decide the open choices**, and Stoa's hint on Saturday at about midday can move the
   plan. Keep the plan open until then, and build what every plan needs.

## 1. The problem, as we now understand it

| Fact | Source |
|---|---|
| 127,044 public questions. 67% are 24 templates on one source. A guess of the most common answer scores 55.3% there | M, `DATASET.md` |
| cubicasa5k: the public annotation reproduces 100% of the answers. swiss_dwellings: a PDF parser with no model, 99.63%. ifc_models: IfcOpenShell rules, 3,057 of 3,062. ifc_bench: a copy of a public benchmark | M, the lead ran each check again |
| About 8,600 drawings have no public question: historic scans, US CAD sets, 500 raster plans with dimension chains | M, `research/data/wild.md` |
| The hidden set is harder, on tricky drawings with the same file extensions and another structure. A 90% solution beats a 70% creative one | S, `HOST.md` rows 1, 2 |
| Stoa gives one document, then a series of questions, through our interface. 3D models are judged through our UI | S, `HOST.md` row 9 |
| The cost target is about 10 cents for ingestion plus the questions | S, `HOST.md` row 10 |
| Stoa values deterministic methods, a confidence, and an explicit "I don't know" with a request such as "give us a scale or calibrate" | S, `HOST.md` rows 6, 7 |
| The best frontier model gets the exact door count on 39% of plans. With structured input the same kind of model scores 81% against 31% on the image | S, `STATE-OF-THE-ART.md` |
| A session of 8 documents with 5 questions has a standard deviation of 9 to 12 points. A whole-document failure costs the most | M (arithmetic), `EVALUATION.md` |

## 2. The recommended direction

```
ONCE PER DOCUMENT                                              target: under $0.05, under 60 s
  file -> sniff by content (not by extension): IFC | DXF | vector PDF | scanned PDF | raster | not a drawing
       -> adapter
            IFC         IfcOpenShell: storeys, spaces, quantities, geometry          origin: printed, exact
            vector PDF  paths, text with rotation, closed-path rooms, tables by cell geometry
            DXF         ezdxf: layers, blocks, text
            raster      one model read (text, views, tables) + lines and regions + candidate marks
       -> views (plan, elevation, section, schedule, legend, title block), each with its own scale
       -> scale witnesses per view: ratio text, scale bar, dimension chains, printed room sizes
       -> FACT STORE: rooms, openings, fixtures, texts, dimensions, tables, scales
                      each fact: place on the sheet, origin, confidence, the witnesses that support it
       -> a card: "what I can answer here, and what is missing"

PER QUESTION                                                   target: under $0.002, under 10 s
  question (any language)
       -> plan: one small-model call writes 3 to 6 typed steps
               select, within, count, sum, area, length, lookup, convert, require, ask_user
       -> executor, deterministic: preconditions, value, the facts used, cross-checks
            all facts present      -> answer record: value, unit, marks or polygon or cells or element ids,
                                      steps with their method, convention, confidence
            a fact is missing      -> typed unknown + request ("no scale in this view: click two points")
            no plan fits, or       -> ONE capped code session on the fact store (at most once per document)
            the checks disagree       its result is marked "model reasoning"
```

Rules of the design:

1. **The compiler never guesses silently, and the executor never perceives.**
2. A count is the number of marks. An area is a polygon times a scale. A lookup is a cell or a text span.
3. Prefer a printed value, then exact geometry, then a reconstruction, then a model estimate. Show the origin.
4. A scale belongs to a view. Two witnesses that agree within 2% give "scale confirmed".
5. The counting rule is a named switch in the plan, and the answer states it.
6. Confidence is a table lookup on check results (witnesses, origin, tier), fitted on our own held-out data.
7. No file name, sibling file or public annotation at inference. The harness enforces this.
8. A crash is a zero for the whole document. Every adapter has a time limit and a fallback record.

**Why this direction.**

- It fits the protocol: one document, then many questions. The work per document is shared.
- It serves all four criteria at once. Accuracy: exact where structure exists. Verification: the evidence is
  the computation, so the two cannot disagree. Cost: about $0.05 per document and well under a cent per
  question (E). Creativity: the "what is missing" card, the scale witnesses and the unknown with a request.
- It degrades in a visible way. An unseen style gives fewer facts, not wrong ones.
- A better model next year improves the reader and the planner. The facts, the checks and the harness stay.

**Stack.** Strict Python (uv) for the harness, the compiler and the solvers. IfcOpenShell, ezdxf, pypdfium2
or PyMuPDF (AGPL: fine for the weekend, flag it for a product), shapely. The interface is an app made from
`starter/` with `pnpm j new project <name>`, with the Python service next to it in `<name>/py/`, as the
repository rules ask. The harness tests the app through the same HTTP contract. No UI is built yet.

## 3. The alternatives, and when each would win

| Alternative | It would win if | What we keep from it |
|---|---|---|
| Source parsers tuned to the public generators | the hidden set is more public templates on new drawings (0.20, E) | the existing probes become the first adapters and a baseline |
| A frontier model that answers from the image | a model counts and measures as well as it reads. Today it does not | the model as the reader of rasters |
| An agent loop per question | cost and time did not count | one capped code session per document |
| A trained detector as the main path | the hidden set is mostly cubicasa-style rasters | a detector as one witness for marks on rasters, if measurement 1 asks for it |
| A policy trained with reinforcement learning | we had weeks, and no labels for the middle steps | the reward: the harness, and the consistency checks at inference |
| A Rust core | parsing or geometry set the session time. They do not | a later port of one hot function, after a profile |

`SOLUTIONS.md` compares the families on the four criteria and on each hidden-set scenario.

## 4. What to build first

Hours are from the start of the build. Lanes have disjoint files.

| When | Lane | Work | Done when |
|---|---|---|---|
| 0 to 0.5 h | all | Agree on the contract in `EVALUATION.md` section 2: `/ingest`, `/ask`, `/calibrate` and the answer record | the schema file is committed |
| 0 to 5 h | A, harness | Scorer with its vector file, runner with sealed sessions, `smoke` and `public-mini`, baselines, `diff` | the harness reproduces 55.3%, 99.63% and 3,057 of 3,062 |
| 0 to 6 h | B, compiler | Fact store schema. Adapters for vector PDF and IFC from the existing probes, without layer names and fill colours as the only cue. Scale witnesses from text and bar | `public-mini` passes through the fact store |
| 0 to 4 h | C, questions | Plan language of about 12 operators, executor, planner prompt, preconditions and unknowns | measurement 2: at least 80% valid plans on 40 hand-written questions |
| 0 h onward | D, people | Label `wild-hand` to 150 items. Take `QUESTIONS-FOR-STOA.md` to the Stoa stand | two labels per item |
| 5 to 8 h | A | `ladder` C1 and C3, `unanswerable` with controls, cost and latency columns | the swiss parser falls on the raster condition |
| 6 to 8 h | B, C | Measurements 1 and 3 (`SOLUTIONS.md` section 7) | the raster path is chosen: model reader, detector, or both |
| Sat about 12:00 | all | Stoa's hint. Change the cell weights once. Move people to the cell with the most headroom | |
| 8 to 20 h | B | Raster adapter: one model read per document, candidate marks, dimension-chain scale. Schedule reader by cell geometry | the `count, raster` and `lookup` cells rise |
| 8 to 20 h | C | The capped code session, the cross-checks, the confidence table, `compound` questions | |
| 12 to 24 h | new lane | The evidence view in the starter app: marks, polygon with its arithmetic, cells, element ids in 3D, the request for a scale with two clicks | a teammate verifies an answer in under 10 seconds |
| Sat 20:00 | lead | Second opening of the locked set | |
| 24 to 30 h | all | Robustness: 300-file crash gate, time limits, three timed rehearsals with a teammate as the judge | zero crashes |
| 30 to 33 h | all | Freeze. Last opening of the locked set. Cost report. Submission | |

**If there is time for one thing only: the harness steps 1 to 4, and the compile step for vector PDF and IFC.**
Every plan needs them, also a plan that the hint changes.

**Cut first, in this order:** native DWG (convert, or answer "cannot read this file" with a request), the
predicted-score step of the harness, raster areas on damaged scans (answer with a range and offer
calibration), a trained detector, a synthetic sheet generator.

**Never cut:** the answer computed from evidence, the scale witnesses, the unknown with a request, the
no-crash rule, the sealed sessions.

## 5. Risks, and how we notice each

| Risk | How we notice | What we do |
|---|---|---|
| The compile step is weak on scans, and scans decide the score | `ladder` gap C0 to C1 and the `wild` cell, from hour 8 | move people to the raster adapter; use the model reader more; show ranges and requests |
| The plan language is too narrow for the hidden questions | measurement 2; the share of questions that go to the code session | add operators after the hint; let the code session take more, within the cost limit |
| Stoa counts an abstention as wrong | ask them; the "plain accuracy" column | answer with `best_estimate` and show the doubt as a status |
| Stoa's key follows a generator convention that a person would not use | the two-key suites | state the convention, and offer the other value beside the answer |
| Wrong facts look certain | `VA`, the "right for the wrong reason" rate | confidence from witnesses only; a single-witness fact is never "confirmed" |
| The harness eats the weekend | the build order has a first number at hour 5 | stop at step 9; drop in the listed order |
| We tune to our own suites | the gap between the locked set and VAL | new seeds for the derived suites; 3 openings only |
| A live session is slow, or crashes on a large file | the crash gate with the 302,873-path sheet and the 343 MB IFC | time limits; ingest shows progress and a partial card |
| A licence blocks a later product | CubiCasa5K is CC BY-NC-SA 4.0; PyMuPDF and Ultralytics are AGPL | no cubicasa-trained weights in a product without a licence; pypdfium2 and RF-DETR as the permissive choices |

## 6. What would change this decision

- **The hint says "more of the public kind".** Then raise the weight of the vector cells, keep the named
  conventions as the default, and spend less on scans.
- **The hint says "scans and hand drawings".** Then the raster adapter and the model reader get most people,
  and the unknown path gets a best estimate on every answer.
- **Measurement 1: a frontier model fills marks on rasters with at least 90% exact counts.** Then no detector
  is trained.
- **Measurement 2: under 80% valid plans.** Then the code session becomes the main path, and the plan language
  stays only for the common questions.
- **Measurement 3: the vector path keeps its score on rasterised sheets.** Unlikely. It would mean that the
  raster adapter is cheap.
- **Stoa runs the hidden set as a file of answers, with no interface.** Then the evidence view loses weight,
  and plain accuracy leads.

## 7. Open questions for Stoa

`QUESTIONS-FOR-STOA.md` has the ranked list. The three that change the most:

1. How is an "I don't know" scored? Is a wrong number worse than an abstention, and does an answer count
   after the user gives a scale?
2. Which kinds of file are in the hidden set: scans, raster plans without a scale, US sheets in feet and
   inches, sets of several sheets?
3. Which counting rule applies when the question does not state one?

## 8. Where everything is

| Topic | File |
|---|---|
| The brief | `BRIEF.md` |
| What the host said, and what it changes | `HOST.md` |
| The dataset, and how the public score misleads | `DATASET.md` |
| The evaluation environment | `EVALUATION.md` |
| State of the art, with checked sources | `STATE-OF-THE-ART.md` |
| Solution designs compared; reinforcement learning, Rust, synthetic data | `SOLUTIONS.md` |
| The earlier research, checked claim by claim | `PRIOR-RESEARCH.md` |
| Questions for Stoa | `QUESTIONS-FOR-STOA.md` |
| The explainer video | `../video/`, see `../README.md` |
| Detailed reports: 5 on data, 11 on the state of the art, 7 idea lenses, 3 evaluation designs | `research/` |
| Scripts behind each measured number | `../analysis/` |
