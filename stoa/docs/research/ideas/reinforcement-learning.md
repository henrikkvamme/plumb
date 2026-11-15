# Ideas through one lens: reinforcement learning and checkable rewards

Written 2026-11-14 for the Stoa challenge. One lens only. I did not read the other lens files.

Tags: **MEASURED** = I measured or saw it myself in this session. **SOURCED** = from a named report in `stoa/docs/research/` or from the lead's brief. **ESTIMATE** = my judgement.

What I looked at myself (MEASURED, by eye): 12 drawings from 8 sources and 102 sampled questions from 5 sources. Points that shaped this file:

- `cubicasa5k/high_quality-470.png` is 843 px wide, with single rotated letters (H, K, E) as room labels.
- A 1921 finna blueprint is white on blue, with handwritten dimensions.
- A 1946 finna sheet has a site plan at 1/500 and a plan at 1/50, with dimension numbers (455, 280).
- `wikimedia/43489009.jpg` has no scale, but each room prints its size ("LIVING ROOM 17'-0" x 27'-0"").
- Two `habs` sheets are bridges, not floor plans.

## 1. The lens in one paragraph

The belief: a checkable answer is a reward, and a reward can train or select every part of the system that has no labels of its own. Those parts are discrete choices: which program answers a question, which scale is right, which method to trust, and when to say "I do not know". The lens gets stronger when we stop using Stoa's answer key as the reward. We can make rewards that need no key: geometry we render ourselves, and drafting invariants that hold on any drawing (a dimension chain must agree with the scale, rooms must tile the floor). Those rewards exist on the 8,600 drawings without questions (SOURCED, `data/wild.md`) and on the hidden set at inference time.

The strongest argument against it: where a label for the intermediate step exists, supervised learning is cheaper and more stable, and here those labels exist. Points come from the public SVG, DXF and IFC geometry. Programs come from the parsers that already match 99.6% to 100% of the public answers (SOURCED, lead). RL mostly improves pass@1 inside the training distribution and rarely adds a new skill (SOURCED, `sota/small-models-rl.md`, S11 and S13). A policy trained on the public reward learns Stoa's generator conventions, not drawing reading.

## 2. Concepts

### C1. StoaGym: the evaluation harness as an RL environment

**Pitch.** Build the reward before the policy: one episode is one document plus a series of questions, as in Stoa's own protocol.

**Mechanism.**
- `reset(document)` runs ingestion and records its cost and time. `step(question)` returns an answer record: value, marks, method per step, confidence, unknowns.
- Reward per step: +1 correct, -c wrong (c in 1, 3, 10), 0 for an abstention, +0.3 for an abstention with the right reason code and request, minus lambda times cost in euros.
- The episode reward subtracts ingestion cost once, so shared work per document is rewarded.
- Each run reports the template-mode baseline and a blind baseline.
- Splits hold out whole sources, templates, languages and IFC projects. The headline is the worst split.

**Needs.** No training. About 6 hours (ESTIMATE). 40 to 60 hand-made unanswerable questions for the reason codes.

**Criteria.** Accuracy: none directly. Evidence: it scores the fields the host asked for. Creativity: low. Cost: a number in every run.

**Hidden set.** The public micro average is 67% cubicasa with a 55.3% mode prior (SOURCED, lead). StoaGym replaces it with macro skill above the prior on held-out groups.

**Inference cost.** None. **Evidence view.** A trace per episode. **33 hours.** All of it fits. **Kill measurement.** None: every other concept needs it. **Risk.** We choose c and lambda ourselves. Stoa's rule is unknown, so report three values of c.

**RL versus supervised.** It is the condition for both.

### C2. Executor-reward program policy (question to DSL program)

**Pitch.** A small model writes a short typed query, a deterministic executor runs it on the compiled drawing, and the answer key is the reward.

**Mechanism.**
- Once per document: compile to a fact store (rooms with polygons and labels, openings, fixtures, texts, schedule tables, scale, storeys).
- Per question: the policy writes a program in a DSL of about 15 operators, such as `sum(area(rooms(label~"WC")))`. The executor returns the value and the facts it used.
- Signal 1 (supervised): we sample programs, run them, and an LLM writes the question in 11 languages. This gives gold programs, also for two-step questions such as the tile example.
- Signal 2 (reward): real public questions have an answer but no gold program. The reward is the executor match on Swiss DXF and IFC files, where the fact store is exact.
- A program must be right on every drawing of its question template. This removes programs that are right by chance on small counts.

**Needs.** The fact store. About 63,400 independent question-answer pairs (SOURCED, `data/questions.md`). Option A: GEPA on a prompt for a small API model, no GPU. Option B: SFT of a 2B to 4B text model on synthetic pairs (2 to 4 A100 hours), then GRPO (4 to 8 hours) (ESTIMATE).

**Criteria.** Accuracy: high where the fact store is right, because the residual error follows the store (SOURCED, `sota/agentic-program-synthesis.md`, S3). Evidence: the program is the reasoning, and every step is deterministic. Creativity: medium. Cost: one short model call per question.

**Hidden set.** The public templates need only a few tens of programs (ESTIMATE), so they teach little composition. Composition must come from the synthetic pairs. A question outside the DSL gives "no program", an honest unknown.

**Inference cost.** About €0.001 per question with a small API model, at an assumed 700 input and 80 output tokens (ESTIMATE).

**Evidence view.** One sentence per program step, with its facts lit on the drawing.

**33 hours.** DSL, executor and option A fit. Option B with GRPO is a stretch. **Kill measurement.** Write 40 hidden-style questions by hand (two steps, new wording, three languages). If a frontier model with a plain prompt writes a correct program for over 90%, drop option B. **Risk.** Spurious programs. A DSL too narrow for Saturday's hint.

**RL versus supervised.** RL is real here only for signal 2, because no gold programs exist. Signal 1 is supervised and covers more ground. GEPA beat GRPO with up to 35 times fewer rollouts (SOURCED, `sota/small-models-rl.md`, S18). GRPO adds under 2 points here (ESTIMATE).

### C3. Point-reward pointer (GRPO on a small VLM)

**Pitch.** A 2B to 4B VLM emits one point per object, the count is the number of points, and the reward scores the points.

**Mechanism.**
- Labels: object centres from Swiss DXF layers, IFC plan renders and our own restyled renders.
- Stage 1: SFT with LoRA to emit points per class on tiles.
- Stage 2: GRPO, 8 rollouts. Reward = Hungarian-matched point F1, plus a bonus when the count is exact, minus a format penalty.
- Once per document: all classes pointed on all tiles, stored as marks. Per question: no model call.

**Needs.** 5,000 to 10,000 tiles. One SFT run of 2 to 5 hours and one GRPO run of 4 to 10 hours on one A100 (SOURCED estimate, `sota/small-models-rl.md`). Under $40 (ESTIMATE).

**Criteria.** Accuracy: Perception-R1 went from 59.9 (SFT) to 75.6 (RL) on PixMo-Count (SOURCED, same report, S1). That is far from exact counts with a mean of 8.7 doors per plan (SOURCED, `sota/floorplan-cv.md`). Evidence: points on the sheet. Creativity: high, and Verda-trained. Cost: near zero per question.

**Hidden set.** Weak. Fine-tuned counters fall to 16% to 34% at twice the training counts (SOURCED, S5). A 1921 blueprint is far from every label we have.

**Inference cost.** One GPU pass per document, about €0.002 at $2.4 per hour and 3 seconds (ESTIMATE). **Evidence view.** Numbered dots.

**33 hours.** One SFT run and one GRPO run fit. No search over settings fits. **Kill measurement.** Train on CubiCasa-style tiles, test exact counts on 100 Swiss PNG sheets against a plain detector with the same labels. If the detector wins or ties, stop. I expect that (ESTIMATE). **Risk.** A model that learns "8 doors" as a prior. A 0/1 count reward is known to do worse than SFT (SOURCED, S6).

**RL versus supervised.** We have point labels, so this is a supervised problem. RL adds one real thing: it optimises the exact-count metric, which a detection loss does not. A threshold search on exact-count accuracy gives most of that gain in minutes (ESTIMATE).

### C4. Reward-shaped gate: answer, escalate once, ask, or refuse

**Pitch.** A small policy chooses among four actions per question, trained with a penalty for wrong answers.

**Mechanism.**
- Actions: answer from the fact store; escalate once to a frontier model on the cropped evidence; ask the user (two points of a known length); refuse with a reason code.
- State: only label-free features. Agreement between independent methods, the C6 consistency score, the size of the count, scale status, the share of the question that the program covered.
- Reward: the StoaGym reward.
- One threshold per action, fitted on held-out sources.

**Needs.** Logged runs of all methods on about 2,000 held-out questions. No GPU. 3 to 4 hours (ESTIMATE).

**Criteria.** Accuracy: it removes wrong answers, it does not add right ones. Evidence: the confidence and the reason the host asked for. Creativity: medium. Cost: it holds escalation to a few percent of questions.

**Hidden set.** The features hold on new styles because they measure agreement, not source. The thresholds drift under shift. Fit them on the worst held-out source and round toward caution.

**Inference cost.** Zero for the gate. One frontier call of about €0.01 to €0.03 when it escalates (ESTIMATE).

**Evidence view.** A confidence bar with its inputs: "2 methods agree, scale confirmed by 3 dimensions".

**33 hours.** All of it fits. **Kill measurement.** The risk-coverage curve on a held-out source. If refusing the lowest 20% does not halve the errors, a fixed rule is enough. **Risk.** Parsers make few errors on the public set, so the errors to learn from must come from the C5 sets.

**RL versus supervised.** Offline we can run every action on every question, so all outcomes are known. This is cost-sensitive classification. A bandit adds nothing. The lens gives the reward shape, not the algorithm.

### C5. Tricky-drawing self-play: a generator bandit against the solver (unusual)

**Pitch.** A generator earns reward when the solver fails on a drawing whose answer we know exactly, so it finds our weak points before Stoa does.

**Mechanism.**
- Seeds are real geometry with exact answers: Swiss Dwellings polygons, IFC models, CubiCasa SVG.
- About 25 knobs: wall hatch, line weight, symbol library, label language, rotation, two views on one sheet, no scale bar, dimension chains only, feet and inches, a schedule table, rasterising, blueprint inversion, paper noise, low resolution.
- Each knob setting is an arm. Thompson sampling raises arms where the solver fails and a validity check passes.
- Validity: the answer must stay derivable. With the scale removed, the right answer becomes "need a scale", which is also checkable.
- Outputs: a ranked list of failure modes, a hard evaluation set for C1, C4 and C7, and training tiles.

**Needs.** A renderer. A 90-line prototype already wrote DXF, PDF and PNG with exact labels (SOURCED, `sota/synthetic-data.md`). No GPU. About 8 hours (ESTIMATE).

**Criteria.** Accuracy: indirect, but aimed at the hidden set. Evidence: none directly. Creativity: high. Cost: none at inference.

**Why it could win.** It is self-play that converges in hours, because the generator policy is 25 numbers. It aims at what the host said decides the score: tricky drawings.

**Hidden set.** This is the only concept that makes hidden-like data. Limit: synthetic alone transfers weakly (63.8 against 69.4 edge mAP for real data, SOURCED, `sota/synthetic-data.md`, S2). It will not produce a 1921 hand-drawn sheet.

**Inference cost.** None. **Evidence view.** For the pitch: one floor in 12 styles, with pass or fail.

**33 hours.** A knob bandit fits. A neural generator does not. **Kill measurement.** Render 50 Swiss floors in 6 styles by hand and run the first solver. If accuracy does not vary by style, a fixed grid replaces the bandit. **Risk.** The generator finds unreadable drawings, not tricky ones. A person must look at the top 20 failures.

**RL versus supervised.** No supervised form exists: the target (our own failures) moves as the solver changes.

### C6. Consistency reward at inference: search over readings with no answer key (unusual)

**Pitch.** Generate several candidate readings of a document and keep the one that best satisfies drafting invariants, which act as a reward without labels.

**Mechanism.**
- Scale candidates: the title-block ratio, the scale bar, each dimension chain, printed room sizes, a door-leaf width prior of 0.7 to 1.0 m, the sheet format. Candidates are per view, because one sheet can hold several scales (MEASURED: 1/50 and 1/500 on one finna sheet).
- Room candidates: polygons from vector walls or from raster segmentation.
- Reward terms, each between 0 and 1: dimensions reproduce within 1%; rooms do not overlap and tile the outline; door widths are plausible; printed areas match computed areas where both exist; printed totals match row sums; symbol count equals schedule count where both exist.
- Deterministic beam search picks the best joint reading. Confidence is the reward and the margin to the second reading.
- A failed term is the reason code, such as "2 scale candidates disagree (1:50 and 1:100)".

**Needs.** No labels, no training. Term weights fitted on Swiss and IFC sheets with the scale hidden. 10 to 12 hours (ESTIMATE).

**Criteria.** Accuracy: it protects the 2% area rule, where a wrong scale is a total miss. Evidence: the strongest of all concepts. Creativity: high. Cost: CPU only.

**Why it could win.** It gives the confidence score and the "give us a scale" request from one mechanism, and next year's models do not replace a check.

**Hidden set.** The invariants are physics and drafting practice, not Stoa conventions. They hold for a US sheet in feet (MEASURED: the wikimedia plan prints 17'-0" x 27'-0", which calibrates it with no scale bar). On a sketch with no dimensions they fail, and the output is the request the host wants.

**Inference cost.** Zero model calls after ingestion.

**Evidence view.** The chosen scale with the three dimension lines that confirm it, each with "drawn 4.55 m, computed 4.53 m".

**33 hours.** Scale candidates and four terms fit. Joint room search on scans does not. **Kill measurement.** On 100 Swiss sheets, hide the scale text and the bar. If door-width and outline terms recover 1:100 on fewer than 80, the concept needs printed dimensions. Then check on 20 `opening_design` plans that the dimension-chain scale equals the stated scale. **Risk.** OCR of dimension text on scans. A wrong reading can be self-consistent.

**RL versus supervised.** No labels exist for unseen drawings, so supervised learning has nothing to fit. This is where a reward adds the most.

### C7. Agents as the policy: reward-driven search over the solver code

**Pitch.** Coding agents propose changes to the compile step and the solver, and StoaGym accepts only changes that win on held-out groups.

**Mechanism.**
- A candidate is a commit. Its reward is a vector: macro skill above prior on the worst split, the C5 hard set, cost, refusal quality.
- Keep the Pareto front. Mutations come from an agent that reads failed traces.
- A locked split is never shown to an agent. It is run at most 5 times.
- Generator conventions go in a named adapter, not in the core. Example: the Swiss key counts a shared door once per apartment, so visible doors match on only 7.1% of floors (SOURCED, lead). The core counts visible doors. The adapter can report the other convention.

**Needs.** C1. Many agents, which we have. No GPU.

**Criteria.** Accuracy: the gain is the acceptance rule. Evidence: neutral. Creativity: medium. Cost: the reward vector stops gains bought with API calls.

**Hidden set.** Search against a public key finds generator quirks first. That is reward hacking by the team. The guards are the held-out splits, the C5 set and the adapter.

**Inference cost and evidence view.** None. **33 hours.** Fits. One person keeps the gate. **Kill measurement.** Run one candidate twice. If the reward moves more than the gain we accept, the gate decides nothing. Small sources need about 12 points to show a difference (SOURCED, `sota/eval-methodology.md`). **Risk.** Agents tune to the open splits within hours.

**RL versus supervised.** Black-box search. No gradient method fits a pipeline of parsers.

### C8. Learned zoom policy (include only to reject)

**Pitch.** A policy learns where to crop a large sheet before it reads.

**Mechanism and needs.** State: a thumbnail and the question. Action: a crop box. Reward: answer correct, minus tokens. GRPO on a 7B VLM with multi-turn rollouts needs more than 20 A100 hours for one run (ESTIMATE).

**Criteria and hidden set.** Crop-and-zoom agents give marginal or negative gains at higher token cost (SOURCED, `sota/agentic-program-synthesis.md`, S4). The work is per question, so questions on one drawing share nothing.

**What replaces it.** Tile the sheet once at ingestion, index text and marks by position, and crop to the facts that the program touched.

**Kill measurement.** Text recall of fixed tiling on 20 `opening_design` sheets against the PDF text layer. Above 98%, zoom has nothing to add. **Risk.** Time lost on good demos with weak evidence.

## 3. The system I would build from this lens

Rewards choose and refuse. They do not perceive. Perception is deterministic parsing of vector data and models, and a supervised detector plus a text reader on rasters. Three rewards do the rest: the key reward (offline, held-out groups), the generator reward (offline, finds failures) and the consistency reward (online, no key).

```
OFFLINE
  generator bandit (C5) --renders--> hard sets --+
  public key, held-out groups -------------------+--> StoaGym (C1) --> accept or reject commits (C7)
                                                 +--> fit gate thresholds (C4), fit C6 weights

ONLINE, once per document (target: under EUR 0.05)
  file --> parse: IFC | DXF | vector PDF | raster (detector marks + text read on fixed tiles)
       --> candidates: scales per view, room polygons, tables
       --> consistency reward (C6) --> fact store + confidence per fact + failed checks

ONLINE, per question (target: under EUR 0.002)
  question --> program (C2, small model) --> executor (deterministic) --> value + used facts
           --> gate (C4): answer | escalate once | ask for a scale | unknown + reason
           --> answer record: value, marks, steps, method per step, confidence, unknowns
```

Order of work, in hours from now (ESTIMATE):

1. Hours 0 to 6: StoaGym, the fact-store schema, the DSL and the executor.
2. Hours 3 to 12: parsers into the fact store. Six restyles of 50 Swiss floors by hand (the C5 seed).
3. Hours 8 to 18: scale candidates and four consistency terms (C6). GEPA on the program prompt (C2, option A).
4. Hour 14 (Saturday midday): read Stoa's hint. Add DSL operators and generator knobs for it.
5. Hours 16 to 24: the gate (C4). The generator bandit, if the restyles showed that style matters.
6. Hours 20 to 28, stretch: one SFT run and one GRPO run of the pointer (C3) on Verda, as a second opinion for the gate.
7. Hours 28 to 33: freeze. Run the locked split once. Rehearse a live session on 10 unseen files.

Cut first, in this order: C8 (never start), C3 GRPO, C2 option B, the bandit in C5 (keep the restyle grid), room search in C6. Never cut C1, the gate or the scale search.

## 4. Where this lens is wrong

- **Perception on rasters.** A 1921 blueprint needs a better detector and text reader. No reward creates that in 24 hours. Learned perception or frontier-model reading wins there.
- **Where labels exist.** For points and programs, supervised learning on the same labels is faster and more stable. GPU hours on a detector with more data beat GPU hours on GRPO.
- **A small, human-run evaluation.** A gain of 2 points from a tuned policy is invisible on a few tens of questions. A crash on one file is a zero. Robust engineering beats optimisation.
- **Free-text answers.** `ifc_bench` has no checkable reward. An LLM judge is not a verifiable reward, and the best published agent scores about 56% (SOURCED, lead). A code agent over IfcOpenShell is the better tool.
- **Conventions.** A reward teaches the generator's convention without saying so. A person who asks "how many doors" on a hidden sheet means visible doors.
- **Self-consistency is not truth.** A wrong reading can satisfy every invariant.

## 5. Ten things to measure first

1. **A frontier model with a plain prompt on 40 hand-written hidden-style questions, given the fact store as JSON.** Settles whether a trained question policy (C2 option B) is needed.
2. **Solver accuracy on 50 Swiss floors in 6 hand-made styles.** Settles whether the C5 bandit is worth building.
3. **Scale recovery on 100 Swiss sheets with the scale text and bar hidden.** Settles whether the C6 priors work without printed dimensions.
4. **Dimension-chain scale against stated scale on 20 `opening_design` plans.** Settles whether C6 works on real CAD with several scales per sheet.
5. **Risk-coverage curve of method agreement on a held-out source.** Settles whether the gate (C4) learns anything beyond a fixed rule.
6. **Detector against zero-shot pointer on 100 Swiss PNG sheets, exact count.** Settles whether C3 starts at all.
7. **Run-to-run variance of the StoaGym reward for one fixed system.** Settles the smallest gain that C7 may accept.
8. **Text recall of fixed tiling on 20 `opening_design` sheets and 20 scans.** Settles C8 and the tile size for ingestion.
9. **Cost and time of ingestion for one A1 vector sheet and one scan.** Settles whether a frontier model fits in ingestion inside €0.10.
10. **Share of 60 unlabelled scans where a person can answer one count and one area question.** Settles how much effort the "unknown with a request" path deserves.
