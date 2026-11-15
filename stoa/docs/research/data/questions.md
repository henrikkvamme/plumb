# The question file: templates, priors, noise, splits

Subject: `stoa/data/junction-dataset/questions.jsonl` (127,044 rows) and the preview file (7,990 rows).
Date: 2026-11-13. Every number has a tag: **(M)** measured by the named script, **(R)** read in a
source, **(E)** my estimate. Scripts are in `stoa/analysis/questions/`. Run each with `uv run <script>.py`
from that folder. Each script writes JSON to `stoa/analysis/questions/out/`.

## Findings that change decisions

1. **The micro average is a cubicasa5k score, and half of it is free.** cubicasa5k has 67.3% of the rows (M).
   A constant per template family, fit without seeing a drawing, scores 41.7% micro on a grouped 2-fold
   split, but only 14.6% macro over sources (M, `baselines.py`). On the locked test of `split_v0.json` a
   dev-fit template constant scores 42.2% micro and 13.8% macro over (source, task) cells (M, `split.py`).
   Report macro skill above this prior, never the micro accuracy.
2. **Translation pairs double the count but add no information.** 62,910 translation groups. All of
   them have equal answers in every language (M, `consistency.py`). There are 63,404 independent items,
   not 127,044 (M, `baselines.py`). The 42,757 Finnish cubicasa rows are copies of the English rows.
3. **The answer key is internally consistent. Pure random label noise is not the risk. Convention is
   the risk.** 0 violations in 15 hard checks on swiss_dwellings and ifc_models (M). In cubicasa5k, 26 of
   2,332 plans (1.1%) have more WC rooms than toilet bowls (M). I opened 3 of these plans
   (high_quality-10458, colorful-8238, high_quality-473). Each shows a room marked WC but no toilet symbol.
   The answer "0 toilet bowls" is literally correct. The labels count drawn symbols and labelled rooms,
   from the source annotations. An honest solver loses points where its convention differs from the
   generator, not where the key is random.
4. **Two swiss_dwellings families are text extraction, not drawing reading.** The PDF text layer
   reproduces "How many rooms labelled X" on 6,364 of 6,365 questions (99.98%) and "How many apartments" on
   1,040 of 1,040 (100%) with a short text-matching script (M, `probe_swiss_text.py`). 307 of 1,040 swiss PDFs (29.5%)
   print room areas with m², and on those all room-area answers are in the text (M,
   `probe_text_answer_leak.py`). The two count families are 14,810 of 37,584 swiss rows (39.4%) (M, template counts). A
   high swiss score can come from `get_text()`. The hidden set's "tricky drawings" probably do not have a
   clean text layer (E).
5. **The only change from preview to full is where IFC questions are attached.** All 866 unmatched
   preview rows are ifc_models. 826 storey questions moved from the `.ifc` file to the storey's plan PDF.
   40 model-wide questions moved to the `plan-01` sheet. Answers for the same (path, question) changed in
   0 of 7,124 rows. 0 templates were removed. 915 of 922 preview files are byte-identical in the full set
   (only 7 LICENSE.md files differ) (M, `preview_vs_full.py`). Consequence: the hidden set can ask the same
   question on another modality of the same building. 176 full-set questions on a `plan-01` PDF ask about
   the whole model, so the answer is not on that sheet (M).
6. **New models brought new languages.** The preview ifc_models rows are in en, et, da, de. The full set
   adds nl, es, pl, ro, it (533 rows on templates absent from the preview) (M). The questions use 11
   languages (en, fi, de, fr, it, et, nl, da, es, pl, ro), not 30 (M, `templates.py`). Expect more
   languages in the hidden set. Test with a leave-one-language-out suite.
7. **A split by row or by drawing inflates ifc_models by about 28 points.** A prior keyed on room name
   scores 29.8% on ifc_models with a row split, 29.0% with a drawing split, and 2.1% with a building split
   (M, `baselines.py`). Room names repeat inside one model (for example, 'TUALETTRUUM' rooms of 5.58 m²).
   Eight ifc_bench files are byte-identical to ifc_models files (M). Group ifc_models and ifc_bench together
   by building. `split_v0.json` does this.
8. **About 60% of drawings on disk have no question. The hidden set can ask about them.** Habs, finna,
   europeana and wikimedia: 6,566 drawings with 0 questions (M, `split.py`). ifc_models has 500
   `resbim-*_plan.png` plans with 0 questions (M). opening_design has 987 file stems and questions on 3 (M).
   Only cubicasa5k and swiss_dwellings have questions on every drawing.

## 1. Template inventory and languages

Script: `templates.py`. Full table: `stoa/docs/research/data/templates.json` (one entry per template:
source, language, type, units, family, count, drawings, slot kinds, answer distribution with entropy,
mode, mode share, best constant, top 5, and the paired template).

Method. A template is the question text with its slots replaced. Slots are quoted values (room labels,
room names with ids, storey names, model names, with « », „ “, “ ”, ' ', " " quotes), swiss room ids
(`4.01`, `U1.07`) and apartment ids (`A`, `B`). opening_design keeps the sheet and project as slots.
ifc_bench is free text, so each distinct question is its own template. The pair of a non-English
template is the English template with the most shared (path, slot values) and equal answers. A family is
an English template and its translations.

Counts (M):

| source | rows | templates | families | languages |
|---|---|---|---|---|
| cubicasa5k | 85,514 | 24 | 12 | en, fi (42,757 each) |
| swiss_dwellings | 37,584 | 48 | 12 | en 18,792, de 12,620, fr 4,461, it 1,711 |
| ifc_models | 3,062 | 129 | 21 | en 1,699, de 318, et 315, nl 281, da 197, es 196, pl 38, ro 14, it 4 |
| ifc_bench | 820 | 701 | 8 keyword groups | en |
| opening_design | 64 | 64 | 3 (by type) | en |
| total | 127,044 | 966 | | 11 languages |

Questions per language (M): en 64,132; fi 42,757; de 12,938; fr 4,461; it 1,715; et 315; nl 281; da 197;
es 196; pl 38; ro 14. The stopword detector agrees with `langdetect` on 260 of 265 templates. The 5
differences are langdetect errors (nl read as af, da as no, et as fi) (M). The README's "about 30
languages" describes the drawings, not the questions (E). Swiss questions in German, French or Italian
follow the language of the drawing. Every swiss floor also has an English copy (M).

Slot values are often in another language than the question. English swiss questions quote German,
French or Italian labels ('Bad', 'Camera da letto'). The label language is synthetic: the swiss PDF
footer says "label language and numbering are synthetic" (R, PDF text of
`site3924_bldg6134_floor25547.pdf`).

English templates, with the answer distribution (M, from `templates.json`). "Mode" is the share of rows
that the single most common answer covers. For measures it is the best constant within 2%.

| family | rows (en) | type | mode answer | mode share | entropy bits | partner languages |
|---|---|---|---|---|---|---|
| cc floors (storeys) | 4,787 | count | 1 | 79.9% | 0.85 | fi |
| cc windows | 4,787 | count | 4 | 13.6% | 4.36 | fi |
| cc toilet bowls | 4,782 | count | 1 | 60.4% | 1.41 | fi |
| cc sinks and basins | 4,725 | count | 2 | 51.0% | 1.95 | fi |
| cc showers and tubs | 4,442 | count | 1 | 76.2% | 1.21 | fi |
| cc doors | 3,519 | count | 6 | 11.6% | 4.03 | fi |
| cc saunas | 3,315 | count | 1 | 56.9% | 1.02 | fi |
| cc kitchens | 3,262 | count | 1 | 95.8% | 0.30 | fi |
| cc bedrooms | 2,960 | count | 1 | 31.1% | 2.22 | fi |
| cc bathrooms | 2,384 | count | 1 | 88.6% | 0.65 | fi |
| cc separate WC rooms | 2,332 | count | 0 | 55.6% | 1.33 | fi |
| cc balconies | 1,462 | count | 0 | 51.0% | 1.07 | fi |
| sw rooms labelled X | 6,365 | count | 2 | 22.7% | 3.14 | de, fr, it |
| sw room area (id, label) | 2,076 | area | - | 3.7% | 10.23 | de, fr, it |
| sw apartment net area | 1,875 | area | - | 6.3% | 10.67 | de, fr, it |
| sw apartments | 1,040 | count | 2 | 27.6% | 2.75 | de, fr, it |
| sw doors | 1,040 | count | 26 | 3.5% | 6.02 | de, fr, it |
| sw toilets | 1,040 | count | 2 | 20.8% | 3.35 | de, fr, it |
| sw washbasins | 1,040 | count | 2 | 17.4% | 3.48 | de, fr, it |
| sw windows | 1,040 | count | 11 | 5.4% | 5.21 | de, fr, it |
| sw floor total net area | 1,040 | area | - | 5.0% | 10.00 | de, fr, it |
| sw label total area | 1,017 | area | - | 3.7% | 9.94 | de, fr, it |
| sw bathtubs | 897 | count | 2 | 29.2% | 2.74 | de, fr, it |
| sw showers | 322 | count | 1 | 41.9% | 2.16 | de, fr, it |
| ifc room area | 1,183 | area | - | 6.5% | 7.98 | et, nl, es, da, de, pl |
| ifc rooms on plan | 52 | count | 17 | 25.0% | 4.19 | 6 languages |
| ifc doors on plan | 47 | count | 16 | 19.1% | 4.21 | 6 languages |
| ifc storey total area | 40 | area | - | 20.0% | 4.50 | 6 languages |
| ifc slab volume | 36 | volume | - | 16.7% | 5.06 | de, nl, da |
| ifc stairs on plan | 34 | count | 1 | 67.6% | 1.33 | 6 languages |
| ifc wall volume, length, side area | 33, 32, 32 | volume, length, area | - | 12-22% | 4.7-5.0 | de, nl, da |
| ifc walls, columns, windows on plan | 31, 22, 21 | count | | 19-36% | | 4-6 languages |
| ifc model-wide counts (rooms, walls, windows, doors, beams, stairs, columns, sanitary, lights) | 5-22 each | count | | 9-40% | | up to 8 languages |

The cubicasa generator skips questions per plan. Floors and windows are asked on 100% of plans, balconies
on 27-43% (M, `consistency.py`, `cubicasa_presence_rate_by_collection`). The skip pattern is not
random: a question about a room type is asked mostly when the room type exists (E, from the zero shares:
WC rooms are 0 on 55.6% of plans where asked, kitchens on 2.0%) (M for the shares).

ifc_bench: 701 distinct questions on 820 rows. 637 questions occur once, 64 repeat 2-6 times, with
small rewordings ("fire rating information" versus "fire rating data") (M). Keyword groups (M): spaces
and areas 208, walls and slabs 165, MEP 97, other 96, doors and windows 93, materials 84, software and
project 40, levels 37.

## 2. Preview versus full

Script: `preview_vs_full.py`. Output: `out/preview_vs_full.json`.

| kind of change | rows | example |
|---|---|---|
| storey question moved from `<model>.ifc` to `<model>_plan-NN-<storey>.pdf`, same text and answer | 826 | "How many doors are shown on the floor plan of '1.korrus'?" = 46, from `bsc-esplanades_1807-ep-ar-v18.ifc` to `..._plan-01-1-korrus.pdf` |
| model-wide question moved from one plan PDF to the `plan-01` PDF, same text and answer | 40 | "How many walls are there in the model 'Molio Demo-hus'?" = 189, from `plan-02-klder.pdf` to `plan-01-fundament.pdf` |
| answer, type or unit changed for the same (path, question) | 0 | |
| wording changed | 0 | every unmatched preview question text exists in the full set for the same model |
| template removed | 0 | |
| drawing removed | 0 | 318 of 320 preview drawings still have questions. The 2 others are the `.ifc` files whose questions moved |
| full rows on preview drawings that the preview did not have | 0 | the preview is a strict sample of the full set, apart from the moves |
| files changed | 7 | only `LICENSE.md` of 7 sources. 915 drawing files are byte-identical |

All counts (M). What the moves show (E): Stoa regenerated the question file with a rule that attaches a
storey question to the storey's rendered plan and a model question to the first plan sheet. It did not
regenerate answers. The full set has 368 ifc_models rows still on `.ifc` paths (64 of them model-wide)
and 2,694 on PDFs (M). The full set adds 4 to 16 ifc_models projects, 64 ifc_models templates in 5 new
languages, and 456 ifc_bench question strings (M). The preview README and the full README are identical (M).

## 3. How a public score misleads

Script: `baselines.py`. Output: `out/baselines.json`. Scoring: counts exact, measures within 2%, text exact.
No predictor reads a drawing. "CV" is a grouped 2-fold split, folds by hash of the building key.

| predictor | micro (CV) | macro over sources (CV) | cubicasa5k | swiss | ifc_models | ifc_bench | opening_design |
|---|---|---|---|---|---|---|---|
| (a) constant per family | 41.7% | 14.6% | 55.3% | 14.8% | 3.1% | 0% | 0% |
| (b) constant per template (family x language) | 41.6% | 14.4% | 55.3% | 14.7% | 2.1% | 0% | 0% |
| (c1) constant per (template, label or room name) | 42.2% | 14.8% | 55.3% | 16.7% | 2.1% | 0% | 0% |
| (c1) the same, fit and scored on all rows (in sample) | 43.9% | 36.5% | 55.3% | 18.9% | 44.2% | 0% | 64.1% |

All (M). The in-sample row shows memorisation: room names and question strings repeat. Never fit a prior
or a few-shot set on the rows you score.

(c2) Copying the answer of the paired language scores 100% on the 62,910 groups (M). Any metric that
counts both rows of a pair counts one success twice.

(c3) One other question about the same drawing predicts a lot (M, `P3_conditional_cv`, gold answer of
the best single other family, grouped CV):

| target | best predictor | mode accuracy | conditional accuracy |
|---|---|---|---|
| sw bathtubs | sw apartments | 29.2% | 82.5% |
| sw apartments | sw bathtubs | 27.6% | 74.0% |
| sw toilets | sw washbasins | 18.2% | 68.3% |
| sw washbasins | sw toilets | 16.4% | 68.4% |
| cc toilet bowls | cc sinks | 60.4% | 81.8% |
| cc separate WC rooms | cc sinks | 55.6% | 80.7% |
| cc sinks | cc toilet bowls | 51.0% | 71.0% |
| cc saunas | cc windows | 56.9% | 71.7% |
| cc bedrooms | cc windows | 31.1% | 49.5% |
| cc windows, cc doors | | 13.6%, 11.4% | 16.9%, 17.6% |

A system that answers all questions about one drawing in one call can exploit these correlations
without seeing the asked object (E). Windows and doors carry the real signal: no prior predicts them.

(d) Share by source (M): cubicasa5k 67.3%, swiss 29.6%, ifc_models 2.4%, ifc_bench 0.65%, opening_design
0.05%. A 10-point gain on ifc_models moves the micro average by 0.24 points.

**Proposed headline metric.**
1. Cells: (source, task). Tasks group families by what they measure (`split.py`, `TASKS`): room area,
   apartment area, aggregate area, volume, length, model-wide count, rooms by label, room type count,
   fixture count, openings, structure, free text, schedule lookups. 23 cells on the locked test (M).
2. Per cell: accuracy on the locked test with one row per translation group (keep the language with the
   lower score, or report both).
3. Per cell: skill = (accuracy - prior) / (1 - prior). Prior = the dev-fit template constant
   (`test_prior_template_constant_fit_on_dev` in `out/split_stats.json`).
4. Headline = mean skill over cells. Show the cell table, abstention rate and cost next to it.
5. Second number: worst shift-suite skill (section 6).

## 4. Consistency checks and label noise

Script: `consistency.py`. Output: `out/consistency.json` (each check with up to 8 examples).

| check | kind | violations / checked |
|---|---|---|
| translation pair answers differ | hard | 0 / 62,910 |
| same (path, question) twice | hard | 0 / 127,044 |
| negative value, non-integer count, zero measure | hard | 0 |
| swiss "rooms labelled X" = 0 | hard | 0 / 12,730 |
| swiss room area > total of its label | hard | 0 / 478 |
| swiss asked rooms of a label sum > label total | hard | 0 / 478 |
| swiss all rooms of a label asked, sum differs from total by > 2% | hard | 0 / 25 |
| swiss more room ids asked than the label count | hard | 0 / 1,790 |
| swiss apartment areas sum > floor total | hard | 0 / 1,040 |
| swiss more apartment ids than the apartment count | hard | 0 / 1,040 |
| ifc room areas sum > storey total | hard | 0 / 40 |
| ifc more rooms asked than the room count | hard | 0 / 40 |
| ifc sum of storey counts > model count | hard | 0 / 68 (42 equal) |
| cc separate WC rooms > toilet bowls | hard by name | 26 / 2,332 (1.1%) |
| cc toilet bowls 0 but a WC room | hard by name | 22 / 2,332 (0.9%) |
| cc bathrooms > showers and tubs | soft | 106 / 2,208 (4.8%) |
| cc kitchens > sinks | soft | 37 / 3,235 (1.1%) |
| cc windows = 0 | soft | 23 / 4,787 (0.5%) |
| sw fewer toilets than apartments | soft | 80 / 1,040 (7.7%) |

All (M). What I saw in the drawings (M, by eye): the 3 cubicasa plans with WC rooms and 0 toilet bowls
show no toilet symbol in the WC room (high_quality-10458 is a hand sketch with no fixtures at all). swiss
`site3924_bldg6134_floor25547` (1 apartment, 0 toilets) shows one apartment part with two Zimmer and
three Reduit and no bathroom. Both answers follow the drawing. When all apartments of a swiss floor are
asked, their areas cover a median 91.6% of the floor total (p05 40.7%, never above 102%) (M). The floor
total includes staircases and common rooms.

Noise estimate (E). swiss_dwellings and ifc_models answers are computed from one geometry or IFC source.
They have 0 internal contradictions, so random noise is below about 0.1%. Convention noise is unknown: is
a door leaf in a wall opening a door, is a shaft a room. cubicasa5k: about 1% of plans have a WC/toilet
pattern that looks wrong but matches the drawing. The answers count annotated symbols. Real errors in the
CubiCasa5K annotations exist, but these checks cannot see them. My estimate is 2-5% of cubicasa rows,
mostly windows and doors (E, not measured: it needs a manual audit). ifc_bench text answers have no rule;
14.4% of them say "not available in the model" in some form (M, `answer_formats.py`). The ceiling for an
honest solver is the share of rows where its convention equals the generator's, not 100%.

## 5. Answer formats

Script: `answer_formats.py`. Output: `out/answer_formats.json`.

- Types (M): count 111,763; area 14,243; text 836; volume 138; length 64. Type "other" (named in the
  README): 0 rows.
- Units (M): count -> "count"; area -> "m2" (swiss, ifc_models) or "ft2" (opening_design, 9 rows); volume
  -> "m3"; length -> "m"; text -> null (836 rows). Every measure question names its unit in the text,
  except 5 opening_design area questions that rely on the schedule's SF (M).
- Precision (M): swiss areas have 2 decimals (10,814), 1 (1,090) or 0 (112), so trailing zeros are
  dropped. ifc_models areas mostly 2 decimals; volumes and lengths mostly 3. opening_design areas are
  integers in ft². The 2% tolerance is wider than the rounding in every case.
- Ranges (M): swiss area 1.02-1,723.34 m²; ifc area 0.22-2,482.22 m²; cubicasa counts 0-92; swiss counts
  0-157; ifc counts 1-3,104.
- Text answers (M): 820 ifc_bench, 16 opening_design. Median 196 characters, p90 739, max 5,895. 70.7%
  are multi-line lists. 83.1% contain a number. Units in text: "sq m" 119, "m²" 25, "cu m" 23, "mm" 86,
  "%" 158. 120 (14.4%) contain an abstention phrase, and 36 contain an estimate word. One opening_design
  text answer is a bare number ("19", hardware group). Free text needs a rubric or an LLM judge. Exact
  match scores near 0 (E).

## 6. Split design

Script: `split.py`. Manifest: `stoa/analysis/questions/split_v0.json`. Stats: `out/split_stats.json`.

Grouping keys (`qcommon.group_key`) and sizes (M):

| source | key | groups with questions | rows per group (min/median/max) |
|---|---|---|---|
| cubicasa5k | plan id (`colorful-268` -> `268`) | 4,787 | 6 / 18 / 24 |
| swiss_dwellings | site (1 site = 1 building = 1 floor in this set) | 1,040 | 18 / 36 / 44 |
| ifc_models + ifc_bench | project (`bsc-molio`, `rwth-digitalhub`); bench files mapped to the same project | 16 + 9 bench-only | 4 / 128 / 630 |
| opening_design | project folder | 2 | 20, 44 |
| habs / finna / europeana / wikimedia | survey id / record id / record prefix / file | 1,271 / 312 / 252 / 2,175 | no questions |

Seven projects have questions in both ifc_models and ifc_bench (molio, institute, digitalhub, fzk-haus,
smiley-west, duplex, clinic) (M). Eight file pairs are byte-identical (M, sha1).

Algorithm. Strata: cubicasa5k, swiss, ifc (both IFC sources), opening_design. Targets 60/20/20. Groups
are visited in sha256(seed:group) order, largest first in strata with under 40 groups. Each group goes to
the split with the largest deficit over its families and languages. Seed `stoa-split-v0-2026-11-13`.
sha256 of the manifest core: `607f5dd49025092c72fc464523036254af0aabf54b7547bf914b0e883d7b8eea`.

Result (M): dev 76,414, val 25,388, test 25,242 rows. Per source (dev/val/test): cubicasa5k
51,314/17,098/17,102; swiss 22,544/7,530/7,510; ifc_models 2,024/572/466; ifc_bench 512/188/120;
opening_design 20/0/44 (Sports_Complex to test, CTR to dev). No family is missing from test. Two
families are missing from dev: ifc light fixtures (6 rows) and opening_design area (9 rows). Small-language
ifc rows cannot be balanced, because one model carries one language: et, da in dev only; es in val only;
pl, ro in test only. 4,551 groups without questions also have a split, for unlabelled checks.

Rules for use (E): tune only on dev. Check on val. Open test once per milestone and log every opening.
Report ifc and opening_design with confidence intervals: 16 and 2 groups.

Shift suites (definitions in `split_v0.json`, `shift_suites`):
- leave-one-source-out: 5 suites (64 to 85,514 rows).
- leave-one-language-out: 10 non-English languages. Hold out the language for prompts, rules and label
  dictionaries. For swiss, also remove the label vocabulary of that language.
- leave-one-task-out and leave-one-family-out: 45 families.
- modality swap: the same question on `.ifc` and on the plan PDF; on swiss PDF, DXF and PNG. The answer
  must not change.
- unlabelled sources: 6,566 historic scans plus 500 resbim plans. Use them for abstention and calibration
  ("I do not know" rate, cost), since no key exists.
- text-layer ablation (my proposal): score swiss on the PNG copy, or on the PDF with text removed. The gap
  shows how much of the score is `get_text()`.

## Risks for the hidden test set

1. Text-layer shortcuts (finding 4) do not transfer to scans. The 6,566 historic scans have no text layer.
2. Model-wide questions on a single sheet (176 rows) need the IFC or an explicit "not on this sheet". A
   sheet-only solver must abstain or ask for the model.
3. Room-name priors and few-shot examples leak across rows of one model (finding 7).
4. New languages: 5 of 9 ifc_models languages appeared only after the preview (finding 6).
5. New templates. The public set has 45 English families. The 456 new ifc_bench strings show that Stoa
   adds questions freely. A template router tuned to 45 families fails on new phrasing.
6. Generator conventions (what counts as a door, a window, a WC). A solver that is "right" by a human
   reading can score lower than one that copies the convention.
7. cubicasa5k labels likely come from the public CubiCasa5K SVG annotations (E, not checked: no download
   in this task). swiss geometry is from Swiss Dwellings v3.0.0 on Zenodo (R, PDF footer). ifc_bench uses
   the public IFC-Bench v2 questions (R, dataset README). A score that uses those public labels is leakage.

## Open questions for Stoa

1. Is the hidden set built with the same generator and templates, or written by hand like opening_design?
2. Are the hidden drawings new buildings, or new questions on the public drawings?
3. Which languages does it use, and does a question keep an English pair?
4. Will model-wide questions appear on plan sheets, and is the `.ifc` file available then?
5. How is free text scored (rubric, LLM judge, key facts)? Does "not available in the model" count?
6. How do you score an abstention or a request for a scale? Is it better than a wrong answer?
7. Do you score each translation of a question separately?
8. Are the historic scans in the hidden set, and with which question types?
9. Conventions: does a doorway without a leaf count as a door in swiss_dwellings, as in cubicasa? Is a
   double sink one sink everywhere?

## Reproduce

```sh
cd stoa/analysis/questions
uv run templates.py          # -> docs/research/data/templates.json, out/templates_summary.json
uv run preview_vs_full.py    # -> out/preview_vs_full.json (hashes all files, about 1 minute)
uv run baselines.py          # -> out/baselines.json
uv run consistency.py        # -> out/consistency.json
uv run answer_formats.py     # -> out/answer_formats.json
uv run split.py              # -> split_v0.json, out/split_stats.json
uv run probe_swiss_text.py   # -> out/probe_swiss_text.json
uv run probe_text_answer_leak.py  # -> out/probe_text_answer_leak.json
```

`qcommon.py` holds the shared template, language, scoring and grouping code. Drawings I looked at: 17
cubicasa5k, 14 swiss_dwellings, 13 ifc_models plans and resbim PNGs, 1 opening_design sheet, 13 historic
scans (habs, finna, europeana, wikimedia).
