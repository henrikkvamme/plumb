# BIM (IFC) question answering and CAD/PDF tooling - state of the art, measured on our data

Track: question answering on IFC models, and the tooling to read IFC, DXF, DWG and vector PDF.
Date: 2026-11-13. Author: research agent for the Stoa team.

Labels used in this file:

- **MEASURED**: I ran it on our local dataset. The script is in the scratchpad (paths at the end).
- **READ**: I opened the source and the quote is in the Sources table.
- **UNVERIFIED**: I saw it only in a search snippet, or the page did not load. Do not rely on it.
- **ESTIMATE**: my judgement. No measurement stands behind it.

Web search and web fetch hit a rate limit near the end of this pass. Some secondary items stay UNVERIFIED for that reason. They are marked.

## Findings that change decisions

1. **The ifc_models ground truth was made with IfcOpenShell. Deterministic IfcOpenShell code reproduces it.** MEASURED: for room net floor area questions (IFC and plan PDF, all languages), `ifcopenshell.util.shape.get_footprint_area` on the IfcSpace geometry is within 2% for 1,145 of 1,150 matched rooms (99.6%). The plan PDFs carry the footer "Genereret fra IFC (Molio_with_URIs.ifc, IfcOpenShell IfcConvert 0.9.0)" and "Målestok 1:100". Pin `ifcopenshell==0.9.0.post1` to match the generator. Moves accuracy, cost ($0 per question) and verification (cite GlobalId). [M1, M2, S9]
2. **Qto base quantities agree with the truth where they exist, but they are often missing, and they use model units.** MEASURED: `Qto_SpaceBaseQuantities.NetFloorArea` exists for 417 of 1,150 rooms (36%), and all 417 are within 2%. Wall NetVolume (69/69) and NetSideArea (32/32) match Qto summed over the storey decomposition. Wall Length Qto is in millimetres in the Molio model (185,129.31 for an answer of 185.129 m). Geometry-computed wall volume matches only 45/69. Rule: use Qto when present and scale by the project unit, else geometry. [M1, M3]
3. **Storey assignment and "what counts" decide the count questions.** MEASURED: storey counts match in 204/207 cases with recursive decomposition (`get_decomposition`) but only 140/207 with direct containment. Model counts match 127/136 with `by_type` including subtypes, versus 116/136 without. IFC2X3 has no IfcSanitaryTerminal or IfcLightFixture: count IfcFlowTerminal by type object (8 more hits). Molio has 579 IfcStair, of which 564 are parts of another IfcStair. The answer is 15, the top-level stairs. [M3, M4]
4. **Our 820 ifc_bench questions are exactly IFC-Bench v2, with public answers. The 206 missing questions sit on 3 projects we do not have.** MEASURED: all 820 questions and answers match the Hugging Face CSV (1,026 data rows; the dataset card says 1,027 pairs). 399 of ours are in the paper's test split, 421 in train. The missing 206 are on samuel_macalister_sample_house (74), schependomlaan (51) and wbdg_office (81). A hidden set that holds out whole projects is likely (ESTIMATE). Any eval on ifc_bench must split by project, and must never look up the public answers. [M5, S2]
5. **Free-text IFC QA is not solved by agents. A strong agent scores about 56%.** READ: Hellin et al. report 56.0% for an adaptive IfcOpenShell agent on GLM 4.7 versus 19.1% for one-shot query generation, on 514 test questions, graded by an LLM judge. "For high-capability models, augmentation adds cost without measurable benefit." Materials questions reach only 42%. Plan for 50-65% on ifc_bench with an agent, and put effort into the structured ifc_models slice first. [S1]
6. **The scoring of IFC-Bench is an LLM judge with four binary criteria, not a 2% rule.** READ: an answer is "rated correct only when all four substantive criteria (1–4) are simultaneously satisfied" (faithfulness, completeness, transparency, relevance), and the judge sees the execution trace. A trace with cited GlobalIds and property names directly serves both accuracy and verification. [S1, S3]
7. **Easy IFC retrieval is solved, so creativity must come from elsewhere.** READ: on the auto-generated IFC-MCQ benchmark, "14 exceed 95% overall accuracy and seven exceed 99%", and a 27B open model reaches 100%. On a 30-question set, IfcLLM reached 96-100% with GPT-OSS 120B at 3-4 LLM calls and about 3k-4.6k input tokens per query. Small open models handle routing and lookups. The hard part is geometry, missing data and conventions. [S4, S5]
8. **No question in the public set targets DWG or DXF, and vector PDFs carry no layers.** MEASURED: question targets are png 85,514, pdf 40,342, ifc 1,188. The 271 DWG files are all in opening_design (244 are AC1027). OCG layers exist in 14 of 1,825 PDFs. A /VP viewport (scale metadata) exists in 11. Scale must come from text ("1:100", "1:200 (A3)") or from a scale bar, not from PDF metadata. DWG conversion is a low priority for the public set, but keep a path for the hidden set. [M6, M7]
9. **PyMuPDF is AGPL-3.0. pypdfium2, pdfplumber, ezdxf and shapely are permissive.** READ. AGPL is fine for a non-commercial hackathon, but Stoa would need a commercial licence to ship it. LibreDWG is GPL-3.0+ and "AutoCAD® fails to import some of our files still (~10% failure rate)". ODA File Converter is closed and packaged as "custom" licence. [S11, S12, S13, S14, S15]

## Landscape

### LLM agents and query systems on IFC

| System | What | Measured result | Cost data | Code, licence | Status |
|---|---|---|---|---|---|---|
| cobbie / IFC-Bench v2 (TU Munich, 2026) [S1, S2, S3] | Adaptive CodeAct agent writes IfcOpenShell Python in a sandbox; 4-tier claim sourcing; abstains on budget exhaustion | 56.0% (GLM 4.7, adaptive), 19.1% (static), 25.7% (GLM 4.5 Air). Per category 53-67% for GLM 4.7. Per-project spread 25-90% | Not reported; examples took 13-14 iterations | github.com/sylvainHellin/cobbie, CC BY 4.0; dataset CC BY 4.0, some models GPLv3 | READ |
| ONESTRUCTION Construction AI Leaderboard (Nov 2026) [S6] | IFC-Bench v2, 514 questions, 15 code runs, DeepSeek-V3.2 judge (model count of 20 not confirmed) | Scores only in an image (not confirmed); Claude Opus 5 ranked first on the BIM understanding axis, Opus 5.5 first overall (73.7) | No IFC cost; AEC-Bench (drawings): Opus 5.5 70.2 (Drawings & documents axis) at $0.33 per task, GPT-6.1 Sol 66.3 (same axis; 70.2 overall) at $0.12 | blog | READ (numbers per model for IFC not readable) |
| IfcLLM (UNSW, 2026) [S4] | IFC to compact SQLite (16 tables, EAV property table) plus Neo4j room-door-stair graph; LangGraph; open models | 0.96 overall (GPT-OSS 120B), 29/30 on a 99-room office; GPT-5.6 Luna 0.90 | about 2.3k-4.6k input tokens, 3-4 calls per query; outliers to 428.7k tokens on large result sets | No repo link found in the read part; paper CC BY-NC-ND | READ |
| IFC-MCQ (UNSW, Oct 2026) [S5] | Auto-generated multiple-choice items, 17 read-only tools, verified answers | Up to 100%; 14 models over 95%; no-IFC control 37.0-49.7% | Most items need one tool call | Paper CC BY-NC-ND | READ |
| LLM-assisted Graph-RAG on IFC (Iranmanesh et al., Apr 2025) [S20] | IFC to Neo4j, few-shot text-to-Cypher | Not read (paper exists, checked 2026-11-13; GPT-4o, Neo4j, Cypher confirmed) | - | - | paper confirmed, result not read |
| EC3 2025 multi-agent BIM QA (cobbie predecessor) [S21] | ReAct agent with 29 hand-coded tools | "80%" on 99 queries per S1's related work; S1 says "tool limitations accounted for 45% of errors" | - | - | 80% confirmed on the EC3 page; rest via S1 |

### MCP servers for IFC

| Server | Tools | Licence | Status |
|---|---|---|---|
| IfcMCP (official IfcOpenShell, `pip install 'ifcmcp[mcp]'`) [S7] | Session, query (`ifc_summary`, `ifc_tree`, `ifc_info`, `ifc_select`, `ifc_relations`, `ifc_clash`, `ifc_materials` ...), drawing (`ifc_plot` via ifcopenshell.draw), ShapeBuilder, edit, `ifc_quantify` ("writes `IfcElementQuantity` psets in-place") | LGPL-3.0-or-later per the repo package table [S8] | READ |
| ifc-lite MCP (`ifc-lite mcp model.ifc`) [S10] | Query and edit over stdio or HTTP | MPL-2.0 | READ |
| smartaec/ifcMCP, flinker-app/ifc-mcp, Daviidro/ifcopenshell-mcp, Bonsai MCP servers | 7-8 read tools, or Blender-hosted | various | UNVERIFIED (search snippets only) |

MCP is a transport, not an accuracy gain. S1 found that hand-made tools gave no gain for a strong model, and hurt a weak one (-10.2 pp). For our cost criterion, direct Python is cheaper than an MCP round trip per tool call (ESTIMATE).

### IFC libraries

| Library | Version (READ) | Licence | Strength | What it cannot do |
|---|---|---|---|---|
| IfcOpenShell (Python, C++) [S8, S9] | 0.9.0.post1, 15 Oct 2026; wheels for macOS arm64 and Linux x86-64/aarch64, Python 3.10-3.15 | LGPL-3.0-or-later | Full schema parsing IFC2X3 to IFC4X3; OpenCASCADE geometry; `util.element`, `util.shape`, `util.unit`, `ifc5d` QTO, `ifcpatch` Ifc2Sql, `ifcopenshell.draw`, IfcConvert | Booleans are slow on big models; geometry can fail per element (MEASURED: duplex hallways give area 0.0) |
| ifc-lite (Rust, WASM) [S10] | crates up to 20.x (UNVERIFIED versions) | MPL-2.0 | "full parse lands around 50 MB/s"; "99.9%+ agreement" with IfcOpenShell on its corpus; Python geometry wheel `ifclite-geom` | No Python query API or QTO named in the README; young project (473 stars) |
| web-ifc (That Open) [S16] | not shown on the page | MPL-2.0 | JS/WASM reader and writer, also a C++ library | Limits not documented on the page |
| That Open Fragments | 3.6.0 (UNVERIFIED, third-party PR) | MIT (UNVERIFIED) | Viewer format | Not a QA tool |
| xBIM Essentials [S17] | last push 28 Aug 2026 | CDDL (READ from LICENCE.md) | .NET | Wrong ecosystem for us |

### DXF, DWG and PDF libraries

| Tool | Version (READ) | Licence | Use for us | Limits |
|---|---|---|---|---|
| ezdxf [S12] | 1.4.5, 16 Oct 2026 | MIT | Read swiss_dwellings DXF (MEASURED: 26 ms per file, semantic layers ROOM_OUTLINE, ROOM_TEXT, DOOR, WINDOW, WALL, $INSUNITS=6 metres) | DWG only through the `odafc` add-on and the external ODA File Converter |
| dxf-rs (Rust) [S17] | last push 31 Oct 2026 | MIT | Rust DXF reader if we pick a Rust core | Release cadence low (UNVERIFIED version list) |
| LibreDWG `dwg2dxf` [S14] | 0.13.4 manual (17 Mar 2026); Homebrew formula 0.14 (MEASURED via `brew info`) | GPL-3.0-or-later | Convert our 271 DWG (AC1015 to AC1027) | "not as stable as the unfree Teigha library yet"; ~10% AutoCAD import failures; `--binary` "under construction" |
| ODA File Converter [S15] | ODA Platform 27.10 (30 Oct 2026) | "custom", unfree packaging (AUR) | Best fidelity DWG to DXF; CLI takes source dir, target dir, filter, version, recursive, audit | Qt app; needs a display (xvfb on Linux, UNVERIFIED); licence text not readable online |
| PyMuPDF [S11] | 2.1, 2 Nov 2026 | AGPL-3.0 or Artifex commercial | Fast text with boxes, `get_drawings()` paths, OCG API | AGPL |
| pypdfium2 [S13] | 5.15.2, 9 Nov 2026 | Apache-2.0 / BSD-3-Clause | Rendering, text, page objects | Path segments only through the raw API |
| pdfplumber (pdfminer.six) | 0.11.10 (MEASURED install) | MIT (MEASURED metadata) | Lines, rects, curves, words with boxes, table finder | Slower; pure Python |
| pdfium-render (Rust) [S17] | 0.9.6 (Cargo.toml) | MIT OR Apache-2.0 | Rust PDF reading via PDFium | Must ship the PDFium binary |
| lopdf (Rust) [S17] | last push 12 Nov 2026 | MIT | Raw object access (/VP, /Measure, OCG) | No renderer; you parse content streams yourself |
| shapely 2.2.0 | MEASURED install | BSD-3-Clause | Polygon area, point in polygon, buffers, unions, STRtree | 2D only |

### Geometric predicates we need, and the library for each

| Predicate | Best library | Note |
|---|---|---|
| Polygon area (shoelace), union, difference | shapely (Python), `geo` crate (Rust, UNVERIFIED) | Room outlines in DXF are closed LWPOLYLINE; IFC spaces via `util.shape.get_footprint_area` |
| Point in polygon (label to room, symbol to room) | shapely `contains` with STRtree | Use the label insertion point from ROOM_TEXT or PDF word box |
| Space and element area or volume from IFC | IfcOpenShell `util.shape` (`get_footprint_area`, `get_volume`, `get_side_area`) | MEASURED: footprint area is the generator's rule for rooms |
| Storey membership | `ifcopenshell.util.element.get_decomposition(storey)` | MEASURED: 204/207 versus 140/207 for direct containment |
| Units | `ifcopenshell.util.unit.calculate_unit_scale` | MEASURED: Qto length in mm in Molio |
| Wall centre lines | IFC: the wall `Axis` representation, else Qto Length; drawings: `pygeoops.centerline` on wall hatch polygons (UNVERIFIED) | Straight skeleton in CGAL is GPL (ESTIMATE, not checked) |
| Openings, doors, windows | IFC: IfcRelVoidsElement and IfcRelFillsElement; DXF: DOOR layer leaf rectangle + ARC; DWG: INSERT block names | Block names are office conventions, so treat them as data, not rules |
| Scale from PDF | Regex on text ("1:100", "Målestok 1:100", architectural feet-inch scales), then a scale bar; /VP only in 11 of 1,825 PDFs | MEASURED |

## What we can use this weekend

1. **ifc_models solver, deterministic (4-6 h, ESTIMATE).** `pip install ifcopenshell==0.9.0.post1 shapely`. For a plan PDF, read the footer to get the source IFC file name and the storey. Answer rooms by geometry footprint area. Answer walls and slabs by Qto (scaled by unit) over `get_decomposition(storey)`, with geometry as a fallback. Count with `by_type` including subtypes, top-level only (skip parts aggregated into the same class), and map IFC2X3 flow terminals by type. MEASURED upper bound on the public slice: about 99% for room areas, 100% for wall volume and side area, about 94% for wall length after the unit fix (30/32, ESTIMATE from M3 rows). Cost $0. Evidence: GlobalId, Qto name, value, unit.
2. **Room-name matching across conventions (1 h).** Match on `LongName (Name)`, then `Name`, then `LongName`, case and accent folded. MEASURED: one model (tuwien escape route, 33 rooms) uses another pattern.
3. **ifc_bench agent (6-10 h).** Clone github.com/sylvainHellin/cobbie (CC BY 4.0) for the judge rubric only. Build our own loop: Claude writes IfcOpenShell code in a sandbox, max 10-15 runs, must cite GlobalIds and property names, must say "Information not found in BIM model" when it fails. Precompute a per-model JSON summary (storeys, spaces with areas, type counts, materials) so most questions need 1-3 calls (ESTIMATE). Evaluate by project-held-out split; never read the HF ground truth at inference.
4. **Official IfcMCP for demos (1 h).** `pip install 'ifcmcp[mcp]'`, then `claude mcp add --transport stdio ifc -- ifcmcp`. Useful to show the judges an interactive trace. Not needed for batch scoring.
5. **Swiss DXF reading (2 h, other track owns the solver).** `ezdxf.readfile`, layers ROOM_OUTLINE and ROOM_TEXT, shapely for areas. MEASURED: only 1,266 of 12,016 swiss area answers equal a printed room label exactly, so most area questions need polygon sums, not label lookup.
6. **DWG fallback (2 h, only if time).** `brew install libredwg` (0.14, GPL) and `dwg2dxf --as=r2013`, then ezdxf. Keep ODA File Converter as a manual check for files that fail. Not needed for the public questions.
7. **Vector PDF reader.** PyMuPDF for the hackathon (`page.get_text("words")`, `page.get_drawings()`). Wrap it behind an interface so pypdfium2 or pdfplumber can replace it if Stoa wants a permissive stack.

## What does not work

- **One-shot text-to-code on IFC.** 19.1% versus 56.0% for an iterating agent (S1). Static generation abstains on over 75% of geometric questions.
- **Hand-made tool libraries for a strong model.** "1.2pp range with no significant pairwise differences" for GLM 4.7; -10.2 pp for the weaker model (S1).
- **Trusting Qto alone.** MEASURED: 64% of rooms have no NetFloorArea Qto. Values are in model units.
- **Trusting computed geometry alone for walls.** MEASURED: geometry volume matches 45/69 wall-volume answers; Qto matches 69/69.
- **Direct containment for storey counts.** MEASURED: 140/207.
- **Counting every IfcStair.** MEASURED: 579 versus the answer 15 in Molio.
- **Graph-only stores for numeric aggregation.** IfcLLM: in single-backend variants "65.2% of the SQL statements it generated for graph-based queries were invalid", and graph-only variants miss aggregation queries (S4).
- **Raw Ifc2Sql as an LLM interface.** IfcLLM rejects it as "not well suited to LLM-based querying" because its schema mirrors IFC (S4).
- **Scale from PDF metadata.** MEASURED: /VP in 11 of 1,825 PDFs, OCG in 14.
- **LibreDWG output as ground truth.** ~10% AutoCAD import failures by its own manual (S14).

## Open questions

1. Do hidden ifc_models plan PDFs always ship with their IFC? The footer names it. If the IFC is absent, we need polygon measurement at 1:100 from the PDF, which nobody has measured.
2. Does Stoa grade ifc_bench free text with the cobbie LLM judge, or another rule?
3. Are the 206 missing IFC-Bench questions (3 projects) in the hidden set? If yes, an agent must work on unseen models, and leakage from public answers is a judge question.
4. Are the 5 geometry misses on rooms (duplex hallways with area 0.0, 3 Molio technical rooms) a generator rule we can copy, or generator noise?
5. Why do 7 storey-count and 1 model-count questions still miss? Not analysed.
6. Will the hidden set ask about DWG? If so, LibreDWG versus ODA fidelity on our 271 files must be measured.

## Check of the prior research

Read after my own search. File: `stoa/docs/inputs/prior-research/weekend-plan.md` and `research-tracks.json`.

| Prior claim | Verdict |
|---|---|
| "IFC recipes (Qto, storeys, spaces) ... 90% target, unmeasured" | Now measured. Better than claimed for areas (99.6% with geometry), but Qto-only would fail 64% of rooms. Recipe must be geometry first for spaces, Qto first for walls and slabs, with unit scaling. |
| "ifc_models: 13% of questions on only 6 models", "ifc_bench 249 questions on 5 models" | Preview figures. Full set: ifc_models 3,062 questions on 84 files; ifc_bench 820 questions on 25 IFC files (31 files in the folder). |
| CodeAct agent "55-65%. GLM-4.7 reached 56%" | Confirmed: 56.0% [51.8, 60.3] on 514 test questions (S1). |
| "an exploring IfcOpenShell agent beats static queries by 37 points" | Confirmed: +36.8 to +38.5 pp (S1). |
| cobbie "rubric (exact counts, 2%, cited properties) matches Stoa's scoring" | Not supported. The rubric is an LLM judge with abstention plus four binary criteria (S1). I found no 2% rule in it. |
| "Stoa's ifc_bench slice ... comes from this benchmark" | Confirmed and sharpened: all 820 questions and answers match the public CSV exactly (M5). This is a leakage risk. |
| LibreDWG manual 0.13.4 (17 Mar 2026), GPL, AutoCAD fails on some DXFs, Homebrew ships 0.14 | Confirmed (S14, `brew info`). |
| ODA "non-members may use it for non-commercial applications only" | UNVERIFIED. The ODA page I read does not state the licence; AUR lists "custom". |
| PyMuPDF AGPL-3.0; pdfplumber and pypdfium2 permissive | Confirmed (S11, S13, MEASURED metadata). |
| "opening_design has 20 DWGs" | Preview figure. Full set: 271 DWG files, all in opening_design. |

## Sources

| id | URL | title | date | claim it supports | exact supporting quote | check |
|---|---|---|---|---|---|---|
| S1 | https://arxiv.org/html/2605.01698v1 | BIM Information Extraction Through LLM-based Adaptive Exploration (Hellin, Jang, Fuchs, Nousias, Borrmann, TU Munich) | 2026-05-03 | 56.0% vs 19.1%; augmentation no gain; LLM judge; materials 42% | "Adaptive-4.7 outperforms Static-4.7 by +36.8–38.5 pp across all completed augmentation strategies"; Table 3 cell "56.0% [51.8, 60.3]"; "For high-capability models, augmentation adds cost without measurable benefit."; "rated correct only when all four substantive criteria (1–4) are simultaneously satisfied"; "materials-related questions (26% of Category 1) achieve only 42% accuracy" | confirmed (title, 5 authors, 2026-05-03, 56.0%/19.1%/25.7%, +36.8-38.5 pp, 1.2pp range with p>0.8, -10.2 pp, 42% materials, four criteria, judge sees full execution trace, 514 test, 25-90% per-project spread, 29 tools/45% all in text) |
| S2 | https://huggingface.co/datasets/sylvainHellin/ifc-bench | sylvainHellin/ifc-bench dataset card | 2026 (version v2.0.3 not found on page) | 1,027 pairs, CC BY 4.0, test split 514, project list | "1,027 question-answer pairs covering diverse BIM information retrieval tasks"; "Licensed under CC BY 4.0"; "Test: 514 questions." | corrected: the card says 1,027 pairs and "Test: 514 questions", CC BY 4.0, some models GPL v3, all confirmed. The version "v2.0.3" is not on the page (not found). The CSV has 1,026 data rows plus a header, so the card count is one higher than the file |
| S3 | https://github.com/sylvainHellin/cobbie | cobbie: A Question Answering system for BIM models | 2026 | Licence, stack, judge | "CC BY 4.0 -- see LICENSE"; "Z.AI (GLM-4.7) -- default for all experiments" | confirmed (README: "License CC BY 4.0 -- see LICENSE"; GLM-4.7 default model). The GPLv3 remark comes from S2, not S3 |
| S4 | https://arxiv.org/html/2605.13236 | IfcLLM: Natural Language Querying of IFC Models through Complementary Relational and Graph Representations (Lamsal et al., UNSW) | v3 2026-10-21 | 96-100% on 30 queries; tokens; Ifc2Sql rejected; graph-only SQL invalid | "29 out of 30 queries (96.7% accuracy)"; "not well suited to LLM-based querying"; "65.2% of the SQL statements it generated for graph-based queries were invalid" | confirmed (title, 5 authors, v1 2026-05-13, v3 2026-10-21, 29/30 = 96.7% on Building B3 with 99 rooms, GPT-OSS 120B 0.96, GPT-5.6 Luna 0.90, ~3-4 calls, 428.7k outlier, 16 tables with EAV, 65.2%, "not well suited", CC BY-NC-ND). Authors are 5, not "Lamsal et al." only; no repo link found in the page |
| S5 | https://arxiv.org/html/2610.30533 | IFC-MCQ: Automatically Generating Multiple-Choice Benchmarks for Evaluating LLM Agents on IFC Data Retrieval (Lamsal, Zlatanova, Shen) | 2026-10-21 | Easy retrieval near 100%; no-IFC control | "14 exceed 95% overall accuracy and seven exceed 99%."; "overall accuracy ranged from 37.0% to 49.7% across the four LLMs" | confirmed (title, 3 authors, 2026-10-21, "Among 17 LLMs, 14 exceed 95% ... seven exceed 99%", 17 read-only tools, 37.0-49.7%, qwen3.6-27b 100%, CC BY-NC-ND) |
| S6 | https://huggingface.co/blog/ONESTRUCTION/construction-ai-leaderboard | Construction AI Leaderboard: Overview and Evaluation Details (Ryo Kanazawa, ONESTRUCTION) | 2026-11-07 | IFC-Bench as a leaderboard axis; AEC-Bench cost | "it consists of 514 questions on 31 IFC models."; "The agent runs code up to 15 times and answers in text."; "we fixed the judge AI to DeepSeek-V3.2, shared across all models." | partly: confirmed author, date 2026-11-07, 514 questions on 31 IFC models, 15 code runs, DeepSeek-V3.2 judge, Opus 5.5 $0.33 vs Opus 5 $1.8, Sol $0.12. Corrected: Opus 5.5 ranks first overall (73.7) and first in Drawings & documents (70.2); Opus 5 is first on the BIM understanding axis, which holds the IFC-Bench-V2 score. Sol scores 70.2 overall and 66.3 in Drawings & documents. "20 models" and "scores only in an image" not confirmed in the page text |
| S7 | https://docs.ifcopenshell.org/ifcmcp.html | IfcMCP - IfcOpenShell 0.9.0post1 documentation | 2026 | Official MCP install and tools | "pip install 'ifcmcp[mcp]'"; `ifc_quantify`: "run quantity take-off; writes `IfcElementQuantity` psets in-place" | confirmed (install line, ifc_quantify text, ifc_plot, ifc_clash, ifc_summary; docs titled 0.9.0post1) |
| S8 | https://github.com/IfcOpenShell/IfcOpenShell | IfcOpenShell repository | 2026 | Licence, schemas, ifcmcp component | "IfcOpenShell is an open source (LGPL) software library for working with Industry Foundation Classes"; "Complete parsing support is provided for IFC2x3 TC1, IFC4 Add2 TC1, IFC4x1, IFC4x2, and IFC4x3 Add2." | confirmed (LGPL README text, schema list; ifcmcp listed LGPL-3.0-or-later in the component table) |
| S9 | https://pypi.org/project/ifcopenshell/ | ifcopenshell on PyPI | 0.9.0.post1, 2026-10-15 | Version, wheels, licence | Version "0.9.0.post1", release "Oct 15, 2026", licence "LGPL-3.0-or-later" | confirmed (0.9.0.post1, Oct 15, 2026, LGPL-3.0-or-later, Python >=3.10 <3.16, macOS ARM64, Linux x86-64 and aarch64 wheels) |
| S10 | https://github.com/LTplus-AG/ifc-lite | ifc-lite (LTplus AG) | 2026 | Rust/WASM parser, MCP, speed, licence | "STEP tokenization runs at roughly 1.2 GB/s; a full parse lands around 50 MB/s."; "verified element-by-element against IfcOpenShell (99.9%+ agreement on the public benchmark corpus)"; "MPL-2.0 - use, modify, redistribute." | confirmed (1.2 GB/s, 50 MB/s, 99.9%+ agreement, MPL-2.0, ifclite-geom, 473 stars via page and API) |
| S11 | https://pypi.org/project/PyMuPDF/ | PyMuPDF on PyPI | 2.1, 2026-11-02 | AGPL licence | "Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License" | confirmed (2.1, Nov 2, 2026, dual AGPL / Artifex commercial) |
| S12 | https://pypi.org/project/ezdxf/ | ezdxf on PyPI | 1.4.5, 2026-10-16 | MIT; DWG only via ODA | "`odafc` add-on, an interface to the ODA File Converter to read and write DWG files" | confirmed (1.4.5, 16 Oct 2026, MIT, odafc add-on) |
| S13 | https://pypi.org/project/pypdfium2/ | pypdfium2 on PyPI | 5.15.2, 2026-11-09 | Permissive licence; raw API for paths | "pypdfium2 itself is available by the terms and conditions of `Apache-2.0` / `BSD-3-Clause`."; "many components are not covered by helpers yet" | confirmed (5.15.2, Nov 9, 2026, Apache-2.0 / BSD-3-Clause, "not covered by helpers yet") |
| S14 | https://www.gnu.org/software/libredwg/manual/LibreDWG.html | GNU LibreDWG manual | 0.13.4, 2026-03-17 | GPL; DXF output quality | "We can write ASCII DXF files in various versions, with much more data than other free DWG libraries, but not as stable as the unfree Teigha library yet. AutoCAD ® fails to import some of our files still (~10% failure rate)."; "--binary as a binary DXF file, with full precision, under construction." | confirmed (0.13.4, 17 March 2026, GPLv3+, ~10% failure rate, Teigha text, --binary under construction) |
| S15 | https://www.opendesign.com/guestfiles/oda_file_converter and https://aur.archlinux.org/packages/oda-file-converter | ODA File Converter; AUR package | ODA Platform 27.10 2026-10-30; AUR updated 2026-11-08 | CLI inputs; unfree licence | "ODA File Converter application features a graphical interface and a command-line interface, and accepts the following inputs: Source directory Target directory Input file filter ... Output version/type Recursive flag Audit flag"; AUR "Licenses: custom" | partly: ODA Platform 27.10 (Oct 30, 2026), CLI inputs, AUR "Licenses: custom" and update 2026-11-08 confirmed. Qt and display need not checked |
| S16 | https://github.com/ThatOpen/engine_web-ifc | web-ifc | 2026 | JS reader, MPL-2.0 | "web-ifc is a javascript library to read and write ifc files, at native speeds."; licence shown "MPL-2.0 license" | confirmed (quote, MPL-2.0 licence) |
| S17 | https://api.github.com/repos/{xBimTeam/XbimEssentials, ixmilia/dxf-rs, ajrcarey/pdfium-render, J-F-Liu/lopdf} and raw Cargo.toml | GitHub API repository metadata and licence files | read 2026-11-13 | Licences and activity | XbimEssentials LICENCE.md: "Common Development and Distribution License (CDDL)"; pdfium-render Cargo.toml: `license = "MIT OR Apache-2.0"`, `version = "0.9.6"`; dxf-rs and lopdf API `license.spdx_id`: "MIT" | confirmed (XbimEssentials CDDL, pushed 2026-08-28; dxf-rs MIT, 2026-10-31; lopdf MIT, 2026-11-12; pdfium-render Cargo.toml 0.9.6 and MIT OR Apache-2.0, although the GitHub API shows NOASSERTION) |
| S20 | https://arxiv.org/pdf/2504.16813 | LLM-assisted Graph-RAG Information Extraction from IFC Data (Iranmanesh, Saadany, Vakaj) | 2025-04-23 | IFC to Neo4j text-to-Cypher exists | UNVERIFIED: not opened (rate limit) | confirmed: arXiv 2504.16813 exists, title, 3 authors, 2025-04-23; abstract says Graph-RAG with GPT-4o on IFC (S4 adds Neo4j and Cypher). The result figure was not read |
| S21 | https://ec-3.org/publication/ec32025_265/ | Natural Language Information Retrieval from BIM Models: An LLM-Based Multi-Agent System Approach | EC3 2025 | 80% predecessor | UNVERIFIED directly; S1 says prior work had "29 manually coded tools" and "tool limitations accounted for 45% of errors" | confirmed: EC3 page exists with this title (Hellin, Nousias, Borrmann, TUM, DOI 10.35490/EC3.2025.265); abstract states "80% overall accuracy". The 99 queries and 29 tools come from S1 |

Local measurements (scripts in the session scratchpad
`/private/tmp/claude-501/-repo/d76b56b4-2c8d-49ae-95bb-bbb65c392808/scratchpad/scripts/`, IfcOpenShell 0.9.0.post1, ezdxf 1.4.5, PyMuPDF 2.1, on this Mac with 14 cores):

| id | Script | Result |
|---|---|---|
| M1 | `qto_check.py` | 1,183 room-area questions on 12 models; 1,150 rooms matched; geometry footprint within 2%: 1,145; Qto NetFloorArea present: 417, all within 2%; no Qto: 733 |
| M2 | PyMuPDF text of `ifc_models/bsc-molio_molio-with-uris_plan-03-grundplan.pdf` | Footer "Målestok 1:100 · snit 1.20 m over etagens niveau · Genereret fra IFC (Molio_with_URIs.ifc, IfcOpenShell IfcConvert 0.9.0)"; all 107 ifc_models PDFs have producer "junction-dataset-builder/0.1" |
| M3 | `agg_check.py` | Storey counts: decomposition 204/207, containment 140/207. Model counts: by_type incl. subtypes 127/136, excl. 116/136, IFC2X3 typed terminals 8. Wall net volume Qto 69/69, geometry 45/69. Wall net side area Qto 32/32. Total room area geometry 38/40. Wall length Qto 23/32, Molio Qto in mm |
| M4 | `iter_time.py` | Molio: 579 IfcStair, 564 aggregated in another IfcStair. Geometry iterator: clinic 13.0 MB 1.9 s (3,258 shapes); Molio 73.9 MB 12.1 s (3,860 shapes); open 0.14 s and 0.74 s |
| M5 | overlap script against HF `ifc-bench-v2.csv` | 820/820 questions and answers match; 399 test, 421 train; 206 missing on samuel_macalister_sample_house, schependomlaan, wbdg_office |
| M6 | file and question counts | Question targets png 85,514, pdf 40,342, ifc 1,188. 271 DWG (AC1027 244, AC1021 16, AC1015 7, AC1018 4), 1,049 DXF |
| M7 | `pdfscan.py`, `vpscan.py` | 1,825 PDFs; OCG in 14 (all opening_design); /VP in 11; scale text in all ifc_models and swiss PDFs; swiss area answers equal to a printed label: 1,266/12,016 |

## Verification

Date: 2026-11-13. Checker: independent fact-check agent. Method: pages fetched with curl (the web fetch tool was rate limited), text extracted and the quotes searched.

- Sources opened: 19 of 19 (S1-S17, S20, S21). S15 counts both its pages.
- Result: 14 confirmed, 1 confirmed with a small note on authors (S4), 2 partly (S6, S15), 1 corrected (S2). S3, S20 and S21 are confirmed. No source was NOT FOUND. No finding needed an **UNVERIFIED** mark because of a missing source.
- Not checked: the local measurements M1-M7, and the counts that need the local dataset (399 test, 421 train, 206 missing). The 820/820 overlap was not re-run.

Corrections:

1. S2: the version "v2.0.3" is not on the dataset card. The card says 1,027 pairs. The CSV has 1,026 data rows plus a header line.
2. S6: Claude Opus 5.5 is first overall (73.7) and first in Drawings & documents (70.2). Claude Opus 5 is first on the BIM understanding axis, which holds IFC-Bench-V2. The row said only "Opus 5 ranked first". GPT-6.1 Sol has 70.2 overall and 66.3 on Drawings & documents.
3. S6: "20 models" and "scores only in an image" are not in the page text. They are marked not confirmed.
4. S4: the paper has five authors (Lamsal, Zlatanova, Xu, Sun, Shen), v1 dated 2026-05-13, v3 dated 2026-10-21.
5. S17: the GitHub API shows NOASSERTION as the licence for pdfium-render. The Cargo.toml line "MIT OR Apache-2.0" is correct.
6. S21 and S20 were marked UNVERIFIED in the text. Both pages exist and match. The "80%" is on the S21 page. The rows keep their other limits (S20 result not read).
