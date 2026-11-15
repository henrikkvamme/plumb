# vlm-direct: the direct VLM baseline

A hosted model sees the first page and one question. No tools, no checks. This is the number that every tool
pipeline must beat. All runs are on the VAL partition, sealed (sandbox on), `--seed vlm`, `--jobs 4`.

## What I built

- `src/bp/tools/render.py`: `render_page(path, side, page=0) -> bytes | None`. A PDF page is drawn with
  PyMuPDF so that the longest side is exactly `side`. An image is reduced with Pillow to at most `side` (never
  enlarged), and transparency goes onto white. A DXF or IFC file returns None. Also `page_count`.
- `src/bp/solvers/vlm_direct.py`: `VlmDirectSolver`. Ingest renders page 1 once. Ask sends the image and the
  question with a short system prompt that asks for JSON `{"answer","unit","confidence","reason_if_null"}`.
  Environment: `BP_VLM_MODEL`, `BP_VLM_SIDE`, `BP_VLM_MIN_CONF` (as asked), plus `BP_VLM_EFFORT`
  (`reasoning_effort`) and `BP_VLM_MAX_TOKENS` (default 2048).
  - A null answer gives an abstention (reason guessed from `reason_if_null`). A confidence under
    `BP_VLM_MIN_CONF` gives an abstention that keeps the answer as `best_estimate`.
  - A reply with no JSON gives status "error". A failed router call gives status "error".
  - A DXF or IFC file abstains as UNSUPPORTED (no model call).
  - `cost_usd` is the `ChatResult.cost_usd` of the call.
- `src/bp/solvers/vlm_direct_study.py` (new file, my slug): the threshold study. It reads saved `items.jsonl`,
  turns each answer under a threshold into an abstention, scores again with the real keys, and prints the table.
  It reads labels, so it is not a solver and it runs outside the sandbox.
- `tests/test_vlm_direct.py`: 32 tests (render sizes, parsing, every record kind, env variants). No network.

All my runs used `BP_VLM_MIN_CONF=0`, so only a null answer abstains. The threshold comes from the study.

## Unit of cost: credits, not USD (read this)

`usage.credits_charged` is in router credits. The Hostinger setup doc says 250 credits cost USD 2.50, so
**1 credit = USD 0.01**. The sonnet price check agrees (264 credits per million input tokens = USD 2.64).
`bp.llm` and the ledger call the number "usd", and the default cap is 15. So the "$" columns in LEDGER.md are
credits, and the cap of 15 is USD 0.15. I read my "5 USD" limit as 500 credits (USD 5). I set
`BP_LLM_CAP_USD=5000` in my shell for the runs. Everything below says credits. Divide by 100 for USD.

My total spend: **435.9 credits = USD 4.36** (own tag `vlm-direct:*` in `llm_spend.jsonl`; 5 probe calls at the
start cost 6.8; a stopped dev run cost 3.6, see "What failed").

## Commands

```sh
cd stoa; set -a; . ../infra/hostinger/secrets.env; set +a
export BP_LLM_CAP_USD=5000 BP_VLM_MODEL=<model> BP_VLM_SIDE=1568 BP_VLM_MIN_CONF=0 [BP_VLM_EFFORT=minimal]
uv run bp run bp.solvers.vlm_direct:VlmDirectSolver --source cubicasa5k --partition val --docs 40 --seed vlm --jobs 4 --note "..."
uv run bp run bp.solvers.vlm_direct:VlmDirectSolver --source swiss_dwellings --partition val --docs 15 --seed vlm --jobs 4 --note "..."
uv run bp diff <run a> <run b>
uv run python -m bp.solvers.vlm_direct_study <run id> [<run id> ...]   # writes experiments/notes/vlm-direct-threshold.json
```

`--docs N` keeps a prefix of one fixed document order, so 20 docs are a subset of 40 and 10 are a subset of 15.
cubicasa5k 40 docs = 361 items = 722 asked rows (with translations). swiss_dwellings 15 docs = 272 items = 544 rows.

## Results (VAL, side 1568)

Run ids have the prefix `20261114-` and the suffix `-bp.solvers.vlm_direct.VlmDirectSolver-stoa`.
Score is the mean over items with a 95% cluster bootstrap interval. "Credits/doc" is credits per document (all
questions of a document, with translations).

| Model (effort) | Source, docs | Run | Items | Score | Acc % | Answered % | Wrong % | Credits/doc |
|---|---|---|---|---|---|---|---|---|
| gemini-3.5-flash-lite | cubicasa5k 40 | `013518` (first 20 docs also in `013242`) | 361 | +0.199 [+0.080, +0.302] | 57.1 | 94.2 | 37.1 | 1.04 |
| gemini-3.5-flash-lite | swiss 15 | `013723` | 272 | -0.228 [-0.343, -0.107] | 30.2 | 83.1 | 52.9 | 2.14 |
| claude-haiku-5.5 | cubicasa5k 40 | `014038` | 361 | +0.219 [+0.102, +0.321] | 58.5 | 95.0 | 36.6 | 0.84 |
| claude-haiku-5.5 | swiss 15 | `015330` | 272 | +0.085 [-0.004, +0.180] | 52.2 | 95.2 | 43.8 | 2.60 |
| gpt-5-mini (minimal) | cubicasa5k 40 | `020346` (a free rerun from the cache) | 361 | -0.280 [-0.407, -0.151] | 36.0 | 100.0 | 64.0 | 0.63 |
| gpt-5-mini (minimal) | swiss 15 | `014737` | 272 | -0.452 [-0.586, -0.322] | 26.1 | 97.4 | 71.3 | 1.58 |
| gemini-3.5-flash (minimal) | cubicasa5k 20 | `020354` | 192 | +0.214 [+0.046, +0.359] | 59.9 | 98.4 | 38.5 | 5.86 |
| gemini-3.5-flash (minimal) | swiss 10 | `020756` | 178 | -0.062 [-0.202, +0.073] | 35.4 | 77.0 | 41.6 | 11.4 |
| claude-sonnet-5.5 | not run | - | - | - | - | - | - | about 1.5 per call |

Errors: haiku on swiss had 0.74% error rows (4 parse failures). Every other run had
0 errors. The ledger "Cost $" of `013518` (19.36) holds only the new half, the first 20 docs came from the
cache of `013242` (22.06). The real cost of the 40 docs is 41.4 credits. The ledger cost of `020346` is 0 (cache);
the first run of it cost 25.05 credits.

By cell (swiss, VAL):

| Model | area/pdf score (acc %, answered %) | count/pdf score (acc %) |
|---|---|---|
| flash-lite (15 docs) | -0.307 (9.1, 48.9) | -0.190 (40.2) |
| haiku (15 docs) | -0.557 (20.5, 94.3) | +0.391 (67.4) |
| gpt-5-mini (15 docs) | -0.761 (10.2, 96.6) | -0.304 (33.7) |
| flash (10 docs) | -0.119 (10.2, 32.2) | -0.034 (47.9) |

Same items, all four models (cubicasa 20 docs + swiss 10 docs = 370 items, so flash can be compared):

| Model | Score | Acc % | Answered % | Wrong % |
|---|---|---|---|---|
| haiku-5.5 | +0.124 [+0.038, +0.214] | 53.8 | 94.9 | 41.4 |
| flash (minimal) | +0.081 [-0.037, +0.196] | 48.1 | 88.1 | 40.0 |
| flash-lite | -0.032 [-0.165, +0.103] | 42.7 | 88.6 | 45.9 |
| gpt-5-mini (minimal) | -0.386 [-0.511, -0.266] | 30.3 | 99.2 | 68.9 |

All 633 items (cubicasa 40 + swiss 15), three models: haiku +0.161 [+0.083, +0.237] acc 55.8%; flash-lite +0.016
[-0.084, +0.127] acc 45.5%; gpt-5-mini -0.354 [-0.453, -0.254] acc 31.8%.

Paired differences (`bp diff`, b minus a):

| a to b | Items | Score difference | Significant |
|---|---|---|---|
| lite to haiku, cubicasa 40 | 361 | +0.019 [-0.094, +0.131] | no |
| lite to mini, cubicasa 40 | 361 | -0.479 [-0.588, -0.372] | yes |
| lite to flash, cubicasa 20 | 192 | +0.052 [-0.070, +0.188] | no |
| haiku to flash, cubicasa 20 | 192 | +0.021 [-0.129, +0.168] | no |
| lite to haiku, swiss 15 | 272 | +0.313 [+0.176, +0.431] | yes |
| lite to mini, swiss 15 | 272 | -0.224 [-0.292, -0.151] | yes |
| lite to flash, swiss 10 | 178 | +0.180 [+0.061, +0.305] | yes |
| haiku to flash, swiss 10 | 178 | -0.112 [-0.298, +0.067] | no |

Reading: with no threshold, no model clears +0.22 on cubicasa, and every model is near or under zero on swiss
areas. For reference the prior (most frequent answer, no document) gets 55.3% right on cubicasa
rows (TRUST.md). The best row accuracy of the 40-document cubicasa runs is 65.9% (haiku), so the model adds only a little over
a guess on counts. The confidence field carries the value (next section).

## Confidence-threshold study (no new calls)

From the saved items of the best model (haiku, 633 items, `014038` and `015330`). Rows from a threshold
t: an answer with confidence under t becomes an abstention. This is IN-SAMPLE on VAL: the best threshold is
chosen on the same items. I could not fit it on DEV (see "What failed"). Use the curve, not the exact peak.

| Threshold | Score [95%] | Acc % | Answered % | Wrong % | Acc of answered % |
|---|---|---|---|---|---|
| 0.00 | +0.161 [+0.083, +0.237] | 55.8 | 95.1 | 39.7 | 58.6 |
| 0.25 | +0.216 [+0.146, +0.282] | 55.3 | 88.5 | 33.6 | 62.5 |
| 0.30 | +0.240 [+0.171, +0.302] | 55.1 | 85.8 | 31.1 | 64.3 |
| 0.35 | +0.330 [+0.270, +0.384] | 52.9 | 72.2 | 19.9 | 73.3 |
| 0.45 | +0.348 [+0.298, +0.391] | 48.2 | 61.0 | 13.4 | 79.0 |
| **0.50** | **+0.352 [+0.301, +0.398]** | 47.4 | 58.9 | 12.2 | 80.4 |
| 0.55 | +0.351 [+0.304, +0.392] | 43.3 | 50.9 | 8.2 | 85.1 |
| 0.60 | +0.348 [+0.304, +0.387] | 42.7 | 49.9 | 7.9 | 85.4 |
| 0.70 | +0.318 [+0.271, +0.360] | 35.7 | 39.0 | 3.9 | 91.5 |
| 0.80 | +0.288 [+0.237, +0.332] | 32.4 | 35.4 | 3.6 | 91.5 |
| 0.90 | +0.183 [+0.137, +0.228] | 19.3 | 19.6 | 0.9 | 98.4 |

The curve is flat from 0.45 to 0.60 (about +0.35). By source at 0.50: cubicasa +0.321, swiss +0.393. So the
direct baseline to beat is **about +0.35 score at 40 to 60% answered, with abstention on the rest** (haiku,
threshold 0.5), and +0.16 with no threshold. Other models (same study, all 633 items unless noted):
flash-lite peaks at +0.090 (threshold 0.90; it is over-confident, almost every answer says 0.8 or 0.9);
gpt-5-mini peaks near -0.006 (it never reaches a useful score); flash minimal (370 items) peaks at +0.200 at 0.95.
The full tables are in `experiments/notes/vlm-direct-threshold.json` (key is the run ids).

## What failed or is weak

- **Run id clash.** The haiku and gpt-5-mini cubicasa runs started in the same second and got the same run id
  `20261114-014038-...`. The haiku run saved last and kept the directory. The mini result was lost. I ran it
  again from the cache (free) as `020346`: the score is identical (-0.2798). The ledger row `014038` is haiku.
  Fix for the lead: put the model or a counter in `new_run_id`, or use a lock.
- **Dev threshold fit was stopped.** I started a haiku run on DEV (`021221` cubicasa 20 docs, `021344` swiss 8
  docs) to fit the threshold out of sample. The lead's stop file (`experiments/LLM_STOP`) blocked the calls, so
  76% and 100% of the rows are errors. **Ignore these two ledger rows.** They hold no result. I made no further call.
- **Sonnet not run.** One call is about 1.5 credits, so 722 plus 544 rows is about 1,900 credits. Two probe calls
  only. gemini-3.5-flash with default thinking costs 1.7 credits per call (1,200 reasoning tokens), so I ran it with
  `reasoning_effort=minimal` (about 0.30 per call) and on fewer documents (20 and 10). The flash numbers cover
  fewer items, so compare them only on the common 370 items.
- gpt-5-mini with `minimal` effort is very over-confident and answers every question. It might do better with
  more reasoning, which I did not test.
- The cubicasa images show the model no scale or legend. It counts windows and doors by eye. Counts of small
  symbols (doors, windows, sinks) are where it fails.
- Parse failures: only haiku on swiss, 4 rows of 544. I did not look at the cause (maybe an empty reply from
  reasoning tokens over `max_tokens`).
- I did not run the 2400 px variant. `BP_VLM_SIDE=2400` works (tests cover it), but the budget went to models.
- The LOCK partition was never touched.

## What I would try next

1. A run of haiku with `BP_VLM_SIDE=2400`, and with a prompt that says "count each symbol, list them" (about 45
   credits per run on 40 plus 15 documents).
2. Fit the threshold on DEV (about 40 credits) and report the VAL score of that threshold. Expect a little
   under +0.35.
3. Use the VLM only as a reader inside the tool pipeline, and use its confidence as one input. The study shows
   that haiku's own confidence separates right from wrong well (80% accurate at 0.5, 91% at 0.7).
4. Areas on swiss are a lost cause for the direct path (-0.56 haiku, 10 to 20% accuracy): a tool must read the PDF
   vectors. Counts on swiss are the best direct cell (haiku +0.39).
5. Cost target (10 cents per document): flash minimal is at 6 to 11 cents per document with translations, haiku
   at 1 to 3 cents, flash-lite 1 to 2 cents. A pipeline that asks each question with the image again pays the image
   each time. Send the image once and ask all questions in one call to cut the cost by about 10x.
