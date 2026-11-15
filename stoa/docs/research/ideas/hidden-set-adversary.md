# Lens: the hidden set is not like the public set

Date: 2026-11-14. Labels: **[M]** measured by me in this session, **[S]** sourced (file named), **[E]** estimate.
I opened 12 drawings with no public questions and read 100 questions.

## 1. The lens in one paragraph

Stoa built the hidden set to break systems that learned the public generators. The public answers
are generator output [S, lead update], so every public point can be won by a lookup or a narrow parser.
The hidden session is a person who loads one unknown document and asks a series of hard questions [S,
`docs/HOST.md`]. So the score depends on a few general skills on unseen sheets: read any text, find the
scale of each view, read a schedule, count a named symbol, compute from printed dimensions, query a model,
and say what is missing. A system wins when its worst case is a correct "I do not know, I need X". It loses
when its worst case is a confident wrong number. **Strongest argument against:** scenario C in
`data/wild.md` gives 0.20 [E] to a hidden set that is mostly public templates with harder variants. In that
case the source-specific parsers at 99% win, and general machinery at 85% loses.

## 2. What I saw, and the 40 questions I would ask

Facts from the 12 sheets [M by eye] and one script [M]:

- HABS `ky0124_sheet_00002`: rooms carry printed sizes ("COURT OF APPEALS 30'-9" x 44'-0""), door tags in
  circles (A to M), general notes with wall thickness and floor finish per room, two scale bars (feet, metres).
- HABS `nd0014_sheet_00001`: two scales on one sheet (plan 1/4", elevations 3/16"), a materials list.
- finna `hka.144784947553900_168796499079300`: a hand-lettered parts list with quantities (18, 18, 12, 6) and
  "545 m2" in the title. finna `mfa.69c758a7...`: a stair section, "MITTAKAAVA 1/30", level marks.
- europeana `91625_nomu...`: a photo with a centimetre colour chart next to the sheet, and a drawn scale bar.
  europeana `2021633_...`: roof trusses, no text, no scale.
- wikimedia `12126807`: a site map with a Ukrainian colour legend, numbered buildings and a 50 m bar.
- `resbim-109_plan.png`: dimension chains in mm, grid bubbles, no scale bar, a cut-off label ("Bathroo").
- opening_design A100 Demolition Plans: 7 views on one sheet at 1/8" and 3/16", level marks (874'-0").
  CTR Beam Plan: a colour legend of 7 beam types, no scale string. Aalseth Site Plan: areas printed in notes
  ("4597 S.F.", "821 S.F.").
- opening_design text layers: 2,741 pages, 175 with no text. 1,347 pages print a feet-inch scale string. 716 of
  those (53%) print 2 or more different scales. 139 pages say NTS [M, regex on `get_text()`, an undercount].

| # | Source | Question | Skill and trap |
|---|---|---|---|
| 1 | habs | What is the floor area of the Court of Appeals room? | printed 30'-9" x 44'-0", multiply, ft2 |
| 2 | habs | How many square feet of oak flooring for Committee Room No. 1? | note lookup, then area (tile pattern) |
| 3 | habs | How thick are the exterior walls? | general note, 2'-6" |
| 4 | habs | How many door types does the plan tag? | circled letters, distinct vs instances |
| 5 | habs | How many windows on the east elevation of the Bakery Shop? | view selection on a multi-view sheet |
| 6 | habs | What is the height from floor to top of roof? | sum 9'-4" and 5'-8" |
| 7 | habs | What scale is the floor plan drawn at? | two scales on the sheet |
| 8 | habs | What is the roof made of? | materials list |
| 9 | habs | How many sheets are in this set? | title block "sheet 2 of 23" |
| 10 | finna | Montako porrasarinarautaa tarvitaan? | handwritten parts list, Finnish, ditto marks |
| 11 | finna | What scale is the stair section? | "MITTAKAAVA 1/30" |
| 12 | finna | What is the floor area of the stadium? | no plan on the sheet: unknown, reason |
| 13 | finna | Who signed the drawing, and when? | handwriting, stamp |
| 14 | finna | Hur många våningar har byggnaden? | Swedish, count on a section |
| 15 | europeana | How long is the balustrade front? | 2.430 + 2.430 printed, metres |
| 16 | europeana | What is the span of the truss? | no scale, no dimension: ask to calibrate |
| 17 | europeana | Is this a building drawing? | a watercolour or poster: say no |
| 18 | wikimedia | How many buildings are from the Roman period? | colour legend in Ukrainian, count by fill |
| 19 | wikimedia | How long is building 10? | scale bar, rotated object |
| 20 | wikimedia | How many storeys does the sheet show? | several plans photographed on one sheet |
| 21 | resbim png | What is the area of the Kitchen in m2? | no scale bar: calibrate on dimension chains |
| 22 | resbim png | What is the overall building width? | printed 7280 mm |
| 23 | resbim ifc | How many rooms does the model have? | no IfcSpace: derive from walls, or say so |
| 24 | resbim png | How many doors? | arcs on a raster, no legend |
| 25 | opening_design | How many 24IT40 beams on the beam plan? | colour legend, vector fill count |
| 26 | opening_design | What area of new impervious surface is added? | note "821 S.F.", net change is 0 |
| 27 | opening_design | What is the 2nd floor to 1st floor height? | level marks 883'-2 1/2" minus 874'-0" |
| 28 | opening_design | How many doors in the schedule are fire rated 90 min? | another schedule, another column |
| 29 | opening_design | How many doors? (archive A-801) | revision trap, 41 not 38 [S, wild.md] |
| 30 | opening_design | Total wall area in the wall schedule? | printed total vs row sum |
| 31 | opening_design | How many lavatories does the restroom plan need tiles behind, and what wall length? | compound, enlarged plan scale |
| 32 | opening_design | What is the occupant load? (scanned sketch) | PDF with no text layer |
| 33 | opening_design | What is the room height of room 118? | answer is on another sheet: unknown, name the sheet type |
| 34 | swiss png | How many m2 of tiles for all rooms labelled Bad and WC? | raster only, two steps, scale 1:100 at A3 |
| 35 | swiss pdf | Which apartment is the largest, and by how much? | compare, text answer |
| 36 | cubicasa | What is the area of the largest bedroom? | no scale on the plan: unknown, or printed m2 if any |
| 37 | cubicasa | Montako huonetta, joissa on ikkuna? | relation between symbols and rooms |
| 38 | ifc sheet | How many m2 of floor finish on levels 1 and 2 together? | sheet shows one level: needs the model |
| 39 | ifc | Which rooms have no door? | relation query, model conventions |
| 40 | ifc | What is the wall volume in cubic feet? | unit conversion, Qto absent |

## 3. Concepts

### C1. Sheet compiler and a small query language
**Pitch:** compile each document once into a typed evidence graph, and answer every question with a short
deterministic program over it.
**Mechanism:** Per document: a format adapter (vector PDF, DXF, IFC plan cut, raster) emits one schema:
`View` (title, kind, bbox, scale), `Text` (string, bbox, rotation, language), `Dim` (value, unit, end points),
`Table` (cells), `Legend` (swatch or symbol, meaning), `Region` (polygon, label), `Mark` (symbol instance,
cluster id), `Note`. A raster gets one tiled VLM pass for text, views and tables, plus classic CV for lines
and regions. Per question: one small-model call maps the question to 3 to 8 operators (`find`, `filter`,
`count`, `sum`, `area`, `convert`, `require`). The program runs with no model. A count is `len(marks)`.
**Needs:** no training. One VLM call per raster document.
**Criteria:** accuracy high where structure exists (81% with layout JSON vs 31% with the image [S, lead
update]); evidence is native, each operator returns ids with boxes; creativity medium; cost low.
**Hidden set:** degrades by adapter, not by template. A new template is a new program over the same
operators. A new language touches only `find`.
**Cost per question:** about $0.002 text-only planning; about $0.03 per raster compile [E].
**Evidence view:** the program as steps, and each step's objects lit on the sheet.
**33 hours:** schema, vector PDF and IFC adapters, 8 operators: yes. A full raster adapter: partly.
**Kill test:** hand-write the graph for 5 unseen sheets and check that the 40 questions are expressible.
Under 30 of 40 kills it.
**Risk:** the schema grows to fit every sheet, and the adapters stay shallow.

### C2. Scale ledger with independent witnesses
**Pitch:** every view gets a scale from up to four independent sources, and agreement sets the confidence.
**Mechanism:** Per view: (a) the ratio string ("1:100 (A3)", "1/4" = 1'-0"", "MITTAKAAVA 1/30") with the
paper size; (b) the scale bar length in pixels; (c) a regression of printed dimension values against the
pixel length of their dimension lines; (d) priors (door leaf width, the centimetre ruler of a colour chart).
Two witnesses within 2%: high confidence. One: medium. None: a typed unknown that opens two-click
calibration. Each measured answer cites its witness.
**Criteria:** accuracy for every area and length; evidence strong (the bar and the fitted chains are
drawn); creativity medium; cost zero per question.
**Hidden set:** this is the skill the public set never tests on rasters. Witness (c) works on ResBIM, which
has no bar [M by eye]. Multi-scale sheets are the norm in opening_design (53% [M]).
**Cost:** none per question. **33 hours:** (a) and (c) on vector text and on ResBIM PNG: yes. Faded bars: no.
**Kill test:** on 20 ResBIM PNGs, does the chain regression give one scale with under 1% residual?
**Risk:** a ratio string is true only at the original paper size, and a scan loses that.

### C3. Evidence ladder: read before you measure
**Pitch:** prefer a printed value to a computed one, and a value computed from printed dimensions to one
measured from pixels.
**Mechanism:** Four rungs with fixed order: R1 printed answer (schedule cell, note "821 S.F."); R2 arithmetic
on printed values (30'-9" x 44'-0"); R3 geometry with a ledger scale; R4 unknown with a request. The planner
must try the rungs in order and report the rung. The core is an exact feet-inch and metric parser. Confidence follows the rung, not a model's self-report.
**Criteria:** accuracy up on real sheets, because VLM area estimates miss by about 43% [S, lead update];
evidence clear ("R2: two printed dimensions"); cost none.
**Hidden set:** the tile example is R1 or R2 on a real sheet and R3 on a synthetic one. One ladder covers both.
**33 hours:** yes, all of it. **Kill test:** on 30 unlabeled sheets, how often does a room carry a printed
size or area? Under 20% makes R2 minor.
**Risk:** a printed room size is nominal and can differ from the net area the reference uses.

### C4. Schedule engine with stated counting rules
**Pitch:** treat every table, list and legend as a database table built from cell geometry, and answer with a
filter that a person can read.
**Mechanism:** Per document: map words through `page.rotation_matrix`, find ruling lines, build cells from
column x-ranges and row y-ranges, join header rows, and type each column (code, size, area, count). Legends
and key notes become lookup tables that join on codes. Per question: a filter and an aggregate. Fixed rules,
printed with the answer: printed total first; rows vs distinct numbers stated; only the given file is read.
**Needs:** for scans, the VLM pass emits cells and a second pass checks row counts.
**Criteria:** accuracy high on US sets; evidence is a highlighted row set; cost near zero.
**Hidden set:** 25 door, 8 window and 60 finish schedules exist with 3 questioned [S, wild.md].
**33 hours:** yes for vector. Handwritten lists (finna): VLM only.
**Kill test:** run on 10 schedules without questions and compare row counts by eye. Under 9 of 10 exact
needs a redesign. **Risk:** merged cells and silent row merges [S, wild.md finding 7].

### C5. Cluster first, name later (unusual)
**Pitch:** count a symbol by finding every repeated shape on the sheet without a model, and use the model
only to name each cluster once.
**Mechanism:** Per document, vector: hash each drawing group by a normalised path signature (segment
counts, length ratios, fill colour), up to rotation and mirror. Equal hashes form a cluster. Raster: take
connected components in a size band, describe each with a small shape descriptor, and cluster. The legend
gives exemplars when it exists. One VLM call sees one crop per cluster and names it ("toilet", "24IT40
beam"). Per question: pick the clusters by name, and the count is the number of members inside the asked view.
**Needs:** no training, no labels. One VLM call per document.
**Criteria:** accuracy: exact where symbols are CAD blocks; evidence: every member has a box, and the
person sees the exemplar; creativity high; cost about $0.01 per document [E].
**Why it can win:** VLMs count doors and windows exactly on 16% to 39% of plans, and fine-tuned counters
collapse out of distribution [S, lead update]. This has no learned detector to collapse.
**Hidden set:** style-free on vector sheets. Weak on hand drawings, where no two symbols are equal.
**33 hours:** vector version yes. Raster version: a test only.
**Kill test:** on 10 swiss PDFs, do toilets and washbasins form clean clusters that equal the answer key?
**Risk:** a symbol drawn as loose lines, not as a block, never forms a group.

### C6. Typed unknowns with a request
**Pitch:** every operator declares what it needs, and a missing need becomes a specific question to the person.
**Mechanism:** `area` requires a scale and a closed region. `count` requires a view of the right kind.
A model-wide question requires a model. Before running, the program checks its requirements against the
graph. A failure returns `{unknown, missing: "scale", request: "click two points of a known length"}` and a
best-effort bound when one exists ("at least 3 visible"). A sheet classifier (plan, elevation, schedule, not a drawing) feeds the checks.
**Needs:** about 20 no-answer test rows (5 exist in `wild-probe-questions.jsonl` [S]).
**Criteria:** the host called this "super important" [S, HOST.md]; cost none.
**Hidden set:** this is where a tuned system fails worst. 28/30 habs but 15/30 europeana sheets have a scale [S, wild.md].
**33 hours:** yes. **Kill test:** on the 40 questions above, does it abstain on the 6 unknowns and on none
of the others? **Risk:** abstaining too often reads as weakness, and no scoring rule is known.

### C7. Metamorphic red team (unusual)
**Pitch:** make our own hidden set by damaging the solved public sheets, where the truth stays known.
**Mechanism:** Take swiss and ifc_models PDFs with exact answers. Apply transforms that keep the answer:
rasterise at 100 to 200 dpi, drop the text layer, rotate 90 degrees or 3 degrees, add scan noise, crop the
legend or the scale bar, re-letter labels in another language, redraw the scale as feet. Each transform has a known effect: same answer, converted answer, or "now unknown". The harness reports accuracy per transform.
At inference, the same idea gives a free check: answer on two renders, and disagreement lowers confidence.
**Needs:** a day of one person. **Criteria:** it measures the other concepts; creativity high in the pitch.
**Why it can win:** it is the only way to get thousands of labelled "tricky" rows in 33 hours, and it turns
the worthless public score into a robustness curve that judges can read.
**Hidden set:** it predicts the drop from vector to scan. It says nothing about real hand drawings.
**33 hours:** 5 transforms: yes. **Kill test:** if the vector parser scores 99% and its raster path
scores under 30% on the same sheets, the raster adapter is the whole project. **Risk:** synthetic damage is
kinder than a 1926 pencil sheet.

### C8. The operator as a sensor (unusual)
**Pitch:** let the person fix one mark or set one scale in two clicks, and recompute the answer
deterministically.
**Mechanism:** Every answer is a set of marks, regions and a scale. The UI lets the person remove or add a
mark, drag a region corner, or click two points and type a length. The program runs again with no model
call.
**Needs:** UI work only. **Criteria:** verification very high; accuracy in a live session rises, because Stoa's
people run it through our interface [S, HOST.md]; cost zero.
**Why it can win:** the host asked for "give us a scale or calibrate".
**Hidden set:** it is the only concept that works on any drawing at all. **33 hours:** calibration yes,
mark editing if C1 marks exist. **Kill test:** ask Stoa on Saturday whether a corrected answer counts.
**Risk:** judges score the first answer only.

## 4. The system I would build from this lens

```
document ──> adapter (pdf-vector | dxf | ifc | raster) ──> evidence graph (C1)
                 │  raster: 1 tiled VLM read + CV                 │
                 └──> scale ledger per view (C2), tables (C4), clusters (C5)
question ──> planner (small model, text only, sees the graph summary)
         ──> program: require… find… filter… ladder R1>R2>R3 (C3) … aggregate
         ──> executor (no model) ──> record {value, unit, rung, witnesses,
                                             marks, confidence, unknowns+request (C6)}
         ──> view: steps, lit objects, calibrate and fix (C8)
harness: public rows + metamorphic variants (C7) + 50 probe rows + the 40 above
```

Order of work, hours [E]: (1) record format and harness with C7 transforms, 4. (2) Vector PDF adapter with
rotation, unit parser and ladder, 6. (3) Schedule engine, 4. (4) Scale ledger with ratio string and chain
regression, 4. (5) IFC adapter: the existing probe plus a plan cut that feeds the same region code, 3.
(6) Raster adapter with one VLM read, 6. (7) Typed unknowns and calibration in the UI, 4. (8) Clustering for
vector sheets, 4.
Cut first: raster clustering, then DXF and DWG adapters (convert to PDF), then handwritten tables, then
mark editing. Never cut: the unit parser, the scale ledger and typed unknowns.

Public-set work that is wasted under this lens: a template classifier, per-template priors, a counter
trained on CubiCasa5K, the `model.svg` lookup, sibling-format lookups by file name, LICENSE.md metadata,
and the emulation of generator conventions such as "a shared door counts once per apartment". Work that
still pays: the rotation-aware vector parser, the IfcOpenShell probe, room polygons from vector fills, scale
bar reading, multilingual room synonyms, and the public answers as the truth under C7 transforms.

## 5. Where this lens is wrong

- If the hidden set is public templates on new plans of the same sources, generator-matched parsers win,
  and our general door count loses to a convention we refused to copy. Keep the cheap source parsers as a first tier, and name the rule in the record.
- If hidden cubicasa-style rasters dominate, a learned symbol detector beats clustering and a VLM.
- If Stoa scores free text with an LLM judge, a frontier agent per question can beat a strict executor on
  ifc_bench-style questions. The best published agent scores about 56% [S, lead update].
- If abstentions score as wrong, a guess beats an honest unknown. Then always give a best estimate next to the unknown.
- On historic scans the ladder mostly ends at R1 or R4. A VLM that reads the sheet directly is as good there.

## 6. Ten things to measure first

1. Ask Stoa at midday: are abstentions scored, are unlabeled sources used, does a corrected answer count?
   Settles C6 and C8 weight.
2. Vector parser on rasterised swiss sheets (C7, 50 sheets). Settles how much effort the raster adapter gets.
3. Chain-regression scale on 20 ResBIM PNGs. Settles whether C2 witness (c) ships.
4. Expressibility of the 40 questions in 8 operators. Settles the schema of C1.
5. Schedule row counts on 10 unquestioned schedules. Settles C4 as built or redesigned.
6. Share of rooms with a printed size or area on 30 unlabeled sheets. Settles the weight of R2.
7. Cluster purity for toilets and washbasins on 10 swiss PDFs against the key. Settles C5.
8. One VLM read of 10 historic scans: text recall against my eye, and cost per sheet. Settles the model
   tier and the 10-cent budget.
9. Planner accuracy with a small model on the 40 questions in 5 languages. Settles the planner model.
10. False-abstention rate on 100 answerable public rows. Settles the confidence thresholds.
