# Ideas through one lens: geometry and structure first

Date: 2026-11-14. Lens: compile each drawing once into an exact, typed structure, and answer questions as typed
queries over it.

Labels: **MEASURED** = measured in this session. **SOURCED** = from `stoa/docs/research/` or
`stoa/docs/HOST.md`. **ESTIMATE** = my judgement.

What I looked at (MEASURED, by eye): 12 drawings from 8 sources. Among them: habs hi0822 sheet 14 (plans,
sections, a schedule and three scale bars on one sheet), a 1912 finna elevation with mm dimension chains and a
1:20 bar, a europeana engraving with a bar in "Schuch", a wikimedia photo of a site-map sign, a cubicasa plan
with all text upside down, ResBIM resbim-65 (dimension chains, no scale bar), barlad ground level (walls only),
and opening_design CTR A101 (a plan, a key plan at another scale and two tables). I read 102 questions.

## 1. The lens in one paragraph

A drawing is a program that a draughtsman wrote in a graphic language. The right move is to compile it once
into a typed scene graph: views, scales, rooms, walls, openings, fixtures, text, dimensions, levels and tables,
each node with its source pixels or vector paths, its origin (exact, derived or model) and its error bound.
Every question then becomes a short typed query, and the query result carries its evidence back to the sheet for
free. This gives exact counts (a count is the number of nodes), areas inside 2% (a polygon and a scale),
determinism, a stated method, a confidence that comes from checks and not from a model's feeling, and a cost near
zero per question. Evidence: the same model scores 81% on layout JSON and 31% on the image (SOURCED, lead's digest). **The strongest argument against it:** a compiler needs a grammar, and
the hidden set is "tricky drawings" with another structure. A typed schema answers only what its author foresaw.
On a 1912 hand-drawn scan the compile step is perception, and perception is the unsolved part. So the lens can
give a system that is exact on the sheets it understands and empty on the sheets that decide the score.
Also, public references follow generator conventions (stacked doors, duplicate spaces; SOURCED), and exact
geometry does not protect against that.

## 2. Concepts

Eight concepts. C6, C7 and C8 are the unusual ones.

### C1. Sheet Graph: one layered IR with provenance

**Pitch:** all formats compile to the same four-layer graph, and each layer can be missing without breaking the rest.

**Mechanism.**
- L0 primitives: vector paths, text spans (with rotation), images, IFC entities. All in page coordinates.
- L1 views: a sheet is split into views (plan, elevation, section, detail, schedule, legend, title block, key
  plan). Each view has its own scale and its own unit. CTR A101 and habs hi0822 both need this (MEASURED, by eye).
- L2 entities: Room, Wall, Opening, Fixture, Dimension, Level, Table, Tag. Each has geometry, text, `origin`
  (`printed`, `exact-geometry`, `reconstructed`, `model`), an error bound and a list of L0 ids as evidence.
- L3 relations: contains, bounds, hosts, tags, row-of, same-as (duplicate), on-storey.
- Per format: IFC through IfcOpenShell to L2 directly. DXF through ezdxf. Vector PDF through the path and text
  layers. Raster through C6. DWG through a converter, with a 10% failure rate (SOURCED, `sota/bim-cad-tooling.md`).
- Once per drawing: the full compile, stored as JSON. Per question: a query (C4).

**Needs:** no labels, no training. **Criteria:** accuracy high where L2 exists; evidence is native; creativity
medium; cost near zero.
**Hidden set:** L0 and L1 always exist, so text lookups and schedules work on any file. With C8, an unseen
style gives fewer L2 nodes, not wrong ones.
**Evidence view:** the sheet with the answer's nodes outlined, coloured by `origin`.
**33 hours:** vector PDF and IFC fit. Native DXF and DWG do not; no public question targets them (SOURCED).
**Kill measurement:** MEASURED here. A style-free room rule on 40 swiss sheets with printed areas (1,100 rooms,
no colour codes, no layers): "smallest closed path that contains the room label" is within 2% of the printed
area for 89.9%. "Faces of the arrangement of all line work" gets 1.4% (6.0% without curves), because hatch and
clip lines cut every room. So generic rules work on closed paths only; loose-line walls need
reconstruction first.
**Main risk:** the schema grows without end.

### C2. Scale court: scale as an over-determined estimate per view

**Pitch:** never read "the scale"; collect every witness of scale in a view and let them agree or disagree.

**Mechanism.**
- Witnesses: scale text ("1:100 (A3)", `1/4" = 1'-0"`), a scale bar (bar length against its numbers), each
  dimension string (printed value against the distance between its extension lines), printed room areas against
  polygon areas, DXF `$INSUNITS`, IFC units, and weak priors (a door leaf is 0.7 to 1.0 m).
- Each witness gives pixels per metre with an interval. A robust consensus (median, then inliers) gives the
  scale and its interval. One dimension chain gives 5 to 20 witnesses.
- "1:100 (A3)" is true only on an A3 page. A raster has no paper size, so there only a bar or a dimension counts.
- No witness: the view is `unscaled`. Area and length queries return "unknown: no scale in this view", and the UI
  offers two-click calibration, as the host asked (SOURCED, HOST.md row 7). Counts still work.
- Witnesses disagree: report both, pick none, confidence low. A "not to scale" note (seen on 5 of 33 cubicasa
  plans, SOURCED) vetoes all geometry witnesses.

**Needs:** OCR for rasters, a line detector. **Criteria:** accuracy on every area and length; the explicit
unknown is a host wish; cost 0.
**Hidden set:** the most general part: ResBIM (dimensions, no bar), finna (bar plus chain), US sheets with
several scales, a photo of a sign (an unknown).
**Evidence view:** each witness drawn on the sheet with its value, and a small plot of the agreement.
**33 hours:** text, bar and dimension witnesses on vector PDF fit (8 hours). Bars on old scans do not fit fully.
**Kill measurement:** on 30 ResBIM PNGs, compute the scale from dimension strings and check the spread of the
witnesses. Kill it if the spread is above 1%.
**Main risk:** matching a dimension text to its extension lines on crowded sheets.

### C3. Printed first, computed second: the two-witness rule

**Pitch:** rank answer sources by how exact they are, and use a second source as the confidence.

**Mechanism.** For each quantity the IR can hold up to four values: printed (a schedule cell, a room tag area, a
Qto value), exact geometry (a vector polygon and a consensus scale), reconstructed geometry (raster), and model
estimate. The query returns the best-ranked value. The others become a check. Agreement inside 2% gives high
confidence. Disagreement is shown, not hidden. The data supports it: Qto beats geometry on wall volumes (100% against 61%),
and printed areas answer 99.35% of room questions where they exist (SOURCED, `data/ifc.md`, `data/swiss.md`).

**Needs:** only C1. **Criteria:** accuracy up on convention cases; a real confidence; cost 0.
**Hidden set:** safe, because it prefers what the sheet says over what we infer.
**Evidence view:** "printed 12.03 m², measured 12.01 m², agree" beside the room.
**33 hours:** fits. **Kill measurement:** on the 307 swiss sheets with printed areas, how often do printed and
polygon disagree by more than 2%? If never, the check has no power and is only decoration.
**Main risk:** the generator's reference is sometimes the computed one, not the printed one.

### C4. Typed query plans with convention switches

**Pitch:** a question compiles to a 3 to 6 step plan in a closed algebra, and each ambiguous word is an explicit switch.

**Mechanism.**
- Operators: `select(type, filter)`, `within(view|storey|room|apartment)`, `count`, `sum(attr)`, `measure(area|
  length|perimeter)`, `lookup(table, row, column)`, `join`, `argmax`, `convert(unit)`, `distinct`.
- The tile question becomes: `select(Room, kind=toilet) -> measure(area) -> sum`. Wall tiles would add
  `measure(perimeter) * height`, and height is unknown on a plan, so the plan itself yields the unknown and its request.
- One small-model call per question writes the plan. It sees the question and a text digest of the IR (entity
  types, room labels, table headers, languages). It never sees pixels. Label matching across languages happens
  here ("TUALETTRUUM", "KPH", "Bad" all map to kind=toilet or bath), and the mapping is shown.
- Switches: `distinct|rows`, `visible|model`, `leaf-only|all openings`, `net|gross`, `printed-total|row-sum`.
  The default follows the question text. The answer states the switch and gives the other value as a note.
- Execution is deterministic. The plan is stored, so a replay gives the same answer.

**Needs:** 1 call per question, about 1.5k tokens in and 150 out; about $0.001 on a small model (ESTIMATE from
the price table in `sota/agentic-program-synthesis.md`). **Criteria:** accuracy on compound questions; the plan
is the reasoning view; cost low.
**Hidden set:** new templates and languages cost nothing, because no template is coded. A question outside the
algebra (free text such as "what is the space breakdown per floor") falls to a second tier: a code-writing
agent over the same IR. Two tiers only (SOURCED: more tiers give no gain).
**Evidence view:** the plan as 3 to 6 chips; a click on a chip highlights its node set on the sheet.
**33 hours:** fits. **Kill measurement:** 40 questions that are not public templates (`data/wild-probe-questions.jsonl` plus
compound ones). Kill the closed algebra if under 80% get a valid plan.
**Main risk:** one wrong switch default costs a whole question family.

### C5. Tables are geometry: the schedule compiler

**Pitch:** a schedule is a grid of ruled cells, so rebuild it from the rulings, and it becomes a SQL table.

**Mechanism.** Find ruling lines (vector) or long straight runs (raster). Build the cell lattice. Assign words to
cells through `page.rotation_matrix`. Detect header rows, merged cells and continuation rows. Type each column
(feet-inch, integer, code, text). Link codes to legends ("B3" to "aluminium sliding door"). Link schedule rows to
plan tags (door 121.A in the table to the tag on the plan). Queries run in DuckDB.
Line grouping merged rows on A-801 and G-100 (SOURCED, `data/wild.md`). Cell geometry cannot merge rows. CTR A101 holds a "UNIT COUNT" table and an "AREA PER FLOOR"
table beside the plan, in 302,873 vector paths and 1,805 words (MEASURED).
**Needs:** no training. **Criteria:** accuracy on schedule questions; evidence is the highlighted cells; cost 0.
**Hidden set:** strong on any CAD set. US material is a stated part of the hidden set (SOURCED, HOST.md row 12).
Weak on a scanned schedule: then OCR fills the cells and each cell carries an OCR confidence.
**33 hours:** fits (6 to 8 hours). **Kill measurement:** rebuild the A-801 door table; the row count must be 38
and the archive version 41. **Main risk:** tables without rulings.

### C6. Raster lift with interval geometry (unusual)

**Pitch:** on a raster, every measured quantity is an interval, and abstention is arithmetic.

**Mechanism.**
- Reconstruct: binarise, find wall bands (thick dark runs or parallel line pairs), close door gaps with the
  detected openings, take room faces as regions, attach OCR labels (4 rotations).
- A detector or one VLM call per sheet proposes symbols as points. Each becomes an L2 node with `origin=model`.
  A count is the number of nodes, never a number that a model wrote (SOURCED rule).
- Each room polygon gets an inner and an outer bound (about 1 px per wall edge). The area is an interval, and
  the scale interval from C2 multiplies in. An interval wider than 2% gives a range with the reason "low
  resolution: 1 px = 3.4 cm". A flood fill is within 2% for only 20.8% of rooms on the swiss PNGs (SOURCED), so
  the honest answer is often a range, unless a printed area or a dimension exists (C3, C7).

**Why it could win:** a derived error bar is the unknown that the host asked for. It stops confident wrong numbers.
**Needs:** 1 or 2 vision calls per sheet at ingestion, about $0.02 to $0.05 (ESTIMATE); OCR; optional detector
trained on CubiCasa5K train split (leak rules in `data/cubicasa.md`). **Criteria:** accuracy moderate; evidence
strong; creativity high; cost inside the 10 cent zone.
**Hidden set:** the weakest point of the lens. Hand-drawn plans and elevations have no clean wall bands. The
design then keeps L0 and L1 and marks L2 as missing.
**Evidence view:** the room with its inner and outer outline, and each counted symbol as a numbered dot.
**33 hours:** wall bands and room faces on clean rasters (cubicasa, ResBIM, swiss PNG) fit. Old scans do not.
**Kill measurement:** on 50 swiss PNGs (truth from the PDF), the share of true areas inside our interval. Kill
it if under 90%. **Main risk:** time. It is the largest build with the least certain gain.

### C7. The drawing as a system of equations (unusual)

**Pitch:** printed dimensions are exact, so solve the geometry from the numbers and use pixels only for topology.

**Mechanism.** Read every dimension string and its two extension lines. Each gives an equation: the distance
between two wall lines equals the printed value. Wall lines that are collinear share one unknown. Solve the
linear system (least squares) for all wall-line positions in millimetres. Room areas follow from the solved
coordinates, not from pixels. Chains give free checks: the parts must sum to the total. The finna elevation
and the ResBIM plan both have chains under a total (MEASURED, by eye). A failed sum marks an OCR error at a
known place.
**Why it could win:** it breaks the pixel limit. A 700 px scan with dimension chains gives areas from the
printed millimetres, where a pixel method is outside 2% (ESTIMATE). The evidence is a set of sums that a person
checks. It needs no scale. A frontier model next year will not do this reliably by looking (ESTIMATE).
**Needs:** OCR of rotated digits, line detection, no training. **Criteria:** accuracy on dimensioned rasters and
on the 500 ResBIM plans; creativity high; cost 0 per question.
**Hidden set:** works on any dimensioned orthogonal plan in any language. Useless on undimensioned marketing
plans. Unsolved rooms stay intervals from C6.
**Evidence view:** each dimension coloured green (consistent) or red (residual), and the room with its solved
width and depth.
**33 hours:** axis-aligned plans only. Fits as a 10-hour unit for one person. Skewed scans do not fit.
**Kill measurement:** on 20 ResBIM PNGs, the Living Room area from dimensions against the IFC geometry of the
same model. Kill it if under 15 of 20 are inside 2%.
**Main risk:** rooms whose walls carry no dimension; feet-inch fractions.

### C8. Ink accounting: confidence by round trip (unusual)

**Pitch:** render the IR back to an image, subtract it from the sheet, and treat the ink that is left as what we did not understand.

**Mechanism.** After the compile, every L0 primitive (or every dark pixel on a raster) is either claimed by an
L2 node or not. The share of claimed ink per view is a coverage score. Unclaimed ink is clustered and shown.
A query on a region with low coverage gets a lower confidence and a reason: "34% of the line work in this
plan is not classified". Repeated unclaimed shapes are symbol candidates: one click by the user ("this is a
shower") types all copies for the document.
**Why it could win:** the confidence is computed and local on the sheet. An unseen style becomes a visible gap
with a cheap repair, not a silent failure. Judges see it in 5 seconds.
**Needs:** nothing but C1. **Criteria:** accuracy indirectly (fewer confident errors); evidence very strong;
creativity high; cost 0.
**Hidden set:** this is the guard for it. A tricky drawing gives low coverage, so the system says so.
**33 hours:** the vector version fits (4 hours). The raster version fits as a rough pixel diff.
**Kill measurement:** drop one parser rule on 50 sheets. Kill it if coverage does not drop where answers go wrong.
**Evidence view:** claimed ink in colour, unclaimed ink in grey.
**Main risk:** hatches, dimension lines and furniture are harmless ink and need their own class.

## 3. The system I would build from this lens

One pipeline, one rule: **the compiler never guesses silently, and the query engine never perceives.**

```
file -> [sniff: IFC | DXF/DWG | PDF vector | PDF scan | raster]
          |
          v
   L0 primitives (paths, text+rotation, images, IFC entities)      exact
          |
   L1 views: split sheet -> plan / elevation / section / schedule / legend / title
          |            each view: scale court (C2) -> scale interval | unscaled
          v
   L2 entities + L3 relations
      IFC      : IfcOpenShell (Qto, footprint, storey decomposition)        origin=printed|exact
      vector   : closed paths + labels, schedule compiler (C5)             origin=exact|printed
      raster   : OCR + wall bands + proposed marks (C6), dimension solve (C7) origin=reconstructed|model
          |
   ink accounting (C8) -> coverage per view, list of unknowns
          |
          v
   Sheet Graph JSON (stored once per document)  ---> evidence renderer (overlay on the sheet, 3D for IFC)
          ^
question -> plan compiler (1 small-model call, text only, C4) -> executor (deterministic)
          -> answer record {value, unit, plan, evidence ids, origin per step, switches, interval,
                            confidence from checks (C3, C8), unknowns + request}
          -> tier 2 only if no valid plan: code agent over the same JSON, marked "model reasoning"
```

Ingestion: 0 for IFC and vector PDF, $0.02 to $0.05 for a raster (ESTIMATE). Per question: about $0.001
(ESTIMATE). 30 questions on one document stay inside the 10 cent zone (SOURCED, HOST.md row 10).

**Order of work.**
1. Hours 0 to 6: the answer record, the IR schema, L0 and L1 for PDF, scale text and bar, the IFC compile, 8
   plan operators. Test on the public set with the leak paths banned.
2. Hours 6 to 14: closed-path rooms with holes and unit outlines, the schedule compiler, the switches, ink
   accounting for vectors.
3. Hours 14 to 22: the raster path: rotated OCR, dimension witnesses, proposed marks, interval areas. After the
   Saturday hint, move people to the format that the hint names.
4. Hours 22 to 28: C7 if dimensioned rasters matter; else robustness: no crash, time limits, a fallback record.
5. Hours 28 to 33: probe questions, unknown cases, the evidence view, a rehearsal of a live session.

**What I would cut first:** a 3D lift of the plan to a mini-IFC (walls extruded to `IfcWall`, one viewer for all
formats: good for creativity, no accuracy), then DXF and DWG native parsing, then C7, then symbol detection on old
scans. **Never cut:** the scale court, the unknown with a request, and the no-crash rule.

## 4. Where this lens is wrong

- **Old scans, engravings, photos of signs** (habs, finna, europeana, wikimedia: 6,566 drawings, SOURCED). A frontier VLM reads
  text at 0.8 to 0.95 (SOURCED) and beats any reconstruction I can build in 33 hours. Here the right design is
  VLM first with marks as evidence, and my lens adds only the scale court and the counting rule.
- **Symbol counts on rasters.** Counting needs a detector. Geometry does not find a toilet. A learned-perception
  lens owns this, and windows and doors are 19.4% of cubicasa questions (SOURCED).
- **Generator conventions.** Stacked doors, duplicate spaces, nested stairs. If the hidden set keeps the public
  generators, a lookup-shaped solver that copies conventions beats a correct compiler. My switches reduce the
  loss but cannot remove it.
- **Free-text questions.** On ifc_bench an iterating code agent scores 56% against 19% for one-shot queries
  (SOURCED). A closed algebra is the wrong tool there.
- **A very small hidden set.** If Stoa asks 30 questions on 5 files by hand, a good VLM with a person-in-the-loop
  UI can match us with a tenth of the work. The compiler pays off only if it is robust on file one.

## 5. Ten things to measure first

1. **Closed-path room rule on real CAD sheets** (5 opening_design plans, 71 ifc_models plans). Settles whether
   vector L2 is generic or a swiss artifact. Baseline: 89.9% on swiss (MEASURED).
2. **Scale court on 30 ResBIM PNGs and 20 opening_design sheets**: witness spread, share of views with a scale.
   Settles whether areas on unlabelled sources are possible.
3. **Plan coverage on 40 non-template questions.** Settles closed algebra against agent-first.
4. **Interval coverage on 50 swiss PNGs** against PDF truth. Settles whether C6 ships.
5. **Dimension solve on 20 ResBIM plans** against IFC geometry. Settles whether C7 gets a person.
6. **Schedule compiler on A-801 current and archive** (38 and 41 rows). Settles cell geometry against a VLM read.
7. **Coverage against error** on deliberately broken parses. Settles whether C8 is the confidence or a visual.
8. **Compile time and crash rate on 200 random files**, with the 302,873-path sheet. Settles the time limit
   per file in a live session.
9. **Printed against computed disagreement** on swiss printed-area sheets and Qto models. Settles the
   two-witness thresholds.
10. **Unknown detection on 30 questions with no answer on the sheet.** Settles whether unknowns come from the
    structure alone or need a model check.
