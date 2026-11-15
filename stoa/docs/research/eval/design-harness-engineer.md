# Evaluation environment: the harness engineer's design

Date: 2026-11-14. Lens: the machinery. Labels: **MEASURED** (my scripts in
`stoa/analysis/eval-design-harness-engineer/`, outputs in `out/`), **SOURCED** (report named), **ESTIMATE**.
I opened 12 drawings from 8 sources and read 100 sampled questions.

## 1. The main idea

Lookups and parsers reproduce the public key (SOURCED: `data/cubicasa.md`, `data/swiss.md`, `data/ifc.md`).
So a public score is a regression test for parsers, not the target. The harness has two sides with a wall
between them:

- **Key side.** It may use each public annotation (CubiCasa5K `model.svg`, Swiss Dwellings geometry, IFC,
  IFC-Bench) to build new, harder questions with exact keys and ground-truth evidence.
- **Solver side.** It gets one document under a neutral name, then questions. It never sees a key, a
  sibling file, a file id or a public annotation.

The harness speaks Stoa's protocol: one document, then a series of questions (SOURCED: `HOST.md` row 9).

## 2. Goals and non-goals

1. One headline number that moves like the hidden score, with per-cell numbers under it.
2. Each run is reproducible from its manifest. Re-scoring needs no model call.
3. A solver cannot cheat by accident.
4. `diff` of two runs shows each flip, an interval and the cost change.
5. The contract is HTTP and JSON, so the starter app is tested through the API that its UI calls.

Non-goals: the product UI, a general eval framework, training code, a high public micro average.

## 3. Contract between solver and harness

`stoa/eval/contract/contract.schema.json` is the one source. Python `msgspec` structs and the app's Effect
Schema are generated from it. A contract test runs in `pnpm j check`.

```
POST /ingest     {session_id, file: "doc-3fa9c1d2e0b4.pdf", seed}           -> IngestRecord
POST /ask        {session_id, question_id, question, locale_hint?}          -> AnswerRecord
POST /calibrate  {session_id, scale: {ratio: "1:100"} | {p1, p2, length_m}} -> IngestRecord
```

```json
{"question_id": "q-00017", "status": "answered", "value": 23.41, "unit": "m2", "text": "23.41 m2",
 "confidence": 0.86, "deterministic": true, "convention": "net area, holes subtracted", "abstain": null,
 "evidence": [
  {"id": "e1", "kind": "polygon", "page": 0, "role": "measured", "pts": [[412, 300], [498, 300], [498, 377], [412, 377]]},
  {"id": "e2", "kind": "text_span", "page": 0, "bbox": [440, 330, 470, 340], "text": "Bain 4.01"},
  {"id": "e3", "kind": "scale", "page": 0, "source": "ratio_text", "text": "1:100 (A3)", "m_per_unit": 0.035278}],
 "steps": [{"op": "shoelace*scale^2", "kind": "deterministic", "in": ["e1", "e3"], "out": 23.41}],
 "cost": {"calls": ["sha256:9c1f..."], "gpu_s": 0.0, "cpu_s": 0.21}, "latency_ms": 310}
```

- `status`: `answered`, `abstained` or `error`. A crash or a timeout becomes `error` and scores as wrong.
- `abstain`: `{reason, detail, request}`. `reason` is one of `needs_scale`, `not_on_document`, `not_in_model`,
  `illegible`, `not_a_drawing`, `ambiguous_question`, `parse_failed`, `out_of_scope`. `request` says what the
  user can give, for example `calibrate_two_points`.
- Evidence kinds: `mark`, `polygon`, `text_span`, `table_cell`, `ifc_element` (GlobalId), `scale`, `calc`.
  Coordinates are in the page's own units before rotation.
- `value` is a JSON number and `unit` is an enum. Locale parsing applies only to free text.

### Sandbox

- Each session gets an empty directory with one file, renamed to `doc-<sha256[:12]>.<ext>`. MEASURED: 1,040
  swiss stems have `.dxf` and `.png` siblings, and 107 ifc_models stems have 2 extensions. File names carry
  lookup ids (`site292_bldg545_floor2188`).
- The solver process has no path to the dataset or to `keys/`: `sandbox-exec` with a deny rule on macOS, a
  container with one mount on Linux. Network goes only through the harness proxy (section 6).
- `leaks.toml` lists artefacts banned at inference. A trained component lists its training groups. The run
  fails when a training group is in the scored split.
- Leak canaries on 50 documents: re-encoded bytes, and a masked title block. The swiss title block prints
  "Site 292 · Bâtiment 545". All cubicasa PNGs are byte-identical to public images (SOURCED: `cubicasa.md`).
  A score that drops under a canary shows an id or hash lookup.

## 4. Splits and suites

The split is `stoa/analysis/questions/split_v0.json` (sha256 `607f5dd4...`; SOURCED: `questions.md`): dev 76,414,
val 25,388, test 25,242 rows, grouped by plan, site and IFC project. I do not make a second split. Each derived
suite inherits the split of its group. The 4,551 unlabelled groups already have one.

Items, not rows: language twins count once (63,404 independent items, SOURCED: `questions.md`). The harness
asks both twins. The item is correct only when both are correct.

| suite | the solver gets | key | size |
|---|---|---|---|
| `smoke` | 12 documents, all 6 extensions | public | 72 items |
| `public-mini` | 304 documents | public | 7,320 rows (MEASURED, `07.txt`) |
| `public-full` | 5,939 documents | public | 127,044 rows (MEASURED) |
| `swiss-raster` | PNG only | public | val: 7,530 rows, about 208 floors |
| `swiss-visible` | PDF or PNG | distinct doors and windows on the sheet | 2 x 1,040 |
| `compound` | swiss PDF, PNG; IFC | new templates on the geometry: tile area of all wet rooms, largest room, apartments with a balcony, rooms under 6 m2 | 6 x 208 val floors = 1,248 (ESTIMATE) |
| `cubicasa-hard` | PNG | CubiCasa5K SVG, stated convention, accept set | 14,687 plan-template pairs that Stoa did not ask (MEASURED: 12 x 4,787 - 42,757) |
| `no-scale` | swiss PNG, footer and scale bar cropped | area: `needs_scale`. count: unchanged | 100 floors x 4 |
| `xmodal` | plan PDF only | model-wide question: the number or `not_on_document` | 170 rows (MEASURED, `03_groups.txt`) |
| `ifc-text` | IFC | fact keys (section 9) | 820 rows, 115 with a "not available" key (MEASURED) |
| `ifc-holdout` | IFC | 206 public IFC-Bench rows on 6 models outside Stoa's data (SOURCED: `ifc.md`) | 206 |
| `wild-hand` | scans, US CAD sheets, ResBIM PNG | hand labels by 2 people | 50 rows exist (MEASURED). Target 150 on 60 documents |
| `meta` | rotations, JPEG q40, 0.5x, rasterised PDF | none | 100 documents x 6 |
| `crash` | one `ingest` each | none | 300 files, 200 of them unlabelled |

`wild-hand` must hold cases like the ones I saw: a europeana sheet that is a ceiling painting (`not_a_drawing`);
a habs site plan with scale bars in feet and in metres; a ResBIM plan with dimension chains in mm and no
scale bar; sheet A-701, where each toilet is drawn in a plan and in 3 elevations.

## 5. Metrics and the headline

Item score `s`:

| key | solver output | s |
|---|---|---|
| answerable | correct | +1 |
| answerable | abstained | 0 |
| answerable | wrong, `error` or invalid | -1 |
| unanswerable | abstained, reason in the key's set | +1 |
| unanswerable | abstained, other reason | +0.5 |
| unanswerable | any answer | -1 |

Stoa's rule is unknown. With penalty 1, an answer pays only when P(correct) is above 0.5. The report also
prints the score with penalties 0 and 3.

Cell score: `S_c = mean over documents of (mean of s over the document's items)`. Each document weighs the
same, like one session at Stoa's table.

**Headline: `H = 100 * sum over cells of w_c * S_c`, on val.** The weights are an ESTIMATE of the hidden mix.
They live in `suites/weights.toml` with a version.

| cell | suites | w |
|---|---|---|
| lookup, vector | opening_design, swiss label and printed-area families | 0.10 |
| count, vector | swiss and ifc counts, `swiss-visible` | 0.05 |
| count, raster | `swiss-raster` counts, `cubicasa-hard`, cubicasa val | 0.15 |
| measure, vector | swiss and ifc areas, volumes, lengths | 0.10 |
| measure, raster | `swiss-raster` areas, `no-scale` after calibration | 0.10 |
| compound | `compound` | 0.15 |
| model query | ifc_models on `.ifc`, `ifc-text` | 0.10 |
| unanswerable | `no-scale`, `xmodal`, 115 `ifc-text` rows | 0.10 |
| wild | `wild-hand` | 0.15 |

Each run also prints: the worst cell; `VA`; `C10` and latency; coverage; Brier score and a 10-bin reliability
table per cell; the `meta` change rate; `crash` errors; the share of deterministic answers.

Threshold sweep: the store keeps each confidence. `ev sweep` scores again with "abstain when confidence < t"
and prints `H(t)`, with no model call. Pick t on val only.

Baselines in each table: `null` (always abstains), `prior` (template constant fitted on dev), `blind` (LLM
with the question only), `oracle-parser` (the existing probes).

## 6. Recording a run

```
stoa/eval/
  contract/contract.schema.json
  scorer/{parse.py,units.py,score.py,vectors.jsonl}      # pure, no I/O
  harness/{run.py,sandbox.py,proxy.py,store.py,stats.py,report.py,diff.py,viewer.py}
  keybuild/{swiss.py,cubicasa.py,ifc.py,text_facts.py}   # may read public annotations
  suites/<suite>.jsonl  suites/weights.toml  data.lock.json  prices.toml  leaks.toml
  keys/{dev,val}/<suite>.jsonl  keys/test/*.age          # test keys are encrypted
  cache/calls/ab/<sha256>.json.zst  cache/index.sqlite
  runs/<run_id>/{manifest.json,answers.jsonl,ingest.jsonl,scores.parquet,report/index.html}
  ledger.jsonl                                           # append-only, committed
```

```json
{"run_id": "2026-11-14T0312-a41f9c2", "git": "a41f9c2", "dirty": false, "who": "henrik/claude-code",
 "solver": {"version": "0.3.1", "config_sha": "77be...", "models": ["<pinned id with date>"],
            "weights": {"symbols.onnx": "sha256:1d0c..."}, "train_groups_sha": "c2aa..."},
 "suite": "val-core", "split": "split_v0:607f5dd4", "weights_version": 2, "keys_sha": "e19b...",
 "data": {"questions_sha256": "0e6322c7...6d1f", "tree_sha256": "..."},
 "mode": "replay", "seed": 20261114, "prices": "prices.toml@3", "workers": 16}
```

- `questions.jsonl` has sha256 `0e6322c7...6d1f` (MEASURED). Hashing 3,121 swiss files (594 MB) took 0.78 s
  (MEASURED), so the 11 GB tree takes about 15 s (ESTIMATE), once, into `data.lock.json`.
- `answers.jsonl` holds the raw AnswerRecords and is never rewritten. `scores.parquet` is derived: `(run_id,
  cell, group, doc, item_id, family, lang, key, verdict, s, evidence_ok, va, confidence, cost_usd,
  latency_ms, flags)`. DuckDB reads `runs/*/scores.parquet`. No server.
- **Model-call proxy.** The solver uses `ANTHROPIC_BASE_URL=http://127.0.0.1:4311`. Cache key = `sha256` of the
  canonical JSON of `{endpoint, pinned model id, body with sorted keys, attachments as sha256, epoch}`. Modes:
  `record` (a miss goes live and is stored), `replay` (a miss fails the run), `fresh` (new epoch, to measure
  variance). The proxy rejects a model alias with no date. It stores tokens and latency. Temperature 0 is not
  deterministic (SOURCED: `sota/eval-methodology.md`, S30). Only replay gives equal runs.
- The solver's ingest result is cached by `(file sha256, ingest version)` with its cost record. A cached
  ingest still counts in `C10`.
- Parallel runs: the unit of work is a session. Workers append each answer at once. `--resume` skips answers
  that exist. Loading 127,044 rows takes 0.15 s (MEASURED). Scoring `public-full` in replay takes under 10 s
  (ESTIMATE).

```sh
uv run ev run --suite smoke --solver http://127.0.0.1:4310 --mode replay
uv run ev run --suite val-core --mode record --workers 16 --resume
uv run ev diff runs/<A> runs/<B> --cell compound --flips broken
uv run ev sweep runs/<B>
uv run ev rescore runs/<A>      # new scorer or keys, no solver, no model call
uv run ev run --suite test-core --unlock "Sat 20:00 checkpoint"
```

## 7. Is a difference real, and what does it cost

- `ev diff` pairs the items of two runs. It prints flips per cell (fixed, broken, wrong to abstain, right to
  abstain) and lists the 20 worst broken items with links to the viewer.
- Interval: paired cluster bootstrap. Resample `split_v0` groups inside each cell 2,000 times, compute `H_B -
  H_A`, report the 5th and 95th percentile. A cell under 30 documents gets a sign-flip permutation test.
- Printed beside each cell: `MDE = 2.8 * sd / sqrt(n documents)`, with `sd` of the per-document paired
  difference. ESTIMATE before any run: `wild` (60 documents, sd 0.35) 12.7 points; `swiss-raster` (208
  floors, sd 0.25) 4.9 points.
- Noise floor: one `fresh` run of `public-mini` per day.
- **Accept rule.** Merge when the lower bound of `H_B - H_A` is above 0, no cell falls by more than its MDE,
  `crash` errors stay at 0, and `C10` is at or under USD 0.10. A change that only lowers cost merges when the
  upper bound of the loss is under 1 point.
- Each run is in `ledger.jsonl`, also the bad ones.

`cost(session) = ingest + sum of asks`. Each part = tokens x `prices.toml` at list price + `gpu_s` x 2.37 / 3600
(A100). Batch discounts do not count: a live session cannot wait for a batch.

- **`C10`** = median and p95 over documents of `ingest + 10 questions`. Target: USD 0.10 or less (SOURCED:
  `HOST.md` row 10). Also `C1` (the cold case) and the cost per question after ingest.
- Ingest and query cost are separate columns. The public medians are 18 and 36 questions per drawing
  (MEASURED). A fixed 10 stops that from hiding the ingest cost.
- Latency: p50 and p95 of ingest and of ask. Budgets (ESTIMATE): ingest p95 60 s, ask p95 10 s. Over 180 s is
  `error`.

## 8. Evidence score

Checks with no key (they run on each answer, also on unlabelled sources):

- E1: a count equals the number of `mark` objects with `role: counted`. No two marks are closer than 0.5% of
  the page diagonal.
- E2: an area equals shoelace(polygons) x scale squared within 0.5%. A `scale` object exists.
- E3: each `text_span` exists. For a vector PDF the harness reads the words in the box with PyMuPDF and compares.
  For a lookup, the span contains the answer value.
- E4: each GlobalId exists in the IFC with the stated class. The cited quantities sum to the answer.
- E5: each coordinate is inside its page. Each step cites evidence ids that exist.

Checks with ground truth (swiss geometry, CubiCasa SVG, IFC): Hungarian matching of marks to objects, then
precision, recall and F1. Polygons: IoU.

**`VA` (verifiable accuracy)** = share of answerable items that are correct, pass E1 to E5 and, where ground
truth exists, have mark F1 of 0.9 or more, or IoU of 0.8 or more. `correct - VA` is the "right for the wrong
reason" rate. The share of wrong answers that fail an E check should feed the confidence.

## 9. The scorer, exactly

`score(candidate, key) -> Verdict`. Pure function. Decimal arithmetic.

**Numbers in text.** NFKC. Remove NBSP and thin spaces. Map the Unicode minus to `-`.
- `.` and `,` both present: the last one is the decimal mark (`1.234,5` and `1,234.5` give 1234.5).
- Apostrophe or space groups (`1'234.50`, `1 234,5`) are thousands.
- One separator with exactly 3 digits after it (`1,234`, `1.234`): ambiguous. Use `locale_hint` (`,` is decimal
  for de, fr, it, fi, es, nl, da, pl, et, ro). No hint: en. A leading `0` (`0,125`) is a decimal. Flag
  `ambiguous_number`.
- Feet and inches (`5'-10 3/8"`, `12'-0"`, `35 1/2"`, `5 ft 10 in`) parse to an exact `Fraction` of inches.
  `5'-10 3/8"` = 70.375 in = 1.787525 m.
- Number words, ranges, NaN and infinity give `invalid_output`.

**Units.** Canonical: `count, m, mm, cm, m2, m3, ft, in, ft2, ft3, percent, none`. Aliases: `m²`, `sqm`, `sq m`,
`qm`; `SF`, `sq ft`, `ft²`; `m³`, `cu m`; `LF`. Exact factors: ft 0.3048, in 0.0254, ft2 0.09290304, ft3
0.028316846592. Same dimension, other unit: convert, compare, flag `unit_converted`. Other dimension, or no
unit on a measure: wrong, flag `unit_mismatch`.

**Counts.** Integer equality. `12.0` is accepted. `12.4`, a negative number or a boolean is `invalid_output`.

**Measures.** Correct when `|c - r| <= 0.02 * |r|`, boundary included.
- `r = 0`: correct when `|c| <= h`, with `h` half the rounding step of the reference. The public key has 0
  zero measures (MEASURED).
- Reference rounding: `h` is larger than the 2% tolerance on 50 public rows (36 ifc_models, 14 swiss) and larger
  than half of it on 151 (MEASURED, `out/08.txt`). Example: key 0.22 m2, exact value 0.2249, error 2.2%, wrong.
  The headline uses the strict rule. A second column uses `0.02 * |r| + h`, and the flag `rounding_victim` marks
  the difference. The solver should round like the generator (2 decimals).
- 112 swiss areas are integers because trailing zeros are dropped (MEASURED). So `h` comes from the family's
  precision.

**Accept sets.** A key can hold `accept: [{value, convention}]`. Any match is correct, and the verdict records
the convention. `public-*` keys hold only Stoa's value.

**Free text**, three tiers. A later tier runs only when the earlier one cannot decide.
1. Abstention key (115 ifc_bench rows, MEASURED by regex): the solver must abstain with `not_in_model`.
2. Fact key. `keybuild/text_facts.py` turns each of the 836 text answers once into typed facts `{kind:
   number|dimension|code|name|bool, value, unit, required}`. An LLM proposes, a person checks 100. `B3
   (aluminium sliding door)` gives `code B3` required and a name optional. Correct when each required fact is in the candidate: numbers by the rules above, schedule
   dimensions exactly, codes after case and space folding. MEASURED on ifc_bench: 140 answers have no number,
   85 have exactly 1, the median is 6.
3. Judge: a pinned model sees question, reference and candidate and gives correct, incorrect or abstained.
   Cached. Checked on 60 hand labels with Cohen's kappa. Under 0.7, tier 3 items leave the headline.

**Unit tests** (`scorer/vectors.jsonl`, one case per line, so another language can run the same file):
decimal comma; both separators in both orders; apostrophe and NBSP groups; `1,234` with and without a hint;
`0,125`; Unicode minus; exponent; each feet and inch form; each unit alias; `ft2` to `m2` and back within
1e-12; dimension mismatch; missing unit; count `12.0`, `12.4`, `-1`, `true`, `"12"`; tolerance at 2.000% and
2.001%; `r = 0`; the rounding victim 0.22; an integer-valued area; NaN; empty answer; `error` status; each
row of the score table; a reason outside the enum; an accept set; a twin item with one wrong twin; a fact
key with an optional fact missing; a code in other case. Property tests (Hypothesis): the verdict does not
change when value and unit convert together; `rescore` gives the same bytes twice.

**Acceptance test of the harness.** Before any solver exists, it must reproduce 4 known numbers: `prior` 55.3% on
cubicasa (MEASURED, `02_summary.txt`), the swiss PDF parser 99.63%, the IFC rule 3,057 of 3,062 (both SOURCED),
and `null` with `H` between 5.0 and 6.5 (0.5 on the unanswerable cell and on the unanswerable part of `wild`).

## 10. Rust, Python or a mix

- **Rust for both.** For: exhaustive `match`, one binary. Against: the evidence checks need IfcOpenShell and
  PyMuPDF; the Rust `dxf` crate drops HATCH with no error; agents resolve fewer Rust issues (15.9% against
  52.2%) (all SOURCED: `sota/stack-rust-python.md`).
- **Mix (Rust scorer through PyO3).** A build boundary for about 300 lines. The scorer's risk is a wrong rule,
  not a wrong type.
- **Python 3.12 with pyright strict, `msgspec` and ruff.** Fastest for agents. One language with the key
  builders. Speed does not matter (0.15 s load, MEASURED).

**Recommendation: strict Python for the scorer and the harness.** The safety comes from a tagged `Answer |
Abstain | Error` union with `assert_never`, a `Unit` enum with conversion in one place, the vector file, and
the acceptance test. A Rust port after the event can prove itself against the vector file.

## 11. Rules that protect the locked test set

1. Test keys are encrypted with `age`. Henrik holds the passphrase. `--unlock` needs a reason and writes the ledger.
2. A test run prints `H` and the cells with 20 or more items. It prints no item and no flip.
3. At most 3 unlocks: now with the baselines, Saturday 20:00, and the freeze.
4. Prompts, thresholds, few-shot examples and training use dev only. Val is for accept decisions. A val or
   test run with a dirty git tree fails.
5. A `wild-hand` labeller does not write solver code for the sheets that he or she labelled.
6. A change of weights, keys or scorer bumps a version. `ev rescore` then scores the old runs again.
7. CI: scorer tests, contract test and `smoke` in replay at each commit. `public-mini` and `crash` at each push.

## 12. Build order

Hours are ESTIMATES.

1. Contract schema, scorer, vectors, tests: 2.5 h.
2. Runner, sandbox directory, store, manifest, resume: 2 h.
3. Model-call proxy with cache and cost: 2 h.
4. `smoke`, `public-mini`, baselines, the acceptance test: 1.5 h.
5. Report, `diff`, bootstrap, `sweep`: 2 h.
6. Key builders for `swiss-raster`, `no-scale`, `compound`, `swiss-visible`, `xmodal`: 3 h.
7. `wild-hand` to 150 rows, by people: 3 h.
8. Evidence checks and ground-truth matching: 2.5 h.
9. Viewer (static pages: sheet, evidence overlay, key, verdict): 2 h.
10. `cubicasa-hard`, fact keys, judge check: 3 h.
11. `meta`, canaries, `crash`, CI gates, test-key encryption: 2 h.

Parts 1 to 5 are 10 hours in 2 lanes: a first trusted number after about 5 hours. After the Saturday hint:
change `weights.toml`, add templates to `compound`, rescore.

## 13. Worked example (invented numbers that show the mechanics)

Run A scores: lookup 0.92, count vector 0.95, count raster 0.31, measure vector 0.90, measure raster 0.12,
compound 0.40, model query 0.70, unanswerable 0.20, wild 0.25.

`H_A = 100 * (0.092 + 0.0475 + 0.0465 + 0.09 + 0.012 + 0.06 + 0.07 + 0.02 + 0.0375) = 47.6`

Run B adds a scale finder and abstains under confidence 0.5. Four cells change: count raster 0.33, measure
raster 0.30, unanswerable 0.70, wild 0.33.

`H_B = 100 * (0.092 + 0.0475 + 0.0495 + 0.09 + 0.03 + 0.06 + 0.07 + 0.07 + 0.0495) = 55.9`

`ev diff` prints: `dH = +8.3`, 90% interval `[+5.1, +11.6]`; fixed 212, broken 37, wrong to abstain 164, right
to abstain 41; `wild` +8 points against an MDE of 12.7, so that cell alone proves nothing; `C10` median from
USD 0.062 to 0.071. The lower bound is above 0, no cell falls, `C10` is under 0.10: accept. The 41 "right to
abstain" items go to the viewer.

## 14. Weaknesses of this design

1. The weights are a guess, and `H` moves with them. The cell table and the worst cell are the defence.
2. The derived suites use Stoa's renderers and three public geometries. A real tricky sheet is none of them.
   Only `wild-hand` covers that, with 150 items and an MDE near 13 points.
3. Penalty 1 is my choice. If Stoa scores an abstention as wrong, the best threshold is 0. `ev sweep` shows
   the size of that mistake.
4. Stoa judges by hand through our UI. The harness tests the API under the UI, not a person's trust in the
   evidence view. Three timed dress rehearsals with a teammate as the judge are needed.
5. The sandbox stops accidents, not a determined agent. A hash table of public images inside a model's weights
   passes it. Only the canaries find that.
6. `ifc-holdout` and `cubicasa-hard` need public downloads. The score is honest only while no solver
   component saw that data.
7. The fact keys start from an LLM. A key error is a silent score error until the 100-row check.
8. The viewer is static HTML from a script. If the lead reads the repository rule against plain HTML wider
    than product UI, it becomes a `/dev/eval` route in the starter app (about 2 hours more).
9. Eleven parts in 25 hours is much. Drop in this order: `meta`, the judge tier, `cubicasa-hard`, encryption.
