# The plan-writing model: API tiers and open models, as of 14 November 2026

Topic: the language model that writes typed plans (or tool calls) over the fact store, with a closed set of about 15 tools.
Date of research: 2026-11-14. All pages were opened on that day.

Verifier note (2026-11-14): 20 claims re-checked against primary pages. The primary recommendation stands. No value was wrong. See "Verification" at the end.

Labels: **SOURCED** = read on a page I opened (id in brackets, see Sources). **ESTIMATE** = my arithmetic or judgement, not a measurement. **UNVERIFIED** = I could not open a primary source.

How I read the evidence: vendor model cards are self-reported. The OpenRouter tau2 board is a third party, but it covers one domain (airline), it mixes model and provider, and its error bars are large. Neither says how a model does on our plan language. Only the 1-hour tests in section 4 say that.

## In short

1. **Open model to train: `Qwen/Qwen3.5-9B`** (9.65B dense, Apache-2.0, 2026-02-27). It fits one A100 for LoRA SFT (22 GB, Unsloth figure) and for GRPO with vLLM on the same GPU. Its tau2 airline score is 73.4 +/- 4.5 and the vendor BFCL-V4 is 66.1. This is the primary recommendation.
2. **Fallback: `Qwen/Qwen3.8-27B`** (27.8B dense, Apache-2.0, 2026-08-05). It is the newest open model that fits one A100 (tau2 airline 77.5 +/- 2.6). Use it for SFT only. It is about 3 times slower to train and to serve, and RL does not fit on one A100.
3. **API model to run tonight: `claude-haiku-5-5`** at $0.10 in and $0.50 out per million tokens. It has grammar-constrained JSON output and strict tool use. A plan call costs about $0.0003 to $0.0008 (ESTIMATE). Escalate to `claude-sonnet-5-5` ($2 and $10) when the executor rejects a plan twice.
4. **One-night experiment on the 9B: SFT, then rejection-sampled SFT, then a short GRPO run, about 8 A100 hours and about $20** (ESTIMATE). The 27B SFT fallback adds about 3 hours. GEPA on the Haiku prompt runs in parallel and needs no GPU.
5. **RL is a polish step, not the core.** Controlled evidence says LoRA SFT wins in distribution (15 of 18 settings) and GRPO adds under one point out of distribution [C2]. Prompt optimisation matched or beat GRPO with far fewer rollouts on 6 tasks [C3]. Run RL only after SFT works and only on tasks the executor can score exactly. Swap the open model in for Haiku only if it passes the gate in section 3.

## 1. Candidates

### 1.1 Track A: API models

Prices are per million tokens, USD, standard tier, short prompts. Tau2 is the OpenRouter airline board, last run 2026-11-14 [A16]. The user simulator there is `gemini-2.5-flash`. A run that hits the step limit scores 0. Cost and tokens are per task.

| Model (API id) | Input / output | Cache read, batch | Output guarantee | tau2 airline | Cost per tau2 task, output tokens | Notes |
|---|---|---|---|---|---|---|
| Claude Haiku 5.5 (`claude-haiku-5-5`) | $0.10 / $0.50 (over 100K prompt tokens: $0.50 / $2.50) | $0.01; batch $0.05 / $0.25 | Grammar-constrained `output_config.format` json_schema and `strict: true` tools [A6, A7] | 72.8 +/- 4.1 | $0.012, 10.7k | Released 2026-10-07. Effort levels low to max. Adaptive thinking. 1M context [A1, A3] |
| Claude Sonnet 5.5 (`claude-sonnet-5-5`) | $2 / $10 | $0.10; batch $1 / $5 | same | 78.8 +/- 2.2 | $0.16, 6.25k | Escalation tier [A1, A2] |
| Claude Opus 5.5 (`claude-opus-5-5`) | $4 / $20 | $0.20; batch $2 / $10 | same | 75.3 +/- 1.7 | $0.34, 7.04k | Not needed for plans. Fable 5.2 ($8 / $40) is also listed [A1] |
| GPT-6 Luna (`gpt-6-luna`) | $0.10 / $0.50 (over 272K: $0.20 / $0.75) | $0.01; batch $0.05 / $0.25 | Structured Outputs, "constrains completed, non-refusal model output" to the schema [A9, A10, A11] | 67.3 (no spread given) | $0.009, 8.9k | Chat Completions allows function calling only with `reasoning_effort` set to `none`. No fine-tuning [A10] |
| GPT-6.1 Terra (`gpt-6.1-terra`) | $1 / $5 | $0.05; batch $0.50 / $2.50 | same | 68.4 +/- 1.6 | $0.064, 4.74k | [A9, A16] |
| GPT-6.1 Sol (`gpt-6.1-sol`) | $2 / $10 | $0.10; batch $1 / $5 | same | 70.0 | $0.10, 3.64k | [A9, A16] |
| Gemini 3.5 Flash-Lite (`gemini-3.5-flash-lite`) | $0.30 / $2.50 | cache $0.03; batch $0.15 / $1.25 | JSON Schema subset. States and branching limited. `minLength` and similar are stripped, not enforced [A12, A13] | 78.3 +/- 1.0 | $0.074, 21.5k | GA since 2026-07-21 (trackers, secondary). Uses 2 times the output tokens of Haiku in this test |
| Gemini 3.8 Flash (`gemini-3.8-flash`) | $0.75 / $3.75, rising to $1.50 / $7.50 on 2027-01-01 | $0.075 | same | 71.3 | $0.21, 27.6k | [A12, A16] |
| Gemini 4 Hydrogen (`gemini-4-hydrogen`) | $1.50 / $7.50 | $0.075 | same; combining structured output with function calling is a preview [A13] | not on the board | not on the board | Launched 2026-11-12 [A14]. No `flash-lite` in the Gemini 4 line yet [A12] |

Reading of Track A:

- **Haiku 5.5 is the cheapest tier that is also good at tool use.** In the one head-to-head I could open, it beats GPT-6 Luna (72.8 against 67.3), at similar price. The gap between Haiku and Luna is 5.5 points. Haiku's own spread is 4.1 points, so treat this as a lean, not a result.
- Gemini 3.5 Flash-Lite scores higher (78.3 +/- 1.0) but costs 6 times more per task and writes 2 times more tokens. For a single plan call that does not matter much, so it is the cross-vendor spare to test in section 4.
- Anthropic published no tool-use benchmark for Haiku 5.5. Its numbers are for coding, computer use and knowledge work [A4]. One of them has an effort caveat: Terminal-Bench 4.0 39.2% is at max effort and about 20% at default medium effort [A8]. Expect a plan call at `medium` effort to be weaker than the headline numbers.
- **Structured-output limits that matter for a 12-operator plan language (Anthropic, SOURCED [A6]):** at most 20 strict tools, 24 optional parameters in total, 16 parameters with `anyOf` or type arrays, no recursive schemas, no `minimum`, `maxLength` and similar, `additionalProperties` must be `false`, a 180 s compile timeout, first-use latency while the grammar compiles, grammar cache 24 hours. Enum casing is not guaranteed: compare case-insensitively. A refusal or `max_tokens` can still break the schema. Design the plan schema flat: one `op` enum, all fields required, no nulls.
- Haiku 5.5 with thinking off and a JSON format can skip a tool call it needs [A5]. This matters only for a tool loop. For plan-as-JSON, leave thinking on (adaptive) at `low` or `medium`, or force the call with `tool_choice`.
- Haiku 5.5 rejects `temperature`, `top_p` and `top_k` (use the defaults) and rejects `budget_tokens` [A5]. Output is not deterministic, so cache each plan by a hash of its input.
- Cost of one plan call (ESTIMATE): 4,000 input tokens (3,000 cached prefix with the tool spec), 300 output tokens. Haiku: $0.0003 without thinking, about $0.0008 with 1,000 thinking tokens. Luna: the same without thinking. Flash-Lite: about $0.0015. Sonnet 5.5: about $0.005. For a document with 30 questions: Haiku $0.01 to $0.02, which is inside the $0.10 target. Sonnet for every question is not.
- The Claude tokenizer gives about 30% more tokens for the same text than earlier models [A2, A3]. The numbers above already use Claude token counts.

### 1.2 Track B: open models we can serve on one A100 80 GB

Weights size is parameters times 2 bytes (ESTIMATE, arithmetic). "FT fit" is for LoRA on one 80 GB card. Dates are Hugging Face `createdAt` [B4, B12].

| Model id | Params | Licence | Created | Tool-call evidence | FT fit and serve fit | Verdict |
|---|---|---|---|---|---|---|
| `Qwen/Qwen3.5-9B` | 9.65B dense (Gated DeltaNet hybrid) | Apache-2.0 | 2026-02-27 | Vendor: BFCL-V4 66.1, TAU2 79.1 [B2]. OpenRouter airline 73.4 +/- 4.5, but 52.9k output tokens and 20 min per task (it overthinks) [A16] | LoRA bf16 22 GB (Unsloth) [B7]. Weights 19 GB. GRPO with vLLM colocated fits (ESTIMATE) | **Primary** |
| `Qwen/Qwen3.8-27B` | 27.78B dense | Apache-2.0 | 2026-08-05 | OpenRouter airline 77.5 +/- 2.6 [A16]. Card has no BFCL or tau2. It has agent rows (Terminal Bench 2.1 73.0, ClawEval-MM 57.4 Pass@3) [B3] | Unsloth: QLoRA works in 24 GB, LoRA needs more than 36 GB [B8]. For Qwen3.5-27B the Unsloth figure is 56 GB bf16 LoRA [B7]. Weights 56 GB (Unsloth) | **Fallback**, SFT only |
| `Qwen/Qwen3.5-27B` | 27.78B dense | Apache-2.0 | 2026-02-24 | Vendor: BFCL-V4 68.5, TAU2 79.0 [B2] | same as above | Superseded by 3.8 |
| `Qwen/Qwen3.6-35B-A3B` | 35.95B MoE, 3B active | Apache-2.0 | 2026-04-15 | MCP-Atlas 62.8, MCPMark 37.0 [B6]. TRL lists it as tested [B11] | Weights 72 GB: no room for KV cache in BF16. Unsloth LoRA figure for the 3.5 twin is 74 GB. A100 has no FP8 units (secondary) | Skip on one A100 |
| `google/gemma-4-31B-it` | 31.27B dense | Apache-2.0 | 2026-03-11 | Vendor tau2 76.9 (average of 3) [B5]. OpenRouter airline 75.6 +/- 3.2 [A16] | Weights 63 GB: LoRA needs QLoRA. TRL lists only `gemma-4-E2B-it` as tested [B11] | Alternative to the 27B |
| `google/gemma-4-12B-it` | 11.96B dense | Apache-2.0 | 2026-05-23 | Vendor tau2 69.0 [B5] | Fits easily | Alternative to the 9B. Lower vendor score |
| `google/gemma-4-26B-A4B-it` | 25.2B MoE, 3.8B active | Apache-2.0 | 2026-04 | Vendor tau2 68.2 [B5] | Weights 50 GB, MoE FT is harder | Skip |
| `zai-org/GLM-5.3-Flash` | 320B, 18B active | MIT | 2026-08-25 | No tau2 or BFCL on the card [B13] | Does not fit | Too big |
| `deepseek-ai/DeepSeek-V4.1-Flash` | 763B on the hub, 552B backbone | MIT | 2026-09 | No tau2 or BFCL on the card [B14] | Does not fit | Too big |
| Mistral Small 4 119B, Large 4 1T, Medium 3.5 128B | 119B to 1T | Small 4: Apache-2.0. Others: other | 2026-01 to 2026-10 | not opened | Does not fit | Too big [B15] |
| `openai/gpt-oss-20b` and `-120b` | 21B and 117B MoE | Apache-2.0 | 2025-08-04 | Not opened. Qwen's card leaves them blank on BFCL and TAU2 [B2] | 20B fits | UNVERIFIED, 15 months old |
| NVIDIA Nemotron 3.5 Lightning 30B-A3B | 30B MoE | other | 2026-08-05 | not opened | Licence "other" | Skipped [B15] |
| `LiquidAI/LFM3-1.7B`, others | 1.7B | other | 2026-10-23 | A tracker (BenchLM) shows BFCL 71.4 [S1] | Small | UNVERIFIED. The tracker also shows "BTL-3" at 88.5. I do not trust it |

Reading of Track B:

- **No model between 9B and 27B is newer than Qwen3.5-9B in a form we can use.** Qwen3.6 and Qwen3.8 ship only 27B (and 35B-A3B) as small open weights [B4]. Gemma 4 12B and 31B are the other Apache-2.0 families with real tau2 numbers.
- **The 9B against the 27B:** 73.4 +/- 4.5 against 77.5 +/- 2.6 on airline tau2, and 66.1 against 68.5 on vendor BFCL-V4 (a different 27B generation). The gap is inside the noise. After SFT on a closed plan language I expect it to shrink more (ESTIMATE). The vendor card has an oddity: the 4B scores 79.9 on TAU2, above the 9B at 79.1 [B2]. Treat vendor numbers as weak.
- **BFCL V4 is stale for our purpose.** The Berkeley page says "last updated 2026-04-12" and the CSV I downloaded has Claude Opus 4.5 first at 77.47% and no 2026 model above [B16]. Trackers list newer models with "Unverified" labels. I did not use them.
- **Overthinking is the known failure mode of the Qwen3.5 family.** The 9B wrote 52.9k output tokens per airline task [A16]. For plans, turn thinking off (`chat_template_kwargs: {"enable_thinking": false}`) and train on the same template [B1, B8].
- **Licences are clean.** Qwen3.5-9B, Qwen3.8-27B and Gemma 4 are all Apache-2.0 [B1, B3, B5].

### 1.3 Speed on one A100 (ESTIMATE, then measure)

I found no published A100 number for any of these models. The one A100 data point is Qwen2.5-7B-Instruct on vLLM: 96 tokens per second per user, 35 ms median time to first token, 1 request per second offered load [B17]. Decode is limited by memory bandwidth, so I scale by weight bytes (7.6B -> 15 GB):

| Model | Weights | Single-stream decode (ESTIMATE) | A plan of 250 tokens |
|---|---|---|---|
| Qwen3.5-9B BF16 | 19 GB | about 75 tokens/s | about 3 s |
| Qwen3.8-27B BF16 | 56 GB | about 26 tokens/s | about 10 s |

The 27B misses the "under 10 s per question" target on a single stream. The 9B meets it. Multi-token prediction may help: the cards give `--speculative-config '{"method":"qwen3_next_mtp","num_speculative_tokens":2}'` for the 9B [B1] and `{"method":"mtp","num_speculative_tokens":3}` for the 27B [B9]. Acceptance after LoRA fine-tuning is unknown, because the MTP head is not trained by SFT. Measure it.

### 1.4 Constrained decoding on the open model (SOURCED)

vLLM serves JSON schema, regex, choice and EBNF grammar through `structured_outputs`. Backends are xgrammar and guidance, default `auto` [B10]. Write the plan language as an EBNF grammar and syntax errors become impossible, whatever the model does. One trap: with a reasoning parser, structured outputs can switch off if the reasoning is not parsed. Run with thinking off, or set `--structured-outputs-config.enable_in_reasoning=True` [B10]. Native tool calling on Qwen needs `--enable-auto-tool-choice --tool-call-parser qwen3_coder` and `--reasoning-parser qwen3` [B1, B9]. For plan-then-execute you do not need it.

## 2. Evidence: when RL beats prompt optimisation or SFT

| Work | Setting and data size | Finding | Caveat |
|---|---|---|---|
| SFT or RL for tool-calling agents, arXiv 2609.17848, 2026-09-15 [C2] | 6 Qwen3 models, 0.6B to 32B. Three public tool-calling sets, up to 20,000 examples each. LoRA SFT, GRPO, SFT then GRPO | LoRA SFT is best in distribution in 15 of 18 settings. On transfer, GRPO wins 29 of 54 but by under 1 point on average. SFT then GRPO is rarely best. LoRA beat full fine-tuning at 4B (88.0 against 80.4 on xLAM) | GRPO used a decomposed reward (format, name, argument match). No GPU hours reported. The paper says GRPO costs more per example |
| ToolRL, arXiv 2504.13958 [C1] | Qwen2.5 1.5B to 7B, Llama-3.2-3B. 4K mixed examples. GRPO from the instruct model, 2 A100 | BFCL: GRPO cold start 58.38% against 41.97% for the raw 7B model. SFT baselines were worse than raw (34.08% and 36.53%). Claims +17% over base and +15% over SFT (the +17% and +15% are CONFIRMED in the abstract; the four BFCL percentages are UNVERIFIED, the verifier read only the abstract) | The SFT baselines look weak. The later controlled study [C2] reaches the opposite order in distribution. Training time not reported |
| GEPA, arXiv 2507.19457, ICLR 2026 oral [C3, C6] | 6 tasks, mostly QA pipelines (HotpotQA, IFBench, HoVer, PUPA, AIME) | Beats GRPO by 6% on average, up to 20%, with up to 35 times fewer rollouts. "100-500 evals vs 10K+ for RL" (repo) | A review notes the 35 times is one case. Average GEPA budget was about 3,900 rollouts, so about 6 times. GRPO won on AIME (38.00 against 32.00) [C8, secondary]. These are not classic tool agents |
| ART-E email agent, OpenPipe [C5, secondary via ZenML] | Qwen 14B, GRPO with ART. About 4,000 questions. One H100, "under a day", about $80 | Beat o3 on their task. Reward: LLM judge on the final answer, a turn bonus, a penalty for wrong answers. A partial-credit reward for more turns was hacked (the model repeated its last tool call to the turn limit) | I could not open the primary blog. Accuracy numbers differ between sources. UNVERIFIED |
| LoRA Without Regret, 2025-09-29 [C4] | Many models, SFT and RL | RL with LoRA matches full fine-tuning, even at rank 1. LoRA's best learning rate is about 10 times the full fine-tuning rate. Apply LoRA to all layers, not attention only. LoRA is less tolerant of large batches | Capacity matters only when the dataset exceeds the adapter |
| Rethinking "RL generalizes, SFT memorizes", arXiv 2611.14912 (from the earlier report, not reopened) [S13 in `small-models-rl.md`] | SFT data role | At a matched rollout budget, SFT generalizes as well as RL | Not reopened by me |

What this means for us (ESTIMATE, my reading):

- **A few hundred tasks:** use prompt optimisation (GEPA) on the API planner. RL has no signal here: a group of 8 samples that all pass or all fail gives zero gradient, and ART-E tracked reward spread for this reason [C5].
- **A few thousand tasks with exact labels:** SFT first. Our plan language is closed, so the output is a format-and-routing problem, which is where LoRA SFT wins [C2].
- **RL is worth its cost only when** (a) the executor gives an exact, cheap reward, (b) SFT has plateaued on decision errors (wrong filter, wrong convention, a missed "ask the user") and not on syntax, (c) there are at least about 1,000 distinct tasks with mixed outcomes in a group, and (d) someone reads the outputs, because RL finds loopholes [C5].
- **The reward must punish a confident wrong answer and pay for a correct "ask_user".** A plain 0/1 reward invites the mode answer: on cubicasa the template mode scores 55.3% without looking at the drawing (from `STATE-OF-THE-ART.md` section 3.1).

## 3. Recommendation and recipe

### 3.1 Decisions

| Role | Model | Why | Gate to replace it |
|---|---|---|---|
| Run tonight (plan writer in the product) | `claude-haiku-5-5`, strict JSON plan, adaptive thinking at `low` or `medium` | Cheapest, grammar-guaranteed, good tool use. About $0.0003 to $0.0008 per plan | Keep until the open model passes the gate |
| Escalation | `claude-sonnet-5-5`, one retry, then `ask_user` | Best score on the board among Claude tiers (78.8). More than two tiers gave no gain in 118 of 135 comparisons (from `STATE-OF-THE-ART.md`, AG-S7) | none |
| Train tonight | `Qwen/Qwen3.5-9B` | Fast to train, fast to serve, RL fits | See gate |
| Train as fallback | `Qwen/Qwen3.8-27B` | Higher ceiling. SFT only | See gate |

**Gate for the open model to replace Haiku** (my rule, ESTIMATE): on the held-out split by drawing, template and language, (1) the share of valid plans is within 2 points of Haiku, (2) the executed answer is as accurate within 2 points, (3) p95 latency is under 10 s on one A100, (4) no loss on the 5-language set. If it fails, ship Haiku and present the open model as the "small fine-tuned model" and as a second witness. Do not claim more.

### 3.2 Use a plan, not a tool loop

One call writes 3 to 6 typed steps. A tool loop is 3 to 6 calls with a growing prompt. At Haiku prices a loop is still cheap, but the 9B's latency is not (3 s per call). Compact text steps, one per line, use about half the tokens of JSON. For the API path use the flat JSON schema from section 1.1.

### 3.3 Fine-tuning recipe for the 9B (A100 80 GB on Verda, `1A100.22V`)

Versions on PyPI on 2026-11-14 [B12]: `trl 1.18.0`, `transformers 5.23.0`, `peft 0.21.3`, `unsloth 2026.11.4`, `vllm 0.33.0`, `flash-linear-attention 0.6.0`, `xgrammar 0.2.9`, `dspy 3.5.0`, `gepa 0.1.4`. Qwen3.5 needs transformers 5 [B7]. The Qwen3.8 vLLM recipe wants vLLM 0.17 or later and transformers 5.8 or later [B9]. Whether these pins work together in one environment is untested (UNVERIFIED). Use two virtual environments: one for training, one for vLLM. Run `pnpm j gpu run` with a `requirements.txt` per environment.

**Data** (ESTIMATE of size):

- 3,000 training examples, 400 held out by drawing, 200 by template, plus the 40 hand-written questions in 5 languages from the lead's measurement 2.
- Gold plans come from the 24 public templates and the deterministic parsers, so the gold answer is exact. Add paraphrases and other languages from an Apache-2.0 model served on the same GPU (Qwen3.8-27B or Gemma 4 31B), not from Claude.
- **Do not train on Claude outputs without checking the terms.** Anthropic's Commercial Terms D.4 bar using the service "to build a competing product or service, including to train competing AI models" [A17]. A plan writer for a hackathon app is probably not a competing model, but I am not a lawyer and the terms may have changed since 2025-06-17. UNVERIFIED reading. Template gold plans and open-model paraphrases avoid the question.
- Message layout: a fixed system prefix (plan language and tool spec, about 700 tokens), then the card and the question, then the plan. Loss on the plan only. Render with thinking off, and use the same template at inference [B8].
- Never put the file name, sibling files or the public annotation in the prompt (rule 7 of `DECISION.md`).

**Stage 1, SFT (about 1 to 1.5 A100 hours, ESTIMATE).** Settings follow the Unsloth Qwen3.5 and 3.8 guides [B7, B8] and LoRA Without Regret [C4].

```python
# train env: unsloth 2026.11.4, trl 1.18.0, transformers 5.23.0, peft 0.21.3
from unsloth import FastModel
model, tok = FastModel.from_pretrained("Qwen/Qwen3.5-9B", max_seq_length=4096,
                                       load_in_4bit=False, load_in_16bit=True, full_finetuning=False)
model = FastModel.get_peft_model(model, finetune_vision_layers=False, finetune_language_layers=True,
    finetune_attention_modules=True, finetune_mlp_modules=True,   # all linear layers, not attention only
    r=32, lora_alpha=32, lora_dropout=0, bias="none", use_gradient_checkpointing="unsloth", random_state=3407)
# SFTConfig: learning_rate=2e-4, num_train_epochs=2, per_device_train_batch_size=4,
#   gradient_accumulation_steps=8 (effective 32), warmup_steps=10, lr_scheduler_type="cosine",
#   optim="adamw_8bit", max_seq_length=4096, bf16=True
# train on the plan tokens only (Unsloth train_on_responses_only)
model.save_pretrained_merged("out/sft-9b", tok, save_method="merged_16bit")
```

- Do not use 4-bit for Qwen3.5-9B. Unsloth: "not recommended to do QLoRA (4-bit) training on the Qwen3.5 models" [B7].
- Throughput (ESTIMATE): about 6 x 9.65e9 FLOPs per token with gradient checkpointing, at about 40% of A100 peak, gives about 2,000 tokens per second. 3,000 examples at 1.5k tokens, 2 epochs, is about 9M tokens, so about 75 minutes.
- Serve and test the merged model:

```sh
# vllm env: vllm 0.33.0
vllm serve out/sft-9b --max-model-len 8192 --reasoning-parser qwen3 \
  --speculative-config '{"method":"qwen3_next_mtp","num_speculative_tokens":2}'   # drop if acceptance is low
# request: temperature 0, presence_penalty 0, chat_template_kwargs {"enable_thinking": false},
#          structured_outputs {"grammar": "<EBNF of the plan language>"}
```

- Set `presence_penalty` to 0 and the temperature to 0 for plans. The card's non-thinking default is `presence_penalty=1.5` [B1], which would punish a repeated operator name in a plan (ESTIMATE of the effect).

**Stage 2, rejection-sampled SFT (about 1 A100 hour).** Sample 8 plans per training prompt from the SFT model with vLLM, run the executor, keep the plans whose answer is exact, add them to the data, train 1 epoch more. This is the matched-budget control for GRPO [S13 in `small-models-rl.md`].

**Stage 3, GRPO with the executor as reward (about 3 to 4 A100 hours, ESTIMATE).** TRL 1.18.0 supports GRPO with vLLM, tools and `environment_factory`, and lists Qwen3.5 and Qwen3.6 as tested [B11]. Qwen3.8 is not on that list, but it uses the same `qwen3_5` architecture [B8]. Unsloth GRPO on Qwen3.5 only works with `fast_inference=False`, which is slow, so use TRL [B7].

```python
# GRPOConfig, names from the TRL v1.18.0 docs [B11]; smoke-test each one
use_vllm=True, vllm_mode="colocate", vllm_gpu_memory_utilization=0.35,
num_generations=8, per_device_train_batch_size=8, gradient_accumulation_steps=32,  # 256 rollouts = 32 prompts per step
max_completion_length=384, learning_rate=1e-5,      # LoRA: about 10 times a full fine-tuning rate of 1e-6 [C4, C1]
beta=0.0, loss_type="dapo", mask_truncated_completions=True,
vllm_importance_sampling_correction=True, chat_template_kwargs={"enable_thinking": False}, max_steps=80
# peft_config = LoraConfig(r=32, lora_alpha=32, target_modules="all-linear")
```

- Reward (my design, ESTIMATE): 0.1 for a plan that parses, 0.2 for a plan whose preconditions pass, 0.7 for an exact or within-2% answer, minus 1.0 for a wrong confident answer, plus 0.5 for a correct `ask_user` with the right missing fact on an unanswerable item. The ToolRL result says to give partial credit for name, argument and value matches [C1]. ART-E says to punish wrong answers and to check outputs by eye [C5].
- Cost per step (ESTIMATE): 256 rollouts of about 1.4k tokens in the forward and backward pass is about 360k tokens, so about 3 minutes. Eighty steps is about 4 hours. That is about 2,500 prompt visits. Shorten the system prefix if it is slower.
- Memory (ESTIMATE): 19 GB trainer weights, a vLLM engine at 0.35 x 80 = 28 GB, and 10 to 15 GB of activations. About 60 GB in total.
- Controls to report: the per-template mode baseline, SFT-only, rejection-sampled SFT, and the same GRPO run with random rewards (if time allows). Without them a gain can be a format effect [S12 and S9 in `small-models-rl.md`].

**GEPA on the Haiku prompt (no GPU, in parallel).** `dspy.GEPA(metric=..., max_metric_calls=150..500, reflection_lm=...)` with a metric that returns the executor's error text as feedback [C6]. The repo's own guidance is 100 to 500 evaluations. Use Sonnet 5.5 as the reflection model and Haiku 5.5 as the student. Cost (ESTIMATE): 500 plan calls at $0.0008 plus about 50 reflection calls at $0.02 is about $1.5.

### 3.4 Expected cost (ESTIMATE, A100 at $2.37 per hour)

| Step | A100 hours | USD |
|---|---|---|
| Smoke test: load, one SFT step, merge, serve (1 hour test below) | 0.7 | 1.7 |
| Data generation and paraphrases | 0.5 | 1.2 |
| Stage 1, SFT, 9B | 1.0 to 1.5 | 2.4 to 3.6 |
| Evaluation after each stage (3 times) | 0.9 | 2.1 |
| Stage 2, rejection-sampled SFT | 1.0 | 2.4 |
| Stage 3, GRPO | 3.0 to 4.0 | 7.1 to 9.5 |
| **Total, 9B path** | **about 7 to 9** | **about 17 to 21** |
| Fallback: SFT of the 27B, 2 epochs (about 750 tokens/s, so about 3.5 h; Unsloth says 1.5 times faster) | 2.5 to 3.5 | 6 to 8 |
| GEPA on Haiku, API cost only | 0 | about 1.5 |

Two VMs can run the 9B path and the 27B fallback at the same time. The total stays under $35 of the $200 credit.

## 4. Risks and how to test them in 1 hour

Run these in parallel. Total A100 time about 40 minutes, total API cost under $1.

| Risk | Test | Pass line | Time |
|---|---|---|---|
| The training environment does not work: Qwen3.5 uses Gated DeltaNet kernels that compile on first run, and the pins may clash [B7, B8] | On a `1A100.22V`: install, run 20 SFT steps on 50 examples, merge, serve with vLLM, send one request | The merged model answers through vLLM with the same plan as in training | 25 min |
| Thinking does not stay off after SFT | 20 requests with `enable_thinking: false` | No `<think>` text in any answer, under 400 tokens each | 5 min |
| The open model is too slow on the A100 | `vllm bench serve` at concurrency 1 and 16 on the base 9B, with and without MTP | 9B: 250 tokens in under 4 s at concurrency 1 (my estimate is 3 s). Acceptance of MTP above 0.6, else drop it | 10 min |
| The API plan schema is too complex for the grammar compiler | Send the real plan schema to `claude-haiku-5-5` with `output_config.format` | No 400 "Schema is too complex". Limits: 16 union parameters, 24 optional [A6] | 5 min |
| Haiku 5.5 is not good enough as the planner | Lead's measurement 2: 40 hand-written questions, 5 languages, hand-made fact stores. Compare Haiku, Sonnet, Gemini 3.5 Flash-Lite, GPT-6 Luna, and zero-shot Qwen3.5-9B | At least 80% valid plans for Haiku (the lead's own line in `DECISION.md`). Pick the cheapest model within 3 points of the best | 15 min, about $0.30 |
| Executor reward can be gamed | Score 50 plans that are random but valid, and 50 that only copy the template mode | Random plans average below 0.3. Mode copies score below the SFT model on the high-entropy templates | 10 min, CPU |
| Distillation terms | Decide the data source before generating data | Gold plans from templates, paraphrases from Qwen3.8-27B or Gemma 4 31B | 0 min, a decision |
| A new drawing style breaks the plan writer | Plans are written from the fact-store card, not from pixels. Hold out a whole source (for example `wild` scans) | Valid-plan rate drops by under 5 points from the in-distribution split. Fine-tuned counters collapsed above the trained range in the earlier report [S5 in `small-models-rl.md`], so test this | 10 min |
| Vendor numbers mislead | Trust only your own held-out numbers. The vendor card has the 4B above the 9B on TAU2 [B2]. OpenRouter airline has error bars of 2 to 4.5 points [A16] | n/a | 0 |

## 5. What I could not confirm

- No A100 throughput number for any Qwen3.5 or 3.8 model (section 1.3 is arithmetic).
- No tool-use benchmark from Anthropic for Haiku 5.5. The only comparison is the OpenRouter airline board.
- Gemini 3.5 Flash-Lite numbers come from trackers and the pricing page. The model card was not opened.
- The `gemini-4-hydrogen` API id is from the pricing page [A12]. The Google blog does not state it [A14].
- The OpenPipe ART-E primary blog could not be fetched. The ZenML summary has about 4,000 questions, one H100 and about $80.
- Qwen3.8-27B LoRA memory: Unsloth gives "more than 36 GB" for LoRA in the 3.8 guide and 56 GB for the 3.5 twin [B7, B8]. Measure.
- Whether `unsloth 2026.11.4`, `trl 1.18.0` and `transformers 5.23.0` train Qwen3.5-9B together. Not tested.
- The legal reading of Anthropic's D.4 clause.

## Sources

All pages opened on 2026-11-14. "Date" is the date on the page where it has one.

| id | Title | URL | Date | Supports |
|---|---|---|---|---|
| A1 | Claude models overview | https://platform.claude.com/docs/en/models/overview | 2026-11 | Lineup, ids, prices, 1M context, Haiku 5.5 retirement not before 2027-10-07 |
| A2 | Claude pricing | https://platform.claude.com/docs/en/about-claude/pricing | 2026-11 | Cache, batch and long-prompt prices. Tokenizer gives about 30% more tokens |
| A3 | Claude Haiku 5.5 model page | https://platform.claude.com/docs/en/models/haiku-5-5/overview | 2026-10-07 | `claude-haiku-5-5`, prices, 512-token cache minimum, thinking and effort |
| A4 | Anthropic: Claude Haiku 5.5 | https://www.anthropic.com/claude-haiku-5-5 | 2026-10-07 | Benchmark table (no tool-use benchmark), effort levels |
| A5 | Prompting Claude Haiku 5.5 | https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-haiku-5-5 | 2026-10 | Skips a tool call with thinking off and JSON output. Early stopping. No `temperature`. No `budget_tokens` |
| A6 | Structured outputs (Claude) | https://platform.claude.com/docs/en/build-with-claude/structured-outputs | 2026-11 | Grammar guarantee, schema limits (20, 24, 16, 180 s), enum casing, refusal and `max_tokens` cases |
| A7 | Strict tool use (Claude) | https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use | 2026-11 | `strict: true` on Haiku 5.5 and Sonnet 5.5 |
| A8 | VentureBeat: Haiku 5.5 launch | https://venturebeat.com/technology/anthropic-launches-claude-haiku-5-5-with-90-api-price-reduction-matching-gpt-6-luna | 2026-10-07 | Terminal-Bench 39.2% at max effort, about 20% at medium |
| A9 | OpenAI API pricing | https://developers.openai.com/api/docs/pricing | 2026-11 | GPT-6 family ids and prices |
| A10 | `gpt-6-luna` model page | https://developers.openai.com/api/docs/models/gpt-6-luna | 2026-11 | Features, reasoning effort, Chat Completions caveat, no fine-tuning |
| A11 | OpenAI structured outputs guide | https://developers.openai.com/api/docs/guides/structured-outputs | 2026-11 | Schema guarantee wording, refusals |
| A12 | Gemini API pricing | https://aistudio.google.com/docs/pricing | 2026-11 | Gemini ids and prices, price rises on 2026-12-01 and 2027-01-01 |
| A13 | Gemini structured output | https://aistudio.google.com/docs/structured-output | 2026-11 | Schema subset, limits, preview of structured output with function calling |
| A14 | Google: Gemini 4 Hydrogen | https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-gemini-4-hydrogen/ | 2026-11-12 | Launch, price, thinking levels |
| A15 | Trackers for Gemini 3.5 Flash-Lite (search results, not opened one by one) | https://openrouter.ai/google/gemini-3.5-flash-lite | 2026-07-21 | GA date, price (secondary) |
| A16 | OpenRouter tau2-bench airline leaderboard | https://openrouter.ai/benchmarks/tau2-bench-airline | 2026-11-14 | All tau2 airline numbers, cost per task, setup |
| A17 | Anthropic Commercial Terms of Service | https://www.anthropic.com/legal/commercial-terms | effective 2025-06-17 | Clause D.4 on competing models |
| B1 | Qwen3.5-9B model card | https://huggingface.co/Qwen/Qwen3.5-9B | 2026-02-27 | Licence, params, vLLM flags, sampling, vendor BFCL and TAU2 |
| B2 | Qwen3.5-27B model card (benchmark table) | https://huggingface.co/Qwen/Qwen3.5-27B | 2026-02-24 | Vendor BFCL-V4 and TAU2 for 27B, 122B, 35B-A3B |
| B3 | Qwen3.8-27B model card | https://huggingface.co/Qwen/Qwen3.8-27B | 2026-08-05 | Licence, params, agent rows, sampling |
| B4 | Hugging Face API, Qwen listing | https://huggingface.co/api/models?author=Qwen&sort=createdAt&direction=-1&limit=40 | 2026-11-14 | Exact ids and dates, Qwen3.6 and 3.8 sizes |
| B5 | Gemma 4 31B model card | https://huggingface.co/google/gemma-4-31B-it | 2026-03 | Sizes, licence, tau2 for each size |
| B6 | Qwen3.6-35B-A3B model card | https://huggingface.co/Qwen/Qwen3.6-35B-A3B | 2026-04-15 | MCP-Atlas, MCPMark |
| B7 | Unsloth: fine-tune Qwen3.5 | https://unsloth.ai/docs/models/qwen3.5/fine-tune | 2026 | VRAM table, no QLoRA, GRPO needs `fast_inference=False`, LoRA settings |
| B8 | Unsloth: Qwen3.8 fine-tuning guide | https://unsloth.ai/docs/models/qwen3.8/train | 2026-08 | Qwen3.8 uses `qwen3_5` architecture, QLoRA 24 GB, config, export |
| B9 | vLLM recipe, Qwen3.8-27B | https://recipes.vllm.ai/Qwen/Qwen3.8-27B | 2026 | Serve flags, vLLM 0.17+, transformers 5.8+, MTP |
| B10 | vLLM structured outputs | https://docs.vllm.ai/en/latest/features/structured_outputs.html | 2026 | Backends, `structured_outputs` fields, reasoning-parser trap |
| B11 | TRL GRPO trainer docs v1.18.0 | https://huggingface.co/docs/trl/en/grpo_trainer | 2026-11 | Tools, `environment_factory`, vLLM colocate, tested models |
| B12 | PyPI JSON for the libraries | https://pypi.org/pypi/trl/json (and the same path for each package) | 2026-11-14 | Exact versions and release dates |
| B13 | GLM-5.3-Flash card | https://huggingface.co/zai-org/GLM-5.3-Flash | 2026-08 | 320B total, 18B active, MIT |
| B14 | DeepSeek-V4.1-Flash card | https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash | 2026-09 | 763B on the hub, MIT |
| B15 | Hugging Face API listings for Mistral and NVIDIA | https://huggingface.co/api/models?author=mistralai&sort=createdAt&direction=-1&limit=20 | 2026-11-14 | Sizes and licence tags of the Mistral and Nemotron releases |
| B16 | Berkeley Function Calling Leaderboard | https://gorilla.cs.berkeley.edu/leaderboard.html | page says 2026-04-12 | BFCL V4 is stale. The CSV tops at Claude Opus 4.5 77.47% |
| B17 | RunPod: best GPU for LLM inference | https://www.runpod.io/articles/guides/best-gpu-for-llm-inference | test 2026-09-15 | A100 80 GB: 96 tokens/s per user on Qwen2.5-7B |
| C1 | ToolRL: reward is all tool learning needs | https://arxiv.org/abs/2504.13958 | 2025-04-16 | GRPO cold start on 4K examples, reward design, BFCL numbers |
| C2 | SFT or RL for tool-calling agents? A controlled study | https://arxiv.org/abs/2609.17848 | 2026-09-15 | SFT best in distribution, GRPO under 1 point on transfer |
| C3 | GEPA: reflective prompt evolution can outperform RL | https://arxiv.org/abs/2507.19457 | v2 2026-02-14, ICLR 2026 oral | 6% over GRPO, up to 35 times fewer rollouts |
| C4 | LoRA Without Regret | https://thinkingmachines.ai/blog/lora/ | 2025-09-29 | LoRA matches full fine-tuning in RL, 10 times learning rate, all layers |
| C5 | ZenML summary of OpenPipe ART-E | https://www.zenml.io/llmops-database/building-art-e-reinforcement-learning-for-email-search-agent-development | 2025 | About 4,000 questions, one H100, about $80, reward hacking by repeated tool calls (secondary) |
| C6 | GEPA repository | https://github.com/gepa-ai/gepa | 2026 | MIT, `dspy.GEPA`, 100 to 500 evals, MCP and LangChain adapters |
| C8 | Review of the GEPA paper (search snippet, secondary) | https://baba9811.github.io/en/papers/0043-gepa-reflective-prompt-evolution-can-outperform-reinforcemen/ | 2026 | 35 times is one case, about 3,900 average rollouts, GRPO wins on AIME |
| S1 | BenchLM BFCL v4 tracker (search snippet, not trusted) | https://benchlm.ai/benchmarks/bfcl-v4 | 2026-10-27 | Shows odd entries such as "BTL-3" at 88.5 |

## Verification

Checked on 2026-11-14 by an independent verifier who opened each primary page. Hugging Face ids, licences, dates and parameter counts come from the `huggingface.co/api/models/<id>` JSON.

| Claim | Verdict | Evidence URL |
|---|---|---|
| `Qwen/Qwen3.5-9B` exists, Apache-2.0, created 2026-02-27, 9,653,104,368 params | CONFIRMED | https://huggingface.co/api/models/Qwen/Qwen3.5-9B |
| Qwen3.5-9B vendor BFCL-V4 66.1, TAU2 79.1; 4B has TAU2 79.9 (above 9B); gpt-oss rows blank | CONFIRMED | https://huggingface.co/Qwen/Qwen3.5-9B |
| `Qwen/Qwen3.8-27B` exists, Apache-2.0, created 2026-08-05, 27.78B params | CONFIRMED | https://huggingface.co/api/models/Qwen/Qwen3.8-27B |
| Qwen3.8-27B card: Terminal Bench 2.1 73.0, ClawEval-MM Pass@3 57.4. No visible BFCL or TAU2 row (a collapsed section of 13 benchmarks was not readable) | CONFIRMED (absence of BFCL/TAU2 only partly) | https://huggingface.co/Qwen/Qwen3.8-27B |
| `Qwen/Qwen3.5-27B` vendor BFCL-V4 68.5, TAU2 79.0, Apache-2.0 | CONFIRMED | https://huggingface.co/Qwen/Qwen3.5-27B |
| `Qwen/Qwen3.6-35B-A3B` exists, Apache-2.0, 2026-04-15, 35.95B params | CONFIRMED | https://huggingface.co/api/models/Qwen/Qwen3.6-35B-A3B |
| `google/gemma-4-31B-it` Apache-2.0, 2026-03-11, 31.27B params; vendor tau2 31B 76.9, 26B-A4B 68.2, 12B 69.0 (card calls it "12B Unified") | CONFIRMED | https://huggingface.co/api/models/google/gemma-4-31B-it and https://huggingface.co/google/gemma-4-31B-it |
| `google/gemma-4-12B-it` exists, Apache-2.0, 2026-05-23, 11.96B params | CONFIRMED | https://huggingface.co/api/models/google/gemma-4-12B-it |
| OpenRouter tau2 airline: Sonnet 5.5 78.8 +/- 2.2 ($0.16, 6.25k); Flash-Lite 78.3 +/- 1.0 ($0.074, 21.5k); Qwen3.8-27B 77.5 +/- 2.6; Qwen3.5-9B 73.4 +/- 4.5 (52.9k tokens); Haiku 5.5 72.8 +/- 4.1 ($0.012, 10.7k); Luna 67.3 (no spread, $0.009, 8.9k) | CONFIRMED | https://openrouter.ai/benchmarks/tau2-bench-airline |
| Claude ids `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`, Fable 5.2; prices $0.10/$0.50, $2/$10, $4/$20, $8/$40; Haiku retirement not before 2027-10-07 | CONFIRMED | https://platform.claude.com/docs/en/models/overview |
| Haiku 5.5 over 100K prompt $0.50/$2.50, cache read $0.01, batch $0.05/$0.25; Sonnet cache $0.10, batch $1/$5; Opus cache $0.20, batch $2/$10 | CONFIRMED | https://platform.claude.com/docs/en/about-claude/pricing |
| Claude structured-output limits: 20 strict tools, 24 optional params, 16 union params, 180 s timeout, 24 h cache, enum casing, no min/max/length; Haiku 5.5 supported | CONFIRMED | https://platform.claude.com/docs/en/build-with-claude/structured-outputs |
| `gpt-6-luna` $0.10/$0.50, cache $0.01, over 272K 2x input and 1.5x output ($0.20/$0.75) | CONFIRMED | https://developers.openai.com/api/docs/models/gpt-6-luna |
| Gemini ids and prices: `gemini-3.5-flash-lite` $0.30/$2.50 (batch $0.15/$1.25), `gemini-3.8-flash` $0.75/$3.75 then $1.50/$7.50 on 2027-01-01, `gemini-4-hydrogen` $1.50/$7.50 | CONFIRMED | https://aistudio.google.com/docs/pricing |
| Unsloth Qwen3.5 bf16 LoRA VRAM: 9B 22 GB, 27B 56 GB, 35B-A3B 74 GB; no QLoRA on Qwen3.5; GRPO needs `fast_inference=False` | CONFIRMED | https://unsloth.ai/docs/models/qwen3.5/fine-tune |
| arXiv 2609.17848: SFT best in 15 of 18 settings, GRPO wins 29 of 54 transfer settings by under 1 point, SFT then GRPO rarely best, LoRA beats full fine-tuning | CONFIRMED (the "88.0 against 80.4 on xLAM" detail not checked: UNVERIFIED) | https://arxiv.org/abs/2609.17848 |
| GEPA arXiv 2507.19457: ICLR 2026 oral, beats GRPO by 6% on average, up to 20%, up to 35x fewer rollouts | CONFIRMED | https://arxiv.org/abs/2507.19457 |
| ToolRL arXiv 2504.13958: +17% over base, +15% over SFT, submitted 2025-04-16 | CONFIRMED (the four BFCL percentages: UNVERIFIED) | https://arxiv.org/abs/2504.13958 |
| Not rechecked: Unsloth Qwen3.8 guide, vLLM recipe, TRL docs, PyPI versions, GLM-5.3-Flash, DeepSeek-V4.1-Flash, Gemini 3.5 Flash-Lite GA date, A100 speed estimates, ART-E, Anthropic D.4 terms | UNVERIFIED by this pass | n/a |

Result: the primary recommendation (`Qwen/Qwen3.5-9B` to train, `claude-haiku-5-5` to run, `Qwen/Qwen3.8-27B` as SFT fallback) survives. Every id, licence, size, price and score that the recommendation depends on matched its source. The estimates (speed, GPU hours, cost) are still the researcher's arithmetic and were not tested.
