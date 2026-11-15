# Solution designs, compared

Date: 2026-11-14. Author: the lead. Labels: **M** measured, **S** sourced (report named), **E** estimate.
No design in this file has run on a drawing yet. The ratings are judgements from the evidence. Section 7
lists the measurements that turn them into numbers.

## In short

- Seven agents searched for solutions, each through one lens and without sight of the others: geometry,
  learned perception, agents with tools, reinforcement learning, verification first, the hidden-set adversary,
  and ideas from other fields. Their reports are in `research/ideas/`.
- All seven arrived at the same skeleton: **read a document once into typed facts with their place on the
  sheet; let a small model write a short plan; let deterministic code compute the answer from the facts.** The
  lenses differ in what fills the facts when the file has no structure.
- No single family wins. Geometry is exact and almost free, and it is empty on a scan. A trained detector is
  cheap, and it fails exact counts on large floors and on unseen styles. A frontier model reads text well and
  counts badly. An agent loop per question costs 10 to 30 times the 10-cent target for a document with 10
  questions (E).
- Reinforcement learning: use the reward, not the gradient. The evaluation harness is the environment. A
  consistency reward at inference is the scale check. Do not train a policy with GRPO this weekend.
- Rust core: not this weekend. The file readers that decide accuracy are Python libraries, and the time and
  the cost are in perception and model calls, not in geometry.
- Synthetic data: first as a test suite with exact keys (transforms of real sheets). Second as extra training
  data for a detector. Never as the only training data.

## 1. How we searched

Each lens agent got the brief, the measured dataset facts and the host's statements. It opened drawings,
measured where it could, and wrote: 6 to 9 concepts, one system, where the lens is wrong, and ten things to
measure first. The agents did not read the prior research and did not see each other's files.

| Lens | Report | Its system in one line |
|---|---|---|
| Geometry and structure | `research/ideas/geometry-compiler.md` | A four-layer sheet graph. "The compiler never guesses silently, and the query engine never perceives." |
| Learned perception | `research/ideas/learned-perception.md` | Small vision models fill a scene graph. A count comes with its odds. Vector files label their own rasters. |
| Agents with tools | `research/ideas/agentic.md` | A "drawing notebook" per document. The model writes plans, never values. One capped escalation. |
| Reinforcement learning | `research/ideas/reinforcement-learning.md` | "Rewards choose and refuse. They do not perceive." |
| Verification first | `research/ideas/verification-first.md` | Every answer has a proof object. A kernel with no model checks it. |
| Hidden-set adversary | `research/ideas/hidden-set-adversary.md` | General skills on unseen sheets: read, find the scale per view, read a schedule, say what is missing. |
| Other fields | `research/ideas/wildcard.md` | Ideas from compilers, accounting, chip verification, GIS and pathology. |

**A caution about the agreement.** The seven lenses agree, but they are not seven independent proofs. All
got the same facts from me, including "structure beats pixels" and the host's wish for deterministic methods.
The agreement shows that the design follows from those facts. It does not show that the facts are complete.

## 2. What every lens agrees on

1. **Compile once per document.** Stoa gives one document and then a series of questions (S, `HOST.md`). The
   public set has a median of 18 to 36 questions per drawing (M). Work per document is shared.
2. **The model never states a number.** A model given layout JSON scores 81%, and the same model given the
   image scores 31% (S, `research/sota/vlm-on-drawings.md`; the benchmark has single-room layouts). The best
   frontier model gets the exact door count on 39% of plans, and room areas miss by about 43% on average (S,
   same report). So a model selects and plans. Code computes.
3. **A count is the number of marks.** Each counted object is a mark on the sheet. The answer and the evidence
   cannot disagree.
4. **A scale belongs to a view, and it has witnesses.** The ratio text, the scale bar, each dimension chain,
   printed room sizes. 53% of the opening_design pages with a scale string print 2 or more scales (M, adversary
   lens). "1:100 (A3)" is true only at the A3 size, which a raster does not have.
5. **Printed before computed before measured.** A schedule cell or a printed area beats a polygon, and a
   polygon from vector paths beats pixels.
6. **A missing fact is a typed unknown with a request.** "No scale in this view. Click two points of a known
   length." The host asked for exactly this (S, `HOST.md` row 7).
7. **Confidence comes from checks, not from the model.** Two witnesses agree, a total equals its rows, a
   dimension chain sums to its overall dimension.
8. **The counting rule is a parameter, shown with the answer.** Stoa's swiss door key counts a shared door
   once per apartment, and it equals the visible doors on 7.1% of floors (M). No rule is "the truth".
9. **Two tiers, not a cascade.** More than two tiers gave no gain in 118 of 135 comparisons (S,
   `research/sota/agentic-program-synthesis.md`).
10. **Hidden-like tests come from transforms of solved sheets.** Rasterise, drop the text layer, rotate, crop
    the scale. The key stays known.

## 3. The design families

| | Family | What answers the question |
|---|---|---|
| A | Frontier model on the image | one vision call per question, the model writes the value |
| B | Agent loop per question | a strong model calls tools (crop, zoom, OCR, code) until it has an answer |
| C | Source parsers | one hand-written parser per public source, tuned to its generator |
| D | Trained perception | a detector or a small vision model, trained on public labels, then arithmetic |
| E | Fact compiler with typed plans | compile once to facts; a small model writes a plan; code computes |
| F | Trained policy (RL) | a model trained with the answer key as reward: a pointer, or a plan writer |
| G | Capped code agent on the fact store | one model session with code execution, for questions outside the plan language |

### How they compare

The four criteria weigh 25% each. Generalisation to the hidden set is the fifth row, because the host said
that it decides (S, `HOST.md` row 1). Ratings: ++ strong, + good, 0 neutral, - weak, -- fails. All E, with the
evidence named.

| | A model on image | B agent loop | C source parsers | D trained perception | E fact compiler | F trained policy | G capped code agent |
|---|---|---|---|---|---|---|---|
| Accuracy, public set | - | 0 | ++ | + | ++ on structured files | + | + |
| Accuracy, hidden set | - | 0 | -- on new structure | - on new styles | + where facts exist | - | + on model files |
| Verifiable in seconds | -- | - | + | + | ++ | 0 | 0 |
| Creativity | -- | - | -- | 0 | + | + | 0 |
| Cost per document with 10 questions | $0.06 to $0.12 | $1 to $3 | about 0 | about $0.002 | $0.03 to $0.06 | about $0.002 | $0.07 to $0.11 per use |
| Repeatable | no | no | yes | yes | yes, with recorded plans | yes | with a record |
| Fits in the weekend | yes | yes | yes | partly | yes for vector and IFC, partly for raster | no | yes |

Evidence for each rating:

- **A.** Exact door and window counts: 0.16 to 0.39 across frontier models. Text and labels: 0.76 to 0.95 (S,
  AECV-Bench, `research/sota/vlm-on-drawings.md`). The answer has no marks, so a person must count again.
  Cost: one image is about $0.006 on Sonnet 5.5 and $0.012 on Opus 5.5 (E from the price table).
- **B.** A naive Opus loop with 15 tool calls costs about $0.31 per question, and a Sonnet loop about $0.11 (E,
  agent lens). Crop and zoom loops give marginal or negative gains on counting (S,
  `research/sota/agentic-program-synthesis.md`). On IFC questions an iterating code agent beats one-shot code by
  about 37 points (S, same report): that is family G, not B.
- **C.** 100%, 99.63% and 99.8% on the three large public sources (M, `DATASET.md`). The parsers read what
  Stoa's renderers wrote: layer names, fill colours, fixed label positions. The hidden files have "the same
  extensions" and "content structured differently" (S, `HOST.md` row 2). A style-free room rule already falls
  to 89.9% on the same swiss sheets (M, geometry lens).
- **D.** A detector that misses 3% and invents 3% gets the exact door count on about 65% of cubicasa plans and
  39% of swiss floors (E, model on M count distributions, perception lens). Fine-tuned counters fall to 16% to
  34% at twice the training counts, and open-vocabulary detectors are near 0 mAP50 zero-shot on CubiCasa (S,
  `research/sota/small-models-rl.md`, `floorplan-cv.md`). Room masks miss the 2% rule on small rooms: 1 px is
  16.9 mm on a swiss PNG, and 1 px per side is 3% of a small bathroom (M and arithmetic).
- **E.** Exact where facts exist: vector PDF, DXF, IFC, schedules, printed values. One third of the public
  questions are on such files (M). The plan is the explanation, and each step lights its objects on the sheet.
  Cost: one Sonnet call per document (about $0.05) and one Haiku plan per question (about $0.0003) (E, agent
  lens; the prices agree with the current table). Weak where the compile step is perception: scans and hand
  drawings. There the store is thin, and the design says so.
- **F.** A right-or-wrong count reward does worse than supervised training. Point-level rewards help (59.9 to
  75.6 on a counting benchmark), but that is far from exact counts. Prompt optimisation beat GRPO with up to
  35 times fewer rollouts (S, `research/sota/small-models-rl.md`). A policy trained on Stoa's key learns
  Stoa's generator conventions.
- **G.** The best published agent on IFC-Bench v2 scores 56.0% with a model as judge (S,
  `research/sota/bim-cad-tooling.md`). It is the only path for a question that nobody planned for. A value
  from it without marks on the sheet is "unverified".

### By hidden-set scenario

The scenarios and their weights are estimates from `research/data/wild.md`.

| Scenario | Weight (E) | Best family | Why |
|---|---|---|---|
| Harder questions on released files that have no public question | 0.45 | E, with D or A as the filler on rasters | new templates cost nothing when no template is coded. Compound questions need a plan |
| New, tricky files | 0.35 | E for structure, A or D for perception, the unknown path for the rest | the worst case must be a correct "I need X", not a confident wrong number |
| More public templates on new drawings | 0.20 | C | generator-matched parsers at 99% beat general machinery at 85% |

The fact compiler holds in all three, because its vector and IFC adapters are the source parsers made
general, and a named convention can reproduce Stoa's key where that is wanted.

## 4. Where the lenses disagree

| Question | Positions | How to settle it |
|---|---|---|
| What fills the facts on a raster? | Perception lens: a trained detector with a count posterior. Agent lens: a proposer with high recall, and a small model that says yes or no per numbered candidate. Adversary lens: cluster repeated shapes without a model, name each cluster once. | Measurement 1 and 4 in section 7 |
| Closed plan language, or code? | Geometry and agent lenses: a closed set of about 15 operators. Wildcard lens: the model writes an extractor per drawing family, and a test suite accepts it. | Measurement 2 |
| Abstain, or always give a number? | Adversary lens: a typed unknown. Verification lens: always give a number when one exists, and let the status carry the doubt. | Ask Stoa. Until then: abstain with a `best_estimate` |
| Copy Stoa's conventions? | Adversary lens: wasted work. Scenario 3 says it wins. | Keep the convention as a named switch. Default to what a person would count |
| Raster areas | Geometry lens: an interval, often outside 2%. Perception lens: snapped room polygons. Equation idea: solve the geometry from printed dimensions. | Measurement 5 |

## 5. Henrik's three ideas

### Reinforcement learning

The RL lens argued against most of itself, with sources.

| Use of a reward | Verdict | Reason |
|---|---|---|
| The harness as an environment: one episode is one document and its questions, the reward includes cost and a penalty for a wrong answer | **Yes, build first** | it is the evaluation environment. Every other use needs it |
| A consistency reward at inference: keep the reading that satisfies drafting invariants (dimensions agree with the scale, rooms tile the floor, a total equals its rows) | **Yes** | no labels exist for unseen drawings, so supervised learning has nothing to fit. This is where a reward adds the most |
| Reward-driven search over the solver code: agents propose commits, the harness accepts on held-out groups | **Yes, as the working method** | it is how the team works already. The guard is the locked set |
| A gate that learns answer, escalate, ask or refuse | Use the reward shape, fit thresholds | every action can be run offline on every question, so this is cost-sensitive classification |
| A generator that earns reward when the solver fails ("tricky-drawing self-play") | Later | start with a fixed grid of restyles. Build the bandit only if style matters |
| A plan writer trained with the executor as reward | No GRPO. Prompt optimisation at most | a frontier model with a plain prompt probably writes the plans. Measurement 2 |
| A small vision model that points, trained with GRPO | No | we have point labels, so it is a supervised problem. A threshold search on exact-count accuracy gives most of the gain in minutes (E) |
| A learned zoom policy | No | over 20 A100 hours for one run (E), and the work is per question |

Where a label for the middle step exists, supervised learning is cheaper and more stable, and here the labels
exist. A gain of 2 points from a tuned policy is invisible on a few tens of hand-run questions.

### A Rust core with Python for training

**Not this weekend.** The evidence is in `research/sota/stack-rust-python.md`:

- The readers that decide accuracy are IfcOpenShell (C++ with Python bindings), ezdxf, PyMuPDF or pypdfium2,
  and shapely. Rust has no IFC reader of that depth, and the Rust `dxf` crate drops HATCH entities with no
  error.
- Coding agents resolve fewer issues in Rust than in Python (15.9% against 52.2% in the cited benchmark). Our
  workers are agents.
- Speed is not the limit. Loading 127,044 rows takes 0.15 s, and the swiss parser needs no model (M). The
  time and the cost of a session are in perception and in model calls.

Where Rust can pay later: one hot geometry kernel behind PyO3, for example a planar arrangement of 300,000
vector paths (one opening_design sheet has 302,873, M), if a profile shows that it sets the ingest time. The
rule: profile first, then port one function, and test the port against the Python version on the scorer's
vector file. Stack for now: strict Python for the harness, the compiler and the solvers; the TypeScript starter
for the interface; a small Python service next to it, as the repository rules ask.

### Synthetic data

| Use | Verdict | Reason |
|---|---|---|
| Transforms of real sheets with a known effect on the key (rasterise, drop text, rotate, crop the scale, erase k symbols, rescale the geometry) | **Yes, first** | thousands of hidden-like items in hours, with exact keys. It is the `ladder` suite |
| New questions on public geometry (the tile question, the largest room) | **Yes** | the `compound` suite. Keys from the public originals, read by the harness only |
| Restyled renders of real geometry as extra training data for a detector | Yes, if a detector is trained | the vector file labels its own raster for free |
| A full sheet generator with new styles and languages | Later | 6 hours (E). Synthetic damage is kinder than a 1926 pencil sheet |
| Synthetic data as the only training data | No | synthetic alone transfers weakly: 63.8 against 69.4 edge mAP for real data (S, `research/sota/synthetic-data.md`) |

Degrade with geometry-preserving operations only. The default pipeline of a common augmentation library warps
the sheet, and a warp breaks every area key (S, same report).

## 6. Ranking

1. **E, the fact compiler with typed plans**, as the spine. It serves all four criteria and all three
   scenarios, and its parts are useful alone: the scale witnesses, the schedule reader and the unknown path
   work on any file.
2. **G, one capped code session**, as the second tier for questions outside the plan language, and for IFC
   free text. Budget: one per document.
3. **A as a reader inside the compile step**, not as the answerer: one call per raster document for text,
   views and tables, and yes or no decisions on numbered candidates.
4. **D, a trained detector**, only if measurement 1 says that a frontier model cannot fill the marks on
   rasters. Train it leak-free on the public CubiCasa5K train split and on swiss geometry, and judge it on a
   source that it did not see.
5. **C, source parsers**: not built as such. The existing probes become the first adapters of E and the
   `oracle-parser` baseline of the harness.
6. **B and F**: not built.

The full recommendation, with risks and the build order, is in `DECISION.md`.

## 7. Ten measurements that turn judgement into numbers

Merged from the seven "ten things to measure first" lists. Each one runs in the evaluation environment.

| # | Measurement | Decision it settles |
|---|---|---|
| 1 | Zero-shot counting with Haiku 5.5, Sonnet 5.5 and Opus 5.5 on 200 cubicasa plans from the public val and test splits: exact match per template against the `prior` baseline, and mark precision and recall | whether to train a detector at all, and for which classes |
| 2 | Plan validity on 40 hand-written hidden-style questions (two steps, new wording, 5 languages) against hand-made perfect fact stores | closed plan language or agent-first; Haiku or Sonnet as planner. Under 80% valid plans, the closed language is wrong |
| 3 | The vector path on 50 swiss sheets as given, then rasterised at 150 dpi with no text layer | how much effort the raster path gets. If 99% falls under 30%, the raster adapter is the project |
| 4 | Proposer recall and exact-count rate of "marks by id" on 50 plans, against a detector after 1 hour of training | which one proposes and which one judges |
| 5 | Scale from dimension chains on 30 ResBIM plans against the sibling IFC: spread of the witnesses | whether raster areas can meet 2%, or the honest answer is a range |
| 6 | The closed-path room rule on real CAD sheets (5 opening_design plans, 71 ifc_models plans). Baseline 89.9% on swiss | whether vector rooms are general or an artifact of one renderer |
| 7 | Schedule row counts on 10 schedules without questions, by eye | the schedule reader as built, or a redesign |
| 8 | One model read of 10 historic scans: text recall against a person's eye, and the cost per sheet | the model tier and the 10-cent budget on scans |
| 9 | False-abstention rate on 100 answerable public items, and correct abstention on 30 unanswerable ones | the confidence thresholds |
| 10 | Crash and timeout rate on 300 random files of all sources, with the 302,873-path sheet and the 343 MB IFC | the time limit per file. A crash is a zero for the whole document |

Measurements 1, 2 and 3 come first. They decide the three largest open choices, and each takes under 2 hours
once the harness has its first suites.
