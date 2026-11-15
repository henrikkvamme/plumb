# The evaluation environment

Status: design, decided by the lead on 2026-11-14. Nothing here is built yet. Build it before any solver.

Three agents designed the environment independently, each from one point of view: a statistician, a red team
("I am the Stoa engineer who builds the hidden set") and a harness engineer. Their full designs are in
`research/eval/design-statistician.md`, `design-red-team.md` and `design-harness-engineer.md`. This file is the
one design that we build. Section 12 lists what I took from each and what I dropped.

Labels: **M** measured (script named, or a data report), **S** sourced, **E** estimate, **D** our choice.

## In short

- The public score is not the target. A lookup scores 100% on cubicasa5k, a 300-line parser scores 99.63% on
  swiss_dwellings, and IfcOpenShell rules match 3,057 of 3,062 ifc_models rows (M, `DATASET.md`). We keep the
  public rows only as a regression floor.
- The harness speaks Stoa's protocol: one document under a neutral name, then a series of questions (S,
  `HOST.md` row 9). The same HTTP contract serves the later UI.
- The harness has two sides with a wall between them. The key side may read every public annotation to build
  new, harder questions with exact keys. The solver side sees one file and nothing else.
- The headline number `H` is a weighted mean over 9 cells (skill x kind of input). Each document weighs the same.
  A wrong answer costs a point. A useful "I do not know" on an unanswerable question earns one.
- A real hidden session is noisy: 8 documents with 5 questions each has a standard deviation of 8.6 to 12.5
  points at 70% true accuracy (M, arithmetic). So the share of documents with zero correct answers is a
  first-class number. A crash on one file loses more than a weak cell.
- Every change is judged as a paired difference on the same items, with an interval. Small suites say so.
- A first trusted number takes about 5 hours of wall time with 2 workers. The full environment is about 20
  hours of work.

## 1. What the environment must do

1. Rank two builds of the solver on the same items, with a statement of noise.
2. Move like the hidden score: hard questions, tricky drawings, one document at a time.
3. Score the whole answer record: value, evidence, method, confidence, unknowns, cost and latency.
4. Make each known shortcut worthless, so that a solver cannot cheat by accident.
5. Keep one locked set honest until Sunday.

It does not give a pitch number from public rows. It does not test the UI.

## 2. The contract

One schema file, `stoa/eval/contract/contract.schema.json`, is the source. The Python structs of the harness
and the Effect Schema of the app are generated from it.

```
POST /ingest     {session_id, file: "doc-3fa9c1d2e0b4.pdf"}                 -> IngestRecord
POST /ask        {session_id, question_id, question}                        -> AnswerRecord
POST /calibrate  {session_id, scale: {ratio: "1:100"} | {p1, p2, length_m}} -> IngestRecord
```

`AnswerRecord`:

```json
{"question_id": "q-00017", "status": "answered", "value": 23.41, "unit": "m2", "text": "23.41 m2",
 "confidence": 0.86, "convention": "net area, holes subtracted", "abstain": null, "best_estimate": null,
 "evidence": [
  {"id": "e1", "kind": "polygon", "page": 0, "role": "measured", "pts": [[412,300],[498,300],[498,377],[412,377]]},
  {"id": "e2", "kind": "text_span", "page": 0, "bbox": [440,330,470,340], "text": "Bain 4.01"},
  {"id": "e3", "kind": "scale", "page": 0, "source": "ratio_text", "text": "1:100 (A3)", "m_per_unit": 0.035278}],
 "steps": [{"op": "shoelace*scale^2", "kind": "deterministic", "in": ["e1", "e3"], "out": 23.41}],
 "cost": {"calls": ["sha256:9c1f..."], "gpu_s": 0.0, "cpu_s": 0.21}, "latency_ms": 310}
```

- `status` is `answered`, `abstained` or `error`. A crash or a timeout becomes `error`.
- `abstain` is `{reason, detail, request}`. Reasons: `needs_scale`, `not_on_document`, `not_in_model`,
  `illegible`, `not_a_drawing`, `ambiguous_question`, `out_of_scope`. Requests: `calibrate_two_points`,
  `provide_scale`, `provide_model`, `provide_sheet`.
- `best_estimate` is optional on an abstention: the value the solver would give if it had to. It keeps us
  safe if Stoa scores an abstention as a wrong answer (section 5).
- Evidence kinds: `mark`, `polygon`, `text_span`, `table_cell`, `ifc_element` (GlobalId), `scale`, `calc`.
  Coordinates are in the page's own units. Each step is `deterministic` or `model` and cites evidence ids.
- `convention` states the counting or measuring rule that the solver used.

**Sealed sessions.** The harness copies each document to an empty directory under the name
`doc-<sha256[:12]>.<ext>`. The solver gets no path, no source name and no sibling file. This matters: 1,040
swiss stems have `.dxf` and `.png` siblings, file names carry public ids (`site292_bldg545_floor2188`), and
the swiss title block prints those ids on 100 of 100 sampled sheets (M, harness and red-team scripts). The
dataset, `data/external/` and `questions.jsonl` are not reachable from the solver process. Model calls go
through the harness proxy (section 8).

## 3. Partitions

The split is `stoa/analysis/questions/split_v0.json` (sha256 `607f5dd4...`): dev 76,414, val 25,388 and test
25,242 rows, grouped by cubicasa plan, swiss site, IFC project and opening_design project (M). We use it as:

| Partition | Use | Rule |
|---|---|---|
| DEV | read failures, tune prompts and thresholds, train | free |
| VAL | accept or reject a change | read scores and flips, do not tune on its rows |
| LOCK | the honest number | encrypted keys, 3 openings, aggregates only |

- **Items, not rows.** The 127,044 rows are 64,132 independent items: the translation twins never disagree
  (M, `DATASET.md` section 8; `research/data/questions.md` says 63,404 because its key merges free-text rows). The harness asks both twins. An item is correct only when both are.
- **cubicasa5k items come only from the public CubiCasa5K val and test plans.** A detector that is trained on
  the public train split has seen the rest. That leaves 157 plans in VAL and 148 in LOCK. 809 of the 957
  LOCK plans are public train plans (M, the lead ran this check again).
- Each derived suite inherits the partition of its group. A trained part declares its training groups, and
  the run fails when one of them is in the scored partition.

## 4. Suites

Each suite exists to show one kind of failure. Sizes are per partition (D), and VAL and LOCK use other documents.

| # | Suite | The solver gets | Key from | Size (D) | Failure it shows |
|---|---|---|---|---|---|
| 1 | `smoke` | 12 documents, all 6 extensions | Stoa | 72 items | a broken path, in a minute |
| 2 | `public-mini` | native files, at most 10 drawings per (family, answer) | Stoa | about 300 documents | a regression. The floor, not the target |
| 3 | `ladder` | the same items in 4 conditions (below) | Stoa, unchanged | 100 documents x 8 items | dependence on vectors, a text layer, a clean scan, a printed scale |
| 4 | `compound` | swiss PDF or PNG, IFC | key builder on public geometry | 50 documents, 200 items | no two-step reasoning |
| 5 | `unanswerable` | sheets where no correct value exists, each with a control question | construction | 60 documents, 120 + 120 items | a guessed number, and "always abstain" |
| 6 | `resbim` | raster plan with dimension chains and no scale bar | sibling IFC | 50 documents, 200 items | raster counting and scale on an unseen source |
| 7 | `hard` | cubicasa plans where Stoa dropped the template; swiss visible doors | CubiCasa5K SVG, swiss geometry, two keys | 90 documents, 270 items | the ambiguous cases, zero answers, conventions |
| 8 | `wild-hand` | scans, US CAD sheets, hand drawings | 2 people per item | 50 items exist, target 150 on 60 documents | everything that our generators cannot make |
| 9 | `lang` | `public-mini` items, paraphrased and in unseen languages | unchanged | 120 items x 3 | a template router, an English-only dictionary |
| 10 | `ifc-text` | IFC | fact keys (section 6) | 188 VAL rows of ifc_bench | wrong facts in long text |
| 11 | `fresh` | LOCK only | public originals that Stoa did not ship | 213 CubiCasa5K plans, 206 IFC-Bench v2 rows on 6 models | the drawing gap. Nobody opens these before a LOCK opening |
| G | `crash` gate | one `ingest` each | none | 300 files: 271 DWG, 74 PDFs with no text layer, a 343 MB IFC, scans | a crash, a timeout, a cost spike |

**`public-mini`.** The cap of 10 drawings per (family, answer) lowers the mode-guess score on cubicasa from
55.3% to 10.4% (M, `analysis/eval-design-red-team/m10_stats.py`).

**`ladder` conditions.** C0 the native file. C1 a raster at 150 dpi with no text layer (also "a PDF that is a
scan"). C2 a scan simulation: rotation by 90 degrees and by 2 degrees, blur, JPEG quality 40, grey. No warps:
they break areas (S, `research/sota/synthetic-data.md`). C3 the scale stripped: the title band, the scale bar
and the legend cropped. In C3 the key of an area item becomes "abstain, `needs_scale`", then the harness
calls `/calibrate` and asks again: the value must be within 2%. The key of a count does not change. The pairs
are exact, so the gap between two conditions has a small interval.

**`compound` templates.** No public question has them: the tile area of all rooms labelled Bad or WC (the
host's example), the largest room, rooms above 12 m², apartments with more than one bathroom, the largest
apartment and its margin, a label that is not on the sheet (key 0). Half of the templates stay in LOCK only.

**`unanswerable` cases.** An area with no scale on the sheet (`needs_scale`). A model-wide count on one
storey sheet: 170 to 176 such public rows exist (M, two counts) (`not_on_document`). A floor area asked on an elevation. The area
of a room that does not exist. A page that is not a drawing: 8 of 120 sampled scans (M,
`research/data/wild.md`) (`not_a_drawing`). The ratio text and the scale bar disagree. Each case has a
control question with an answer on the same document.

**`hard`.** Two keys per item where the convention is open. cubicasa doors: strict (doors with a leaf) and
inclusive (all openings). swiss doors: Stoa's reference (a shared door counts once per apartment) and the
distinct visible doors. These two agree on 7.1% of floors (M, `research/data/swiss.md`), so one key would
punish an honest solver. An answer is correct when it equals the key of the convention that it states.

**`wild-hand`.** It starts from `research/data/wild-probe-questions.jsonl`: 50 rows on 27 documents, 5 of them
"cannot be determined" (M). Two people label each new item: answer, evidence box, how they verified it. A
third person settles a conflict. At least 30% are compound questions. Include revision traps, feet and inches,
handwritten scales and sheets with several views. A labeller does not write solver code for those sheets.

**Not in the first build:** a synthetic sheet generator with its own styles (6 hours, E). The `ladder` and
`compound` suites give exact keys on real geometry sooner. Build the generator only if the Saturday hint points
at styles that we cannot reach by transforms.

## 5. Scores and the headline

**Item score `s`:**

| Key | Solver output | s |
|---|---|---|
| answerable | correct | +1 |
| answerable | abstained | 0 |
| answerable | wrong, `error` or invalid | -1 |
| unanswerable | abstained, reason in the key's set | +1 |
| unanswerable | abstained, other reason | +0.5 |
| unanswerable | any value | -1 |

Correct means: a count is exact, a measure is within 2% after unit conversion (boundary included), text passes
section 6. Stoa's rule for wrong answers and abstentions is unknown. So each report prints three columns:
penalty 1 (the headline), penalty 0 with `best_estimate` scored as an answer ("plain accuracy", in case Stoa
counts an abstention as wrong), and penalty 3.

**Cells.** A cell is a skill on a kind of input. The weights are our estimate of the hidden mix (E). They live
in `suites/weights.toml` with a version. We may change them once, after Stoa's hint on Saturday, with a logged
reason.

| Cell | Suites | w |
|---|---|---|
| lookup, vector | opening_design, label and printed-value families | 0.10 |
| count, vector | swiss and ifc counts, `hard` visible doors | 0.05 |
| count, raster | `ladder` C1 and C2 counts, `hard` cubicasa, `resbim` | 0.15 |
| measure, vector | swiss and ifc areas, volumes, lengths | 0.10 |
| measure, raster | `ladder` C1 and C2 areas, C3 after calibration | 0.10 |
| compound | `compound` | 0.15 |
| model query | ifc_models on `.ifc`, `ifc-text` | 0.10 |
| unanswerable | `unanswerable`, `ladder` C3 | 0.10 |
| wild | `wild-hand` | 0.15 |

**Cell score** `S_c` = the mean over documents of (the mean of `s` over the items of the document). Each
document weighs the same, like one session at Stoa's table.

**Headline** `H = 100 * sum of w_c * S_c`, on VAL, with a 90% interval from a cluster bootstrap over documents.

**Guard numbers, always printed beside `H`:**

- the worst cell, and the cell table;
- the share of documents with zero correct answers;
- the wrong-answer rate, and the coverage;
- `VA`, the verifiable accuracy (section 7), and `correct - VA`, the "right for the wrong reason" rate;
- `C10` and the latency (section 9);
- the `ladder` gaps C0 to C1, C1 to C2, and the share of items whose answer changes between conditions;
- `crash` errors (the gate is 0);
- the share of answers with only deterministic steps.

**Baselines in each table:** `null` (always abstains), `prior` (the most common answer per family, fitted on
DEV), `blind` (a model that sees only the question), `oracle-parser` (the existing probes on native files).
The skill of a cell is read against the better of `prior` and `blind`.

**Confidence.** The store keeps each confidence. `ev sweep` scores a run again with "abstain when confidence
is under t" and prints `H(t)`, with no model call. Choose t on VAL only. Also report the Brier score and a
10-bin reliability table per cell.

**The predicted hidden score (last build step).** `ev predict` draws cell accuracies from Beta posteriors with
the design effect, scenario weights from a Dirichlet prior, and a discount of 0 to 2 measured gaps
(statistician's design, section 4). It prints the median and the 5% to 95% range, and the range of the observed
score on 8 documents with 5 questions. Use it for the pitch and for the question "how sure are we". Do not
use it to accept a change.

## 6. The scorer

`score(candidate, key) -> Verdict` is a pure function with decimal arithmetic. Its test cases are one JSON line
each in `scorer/vectors.jsonl`. The exact rules are in the harness engineer's design, section 9. The main ones:

- **Numbers in text.** `1.234,5` and `1,234.5` both give 1234.5. One separator with exactly 3 digits after it
  is ambiguous: use the language of the question, and flag it. Feet and inches (`5'-10 3/8"`) parse to an exact
  fraction: 70.375 in = 1.787525 m.
- **Units.** Convert inside one dimension and flag `unit_converted`. Another dimension, or no unit on a
  measure, is wrong.
- **Rounded keys.** On 50 public rows the rounding step of the key is larger than the 2% tolerance (M,
  `analysis/eval-design-harness-engineer/out/08.txt`). Example: key 0.22 m², exact value 0.2249, error 2.2%.
  The headline uses the strict rule. A second column accepts `0.02 * |r| + h` and flags `rounding_victim`.
- **Accept sets.** A key can hold several values, each with its convention.
- **Free text**, three tiers. (1) An abstention key: 74 to 120 of the 820 ifc_bench answers say "not
  available" (M, four counts with different patterns; a person fixes the list once), so the solver must abstain with `not_in_model`. (2) A fact key: each reference is split once into typed facts
  (number, dimension, code, name). A person checks 100 of them. Correct when recall is 0.8 or more, precision
  is 0.5 or more, and no stated value conflicts with a fact. This blocks an answer that lists every number in
  the model. (3) A pinned model as judge for the rest, checked on 60 hand labels. Under a Cohen's kappa of 0.7,
  those items leave the headline.

**Acceptance test of the harness itself.** Before any solver exists, the harness must reproduce 4 known
numbers: `prior` 55.3% on cubicasa5k, the swiss PDF parser 99.63%, the IFC rules 3,057 of 3,062, and `null`
with the score that the weights imply. A harness that cannot reproduce them is not trusted.

## 7. Evidence

Checks with no key. They run on every answer, also on drawings without questions:

- E1: a count equals the number of `mark` objects. No two marks are closer than 0.5% of the page diagonal.
- E2: an area equals the polygon area times the scale squared, within 0.5%. A `scale` object exists.
- E3: each `text_span` exists at its box. For a lookup, the span contains the answer.
- E4: each GlobalId exists in the IFC with the stated class. The cited quantities sum to the answer.
- E5: each coordinate is inside its page. Each step cites evidence ids that exist.

Checks with ground truth (swiss geometry, CubiCasa5K SVG, IFC, hand boxes): marks are matched one to one to
true objects, then precision, recall and F1. Polygons: IoU.

**`VA`** = the share of answerable items that are correct, pass E1 to E5 and, where ground truth exists, have a
mark F1 of 0.9 or more or an IoU of 0.8 or more. Two errors that cancel give a correct count today and a wrong
count on the next sheet. `correct - VA` shows that.

**People.** At each milestone a teammate checks 20 answers in the evidence view with a timer. The harness
plants 5 wrong answers with plausible evidence. Report the median seconds and how many the person caught. This
is the only test of "verify in seconds", and it needs the UI. Until the UI exists, the harness writes a PNG
overlay per flipped item.

## 8. Records, replay and comparison

```
stoa/eval/
  contract/contract.schema.json
  scorer/{parse.py, units.py, score.py, vectors.jsonl}     pure, no I/O
  harness/{run.py, sandbox.py, proxy.py, store.py, stats.py, report.py, diff.py}
  keybuild/{swiss.py, cubicasa.py, ifc.py, text_facts.py}   may read public annotations
  suites/<suite>.jsonl  suites/weights.toml  prices.toml  leaks.toml  data.lock.json
  keys/{dev,val}/<suite>.jsonl  keys/lock/*.age              LOCK keys are encrypted
  cache/calls/                                               model-call records, git-ignored
  runs/<run_id>/{manifest.json, answers.jsonl, scores.parquet, report.md}
  ledger.jsonl                                               append-only, every run, also the bad ones
```

- The manifest holds: git sha and dirty flag, solver config hash, pinned model ids, hashes of trained weights
  and their training groups, suite and key hashes, the weights version, the mode and the seed.
- `answers.jsonl` holds the raw records and is never rewritten. `ev rescore` scores an old run again after a
  scorer or key change, with no solver and no model call.
- **Model-call proxy.** The solver calls models through `http://127.0.0.1:4311`. The cache key is the hash of
  the canonical request. Modes: `record` (a miss goes live and is stored), `replay` (a miss fails the run),
  `fresh` (a new epoch, to measure variance). The current API rejects `temperature`, so only replay gives
  equal runs (S, `research/sota/eval-methodology.md`). The proxy rejects a model alias and stores tokens and
  latency. A cache hit keeps its recorded cost.

```sh
uv run ev run --suite smoke --solver http://127.0.0.1:4310 --mode replay
uv run ev run --suite val-core --mode record --workers 16 --resume --hypothesis "scale from dimension chains fixes measure, raster"
uv run ev diff runs/<A> runs/<B>          # paired difference, interval, flips per cell, cost change
uv run ev sweep runs/<B>
uv run ev rescore runs/<A>
uv run ev audit runs/<B>                  # the checks of section 10
uv run ev run --suite lock-core --unlock "Sat 20:00 checkpoint"
```

## 9. Statistics, cost and latency

- **The unit is the document.** With a simple solver the design effect is 1.75 to 1.86 on cubicasa5k and 3.3
  to 3.5 on swiss_dwellings (M, two agents measured it independently). 687 ifc_models items on 9 projects are
  worth about 74 independent items (M). A naive standard error is too small by these factors.
- **Two runs** are always paired on the same items. The interval is a paired cluster bootstrap over documents
  inside each cell, 2,000 resamples. A cell under 30 documents gets a sign-flip permutation test.
- **Each cell prints its smallest detectable difference.** About 3 points on 150 cubicasa plans, 5 points on
  100 swiss floors, 9 to 13 points on `wild-hand`, over 15 points on the IFC projects (M and E, statistician's
  table). On the small cells, read each flipped item. The mean proves nothing there.
- **Accept rule.** A change is accepted when the lower bound of `H_B - H_A` is above 0, no cell falls by more
  than its smallest detectable difference, `crash` errors stay at 0, and `C10` is at or under USD 0.10. State
  the hypothesis and the target cell before the run.
- **Many tries invent gains.** The best of 30 runs with no real effect looks better by about 2 standard errors
  (M, simulation). So DEV numbers are never quoted, and LOCK opens 3 times.
- **Noise floor.** One `fresh` run of `public-mini` per day. Ignore a difference under 2 standard deviations
  of that noise.

**Cost.** `C10` = ingest plus 10 questions for one document, from a cold cache: tokens at list price from
`prices.toml`, plus GPU seconds at the Verda A100 price. Report the median and the p95. The target is USD 0.10
or less (S, `HOST.md` row 10). Batch discounts do not count: a live session cannot wait for a batch. Ingest and
question cost are separate columns.

**Latency.** p50 and p95 of ingest and of ask, cold. Budgets (E): ingest p95 60 s, ask p95 10 s. Over 180 s is
an `error` for every open question of that document.

## 10. Cheats and the checks that find them

`ev audit` runs these. A failed check blocks an accept.

| Cheat | Why it works on the public set | Check |
|---|---|---|
| Hash or file-name lookup | 4,787 cubicasa PNGs are byte-identical to public files (M) | sealed names; re-encode test (pad 1 px, save again: the score must not move); scan the solver and its caches for `model.svg`, `geometries.csv`, IFC-Bench files |
| Printed id lookup | the swiss title block prints the public ids (M) | a variant with a false plan number |
| Generator fingerprint | producer "Matplotlib" on swiss PDFs, creator "junction-dataset-builder/0.1" on IFC sheets (M) | metadata scrub variant; `wild-hand` |
| Sibling format | a DXF or IFC lies next to the file | sealed session; `ladder` gap |
| Answer priors | mode guess 55.3% (M) | balanced sampling; swap test: ask the questions of document A on document B, the score must fall to the prior |
| Presence leak | bathtubs are asked only where one exists (M) | `hard` zero items |
| Correlated answers | sinks predict toilet bowls (M) | a count needs its own marks (E1) |
| Template routing | 24 templates are 67% of the rows (M) | `lang`, `compound` |
| Convention tuning | swiss doors (M) | two keys and a stated convention |
| Special cases per document | 3 US sheets hold all 64 opening_design questions (M) | scan code and prompts for sheet codes, site ids and project names |
| Always or never abstain | | paired controls; the -1 |
| Marks that only fit the count | | ground-truth matching, `VA` |
| Warm caches | | LOCK runs start cold in a new directory |

## 11. Rules that protect the locked set

1. LOCK keys are encrypted with `age`. Henrik holds the passphrase. An unlock needs a reason and writes the ledger.
2. A LOCK run prints `H` and the cells with 20 or more items. It prints no item and no flip.
3. At most 3 unlocks: with the baselines, Saturday 20:00, and the freeze. Nothing is tuned after the last one.
4. Prompts, thresholds, examples and training use DEV only. VAL is for accept decisions. A VAL or LOCK run
   with a dirty git tree fails.
5. The solver never reads CubiCasa5K SVG, Swiss Dwellings CSV, IFC-Bench CSV, `LICENSE.md` rows or a file
   name. Public annotations live only under `stoa/eval/keybuild/` and `data/external/`.
6. The person who writes the LOCK half of `compound` and `wild-hand` does not work on the solver.
7. If LOCK and VAL differ by more than 8 points of `H` (D), we have overfitted VAL. Build new `ladder`,
   `compound` and `lang` suites with a new seed.
8. A change of weights, keys or scorer bumps a version. Runs with different versions are compared only after
   `ev rescore`.
9. The pitch quotes LOCK numbers and the predicted range. It never quotes a public micro average.

## 12. What I took from each design, and what I dropped

| Decision | Taken from | Why |
|---|---|---|
| HTTP contract with `/calibrate`, one schema for harness and app | harness engineer | Stoa judges through our interface. The harness must test the same API |
| Sealed sessions, the cheat table and `ev audit` | red team | accidents are likely: ids are in file names, title blocks and metadata |
| Document-mean score per cell, -1 for a wrong answer | red team, harness engineer | it matches a session, and the host values "I don't know" |
| Three penalty columns and `best_estimate` | lead | Stoa's rule is unknown. An honest abstention must not cost us if they count it as wrong |
| `ladder` with exact pairs in 4 conditions | statistician | a paired gap has a small interval, and it measures what the hidden set changes |
| cubicasa items only from public val and test plans | all three | a detector trained on the public train split is then tested fairly |
| `fresh` in LOCK: 213 plans and 206 rows that Stoa did not ship | statistician, harness engineer | the closest thing to the hidden files that we have |
| Replay proxy, `rescore`, manifest | harness engineer | equal runs need recorded calls, since the API has no temperature |
| Acceptance test on 4 known numbers | harness engineer | the harness must prove itself before it judges a solver |
| Paired cluster bootstrap, smallest detectable difference per cell | statistician | the naive error is too small by 1.8 to 3.5 times |
| Predicted hidden score with a gap discount | statistician | useful for the pitch. Not for accept decisions: its weights are guesses |
| Strict Python (uv, pyright strict, `msgspec`), no Rust | harness engineer | the risk of a scorer is a wrong rule, not a wrong type. Agents write Python faster |

Dropped:

- **The minimum over variants as the item score** (red team). One unstable model call gives -1, and it
  triples the cost. The `ladder` cells and the flip rate carry the same signal with less noise.
- **VAL that returns only accept or reject** (statistician). With 33 hours we need to read the flips. The
  limit on LOCK openings protects the honest number.
- **A synthetic sheet generator in the first build** (red team). See section 4.
- **A static HTML viewer** (harness engineer). The repository rule keeps UI in the starter app. Overlays as
  PNG files are enough until the evidence view exists.

## 13. Build order

Hours are estimates of work, not of wall time.

| Step | What | Hours | Done when |
|---|---|---|---|
| 1 | Contract schema, scorer, `vectors.jsonl`, tests | 2.5 | the unit tests pass |
| 2 | Runner, sealed directory, store, manifest, resume | 2 | a `null` solver has a run record |
| 3 | `smoke`, `public-mini`, baselines, the acceptance test | 1.5 | the 4 known numbers are reproduced |
| 4 | Report, `diff`, bootstrap, `sweep` | 2 | two baseline runs give a paired interval |
| 5 | `ladder` C1 and C3, `unanswerable` with controls | 3 | the swiss PDF parser falls on the PNG-only condition |
| 6 | `wild-hand` to 150 items, by people, from hour 0 | 4 | two labels per item |
| 7 | Model-call proxy with cache and cost, `C10`, latency, `crash` gate | 2.5 | a replay run makes no network call |
| 8 | `compound` key builder (swiss, IFC), `resbim` keys | 3 | the tile question has a key on 50 floors |
| 9 | Evidence checks E1 to E5, ground-truth matching, `VA` | 2.5 | a planted "right for the wrong reason" answer is found |
| 10 | `hard`, `lang`, fact keys for `ifc-text`, `ladder` C2 | 4 | |
| 11 | `ev audit`, canaries, LOCK encryption, `fresh` | 2 | a planted lookup solver is caught |
| 12 | `ev predict` | 1 | |

Steps 1 to 4 are 8 hours of work in 2 lanes: a first trusted number after about 5 hours of wall time. Steps 1
to 9 are about 23 hours of work, or one night with 3 workers on disjoint files. After the Saturday hint: 1 hour
for new weights and new `compound` templates, then `ev rescore`.

Drop in this order when time is short: step 12, `lang`, the judge tier of free text, `hard`, encryption (use a
rule and the ledger).

## 14. Weaknesses that remain

1. The cell weights are a guess of the hidden mix, and `H` moves with them. The cell table and the worst cell
   are the defence. The order of work is more stable than the level.
2. The derived suites use Stoa's renderers and three public geometries. A real tricky sheet is none of them.
   Only `wild-hand` covers that, with 150 items and an interval of about 10 points.
3. The keys of `hard`, `compound` and the evidence checks come from public annotations, with their
   conventions and errors. Two keys lower that risk only in part.
4. The penalty, the reason codes and the 0.5 for another reason are our rules, not Stoa's.
5. Stoa judges by hand through our UI. The harness tests the API under the UI. Three timed rehearsals with a
   teammate as the judge are needed before Sunday.
6. The sandbox stops accidents, not intent. A model that holds public images in its weights passes it.
7. The environment costs about 20 of the hours that remain. If the hidden set is mostly public templates
   (probability 0.20, E), part of that work adds nothing.
