# Evaluation environment: the red-team design

Date: 2026-11-14. Lens: I am the Stoa engineer who builds the hidden set to separate understanding from
tuning. Labels: **M** = MEASURED (my scripts in `stoa/analysis/eval-design-red-team/`, or the named report in
`stoa/docs/research/data/`). **S** = SOURCED. **E** = ESTIMATE. **D** = a size or threshold that we choose.

I opened 11 drawings and read 102 questions. Seen: a europeana file that is a page of Polish text, a 344 px
wikimedia plan with no scale, a ResBIM plan with dimension chains only, a US sheet with 8 elevations.

## 1. Goals and non-goals

1. Predict the direction of the hidden score: a small, hard, human-run session with one document and then a
   series of questions (S, `HOST.md` fact 9).
2. Make every known shortcut worthless. The public answers are lookups: cubicasa SVG 100%, swiss parser
   99.63%, IfcOpenShell 99.8% (M, data reports).
3. Score the whole answer record: value, evidence, method, confidence, unknowns, cost.
4. Give a verdict per change in 15 minutes, with a statement of noise.

Non-goals: a public micro accuracy, a pitch number, a UI test.

## 2. The contract: sealed sessions

```
POST /ingest {doc_id: "d_7f3a91", filename: "d_7f3a91.pdf", bytes}  -> {handle, unknowns[], usage}
POST /ask    {handle, question, calibration?: {scale: "1:100"}}     -> AnswerRecord
```

- `doc_id` is random. The solver gets no path, no source name, no sibling file, no `LICENSE.md` row.
- The solver runs in an empty directory. The dataset, `data/external/` and `questions.jsonl` are not
  mounted. The network is an allow-list of model APIs.
- Questions arrive in a seeded random order. A crash or a timeout makes each open question of that document wrong.

## 3. Splits and packs

Base: `stoa/analysis/questions/split_v0.json`, grouped by plan, site and IFC project (dev 76,414, val 25,388,
test 25,242 rows; M, `questions.md`). Three added rules:

- `dev` is free. `val` feeds the **practice pack**. `test` feeds the **locked pack**.
- cubicasa items come only from the public CubiCasa5K val and test plans: 157 plans in `val`, 148 in `test`.
  809 of the 957 `test` plans are public train plans (M, `m14_redteam_pools.py`). A detector trained on the
  public train split has seen them.
- One item per translation group. The 62,910 groups never disagree (M, `questions.md`).

Both packs have the same sizes (D). Locked uses other documents, seeds, styles and languages.

| # | Suite | Docs / items (D) | Pool (M) | Hours (E) | Failure it reveals |
|---|---|---|---|---|---|
| 1 | PUB | 90 / 540 | 40 cubicasa, 30 swiss, 17 IFC, 3 US sheets | 1.5 | A broken basic path. The floor, not the target |
| 2 | SHIFT | 60 / 240 x 3 variants | 1,040 swiss PDF+DXF+PNG triples, 69 IFC sheets | 2 | Dependence on a text layer, vectors, orientation, a clean scan |
| 3 | LANG | 0 / 120 x 3 variants | 11 question languages | 1.5 | A template router, an English-only dictionary |
| 4 | HARD | 90 / 270 | cubicasa plans with a dropped template, in public val+test: doors 210, bedrooms 297, kitchens 255, saunas 246, showers 59. swiss floors with no bathtub 143, no shower 718 | 2 | The ambiguous cases that Stoa removed, zero answers, the door convention |
| 5 | COMPOUND | 50 / 200 | swiss geometry, IFC models | 3 | No two-step reasoning |
| 6 | TRAP | 60 / 240, plus 40 follow-ups | 733 swiss sheets with no printed area, 176 model-wide questions on a sheet, 36 elevations and sections | 2 | A guessed area with no scale |
| 7 | WILD | 20 / 75 | 50 probe rows exist; 6,566 scans and 984 US sheets have none | 4 (people) | Scans, handwriting, schedules, revisions, feet and inches |
| 8 | RESBIM | 50 / 200 | 500 raster plans with an IFC twin | 1.5 | Raster counting on an unseen source |
| 9 | SYN | 100 / 800 | generator | 6 | Everything, with exact truth and evidence |
| 10 | FREETEXT | 12 / 60 | practice: 188 `val` ifc_bench rows. Locked: 206 public IFC-Bench rows on 6 models that Stoa did not ship (M, `ifc.md`) | 2 | Wrong facts in long text |
| G | INGEST gate | 300 / 0 | 271 DWG, 135 SVG, 74 PDFs with no text layer, a 343 MB IFC | 0.5 | A crash, a timeout, a cost spike |

A pack has about 480 documents and 3,500 asks (D). A 10% **smoke** subset runs on each commit.

**PUB.** Cap K = 10 drawings per (family, answer). On cubicasa the cap lowers the mode-guess score from 55.3%
to 10.4% (1,159 items, 926 drawings; M, `m10_stats.py`). Counts exact, measures within 2%.

**SHIFT.** Variants of a base item. The item scores its worst variant.

| Variant | Truth |
|---|---|
| PNG only. A flood fill on the PNG is within 2% for 20.8% of rooms (M, `swiss.md`) | same |
| PDF with no text layer; PDF rasterised to one image ("a PDF that is a scan") | same |
| IFC question with only the plan PDF | same, or a TRAP |
| Rotation 90 and 180, skew 2 degrees, scan noise, JPEG quality 30, margin crop, colour inversion. No warps: they break areas (S, `synthetic-data.md`) | same |
| Downscale by 0.5. The printed "1:100 (A3)" becomes false; the scale bar stays true | same |
| Erase k = 1 to 3 symbols in the DXF, render again | count - k |
| Scale the geometry by 1.25, keep the scale bar | area x 1.5625 |
| Metadata scrub: PDF producer, PNG `Software` chunk, a false plan number | same |

**LANG.** Per item 1 paraphrase and 2 translations. Practice: sv, pt, cs. Locked: hu, lv, tr and another
paraphrase style. A model writes them, a second model translates back, a person checks 10%.

**HARD.** Truth from the public CubiCasa5K SVG, read by the harness only. Two keys per item: strict (doors
with a leaf) and inclusive (all openings). An answer is correct when it equals the key of the convention it
states. swiss doors also get two keys: the reference, and the distinct visible doors. These agree on 7.1% of
floors (M, `swiss.md`), so one key would punish an honest solver. Zero items ask for bathtubs, showers and
"rooms labelled X" where none exists.

**COMPOUND.** Templates that no public question has (D): tile area of all rooms with a WC (the host's
example); apartments with more than one bathroom; the largest apartment and its margin; the mean bedroom
area; apartment area without corridors. Truth from the swiss public geometry or IfcOpenShell, with the
conventions of `swiss.md` finding 8. Credit 0.5 when the set of rooms is right and the arithmetic is wrong.

**TRAP.** Each trap has a control question with an answer on the same document. This punishes "always abstain".

| Trap | Reason code |
|---|---|
| Area with the title band cropped (scale text at 0.878 to 0.953 of the page height; M, `m11_metadata.py`), or on a plan with no scale | `NO_SCALE` |
| Model-wide count on one storey sheet | `NOT_ON_SHEET` |
| Wall volume or floor area from an elevation | `NEEDS_OTHER_VIEW` |
| Area of room 9.99 | `NO_SUCH_ENTITY` |
| A text page, a poster, a map (8 of 120 sampled scans; M, `wild.md`) | `NOT_A_DRAWING` |
| Ratio text and scale bar disagree | answer from the bar, flag `SCALE_CONFLICT` |

Follow-up: after `NO_SCALE` the harness sends `calibration` and asks again. The answer must be within 2%.

**WILD.** Two people label each row: answer, evidence box, `how_verified`. Include revision traps (the
archived A-801 differs in 11 of 16 values; M, `wild.md`), rounded totals, duplicate door numbers, feet-inch
values, handwritten scales, and 5 "cannot be determined" rows per 25.

**RESBIM.** Truth by IfcOpenShell: doors, windows, printed overall dimensions. 25 sampled models hold 140
doors, 99 windows and 0 `IfcSpace` (M, `m12_resbim.py`), so no room areas. Check first which of the 2 storeys
the PNG shows (0.5 h).

**SYN.** Seed layouts from ResPlan (CC BY 4.0; S, `synthetic-data.md`), not Swiss Dwellings. Vary 6 render
styles (thin CAD, hatched, hand jitter, scan, inverted, US imperial with a schedule), 12 label languages,
5 scale modes (bar, ratio, dimension chain, none, conflict), 1 to 3 views per sheet, counts up to 80. Locked
has 2 styles and 4 languages that practice lacks. A new seed gives a fresh pack in minutes.

**Leave-one-out.** Each fitted part (detector weights, dictionaries, few-shot examples) declares `fit_data`.
The report shows seen and unseen cells apart. Pools (M): 5 sources; cubicasa style groups 3,578, 943 and 266
plans; swiss floors de 698, fr 247, it 95; IFC rows et 315, nl 281, da 197, es 196, pl 38, ro 14; 45 families.

## 4. Metrics and the headline

| Case | u |
|---|---|
| Answer exists; correct; evidence passes | 1 |
| Answer exists; correct; evidence fails | 0.5 |
| Answer exists; solver abstains | 0 |
| Answer exists; wrong, or a crash | -1 |
| No answer exists; abstains with the right reason | 1 |
| No answer exists; abstains with another reason | 0.5 |
| No answer exists; gives a value | -1 |

```
item      u_i = min of u over the variants of item i
document  D_d = mean of u_i over the items of document d
suite     S_s = mean of D_d over the documents of suite s
HPS       = 100 * sum of w_s * S_s        (range -100 to 100)
```

Weights (E, fixed now): PUB 0.10, SHIFT 0.15, LANG 0.05, HARD 0.10, COMPOUND 0.15, TRAP 0.15, WILD 0.15,
RESBIM 0.05, SYN 0.05, FREETEXT 0.05. They follow the scenarios of `wild.md` (E). We may change them once,
after Stoa's hint on Saturday.

**The headline is HPS on the practice pack.** Always beside it: the lowest suite score, plain accuracy
(abstention = wrong, in case Stoa scores so), `cost@10`, and the INGEST crash count.

Reasons: the document mean matches a session. The minimum folds robustness into one number. The -1
follows the host: "The I don't knows are super important" (S).

Confidence: report the calibration error and the risk-coverage area. Set the threshold on practice only.

## 5. Evidence scoring

Level 1, no labels, each ask:

1. A count equals the number of marks.
2. An area equals polygon area times scale squared, within 0.5%.
3. Each cited text is found at its box (text layer, or OCR of the crop).
4. A total equals the sum of its parts.
5. Each step names its method: `deterministic` or `model`.

Level 2, where evidence truth exists (cubicasa SVG, swiss geometry, IFC room polygons, SYN, WILD boxes):
marks match true objects one to one, pass at F1 >= 0.9; polygons at IoU >= 0.9; cells at IoU >= 0.5.

Level 3, each milestone, 30 minutes: a teammate checks 20 answers in the viewer with a timer. The harness
plants 5 wrong answers with plausible evidence. Report the median seconds and how many the person caught.

## 6. Free text

1. At pack build a model splits each reference into facts `{key, value, unit, kind}`. A person checks them.
   ifc_bench answers have a median of 6 numbers and 199 characters (M, `m10_stats.py`).
2. Scoring is deterministic. Numbers match within 2% after unit normalisation (sq m, m², feet-inch). Names
   match by alias list. A code or its meaning is enough ("B3" or "aluminium sliding door").
3. Correct when recall >= 0.8, precision >= 0.5 and no stated value conflicts with a fact (D). This blocks an
   answer that lists every number in the model.
4. A reference that says "not available" (120 of 820 rows; M, `questions.md`) is a TRAP item.
5. A model judge with the reference is the fallback for descriptive facts. Validate on 60 labelled pairs,
   Cohen's kappa >= 0.7 (S, `eval-methodology.md`).

## 7. Cost and latency

- Per session, cold cache: each model call (tokens at list price), GPU seconds at $2.37/h (S, `AGENTS.md`),
  CPU seconds, wall time.
- `cost@10` = ingest plus 10 questions. Gate: €0.10 (S, host fact 10). Also the marginal cost per question.
- Cached replay is allowed for scoring. Cost comes from the cold record.
- Latency gate (E): ingest p95 under 60 s, a question p95 under 10 s. A run over a gate is `OVER`.
- A cold full pack costs about €35 to €50 at the target price (E).

## 8. Records and comparison

```
stoa/eval/
  packs/practice-v1/{manifest.json, items.jsonl, docs/}
  packs/locked-v1/              # git-ignored, held by one keeper
  packs/locked-v1.opens.jsonl   # who, when, why, run id
  runs/2026-11-14T0312Z-ab12cd3-vector-first/{manifest.json, answers.jsonl, scores.jsonl, summary.json, audit.json}
  ledger.jsonl                  # per run: HPS, interval, cost@10, parent run, verdict
```

Pack item:

```json
{"item_id":"trap-0042","suite":"TRAP","doc_id":"d_7f3a91","variant_of":"pub-0311",
 "variant":{"kind":"crop_title_band","seed":7},"question":"What is the net area of room 1.06 in m²?",
 "lang":"en","skill":"area_room","answerable":false,
 "truth":{"type":"abstain","reason_code":"NO_SCALE","after_calibration":{"value":23.74,"unit":"m2","tol":0.02}},
 "alt_truth":[],"evidence_truth":{"polygons":[[[412,131],[590,131],[590,255],[412,255]]]},
 "provenance":{"source":"swiss_dwellings","group":"site225","truth_from":"generator_reference"},"canary":"stoa-eval-7c1e"}
```

AnswerRecord:

```json
{"answer":{"value":null,"unit":"m2"},"abstain":true,"reason_code":"NO_SCALE",
 "request":"Give the scale, or click two points of a known length.","confidence":0.93,"convention":null,
 "steps":[{"op":"find_scale","method":"deterministic","result":"none"}],
 "evidence":{"marks":[],"polygons":[{"page":0,"points":[[412,131],[590,131],[590,255],[412,255]]}],"citations":[]},
 "usage":{"calls":[],"gpu_s":0,"cpu_s":0.3,"wall_s":0.4}}
```

Run `manifest.json`: git sha, dirty flag, pack sha256, solver config, model ids, `fit_data`, cache mode, seed.

```sh
uv run stoa-eval build-pack practice --seed 1 --from val
uv run stoa-eval run --pack practice-v1 --smoke --solver http://127.0.0.1:8700 --label vector-first
uv run stoa-eval compare runs/<A> runs/<B>     # difference, interval, suites, each flip, verdict
uv run stoa-eval audit runs/<B>                # the checks of section 10
uv run stoa-eval run --pack locked-v1 --reason "milestone 2" --aggregate-only
```


## 9. Statistics

- The unit is the document. The design effect of a simple solver is 1.86 on cubicasa and 3.48 on swiss
  counts. With 100 drawings its standard error is 2.1 and 2.2 points; the naive formula says 1.7 and 1.2
  (M, `m10_stats.py`).
- Test: a paired bootstrap over documents, stratified by suite, 10,000 resamples of HPS(B) - HPS(A).
- Accept when P(difference > 0) >= 0.95 and no suite has P(difference < 0) >= 0.95.
- Noise floor: 3 cold runs of one build on the smoke subset. Ignore a difference under 2 standard
  deviations. Temperature 0 is not deterministic (S, `eval-methodology.md`).
- WILD has 20 documents: its interval is about ±15 to 20 points (E). Read each flip, not the mean.
- Expected resolution of the practice HPS: ±3 points (E).

## 10. Cheats and checks

`stoa-eval audit` runs these. A failed check blocks promotion.

| Cheat | Why it works on the public set | Check |
|---|---|---|
| Hash or file-name lookup | 4,787 cubicasa PNGs are byte-identical to public files (M, `cubicasa.md`) | Sealed `doc_id`. Re-encode test: pad 1 px, save again; the score must not move. Scan the solver and caches for `model.svg`, `geometries.csv`, IFC-Bench files, the canary |
| Printed id lookup | The swiss title block has the public ids on 100 of 100 sheets (M, `m11_metadata.py`) | Scrub variant with a false plan number |
| Generator fingerprint | Producer "Matplotlib" on 100 of 100 swiss PDFs; creator "junction-dataset-builder/0.1" and the `.ifc` name on 71 of 71 IFC sheets (M) | Scrub variants; SYN and WILD |
| Sibling format | A DXF or IFC lies next to the file | Sealed session; SHIFT gap per format |
| Answer priors | Mode guess 55.3% (M) | Balanced sampling. Swap test: ask the questions of A on document B; the score must fall to the prior |
| Presence leak | Bathtubs are asked only where one exists (M, `swiss.md`) | HARD zero items |
| Correlated answers | Sinks predict toilet bowls: 81.8% against 60.4% (M, `questions.md`) | A count needs its own marks. Two question orders; report flips |
| Twin copying, string routing | 24 templates are 67% of rows (M) | One item per group; LANG; COMPOUND |
| Convention tuning | swiss doors (M) | Two keys and a stated convention |
| Per-document special cases | 3 US sheets hold all 64 questions (M) | Scan code and prompts for sheet codes, site ids, project names |
| Name priors in one model | 29.8% with a row split, 2.1% with a building split (M, `questions.md`) | Group by project |
| Number lists in free text | No rule published | Precision and conflict rules |
| Always or never abstain | | Paired controls; -1 |
| Marks that only fit the count | | Evidence level 2 |
| Warm caches | | Locked runs start cold in a new directory |

## 11. Rules of use

1. Reading our own failures on practice is allowed. Reading its truth to tune is not.
2. One keeper builds the locked pack. Builders and their agents do not open it.
3. At most 4 locked runs (D): first full system, after the hint, Saturday night, final. Each is logged.
4. A locked run returns suite scores, HPS and cost only.
5. If locked and practice HPS differ by more than 8 points (D), we have overfitted. Build a new practice
   pack with a new seed.
6. Regenerate SHIFT, LANG and SYN with a new seed at each milestone.
7. Public annotations live only under `stoa/eval/` and `data/external/`. The solver never imports them.

## 12. Build order

| Step | What | Hours (E) |
|---|---|---|
| 1 | Session API, `AnswerRecord`, scorer, sealed runner, run record. Done when a null solver and the prior solver get an HPS | 3 |
| 2 | PUB; `compare` with the bootstrap | 2 |
| 3 | SHIFT and TRAP. Done when the swiss PDF parser of `swiss.md` drops on the PNG-only variant | 3 |
| 4 | Evidence level 1; INGEST gate | 1.5 |
| 5 | WILD labels, 2 people, from hour 0 | 4 |
| 6 | HARD, RESBIM | 3 |
| 7 | COMPOUND | 3 |
| 8 | `audit`. Done when a planted lookup solver is caught | 2 |
| 9 | LANG, FREETEXT facts | 3.5 |
| 10 | SYN, its own agent from hour 0 | 6 |
| 11 | Locked pack; reserve for the hint | 4 |

Steps 1 to 4 give a usable harness after 9.5 hours of work. The total is 35 hours, which 5 parallel workers
finish before Saturday midday (E).

## 13. Worked example

One item on swiss floor `site225_bldg414_floor1644`: "net floor area of room 1.06". The sheet prints 23.74 m².

| Variant | Output | u |
|---|---|---|
| PDF | 23.74, polygon, scale from the bar | 1 |
| PNG, rotated 90 degrees | 23.31 (1.8% off), IoU 0.93 | 1 |
| PNG, downscaled 0.5 | 5.94: it used "1:100 (A3)" and the page size | -1 |

Item score = min(1, 1, -1) = -1. The public score for this question is 1.

Two runs. These figures are invented to show the arithmetic. They are not measurements.

| Suite | w | A: vector-first | B: A + raster path |
|---|---|---|---|
| PUB | 0.10 | 0.92 | 0.90 |
| SHIFT | 0.15 | -0.10 | 0.35 |
| LANG | 0.05 | 0.60 | 0.62 |
| HARD | 0.10 | 0.20 | 0.30 |
| COMPOUND | 0.15 | 0.40 | 0.42 |
| TRAP | 0.15 | 0.55 | 0.60 |
| WILD | 0.15 | -0.20 | 0.10 |
| RESBIM | 0.05 | -0.40 | 0.25 |
| SYN | 0.05 | 0.30 | 0.45 |
| FREETEXT | 0.05 | 0.10 | 0.10 |

HPS(A) = 23.95. HPS(B) = 41.15. Difference +17.2. Say the bootstrap interval is +11.9 to +22.4 and no suite
falls with P >= 0.95. `cost@10` rises from €0.03 to €0.08, under the gate. Verdict: accept. A public micro
accuracy would show 96% against 95% and reject B.

## 14. Weaknesses

1. The weights are my guess of the hidden set. Another guess can reverse two systems. Read the suite table.
2. The suites hold the tricks I thought of. Variants of clean generated sheets are not real site drawings.
3. Truth for HARD, COMPOUND and evidence comes from public annotations, so we tune to those conventions.
   Two keys lower this risk only.
4. The minimum over variants is strict: one unstable model call gives -1. Variants triple the cost.
5. The -1 and the reason codes are our rules. Stoa may grade by eye or count an abstention as a failure.
6. WILD is small and labelled at night. Its labels can be wrong.
7. A rule and a log protect the locked pack, not access control. The canary finds copies, not reading.
8. Only the timed check tests "verify in seconds". A wrong machine translation fails a right solver.
9. If the hidden set is mostly public templates (probability 0.20; E), part of these 35 hours adds nothing.
