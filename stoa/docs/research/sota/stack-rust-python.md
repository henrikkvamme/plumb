# Engineering stack: Rust core or Python, for a 34-hour build

Track: the engineering stack. Date: 2026-11-13. Author: research agent for the Stoa lead.

How to read the labels:

- MEASURED: I ran it on this Mac (14 cores, cargo 1.94.1, uv 0.13) on the local dataset today.
- READ: an exact statement in a source I opened. The id points to the Sources table.
- ESTIMATE: my judgement. Not measured.

Method note. WebSearch and WebFetch were blocked for this session by a usage limit. I fetched every source with
`curl` directly: arXiv API and arXiv HTML, raw GitHub READMEs, the crates.io API and the PyPI JSON API. I opened
each source that I cite. The search was narrower than a web search: I found papers through the arXiv API, and
libraries through the registries. Claims that I could not open are in "Open questions" and are marked unverified.

## Findings that change decisions

1. **Rust buys no inference-cost points.** CPU time per question in Python is milliseconds. MEASURED: PyMuPDF
   `get_drawings` plus words on 100 Swiss PDFs took 1.00 s in total (10 ms per page). pypdfium2 object walk plus
   text took 0.21 s for 100 pages. ezdxf `recover.readfile` plus a full modelspace walk took 10.06 s for 300 Swiss
   DXFs (34 ms per file). The Rust `dxf` crate took 2.41 s for the same 300 files, with process start. The cost
   criterion is driven by LLM and VLM calls, not by 30 ms of parsing. `ort` is a wrapper for the same ONNX Runtime
   that Python `onnxruntime` uses [S5], so model execution speed is the same in both. (S5, local measurement)
2. **The Rust DXF crate silently drops data that we need.** MEASURED: all 300 sampled `swiss_dwellings` DXFs
   (AC1027) contain `HATCH` entities (ezdxf). `dxf` 0.6.2 returned no `HATCH` entity and no error for the same
   files. In its spec, `HATCH` is a commented-out block with `TODO MinVersion="R14"` [S6]. A silent drop is the worst
   failure for a harness: it produces a wrong number with no signal. ezdxf read all 309 local DXFs. (S6)
3. **Coding agents are measurably weaker in Rust repositories.** Multi-SWE-bench, Claude-3.7-Sonnet with
   MopenHands: Python 52.20%, Rust 15.90% resolved [S1]. The repositories differ, so this is not a controlled
   comparison. Rust-SWE-bench: the best baseline agent resolved 21.2%, the authors' own RustForger 28.6%, and "complying with Rust's strict type and trait
   semantics" is one of the two main limits [S2]. A Codex CLI port from Rust to Python reached near-parity (73.8% vs
   70.0% on 80 SWE-bench Verified tasks; on Terminal-Bench Python 42.5% vs Rust 47.5%) with "a 15.9x code reduction" [S3]. (S1, S2, S3)
4. **The defect-rate evidence for Rust is against C++, not Python.** Google reports "a 4x lower rollback rate" and
   "25% less time in code review" for Rust changes in Android [S4]. The baseline is C++. I found no 2025-2026 study
   that compares defect rates of Rust and typed Python. Do not use the Google figures to argue Rust over Python. (S4)
5. **The repository rule already decides the service layer.** `AGENTS.md` says every app with a UI or an HTTP API
   is made from the TypeScript starter, and work that needs Python goes in `<name>/py/`. Rust is not in the rule.
   A Rust core adds a third language to a TypeScript app with a Python sidecar. ESTIMATE: 3 to 6 hours of extra
   build and boundary work over the weekend. (repo rule, READ in `AGENTS.md`)
6. **Python file tooling is far ahead on IFC and DWG.** IfcOpenShell 0.9.0.post1 opened 29 of 30 `ifc_bench` models
   (IFC2X3, IFC4, IFC4X3) in 14.4 s total (MEASURED). The one failure is a syntax error in `dental_clinic_mep.ifc`.
   `ifc_rs` is alpha and "work in progress" [S8]. No Rust DWG reader exists; LibreDWG is GPL-3.0 C, and Homebrew
   ships 0.14 [S9]. The dataset holds 271 DWG and 48 IFC files in `opening_design`, and 563 IFC files elsewhere
   (MEASURED). (S8, S9)
7. **ifc-lite is the one Rust project worth using, and we use it from TypeScript.** It is a Rust core compiled to
   WASM with npm packages and a WebGPU viewer, "verified element-by-element against IfcOpenShell" [S7]. It runs in
   the starter app in the browser. Use it for the "verify in seconds" view: highlight the IFC elements behind each
   count. It also has a Python wheel `ifclite-geom` 4.15.0 (MPL-2.0). It moves fast (crate 28.2.0). (S7)
8. **Rust compile cost is small for a small crate, but real.** MEASURED on a probe crate (dxf, geo, i_overlay, lopdf,
   image, imageproc, serde): clean release build 37.6 s, clean debug build 15.7 s, incremental rebuild 0.4 to 0.7 s.
   The Rust survey: "55% of respondents have to wait more than ten seconds for a rebuild" [S10]. Each new crate
   that a coding agent adds costs a clean build of its tree. (S10, local measurement)
9. **Type safety does not catch the harness errors that matter most.** Unit mix-ups (m2 vs ft2), silent `None`
   answers, cache keys and non-determinism need design, not a language. A tagged answer type with an explicit
   `Abstain` variant and a `Unit` enum gets most of the gain in Python with pyright strict and msgspec or pydantic.
   Cache keys and determinism need property tests and a replay check in both languages. (ESTIMATE, see Landscape)
10. **Detector licence: prefer RF-DETR over Ultralytics for anything Stoa may reuse.** RF-DETR N/S/M/L are Apache
    2.0; YOLOv8, YOLO11 and YOLO26 are AGPL-3.0 [S11]. Both run through ONNX in Rust (`usls` lists RT-DETR v1/v2/v4,
    RF-DETR and YOLO5 to YOLO26 [S12]) and in Python. (S11, S12)

## Landscape

### Registry versions (MEASURED from crates.io and PyPI on 2026-11-13)

| area | Rust crate | version, date | licence | state for us |
|---|---|---|---|---|
| geometry types | geo-types | 0.7.20, 2026-08-02 | MIT/Apache-2.0 | mature |
| geometry algorithms | geo | 0.33.1, 2026-04-20 | MIT/Apache-2.0 | mature; area, contains, simplify |
| polygon booleans | i_overlay | 9.1.0, 2026-10-14 | MIT/Apache-2.0 | mature, used by geo |
| robust predicates | robust | 1.2.0, 2025-05-10 | MIT/Apache-2.0 | mature |
| curves | kurbo | 0.13.1, 2026-05-13 | Apache-2.0/MIT | mature (Linebender) |
| tessellation | lyon | 1.0.19, 2026-03-08 | MIT/Apache-2.0 | mature, not needed |
| PDF (PDFium) | pdfium-render | 0.9.5, 2026-11-01 | MIT/Apache-2.0 | needs a PDFium binary at run time [S13] |
| PDF (edit) | lopdf | 0.47.0, 2026-11-04 | MIT | low level, no rendering |
| PDF | pdf (pdf-rs) | 0.10.0, 2026-03-02 | MIT | rendering in a separate crate |
| PDF (render) | hayro | 0.9.0, 2026-11-02 | Apache-2.0/MIT | read-only; robustness "still needs work" [S14] |
| PDF (MuPDF) | mupdf | 0.8.0, 2026-06-22 | AGPL-3.0 | works, AGPL |
| DXF | dxf | 0.6.2, 2026-10-03 | MIT | no HATCH, no block explode (MEASURED) |
| DWG | none | - | - | LibreDWG C, GPL-3.0, via CLI |
| IFC | ifc_rs | 0.1.0-alpha.9, 2024-12-04 | MIT | alpha, subset of IFC4 [S8] |
| IFC | ifc-lite-core | 28.2.0, 2026-11-02 | MPL-2.0 | usable; WASM and npm first [S7] |
| raster | image / imageproc | 0.25.10 / 0.27.0 | MIT/Apache-2.0, MIT | mature |
| SVG render | resvg / tiny-skia | 0.50.0 / 0.12.0 | Apache-2.0/MIT, BSD-3 | mature |
| inference | ort | 2.0.0-rc.15, 2026-10-19 | MIT/Apache-2.0 | still a release candidate |
| inference | candle-core | 0.11.1, 2026-10-31 | MIT/Apache-2.0 | YOLOv8, Moondream, BLIP, TrOCR examples [S15] |
| inference | burn | 0.22.1, 2026-10-20 | MIT/Apache-2.0 | ONNX import through burn-onnx [S16] |
| inference | tract-onnx | 0.23.10, 2026-11-05 | MIT/Apache-2.0 | pure Rust ONNX/NNEF [S17] |
| model zoo on ort | usls | 0.1.11, 2026-01-10 | MIT | RT-DETR, RF-DETR, YOLO, Florence2, SmolVLM, FastVLM [S12] |
| interop | pyo3 / maturin | 0.30.1 / 1.16.0 | MIT/Apache-2.0 | mature |
| tests | cargo-nextest / insta / proptest / criterion | 0.9.152 / 1.49.0 / 1.12.0 / 0.8.2 | permissive | mature |

| area | Python package | version, date | licence |
|---|---|---|---|
| DXF | ezdxf | 1.4.5, 2026-10-16 | MIT (PyPI classifier; licence field empty) |
| IFC | ifcopenshell | 0.9.0.post1, 2026-10-15 | LGPL-3.0-or-later |
| IFC (Rust core) | ifc-lite / ifclite-geom | 0.4.0 / 4.15.0 | MPL-2.0 |
| PDF | pymupdf | 2.1, 2026-11-02 | AGPL-3.0 or commercial |
| PDF | pypdfium2 | 5.15.2, 2026-11-09 | BSD-3-Clause, Apache-2.0 |
| geometry | shapely | 2.2.0, 2026-10-07 | BSD-3-Clause |
| detector | rfdetr | 1.12.1, 2026-11-12 | Apache-2.0 (N/S/M/L); PML 1.0 for extra sizes [S11] |
| detector | ultralytics | 8.4.212, 2026-11-13 | AGPL-3.0 |
| inference | onnxruntime | 1.32.0, 2026-11-13 | MIT |
| types | pyright / ty | 1.1.414 / 0.0.104 | MIT / MIT; ty "is currently in beta" [S18] |
| models | pydantic / msgspec | 2.14.3 / 0.22.0 | MIT / BSD-3 |
| tests | pytest-xdist / hypothesis / syrupy / inline-snapshot | 3.8.0 / 6.170.15 / 7.0.0 / 0.36.2 | MIT / MPL-2.0 / MIT / MIT |
| lint, env | ruff / uv | 0.17.5 / 0.13.8 | MIT / MIT-Apache |

### Local parser results (MEASURED)

| test | Rust | Python |
|---|---|---|
| 300 Swiss DXF, parse and walk all entities | `dxf` 0.6.2: 300/300, 2.41 s, HATCH missing | ezdxf 1.4.5: 300/300, 10.06 s, HATCH present in 300/300 |
| 9 other DXFs in `opening_design` (R12 and R2000, up to 293,482 3DFACE) | 9/9, largest 1.07 s | 9/9, largest 8.18 s |
| 30 `ifc_bench` IFC files, open and query types | not tried (no mature crate) | IfcOpenShell 0.9: 29/30, 14.4 s, max 3.17 s |
| 100 Swiss PDFs, vectors and words | not tried | PyMuPDF 1.00 s; pypdfium2 0.21 s; pypdfium2 render at 2x, 20 pages 0.80 s |

### Where type safety helps the harness

| harness error | Rust | strict Python (pyright strict, msgspec) | what actually prevents it |
|---|---|---|---|
| m2 vs ft2, mm vs m | newtypes or `uom` stop mixing at compile time | `Literal`/`Enum` unit field; `NewType` is weaker | one `Quantity(value, unit)` type, convert once at parse, and a unit test per source with a known area |
| silent None answer | `Option` must be handled | pyright strict flags optional access | an `Answer = Value | Abstain(reason)` union; the scorer counts abstains apart from errors |
| wrong answer type for the question type | enums with exhaustive `match` | `match` plus `assert_never` checks exhaustiveness | same in both |
| cache key bug | not caught | not caught | key = sha256(file bytes) + normalized question + pipeline version; a property test that changes each part and checks a cache miss |
| non-determinism | `HashMap` order is random per run (std default, background knowledge) | set order of strings depends on `PYTHONHASHSEED` (background knowledge) | sorted outputs, fixed seeds, temperature 0, and a replay test that runs the harness twice and diffs the results |
| float sum order changes the 2% verdict | not caught | not caught | sum areas in a stable order; compare with tolerance in one place |
| silent parser drop (HATCH case) | not caught | not caught | count entity types per file and alert on unknown or missing types |

ESTIMATE: of the seven errors, the type system catches two to three in either language. The other four need tests.

### Agent productivity evidence

| source | finding | caveat |
|---|---|---|
| Multi-SWE-bench [S1] | MopenHands with Claude-3.7-Sonnet: Python 52.20%, Rust 15.90%; "Go and Rust ... falling behind Java" | different repositories per language |
| Rust-SWE-bench [S2] | best baseline agent 21.2%, RustForger 28.6% | no Python control |
| Codex Rust to Python port [S3] | near-parity on agent benchmarks (SWE-bench Verified 73.8% vs 70.0%, Terminal-Bench 42.5% vs 47.5%), 15.9x less code in Python | one system, authors' own port |
| Generative compilation [S19] | Rust strictness "makes generation more difficult"; feedback during generation helps | research method, not in agent tools today |
| Rust compiler survey 2025 [S10] | 55% wait more than 10 s for a rebuild | human developers, not agents |

## What we can use this weekend

Recommendation per component.

| component | choice | why | effort (ESTIMATE) |
|---|---|---|---|
| scorer and harness | Python 3.12+, msgspec `Struct` records with a `Unit` enum and an `Abstain` variant, pyright strict, ruff, pytest + pytest-xdist, hypothesis for metamorphic tests (rotate, scale, translate a DXF and check the answer), inline-snapshot for per-template results | agents write it fastest; the data science tools are there | 3 to 4 h |
| geometry solvers | Python: shapely 2.2 (GEOS) + numpy; ezdxf `virtual_entities()` for blocks | MEASURED speed is enough; no boundary | in the solver budget |
| file parsers | ezdxf 1.4.5; IfcOpenShell 0.9 (LGPL); pypdfium2 for render and objects, PyMuPDF for `get_drawings` (AGPL, fine for the hackathon); LibreDWG `dwg2dxf` (GPL) as a subprocess, `brew install libredwg` | all read our files today | 1 h setup |
| model training | Python on Verda: `pip install rfdetr` (Apache-2.0) or Ultralytics (AGPL) | training is Python only in practice | per the CV track |
| model inference | export ONNX, run with `onnxruntime` 1.32 in the Python service | same engine as Rust `ort`, no second build | 1 h |
| service layer and UI | the starter TypeScript app (repo rule); `@ifc-lite/*` npm for a 3D evidence view of IFC answers | the rule; ifc-lite gives a verifiable view | 3 to 5 h for the IFC viewer |
| hot loops | only if a profile shows one: a PyO3 + maturin extension (`maturin develop` in the uv env) | none found so far | 2 to 4 h if needed |

Commands:

```sh
uv add ezdxf==1.4.5 ifcopenshell==0.9.0.post1 pypdfium2==5.15.2 pymupdf==2.1 shapely==2.2.0 msgspec==0.22.0 onnxruntime==1.32.0
uv add --dev pyright==1.1.414 ruff==0.17.5 pytest pytest-xdist hypothesis inline-snapshot
brew install libredwg   # dwg2dxf, GPL-3.0, CLI only
```

What I would NOT write in Rust this weekend: the DXF parser (HATCH gap), the IFC layer (alpha crates or a fast-moving
WASM-first project), the DWG path (none exists), the PDF layer (bindings to the same PDFium that pypdfium2 bundles),
model training, the LLM and agent loop, and the scorer. A pure Rust CLI that calls ONNX models is buildable (`ort` +
`usls`), but it saves milliseconds on a cost dominated by model calls, and it costs agent hours.

When Rust would pay: a later production version for Stoa, a single static binary, or a WASM evidence viewer.
ifc-lite already covers the viewer.

## What does not work

- `dxf` 0.6.2 on the Swiss DXFs: drops every HATCH entity without an error (MEASURED). No block explode helper in
  the crate source (MEASURED: no `explode`, `virtual` or `transform` function in `src/`).
- `ifc_rs`: "work in progress", "A parser for a subset of the IFC4 STEP format" [S8]. Not usable for IFC2X3 files,
  which are 15 of the 30 `ifc_bench` models (MEASURED).
- Rust DWG: no crate on crates.io named `libredwg` (MEASURED: 404). LibreDWG itself: "some very advanced R2010+
  objects fail to read and are skipped over" [S9].
- `hayro`: "there are still many ways to trigger timeouts and OOM errors" [S14]. A hidden set with tricky PDFs is the
  wrong place for it.
- `ort` 2.0 is still a release candidate (rc.15, MEASURED); APIs can still change.
- ty is beta [S18]. Use pyright strict as the gate; ty can run beside it for speed.
- Using Google's Rust figures to argue against Python: the baseline is C++ [S4].

## Open questions

- No controlled study found (2025-2026) of coding-agent success on the same task in Rust and Python. Search was via
  the arXiv API only; a web search may find one. Unverified.
- No study found of defect rates of Rust vs typed Python. The often-cited "To Type or Not to Type" (ICSE 2017,
  JavaScript, about 15% of bugs detectable by types) was not opened in this session. Unverified.
- tract and burn operator coverage for RT-DETR and RF-DETR ONNX exports: not tested. `usls` claims support on ort only.
- ifc-lite Rust crate API for quantities (`IfcElementQuantity`, Qto sets): not tested. Its npm SDK has `byType().count()`.
- Whether IfcOpenShell 0.9 parses `dental_clinic_mep.ifc` with a lenient option. ifc-lite may parse it; not tested.

## Check of the prior research

- "swiss_dwellings: closed polylines and hatches in DXF, ezdxf + shapely, no model needed": confirmed for the
  tooling. MEASURED: AC1027, LWPOLYLINE, TEXT, ARC, HATCH in 300/300 files. It makes the Rust DXF crate a bad fit.
- "PyMuPDF (AGPL-3.0 or commercial licence), pypdfium2 permissive alternative": confirmed by PyPI metadata.
- "LibreDWG GPL-3.0, Homebrew ships 0.14": confirmed (`brew info libredwg`: stable 0.14) and README [S9]. The
  "99% of DWG" figure was not checked.
- "Ultralytics AGPL-3.0; RF-DETR Apache as a permissive alternative": confirmed [S11], with one correction: RF-DETR
  Atto, Femto, Pico, XL and 2XL are under PML 1.0, not Apache.
- The prior research does not discuss Rust at all. Nothing to correct there.

## Sources

| id | URL | title | date | claim it supports | exact supporting quote | check |
|---|---|---|---|---|---|---|
| S1 | https://arxiv.org/abs/2504.02605 (HTML v1, Table 4) | Multi-SWE-bench: A Multilingual Benchmark for Issue Resolving (Zan et al., ByteDance) | 2025-04-03 | agents resolve fewer Rust issues | "Go and Rust exhibit inconsistent performance across models, generally outperforming TS and JS but falling behind Java." Table 4, MopenHands Claude-3.7-Sonnet: Python 52.20, Rust 15.90 | confirmed (Table 4 columns: Python, Java, TS, JS, Go, Rust, ...; MopenHands Claude-3.7-Sonnet Python 52.20, Rust 15.90; Python is the Python split of Multi-SWE-bench) |
| S2 | https://arxiv.org/abs/2602.22764 | Evaluating and Improving Automated Repository-Level Rust Issue Resolution with LLM-based Agents (Xiang et al.) | 2026-02-26 | Rust type and trait rules limit agents | "they are limited by two primary challenges: comprehending repository-wide code structure and complying with Rust's strict type and trait semantics" | confirmed (21.2% is the best baseline; 28.6% is RustForger) |
| S3 | https://arxiv.org/abs/2604.11518 | From Translation to Superset: Benchmark-Driven Evolution of a Production AI Agent from Rust to Python (Wang, Sengupta) | 2026-04-13 | Python port at parity, much less code | "the Python port resolves 59/80 SWE-bench Verified tasks (73.8%) versus Rust's 56/80 (70.0%)"; "Python's expressiveness yields a 15.9x code reduction with negligible performance cost" | corrected (abstract says "near-parity"; Terminal-Bench Python 42.5% vs Rust 47.5% was omitted; quote in report is a shortened form of the abstract) |
| S4 | https://security.googleblog.com/2025/11/rust-in-android-move-fast-fix-things.html (301 redirect to https://blog.google/security/rust-in-android-move-fast-fix-things/) | Rust in Android: move fast and fix things (Google Security Blog) | 2025-11-13 | Rust defect evidence is against C++ | "With Rust changes having a 4x lower rollback rate and spending 25% less time in code review, the safer path is now also the faster one." | confirmed (author Jeff Vander Stoep; date 2025-11-13; URL redirects to blog.google; Rust vs C++ baseline) |
| S5 | https://github.com/pykeio/ort (README) | ort | read 2026-11-13; crate 2.0.0-rc.15, 2026-10-19 | ort runs the same engine as Python onnxruntime | "`ort` is primarily a wrapper for Microsoft's ONNX Runtime library, but offers support for other pure-Rust runtimes." | confirmed |
| S6 | https://github.com/ixmilia/dxf-rs (README; spec/EntitiesSpec.xml in crate 0.6.2) | dxf-rs | crate 0.6.2, 2026-10-03 | no HATCH support | spec file: "HATCH" inside an XML comment, then "<!-- TODO MinVersion="R14" -->" | confirmed (README has no HATCH; the spec file in crate 0.6.2 has the commented HATCH block and TODO; licence MIT) |
| S7 | https://github.com/LTplus-AG/ifc-lite (README) | IFClite (LTplus AG) | read 2026-11-13; crates 28.2.0, 2026-11-02 | Rust core, WASM, npm, checked against IfcOpenShell; Python wheel | "A Rust core compiled to WASM does the parsing and geometry ... verified element-by-element against IfcOpenShell across the public benchmark corpus." "`pip install ifclite-geom` runs the geometry kernel in-process" | confirmed (also: WebGPU renderer, npm packages, ifclite-geom 4.15.0 MPL-2.0 on PyPI) |
| S8 | https://github.com/MetabuildDev/ifc_rs (README) | ifc_rs | crate 0.1.0-alpha.9, 2024-12-04 | Rust IFC parser is alpha | "This crate is still work in progress. The API will most likely change a lot in the future." "A parser for a subset of the IFC4 STEP format" | confirmed |
| S9 | https://github.com/LibreDWG/libredwg (README) | GNU LibreDWG | read 2026-11-13 | DWG reader is GPL C, some objects skipped | "licensed under the terms of the GNU General Public License version 3"; "it can read all DWG versions, just some very advanced R2010+ objects fail to read and are skipped over" | confirmed (README path is /README on master, not README.md; GPL-3.0 and R2010+ sentence present; the "Homebrew 0.14" and "99%" claims were not checked online) |
| S10 | https://blog.rust-lang.org/2025/09/10/rust-compiler-performance-survey-2025-results/ | Rust compiler performance survey 2025 results (Jakub Beránek, compiler performance WG) | 2025-09-10 | compile wait is a real cost | "the fact that 55% of respondents have to wait more than ten seconds for a rebuild is far from ideal." | confirmed (author Jakub Beránek, 2025-09-10) |
| S11 | https://github.com/roboflow/rf-detr (README) | RF-DETR (Roboflow) | read 2026-11-13; PyPI 1.12.1, 2026-11-12 | licences of RF-DETR and Ultralytics | "RF-DETR Nano, Small, Medium and Large detection ... are released under the Apache 2.0 license"; "YOLOv8, YOLO11 and YOLO26 are released under AGPL-3.0." | confirmed (N/S/M/L Apache 2.0; Atto, Femto, Pico, XL, 2XL PML 1.0; YOLOv8/11/26 AGPL-3.0; PyPI rfdetr 1.12.1 Apache-2.0) |
| S12 | https://github.com/jamjamjon/usls (README) | usls | crate 0.1.11, 2026-02-05 | Rust ONNX zoo has DETR, YOLO, small VLMs | model table rows: "RT-DETRv1", "RT-DETRv2", "RT-DETRv4", "RF-DETR" (Object Detection), "Florence2", "SmolVLM", "FastVLM" | confirmed (usls 0.1.11 dated 2026-01-10, not 2026-02-05; crates.io now also has 0.2.0-alpha.3) |
| S13 | https://github.com/ajrcarey/pdfium-render (README) | pdfium-render | crate 0.9.5, 2026-11-01 | needs a PDFium library at run time | "`pdfium-render` binds to a Pdfium library at run-time, allowing for flexible selection of system-provided or bundled Pdfium libraries" | confirmed (crate 0.9.5, 2026-11-01) |
| S14 | https://github.com/LaurenzV/hayro (README) | hayro | crate 0.9.0, 2026-11-02 | robustness gaps | "there are still many ways to trigger timeouts and OOM errors." | confirmed (crate 0.9.0, 2026-11-02) |
| S15 | https://github.com/huggingface/candle (README) | candle (Hugging Face) | crate 0.11.1, 2026-10-31 | candle models | example list: "yolo-v3 and yolo-v8: object detection and pose", "Moondream: tiny computer-vision model", "TrOCR: a transformer OCR model" | confirmed (quote spans two README lines; candle-core 0.11.1, 2026-10-31) |
| S16 | https://github.com/tracel-ai/burn (README) | Burn (Tracel AI) | crate 0.22.1, 2026-11-09 | ONNX import into Burn | "burn-onnx ... Import ONNX models into Burn as native Rust code" | corrected (quote confirmed; burn 0.22.1 is dated 2026-10-20, not 2026-11-09; 0.23.0-pre.2 also exists) |
| S17 | https://github.com/sonos/tract (README) | tract (Sonos) | crate 0.23.10, 2026-11-05 | pure Rust ONNX runtime | "tract loads ONNX and NNEF models, optimises them, and runs them anywhere" | confirmed (tract-onnx 0.23.10, 2026-11-05) |
| S18 | https://github.com/astral-sh/ty (README) | ty (Astral) | PyPI 0.0.104, 2026-11-13 | ty not stable | "ty is currently in beta." | confirmed (PyPI ty 0.0.104, 2026-11-13) |
| S19 | https://arxiv.org/abs/2607.13921 | Generative Compilation: On-the-Fly Compiler Feedback as AI Generates Code (Mündler-Sasahara, Venev, Song, Vechev, He) | 2026-07-15 | Rust strictness makes LLM generation harder | "Languages with rich static semantics, such as Rust, provide stronger guarantees for AI-generated code, but their strictness makes generation more difficult." | corrected (title, id, date and quote confirmed; fifth author Jingxuan He was missing) |
| S20 | https://crates.io/api/v1/crates/<name> and https://pypi.org/pypi/<name>/json | crates.io and PyPI registry APIs | queried 2026-11-13 | all versions, dates and licences in the Landscape tables | registry fields `max_stable_version`, `created_at`, `license` | confirmed (all crates.io and PyPI versions, dates and licences re-queried; differences: burn, usls dates, cargo-nextest now 0.9.152, ezdxf licence is in the PyPI classifier) |

## Verification

Date: 2026-11-13. Sources opened: 20 of 20 (S1 to S19 by their pages, S20 by the registry APIs for 40 crates and 20 Python packages). Result: 17 confirmed, 3 corrected (S3, S16, S19), 0 partly, 0 not found. Some confirmed rows also carry a small fix to a date or note (S4, S9, S12, S20). No finding is marked UNVERIFIED, because every source was found.

Corrections:

- S3 and finding 3: the abstract says "near-parity", not parity. Terminal-Bench was Python 42.5% vs Rust 47.5%. The text now says this.
- Finding 3: in Rust-SWE-bench the best baseline agent resolved 21.2%. The 28.6% is the authors' own RustForger. The text said "the best agent resolved 28.6%".
- S19: the author list had four names. The paper has five (Jingxuan He is the fifth).
- burn 0.22.1 date: 2026-10-20 (the report said 2026-11-09). S16 and the Landscape table are corrected.
- usls 0.1.11 date: 2026-01-10 (the report said 2026-02-05). The Landscape table is corrected. crates.io now also lists 0.2.0-alpha.3.
- cargo-nextest: 0.9.152 (published 2026-11-13), not 0.9.151.
- ezdxf licence: MIT is in the PyPI classifier. Only the licence field is empty.
- S4: the URL redirects (301) to blog.google. Date is 2025-11-13.

Notes, not corrections:

- The MEASURED claims (parse times, HATCH counts, compile times, IfcOpenShell 29 of 30) were not re-run. They are local results of the research agent. The dxf 0.6.2 spec (HATCH commented out, TODO MinVersion R14), the licence MIT, and the absence of `explode` or `virtual` in `src/` were checked in the crate source.
- Not checked online: the "Homebrew ships 0.14" claim for libredwg and the "99% of DWG" figure.
- S1 quote: the HTML text of the paper matches the quote. The Python column of Table 4 is the Python split of Multi-SWE-bench.
- WebFetch was out of quota, so the checks used `curl` on the same URLs (arXiv API and HTML, raw GitHub READMEs, registry APIs).
