# Document AI for drawing sheets

Track: text, tables, legends, title blocks, schedules, dimensions and scales on drawing sheets, also on historic
scans in many languages. Written 2026-11-13.

Labels used in this file:

- **MEASURED**: we ran it on our local dataset in this session. The method is in "Local measurements" below.
- **SOURCE**: we opened the source and copied the figure. The source id is in brackets.
- **ESTIMATE**: our own reasoning or arithmetic. Not measured.
- **UNVERIFIED**: seen only in a search result snippet. We could not open the source (the web tools hit a
  usage limit late in the session).

## Findings that change decisions

1. **MEASURED: schedule questions need a rotation-aware table rebuild from the PDF text layer, not OCR and not a
   VLM.** On `A-801 - Door and Finish Schedules & Wall Types.pdf`, 1,037 of 1,044 text lines run in direction
   (0,-1), so the schedule is rotated 90 degrees. PyMuPDF `find_tables()` finds 0 tables with the "lines"
   strategy and one junk 225x53 table with the "text" strategy. A naive count of type tokens on the sheet
   matches the ground truth for 3 of 6 door types (B1: 33 vs 9, B2: 16 vs 10, C1: 29 vs 1), because the same
   codes appear in the finish schedule and the legends. When we count only the tokens in the TYPE column band
   of the door schedule, all 6 of 6 match (A1 14, A2 1, B1 9, B2 10, B3 1, C1 1). Cost: $0, milliseconds. We
   chose the band by hand, so this proves feasibility, not a general algorithm. [M1]
2. **MEASURED: scale notes are in the text layer for most vector sheets.** 587 of 678 opening_design PDFs have
   a text layer, and 437 of 678 contain a scale string that our regex parses (`3/16" = 1'-0"`, `1:100`).
   Sheets carry several scales, one per view. 40 of 40 sampled swiss_dwellings PDFs carry `Massstab 1:200`
   or `1:100`. 40 of 40 sampled ifc_models PDFs carry `1:100` or `1:200`. The historic sources are JPEG only
   (habs 1,506, finna 1,800, europeana 1,085, wikimedia 2,175 JPEG plus 135 SVG). So "what is the scale"
   is a regex task on vector sheets, a per-view task when a sheet has several scales, and an OCR or abstain
   task on scans. [M2, M3]
3. **SOURCE: sub-1B document models now beat frontier general VLMs at page parsing.** OmniDocBench v1.6
   overall: PaddleOCR-VL-1.6 (0.9B) 96.33, GLM-OCR (0.9B) 95.22, Gemini 3 Pro 92.91, Qwen3-VL-235B 89.78,
   GPT-5.2 86.59. PaddleOCR-VL-1.6 is Apache-2.0, GLM-OCR is MIT. For raster text, run a small OCR model on
   a Verda GPU or a CPU, not a Claude call. This moves the cost criterion. [S1, S2, S4]
4. **SOURCE: skew and rotation split the small models.** Real5-OmniDocBench "Skew" column: PaddleOCR-VL-1.6
   92.66, Gemini 3 Pro 89.45, MinerU2.5 75.24, DeepSeek-OCR 2 61.28. Drawings have rotated text, so
   PaddleOCR-VL is the default raster reader, and DeepSeek-OCR 2 is not. [S1]
5. **SOURCE: old scans are still unsolved for every OCR model.** olmOCR-bench "Old scans": Chandra 2 51.1,
   dots.mocr 48.2, dots.ocr 40.9 (base pages score 99+). CHURRO, trained on historic pages, reaches 82.3%
   (printed) and 70.1% (handwritten) normalized Levenshtein similarity. Text answers on habs, finna,
   europeana and wikimedia scans must carry low confidence or abstain. This matters most for the 60% of
   drawings with no public questions. [S5, S6, S7]
6. **SOURCE: VLMs read drawing text well but cannot count symbols.** AECV-Bench (Jan 2026): "OCR and
   text-centric document QA are strongest (up to 0.95 accuracy)", while counting doors and windows "remains
   unsolved (often 0.40-0.55 accuracy)". Send text questions to OCR plus a small model. Send counts to CV or
   geometry. [S8]
7. **SOURCE: frontier VLM schedule extraction is accurate but slow and costly; GPT-4o-class models drop
   rows.** On 20 tables, mostly door and window schedules: Gemini 2.5 Pro 94.2% at 47.4 s/page and
   $58 per 1000 pages, Amazon Textract 82.1%, Azure Layout 81.5%, GPT-4o 38.5% ("Truncated output, dropped
   rows"). This is an industry blog, not peer-reviewed. Use a VLM only as the fallback for raster schedules,
   and run it on a cropped table. [S9]
8. **SOURCE: page-image retrievers lose small drawing text.** ColQwen2.5 caps a page at 768 image patches
   [S10]. ViDoRe V3 (the "ACL 2026" venue is UNVERIFIED) finds that visual retrievers beat text ones on office documents, but "current
   models still struggle with non-textual elements" [S11]. ESTIMATE: on a 36x24 inch sheet, 768 patches
   cannot resolve 2 mm text. For "which sheet in project X" questions, retrieve by sheet number and title
   from the text layer or the title block first. Use a visual retriever only for scans.
9. **SOURCE: licence traps.** Chandra 2 and Surya weights are under modified OpenRAIL-M with funding/revenue caps
   ($2M and $5M) [S5, S12]. CHURRO is under the Qwen research licence [S7]. The ColQwen2.5 backbone is under
   the Qwen research licence [S10]. These are fine for a non-commercial hackathon. Apache-2.0 or MIT
   alternatives: PaddleOCR-VL-1.5/1.6, GLM-OCR, DeepSeek-OCR 2, granite-docling, dots.mocr [S2, S3, S4, S13,
   S14, S15].

## Landscape

### OCR and page parsing models, 2025-2026

All figures are SOURCE unless marked.

| Model | Size | Licence | Released | Key figure | Notes for drawings |
|---|---|---|---|---|---|
| PaddleOCR-VL-1.6 | 0.9B | Apache-2.0 | 2026-05-28 | OmniDocBench v1.6 96.33; Real5 93.19 | Best on skew; layout via PP-DocLayoutV3; tasks ocr, table, chart, formula, spotting, seal [S1, S2] |
| PaddleOCR-VL-1.5 | 0.9B | Apache-2.0 | 2026-01-29 | OmniDocBench v1.5 94.5 | Adds text spotting (line boxes), llama.cpp support since 2026-03-06 [S3] |
| PaddleOCR-VL | 0.9B | Apache-2.0 | 2025-10-16 | "supports 109 languages" | Card names handwriting and historical documents [S16] |
| GLM-OCR | 0.9B | MIT | 2026-01 (HF repo created 2026-01-30) | OmniDocBench v1.5 94.62; 1.86 pages/s PDF | Real5 Skew 85.39 [S4, S1] |
| MinerU2.5-Pro | 1.2B | MinerU licence (Apache-2.0 plus conditions) | 2026-04 | OmniDocBench v1.6 95.75 | Real5 Skew 81.26; CPU tier available [S1, S17] |
| dots.mocr | 3B | MIT | 2026-03 | olmOCR-bench 83.9; MDPBench 80.5 | Also emits SVG from graphics, "yet to achieve the desired level of robustness" [S15] |
| DeepSeek-OCR 2 | 3B | Apache-2.0 | 2026-01 | Real5 73.01; Skew 61.28 | 256 to 1,120 visual tokens per image (ESTIMATE from card formula) [S14, S1] |
| Chandra OCR 2 | not stated | code Apache-2.0, weights OpenRAIL-M, $2M cap | 2026-03 | olmOCR-bench 85.8; 43-language avg 77.8% | "90+ languages", handwriting, forms; 1.44 pages/s on H100 [S5] |
| Surya 2.5 | 689M | code Apache-2.0, weights OpenRAIL-M, $5M cap | 2026 | 91-language internal avg 74.9%; 4.5 pages/s H100 | Tables as HTML; 0.19 pages/s on M4 Max [S12] |
| olmOCR 2 | 7B | "permissive open licenses" | 2025-10-22 | SOTA claim on English olmOCR-Bench | English only; RLVR with unit-test rewards [S18] |
| granite-docling | 258M (0.3B) | Apache-2.0 | 2025-09-17 | FinTabNet TEDS 0.97 | English; other scripts experimental; "not intended for general image understanding" [S13] |
| CHURRO | 3B (Qwen2.5-VL-3B) | qwen-research | 2025-09 (EMNLP 2025: venue not checked) | 82.3% printed, 70.1% handwritten NLS | 46 language clusters, historic pages [S6, S7] |
| PP-OCRv5 | small | Apache-2.0 (repo; licence not on the cited page) | 2025 | rec 0.8401 server; 0.74 s/image GPU, 4.34 s CPU | Classic det+rec with word boxes; page lists 5 text types; handwriting rec 0.58 [S19] |

Speed figures come from different hardware and are not comparable across rows.

### Drawing-specific work

| Work | What | Figure | Source |
|---|---|---|---|
| AECV-Bench (2026-01) | 120 floor plans, 192 drawing QA pairs | OCR/text QA up to 0.95, door/window counts 0.40-0.55 | [S8] |
| Lombardi et al., EC3 2025 | CNN finds title block, GPT-4o extracts metadata, on CAD and historic drawings | No numbers in abstract | [S20] |
| Businessware Tech (2025-08) | 20 schedule tables, 10 mechanical drawings | Gemini 2.5 Pro 94.2% tables; drawings dimension extraction best 79.96% | [S9] |
| eDOCr2, Machines 13(3):254, 2025 (Toro and Tarkian) | Traditional OCR plus image processing for dimensions, feature control frames and information blocks, then Qwen2-VL-7B and GPT-4o to verify (CRAFT not confirmed) | Text recall 93.75%, CER below 1% (abstract, via Crossref) | [S21] |
| Buildings 15(22):4048 (2025-11-10), "A Study on Methods for Parsing Architectural Multi-Modal Data and Extracting Modeling Parameters" | Multi-scale sliding window and geometric features for nested tables; drawings are DXF | Table parameter recall 95.0% doors/windows, 96.7% structure (abstract, via Crossref; MDPI itself returned 403) | [S22] |

### Retrieval

| Model | Licence | Figure | Source |
|---|---|---|---|
| ColQwen2.5-v0.2 | adapters MIT, backbone Qwen research | max 768 image patches per page; 128-dim multi-vector | [S10] |
| ViDoRe V3 benchmark | - | visual beats text retrievers; late interaction and text reranking help; struggle with non-textual elements | [S11] |

## Local measurements

All on the full local dataset, with PyMuPDF (`uv run --with pymupdf`).

- **M1** (A-801 door schedule). `page.get_text('words')` on page 0. Kept words in {A1, A2, B1, B2, B3, C1}. Most
  tokens with x < 700 sit in one band near y = 2500 (rounded to 50). Counts in that band: A1 14, A2 1, B1 9,
  B2 10, B3 1, C1 1. Ground truth from `questions.jsonl`: A1 14, A2 1, B1 9, B2 10, B3 1, C1 1. Naive counts of
  `^TYPE$` lines over the full sheet text: A1 14, A2 1, B1 33, B2 16, B3 1, C1 29. Text line directions:
  (0,-1) 1,037, (-1,0) 7. The page is 3024 x 2160 pt, with 8,950 vector drawings and 8 images.
- **M2** (opening_design scan). All 678 PDFs. Text layer = more than 200 characters. Scale regex:
  `(\d+(?:/\d+)?"\s*=\s*\d+'\s*-?\s*\d*"?)|(\b1\s*:\s*\d{1,4}\b)`. Results: 587 text layer, 91 no text,
  154 contain the word SCALE, 437 contain a scale string. One false hit: `1:12` on a site plan (likely a slope
  or ratio), so the regex needs a context check.
- **M3** (other sources). 40 random PDFs per source, seed 0. swiss_dwellings 40/40 text, 40/40 scale
  (`Massstab`, `1:200`). ifc_models 40/40 text, 40/40 scale. habs, finna, europeana: JPEG only. wikimedia:
  2,175 JPEG and 135 SVG.

## What we can use this weekend

Effort figures are ESTIMATES.

1. **Vector text layer reader (0 model cost).** PyMuPDF `get_text('words')` and `get_text('dict')` (line
   direction). Rotate word boxes to the reading frame, cluster rows and columns, use vector line segments
   (`get_drawings()`) as cell borders, anchor on headers such as "DOOR SCHEDULE", "TYPE", "MARK". Output a
   table with a bounding box per cell for the citation overlay. Licence: PyMuPDF is AGPL-3.0 (known; not
   re-checked this session). Alternative with a permissive licence: pdfplumber (MIT, not re-checked).
   Effort: 4 to 6 h for a general rebuild, plus 2 h of tests on A-801, A700 and A-701.
2. **Scale extractor.** Regex families on the text layer: imperial `a/b" = 1'-0"`, metric `1:N` and
   `1/N`, and the scale word in many languages: scale, Massstab/Maßstab, échelle, scala, mittakaava, skala
   (sv, pl), mõõtkava, κλίμακα, schaal. Attach each scale to the nearest view title. Cross-check with one
   dimension string: measured PDF distance times scale should equal the printed value. Effort: 3 h.
3. **Feet-and-inches parser.** We found no maintained Python library (search only, UNVERIFIED [S23]). Write a
   small grammar: `5'-6 1/2"`, `5' 6"`, `66"`, `5'-0"`, `1/8" = 1'-0"`, metric `mm`, `cm`, `m`. Add
   property tests (format then parse returns the same value). Effort: 1 to 2 h.
4. **Raster OCR: PaddleOCR-VL-1.6** (`PaddlePaddle/PaddleOCR-VL-1.6`, Apache-2.0, 0.9B). Install
   `paddleocr[doc-parser]>=3.4.0` with `paddlepaddle-gpu==3.2.1`, or use transformers v5 for element-level
   recognition and text spotting [S3]. Use the `spotting` task for word boxes on plans and `table` on
   schedule crops. Run batch jobs on a Verda V100 or A100 through `pnpm j gpu`. Effort: 2 to 3 h to a
   working batch job. Fallback: GLM-OCR (MIT, vLLM, SGLang or Ollama) [S4].
5. **Cheap word boxes on CPU: PP-OCRv5** for room labels on CubiCasa PNGs (Finnish codes such as MH, KH, WC).
   0.74 s/image GPU and 4.34 s/image CPU for the server model [S19]. Effort: 1 to 2 h.
6. **Historic scans: CHURRO-3B** (qwen-research licence) for transcription of notes and titles, with low
   confidence on handwriting [S7]. Effort: 2 h. Use only if the hidden set asks text questions on scans.
7. **Sheet retrieval.** First a sheet-number regex (`[A-Z]{1,2}-?\d{3}`) and title words from the file name and
   the title block text, with BM25. ColQwen2.5 only for scanned sets without text [S10]. Effort: 2 h for
   the text path.

### Cheapest reliable pipeline: "read the door schedule on sheet A-801 and count doors of type B3"

1. Resolve the sheet: match `A-801` against file names and title block text (0 model calls).
2. Open the PDF text layer. If more than 200 characters, use the vector path. Else render the schedule region
   at 300 dpi and run PaddleOCR-VL-1.6 `table` on the crop.
3. Find the "DOOR SCHEDULE" header and the TYPE column. Rebuild rows in the rotated frame.
4. Map the question to a filter (column TYPE, value B3) with a regex template. Fall back to Haiku on the column
   headers only, a few hundred tokens.
5. Count matching rows. Return the count, the list of door numbers, and the cell boxes as highlights.
6. Confidence: high when the row count equals the count of door numbers, and the TYPE values all belong to the
   legend. Else lower confidence and show the table.
   ESTIMATE: under $0.001 per question on the vector path. MEASURED: the column-band count gives 6 of 6 on
   A-801 [M1].

### Cheapest reliable pipeline: "what is the scale of this drawing"

1. Vector PDF: regex over the text layer [M2, M3]. One distinct scale: answer it with its box. Several: answer
   per view, or ask which view.
2. Check: one dimension string against the measured vector length. Disagreement lowers confidence.
3. Raster: PP-OCRv5 or PaddleOCR-VL spotting, then the same regex. If no note, look for a scale bar (line with
   ticks and numbers) and compute metres per pixel.
4. Nothing found, or checks disagree: answer "I do not know. Please give the scale or one known dimension."
5. For PNG copies of PDFs (swiss_dwellings, ifc_models): metres per pixel = scale denominator x page width in
   metres / PNG width in pixels. ESTIMATE: this needs the PNG to cover the full page; check one pair first.

## What does not work

- **Naive token counting on the text layer**: 3 of 6 door types wrong on A-801 [M1].
- **PyMuPDF `find_tables()` on Revit schedules**: 0 tables ("lines"), one junk table ("text") [M1].
- **GPT-4o-class table extraction**: 38.5% on schedules, dropped rows, "No improvement from prompt engineering
  or higher DPI" [S9].
- **Majority vote over repeated VLM runs**: "no universal improvement in the F1 metric from increasing run
  counts" [S9].
- **DeepSeek-OCR 2 on skewed pages**: Skew 61.28, Warping 66.53 [S1].
- **Any current OCR on old scans**: Old scans 40.9 to 51.1 on olmOCR-bench [S5, S15].
- **VLMs for door and window counts**: 0.40-0.55 [S8].
- **Low-resolution page embeddings for drawings**: 768-patch cap [S10]; "struggle with non-textual elements" [S11].
- **granite-docling outside English documents**: other scripts experimental; T4 GPUs output only exclamation
  marks in bf16 [S13].

## Open questions

- Does the hidden set ask schedule questions on raster scans? Then the raster table path decides the score,
  and no benchmark covers rotated drawing schedules.
- Does it ask "which sheet" questions across a project? Then retrieval matters. Today each question names one
  file.
- How are free-text answers scored? Exact strings, or a judge?
- Do the PNG copies cover the full PDF page at a fixed DPI? This decides pixel-to-metre conversion.
- How good is PaddleOCR-VL-1.6 on Finnish, Swedish, Estonian, Polish and Greek drawing labels? No public
  per-language figure exists for it [S1, S2]. Measure on CubiCasa labels.
- PP-OCRv6 (claimed by the prior research) is UNVERIFIED.

## Check of the prior research

- CONFIRMED: opening_design questions are schedule lookups on vector PDFs with full text layers, and
  `find_tables()` finds 0 tables because the schedules are rotated [M1]. We add: the "text" strategy returns
  one junk table, and naive token counts fail for 3 of 6 types.
- CONFIRMED: rebuild tables from word boxes, clustered along the rotated axis. We measured 6 of 6 on A-801 type
  counts with a hand-picked band.
- CONFIRMED in part: "Surya 2.5 (689M params): code Apache-2.0, weights modified" [S12]. The cap is $5M
  revenue.
- CONFIRMED: PaddleOCR-VL multilingual 109 languages [S16] (the prior research gave this for PP-OCRv5; the
  source we opened gives it for PaddleOCR-VL).
- UNVERIFIED: "PaddleOCR 3.7.0 (Jun 2026), PP-OCRv6 tiny/small/medium = 1.5M/7.7M/34.5M params, 50 languages".
  We could not open a source.
- UNVERIFIED but plausible: PyMuPDF is AGPL. Name it if Stoa asks about products.
- NOT IN PRIOR RESEARCH: the sub-1B parsers (PaddleOCR-VL-1.6, GLM-OCR) beat frontier VLMs on parsing, the
  old-scan weakness, and the skew results.

## Sources

| id | URL | title | date | claim | exact quote or cell | check |
|---|---|---|---|---|---|---|
| M1 | local | A-801 measurement | 2026-11-13 | column-band count 6/6, naive 3/6 | MEASURED, see "Local measurements" | not re-run (local measurement) |
| M2 | local | opening_design scan | 2026-11-13 | 587/678 text, 437/678 scale | MEASURED | not re-run (local measurement) |
| M3 | local | per-source sample | 2026-11-13 | swiss and ifc_models scale notes; scans JPEG only | MEASURED | not re-run (local measurement) |
| S1 | https://arxiv.org/html/2606.03264v1 | PaddleOCR-VL-1.6 technical report (Zhang et al.) | 2026-06-02 | v1.6 and Real5 tables | "achieves a new state-of-the-art score of 96.33% on OmniDocBench v1.6"; Table 2 Gemini 3 Pro 92.91, GPT-5.2 86.59; Table 3 Skew: DeepSeek-OCR 2 61.28, MinerU2.5 75.24 | confirmed (arXiv 2606.03264, Zhang et al., 2026-06-02; all quoted table figures found in the HTML version: 96.33, 92.91, 86.59, 89.78, 95.22, 95.75, Real5 93.19, Skew 92.66/89.45/75.24/61.28/85.39/81.26) |
| S2 | https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6 | PaddleOCR-VL-1.6 model card (PaddlePaddle) | 2026-05-28 | licence, release | "License: apache-2.0"; "2026.05.28 We release PaddleOCR-VL-1.6" | confirmed (apache-2.0, 2026.05.28, 0.9B) |
| S3 | https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5 | PaddleOCR-VL-1.5 model card | 2026-01-29 | licence, tasks, install | "License: apache-2.0"; "Options: 'ocr' \| 'table' \| 'chart' \| 'formula' \| 'spotting' \| 'seal'" | confirmed (apache-2.0, 2026.01.29, 94.5, spotting option, llama.cpp 2026.03.06, install line) |
| S4 | https://huggingface.co/zai-org/GLM-OCR | GLM-OCR model card (zai-org) | 2026-01 | score, speed, licence | "Achieves a score of 94.62 on OmniDocBench V1.5"; "1.86 pages/second for PDF documents"; "released under the MIT License" | corrected (licence, 94.62 and 1.86 pages/s confirmed; HF repo created 2026-01-30, not 2026-03) |
| S5 | https://github.com/datalab-to/chandra | Chandra OCR 2 (Datalab) | 2026-03 | olmOCR-bench, licence | Chandra 2 85.8; Old Scans 51.1; "free for research, personal use, and startups under $2M funding/revenue" | confirmed (Chandra 2 85.8, Old Scans 51.1, 43-language avg 77.8%, 1.44 pages/s, code Apache-2.0, weights OpenRAIL-M, $2M funding/revenue) |
| S6 | https://arxiv.org/abs/2509.19768 | CHURRO (Semnani et al., Stanford) | 2025-09 | historic OCR accuracy | "CHURRO achieves 82.3% (printed) and 70.1% (handwritten) normalized Levenshtein similarity" | confirmed (arXiv 2509.19768, 2025-09-24, Semnani et al.; 82.3% and 70.1% in abstract) |
| S7 | https://huggingface.co/stanford-oval/churro-3B | churro-3B model card | 2025 | licence, base | "License: qwen-research"; base Qwen2.5-VL-3B-Instruct | confirmed (qwen-research, base Qwen2.5-VL-3B-Instruct) |
| S8 | https://arxiv.org/abs/2601.04819 | AECV-Bench (Kondratenko et al.) | 2026-01-08 | VLM OCR vs counting | "OCR and text-centric document QA are strongest (up to 0.95 accuracy)"; "remains unsolved (often 0.40-0.55 accuracy)" | confirmed (arXiv 2601.04819, 2026-01-08; 120 floor plans, 192 QA pairs; both quotes in abstract) |
| S9 | https://www.businesswaretech.com/blog/benchmarking-ai-on-tables-and-engineering-drawings-results-findings | AI for construction drawings benchmark (Businessware Technologies) | 2025-08 | schedule table extraction | Gemini 2.5 pro "94,2%", "47.4 ± 15.7", "$58"; GPT-4o "38,5%"; "no universal improvement in the F1 metric from increasing run counts" | confirmed (August 2025; Gemini 2.5 pro preview 05-06 94,2% 47.4 s $58; Azure 81,5%; Textract 82,1%; GPT-4o 38,5%; 18 drawings with 20 tables; 10 mechanical drawings; Gemini best 79.96% on drawings; all quotes found). Industry blog, not peer-reviewed |
| S10 | https://huggingface.co/vidore/colqwen2.5-v0.2 | ColQwen2.5 v0.2 model card (vidore) | 2025 | patch cap, licence | "Maximal resolution is set so that 768 image patches are created at most."; backbone "Qwen RESEARCH LICENSE AGREEMENT" | confirmed (768 patches quote; adapters MIT, backbone Qwen research licence) |
| S11 | https://arxiv.org/abs/2601.08620 | ViDoRe V3 (Loison et al.), ACL 2026 (venue unconfirmed) | 2026-01-13 | retrieval findings | "visual retrievers outperform textual ones"; "current models still struggle with non-textual elements, open-ended queries, and fine-grained visual grounding" | partly (arXiv 2601.08620, Loison et al., 2026-01-13, both quotes confirmed; "ACL 2026" is not on the arXiv page and could not be confirmed) |
| S12 | https://github.com/datalab-to/surya | Surya 2.5 (Datalab) | 2026 | size, licence, languages | "Surya is a 689M param document OCR and layout VLM"; "startups under $5M funding/revenue"; "74.9% on an internal benchmark set of 91 languages" | confirmed (689M, code Apache-2.0, weights modified Open Rail-M under $5M funding/revenue, 74.9% on 91 languages, 4.5 pages/s H100, 0.19 pages/s on M4 Max 36 GB) |
| S13 | https://huggingface.co/ibm-granite/granite-docling-258M | granite-docling-258M (IBM) | 2025-09-17 | licence, limits | "License: Apache 2.0"; "Japanese, Arabic and Chinese support (experimental)"; "The model outputs only exclamation marks" | partly (Apache 2.0, release date 2025-09-17, FinTabNet TEDS 0.97, exclamation-marks note, "not intended for general image understanding" confirmed; the experimental support is for Japanese, Arabic and Chinese only, so "other scripts experimental" is too broad; the card says English) |
| S14 | https://huggingface.co/deepseek-ai/DeepSeek-OCR-2 | DeepSeek-OCR 2 card | 2026-01 | licence, size | "License: apache-2.0"; "Model size 3B params" | confirmed (apache-2.0, 3B, visual token formula (0-6)x144+256; HF repo created 2026-01-27; Real5 73.01 and Skew 61.28 confirmed in S1) |
| S15 | https://huggingface.co/dots-studio/dots.mocr | dots.mocr card (rednote) | 2026-03 | licence, scores | "License: mit"; olmOCR-bench overall 83.9; Old scans 48.2 (dots.ocr 40.9) | confirmed (MIT, 3B, olmOCR-bench 83.9, Old scans 48.2 vs dots.ocr 40.9, MDPBench 80.5, robustness caveat) |
| S16 | https://huggingface.co/PaddlePaddle/PaddleOCR-VL | PaddleOCR-VL card | 2025-10-16 | languages | "This innovative model efficiently supports 109 languages"; "handwritten text and historical documents" | confirmed (109 languages, handwritten and historical documents, apache-2.0, created 2025-10-16) |
| S17 | https://github.com/opendatalab/MinerU | MinerU repository | 2026 | licence, CPU | "MinerU Open Source License, based on Apache 2.0 with additional conditions"; "CPU works" | confirmed (MinerU Open Source License based on Apache 2.0 with additional conditions; CPU execution supported). Release date 2026-04 for MinerU2.5-Pro not checked |
| S18 | https://arxiv.org/abs/2510.19817 | olmOCR 2 (Poznanski et al.) | 2025-10-22 | size, method | "olmOCR-2-7B-1025, a specialized, 7B vision language model"; "our English-language OCR benchmark" | confirmed (arXiv 2510.19817, 2025-10-22; 7B; English benchmark; permissive licences) |
| S19 | https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html | PP-OCRv5 docs (PaddleOCR) | 2025 | speed, accuracy | PP-OCRv5_server_rec 0.8401; GPU 0.74 s, CPU 4.34 s per image | partly (0.8401, 0.74 s GPU, 4.34 s CPU for the server model, 5 text types confirmed. The 5 types are Simplified Chinese, Pinyin, Traditional Chinese, English and Japanese; Finnish, Swedish, Estonian, Polish and Greek are not listed, so use for Finnish labels is an untested assumption. Licence not on the page) |
| S20 | https://arxiv.org/abs/2504.08645 | Title block detection and information extraction (Lombardi et al., EC3 2025) | 2025-04-11 | title block method | "combining a lightweight Convolutional Neural Network and GPT-4o" | confirmed (arXiv 2504.08645, 2025-04-11, Lombardi et al.; quote in abstract; no numbers in abstract) |
| S21 | https://www.diva-portal.org/smash/get/diva2:1950437/FULLTEXT01.pdf | eDOCr2: Optimizing Text Recognition in Mechanical Drawings (Toro and Tarkian), Machines 13(3):254 | 2025-03-20 | text recall 93.75%, CER below 1% | abstract via Crossref; the DiVA PDF text could not be read | corrected (the paper is "Optimizing Text Recognition in Mechanical Drawings: A Comprehensive Approach", Toro and Tarkian, Machines 13(3):254, 2025-03-20, DOI 10.3390/machines13030254, found via Crossref. Abstract: eDOCr2 combines traditional OCR and image processing, text recall 93.75%, CER below 1%, plus Qwen2-VL-7B and GPT-4o to verify. "CRAFT detector" is not in the abstract. The DiVA PDF downloaded but its text could not be read) |
| S22 | https://doi.org/10.3390/buildings15224048 | A Study on Methods for Parsing Architectural Multi-Modal Data and Extracting Modeling Parameters (Buildings 15(22):4048) | 2025-11-10 | table parameter recall 95.0% (doors/windows), 96.7% (structure) | abstract via Crossref (MDPI returned 403) | corrected (opened via Crossref, not MDPI: the title is "A Study on Methods for Parsing Architectural Multi-Modal Data and Extracting Modeling Parameters", Buildings 15(22):4048, 2025-11-10. Abstract: table parameter extraction recall 95.0% for doors/windows and 96.7% for structure. The abstract does not say the table method works on both DXF and PDF; the drawings are DXF) |
| S23 | https://github.com/tyschroed/parse-dimension | parse-dimension (JavaScript) | - | UNVERIFIED: no Python feet-inch parser found | search snippet only | partly (repository exists, MIT, JavaScript/TypeScript; the claim "no maintained Python library" is an absence claim and stays UNVERIFIED) |

## Verification

- Date: 2026-11-13.
- Sources opened: 23 of 23 external sources (S1 to S23). S1 to S20 and S23 were opened as pages (arXiv abs and HTML,
  Hugging Face cards, GitHub READMEs, the Businessware blog, the PaddleOCR docs). S21 and S22 were opened through the
  Crossref API (abstract and metadata) because MDPI returned 403 and the DiVA PDF text could not be read. M1 to M3 are
  local measurements and were not re-run. The WebFetch tool hit a usage limit, so pages were fetched with curl and
  searched as text.
- Result: 16 confirmed, 3 corrected (S4, S21, S22), 4 partly (S11, S13, S19, S23), 0 not found, 3 local not re-run.
  Every figure behind "Findings that change decisions" 3 to 9 was found in its source.
- Corrections:
  1. S4 GLM-OCR: the release date is 2026-01 (HF repo created 2026-01-30), not 2026-03.
  2. S21 eDOCr2: the title is "Optimizing Text Recognition in Mechanical Drawings: A Comprehensive Approach", Machines
     13(3):254, 2025-03-20 (Toro and Tarkian). The abstract gives text recall 93.75% and CER below 1%. The "CRAFT
     detector" detail is not confirmed.
  3. S22: the title is "A Study on Methods for Parsing Architectural Multi-Modal Data and Extracting Modeling
     Parameters", Buildings 15(22):4048, 2025-11-10. The 95.0% figure is recall for door/window table parameters, and it
     is now confirmed from the abstract. The claim "from DXF and PDF" is not supported for tables.
  4. S11: "ACL 2026" is not on the arXiv page. Marked unconfirmed. The quotes and the authors are correct.
  5. S13: experimental support covers Japanese, Arabic and Chinese only, not all other scripts.
  6. S19: PP-OCRv5 lists 5 text types and no Finnish, Swedish, Estonian, Polish or Greek. Use of PP-OCRv5 in "What we can use this
     weekend" item 5 is untested for those languages. The latin codes (MH, KH, WC) may work, but this is not shown.
  7. S5 and S12: the caps are on "funding/revenue" (startups under $2M and $5M), not revenue alone.
- Not checked: release dates for GLM-OCR, MinerU2.5-Pro, Chandra 2 and Surya 2.5 beyond the cards; the EMNLP 2025 venue
  of CHURRO; the PyMuPDF AGPL and pdfplumber MIT licences (the report marks both as not re-checked); the claim that no
  Python feet-and-inches library exists; the PP-OCRv6 claim (still UNVERIFIED).
