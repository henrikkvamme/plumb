# Evaluation environment: the statistician's design

Date: 2026-11-14. Lens: what makes a number trustworthy.
Tags: **(M)** measured by me. **(S)** sourced, file named. **(E)** estimate.
Scripts: `stoa/analysis/eval-design-statistician/m08_cells_icc.py` (data) and `m09_power.py` (arithmetic).

## 1. Goals and non-goals

Goals:

1. Predict the hidden score as an interval, not as one public number.
2. Say if run B is better than run A, with a paired test on the same items.
3. Show where one hour of work adds the most predicted score.
4. Score the full answer record: value, evidence, abstention, confidence, cost, latency.
5. Keep one locked set that stays honest until Sunday.

Non-goals:

- No public micro average. A lookup scores 100% on cubicasa5k and a 300-line parser scores 99.63% on
  swiss_dwellings (S, `data/cubicasa.md`, `data/swiss.md`). That number separates nothing.
- No leaderboard of templates.
- No claim of precision that the data cannot give.

## 2. Three facts that shape the design

1. **The unit is the item, the cluster is the document.** 127,044 rows are 63,404 items after translation
   pairs merge (S, `data/questions.md`). With a mode prior as a proxy
   solver, the design effect is 1.75 on cubicasa5k (ICC 0.106), 3.27 on swiss_dwellings (ICC 0.130) and
   9.33 on ifc_models, where 687 items on 9 projects are worth 74 independent items (M, `m08`). A real
   solver that fails at ingest clusters more. I assume ICC 0.3 until a real run exists (E).
2. **The hidden score itself is noisy.** A session of 8 documents with 5 questions each has a sampling SD
   of 8.6 to 12.5 points at 70% true accuracy, for ICC 0.1 to 0.5 (M, arithmetic in `m09`). Two equal teams
   can differ by 15 points by luck. We can lower our own variance only by lowering failures of a whole
   document. So "documents with zero correct answers" is a first-class metric.
3. **Public gold is generator output, but the generators are public.** This is a risk for the solver and a
   gift for the evaluator. The oracles (CubiCasa5K `model.svg`, Swiss Dwellings geometry, IfcOpenShell)
   can compute gold for question types that Stoa did not publish. The grader may use them. The
   solver may not.

## 3. Partitions and suites

Partitions: `DEV` (open, read failures), `VAL` (score only, no row view), `LOCK` (3 openings).
Public rows keep `stoa/analysis/questions/split_v0.json` (sha256 `607f5dd4...`), where dev, val and test
become DEV, VAL and LOCK. Groups: cubicasa plan id, swiss site, IFC project (ifc_models and ifc_bench
merged), opening_design project. New items get a partition from sha256(seed:group) with the same seed.

Available on split_v0 (M, `m08`), groups/items in DEV, VAL, LOCK: cubicasa5k 2,873/25,657, 957/8,549,
957/8,551. swiss_dwellings 623/11,272, 210/3,765, 207/3,755. ifc_models 7/1,012, 4/308, 5/379.
ifc_bench 9/512, 4/188, 3/120. opening_design 1/20, none, 1/44. Median items per drawing:
cubicasa5k 9, swiss 18, ifc_models 12, ifc_bench 35 (M).

Suites. Each suite has the same sizes in VAL and in LOCK, except `oracle-new.unseen`, `fresh` and `session`,
which exist in LOCK only. DEV has the rest. Sizes are per partition.

| suite | what | gold from | documents | items | 95% half-width at 70% | paired MDE (d=0.10) |
|---|---|---|---|---|---|---|
| `core.cubicasa` | public items, one per translation pair | Stoa | 150 | 1,350 | 3.2 | 3.2 |
| `core.swiss` | 10 sampled items per floor | Stoa | 100 | 1,000 | 5.1 | 5.1 |
| `core.ifc` | all items of the projects, plus ifc_bench and opening_design | Stoa | 4 | 308 | 15.6 | 15.4 |
| `ladder` | 8 items per document in 4 input conditions | Stoa, unchanged | 100 | 800 per condition | 5.0 | 4.9 |
| `oracle-new.seen` | 6 new question families | oracle | 120 | 720 | 5.3 | 5.2 |
| `oracle-new.unseen` | 6 other new families, LOCK only | oracle | 120 | 720 | 5.3 | 5.2 |
| `resbim` | raster plan, dimension chains, no scale bar | sibling IFC | 60 | 240 | 8.0 | 7.9 |
| `wild` | scans, US CAD sheets, hand sketches | 2 people | 40 | 200 | 9.4 | 9.3 |
| `unanswerable` | no correct value exists on the document | construction | 60 | 120 | 9.3 | 9.2 |
| `session` | one document, then 6 questions, through our interface | LOCK items of the suites above | 12 | 72 | 16.7 | 16.5 |

Half-widths and MDE are in points: (M) arithmetic in `m09`, on (M) design effects for `core` and (E) design
effects of 1.3 to 2.5 for the new suites. MDE is the smallest true difference that a paired test finds with
80% power, when the two runs differ on a share d of the items.

Details:

- `core.cubicasa` uses only plans in the public CubiCasa5K val and test splits (769 plans in Stoa's set, S,
  `data/cubicasa.md`), so a model trained on the public train split is tested fairly. About 154 fall in each
  of VAL and LOCK (E).
- `ladder` conditions: C0 native file. C1 raster at 150 dpi with no text layer. C2 scan simulation
  (rotation by 90 degrees and by 2 degrees, blur, JPEG quality 40, grey). C3 the scale stripped (title block,
  scale bar and legend cropped). In C3 the gold of each area item becomes "abstain, reason `no_scale`". The
  gold of counts does not change. The pairs are exact, so the gap between conditions has a small interval.
- `oracle-new` examples: total area of all rooms labelled 'Bad' or 'WC' (the host's tile question), the
  largest room, rooms above 12 m², doors of apartment A, a label that is not on the sheet (gold 0), cubicasa
  doors on plans with open doorways, with the convention in the question. LOCK also holds `fresh`: the 213 public CubiCasa5K plans that Stoa
  did not use and the 206 IFC-Bench v2 rows on 6 models that Stoa did not use (S, `data/cubicasa.md`,
  `data/ifc.md`). Nobody opens these files before a LOCK opening.
- `resbim`: 500 PNG plans each have a sibling `_model.ifc` (M, file listing). They have no questions. Door,
  window and wall counts and wall lengths come from the IFC. The solver gets only the PNG.
- `wild` starts from `docs/research/data/wild-probe-questions.jsonl`: 50 rows on 27 documents, 5 of them
  "cannot be determined" (M). It grows to 200 items on 40 documents. Two people label each item. A third
  settles a conflict. At least 30% are compound questions.
- `unanswerable` sources: C3 items, the 176 public model-wide questions on one sheet (S,
  `data/questions.md`), a room count asked on an elevation or a cover sheet, a scan that is not a drawing.
- The other language of each `core` item runs as a consistency check only.

Questions per document: the variance-optimal number is m* = sqrt((C_d / C_q) (1 - rho) / rho). With an
ingest-to-query cost ratio of 15 (E) it is 10 to 11 at the measured ICC 0.106 to 0.13 and 6 at ICC 0.3
(M, `m09`). So the suites use 6 to 10 items per document and more documents.

## 4. Metrics and the headline number

**Item score.** s = 1 for a correct item, else 0. Count: exact. Area, length, volume: within 2% after unit
conversion. Text: section 9. Unanswerable item: section 7. e = 1 when the solver gave a value and it is
wrong.

**Cells.** A cell is (skill, input condition). 13 cells: lookup, count by label, count symbols, area on
vector files (V); model query (M); compound and schedule on vector files; count symbols and area on clean
rasters (R); lookup, count and area on scans (S); unanswerable. `suites/cells.json` maps each item to one cell.

**Per cell:** accuracy A_c, wrong-answer rate E_c, skill K_c = (A_c - P_c) / (C_c - P_c).
P_c is the better of two priors: the mode guess per family fit on DEV, and a blind model that sees only the
question. C_c is the ceiling, 1 minus the known convention and noise rate of the key.

**Headline: the predicted hidden score H.**

```
H(theta, g) = sum_c w_c(theta) * max(0, A_c - g * G_c)
w(theta)    = sum_k theta_k * W_k            W_k = cell weights of scenario k
theta ~ Dirichlet(8 * pi)                    pi = scenario prior in scenario.json
A_c   ~ Beta(1 + k_c / deff_c, 1 + (n_c - k_c) / deff_c)
g     ~ Uniform(0, 2)                        G_c = measured generalization gap of the cell (section 10)
```

The harness draws 40,000 samples and reports the median of H with the 5% and 95% quantiles. It also prints
the interval of the observed score on 8 documents with 5 questions.

Scenarios and prior (E, to be changed after the Saturday hint, with a logged reason):
same generator on new drawings 0.15; compound questions on clean files 0.35; tricky sheets (scans, rasters,
US CAD sets) 0.40; abstention heavy 0.10.

**Guard numbers, shown next to H:** weighted wrong-answer rate; the lowest cell skill; the share of
documents with zero correct answers; verified accuracy (section 8); cost and latency (section 6.5).

**Headroom table.** For each cell: w_c * (C_c - A_c), per scenario. It ranks the work.

## 5. Run record and comparison

```
stoa/eval/
  suites/<suite>/items.jsonl      one item per line
  suites/manifest.json            sha256 of each file, seed, split_v0 sha
  suites/cells.json  scenario.json  prices.json
  lock/                           LOCK gold, encrypted with age; the lead holds the key
  baselines/prior.json  baselines/blind.jsonl
  runs/index.jsonl                append-only, every run, also failed runs
  runs/<run_id>/run.json  answers.jsonl  scores.jsonl  ledger.jsonl  report.md
```

Item: `{item_id, suite, cell, partition, group, doc_path, condition, lang, question, type, gold:{value,
unit, tol}, unanswerable:{reason, request}|null, gold_evidence, twin_of, provenance, labellers}`.

Answer (the solver's output, one per item):
`{item_id, status: answered|abstained|needs_input, value, unit, confidence, reason_code, request,
steps:[{method: deterministic|model, name}], evidence:[{kind: mark|polygon|text|entity, page, xy|bbox|points,
text, guid}], cost_usd, ms}`.

Run: `{run_id, time, git_sha, dirty, solver_config_sha, model_ids, suites_manifest_sha, partition, note,
hypothesis, parent_run, cache_hits, H:{p05, p50, p95}, guards}`.

Commands:

```sh
uv run stoa-eval baselines                              # prior and blind runs, once
uv run stoa-eval run --part dev --suites all --solver http://127.0.0.1:8787 --hypothesis "..."
uv run stoa-eval compare <run_a> <run_b>                # paired, clustered, per cell
uv run stoa-eval predict <run> --scenario scenario.json
uv run stoa-eval gate <run> --against best              # VAL: prints accept or reject only
uv run stoa-eval lock-open --reason "..."               # needs the key, writes to runs/index.jsonl
```

The solver contract is `ingest(document) -> handle` and `ask(handle, question) -> answer`. It is our interface's contract too: Stoa gives one document and then a series of questions (S, `HOST.md`).
The harness copies each document to a random file name first. This stops lookups by site id or plan id.

`compare` prints, per cell: items, documents, A of both runs, the difference with a 95% interval, the
p-value, and the fixed and broken items. Then H of both runs on the same draws.

## 6. Statistics

### 6.1 Intervals

Cluster bootstrap over documents, 2,000 resamples, inside each suite. Below 10 groups (`core.ifc` has 4
projects) the bootstrap is not valid. The report then shows raw counts and the leave-one-project-out range,
and marks the cell "descriptive".

### 6.2 Two runs

Always paired on the same items. Test: sign-flip permutation on the per-document sum of (s_new - s_old),
10,000 permutations. A difference counts as real when p < 0.05 in the cell where the change was aimed
(named in `--hypothesis` before the run) and no other cell falls with p < 0.05.

### 6.3 Many runs

With K runs that have no real effect, the best one looks better by 1.16 SE (K=5), 1.54 SE (K=10), 2.04 SE
(K=30) and 2.50 SE (K=100) (M, simulation in `m09`). With an SE of 2.5 points on `ladder`, 30 tries invent
5 points. Rules:

- DEV: no limit. DEV numbers are never quoted as the expected hidden score.
- VAL: a ladder. `gate` accepts a run as the new best only when the paired gain in H is above 2 SE of the
  paired difference. It prints accept or reject and H rounded to 1 point. A rejected run leaves the old best.
- LOCK: three openings. The estimate of optimism from reuse is VAL minus LOCK at each opening.

### 6.4 What the sizes can detect

See the table in section 3. On `core.ifc`, `session` and opening_design no realistic change is detectable.
Read the flipped items there.

### 6.5 Cost and latency

`ledger.jsonl` has one line per model call or compute step: `{item_id|doc, phase: ingest|query, model,
tokens_in, tokens_cached, tokens_out, gpu_s, cpu_s, usd, ms, cache_hit}`. Prices come from `prices.json`
(API list prices; Verda A100 at $2.4 per hour, S, brief). A cache hit keeps the recorded cost. It is never zero.

- Cost per session = ingest of one document plus its 6 queries. Report the median, the p95 and the maximum,
  because cost has a long tail. Target: 0.10 per session (S, `HOST.md`, "10 cents to do both").
- Cost is not folded into H. `compare` shows the pair (H, cost). A change that moves the median above 0.10
  or the p95 above 0.30 (E) is rejected unless H rises by 3 points or more.
- Latency: ingest and query wall time, p50 and p95, cold cache, on the demo machine. An ingest above 120 s or
  a query above 30 s (E) is a timeout. A timeout or a crash scores 0 for all items of the document.

## 7. Abstention

Reason codes: `no_scale`, `not_on_sheet`, `not_in_model`, `illegible`, `ambiguous_convention`,
`not_a_drawing`. Requests: `calibrate_two_points`, `provide_scale`, `provide_model`, `provide_sheet`.

| item | answered, correct | answered, wrong | abstained |
|---|---|---|---|
| answerable | s=1 | s=0, e=1 | s=0, e=0 |
| unanswerable | not possible | s=0, e=1 | s=1 with the right reason, 0.5 with another reason |

- Headline accuracy uses s. The second view is Phi_1 = mean(s - e) and Phi_3 = mean(s - 3e), per cell.
  We do not know Stoa's penalty, so the gate needs s up and Phi_1 not down.
- Confidence: risk-coverage curve, Brier score and a 10-bin calibration table. The answer threshold is
  chosen on VAL for Phi_1.
- Assisted round: after `needs_input`, the harness gives the scale from the gold metadata and asks again.
  "Assisted accuracy" is a separate column. It rewards a useful request (S, `HOST.md`, fact 7).

## 8. Evidence

1. **Consistency, on every item, no gold needed.** A count equals the number of marks. An area equals the
   polygon area times the scale squared, within 0.5%. A sum equals the sum of the cited cells. A cited text
   exists at its box. An answer that fails is "unverifiable". Metric: consistent share.
2. **Grounded match, where the oracle has geometry** (`core`, `ladder`, `oracle-new`, `resbim`). Marks are
   matched one-to-one to gold objects. A point must lie in the gold box grown by 10 px. A polygon needs
   IoU of 0.5 or more. Report precision, recall and F1.
3. **Verified accuracy** VA_c = share of items with a correct value and evidence F1 of 0.9 or more (areas:
   IoU of 0.9 or more). A_c - VA_c is the "right for the wrong reason" rate. Two errors that cancel give a
   correct count today and a wrong count on the next sheet. A large gap raises G_c.
4. **Human check, on `session` only.** A teammate accepts or rejects each answer from the evidence view.
   Report the median seconds and the share of wrong answers caught. This is descriptive.

## 9. Free text

1. **Key value.** When the gold holds one value (a number with a unit, `5'-10 3/8"`, `AL-2/GL-2`, `20 MIN.`),
   a deterministic parser normalizes both sides: feet and inches to mm, units, case, punctuation. Numbers match
   within 2%. Codes match exactly.
2. **Fact list.** A long ifc_bench gold answer is split once into atomic facts, stored in the item. Score:
   fact recall, and s = 1 when recall is 0.8 or more with no contradicted fact. 14.4% of gold text answers
   say "not available" (S, `data/questions.md`). These are unanswerable items with `not_in_model`.
3. **Judge.** Only for the rest: a pinned model that sees the reference, with cached verdicts. Two people
   label 60 answers first. Report Cohen's kappa. Below 0.7 the free-text items leave H and get their own line.

## 10. How optimistic is the dev score?

Each gap is measured on pairs or on parallel suites:

| gap | measured as | when |
|---|---|---|
| template | A(`oracle-new.seen`) - A(`oracle-new.unseen`) | LOCK openings |
| input condition | A(C0) - A(C1), A(C1) - A(C2), paired | every run |
| source | A(`core`) - A(`resbim` or `wild`) for the same skill | every run |
| drawing | A(`core` VAL) - A(`fresh`) | LOCK openings |
| language | 100 `core` items translated to 5 unseen languages, paired | every run |
| evidence | A_c - VA_c | every run |
| reuse | A(VAL) - A(LOCK) | LOCK openings |

G_c is the largest gap that applies to the cell, with a floor of 2 points. The model in section 4 assumes
that the hidden set lies 0 to 2 such steps beyond our hardest measured suite. This is a rule of thumb.

Label-noise ceiling C_c: swiss doors are scored against two keys, the reference (a shared door counts once
per apartment) and the visible count, which agrees with the reference on 7.1% of floors (S,
`data/swiss.md`). cubicasa bedrooms have about 3.5% wrong keys (E in `data/cubicasa.md`). Items with
a convention conflict get weight 0 in H until Stoa confirms the convention.

## 11. Rules of use

1. The solver never reads CubiCasa5K SVG, Swiss Dwellings CSV, IFC-Bench CSV, `LICENSE.md` rows or a file name.
2. Learned parts train on DEV groups only, and on the public CubiCasa5K train split only.
3. Nobody reads VAL rows. VAL returns accept or reject and a rounded H.
4. LOCK opens three times: baseline, Saturday 20:00, freeze. Each opening is logged with the reason and the
   git sha. Nothing is tuned after the last opening.
5. The person who writes `oracle-new.unseen` and the LOCK `wild` items does not work on the solver.
6. State the hypothesis and the target cell before the run. Every run is logged, also the bad ones.
7. A change in a suite or in `scenario.json` bumps the manifest sha. Runs with different shas are not compared.
8. The pitch quotes H with its interval and LOCK numbers only.

## 12. Build order

1. Item schema, `core` from split_v0, scorer, run record: 1.5 h.
2. Prior and blind baselines, cluster bootstrap, `compare`: 1.5 h.
3. `ladder` renderer (C1, C2, C3): 1.5 h.
4. `oracle-new` for swiss and cubicasa, `unanswerable` items: 2.5 h.
5. `resbim` gold from the IFC siblings: 1 h.
6. `wild` to 200 items, two labellers: 4 person-hours, in parallel.
7. Evidence consistency and grounded match: 1.5 h.
8. Cost ledger, `session` runner with timeouts: 1 h.
9. Free-text scorer and judge check: 1.5 h.
10. `predict`, `gate`, report: 1 h.

Total about 17 hours of work (E). With 3 workers on disjoint files: pieces 1 and 2 in 3 hours, all pieces
in about 7 hours of wall time (E). After the Saturday hint: 1 hour for new weights and items.

## 13. Worked example

The inputs are invented (E). The outputs are computed by `m09_power.py`.

A solver has these VAL results (correct / items): lookup.V 196/200, count-label.V 190/200, count-symbol.V
150/200, area.V 170/200, model.M 180/200, compound.V 96/120, schedule.V 34/40, count-symbol.R 62/120, area.R
40/120, lookup.S 28/40, count.S 12/40, area.S 6/30, unanswerable 84/120. Gaps G_c are 1 to 15 points.

- Weighted accuracy with the central weights: 75.4%.
- With the uncertainty of the cells and of the scenario weights: 74.4%, interval 68.9 to 79.8.
- **H, with the gap discount: 66.6%, interval 56.7 to 75.8.**
- Observed score on 8 documents with 5 questions: median 67.5%, interval 45.0 to 85.0.
- Per scenario, without and with one gap step: same generator 85.8 and 80.6; compound on clean files 83.2
  and 75.6; tricky sheets 67.7 and 58.6; abstention heavy 63.6 and 54.7.
- Headroom w_c * (1 - A_c): unanswerable 3.4 points, area.R 3.3, compound.V 3.1, count-symbol.V 2.4,
  schedule.V 1.2. This is the order of work.

A change raises count-symbol.R from 62/120 to 84/120: 29 items fixed and 7 broken on 30 documents. Paired
z = (29 - 7) / sqrt(36 * 1.9) = 2.66, p = 0.008 with the design effect of 1.9. The change is real. The weighted
accuracy moves from 75.4 to 76.2, +0.8 points, because the cell has weight 0.045. So a decision is
made in the cell with a paired test. H ranks the work and reports the state.

## 14. Weaknesses of this design

1. The scenario weights and the range of g are estimates. They move H more than most changes do. The
   order of work is more stable than the level.
2. The design effects of the new suites are assumed. The harness must compute them from the first real run.
3. `oracle-new` gold follows the public annotations, with their conventions and errors.
4. `ladder` degradations are synthetic. A real scan differs from a blurred render.
5. `wild` is small. Its interval is about 9 points. Two labellers can share one wrong reading.
6. A compound question can fail at the join of two good skills. Cell weights do not model that.
7. IFC and opening_design results stay descriptive. Three LOCK openings leak some signal.
8. The free-text rules and the 0.5 score for a wrong abstention reason are our choices, not Stoa's.
9. The environment costs about 17 of the 33 hours that remain.
