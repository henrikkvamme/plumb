# Text reading on drawings: OCR and text-spotting models, November 2026

Date: 2026-11-14. Topic: rotated text, small room labels, dimension numbers, schedules, title blocks, handwriting on
historic scans, Nordic and German labels. Earlier work: `../sota/doc-parsing.md` (not repeated here).

Labels: **SOURCED** (URL and date in the Sources table), **MEASURED** (we ran it tonight on this Mac, see
"Measurements"), **ESTIMATE** (our reasoning), **UNVERIFIED** (could not open a source or could not test).

## In short

1. **Primary: two models.** Fast word and line boxes with rotation: **PP-OCRv6 medium** (`PP-OCRv6_medium_det` and
   `PP-OCRv6_medium_rec`, 34.5M parameters, Apache-2.0, released 2026-06-11). MEASURED: 98.5% token recall on a
   4536x3240 render of a US schedule sheet, 94.3% on a German-labelled Swiss plan PNG, 35 s per large sheet on one M4 Max CPU
   with ONNX Runtime. Its rec model lists fi, sv, de, fr, da, nl and et (SOURCED).
2. **Hard crops: PaddleOCR-VL-1.6** (`PaddlePaddle/PaddleOCR-VL-1.6`, 0.9B, Apache-2.0, 2026-05-28) on the Verda A100 with
   vLLM. It gives quad text spotting and OTSL tables. MEASURED: it reads vertical dimensions and labels correctly, but it
   turned `7' - 0"` into `7" - 0"` seven times in 17 schedule rows. Never trust its dimension strings alone.
3. **Fallback: Chandra 2** (`datalab-to/chandra-ocr-2`, 5.3B, OpenRAIL-M with a $2M cap) for handwriting and old scans only.
   It has the best published old-scan score (51.1) and per-language scores for da, de, fi, fr, nl, sv (SOURCED). It has no word boxes.
4. **Do not train an OCR model tonight.** The fast model already reads printed text. No model, ours or theirs, reads
   handwriting on historic scans well. If you must train, start from PaddleOCR-VL-1.6 with the ERNIEKit recipe below.
5. **Three traps.** (a) Turn `use_textline_orientation` ON: without it, text rotated 90 or 180 degrees falls from 94% to 38%
   recall. (b) PP-OCR `return_word_box=True` gives wrong boxes on rotated lines: cut the quad ourselves. (c) HunyuanOCR-1.5 has a
   text-spotting mode, but its licence does not apply in the EU: do not use it.

## Candidates

"Boxes" means what the model returns for position. Speed is for the hardware named. Scores are the vendor's own unless marked.

| Model (exact id) | Params, licence | Released | Boxes and rotation | fi, sv, de, fr, da, nl, et | Speed | Published scores | Verdict |
|---|---|---|---|---|---|---|---|
| **PP-OCRv6 medium** (`PP-OCRv6_medium_det` + `_rec`) | 34.5M; Apache-2.0 | 2026-06-11 (PaddleOCR 3.7.0) | Line quads (4 points, any angle). 0/180 line classifier. Word boxes unreliable on rotated lines (M5) | All 7 named in the rec language table (S1). Printed German and Finnish read well (M2, M3) | M4 Max CPU ONNX: 35 s per 4536x3240 sheet; A100 Paddle: 0.29 s per image (S3, image size not stated) | In-house: det Hmean 86.2, rec 83.2, "Rot." det 93.8 vs 80.0 for v5 (S1, S3) | **Fast model** |
| PP-OCRv6 small (`PP-OCRv6_small_*`) | 7.7M; Apache-2.0 | 2026-06-11 | Same | Same (50 languages) | 7.7 s per sheet (M4 Max, ONNX) | In-house det 84.1, rec 81.3 | **Use for speed**: 98.0% recall on the schedule sheet (M2). Weaker on the Swiss PNG (86.9%, M3, 176 tokens only) |
| PP-OCRv6 tiny (`PP-OCRv6_tiny_*`) | 1.5M; Apache-2.0 | 2026-06-11 | Same | 49 languages | 1.9 s per sheet | In-house det 80.6, rec 73.5 | No: 81% recall on the sheet, 62% on the schedule crop (M2, M4) |
| **PaddleOCR-VL-1.6** (`PaddlePaddle/PaddleOCR-VL-1.6`) | 0.9B (958.6M by HF count); Apache-2.0 | 2026-05-28 | `Spotting:` prompt returns a line of text plus 8 `<\|LOC_n\|>` tokens: a quad on a 0-1000 grid (M6). Page mode: layout boxes, blocks | "109 languages", no list, no per-language score (S5). Lost the umlaut in `Küche` once (M6) | M4 Max MPS: about 10 tokens/s. 35 s for 20 labels. A100 + vLLM: ESTIMATE 5-10x faster | OmniDocBench v1.6 96.33; Real5 Skew 92.66 (S6, confirmed earlier) | **Hard-crop model**, with checks |
| Chandra 2 (`datalab-to/chandra-ocr-2`) | 5.3B (HF count); code Apache-2.0, weights OpenRAIL-M, free under $2M funding or revenue | 2026-03-16 | Layout blocks only | Own 43-language table: da 91.1, de 94.8, fi 83.4, fr 93.7, nl 88.6, sv 92.8. et not in the table (S13) | 1.44 pages/s on H100 (S13) | olmOCR-bench 85.8; Old Scans 51.1; Long tiny text 93.7 (S13) | **Fallback** for handwriting and old scans |
| Surya 2.5 (`datalab-to/surya-ocr-2.5`; pip `surya-ocr` 0.24.0) | 689M; code Apache-2.0, weights OpenRAIL-M, $5M cap | 2026-10-25 | Line detection and block polygons are axis-aligned corners (S11) | 91 languages, 74.9% average, no per-language list read | 4.5 pages/s H100. Needs a vLLM or llama.cpp server for OCR (S11) | OmniParseBench 85.9; olmOCR-bench 83.7 | No: no rotated boxes |
| Indra OCR (`datalab-to/indra-ocr`; pip `indra-ocr` 1.1.2) | 1.25M main rec, 7.3M all; weights OpenRAIL-M ($20M cap) | 2026-10-10 | Axis-aligned line boxes. Page rotation and skew up to 45 degrees only per page (S12) | Latin 50 languages incl. the 7 (S12, list partly lost in the card) | 210 ms per page on 4 CPU cores (S12) | OmniParseBench headline 61.2 (OCR only) to 66.7 (auto) on the card; "Latin 61.6" UNVERIFIED; handwriting 25.2 | No: page-level rotation, not per label |
| GLM-OCR (`zai-org/GLM-OCR`) | 0.9B in the card, 1.33B by HF count; MIT | 2026-01-30 | None. It uses PP-DocLayoutV3 for layout (S14) | Not stated | 1.86 pages/s PDF (S14) | OmniDocBench v1.5 94.62 | Page parser, not a box source |
| dots.mocr (`dots-studio/dots.mocr`) | 3.04B; MIT | 2026-03-19 | Layout blocks | Not checked | Not checked | olmOCR-bench 83.9; Old scans 48.2 | No gain over the two above |
| HunyuanOCR-1.5 (`tencent/HunyuanOCR`) | 1.12B; **Tencent Hunyuan Community Licence** | 2026-07 (paper 2026-07-06) | Has `spotting_json` and `spotting_hunyuan` tasks (S10) | Not checked | 2.14x faster under vLLM than 1.0 | OmniDocBench v1.6 "top-tier" (S10) | **Blocked**: the licence says it "does not apply in the European Union, United Kingdom and South Korea" |
| MiniCPM-OCR 1.0 (`openbmb/MiniCPM-OCR-1.0`) | 1.3B; Apache-2.0 | 2026-10-21 | None documented | "Chinese and English" primary (S15) | 1.2 pages/s on RTX 5090 | Real5 93.68; OCRBench v2 54.7 | No: language scope |
| LightOnOCR-3 (`lightonai/LightOnOCR-3-1B`, `-0.8B`, `-4B`) | 0.8B-4B; Apache-2.0 | 2026-10-06/07 | `grounding` prompt: block labels with boxes (S17) | Not checked | Not checked | Not checked | Not tested: block boxes only |
| HPD-Parsing (`PaddlePaddle/HPD-Parsing`) | 1.07B; Apache-2.0 | 2026-07-21 | Page parser | en, zh only (S16) | 4,752 tokens/s peak, custom vLLM build | OmniDocBench v1.6 94.91 | No: en and zh |
| docTR 1.1.0 | Apache-2.0 | 2026-08-21 | Rotated boxes with `assume_straight_pages=False`, word level (S21) | Not stated | M4 Max CPU: 6.8 s (Swiss), 13.4 s (sheet) | none read | No: 29% and 4% recall (M7) |
| EasyOCR 1.7.2 | Apache-2.0 | 2024-09-24 | Quads | 80+ languages (not re-opened) | M4 Max CPU: 14.6 s, 18.8 s | none read | No: 50% and 48% recall (M7). No release in two years |
| Tesseract 5.5.4 | Apache-2.0 (not re-opened) | 2026-10-28 (S20) | Axis-aligned word boxes, page-level OSD | `fin`, `swe`, `deu`, `est`, `dan`, `nld`, `fra` data exist (not re-opened) | Not run: not installed here | none read | Not tested. Skip unless a CPU-only box has no Python |
| olmOCR 2 (7B) | permissive | 2025-10-22 | None | English only (S22 in doc-parsing.md) | - | - | No |
| TrOCR-style (Microsoft, 2021) and CHURRO-3B | CHURRO: qwen-research (NC) | 2021 / 2025-09 | Line crops only, no detection | CHURRO: 46 language clusters | - | CHURRO 82.3% printed, 70.1% handwritten (earlier doc) | No: stale or non-commercial. Swedish National Archives TrOCR models: UNVERIFIED (one secondary page) |

Corrections to earlier files:

- **PP-OCRv6 is real and current.** `paddleocr` 3.7.0 and PP-OCRv6 on 2026-06-11 (S2). The earlier "UNVERIFIED" is closed.
- **PP-OCRv6 lists Finnish, Swedish, German, French, Danish, Dutch and Estonian** (S1 table). Earlier files said PP-OCRv5
  lacked them: true for v5, false for v6.
- **PaddleOCR-VL-1.6 text spotting is line level.** It is not word level (S5, M6).
- **GLM-OCR size:** the card says 0.9B. The Hugging Face tensor count is 1.33B.
- **Chandra 2 size:** 5.3B by HF count (the card does not say).
- **The PaddleOCR-VL-1.6 card says "For macOS users, please use Docker".** The docs matrix says Apple Silicon works with
  PaddlePaddle plus MLX-VLM (S7). Plain `transformers` on MPS also worked tonight (M6).

## Measurements

Machine: Apple M4 Max, macOS 27.0.1, arm64. Python 3.12 venvs. `paddleocr` 3.7.0, `paddlepaddle` 3.3.1, `onnxruntime` 1.32.0,
`transformers` 5.23.0, `python-doctr` 1.1.0, `easyocr` 1.7.2. Scripts and outputs are in the session scratchpad, not in the repo.

Method for recall: render or load the image, run OCR, split into whitespace tokens, then compare with the PDF text layer
(pypdfium2) as a multiset. Recall is matched tokens over ground-truth tokens. Precision is matched tokens over OCR tokens.
Error: tokens that OCR merges or splits count as misses, so recall is a little low for every model.

**M1. Test inputs.** `A-801` door and finish schedule sheet, rendered at 1.5x to 4536x3240 (1,885 ground-truth tokens, 1,073 text boxes).
Swiss plan `site1000_bldg2082_floor9385.png`, 2480x1753 (176 tokens). Door schedule crop 1179x360 (245 tokens). Also: a Finnish CubiCasa PNG,
a Swedish hand-drawn Finna scan, a HABS historic sheet.

**M2. Whole schedule sheet, PP-OCRv6 by tier (ONNX Runtime, CPU, `use_textline_orientation=False`).**

| Tier | Time per sheet | Recall | Precision |
|---|---|---|---|
| medium | 35.0 s | 0.985 | 0.972 |
| small | 7.7 s | 0.980 | 0.972 |
| tiny | 1.9 s | 0.810 | 0.881 |
| medium, Paddle backend, orientation ON | 135 s | 0.965 | 0.965 |

**M3. Swiss PNG (German labels, m² values).** medium 0.943 recall in 4.2 s. small 0.869 in 1.3 s. tiny 0.875 in 0.35 s.
It read `Zimmer`, `Küche`, `Reduit`, `15.61 m²`, `12.05 m²` correctly. Only 176 tokens, so small versus medium is noise-prone.

**M4. Door schedule crop (245 tokens).** PP-OCRv6 medium 0.955, small 0.955, tiny 0.62. PaddleOCR-VL-1.6 `Table Recognition:`
0.796 recall in 80 s on MPS for 846 tokens. The VL table output had correct structure with spans (OTSL tags `<fcel>`, `<lcel>`, `<ucel>`, `<nl>`).
Its errors: `7' - 0"` came out as `7" - 0"` 7 times, and `2'` and `8'` dropped the foot mark. The PP-OCR misses were
only cell merges (`C100.A2` from two neighbours). The VL model keeps cells apart better. PP-OCR reads the characters better.

**M5. Rotation (Swiss PNG rotated with PIL, medium ONNX).** Recall:

| Rotation of the whole image | Orientation classifier OFF | Orientation classifier ON |
|---|---|---|
| 0 | 0.943 | 0.943 |
| 90 (text reads bottom to top) | **0.381** | 0.847 |
| 180 | **0.381** | 0.886 |
| 270 (text reads top to bottom) | 0.898 | 0.898 |
| 30 | 0.847 | 0.847 |
| 45 | 0.869 | 0.869 |

The classifier (`PP-LCNet_x1_0_textline_ori`, 0 or 180 degrees) costs about 1.5 to 2.5 s more on a 5 s page. The detection quad
follows the angle: a 30 degree label gave `[[1148,789],[1188,770],[1196,785],[1155,804]]`. **`return_word_box=True` is wrong for
rotated lines:** for `Küche` at 30 degrees the word boxes were axis-aligned, 4 px high and outside the quad. At 270 degrees
the boxes were also wrong. `textline_orientation_angles` was 0 for all lines I printed. For word boxes, cut the quad along its long axis in
proportion to character positions (ESTIMATE: 40 lines of code, test on the rotated cases above).

**M6. PaddleOCR-VL-1.6 on MPS (`transformers` 5.23.0, bf16).**

| Input | Task | Tokens | Time | Result |
|---|---|---|---|---|
| Swiss crop 500x350, upscaled 2x | `Spotting:` | 374 | 35 s | 20+ labels with quads. `Zimmer`, `Treppenhaus`, `Wohnen/Essen`, `Korridor` right. `Kuche` (umlaut lost), `Komidor` (wrong), `m2` for `m²` |
| HABS crop 1000x750, upscaled 2x | `Spotting:` | 80 | 17 s | All 6 right: `CRAWL SPACE`, `TRUNK ROOM`, `11'-8"` and `18'-4"` (both vertical), `DRY ROOM`, `FURNACE` |
| Finna crop 3000x1100 (Swedish ink) | `OCR:` | 35 | 4.8 s | `Andringqartning för tomt n=51 twarter 107`. Dropped the line `å Brändö`. True text: `Ändringsritning för tomt nº 51 kvarter 107 å Brändö` |

The output form is `text<|LOC_a|><|LOC_b|>...` with 8 numbers: 4 corners on a 0-1000 grid over the (resized) image, clockwise from the
top-left. First model load took 137 s (download). The card's script fails on `transformers` 5.23.0 at
`processor.image_processor.min_pixels`. Use `processor.image_processor.size.shortest_edge`.

**M7. Others on the same inputs (CPU, torch).** docTR `db_resnet50` + `crnn_vgg16_bn`, `assume_straight_pages=False`: recall 0.290 on the
Swiss PNG, 0.044 on the sheet. EasyOCR (en+de, en): 0.500 and 0.479. docTR's detector resizes the page, so small sheet text vanishes.

**M8. Handwriting and rotated title text, PP-OCRv6 medium.** The Finna sheet: `Andringsritning`, `toarter 107`, `i Brando` (partly right), `Badr.` 0.98,
`Dom.` 1.0, `kok` 0.83 for `Kök`, and `Salon` 0.95 for the label `Hall`. A confident wrong word. The HABS sheet:
the rotated title block read as `IDENER`, `UIVEY`, `ISA` (true: `SURVEY` and similar) at scores 0.5-0.85, while `MT-107`, `30'-0"` and `18'-4"` read right.
Finnish CubiCasa labels: `ET+porras`, `MH`, `1. kerros`, `2. kerros` at 0.97-1.0, 13 boxes in 1.75 s.

## Recommendation and recipe

### Routing (ESTIMATE, from M1 to M8)

1. **Vector PDF, DXF, IFC:** read the text layer or the file. No OCR (earlier finding, `../sota/doc-parsing.md`).
2. **Raster page or scan:** PP-OCRv6 medium on the whole page, or on tiles of about 2,500 px with 15% overlap when the sheet is larger than 5,000 px (ESTIMATE: not tested above 4,536 px). Orientation classifier ON. Keep the quad and the score per line.
3. **Escalate to PaddleOCR-VL-1.6** only these crops: schedule regions (task `table`), lines with a score below 0.85, dimension strings that fail the grammar, and title-block regions. Use at most 40 labels per spotting call (M6: about 18 tokens per label).
4. **Check dimensions with a grammar** (`5'-6 1/2"`, `1:100`, `mm`). When the two models differ on a foot or inch mark, trust PP-OCRv6 and log the doubt (M4).
5. **Scans with handwriting:** give text answers a low confidence. Optional: Chandra 2 on the crop. Do not spend GPU hours on it before we know the hidden set has such questions.
6. **Never use the rec score as the only confidence** (M8: `Salon` at 0.95).

### Install, fast model (tested on macOS arm64)

```sh
uv venv --python 3.12 && uv pip install paddleocr paddlepaddle onnxruntime
```

About 1 minute. `paddlepaddle` 3.3.1 has an arm64 wheel. A "No ccache" warning is harmless. First use downloads the ONNX models.
For Linux with CUDA: `pip install paddleocr onnxruntime-gpu` plus `paddlepaddle-gpu==3.2.1` from
`https://www.paddlepaddle.org.cn/packages/stable/cu126/` (the card's line, S5; not run here).

```python
import os
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
from paddleocr import PaddleOCR
ocr = PaddleOCR(
    use_doc_orientation_classify=False, use_doc_unwarping=False,
    use_textline_orientation=True,                      # required for 90 and 180 degree text (M5)
    engine="onnxruntime",                               # 4x faster than the Paddle backend on CPU (M2)
    text_detection_model_name="PP-OCRv6_medium_det",    # use _small_ for 4.5x speed, same recall on the sheet (M2)
    text_recognition_model_name="PP-OCRv6_medium_rec",
)
res = ocr.predict("sheet.png")[0].json["res"]
# res["rec_texts"], res["rec_scores"], res["rec_polys"] (4-point quads, carry the angle)
```

The result is line level. Do not use `return_word_box=True` for rotated text (M5).

### Install, hard model

Mac (tested, slow): `uv pip install torch "transformers>=5.0.0" pillow` and the card's script with the `size.shortest_edge` fix (M6).

Verda A100 (from the card and the docs, S5 and S7; not run tonight): `vLLM` needs compute capability 8.0 or higher and CUDA 12.6 or higher. The A100 qualifies. A V100 does not (the docs say timeouts and OOM).

```sh
docker run --rm --gpus all --network host \
  ccr-2vdh3abv-pub.cnc.bj.baidubce.com/paddlepaddle/paddleocr-genai-vllm-server:latest-nvidia-gpu \
  paddleocr genai_server --model_name PaddleOCR-VL-1.6-0.9B --host 0.0.0.0 --port 8080 --backend vllm
```

```python
from paddleocr import PaddleOCRVL
pipe = PaddleOCRVL(pipeline_version="v1.6", vl_rec_backend="vllm-server", vl_rec_server_url="http://127.0.0.1:8080/v1")
```

The pipeline does page parsing with layout blocks. **UNVERIFIED:** whether the `Spotting:` prompt is exposed through the pipeline or the vLLM server.
The card only shows spotting through `transformers`. Test this in the first hour. The vLLM image is about 13 GB (S7). The
VL docs give no VRAM figure. ESTIMATE: 0.9B in bf16 fits any 16 GB GPU for inference.

### Fine-tuning (only if the 1-hour tests show a gap)

Do not fine-tune the PP-OCRv6 detector or recognizer tonight: printed text is at 95-98% recall (M2-M4) and the official page has no PP-OCRv6
training recipe (S9, "replace the corresponding configuration file"). Fine-tune PaddleOCR-VL-1.6 if the gap is dimension strings or schedule cells.

| Item | Value | Label |
|---|---|---|
| Library | ERNIEKit (`PaddlePaddle/ERNIE`, branch `release/v1.5`), image `paddlepaddle/paddle:3.2.0-gpu-cuda12.6-cudnn9.5` | SOURCED (S8) |
| Install | `git clone https://github.com/PaddlePaddle/ERNIE && cd ERNIE && pip install -r requirements/gpu/requirements.txt && pip install -e . && pip install tensorboard opencv-python-headless numpy==1.26.4` | SOURCED (S8) |
| Command | `CUDA_VISIBLE_DEVICES=0 erniekit train examples/configs/PaddleOCR-VL/sft/run_ocr_vl_sft_16k.yaml model_name_or_path=PaddlePaddle/PaddleOCR-VL-1.6 train_dataset_path=./train.jsonl` | Command SOURCED (S8, with the 1.0 model name). The 1.6 name is the architecture-compatible swap (S5 says "plug-and-play") |
| Data format | JSONL. `image_info` (`image_url`, `matched_text_index`) and `text_info` (`text`, `tag` alternating `mask` for the prompt such as `OCR:` or `Table Recognition:`, `no_mask` for the answer) | SOURCED (S8) |
| Defaults | `max_steps=926`, `warmup_steps=10` (1% of steps), `packing_size=8`, `gradient_accumulation_steps=8`, `max_seq_len=16384`, `learning_rate=5e-6`. On out-of-memory: lower `packing_size`, raise accumulation | SOURCED (S8) |
| Time | Source example: 29,605 samples, 2 epochs, one A800 80 GB, about 2 hours. For 8,000 crops and 2 epochs: about 0.5 hour on one A100 80 GB | Example SOURCED. Scaling ESTIMATE |
| Image size | Dynamic resolution. Keep crops under 1.6 MP (`max_pixels = 2048*28*28 = 1,605,632` for spotting, about 1 MP for other tasks) | SOURCED (S5) |
| Epochs | 2 | SOURCED (S8 example) |
| Data for us | Crops from the swiss and CubiCasa PNGs whose labels come from the PDF text layer and the IFC or SVG sources, plus foot-and-inch dimension strings rendered in drawing fonts | ESTIMATE |
| Not covered | The `Spotting:` quad format is not in the SFT doc. Train `OCR:` and `Table Recognition:` only. Spotting SFT is UNVERIFIED | UNVERIFIED |
| Cost | 0.5 h x $2.37 = about $1.2 per run | ESTIMATE |

If PP-OCRv6 recognition needs training anyway: `python3 tools/train.py -c <config>.yml -o Global.pretrained_model=PP-OCRv6_medium_rec_pretrained.pdparams`
with the config path UNVERIFIED (the page shows only `configs/rec/PP-OCRv5/PP-OCRv5_server_rec.yml`) (S9).

### Cost check against 10 cents per document (ESTIMATE)

PP-OCRv6 medium on a GPU is about 0.3 s per image (S3), so one sheet costs well under 0.1 cent. PaddleOCR-VL on a crop: 400 to 900 tokens
at an assumed 150 to 300 tokens/s on an A100 is 2 to 6 s, which is about 0.2 cents at $2.37 per hour. A document with 10 hard crops costs 1 to 3 cents.
I do not know where the scored run will happen. If it must run on a CPU only, use the small tier (7.7 s per sheet, M2) and skip the VL model.

## Risks and how to test them in 1 hour

| Risk | Test (about 10 min each) | Pass |
|---|---|---|
| Rotated labels fail at other angles or on real sheets | Rotate 20 plans by 0, 90, 180, 270 and 15 degrees. Run the fast model with the orientation classifier. Compare with the PDF text layer as in M5 | Recall within 10 points of the 0 degree case |
| Word boxes are wrong on rotated text | Write the quad-cutting function. Check that each word box lies inside its line quad on the 30 and 270 degree cases | 100% of word boxes inside their quad |
| Foot and inch marks misread by the VL model | Run `table` and `OCR:` on 20 schedule crops. Count `'` versus `"` mistakes against the text layer. Compare PP-OCRv6 on the same crops | VL mistake rate under 1%, or the rule "trust PP-OCRv6 on marks" is in the code |
| Nordic diacritics and Estonian | Take the labels from 30 CubiCasa and Finna items. Count lost `ä`, `ö`, `å`, `õ`, `ü` for both models. Estonian: only the PP-OCRv6 list is sourced | Under 3% of labels lose a diacritic, or the question matcher folds diacritics |
| Small text on big sheets | Run a 7,000 px sheet whole and tiled. Compare recall | Tiled recall at least equals whole-page recall |
| Overconfident scores | Plot score versus correctness on 200 lines (M8: `Salon` at 0.95) | We have a threshold that keeps 90% precision, or we use the VL model as a second reader |
| VL spotting through vLLM | On a Verda A100 (`pnpm j gpu up 1A100.22V --hours 1`), send the `Spotting:` prompt to the server. Measure tokens/s and pages/s. Run `pnpm j gpu down` after | The prompt works, 20 labels in under 5 s |
| Handwriting on historic scans | Run Chandra 2 and PaddleOCR-VL on 10 Finna and HABS crops with a human transcript | Character accuracy above 85%, else mark the answer low-confidence |
| Install on Linux CUDA | Fresh venv on the A100 with the commands above | `ocr.predict` runs, GPU used |
| Licence | Chandra and Surya: OpenRAIL-M caps ($2M, $5M). HunyuanOCR: not allowed in the EU | Recorded here. Fine for a hackathon. Not for a product |

## Sources

Opened between 2026-11-13 and 2026-11-14. "Card" means the Hugging Face README, read as raw text.

| id | Title | URL | Date | Supports |
|---|---|---|---|---|
| S1 | PP-OCRv6: From 1.5M to 34.5M Parameters, Surpassing Billion-Scale VLMs on OCR Tasks (arXiv 2606.13108) | https://arxiv.org/html/2606.13108 | 2026-06-11 | 50-language table with fi, sv, de, fr, da, nl, et; in-house det and rec scores; DB head polygons; rotated-text gains |
| S2 | PaddleOCR releases | https://github.com/PaddlePaddle/PaddleOCR/releases | v3.7.0 2026-06-11; v3.6.0 2026-05-28 | PP-OCRv6 release; PaddleOCR-VL-1.6 release |
| S3 | PP-OCRv6 introduction (PaddleOCR docs) | https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv6/PP-OCRv6.html | 2026-06 | Speed table (A100 0.29 s, Apple M4 ONNX 5.55 s, Xeon), `use_textline_orientation` flag, Rot. column |
| S4 | PP-OCRv6_medium_rec card | https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec | created 2026-06-10 | Licence apache-2.0; model ids; pipeline example. HF API listing gives the 18 v6 repos |
| S5 | PaddleOCR-VL-1.6 card | https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6 | 2026-05-28 | Licence; install lines; vLLM server command; spotting script; `max_pixels`; "use Docker" note on macOS |
| S6 | PaddleOCR-VL-1.6 technical report (arXiv 2606.03264) | https://arxiv.org/html/2606.03264v1 | 2026-06-02 | OmniDocBench v1.6 96.33; Real5; spotting benchmark covers zh, en, ja only (9 dimensions) |
| S7 | PaddleOCR-VL usage tutorial | https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html | 2026-11 | Hardware matrix (vLLM CC 8.0+, CUDA 12.6+), Apple Silicon matrix, image sizes, 109 languages. Page read only to character 100,000 of 162,170 |
| S8 | PaddleOCR-VL-0.9B SFT (ERNIE docs, `release/v1.5`) | https://raw.githubusercontent.com/PaddlePaddle/ERNIE/release/v1.5/docs/paddleocr_vl_sft.md | 2026 | ERNIEKit recipe, data format, defaults, 2 hours on one A800 80 GB |
| S9 | PaddleOCR text recognition module docs | https://www.paddleocr.ai/latest/en/version3.x/module_usage/text_recognition.html | 2026-11 | Train command pattern; v6 model sizes (73.3, 20.4, 4.4 MB); no v6 recipe |
| S10 | HunyuanOCR (card, LICENSE, paper arXiv 2607.04884) | https://huggingface.co/tencent/HunyuanOCR | 2026-07-06 (paper) | Spotting tasks; Tencent licence "does not apply in the European Union, United Kingdom and South Korea" |
| S11 | Surya 2.5 card | https://huggingface.co/datalab-to/surya-ocr-2.5 | 2026-10-25 | 689M; axis-aligned polygon convention; weights openrail; vLLM or llama.cpp server |
| S12 | Indra OCR card | https://huggingface.co/datalab-to/indra-ocr | 2026-10-10 | 1.25M rec; axis-aligned lines; page rotation; OpenRAIL-M $20M; speed |
| S13 | Chandra OCR 2 card | https://huggingface.co/datalab-to/chandra-ocr-2 | 2026-03-16 | olmOCR-bench table; 43-language table (da, de, fi, fr, nl, sv); licence; 5.3B from HF API |
| S14 | GLM-OCR card | https://huggingface.co/zai-org/GLM-OCR | 2026-01-30 | MIT; 0.9B in text, 1.33B by HF count; PP-DocLayoutV3 dependency |
| S15 | MiniCPM-OCR 1.0 card | https://huggingface.co/openbmb/MiniCPM-OCR-1.0 | 2026-10-21 | Apache-2.0; 1.3B; Chinese and English primary; 1.2 pages/s RTX 5090 |
| S16 | HPD-Parsing card | https://huggingface.co/PaddlePaddle/HPD-Parsing | 2026-07-21 | Apache-2.0; en and zh; custom vLLM |
| S17 | LightOnOCR-3 card | https://huggingface.co/lightonai/LightOnOCR-3-1B | 2026-10-07 | Apache-2.0; grounding mode with block boxes |
| S18 | Benchmarking Deep Learning Approaches for AEC Engineering Drawing Layout Detection and Information Extraction (arXiv 2607.18997) | https://arxiv.org/abs/2607.18997 | 2026-07-21 | RF-DETR mAP50 0.949 for layout; Qwen3-VL F1 0.911 for information extraction; abstract only |
| S19 | PyPI JSON for python-doctr, easyocr, surya-ocr, indra-ocr, chandra-ocr, rapidocr | https://pypi.org/pypi/python-doctr/json (and others) | 2026-11-14 | docTR 1.1.0 (2026-08-21), EasyOCR 1.7.2 (2024-09-24), surya-ocr 0.24.0 (2026-11-13), rapidocr 3.10.0 (2026-10-08) |
| S20 | Tesseract releases | https://github.com/tesseract-ocr/tesseract/releases | 5.5.4 on 28 Oct (year inferred 2026), 5.5.3 on 24 Jul | Latest version; no rotation changes in 5.5.2 to 5.5.4 |
| S21 | docTR README | https://github.com/mindee/doctr | 2026 | Apache-2.0; `assume_straight_pages=False` rotated boxes; word level; no drawings |
| S22 | CHURRO (arXiv 2509.19768) | https://arxiv.org/abs/2509.19768 | 2025-09-24 | Historic OCR scores (from the earlier file, via a search result tonight) |
| S23 | Search results on OmniDocBench rotation, AECV-Bench, Qwen3-VL OCR, and Nordic HTR | web search, 2026-11-14 | - | Search snippets only. **UNVERIFIED**: no engineering-drawing OCR benchmark found for any model here. Nothing here is a published drawing score |
| M1-M8 | Local runs | see "Measurements" | 2026-11-14 | All MEASURED rows. Inputs from `stoa/data/junction-dataset-preview/` |

## What I could not check

- No published OCR score on drawings, rotated dimension text or Nordic labels exists for any model above. Every drawing figure in this file is ours (M1-M8), on 6 inputs.
- GPU speed for PaddleOCR-VL on an A100 is an ESTIMATE. I did not start a Verda VM.
- Tesseract was not installed and was not run. Chandra 2, Surya 2.5, Indra OCR and LightOnOCR-3 were not run. Their figures come from cards.
- Estonian: sourced only for PP-OCRv6 (S1). Chandra's table has no `et` row.
- The tiling advice for sheets above 4,536 px is untested.

## Verification

Checked on 2026-11-14 by an independent verifier who opened each primary source. Local measurements M1-M8 were not rerun: UNVERIFIED by this check. The recommendation stands.

| Claim | Verdict | Evidence URL |
|---|---|---|
| PP-OCRv6 medium: 34.5M total (det 15.5M, rec 19M), Apache-2.0, released 2026-06-11 | CONFIRMED | https://arxiv.org/html/2606.13108 ; https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec ; https://github.com/PaddlePaddle/PaddleOCR/releases |
| PP-OCRv6 rec table lists fi, sv, de, fr, da, nl, et (medium, small 50 languages; tiny 49) | CONFIRMED | https://arxiv.org/html/2606.13108 (Appendix A, Table 10) |
| In-house det Hmean / rec: medium 86.2 / 83.2, small 84.1 / 81.3, tiny 80.6 / 73.5 | CONFIRMED | https://arxiv.org/html/2606.13108 |
| "Rot." det 93.8 (v6 medium) vs 80.0 (v5 server) | CONFIRMED | https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv6/PP-OCRv6.html |
| Speed: A100 0.29 s per image; Apple M4 ONNX 5.55 s (S3) | CONFIRMED | https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv6/PP-OCRv6.html |
| PaddleOCR-VL-1.6: Apache-2.0, 0.9B (card name; HF shows 1.0B rounded), released 2026-05-28 | CONFIRMED | https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6 |
| PaddleOCR-VL-1.6 OmniDocBench v1.6 96.33; Real5 Skew 92.66 | CONFIRMED | https://arxiv.org/abs/2606.03264 ; https://arxiv.org/html/2606.03264v1 (Table 3) |
| PaddleOCR-VL-1.6 card says macOS users should use Docker; `Spotting:` prompt exists | CONFIRMED | https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6 |
| PaddleOCR-VL-1.6 "109 languages" (S5) | UNVERIFIED | The card does not state it (tags: en, zh, multilingual). The file also cites S7, which was not reopened. |
| Chandra 2: OpenRAIL-M weights, $2M cap, olmOCR-bench 85.8, Old Scans 51.1, Long tiny text 93.7, da 91.1 / de 94.8 / fi 83.4 / fr 93.7 / nl 88.6 / sv 92.8, no et, 1.44 pages/s H100 | CONFIRMED | https://huggingface.co/datalab-to/chandra-ocr-2 (size on card: 5B, HF count 5.3B not rechecked) |
| HunyuanOCR-1.5 exists, has `spotting_json` and `spotting_hunyuan`, licence Territory excludes EU, UK, South Korea | CONFIRMED | https://huggingface.co/tencent/HunyuanOCR ; https://huggingface.co/tencent/HunyuanOCR/raw/main/LICENSE (Section 1(l)) |
| Surya 2.5: 689M, $5M cap, OmniParseBench 85.9, olmOCR-bench 83.7, 4.52 pages/s H100 at 192 DPI, 74.9% over 91 languages | CONFIRMED | https://huggingface.co/datalab-to/surya-ocr-2.5 |
| Surya "no rotated boxes" | UNVERIFIED | The card gives 4-corner polygons in clockwise order for line detection. Whether they follow rotation was not tested. |
| Indra OCR: 1.25M rec, 7.3M total, $20M cap, 210 ms per page on 4 cores, handwriting 25.2 | CONFIRMED | https://huggingface.co/datalab-to/indra-ocr |
| Indra "OmniParseBench Latin 61.6" | UNVERIFIED | The card shows headline 61.2 to 71.4 by mode. Row text edited. |
| GLM-OCR: MIT, 0.9B, OmniDocBench v1.5 94.62, 1.86 pages/s, PP-DocLayoutV3 | CONFIRMED | https://huggingface.co/zai-org/GLM-OCR |
| MiniCPM-OCR-1.0: Apache-2.0, 1.3B, Real5 93.68 (card panel shows 93.75), OCRBench v2 54.7, zh and en, 1.2 pages/s RTX 5090 | CONFIRMED | https://huggingface.co/openbmb/MiniCPM-OCR-1.0 |
| LightOnOCR-3-1B exists, Apache-2.0, `grounding` mode with boxes, 0.8B and 4B siblings | CONFIRMED | https://huggingface.co/lightonai/LightOnOCR-3-1B |
