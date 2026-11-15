# swiss_dwellings: what the files hold, where the answers come from, and how the public score can mislead

Source: `stoa/data/junction-dataset/data/swiss_dwellings/` (1,040 floors, each as PDF, DXF and PNG; 37,584 questions).
Scripts: `stoa/analysis/swiss/*.py` (PEP 723, run with `uv run <script>.py`). Outputs go to
`stoa/data/external/swiss-derived/` (git-ignored, because they hold dataset content).
Every figure below is marked MEASURED (a script printed it), READ (a source file states it) or ESTIMATE.

## Findings that change decisions

1. **The answers are a lookup in public data.** MEASURED: all 1,040 floors exist in the public Swiss Dwellings
   v3.0.0 `geometries.csv` (Zenodo 7788422, CC BY 4.0) under the same site, building and floor ids. The ids are
   in the file name and printed in the title block ("Site 3387 · Gebäude 5238", "Plan-Nr. 5238-23498"). A lookup
   in the public CSV, with no drawing opened, reproduces 100% of the toilet, washbasin, bathtub, shower, door,
   window and apartment counts, and 99.5% of the floor totals (`probe_source.py`, `duplicates.py`). Any score
   on this source can be leakage. Our eval must ban the public CSV and any model trained on it.

2. **A deterministic PDF-only parser already answers 99.6% of the public questions, at zero model cost.**
   MEASURED: `probe_pdf.py` (about 300 lines, pymupdf and shapely, no DXF, no LLM) agrees with 37,444 of 37,584
   reference answers (99.63%) on all 1,040 floors, in 13 s total. The DXF probe gets 99.4% (best variant).
   So the public swiss questions do not separate good from bad solvers. They test that the parser exists.
   The hidden set decides the score, and it will not be these clean, generated sheets.

3. **Door counts follow a database convention that no person can see.** MEASURED: the reference door count
   equals the raw number of source rows on 1,040 of 1,040 floors. A door that two units list (apartment and
   stair hall) counts twice, and the generator draws the two copies exactly on top of each other. A count of
   the distinct doors on the sheet matches the reference on only 74 of 1,040 floors (7.1%). The reference
   total is 31,928 doors; the sheet shows 27,025 distinct doors (+18%). Windows: 765 of 1,040 floors (73.6%)
   match by distinct count. A vector parser that counts stacked copies gets 100%. A raster or vision solver,
   or a person, gets about 7% on doors. A simple visible rule (count a door twice when it crosses an apartment
   outline) gets only 14% (`door_rule.py`). This is the clearest case of "the answer follows the generator,
   not the drawing". Ask Stoa which convention the hidden set uses.

4. **Area questions need geometry on 70% of sheets; on the other 30% they are a text lookup.** MEASURED: 307
   of 1,040 sheets (29.5%) print "12.34 m²" under the room number. On those sheets the printed value answers
   99.35% of room-area questions exactly (`probe_printed.py`). Summing printed values for the floor total
   works only 77.9% of the time, because small rooms carry no printed area. On the other 733 sheets the area
   needs the scale and the room polygon. The scale is always printed ("1:100 (A3)" on 863 sheets, "1:200 (A3)"
   on 177) and the scale bar agrees exactly (28.346 pt per m at 1:100). Room polygons in the PDF reproduce the
   reference to the cm² once holes (a lift shaft inside a stair hall) are subtracted. From the PNG alone, a
   flood-fill area is within 2% for only 20.8% of rooms (23.0% at 1:100, 10.8% at 1:200; `probe_png.py`, 400
   questions). So a raster-first solver must use the vector file when it exists.

5. **The public set has no near copies, but the hidden set can.** MEASURED: the 1,040 floors come from 1,040
   different sites (one floor per site, `structure.py`). So the public set is already site-disjoint. But the
   public source has 13,905 floors on 1,466 sites. 978 of our floors have sibling floors in the same building
   (3,530 unused sibling floors), and 4,047 floors sit on sites we never see. A sibling floor has the identical
   door count 43% of the time (1.9% for a random floor of another building), and identical counts on all seven
   count families 37.9% of the time (`source_siblings.py`). If the hidden set reuses this generator on other
   floors, a model that memorised public answers looks good. A fair split groups by `site_id`.

6. **Question presence leaks the answer.** MEASURED: bathtub questions appear only on the 897 floors with at
   least 1 bathtub, shower questions only on the 322 floors with at least 1 shower. "Rooms labelled X" is asked
   only for labels that are on the sheet (answer 0 never occurs in 6,365 English questions). The public set
   never tests "there is none" or "I do not know". The hidden set can.

7. **Labels are exact strings, and the language is synthetic.** READ (`LICENSE.md`): room names are "in an
   assigned language (de, fr or it)", and the sheet says "label language and numbering are synthetic".
   MEASURED: each floor has English plus exactly one local language (de 698, fr 247, it 95 floors); the
   English question quotes the local label verbatim ('Schlafzimmer'), so no translation is needed. Label to
   source class is close to 1:1 (Zimmer = ROOM, Schlafzimmer = BEDROOM, Raum = NOT_DEFINED). The English and
   local twin questions never disagree (0 of 18,792 pairs).

8. **Conventions that matter (all MEASURED by agreement):** room area = polygon area minus inner polygons
   (holes); floor total = all numbered rooms minus outdoor rooms (Balkon, Loggia, Terrasse, Wintergarten) and
   minus unnumbered shafts and voids; outdoor rooms are filled grey 0.89 on the sheet, and 246 of them carry no
   name; apartment area = rooms inside the red dash-dot outline minus outdoor rooms, shafts excluded;
   apartments = number of "Whg. X" / "App. X" tags (unit outline polygons give only 88%, because a unit can be
   split in several polygons); a washbasin is an ellipse with a drain dot, a WC an ellipse with a tank line.

## Evidence

### 1. What each format holds

Script: `inspect_formats.py`, `dxf_dump.py`, `probe_pdf.py` (feature part).

**PDF** (MEASURED on all 1,040): one page, vector only, no images, no layers (no OCGs). Producer "Matplotlib pdf
backend v3.11.2". A3: 821 landscape (1191 x 842 pt), 219 portrait. Embedded text (DejaVuSans):
- each room: label (for example "Schlafzimmer") centred exactly above the room number ("7.08"); 1,451 of 28,829
  numbered rooms have no label (small rooms);
- apartment tags "Whg. A" (German) or "App. A" (French, Italian) in a box;
- printed net areas "12.34 m²" under the number on 307 sheets (29.5%), with "Flächen: Nettoflächen in m²" in the
  title block;
- title block: project "Site N · Gebäude M", plan name ("Grundriss 7. OG"), scale "1:100 (A3)" or "1:200 (A3)",
  plan number "<building>-<floor>", "Masse in Metern", and a source credit;
- a legend with the fixture symbols, a scale bar (0, 1, 2, 5 m or 0, 2, 4, 10 m) and a north arrow.
- No dimension lines and no dimension text on any sheet I opened.
Paths are typed by style: room fills with a grey (0.54) 0.37 pt stroke (white = in an apartment, 0.95 grey = not
in an apartment, 0.89 grey = outdoor), red (0.69, 0.23, 0.18) dash-dot apartment outlines, grey (0.27) quads for
door openings, white boxes with a black 0.51 pt stroke for fixtures and windows, hatched grey walls.

**DXF** (MEASURED on all 1,040): AutoCAD 2013 (AC1027), `$INSUNITS` = 6 (metres) on all files, real-world
coordinates in metres. Layers: `WALL`, `DOOR`, `WINDOW`, `ROOM_OUTLINE`, `ROOM_TEXT`, `FIXTURE`, `ANNOTATION`,
`UNIT_OUTLINE` (1,031 files have all eight). No blocks for fixtures (only dimension arrow blocks), no XDATA.
Door = 5-point polyline (opening) + 2-point leaf + ARC; window = closed rectangle + 2 lines; fixture = outer
rectangle + inner shape (48-point ellipse for WC and basin, 69-point rounded rectangle for a bathtub, 5-point
quad for a shower, four r = 0.08 m circles for a hob). Room polygons and labels sit on their own layers.

**PNG** (MEASURED): 2480 x 1753 (or 1753 x 2480), RGBA, 150 dpi, rendered by Matplotlib from the same figure.
1 px = 1.69 cm at 1:100 and 3.39 cm at 1:200.

**What I saw on 12 sheets** (site3387 floor23498, site1022 floor9481, site392 floor4117, site1015 floor9557,
site1102 floor10281, site956 floor8887, site604 floor5779, site144 floor441, site2141 floor13608, site320
floor2759, site491 floor5181, site272 floor1961): clean CAD-style plans on a white A3 sheet with a frame and a
title block in the local language. Hatched walls, white rooms, grey balconies, red dash-dot apartment borders,
door swings, window bands, sanitary symbols. Text never rotates. Big floors at 1:200 (site1015, 15 apartments;
site491, 8 apartments) have room numbers up to "1.116" and labels that overlap fixture symbols or walls ("Bain
3.19 1.67 m²" over a WC). Small rooms show only a number ("5.06", "2.48"). Some public floors draw many rooms
in light grey outside any apartment (site144: 39 rooms, 1 apartment outline). Some "Bad"/"Bain" rooms hold no
fixture (site320 room 0.01). Nothing looks like a scan: no noise, no skew, no handwriting.

**Leakage map** (MEASURED, `source_subset.py`): file `site{S}_bldg{B}_floor{F}` = `site_id` S, `building_id` B,
`floor_id` F in `geometries.csv` (3,255,905 rows). All 1,040 floors found, site and building ids match. Public
labels per floor: area polygons with `entity_subtype` (ROOM, BEDROOM, BATHROOM, BALCONY, SHAFT and 50 more),
openings (DOOR, ENTRANCE_DOOR, WINDOW), features (TOILET, SINK, BATHTUB, SHOWER, KITCHEN, STAIRS, ELEVATOR,
WASHING_MACHINE), `unit_id` and `unit_usage` (RESIDENTIAL, PUBLIC, COMMERCIAL), walls and railings as polygons.
`simulations.csv` (view, light, noise) and `locations.csv` (no coordinates) also exist; I did not use them.
Download: 932 MB zip, 1.1 GB `geometries.csv` extracted, in `stoa/data/external/swiss-dwellings-v3/`.
Licence: CC BY 4.0 (READ from the Zenodo record). The "Modified Swiss Dwellings" set on 4TU was not checked.

### 2. Templates

Script: `templates.py`, `qparse.py`. MEASURED: 37,584 rows, 1,040 floors, 36.1 questions per floor; 25,568 count
and 12,016 area. 12 template families, each in English plus the floor's local language. Literal strings: 102,
because apartment letters (A to O) and room prefixes (U1., U2.) are part of the text.

| family | example (en) | en rows | answer note (MEASURED) |
|---|---|---|---|
| count_label | How many rooms labelled 'X' are there on this floor? | 6,365 | never 0 |
| apartments | How many apartments (residential units) are shown...? | 1,040 | 1 to 16, mode 2 (28%) |
| doors | How many doors (interior doors and entrance doors together)...? | 1,040 | counts stacked copies |
| windows | How many windows are drawn...? | 1,040 | counts stacked copies |
| toilets / washbasins | How many toilets (WC) / washbasins are drawn...? | 1,040 each | 0 occurs |
| bathtubs / showers | How many bathtubs / showers are drawn...? | 897 / 322 | asked only when at least 1 |
| area_room | What is the net floor area of room 7.01 ('Balkon') in m²? | 2,076 | 2 per floor |
| area_label | What is the total net area in m² of all rooms labelled 'X'? | 1,017 | |
| area_total | ...total net floor area of all numbered indoor rooms (excluding balconies, ..., shafts and voids)? | 1,040 | |
| area_apartment | What is the net floor area of apartment A in m²...? | 1,875 | letters A to O |

Rows by language: en 18,792, de 12,620, fr 4,461, it 1,711. The language of a floor is assigned by the generator
(READ, LICENSE.md); it is constant per floor and the title block, legend and labels follow it. Labels asked in
count questions (34 distinct labels, MEASURED, `templates.py` output `labels_count.txt`): Küche 1,318, Korridor 1,238,
Bad 1,210, Zimmer 1,044, Balkon 920, Treppenhaus 882, Wohnen/Essen 702, Reduit 422, Wohnen 362, Schlafzimmer 350,
Cuisine, Couloir, Bain, Cucina, Pièce, Loggia, Corridoio, Bagno, Balcon, Stanza, Cage d'escalier, Séjour/repas,
Vano scala, Balcone, Soggiorno/pranzo, Chambre à coucher, Séjour, Réduit, Soggiorno, Ripostiglio, Camera da
letto, Küche/Essen, Kellerabteil, Vano cantina. French questions wrap the label in narrow no-break spaces
(« Cuisine »); strip them before matching. Per-template mode baseline (English): 19.6% (MEASURED), far below
cubicasa's 55%.

### 3. Label origin: agreement of small probes with the reference

| family | DXF probe | PDF-only probe | public-source lookup |
|---|---|---|---|
| count_label | 100% | 100% | (needs synthetic numbering) |
| apartments | 100% (tags) / 88.4% (outline polygons) | 100% | 100% (residential units) |
| doors | 100% (5-point polylines incl. stacked) / 13.9% (unique arcs) | 100% (stacked quads) | 100% raw rows / 7.1% distinct |
| windows | 100% | 99.2% | 100% raw rows / 73.6% distinct |
| toilets | 99.8% | 99.9% | 100% |
| washbasins | 99.2% | 98.8% | 100% |
| bathtubs | 99.7% | 99.7% | 100% |
| showers | 100% | 100% | 100% |
| area_room | 100% | 99.7% | - |
| area_label | 100% | 99.8% | - |
| area_total | 96.8% | 98.6% | 99.5% |
| area_apartment | 96.4% | 98.8% | not tested |
| **all 37,584** | **98.75% (99.39% best variants)** | **99.63%** | |

Scripts: `probe_dxf.py`, `probe_pdf.py`, `probe_source.py`, `duplicates.py`. All on the full 1,040 floors
(more than the 200 asked). Agreement rule: counts exact, areas within 2%.

Five disagreements of the PDF probe (MEASURED, `probe_pdf.json`; every miss occurs in both languages):
- site765 floor7457, room 5.10 'Séjour/repas': ref 47.95, PDF 41.45. The probe picks the wrong polygon where
  rooms overlap; the same floor misses its total (552.44 against 538.17).
- site2152 floor13692, room 5.01 'Bad': ref 9.47, PDF 8.68; floor total 98.24 against 65.42 (the probe drops
  rooms it cannot assign).
- site1684 floor13085, floor total: ref 700.17, PDF 623.21.
- site10346 floor39285, apartment A: ref 81.87, PDF 94.46 (a room inside the red outline that the reference
  gives to another unit, or an outdoor room without a label).
- site778 floor7553, washbasins: ref 3, PDF 6 (double basins or kitchen sinks drawn with the basin symbol).
Five disagreements of the DXF main variant (MEASURED, `probe_dxf.json`): the misses sit in the same places.
Apartments from unit outline polygons fail on 121 floors, because one unit can be several polygons (tags give
100%). Washbasins with a "small drain" rule give 85.3%; any drain circle gives 99.2%. Floor totals that count
all numbered rooms give 23.1%; minus outdoor rooms 96.8%; minus outdoor rooms and lift and stair 35.5%. So lift and
stair are inside the total.
Earlier probe versions failed in ways a real solver will meet: a portrait sheet moves the title block (cut-off
by fixed y lost half the plan); a stair hall with a lift shaft is an outer ring plus a separate inner polygon;
windows on rotated walls need a rotation-aware test; room numbers like "U1.04" need their own pattern.

Conventions (MEASURED by which variant agrees): see finding 8. The source door rows include each shared
opening once per unit (MEASURED on `source_rows.csv`, grouped by floor, subtype and exact geometry):
- entrance doors: 912 listed once, 2,827 twice, 340 three times, 13 four or five times;
- interior doors: 21,609 once, 1,293 twice, 31 three times.
That is 4,903 extra rows, the full gap between the reference (31,928) and the distinct doors (27,025)
(`duplicates.py`). Windows: 787 extra rows on 275 floors.

Printed area text (MEASURED, `probe_printed.py`): on the 307 sheets with printed areas, 8,084 of 8,760 numbered
rooms (92%) have a printed value. Room-area questions: 1,216 of 1,224 exact. Label totals: 598 of 604 within 2%.
Floor totals from printed text only: 478 of 614 (77.9%).

### 4. PDF only and PNG only

PDF only: no loss. The PDF holds every entity of the DXF with style-typed paths, the text and the scale
(finding 2). Scale is recoverable from the title text and from the scale bar; both agree on all sheets.

PNG only: see the raster probe below. Counts that depend on stacked copies (doors, 26% of window answers) cannot
be read from pixels at all (finding 3). ESTIMATE: the other counts (fixtures, labels, apartments) need OCR of
5 to 15 px text and symbol detection; feasible but not measured here. At 1:200, a 0.5 px boundary error on a
3 x 3 m room is about 1.7 cm x 12 m = 0.2 m², 2.3% of 9 m² (ESTIMATE): beyond the 2% tolerance for small rooms.

Raster area probe (MEASURED, `probe_png.py`, 200 floors, seed 7, 400 English room-area questions). It simulates
a PNG solver with perfect OCR: the PDF gives only the room-number position and the text boxes to erase. The
area comes from a flood fill of light pixels under the number, holes (fixtures) filled, converted with the
printed scale.

| variant | within 2% | median abs. error |
|---|---|---|
| threshold 200 | 4.0% | 9.9% |
| threshold 200 + 1 px dilation | 20.8% | 6.6% |
| threshold 240 | 2.3% | 12.8% |
| threshold 240 + 1 px dilation | 15.3% | 8.6% |

Best variant by scale: 1:100 23.0% (75 of 326), 1:200 10.8% (8 of 74). Errors are almost all too small
(for example site388 floor3969 room 0.08: ref 7.03, PNG 6.21; site1750 floor49811 room 4.03: ref 11.53, PNG 6.82,
where a door swing or a fixture line cuts the room). The 2% tolerance is about 1 px of boundary at 1:100 on a
small room. A naive raster solver loses most area questions on the 70% of sheets without printed areas.
ESTIMATE: a calibrated wall-offset model would do better, but I did not measure it. A raster solver should read
the printed "m²" text where it exists and treat the rest as low-confidence.

### 5. Split structure

MEASURED (`structure.py`, `source_siblings.py`): 1,040 floors, 1,040 buildings, 1,040 sites in the public set:
one floor per site. No near-copy leakage inside the public set; a random floor split is already site-disjoint.
In the public source, sibling floors are near copies (finding 5). The grouping key for any split that adds
floors from the source, or for synthetic data from the same generator, is `site_id` (buildings of one site share
a design).

### 6. Label noise

- English vs local twins: 0 contradictions in 18,792 pairs (MEASURED).
- By geometry: the DXF and PDF probes reproduce 99.4% and 99.6% of all answers; the source lookup reproduces 100%
  of fixture, door, window and apartment counts. I found no answer that contradicts the generator's own data.
- By eye (12 sheets, about 30 answers on floor23498, floor4117, floor10281, floor1961): fixture counts, room
  counts and printed areas match what I see. The doors do not: floor23498 has 18 distinct door openings,
  and the reference says 20 (2 doors are listed by two units).
- Real noise is against the drawing, not inside the data: door counts (93% of floors), window counts (26%),
  rooms labelled "Bad" that hold no fixture, and 1,451 numbered rooms (5%) without a name on the sheet, of which
  246 are balconies that count as outdoor only through their fill colour.

### 7. Generator artifacts a solver can exploit, and a real drawing does not have

- Site, building and floor ids in the file name and title block: a key into the public CSV (finding 1).
- Semantic DXF layers (`DOOR`, `WINDOW`, `FIXTURE`, `ROOM_OUTLINE`, `UNIT_OUTLINE`) and metres as units.
- PDF paths typed by exact colour and stroke width; fixtures drawn with fixed vertex counts (47-segment
  ellipse, 68-segment tub).
- Room label always centred exactly above the room number (same x to 0.01 pt); room number = floor index + "."
  + sequence ("7.03" on floor 7).
- Shared doors and windows stacked as exact duplicates: countable in vectors, invisible on paper.
- Printed areas on 30% of sheets, equal to the answer to 0.01 m².
- Question presence implies count at least 1 (bathtubs, showers, labels).
- One fixed legend, one font, A3 at 1:100 or 1:200, no rotation of text, no scan noise.

## Risks for the hidden test set

- A solver tuned to these sheets (colour codes, vertex counts, layer names) will break on real drawings with
  blocks, other layer names, raster scans and other symbols. ESTIMATE: most of the 99.6% comes from such
  artifacts.
- If the hidden set uses this generator on the 12,865 unused source floors, our parser works, and leakage from
  the public CSV is total. If it uses real drawings, nothing here transfers except the conventions.
- Door and window answers depend on a convention that a person cannot see. A vision or VLM solver loses about
  93% of door questions if the hidden set keeps it; a vector solver loses them if the hidden set counts what is
  visible.
- "Rooms labelled X" with X absent, "how many showers" with none, and questions whose answer is not on the sheet
  never appear in public; our abstention and zero handling are untested.
- 1:200 sheets and printed-area sheets behave differently; per-scale and per-printed-area reports are needed.
- A high public score on this source says nothing about raster (habs, finna, europeana, wikimedia) sources.

## Open questions for Stoa

1. Door and window counts: should a door shared by two units count once (what a person sees) or once per unit
   (what the reference does)? Does the hidden set keep this convention?
2. Will the hidden set include more swiss_dwellings floors from the same generator (other floors of the same
   buildings, other sites)? Are the site ids and title blocks kept?
3. Is using the public Swiss Dwellings dataset allowed (for synthetic training data, for conventions), or does it
   count as leakage?
4. Will hidden questions give a drawing without a scale, or a PNG without the vector siblings?
5. Is "net floor area" meant as in SIA 416, or as the room polygon area in the source? The reference uses the
   polygon area. Is the 2% tolerance kept for small rooms on raster-only questions?
6. What does "rooms labelled X" mean when X appears on no room: 0, or "I do not know"?
