# Wild sources: opening_design and the historic scans

Scope: `opening_design` (real US practice drawing sets) and the four historic sources that have no
questions: `habs`, `finna`, `europeana`, `wikimedia`. Date: 2026-11-13. All scripts are in
`stoa/analysis/wild/` (PEP 723, run with `uv run`), outputs in `stoa/analysis/wild/out/`.
Nothing was downloaded.

Labels: **[M]** = measured by a script or counted by eye on the sheet. **[R]** = read in a source
(README, LICENSE.md, host talk). **[E]** = my estimate.

Probe file: `stoa/docs/research/data/wild-probe-questions.jsonl` (50 rows, built and path-checked by
`build_probe_questions.py`).

## Findings that change decisions

1. **The public set gives almost no signal for these sources.** 64 questions on 3 of 987
   opening_design drawings, and 0 questions on 6,566 historic drawings [M, `coverage.py`]. The
   README "roughly 40%" is exactly the share of drawings with questions: 5,939 / 14,550 = 0.408 [M].
   So 8,600 drawings, which include all scans and all real CAD sheets, have no labels. A high public
   score says nothing about them. The host said the hidden set is "much more difficult" and has
   "tricky drawings" with the same extensions but different content, and that scans and hand-drawn
   sheets exist [R, `context/stoa-drawings/2026-11-13-2308-38-conversation.md`].
2. **The 64 opening_design questions are schedule lookups only, and a text-layer parser solves
   them.** A 40-line parser gets 14 of 16 reference values on A-801. Both misses are parser defects,
   not hard cases [M, `od_probe_schedule.py`]. No question tests a plan, a scale, a dimension
   chain or a scan. The same kind of schedule is common: 25 PDFs contain "DOOR SCHEDULE", 8
   contain "WINDOW SCHEDULE" and 60 contain a finish or room schedule, and only 3 PDFs have
   questions [M, `od_inventory.py`].
3. **Superseded revisions sit next to current sheets, and the answers change.** 43 sheet codes have
   2 to 6 files [M, `od_revisions.py`]. On the 2015-08-14 archive A-801, 11 of the 16 reference
   values differ from the current A-801 (the sheet with questions): 41 doors, not 38. Fitness Center
   118 is 4068 SF, not 5183. Clinic 121 is 5919 SF, not 2470. Door 128.B is 9'-0" x 12'-0", not
   12'-0" x 14'-0" [M, parser plus eye]. A solver that matches by sheet code, by project or by
   memory gives wrong answers. Read the given file only.
4. **Printed totals are rounded and differ from the sum of the rows.** Aalseth room schedule: total
   3672 SF, rows 3671. Downtowner A501: fence 1159 vs 1160, storefront 871 vs 872, polycarbonate
   435 vs 433. 725 E Johnson occupant load: 10.5 vs 10.6 [M, by eye on text layer]. Areas pass the
   2% rule either way, but a count-type total must be exact. Rule: when the question asks for "the
   total", quote the printed total. Compute only when no total is printed, and say which.
5. **Historic scans need "cannot be determined" and a scale check.** In 120 sampled scans [M by eye,
   `scan_classes.py`]: 5 are not drawings at all (a poster, a letter, 2 watercolours, a medal
   design) and 3 more are maps. A scale bar
   or ratio is present in 28/30 habs, 24/30 finna, 15/30 europeana and 17/30 wikimedia sheets.
   Room labels are present in only 6/30 habs sheets. The public set has about 25 "not available"
   answers, all in ifc_bench [M, grep]. No public question trains the "no scale, so no area" case.
   The host said "The I don't knows are super important" [R].
6. **LICENSE.md metadata is a strong hint, but it is not the sheet.** Every file has a row [M,
   `meta_lookup.py`]. Titles give the building and place in all sources, the year in 51% of finna
   rows and "sheet X of Y" in 67% of habs rows. But in 4 of the 20 historic probe files the metadata
   differs from the sheet (5 differences): "Hertfordshire" where the sheet says "Herefordshire", the engraver
   "Laing" where the sheet names the architect "Mr. Nicholson", "Thesstal" vs "Tesstal", "Crowfield
   Ruins" vs "Crowfield Hall", "Harold J. Szold House" vs "Fifty-Seven Willow Street" [M by eye].
   Hidden "tricky drawings" will likely have no row at all [E]. Use metadata only as a flagged hint.
7. **Sheet text is often rotated, and naive line grouping merges table rows.** Many opening_design
   pages have `page.rotation = 90`. PyMuPDF words come back unrotated; the first probe returned 0
   rows until words were mapped with `page.rotation_matrix` [M]. Line grouping still dropped 1 door
   row per A-801 version and 2 of 37 sheet-list rows on G-100 [M]. 74 opening_design PDFs have no
   text layer at all, some of them hand-drawn sketches [M, `od_revisions.py`].
8. **Historic scans are small, multilingual and damaged.** europeana median 1.26 MP with 237 files
   under 1000 px on the long side; wikimedia median 2.07 MP with 579 under 1000 px [M,
   `scan_sample.py`]. The sample shows 11 languages in europeana alone, 11 of 30 europeana
   and 11 of 30 finna sheets with medium or heavy damage, and 8 camera photos of sheets [M by eye].

## 1. opening_design

### Inventory [M, `od_inventory.py`, `od_revisions.py`]

| item | value |
|---|---|
| files | 1006 plus LICENSE.md, in 39 projects |
| formats | 678 pdf, 271 dwg, 48 ifc, 9 dxf |
| PDF pages | 2741; 465 PDFs have 1 page, 213 have more than 1, 16 have 20 or more |
| no text layer | 74 PDFs (scanned sketches, markups) |
| sheet sizes | 42x30 in: 329, 17x11 in: 120, 34x22 in: 72, 8.5x11 in: 42 |
| sheet kind from file name | other 251, plan 160, detail 108, section 51, elevation 50, structural 23, schedule 18, site 7, mep 6, cover 4 |
| text matches | "DOOR SCHEDULE" 25 PDFs, "WINDOW SCHEDULE" 8, finish/room schedule 60, area in SF 146, feet-inch dimensions 450 |
| revisions | 220 single-page PDFs carry a sheet code, 147 project+code groups, 43 codes with more than 1 file (116 files), max 6 (Sports_Complex A100) |
| folders | 100 PDFs in "Current Set" folders, 525 in Transfer folders (dated issues, `_Archive`) |
| largest projects | Sports_Complex 164 pdf / 130 dwg / 20 ifc, CTR 161 pdf, Vacation_Rental 129 files, Lake_Kegonsa 49 pdf, Aalseth 47 pdf |
| licence | CC-BY-SA-4.0 989 rows, MIT 17 [M, `meta_lookup.py`] |

### The 64 public questions [M, read from `questions.jsonl`]

| sheet | questions | what they test |
|---|---|---|
| Sports_Complex "Sheets - Current Set" A-801 Door and Finish Schedules | 41 | door counts by type, material, frame, note, width, height, room; text lookups; finish-schedule areas, sums, filters; largest room |
| Sports_Complex A-701 Restrooms | 3 | fixture counts in enlarged plans 6A and 6B (the only questions that need a drawing, not a table) |
| CTR A700 Schedules | 20 | door and window type counts, totals, floor filters, one derived count (379 ESDH3066 units) |

- Types: 39 count, 9 area (unit `ft2`), 16 text (unit null). No length, no volume [M].
- The questions are hand-written, not template output: the wording varies, and each one names
  the project and the sheet ("On sheet A-801 of the Xcel Sports Complex drawings, ...") [M].
- Text answers join a code and its meaning: "B3 (aluminium sliding door)", "F4 - resilient
  flooring (T.B.D.)", "3 rooms, 4541 SF", "12'-0\" wide x 14'-0\" high", "35 1/2\" wide x 77 1/2\"
  high" [M]. The README says text answers are "free-form" [R].
- What a scoring rule would likely accept [E]: the code alone or the meaning alone if an LLM judge
  or a fuzzy match is used; exact numbers inside text answers. Safe output: give the code, the
  meaning and the number in the same order as the schedule, in the drawing's units.

### Skills the public questions do not test, and sheets that support them [M]

| skill | example sheet (all with no public question) |
|---|---|
| window schedule totals, type filters | Aalseth A600: 39 windows, 30 casements |
| room schedule areas with rounding | Aalseth A600: 3672 SF printed, 3671 by rows |
| wall and glazing schedules | Downtowner A501: 85 walls / 8330 SF; 26 tempered IGUs |
| duplicate door numbers | Downtowner A500: 46 rows, 43 distinct numbers |
| plan note reading | 6060 McKee A101: tenant suite "~3080 SF" |
| scale reading | 6060 McKee A101: 1/2" = 1'-0"; 725 E Johnson: 1/4" = 1'-0" |
| plan symbol counts | 725 E Johnson: 6 chairs at the meeting room 102 table |
| cover sheet lists | Sports_Complex G-100: 37 sheets, occupant load 677 |
| revision traps | Sports_Complex `_Archive` A-801: 41 doors, 4068 SF |

### Schedule probe: agreement and disagreements [M, `od_probe_schedule.py`]

Raw agreement on the current A-801: 14 of 16 reference values (88%). By eye, the reference answers
are right. Five disagreements found while probing:

1. Door count: parser 37, reference 38. The parser merged row 130.B into the row above.
2. Doors in room 128: parser 3, reference 5. The parser counted door-number prefixes "128.x". The
   reference counts the room-number column (122.C, 124.B, 128.A, 128.B, 128.C). The question is
   ambiguous; the reference uses the room column.
3. Archive A-801 door count: parser 40, eye 41. Same merge defect.
4. G-100 sheet list: text-line extraction 35, eye 37. Two rows merged.
5. First run on A-801: 0 rows for every value, because the page has `rotation = 90` and the words
   were not mapped through `page.rotation_matrix`.

## 2. Historic scans

### Files and image statistics [M, `scan_sample.py`, `coverage.py`]

| source | drawings | median MP | long side 3000 px | long side < 1000 px | colour (sat > 0.15) | near b/w |
|---|---|---|---|---|---|---|
| habs | 1506 | 6.2 | 1506 | 0 | - | 1503 |
| finna | 1800 | 6.58 | 1791 | - | 618 | - |
| europeana | 1085 | 1.26 | - | 237 | 567 | - |
| wikimedia | 2175 (+135 svg) | 2.07 | 0 | 579 | 365 | 1228 |

### Classification of 120 scans by eye [M, `scan_classes.py`; seed 2026, 30 per source]

| field | habs | finna | europeana | wikimedia |
|---|---|---|---|---|
| plan | 4 | 8 | 3 | 21 |
| mixed views on one sheet | 6 | 9 | 11 | 7 |
| elevation / section | 5 | 2 | 8 | 1 |
| detail / axonometric | 7 | 3 | 3 | 0 |
| site / map / cover | 8 | 6 | 2 | 1 |
| not a building drawing | 0 | 2 (poster, letter) | 3 (2 watercolours, 1 medal) | 0 |
| languages | en 30 | sv 13, fi 10, fi+sv 5, other 2 | en 6, fr 4, nl 3, de 3, la 2, pt 2, it, es, hu, et, hr, 5 unclear | de 5, fr 5, en 4, sv 4, ru 3, hu, no, uk, 6 none or unclear |
| scale bar or ratio | 28 | 24 | 15 | 17 |
| dimension strings | 15 | 8 | 4 | 1 |
| room or space labels | 6 | 7 | 7 | 15 |
| title block or stamp | 30 | 10 | 2 | 0 |
| hand / CAD / print / digital | 16 / 14 / 0 / 0 | 29 / 0 / 1 / 0 | 19 / 0 / 11 / 0 | 12 / 0 / 12 / 6 |
| medium or heavy damage | 0 | 11 | 11 (4 heavy) | 5 |
| poor legibility | 0 | 5 | 3 | 2 |
| camera photo of a sheet | 0 | 0 | 5 | 3 |

What this means [E]:
- **habs** is the clean source: English, a full title block on every sheet (building, place,
  survey number, sheet X of Y, delineator, date), a scale on almost all. But only 6 of 30 sheets
  have room labels. Many carry narrative text with facts (year built, architect).
- **finna** is hand-drawn, Swedish or Finnish, often faded, with stamps, signatures and dates. Scale
  bars are common; room labels are rare.
- **europeana** is the hardest: book engravings, watercolours, photos of sheets, heavy damage, a
  scale on half, a dozen languages, small files.
- **wikimedia** is mostly plans (21 of 30) with room labels on half, but crops with no title block,
  born-digital diagrams, and some mirrored or photographed images (47712772 has a mirrored scale
  bar).

### Public templates that transfer [E, based on the sample]

| template | habs | finna | europeana | wikimedia |
|---|---|---|---|---|
| count labeled rooms / rooms of a kind | weak (6/30) | weak (7/30) | weak (7/30) | good (15/30) |
| count windows, columns, spans, storeys, minarets on an elevation | good | good | good | weak |
| read a dimension (length) | good (15/30) | weak | rare | rare |
| length or area from the scale bar | good | fair (bars are faded) | weak | fair |
| read title, place, year, architect, sheet number, scale | good | good (stamps) | fair (captions) | weak |
| room area from geometry | rare | rare | rare | fair |
| "cannot be determined" (no scale, no plan, not a drawing) | rare | needed | needed | needed |

### What a person can verify

- Counts of labeled items, printed text (title, year, architect, scale ratio) and printed
  dimensions: yes, on a zoom, in 1 to 3 minutes per question [M, done for the 25 probes].
- Lengths from a scale bar: yes, with a pixel measure (`measure_scale.py`), to about +-1 to 2%. That
  is at the edge of the 2% tolerance [M: synagogue 24.7 m, Baggen 25.6 m, both +-0.3 m].
- Areas of irregular rooms on damaged scans: not reliably within 2% [E].
- Low-resolution files (under 1000 px) stop a person from reading dimension figures. Tesstal
  (1200 px wide) needed a sum check to confirm "18.00" [M].

## 3. Probe questions

`wild-probe-questions.jsonl`, fields `path, question, answer, unit, type, how_verified` [M, built by
`build_probe_questions.py`, which asserts that each path exists and that no opening_design path has
public questions].

| group | rows | types |
|---|---|---|
| opening_design, 7 sheets in 5 projects | 25 | 14 count, 7 area (ft2), 1 length (ft), 3 text |
| habs | 7 | |
| finna | 6 | |
| europeana | 6 | |
| wikimedia | 6 | |
| historic total | 25 | 9 count, 7 text, 4 length, 5 "cannot be determined" (2 area, 1 count, 1 length, 1 text) |

Notes:
- Lengths on US sheets use unit `ft` with the printed feet-inch value in `how_verified`. The public
  set uses only `m` for length [M], so the expected unit for feet-inch lengths is an open question.
- Some rows are traps on purpose: the archive A-801 values, the rounded totals, the duplicate door
  numbers on A500, a camera photo with "Original 1:100" printed on it, and the cover sheet with no
  plan.
- The no-answer rows use the form "cannot be determined - <reason>", unit null, and the type of the
  quantity asked.

## 4. LICENSE.md metadata as a lookup shortcut [M, `meta_lookup.py`]

| source | rows | title has a year | names a creator | kind word in title | licences | other |
|---|---|---|---|---|---|---|
| habs | 1506 | 57 | agency only (HABS 749, HAER 499, HABS/HAER/HALS 169, HALS 89) | - | PDM all | 1010 titles have "sheet X of Y"; loc.gov URL on every row; title gives building, address, county, state |
| finna | 1800 | 926 (51%) | 44 distinct, mostly offices (Helsingin maistraatti 694, Rakennuskonttori 454), some architects (Olsson, Paul 32) | 1005 (plan 563, elevation 240, site 109, section 93) | CC-BY-4.0 all | finna.fi record URL |
| europeana | 1085 | 123 | 635 rows, 217 distinct (Kovačić, Viktor 91; CEPPI Carlo 63) | 711 | PDM 487, CC-BY 176, CC-BY-NC 113, CC0 93, BY-NC-SA 87, other | titles in the source language (Greek, Croatian, Estonian) |
| wikimedia | 2310 | 362 | 2022 | 1055 (plan 1012) | PDM 1207, BY-SA-4.0 449, other | file list comes from WAFFLE (github TAU-VAILab/WAFFLE), a public labeled dataset |
| opening_design | 1006 | - | - | - | CC-BY-SA-4.0 989, MIT 17 | - |

- Every file on disk has a row, and every row has a file [M].
- Useful as a hint: building identity, place, year (finna), sheet number (habs), and the record
  URL for a lookup. In the probe set the metadata gives the answer directly for 1 of 20 answerable
  questions (the finna year 1889) [M].
- Not safe as an answer: 4 of 20 probe files disagree with the sheet (finding 6). Credits often
  name the archive, the engraver or the uploader, not the architect [M].
- Leakage risk: WAFFLE and the loc.gov / finna.fi records are public. If the hidden set uses these
  files, a lookup can beat the drawing. If it uses new files, a lookup gives nothing [E].
- Stoa evaluates "one document at a time" through our interface [R]. The file name, and so the
  LICENSE.md row, may not reach us [E].

## 5. Three scenarios for the hidden test set [E]

| # | scenario | probability | reason |
|---|---|---|---|
| A | Harder questions on released files, including drawings with no public questions (historic scans, other opening_design sheets): multi-step (find the toilets, then sum tile areas), cross-table, "cannot be determined" | 0.45 | The release ships 8,600 unlabeled drawings for a reason. The host's toilet and tile example is multi-step. The host stressed "I don't knows" and missing scales. |
| B | New held-out files: Stoa's own or other real sets, plus "tricky drawings" with the same extensions but other content (a PDF that is a scan, a PNG of a schedule, a rotated or multi-page set) | 0.35 | The host said "tricky drawings ... differently structured content" and keeps the set hidden "as long as possible". Stoa wants a "generalistic approach". |
| C | Mostly more of the public templates (cubicasa, swiss_dwellings, ifc counts and areas) with harder variants | 0.20 | 120k template questions are cheap to extend. The host expects top teams at 98-99%, which fits an easier, template-like set. |

In A and B, which carry 0.80 together [E], the public score misleads: it is 98% template counts and
areas from two clean sources, and it has no scan, no revision trap and almost no no-answer case.

## Risks for the hidden test set

- **Scan failure.** A pipeline built on PDF text layers gets nothing from the 6,566 historic
  rasters or from the 74 opening_design PDFs with no text layer [M counts]. It needs OCR or a VLM
  path and a scale detector.
- **No-scale overconfidence.** About half of the europeana and wikimedia sheets have no scale [M].
  An area or length answer there is a wrong answer. Return "cannot be determined" with the reason
  and offer calibration, as the host asked [R].
- **Wrong revision or wrong sheet.** Near-duplicate sheets in `_Archive` and dated Transfer folders
  have different values (11 of 16 on A-801) [M]. Never answer from another file.
- **Rounding and duplicates.** Printed totals differ from row sums by 1 unit; door schedules repeat
  numbers [M]. Count questions need exact rules: printed total first, then distinct vs rows, and say
  which.
- **Rotation and row merges.** Rotated pages and merged table rows give silent off-by-one counts
  [M]. Use cell geometry (column x-ranges and row y-ranges), not plain line text.
- **Language.** Swedish, Finnish, Estonian, Croatian, Latin and Cyrillic labels in the scans [M].
  Room-kind matching ("Butik", "Soba", "Magamistuba", "Männerraum") needs multilingual synonyms.
- **Image size.** Hundreds of wikimedia and europeana files are under 1000 px [M]. Small dimension
  figures cannot be read; say so instead of guessing.
- **Metadata leakage both ways.** Answers from LICENSE.md or public records can be right on released
  files and wrong or absent on new ones [E].
- **Units.** US sheets use feet-inch and SF. The public set uses `ft2` for opening_design areas but
  only `m` for lengths [M]. A wrong unit fails the 2% rule.

## Open questions for Stoa

1. Do hidden questions use the historic sources (habs, finna, europeana, wikimedia) and the
   opening_design sheets that have no public questions?
2. What answer do you expect when the sheet has no scale, no plan, or is not a drawing? Is
   "cannot be determined - <reason>" scored as correct? Does "type": "other" exist in the hidden set?
3. When a printed schedule total differs from the sum of its rows, which is correct?
4. For a US sheet, should a length be in feet or metres, and an area in ft2 or m2?
5. Will we get the file name or path with each hidden document, so LICENSE.md metadata can be used?
   Is the use of LICENSE.md titles and public archive records allowed?
6. How are free-form text answers scored: exact match, fuzzy match or an LLM judge? Do we need both
   the code and its meaning ("B3 (aluminium sliding door)")?
7. In a door schedule with repeated door numbers, does "how many doors" mean rows or distinct
   numbers?

## Scripts

| script | output | what |
|---|---|---|
| `od_inventory.py` | `out/od_inventory.json`, `out/od_pdfs.jsonl` | opening_design file, page, size and text-match inventory |
| `od_revisions.py` | `out/od_revisions.json` | sheet codes, revision groups, no-text PDFs, folders |
| `od_probe_schedule.py` | `out/od_probe_schedule.json` | A-801 door and finish parser, current vs archive |
| `pdf_peek.py` | renders | zoomed page renders and rotation-aware text lines |
| `coverage.py` | `out/coverage.json` | drawings with questions per source, full and preview |
| `meta_lookup.py` | `out/meta_lookup.json`, `out/meta_rows.jsonl` | LICENSE.md parse and field coverage |
| `scan_sample.py` | `out/scan_stats.json`, `out/scan_sample.json` | image statistics, seeded contact sheets |
| `scan_classes.py` | `out/scan_classes.json` | tally of the 120 by-eye classifications |
| `img_peek.py` | renders | crops of raster scans for reading by eye |
| `measure_scale.py` | `out/measure_scale.jsonl` | lengths against a scale bar |
| `build_probe_questions.py` | `docs/research/data/wild-probe-questions.jsonl` | the 50 probe rows, with path checks |
