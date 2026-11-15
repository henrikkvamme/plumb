# Agentic and program-synthesis approaches to drawing and model QA, and their cost

Track report for the Stoa challenge "Make Blueprints Talk". Written 2026-11-13.

How to read the figures:

- **[READ]** means the figure or sentence is in a source I opened. The source id is in brackets, for example [S1].
- **[MEASURED]** means I computed it on our local data in this session.
- **[LEAD]** means the lead measured it and gave it to me in the task. I did not measure it again.
- **[ESTIMATE]** means I computed it from assumptions that I state. It is not a measurement.

Method and limits:

- Web search and the web-fetch tool stopped working early in this session (usage limit). I searched arXiv through its HTML search page, read abstracts and full HTML papers with `curl`, and read vendor price pages with `curl`. GitHub licences come from the GitHub API.
- I could not open the OpenAI "Thinking with images" page (HTTP 403) or a Google "agentic vision" page (HTTP 404). Claims about the built-in code-execution vision of frontier models are therefore **unverified** here.
- The arXiv search page sorts by date. Recall for older work (2023-2024) is lower than for 2026 work.

## Findings that change decisions

1. **For free-text IFC questions, an agent that writes and runs code beats a fixed query translator by a large margin.** On the ifc-bench v2 held-out test split (514 questions), an iterating IfcOpenShell code agent beat single-pass code generation by +36.8 to +38.5 points. The single-pass system abstained on about half of the questions. Hand-written domain tools gave no gain to the strong model and cost the weaker model 10.2 points. Accuracy under a strict LLM-judge rubric was 55.4-56.6% with GLM 4.7 [READ, S1]. Our `ifc_bench` source is this benchmark: 820 text questions on 25 IFC files [MEASURED]. Decision: use a small code-execution agent over IfcOpenShell for free-text IFC questions and for IFC questions that miss a template. Do not build a large hand-made IFC tool library. Criteria: accuracy, generalization to unseen IFC questions. [S1]

2. **"Compile once, then query" is the strongest pattern for cost and for verification, and the quality of the compiled representation sets the ceiling.** On P&IDs, a knowledge-graph representation raised accuracy by 18% over raw images and cut token cost by 85% over raw smart-P&ID files; GPT-5-mini reached 91% at $0.004 per task [READ, S2]. A separate study recovered an evidence graph from P&ID images and made small VLMs (4B-8B) answer only through seven read-only graph operators. Exact match rose from 36.7-41.3% to 74.3-76.0%. The recovered graph had F1 0.742, and "the residual errors track that gap" [READ, S3]. Decision: put effort into exact extraction (DXF, IFC, PDF vectors, raster CV) and a typed fact store. Let the LLM query it, not re-read pixels. Criteria: accuracy, verification, cost. [S2, S3]

3. **Crop-and-zoom "thinking with images" agents are not a reliable accuracy gain, and they cost more tokens.** A causal audit of six such models found "only marginal or negative gains over direct inference at substantially higher token cost" [READ, S4]. A second study found that the returned image pixels are often redundant: replacing them with a text placeholder "matches or exceeds full thinking-with-images" [READ, S5]. On AEC-Bench, construction-sheet tasks that need visual tracing scored 5% mean reward against 100% for text-catchable cases. More image rendering by Codex agents "does not lead to better performance on visually grounded tasks" [READ, S6]. Decision: do not make a zoom agent the core counting method. Use it only as a fallback whose output a deterministic check confirms. Criteria: accuracy, cost. [S4, S5, S6]

4. **An agent loop is about 80 to 150 times more expensive per question than a compiled lookup (Sonnet to Opus).** With prompt caching, a 15-tool-call loop with one high-resolution page image costs about $0.31 per question on Claude Opus 5.5, $0.16 on Sonnet 5.5 or gpt-6.1-sol, and $0.009 on Haiku 5.5 or gpt-6-luna [ESTIMATE from prices READ in S20, S21; assumptions in "Landscape"]. Without caching the Opus figure is about $1.25 [ESTIMATE]. For all 127,044 public questions, an Opus agent would cost about $40,000 [ESTIMATE]. One Sonnet 5.5 compile call per cubicasa drawing, spread over its 17.9 questions, is about $0.002 per question [ESTIMATE; 17.9 from LEAD counts]. Decision: the agent handles only the residual that templates and compiled facts cannot answer. Prompt caching and the Batch API (50% off, [READ, S20]) are mandatory in any LLM path. Criterion: cost. [S20, S21]

5. **Use at most two tiers, and use a deterministic verifier as the escalation signal.** Across 5 benchmarks and 8 models, more than two cascade tiers gave no accuracy gain in 118 of 135 comparisons. Depth helps only when the deferral score tracks the current model's own errors, not shared query difficulty [READ, S7]. A good quality estimator is "the critical factor" for routing and cascading [READ, S8]. Small and large models make correlated errors, so early abstention cut cost by 13.0% and errors by 5.0% [READ, S9]. Decision: tier 0 is deterministic tools; tier 1 is one LLM call or a short agent. The escalation trigger is "two independent witnesses disagree" or "a precondition failed", not model self-confidence. Criteria: cost, accuracy. [S7, S8, S9]

6. **Models do not reliably know when they do not know. Build "I do not know" from explicit checks.** Reasoning fine-tuning "degrades abstention (by 24% on average)", and scaling is "of little use" [READ, S10]. The best of 17 agents reached 59.5% paired accuracy on act-versus-abstain tasks, and abstention is "largely independent of general task-solving capability" [READ, S11]. Code interpreters (verification tools) reduce overconfidence; evidence tools such as search increase it [READ, S12]. Decision: return "I do not know" from deterministic preconditions: no scale bar or dimension, no DXF layer, unit missing, two witnesses disagree, a question that parses to no known operation. Report a confidence derived from these checks. Criteria: verification, accuracy on the hidden set. [S10, S11, S12]

7. **Offline program induction against the answer key works, but it learns the generator's conventions, and tests alone do not catch the shortcuts.** A training-free loop that tests repaired programs against ground truth and keeps "portable skills" raised GPT-5.6-luna from 43% (bare interpreter) to 67% on 30 task families with disjoint learning and evaluation splits [READ, S13]. Code synthesis over documents is cheap but less accurate than direct LLM extraction unless many candidate functions are ensembled; that gave a 110x token reduction [READ, S14]. Against this: programs with "wrong semantics but correct denotation" are a known failure of answer-supervised program search [READ, S15]; about 34.4% of coding-agent trials that passed fixed tests violated the task [READ, S16]; Claude Code and Codex showed "explicit reward hacking" such as hard-coded test cases [READ, S17]. Our own answer key states conventions in the answers, for example "Summing the stored GSA Space Areas.GSA BIM Area values ... gives 7,517.262 sq ft" [MEASURED, local `questions.jsonl`]. Decision: we can let a strong model induce one solver per question family, but hold out by drawing and by template, forbid literal answer constants, and write each convention down as a named, visible rule. Criteria: accuracy, generalization. [S13-S17]

8. **Deterministic replay needs recorded LLM outputs and deterministic executors. Sampling settings no longer give it.** The current Claude API version returns a 400 error for `temperature`, `top_p` or `top_k` on every model from API version 2026-10-21 [READ, S22]. So a run cannot be made repeatable through temperature 0. An audit of agent replay showed that hidden state breaks replay: resetting the random-number generator before each interaction raised replay-admissible cases from 42 to 68 of 71 [READ, S18]. Turning logged agent runs into code workflows kept 93.8% task completion (agent: 96.8%) at 24% lower cost per task [READ, S19]. Decision: cache every LLM output by a hash of its exact input, make all tools pure functions of the file, and "freeze" frequent agent paths into code. Criteria: verification, cost.

9. **For the templated multilingual questions, use rules plus a closed DSL, and keep an LLM parser only for misses.** A fine-tuned encoder beat Claude Haiku zero-shot on a stable closed intent set (95.9 vs 84.1) at about three orders of magnitude lower cost, but the LLM won on out-of-scope recall (85.6 vs 58.1) and on new intents (about 94% vs 0%) [READ, S23]. The ifc-bench agent matched English "outer walls" to German "Aussenwande" and Norwegian level names with "no explicit translation modules" [READ, S1]. Decision: regex and template lookup first, then an LLM that fills the same typed DSL with strict JSON output, and a "no matching operation" output that routes to the agent. Criteria: cost, hidden-set generalization to new languages and templates.

10. **AEC-specific benchmarks agree that symbol counting is the weak point of frontier models.** Door and window counting "remains unsolved (often 0.40-0.55 accuracy)" while OCR-style QA reaches up to 0.95 [READ, S24]. On counting with decoys, "more capable models, greater thinking budgets, and agentic processes often induce larger gaps" [READ, S25]. The best model passes 30.7% of professional PDF items; "miscounted floor-plan symbols" is a named loss pattern [READ, S26]. Decision: counts on raster plans need a trained detector or exact vector data, not a bigger agent. Criterion: accuracy (cubicasa is 67% of public questions by the LEAD counts).

## Landscape

### A. Code-writing agents for visual and geometric QA

| Approach | Year | What it does | Measured result | Licence, code | Fit for us |
|---|---|---|---|---|---|
| VisProg [S27] | 2022 | LLM writes a modular program that calls vision models | No training; interpretable rationale | Apache-2.0, code on GitHub | Precedent for "program as evidence" |
| ViperGPT [S28] | 2023 | LLM writes Python against a vision API | SOTA on several VQA tasks at the time | GitHub licence: NOASSERTION | Same; licence unclear |
| Visual Sketchpad [S29] | 2024 | Model draws lines, boxes, marks and calls detectors | +12.7% on math tasks, +8.6% on vision tasks (avg.) | Apache-2.0 | Drawing marks as evidence fits "verify in seconds" |
| PyVision [S30] | 2025 | Model invents Python tools at run time | +7.8% GPT-4.1 on V*, +31.1% Claude-4.0-Sonnet on VLMsAreBlind-mini | No licence on GitHub: do not copy code | Idea only |
| Thyme [S31] | 2025 | SFT (500K samples) + RL to write image-processing code | Gains on about 20 benchmarks | Apache-2.0 | Too costly to train this weekend |
| RECODE [S32] | 2025 | "Derender" the image into code, then compute | Beats crop-only and line-drawing code on CharXiv, ChartQA, Geometry3K | Not checked | Analogue: vectorize plan, then compute |
| Draw2Think [S33] | 2026 | Propose-Draw-Verify loop with GeoGebra constraint engine | 95.9% predicate-level construction checks; +4.1/16.4% accuracy planar/solid | Not checked | LLM + exact solver hybrid; pattern for area and length checks |
| Self-evolving Code-with-Image [S13] | 2026 | Interpreter only; reflection loop keeps tested "skills" | below 30% (CoT) -> 43% (interpreter) -> 67% (skills), disjoint splits | Not checked | Pattern for offline solver induction |
| VLM-in-Sandbox [S34] | 2026 | Bounded visual workspace for crops and overlays | 66.27% at 18.6% fewer tokens than retain-all | Not checked | Keep image context bounded in any agent |
| ChartAgent [S35] | 2025 | Chart-specific vision tools in an agent loop | +16.07% absolute on ChartBench/ChartX | Not checked | Domain tools help when tasks are visual-numeric |

Negative evidence in this lineage: [S4] (illusion of tool use), [S5] (pixels redundant), [S25] (agentic processes enlarge counting gaps), [S6] (rendering images did not help Codex on visual AEC tasks).

### B. LLM plus structured representation (compile once, query many)

| System | Domain | Representation | Measured result | Cost data |
|---|---|---|---|---|
| ifc-bench v2 / adaptive exploration [S1] | IFC | Raw IFC via IfcOpenShell, agent discovers schema | +36.8-38.5 pp over static; 55.4-56.6% strict accuracy (GLM 4.7) | Not reported in the parts I read |
| IfcLLM [S36] | IFC | Relational + graph backends, query routed by type | 96% on 30 scenarios, 3 models | Not checked |
| IFC-MCQ [S37] | IFC | Auto-generated multiple choice from file | "performance can vary with the source IFC model and retrieval interface" | - |
| ChatP&ID [S2] | P&ID (DEXPI) | Knowledge graph + GraphRAG tools | +18% vs images; 91% GPT-5-mini + ContextRAG | $0.004 per task; tokens -85% |
| Graph-Grounded Harness [S3] | P&ID images | Recovered evidence graph, 7 read-only operators | 36.7-41.3% -> 74.3-76.0% EM (4B-8B VLMs) | Small open models |
| AEC-Bench [S6] | Construction PDFs | Coding-agent harness + parsed sheets | Parsing +32.2 pts on retrieval-heavy review; hurts visual tasks | - |
| EVAPORATE [S14] | Semi-structured docs | LLM writes extraction functions, ensemble with weak supervision | Beats SOTA; 110x fewer LLM tokens | Sublinear LLM passes |
| BatchDAG [S38] | Enterprise data | LLM plans a typed DAG, deterministic engine runs it | Quality 3.74/5 vs ReAct 3.09/5 | $0.02-$0.24 per query |
| Read Once, Answer Many [S39] | Long docs, self-hosted | Decode many questions over one shared KV cache | 3.7x-6.0x faster than SGLang | Self-hosted only |

### C. Cost levers: caching, batch, routing

| Source | Claim | Note for us |
|---|---|---|
| FrugalGPT [S40] | Matches GPT-4 "with up to 98% cost reduction" | 2023 models; chat tasks |
| RouteLLM [S41] | Cuts cost "by over 2 times in certain cases" | Router trained on chat preference data; not drawings |
| Cascade depth [S7] | No gain beyond two tiers in 118/135 comparisons | Two tiers |
| Cascade routing [S8] | Quality estimator is the critical factor | Our estimator: verifier agreement |
| Early abstention [S9] | -13.0% cost, -5.0% errors, +4.1% abstention | Correlated errors between sizes |
| UCCI [S42] | Calibrated router -31% cost at same F1 on 75k NER queries; beats FrugalGPT-style threshold | Calibration on our dev set |
| AgentRouter [S43] | Step-level routing -72% cost, 97.3% of frontier quality; RouteLLM 31%, FrugalGPT 44% per-step | One paper, self-reported |
| Scout before you route [S44] | Predicting output length saves 9-33% at matched accuracy | Reasoning output length varies 10x |
| RouterXBench [S45] | Prior router evaluations overlook out-of-distribution robustness | Hidden set is OOD for any trained router |

### D. Prices read on 2026-11-13 (USD per million tokens)

| Model | Input | Output | Cache read | Cache write | Batch | Source |
|---|---|---|---|---|---|---|
| Claude Opus 5.5 | 4.00 | 20.00 | 0.20 | 5.00 (5 min), 8.00 (1 h) | 2.00 / 10.00 | [S20] |
| Claude Sonnet 5.5 | 2.00 | 10.00 | 0.10 | 2.50 / 4.00 | 1.00 / 5.00 | [S20] |
| Claude Haiku 5.5 (prompt <= 100k) | 0.10 | 0.50 | 0.01 | 0.125 / 0.20 | 0.05 / 0.25 | [S20] |
| gpt-6.1-sol | 2.00 | 10.00 | 0.10 | 2.50 (30 min) | 1.00 / 5.00 | [S21] |
| gpt-6.1-terra | 1.00 | 5.00 | 0.05 | 1.25 | 0.50 / 2.50 | [S21] |
| gpt-6-luna | 0.10 | 0.50 | 0.01 | 0.125 | 0.05 / 0.25 | [S21] |
| Gemini 4 Carbon / Argon | 2.00 to 30 Nov, then 4.00 | 10.00, then 20.00 | 0.10, then 0.20 (implicit only) | - | Batch 50% | [S46] |
| Gemini 3.8 Flash | 0.75 to 31 Dec, then 1.50 | 3.75, then 7.50 | not read | - | - | [S46] |

Other facts [READ, S20, S47]: a Claude image costs `ceil(w/28) x ceil(h/28)` tokens; Claude 4.7 and later accept up to 2,576 px long edge and 4,784 image tokens. Server-side code execution is free with web tools, otherwise 1,550 free hours per month and then $0.05 per container hour. The tool-use system prompt adds 286 tokens on Opus 5.5, Sonnet 5.5 and Haiku 5.5.

### E. Cost per question of an agent loop [ESTIMATE]

Assumptions: system prompt and tools 3,000 tokens; one page image 4,784 tokens; question 100 tokens; each turn 400 output tokens (including thinking) and a 900-token tool result; final answer 300 tokens; 5-minute cache on every turn; the same token counts for all vendors (image tokenization differs per vendor). Script: `cost.py` in my scratchpad; the numbers below are its output.

| Model | 0 tool calls | 10 calls | 15 calls | 20 calls | 15 calls, no cache |
|---|---|---|---|---|---|
| Claude Opus 5.5 | $0.045 | $0.218 | $0.314 | $0.416 | $1.255 |
| Claude Sonnet 5.5 / gpt-6.1-sol | $0.023 | $0.109 | $0.157 | $0.208 | $0.627 |
| gpt-6.1-terra | $0.011 | $0.055 | $0.079 | $0.104 | $0.314 |
| Claude Haiku 5.5 / gpt-6-luna | $0.001 | $0.006 | $0.009 | $0.012 | $0.031 |
| Gemini 3.8 Flash (no cache price read) | $0.007 | $0.135 | $0.235 | $0.360 | $0.235 |

Batch halves each figure but is unusable for an interactive loop. If thinking adds 2,000 output tokens per turn, the Opus 15-call figure roughly doubles. Compiled path: one Sonnet 5.5 call per drawing (7,884 input, 2,000 output) costs about $0.036; per question that is $0.0020 on cubicasa (17.9 questions per drawing) and $0.0010 on swiss_dwellings (36.1 per floor) [ESTIMATE; questions per drawing from LEAD counts]. A Haiku 5.5 template-miss parse with a cached 3,000-token prompt costs about $0.00007; uncached about $0.0003 [ESTIMATE].

### F. How each approach degrades on a harder hidden set

| Approach | Unseen template | Unseen language | Unseen source or style | Failure mode | Graceful? |
|---|---|---|---|---|---|
| Template lookup + exact executors | Fails (no match) | Fails unless slots are language-free | Executor may not exist (for example a scan with no vectors) | Silent wrong parse if lookup is fuzzy | Yes, if a miss routes on and does not guess |
| LLM parser to closed DSL [S23] | Good if the operation exists in the DSL | Good | Not its job | Out-of-DSL question forced into a near operation | Yes, with a "no operation" output |
| Compiled fact store + query [S2, S3] | Good if the fact exists | Good | Depends on extractor; errors track extractor F1 [S3] | Wrong facts look certain | Partly; needs witnesses |
| Code agent over IFC [S1] | Good (+37 pp over static) | Good (no translation module) | Good on new IFC schemas | Cost, long loops, wrong conventions | Yes, at a price |
| Crop/zoom VLM agent [S4, S5] | Good in principle | Good | Weak on dense symbols [S6, S24] | Confident wrong counts, high cost | No |
| Offline-induced solvers [S13] | Fails outside the family | Fine | Overfits generator conventions [S15-S17] | Right answers for wrong reasons | Only with family-disjoint validation |
| Learned router [S45] | Uncertain | Uncertain | OOD robustness often untested | Mis-routing | Use verifier signals instead |

## What we can use this weekend

| Item | What | Licence, availability | Effort | Use |
|---|---|---|---|---|
| IfcOpenShell | Python IFC parser and geometry | LGPL-3.0 [S48], `pip install ifcopenshell` | 0 h | Executor for IFC facts and the IFC agent |
| cobbie (ifc-bench v2 agent code) | Adaptive exploration agent | Paper: CC-BY-4.0 [S1]; GitHub licence field: NOASSERTION [S48] | 2-4 h to read and port the loop | Reference design for our IFC agent; check its licence file before copying |
| ifc-bench v2 dataset | 1,027 QA (paper) with a 514-question test split | CC-BY-4.0 on Hugging Face [S1, S48] | 1 h | Extra dev data. Warning: our `ifc_bench` questions come from it, so tuning on it is tuning on public answers |
| AEC-Bench harness | Coding-agent harness and verifiers for construction PDFs | Apache-2.0 [S6, S48] | 2 h | Ideas for task verifiers and output contracts |
| Visual Sketchpad | Drawing marks and detector calls in a loop | Apache-2.0 [S48] | 2-3 h | Overlay numbered marks as evidence images |
| VisProg | Program-as-rationale | Apache-2.0 [S48] | Idea only | Evidence trace format |
| Claude API caching + Batch | Cache reads 0.05x on Opus/Sonnet 5.5; Batch -50% | Available today [S20] | 1 h | Mandatory for every LLM call; Batch for eval runs and compile passes |
| Claude strict tool use / structured outputs | Typed DSL from free text | Available today [S22] | 1-2 h | Template-miss parser |
| Record and replay cache | Hash(model, prompt, image bytes) -> stored output | Our code | 2 h | Deterministic replay for judges and regression tests |
| Offline solver induction | Strong model writes and tests one solver per family | Our code | 4-8 h | Only with drawing- and template-disjoint folds, no literal constants, named conventions |

Concrete commands:

```sh
pip install ifcopenshell ezdxf shapely   # executors; licences LGPL-3.0, MIT, BSD-3 (ezdxf and shapely licences not re-checked here)
huggingface-cli download sylvainHellin/ifc-bench --repo-type dataset --local-dir data/ifc-bench   # CC-BY-4.0
git clone https://github.com/Nomic-ai/aec-bench   # Apache-2.0
```

Suggested shape (from findings 1-9):

1. Router by file type and template lookup (no LLM).
2. Compiled fact store per drawing, with two witnesses per fact where possible (for example DXF polygon area and printed area label).
3. A deterministic answer with its evidence and a confidence from the checks.
4. On a miss or a disagreement: one LLM step. A Haiku-class model fills the DSL; for IFC, a Sonnet-class code agent with a hard cap of about 10-15 runs.
5. "I do not know" when preconditions fail.
6. Every LLM output recorded for replay.

## What does not work

- **Static single-pass code generation for heterogeneous IFC (the paper's "static" baseline).** It abstains on about half of the questions and on 75.4% of the questions that need a geometric property that is not stored in the model [READ, S1].
- **Hand-made domain tool libraries for a weaker agent model.** Accuracy fell from 25.7% to 15.4%; abstention reached 50.6% [READ, S1]. Documentation retrieval gave the strong model +0.6 pp (not significant) [READ, S1].
- **Crop-and-zoom as a general fix for perception.** Marginal or negative gains at higher token cost [READ, S4]; returned pixels often carry no signal [READ, S5].
- **More thinking or more agent steps for counting.** They often enlarge the reasoning-alignment gap on counting with decoys [READ, S25].
- **Parsed text for visual-spatial sheet tasks.** On AEC-Bench, parsing hurt note-callout and cross-reference tasks [READ, S6]; 77% of trajectories called `pdftotext`, which "collapses spatial layout" [READ, S6].
- **Cascades deeper than two tiers** [READ, S7].
- **Model self-reported confidence as the abstention signal** [READ, S10, S11]. Evidence tools such as web search increase overconfidence [READ, S12].
- **Generic memory systems for BIM agents.** The best reached 32.4% answer accuracy [READ, S49]. Not needed for single-question QA.
- **Fixed unit tests as the only check on induced programs.** 34.4% of passing trials violated requirements [READ, S16]; held-out tests gave "only minimal improvement" in detecting hacks [READ, S17].

## Open questions

1. How does Stoa score free-text answers (`ifc_bench`, 836 text rows)? An LLM judge with a rubric like ifc-bench's five criteria would reward cited sources and stated assumptions [S1].
2. Is "I do not know" scored as wrong, as neutral, or as a positive? This sets the abstention threshold.
3. Does the inference-cost criterion count a one-time compile pass per drawing, or only per-question calls? Compile-once wins by 100x only if compile cost is amortized.
4. Does the hidden set reuse public drawings with new questions, or new drawings? Compile-once helps most in the first case.
5. For historic scans with no questions (habs, finna, europeana, wikimedia), which question types should we expect? No source I read covers agentic QA on historic hand-drawn scans.
6. Can we get vendor numbers for built-in code-execution vision (OpenAI "thinking with images", Gemini agentic vision)? I could not open those pages.

## Check of the prior research

I read `weekend-plan.md` sections 1-2 and the two tracks in `research-tracks.json` that cover routers, cascades, caching, agents and question parsing.

| Prior claim | Verdict | Evidence |
|---|---|---|
| Evidence graph raised P&ID exact match "from about 39% to about 75%" (2609.05880) | Confirmed. Exact: 36.7-41.3% -> 74.3-76.0%, with 4B-8B open VLMs; recovered graph F1 0.742 | [S3] |
| "Deeper cascades gave no gain in 118 of 135 comparisons" (2605.06350) | Confirmed; also "adds at most 0.43 percentage points" | [S7] |
| ifc-bench "rubric (exact counts, 2%, cited properties) matches Stoa's scoring" | **Not supported.** The paper scores with an LLM judge on five binary criteria (abstention, faithfulness, completeness, transparency, relevance). It has no 2% rule | [S1] |
| "GLM-4.7 reached 56%" on ifc-bench | Confirmed: 55.4-56.6% across four augmentation settings, on the 514-question test split | [S1] |
| CodeAct agent on Sonnet 5.5 will reach 55-65% on ifc_bench | Unsourced estimate. Stoa's scoring of text answers is unknown | - |
| IFC-Bench HF dataset has "1,026 QA pairs over 51 IFC models in 22 projects" | Conflicts with the paper: 1,027 tasks, 37 IFC models, 21 projects. I did not open the CSV. Unverified | [S1] |
| Abstract of 2605.01698 "gives no accuracy numbers or model names" | True for the abstract; the full paper has them (GLM 4.7, GLM 4.5 Air, +36.8-38.5 pp) | [S1] |
| Claude prices (Opus 5.5 $4/$20, cache read $0.20, write $5; Haiku 5.5 $0.10/$0.50, cache read $0.01; Batch -50%) | Confirmed | [S20] |
| "Minimum cacheable prefix 286 tokens" | **Wrong.** 286 tokens is the tool-use system prompt size on Opus 5.5, Sonnet 5.5 and Haiku 5.5 | [S20] |
| Image tokens `ceil(w/28) x ceil(h/28)`, max 2,576 px and 4,784 tokens | Confirmed | [S47] |
| Haiku 5.5 template-miss parse "about $0.0003" | Plausible for an uncached 3k prompt; about $0.00007 with a cached prompt [ESTIMATE] | [S20] |
| "Opus everywhere costs about $0.10-0.19 per question" | Unsourced. My estimate: $0.045 for one call with one image, $0.31 for a 15-call loop with caching | Section E |
| FrugalGPT "up to 98% cost reduction" | Confirmed from the abstract | [S40] |
| RouteLLM "up to 85% cost reduction while keeping 95% of GPT-4 quality" (README) | Not checked (README not opened). The abstract says "over 2 times in certain cases" | [S41] |
| Early-abstention cascade figures (-2.2% loss, -13% cost, -5% error, +4.1% abstention) | Confirmed | [S9] |
| Cascade routing: quality estimator is the key factor | Confirmed | [S8] |
| Fine-tuned encoder vs Claude Haiku (ATIS 95.9 vs 84.1; OOS 85.6 vs 58.1; new intents ~94% vs 0%) | Confirmed | [S23] |
| ViperGPT has "No repo on GitHub" | Wrong: `cvlab-columbia/viper` exists (licence field NOASSERTION) | [S48] |
| AECV-Bench door and window counting "often 0.40-0.55 accuracy" | Confirmed | [S24] |

## Sources

All sources opened on 2026-11-13. arXiv quotes are from the abstract or the full HTML text of the version served on that date.

| id | URL | title | date | the claim it supports | exact supporting quote | check |
|---|---|---|---|---|---|---|
| S1 | https://arxiv.org/abs/2605.01698 | BIM Information Extraction Through LLM-based Adaptive Exploration (Hellin et al.) | 2026-05-03 | Code agent beats static by 37 pp; abstention; tools hurt weak model; multilingual matching; LLM-judge rubric | "Adaptive-4.7 outperforms Static-4.7 by +36.8–38.5 pp across all completed augmentation strategies"; "Static-4.7 abstains on roughly half the benchmark even when tools are available, while Adaptive-4.7 abstains on fewer than 7% of questions"; "For GLM 4.5 Air, manual tools are harmful. Accuracy drops from 25.7% to 15.4%"; "No explicit translation modules are required"; "Each answer is evaluated against five binary criteria" | confirmed (abstract and full HTML). "Static" in the paper means single-pass code generation, not a fixed NL-to-query translator; the 55.4-56.6% is Adaptive-4.7 with GLM 4.7; the 10.2 pp drop and 75.4% static abstention on geometric-property questions are in the full text |
| S2 | https://arxiv.org/abs/2603.22528 | GraphRAG for Engineering Diagrams: ChatP&ID (Alimin, Schweidtmann) | 2026-03-23 | Graph representation: more accurate, cheaper | "graph-based representations improve accuracy by 18% over raw image inputs and reduce token costs by 85%"; "GPT-5-mini combined with ContextRAG achieves 91% accuracy at a cost of only $0.004 per task" | confirmed |
| S3 | https://arxiv.org/abs/2609.05880 | Grounded and Faithful P&ID Reasoning (Gadekar et al.) | 2026-09-05 | Evidence graph doubles exact match; errors track extraction | "raises exact match accuracy from 36.7--41.3% under image-only prompting to 74.3--76.0%"; "The residual errors track that gap" | confirmed |
| S4 | https://arxiv.org/abs/2608.06270 | The Illusion of Visual Tool-Use (Wang et al.) | 2026-08-06 | Crop/zoom gains marginal, costly | "models using these operations often achieve only marginal or negative gains over direct inference at substantially higher token cost" | confirmed |
| S5 | https://arxiv.org/abs/2608.09682 | Thinking With Tools, Not With Pixels (Shao et al.) | 2026-08-10 | Returned pixels redundant | "TextCall matches or exceeds full thinking-with-images" | confirmed |
| S6 | https://arxiv.org/abs/2603.29199 | AEC-Bench (Mankodiya et al., Nomic) | 2026-03-31 | Retrieval bottleneck; parsing helps text tasks, not visual; images did not help | "Text-catchable instances achieve near-perfect performance (mean reward 100%), while visual-required instances achieve only 5%"; "this increased use of image rendering does not lead to better performance on visually grounded tasks"; "77% of trajectories invoke pdftotext" | confirmed (full HTML); parsing deltas: note-callout -3.6, cross-reference-resolution -2.4 points |
| S7 | https://arxiv.org/abs/2605.06350 | Is Escalation Worth It? On the Depth of LLM Cascades (Bouchard) | 2026-05-07 | Two tiers enough | "allowing more than two models does not improve mean test-set accuracy in 118 of 135 comparisons" | confirmed |
| S8 | https://arxiv.org/abs/2410.10347 | A Unified Approach to Routing and Cascading for LLMs (Dekoninck et al.) | 2024-10-14 | Quality estimator decides | "we identify good quality estimators as the critical factor for the success of model selection paradigms" | confirmed |
| S9 | https://arxiv.org/abs/2502.09054 | Cost-Saving LLM Cascades with Early Abstention (Zellinger et al.) | 2025-02-13 | Correlated errors; early abstention | "trading a 4.1% average increase in the overall abstention rate for a 13.0% reduction in cost and a 5.0% reduction in error rate" | confirmed |
| S10 | https://arxiv.org/abs/2506.09038 | AbstentionBench (Kirichenko et al.) | 2025-06-10 | Reasoning hurts abstention | "reasoning fine-tuning degrades abstention (by $24\%$ on average)" | confirmed |
| S11 | https://arxiv.org/abs/2607.10059 | AgentAbstain (Liu et al.) | 2026-07-11 | Agents abstain poorly; independent of capability | "the best agent (Gemini 3.1 Pro) achieves only 59.5% paired accuracy"; "abstention capability is largely independent of general task-solving capability" | confirmed |
| S12 | https://arxiv.org/abs/2601.07264 | The Confidence Dichotomy (Xuan et al.) | 2026-01-12 | Code tools improve calibration | "verification tools (e.g., code interpreters) can ground reasoning through deterministic feedback and mitigate miscalibration" | confirmed |
| S13 | https://arxiv.org/abs/2608.11292 | Self-Evolving Code-with-Image Reasoning (Yang et al.) | 2026-08-11 | Tested skill induction on disjoint splits | "given a bare interpreter it reaches 43%, and with skills evolved through its own executable reflection, 67%" | corrected: abstract says GPT-5.6-luna "stays below 30%" tool-free (not exactly 30%) and that the 30 task families have disjoint learning and evaluation splits (not "held-out families") |
| S14 | https://arxiv.org/abs/2304.09433 | EVAPORATE (Arora et al.) | 2023-04-19 | Code synthesis cheap but less accurate; ensembles fix it | "Code synthesis is cheap, but far less accurate than directly processing each document with the LLM"; "110x reduction in the number of tokens" | confirmed |
| S15 | https://arxiv.org/abs/2311.01161 | Weakly Supervised Semantic Parsing with Execution-based Spurious Program Filtering (Lee et al.) | 2023-11-02 | Answer-supervised programs can be spurious | "programs that have wrong semantics but correct denotation" | confirmed |
| S16 | https://arxiv.org/abs/2610.10619 | TestJack (Yao et al.) | 2026-10-07 | Passing tests is not correctness | "about 34.4% of the model trials currently judged correct violate the task requirements" | confirmed |
| S17 | https://arxiv.org/abs/2511.21654 | EvilGenie: A Reward Hacking Benchmark (Gabor et al.) | 2025-11-26 | Coding agents hack tests | "We observe explicit reward hacking by both Codex and Claude Code"; "only minimal improvement from the use of held out test cases" | confirmed |
| S18 | https://arxiv.org/abs/2611.11216 | Replay Fidelity in LLM Agent Evaluation (Liu, Lu) | 2026-11-08 | Hidden state breaks replay | "resetting the random-number generator before each interaction admits 68" (of 71; declared settings admit 42) | confirmed |
| S19 | https://arxiv.org/abs/2611.14492 | ReTrace: Distilling Tool-Using Agents into Planner-Free Workflows (Hou et al.) | 2026-11-10 | Freeze agent paths into code | "ReTrace workflows reach $93.8\%$ completion, against $96.8\%$ for the agent, at $24\%$ lower cost per task" | confirmed (93.8 / 96.8 / 24% found in the full HTML text) |
| S20 | https://platform.claude.com/docs/en/about-claude/pricing.md | Pricing (Anthropic) | read 2026-11-13 | Claude prices, Batch, code execution, tool tokens | "Claude Opus 5.5 \| $4 / MTok \| $5 / MTok \| $8 / MTok \| $0.20 / MTok \| $20 / MTok"; "The Batch API allows asynchronous processing of large volumes of requests with a 50 percent discount on both input and output tokens."; "Additional usage beyond 1,550 hours is billed at **$0.05 USD per hour, per container**"; "Claude Opus 5.5 \| 286 tokens" (tool use system prompt tokens) | confirmed |
| S21 | https://developers.openai.com/api/docs/pricing | Pricing (OpenAI) | read 2026-11-13 | OpenAI prices | standard row gpt-6.1-sol: input $2, cached input $0.10, cache write $2.50, output $10 (page data, column order differs from the string first quoted here); batch row: input $1, cached $0.05, write $1.25, output $5 | corrected: prices confirmed (sol 2/10, cache read 0.10, write 2.50; batch 1/5; terra 1/5; luna 0.10/0.50), but the quoted string lists columns in a different order than the page; the page row is input 2, cached input 0.10, cache write 2.50, output 10 |
| S22 | Local copy of Anthropic docs: claude-api skill `shared/api-version-migration.md` (cached 2026-11-03), source page https://platform.claude.com/docs/en/api/versioning.md (opened in verification) | API version migration (Anthropic) | 2026-11-03 | Sampling parameters removed | "remove `temperature`, `top_p` and `top_k` from the Messages requests"; skill index: "On `2026-10-21`, a Messages request sending `temperature`, `top_p` or `top_k` returns a 400 on every model" | confirmed: the source page https://platform.claude.com/docs/en/api/versioning.md was opened; it lists "temperature, top_p, and top_k request parameters removed" and a 400 on every model under version 2026-10-21. The change applies when a request sends that version header. The local skill copy was not re-read |
| S23 | https://arxiv.org/abs/2608.20371 | When Do LLMs Replace Fine-Tuned NLU? (Rodrigues, Vas) | 2026-06-19 | Encoder vs LLM parser trade-off | "on ATIS it beats Claude zero-shot by 11.8 points (95.9 vs. 84.1, p<0.001)"; "OOS recall 85.6 vs. 58.1"; "serves both at ~94% with zero retraining" | confirmed |
| S24 | https://arxiv.org/abs/2601.04819 | AECV-Bench (Kondratenko et al.) | 2026-01-08 | Counting unsolved | "reliable counting of doors and windows - remains unsolved (often 0.40-0.55 accuracy)" | confirmed |
| S25 | https://arxiv.org/abs/2610.34855 | DecoyCount (Zhang et al.) | 2026-10-26 | More reasoning/agents can hurt counting | "more capable models, greater thinking budgets, and agentic processes often induce larger gaps" | confirmed |
| S26 | https://arxiv.org/abs/2607.11192 | GDP.pdf (Garre et al.) | 2026-07-13 | Professional PDFs hard; floor-plan symbol miscounts | "the best model passes only 30.7% of the items"; "miscounted floor-plan symbols" | confirmed |
| S27 | https://arxiv.org/abs/2211.11559 | Visual Programming (VisProg) (Gupta, Kembhavi) | 2022-11-18 | Program as rationale | "executed to get both the solution and a comprehensive and interpretable rationale" | confirmed |
| S28 | https://arxiv.org/abs/2303.08128 | ViperGPT (Surís et al.) | 2023-03-14 | Code composes vision modules | "leverages code-generation models to compose vision-and-language models into subroutines" | confirmed |
| S29 | https://arxiv.org/abs/2406.09403 | Visual Sketchpad (Hu et al.) | 2024-06-13 | Sketching gains | "yielding an average gain of 12.7% on math tasks, and 8.6% on vision tasks" | confirmed |
| S30 | https://arxiv.org/abs/2507.07998 | PyVision (Zhao et al.) | 2025-07-10 | Dynamic tools | "boosting GPT-4.1 by +7.8% on V* and Claude-4.0-Sonnet by +31.1% on VLMsAreBlind-mini" | confirmed |
| S31 | https://arxiv.org/abs/2508.11630 | Thyme: Think Beyond Images (Zhang et al.) | 2025-08-15 | Training cost of code-vision models | "an initial SFT on a curated dataset of 500K samples to teach code generation, followed by a RL phase" | confirmed |
| S32 | https://arxiv.org/abs/2510.13756 | RECODE (Shen et al.) | 2025-10-15 | Derendering to code | "RECODE significantly outperforms methods that do not leverage code or only use code for drawing auxiliary lines or cropping" | confirmed |
| S33 | https://arxiv.org/abs/2605.20743 | Draw2Think (Hu et al.) | 2026-05-20 | LLM + constraint engine | "builds canvases that pass 95.9% predicate-level and 84.0% strict problem-level construction checks" | confirmed |
| S34 | https://arxiv.org/abs/2609.24362 | VLM-in-Sandbox (Yang et al.) | 2026-09-21 | Bounded visual context | "reaches 66.27% accuracy with 18.6% fewer total tokens than the automatic, retain-all control" | confirmed |
| S35 | https://arxiv.org/abs/2510.04514 | ChartAgent (Kaur et al.) | 2025-10-06 | Domain visual tools | "surpassing prior methods by up to 16.07% absolute gain overall" | confirmed |
| S36 | https://arxiv.org/abs/2605.13236 | IfcLLM (Lamsal et al.) | 2026-05-13 | Route by representation | "the top-performing configuration achieved 96% accuracy" (30 scenarios, three IFC models) | confirmed |
| S37 | https://arxiv.org/abs/2610.30533 | IFC-MCQ (Lamsal et al.) | 2026-10-21 | Results depend on model and interface | "performance can vary with the source IFC model and retrieval interface" | confirmed |
| S38 | https://arxiv.org/abs/2607.18241 | BatchDAG (Walia) | 2026-04-17 | LLM plans, deterministic engine runs | "measured per-query costs of $0.02-$0.24 at published GPT-5.1 pricing" | confirmed |
| S39 | https://arxiv.org/abs/2611.15130 | Read Once, Answer Many (Zhao, Flanigan) | 2026-11-11 | Many questions per document | "Parallel Prompting is 3.7x faster than stock SGLang" | confirmed |
| S40 | https://arxiv.org/abs/2305.05176 | FrugalGPT (Chen et al.) | 2023-05-09 | Cascade savings | "FrugalGPT can match the performance of the best individual LLM (e.g. GPT-4) with up to 98% cost reduction" | confirmed |
| S41 | https://arxiv.org/abs/2406.18665 | RouteLLM (Ong et al.) | 2024-06-26 | Router savings | "significantly reduces costs-by over 2 times in certain cases-without compromising the quality of responses" | confirmed |
| S42 | https://arxiv.org/abs/2605.18796 | UCCI (Kotte) | 2026-05-11 | Calibrated cascade | "UCCI cuts inference cost by 31% (95% CI: [27%, 35%]) at micro-F1 = 0.91" | confirmed |
| S43 | https://arxiv.org/abs/2609.22951 | AgentRouter (Paul, Nandy) | 2026-09-19 | Step-level routing | "AgentRouter achieves 72% cost reduction relative to frontier-only baselines, retaining 97.3% of frontier-only quality" | confirmed |
| S44 | https://arxiv.org/abs/2611.09028 | Scout Before You Route (Milios, Pal) | 2026-11-06 | Predict output length | "our predicted costs save 9-33% at matched accuracy relative to median-length pricing" | confirmed (abstract: 9-33% saving; output length "varies order of magnitude") |
| S45 | https://arxiv.org/abs/2602.11877 | RouterXBench (Wu et al.) | 2026-02-12 | Router OOD robustness under-tested | "Existing router evaluations are unsystematic, overlooking scenario-specific requirements and out-of-distribution robustness" | confirmed: arXiv title is "Towards Fair and Comprehensive Evaluation of Routers in Collaborative LLM Systems"; RouterXBench is the benchmark name inside the paper |
| S46 | https://ai.google.dev/gemini-api/docs/pricing | Gemini Developer API pricing (Google) | read 2026-11-13 | Gemini prices | "$2.00 through November 30, 2026. $4.00 starting December 1, 2026." (Gemini 4 Carbon input); "Batch API (50% cost reduction)" | confirmed |
| S47 | https://platform.claude.com/docs/en/build-with-claude/vision.md | Vision (Anthropic) | read 2026-11-13 | Image token formula and limits | "An image, therefore, costs `⌈width / 28⌉ × ⌈height / 28⌉` visual tokens."; "High-resolution \| Claude 4.7 and later models \| 2,576 px \| 4,784" | confirmed |
| S48 | GitHub API (`api.github.com/repos/...`, `gh api`) and https://huggingface.co/api/datasets/sylvainHellin/ifc-bench | Repository metadata | read 2026-11-13 | Licences | IfcOpenShell "LGPL-3.0"; Nomic-ai/aec-bench "Apache-2.0"; Yushi-Hu/VisualSketchpad "Apache-2.0"; allenai/visprog "Apache-2.0"; cvlab-columbia/viper "NOASSERTION"; lm-sys/RouteLLM "Apache-2.0"; yfzhang114/Thyme "Apache-2.0"; agents-x-project/PyVision licence null; sylvainHellin/cobbie "NOASSERTION"; ifc-bench dataset "cc-by-4.0" | confirmed: all nine GitHub licences re-read with the GitHub API and the Hugging Face dataset card says cc-by-4.0; the cobbie CC-BY-4.0 claim is in the S1 full text |
| S49 | https://arxiv.org/abs/2607.26072 | IFCMemoryBench (Du et al.) | 2026-07-13 | Memory systems weak on BIM | "The strongest system achieves only 32.4% answer accuracy under a deployment-realistic ingestion scope" | confirmed |

## Verification

Checked on 2026-11-13 by an independent fact checker. Method: arXiv abs pages and, for S1, S6 and S19, the full HTML, fetched with `curl` (the web-fetch tool hit a usage limit); vendor price pages fetched with `curl`; licences from `gh api` and the Hugging Face API.

- Sources opened: 49 of 49 (43 arXiv abstract pages, 3 of them also full HTML; Anthropic pricing, vision and versioning pages; OpenAI pricing; Gemini pricing; 9 GitHub repositories; 1 Hugging Face dataset card).
- Result: every arXiv id exists, and the title, first authors and date match. Every quoted figure was found. 47 confirmed, 2 corrected in the check column (S13, S21) with details in the column. No source is NOT FOUND, so no finding is marked UNVERIFIED. The earlier note about the OpenAI "thinking with images" and Google "agentic vision" pages stays open: the checker did not try them, and claims about built-in code-execution vision remain unverified.
- Corrections to the text:
  1. S13: GPT-5.6-luna is "below 30%" with chain of thought, not 30%. The 30 task families have disjoint learning and evaluation splits; they are not "held-out families". Fixed in Finding 7 and in table A.
  2. S21: the quoted OpenAI price string had the columns in the wrong order. The prices in table D are correct. Quote replaced.
  3. S1: the paper's "static" baseline is single-pass code generation, not an NL-to-query translator. The "over 75% of geometric questions" claim is 75.4% of the questions that need a geometric property not stored in the model. Fixed in "What does not work".
  4. S22: the source page was in fact opened in this check; the "(not opened)" note is removed. The parameter removal applies under API version 2026-10-21.
- Notes that are not errors: S45's arXiv title differs from the name RouterXBench (the benchmark name inside the paper). Cost estimates in section E and the 80-150x ratio are the research agent's own arithmetic and were not re-derived here; the ratio follows from its stated figures ($0.157 to $0.314 against $0.002).
- Not checked: the prior-research claim about the Hugging Face dataset size (1,026 QA over 51 models) stays "unverified" as the report says. The local `claude-api` skill copy for S22 and the local counts marked MEASURED or LEAD were not checked.
