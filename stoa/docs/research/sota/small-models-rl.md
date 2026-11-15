# Small fine-tuned models and RL with checkable rewards

Track: small vision-language models (VLMs), reinforcement learning with verifiable rewards (RLVR), executor-reward RL,
distillation and prompt optimisation, for Stoa "Make Blueprints Talk".
Date of research: 2026-11-13. Every figure has a tag:

- **[M]** measured by me on the local dataset (`stoa/data/junction-dataset/questions.jsonl`).
- **[S]** read in a source I opened. The source id is in brackets, for example [S3].
- **[E]** my estimate. It is not a measurement.
- **[U]** a claim that I could not open in a primary source. It is unverified.

## Findings that change decisions

1. **A binary "count is right" reward is the wrong reward. Plain GRPO with 0/1 accuracy did worse than SFT on counting [S6].**
   Perception-R1 got its counting gain with a point-matching reward (Hungarian match, Euclidean distance per point), not answer match [S1].
   It improved Qwen2-VL-2B on PixMo-Count test from 50.5 to 75.6, while SFT alone reached 59.9 [S1].
   Decision: if we do RL, the reward must score the points (or boxes), not only the final number. That needs point labels.
   Moves: accuracy, verifiability (the points are the evidence).
2. **Reward hacking by the mode answer is a measured, not a theoretical, risk on cubicasa5k.** [M] Share of English questions where the
   answer equals the template mode: kitchens 95.8%, bathrooms 88.6%, storeys 79.9%, showers and bathtubs 76.2%, toilets 60.4%,
   but doors 11.6% and windows 13.6%. [M] Mode accuracy over all 12 English templates is 55.3%.
   With GRPO, a group where all samples answer "1 kitchen" gets reward 1 and zero advantage, so it teaches nothing and rewards the prior.
   The "spurious rewards" result shows the same danger: Qwen2.5-Math-7B gained 21.4 points on MATH-500 from random rewards [S12].
   Decision: report every model against the per-template mode baseline and a random-reward control. Spend RL only on high-entropy
   templates (doors, windows, sinks, WC seats).
3. **Fine-tuned counters collapse on counts above the training range. This is a threat for the harder hidden set.** [S5] After LoRA fine-tuning,
   four 3B-8B VLMs reached 70-82% on in-distribution real images, but 1-26% on the out-of-distribution (OOD) real split (16-34% when the
   count was taken as the number of emitted points). Check: in [S5] "OOD" means images with up to twice as many targets as in training
   (objects on a simple background), not a new image style. The same paper says Point-then-Count (PtC) "improves out-of-distribution generalization",
   and PtC was the best fine-tuned method in its OOD tables. The model's stated count often did not match its own points on the synthetic OOD split
   (consistency 20.56% for Qwen2.5-VL-3B, 48.79% for 7B, 77.72% LLaVA-OneVision, 99.27% InternVL3.5) [S5].
   Decision: never trust the model's number. Count the emitted points, show them, and abstain when points and number disagree.
   Whether this transfers to a new drawing style is not tested in [S5].
4. **For door and window counts on cubicasa, a small detector beats a small VLM on all four criteria.** [S16] RT-DETR-L (32.8M parameters) trained on
   CubiCasa5K (5 classes only: wall, door, window, railing, linkage_point; no toilets, sinks or kitchens) reached 89.8 AP50 for doors and 89.3 AP50 for windows, in about 2.3 h on 2x A100, about 0.1 s per image on GPU.
   No published small-VLM result on floor plans comes close for doors and windows [E, absence claim, not checked by the fact check]; frontier VLMs get "often 0.40-0.55 accuracy" [S15].
   A detector gives boxes (verifiable), runs deterministically, and costs near zero per question.
   Caveat: Ultralytics is AGPL-3.0 [S16]. CubiCasa5K labels likely cover the same drawings as Stoa's cubicasa5k [E], so this is a leakage
   question the judges will ask. Split by drawing and say so.
5. **RL improves pass@1 but rarely adds new capability. Distillation can.** [S11] "the base models achieve a higher pass@k score when k is
   large", and "distillation can introduce new reasoning patterns from the teacher". A 2026 follow-up shows SFT matches RL generalization
   when the rollout budget is matched [S13]. And R1-V's own README says the 2B base model scored 86% on SuperCLEVR counting when asked to
   answer directly, more than the 82.5% of its GRPO model [S9].
   Decision: RL is a polish step after a good SFT or teacher-distilled model, not the core of the system.
6. **Executor rewards work best for program synthesis, which maps to IFC and DXF queries, not pixels.** [S17] Arctic-Text2SQL-R1 uses GRPO
   with an execution-correctness reward; its 7B model matches earlier 70B-class systems. But GEPA reached a higher average score than GRPO
   on 6 tasks with up to 35x fewer rollouts [S18]. With only 820 ifc_bench questions on 25 models [M lead], prompt optimisation of a
   frontier or mid-size model with the same checker is the cheaper first step.
7. **Tooling for the newest base model is the weakest link.** TRL's GRPO VLM list is Gemma3, LLaVA-NeXT, Qwen2-VL, Qwen2.5-VL,
   SmolVLM2 [S19]. Unsloth supports Qwen3.5 vision GRPO, but only with `fast_inference=False`, so rollouts run without vLLM [S21].
   Decision: if RL runs this weekend, use Qwen2.5-VL-3B or Qwen3-VL with vLLM, not Qwen3.5.
8. **A pointing-trained small model is a cheap, independent cross-check.** Molmo2-4B scores 88.1 on PixMo-Count test, against 58 for
   Qwen3-VL-4B [S27, a secondary leaderboard, opened and checked; the Molmo2 paper arXiv 2601.10611 Table 6 gives the same Molmo2 and InternVL3.5 values]. Qwen3.5-4B reports CountBench 96.3 [S22] (CountBench has easy, sparse images).
   Pointing-trained models (Molmo-7B-D, Molmo-72B, Moondream-2B) were about 2x more accurate than frontier models on counterfactual counting (36.02% vs 17.05%) [S8].

## Landscape

### Small VLMs that point, detect or count

| Model | Size | Licence | Counting / pointing evidence | Fine-tune tooling | Note |
|---|---|---|---|---|---|---|
| Qwen3.5-2B/4B/9B | 2-9B | Apache-2.0 [S22] | 4B: CountBench 96.3, RefCOCO avg 88.1, OCRBench 85.0 [S22] | Unsloth SFT and GRPO, GRPO without vLLM [S21] | Feb 2026. Best quality per parameter on paper. |
| Qwen3-VL-2B/4B/8B | 2-8B | Apache-2.0 (HF model card, checked) | Points and boxes, PixMo data in training [U]. PixMo-Count test 58 (4B), 65 (8B) [S27, checked] | Unsloth GRPO with vLLM [S20]; TRL agent list [S19] | Safer RL base than Qwen3.5. |
| Qwen2.5-VL-3B/7B | 3-7B | 3B: Qwen research licence; 7B: Apache-2.0 (HF model cards, checked) | Base of most RL papers [S1][S3][S4] | TRL tested [S19], Unsloth [S20] | Most RL recipes exist for it. |
| Molmo2-4B/8B | 4-9B | Apache-2.0, trained on some non-commercial data [S23] | PixMo-Count test 88.1 (4B) [S27, checked] | Training code "will be made available at a later date" on the model card [S23] | Best open pointer. Hard to fine-tune this weekend. |
| Moondream 3 Preview | 9B MoE, 2B active | BSL 1.1, no third-party service [S24] | CountBenchQA 93.2, vendor-reported [S24] | "Finetuning (beta)" [S24] | Licence fine for a hackathon demo. |
| Gemma 4 E2B/E4B | 2.3B/4.5B effective | Apache-2.0 [S25] | Lists "pointing" and object detection, no counting benchmark [S25] | Gemma 3 is on TRL's list [S19] | Pointing quality unknown. |
| Florence-2-large | 0.77B | MIT [S26] | `<OD>`, `<OCR_WITH_REGION>`; COCO OD AP 39.8 for this checkpoint [S26] | Plain PyTorch | A cheap box detector, not a reasoner. |
| PaliGemma 2 | 3/10/28B | Gemma terms (HF card, checked) | Detection and segmentation in mix tasks [U] | big_vision, HF | Older licence. Not opened in depth. |
| LFM2-VL / LFM2.5-VL | 0.45-1.6B | "other", lfm1.0 (HF card, checked) | No counting result found | HF | LFM2-VL is marked deprecated [U]. |
| InternVL3.5-4B/8B | 4-8B | not checked | PixMo-Count test 62.4 / 61.9 [S27, checked]; 99.27% OOD synthetic PtC consistency (100% in distribution) [S5]; Apache-2.0 for 4B (HF card) | LoRA in [S5] | Best point-count consistency in [S5]. |
| SmolVLM2-2.2B, PerceptionLM, MiniCPM-V | 2-8B | not checked | PLM-3B 63, PLM-8B 68 on PixMo-Count [S27, checked]; no SmolVLM2 count number found | SmolVLM2 on TRL list [S19] | Not read in depth. |

### RL for perception with verifiable rewards

| Work | Base | Reward | Gain measured | Data and compute | Source |
|---|---|---|---|---|---|---|
| Perception-R1 (NeurIPS 2025) | Qwen2-VL-2B | Hungarian-matched point distance + format | PixMo-Count test 50.5 to 75.6. SFT only 59.9. SFT+RL 75.4. "w thinking" 72.8 (worse than no thinking) | 5k-10k sample subset per task (paper wording), 8 rollouts. NeurIPS 2025 venue not confirmed on arXiv. GPUs and hours not stated | [S1][S2] |
| Visual-RFT (ICCV 2025) | Qwen2-VL-2B/7B | IoU, class | COCO 2-shot detection 19.6 to 41.5 (SFT 21.0). LVIS rare 4.0 to 19.4 (SFT 10.0) | 200 steps, few-shot data. GPUs and hours not stated | [S3] |
| R1-V | Qwen2-VL-2B | count exact | SuperCLEVR 48.0% to 82.5% after 100 steps. But direct-answer base = 86% | "Less Than $3" | [S9] |
| CrowdVLM-R1 | Qwen2.5-VL-3B/7B | fuzzy count reward | 0/1 reward "underperforms" SFT; fuzzy reward beats SFT in domain, equal out of domain | not read | [S6] |
| Point-then-Count | Qwen2.5-VL, InternVL3.5, LLaVA-OV | SFT, not RL | In-domain real 76-82%; OOD real 16-34% by point count | LoRA r=32, 1x A100 80 GB, about 2 days per experiment | [S5] |
| DeepEyes | Qwen2.5-VL-7B | answer + tool-use bonus, zoom tool | V* 90.1% vs 71.2% base. Text-only RL ablation 88.5% on V* | end-to-end RL, no SFT | [S7] |
| ViGoRL (NeurIPS 2025) | Qwen2.5-VL | grounded points per thought, MCTS + GRPO | V*Bench 86.4% with multi-turn zoom | not read | [S10] |
| Pixel Reasoner | Qwen2.5-VL-7B | answer + curiosity bonus | paper exists (arXiv 2505.15966); the "collapses to zero" wording was not found in it. It describes a "learning trap" that the bonus avoids | warm-start SFT then RL | [U] |
| MechVL (ICML 2026) | Qwen3-VL-4B | LLM-judge accuracy + format + quality, DAPO | 76.36 SFT to 84.85 RL on MechVQA | not stated | [S14] |
| FloorplanVLM | not in abstract | SFT then GRPO for geometry | 92.52% external-wall IoU, no SFT-only baseline in the abstract | Floorplan-2M | [S28] |
| "RL makes MLLMs see better than SFT" | Qwen2.5-VL-3B | GRPO vs SFT | "RL shows a clear advantage over SFT in strongly vision-related VQA benchmarks" | not read | [S29] |

### RL and optimisation with an executor as the reward

| Work | What | Result | Source |
|---|---|---|---|
| Arctic-Text2SQL-R1 | GRPO, execution correctness + small syntax bonus | 7B matches 70B-class systems; 32B first on BIRD | [S17] |
| GEPA (ICLR 2026 oral) | Reflective prompt evolution, Pareto search | +6% average over GRPO, up to 20%, up to 35x fewer rollouts | [S18] |
| ifc-bench v2 / ECPPM 2026 | LLM agents on IFC: IfcOpenShell, SQLite, files, Neo4j | 78.7% for native IFC + IfcOpenShell (search snippet). **UNVERIFIED**: no paper or repo with this figure found; the public repo sylvainHellin/ifc-bench README has no 78.7 | [U] |

### Frameworks

| Framework | Vision RL today | Note | Source |
|---|---|---|---|
| TRL `GRPOTrainer` v1.18 | Yes. Tested: Gemma3, LLaVA-NeXT, Qwen2-VL, Qwen2.5-VL, SmolVLM2 | vLLM colocate/server. Losses: dapo (default), dr_grpo, sapo, cispo, vespo | [S19] |
| Unsloth | Yes. Qwen3-VL-8B, Qwen2.5-VL-7B, Gemma-3-4B notebooks; Qwen3.5-4B vision GRPO notebook | vLLM cannot LoRA the vision layers; Qwen3.5 GRPO needs `fast_inference=False`; QLoRA not recommended for Qwen3.5 | [S20][S21] |
| prime-rl 0.10 + verifiers 0.4 | "Qwen-VL and Kimi K2.5 are supported" for multimodal RL | Multi-node oriented. Post dated 2026-10-19 | [S30] |
| Tinker (Thinking Machines) | Vision input since Dec 2025, LoRA only | Hosted API, costs money per token | [U] |
| OpenPipe ART | No vision example found | Text agents (incl. text-to-SQL) | [U] |
| EasyR1 (verl) | Used by MechVL for DAPO on Qwen3-VL-4B | | [S14] |
| DSPy GEPA | Images pass to the reflection LM as `dspy.Image` | Needs a metric with text feedback | [U, docs read only via search] |

## What we can use this weekend

Time budget assumption: about 24 h wall time, 1-2 A100 80 GB on Verda at $2.37/h per GPU (price from the repo `AGENTS.md`).

| Item | What to run | Licence | Effort [E] | Expected value [E] |
|---|---|---|---|---|
| A. Detector for cubicasa symbols | RT-DETR-L or RF-DETR on CubiCasa5K-style boxes; count = detections above threshold; show boxes | Ultralytics AGPL-3.0 (RF-DETR Apache-2.0 [U]); CubiCasa5K CC BY-NC-SA 4.0 | 4-6 h incl. labels and 2.3 h training [S16] | Largest gain on doors and windows, where the mode scores 12-14% [M] |
| B. Zero-shot pointer as a second opinion | Qwen3.5-4B or Molmo2-4B prompted to point, count = number of points | Apache-2.0 | 2-3 h | A disagreement signal for abstention, not a primary answer |
| C. SFT a pointer VLM | Qwen3-VL-4B or Qwen2.5-VL-3B, LoRA r=16-32, labels = detector boxes or DXF-derived points, output one point per object | Apache-2.0 base | 6-10 h incl. data | Probably below the detector on cubicasa [E]; meets Stoa's "small fine-tuned model" wish |
| D. GRPO on top of C | TRL `GRPOTrainer` with vLLM colocate, reward = Hungarian point match + format, only high-entropy templates, 8 rollouts | as above | +6-10 h, 1 GPU | +a few points in domain [E, based on S1]; unknown out of domain |
| E. GEPA on the question parser or the IFC agent prompt | `dspy.GEPA(metric=exact_or_2pct, ...)` on a held-out split | MIT [U] | 3-5 h | Cheaper than RL for program-style questions [S18] |
| F. Distil the frontier model into the parser | Label unseen question phrasings with Claude once, SFT a small text model or keep a lookup | - | 2-4 h | Lowers per-question cost; RL not needed |

Concrete commands (from the sources):

```sh
# TRL VLM GRPO example (S19), adapted: the doc uses --nproc_per_node 8 and --deepspeed zero3 and no --max_completion_length change. Replace the reward with point matching.
torchrun --nproc_per_node 1 examples/grpo_visual_math/grpo_visual_math.py \
  --model_name_or_path Qwen/Qwen2.5-VL-3B-Instruct --use_vllm --vllm_mode colocate \
  --use_peft --lora_target_modules q_proj v_proj --max_completion_length 1024 --dtype bfloat16
```

```python
# Unsloth Qwen3.5 vision (S21): GRPO only with fast_inference=False; use transformers v5; avoid 4-bit.
from unsloth import FastVisionModel
model, tok = FastVisionModel.from_pretrained("Qwen/Qwen3.5-4B", load_in_4bit=False, fast_inference=False)
```

Realistic view of 24 h on 1-2 A100 [E]:

- SFT of a 3-4B VLM with LoRA on about 5-10k images: 2-5 h per run. Unsloth lists 10 GB VRAM for Qwen3.5-4B bf16 LoRA [S21].
- GRPO with 8 rollouts per image, about 1-2k image tokens and up to 300 output tokens (a plan with 92 windows needs a long point list [M max]):
  roughly 1-3k prompts per GPU-hour with vLLM, several times fewer without vLLM [E]. Perception-R1 used a 5k-10k subset per task [S1];
  Visual-RFT used 200 steps [S3]. So one useful GRPO run fits in 4-10 h on one A100 [E].
- That leaves time for one SFT run, one RL run, and one evaluation pass. There is no time for a hyperparameter search.
- Cost: under $60 of GPU time for the whole plan [E].

How each option moves the four criteria:

| Option | Accuracy (hidden set) | Verifiability | Creativity | Inference cost |
|---|---|---|---|---|
| Detector + rules | High on cubicasa-like plans; drops on scans [E] | Boxes, deterministic | Low-medium | Near zero |
| SFT pointer VLM | Medium; OOD collapse risk [S5] | Points | Medium | Low (own GPU) |
| SFT + GRPO pointer | Medium+, in domain only [S1][S6] | Points | High (Stoa likes it) | Low |
| GEPA on frontier prompts | Medium-high on text/IFC | Trace and program | Medium | Per-call API cost |

## What does not work

- **0/1 accuracy reward for counting.** GRPO with it "underperforms compared to supervised fine-tuning" [S6].
- **Forced chain of thought for small perception models.** Perception-R1: thinking 72.8 vs 75.6 without [S1]. R1-V: the 2B base answers
  directly at 86%, above the 82.5% GRPO model, and the authors say forced CoT "may be not only unnecessary but potentially detrimental" [S9].
- **Trusting the model's stated count.** On the synthetic OOD split (up to twice the training counts), the count and the number of points disagree often (Qwen2.5-VL-3B consistency 20.56%; InternVL3.5 99.27%) [S5].
- **Expecting fine-tuning to transfer to higher counts.** OOD real accuracy after fine-tuning was 1-26% (direct and PtC) when test images had up to twice the training counts [S5]. A change of drawing style was not tested.
- **Zoom-agent RL without an extra incentive.** Pixel Reasoner reports a "learning trap" that the curiosity bonus avoids [U, wording of the "collapse" not found in the paper]. DeepEyes beats a
  text-only RL ablation by only 1.6 points on V* (90.1 vs 88.5), but by 12.2 points on HR-8K (72.6 vs 60.8) [S7]. For floor plans, a fixed tiling grid is cheaper than learning to zoom [E].
- **Claiming an RL gain without a control.** Random rewards gave Qwen2.5-Math-7B +21.4 points [S12]; the effect is "highly model-dependent".
- **SFT alone on few examples.** Visual-RFT one-shot classification: SFT 51.7 vs base 56.0 (SFT made it worse) [S3].
- **Frontier VLMs as symbol counters.** Door and window counting "remains unsolved", "often 0.40-0.55 accuracy" [S15].
  Counting on counterfactual images averaged 17.05% [S8].

## Open questions

1. Are Stoa's cubicasa5k PNGs the same images as public CubiCasa5K? If yes, public SVG labels give point supervision but raise leakage. Ask Stoa.
2. Does the hidden set contain counts on historic scans (habs, finna, europeana, wikimedia)? No public method in this track has evidence of transfer to them, and [S5] only tests higher counts, not new styles.
3. How is free text scored? An RL reward for ifc_bench text needs a rule; MechVL used an LLM judge [S14], which is not a verifiable reward.
4. Can DXF geometry in swiss_dwellings give free point labels aligned to the PNG? That gives clean training data without leakage, but only for one drawing style.
5. Does Stoa count a self-hosted GPU model as "low inference cost"? A detector on CPU (about 2 s per image [S16]) avoids the question.
6. No source gives GPU-hours for Perception-R1 or Visual-RFT. Our own smoke test is the only way to know the rollout throughput.

## Check of the prior research

Checked against `inputs/prior-research/weekend-plan.md` and `research-tracks.json`, track "Fine-tuning small open VLMs".

| Prior claim | Verdict |
|---|---|
| "Generic SFT gave no counting gain in Perception-R1" | Partly wrong. SFT only: PixMo val 60.2 to 58.0 (worse), test 50.5 to 59.9 (better) [S1]. RL gave the large gain (75.6). |
| JSON: "SFT only 58.0/59.9, 74.9/72.8" | 74.9/72.8 is the "w thinking" row, not SFT [S1]. |
| Visual-RFT +21.9 COCO 2-shot, +15.4 LVIS | Confirmed: 19.6 to 41.5; 4.0 to 19.4 [S3]. |
| TRL tested VLMs (Gemma3, LLaVA-NeXT, Qwen2-VL, Qwen2.5-VL, SmolVLM2), Qwen3-VL only on the agent list | Confirmed [S19]. |
| Unsloth: vLLM cannot LoRA vision layers; set `finetune_vision_layers=False` | Confirmed [S20]. Add: Qwen3.5 GRPO needs `fast_inference=False` [S21]. |
| Qwen3.5-4B CountBench 96.3, RefCOCO 88.1, OCRBench 85.0; 9B 97.2/89.7/89.2 | Confirmed [S22]. |
| RT-DETR-L about 90 AP50 in 2.3 h on 2x A100 | Confirmed: doors 89.8, windows 89.3, walls 82.3 [S16]. Add AGPL-3.0 caveat. |
| Frontier models 0.40-0.55 on door/window counts | Confirmed from the abstract [S15]. Per-model CSV figures not checked. |
| PtC: LoRA r=32, 1x A100, up to 2 days per experiment | Confirmed [S5]. Missing: the OOD collapse (1-34% real OOD, defined as up to 2x the training counts), which weakens the "Pointer VLM" case. |
| Molmo2: Apache-2.0, training data partly non-commercial | Confirmed [S23]. Counting scores came from a secondary leaderboard [S27], which matches the Molmo2 paper table. |
| "Dropped: the GRPO Question Compiler" | Agree. GEPA [S18] or a lookup is cheaper for question parsing. |
| "Pointer VLM - stretch only" | Agree, with a stronger reason: OOD count collapse [S5] and mode hacking [M]. |

## Sources

| id | URL | title | date | claim it supports | exact supporting quote | check |
|---|---|---|---|---|---|---|
| S1 | https://arxiv.org/html/2504.07954 | Perception-R1: Pioneering Perception Policy with Reinforcement Learning (Yu, Lin et al.) | 2025-04, NeurIPS 2025 | Counting gain, SFT vs RL, point reward, thinking hurts | Table 3(a) "Qwen2-VL 2B 60.2 50.5", "Perception-R1 2B 78.1 75.6"; Table 5 "SFT only 58.0 59.9", "w thinking 74.9 72.8"; "the reward is derived from the Euclidean distance computed during reward matching." | corrected: numbers match (Table 5: w/o RL 60.2/50.5, SFT only 58.0/59.9, w thinking 74.9/72.8, RL 78.1/75.6, Qwen2-VL-2B). "10k samples" is a 5k-10k subset per task. NeurIPS 2025 not shown on arXiv. The arXiv abstract page names Qwen2.5-VL-3B as base; the HTML body uses Qwen2-VL-2B |
| S2 | https://github.com/linkangheng/pr1 | PR1 official code | 2025 | Licence and weights | "Apache-2.0 license"; checkpoint `Kangheng/PR1-Qwen2-VL-2B-Counting` | confirmed (Apache-2.0, checkpoint in README) |
| S3 | https://arxiv.org/html/2503.01785 | Visual-RFT: Visual Reinforcement Fine-Tuning (Liu, Sun et al.) | 2025-03, ICCV 2025 | RFT vs SFT in few-shot | "We then train the Qwen2-VL-2/7B model for 200 steps using both reinforcement fine-tuning and SFT"; Table 2 1-shot: baseline 56.0, SFT 51.7, Visual-RFT 80.3; Table 3 2-shot: SFT 21.0, Visual-RFT 41.5, baseline 19.6 | confirmed (all numbers; ICCV 2025 in README) |
| S4 | https://github.com/Liuziyu77/Visual-RFT | Visual-RFT repository | 2025 | Code available | repository with datasets `laolao77/ViRFT_COCO_8_cate_4_shot` (seen in search; licence not opened) | confirmed (Apache-2.0, dataset named) |
| S5 | https://arxiv.org/html/2603.21746 | Getting to the Point: Pointing Improves LVLMs at Counting (Alghisi et al.) | 2026-03, rev. 2026-05 | PtC, OOD collapse, count vs points mismatch, compute | "a single NVIDIA A100 (80 GiB) GPU with batch size 1"; "each experiment requires at most two days"; "the number of predicted coordinates often does not match the model's final count" | corrected: numbers and LoRA r=32, 1x A100, two days confirmed. "OOD" means up to 2x the training counts, not a new style; the abstract says PtC improves OOD. InternVL3.5 OOD consistency is 99.27, not 100. Quote "at most two days" is not verbatim ("requires two days") |
| S6 | https://arxiv.org/abs/2504.03724 | CrowdVLM-R1 (Wang et al.) | 2025-03, rev. 2025-11 | 0/1 reward worse than SFT | "GRPO with a standard 0/1 accuracy reward underperforms compared to supervised fine-tuning (SFT)." | confirmed (abstract quote) |
| S7 | https://arxiv.org/html/2505.14362v1 | DeepEyes: Incentivizing "Thinking with Images" via RL (Zheng et al.) | 2025-05 | Zoom-tool RL gains and small margin over text-only RL | V* 90.1 (DeepEyes) vs 88.5 text-only RL ablation; 71.2 Qwen2.5-VL-7B baseline (from the search summary of the results table; HTML page found but table read via summary) | confirmed (V* 90.1, 88.5, 71.2). Caveat added: HR-8K 72.6 vs 60.8 |
| S8 | https://arxiv.org/html/2505.23941v4 | Vision Language Models are Biased (Vo et al.) | 2025-05, v4 | Counting bias; counting-trained models better | "scoring an average of 17.05% accuracy in counting"; "(such as Molmo-72B and Moondream-2B) can score a mean accuracy of 36.02%" | confirmed (17.05%, 36.02%; the 36.02% is for pointing models Molmo-7B-D/72B, Moondream-2B) |
| S9 | https://github.com/Deep-Agent/R1-V | R1-V | 2025-02 | Cheap counting RL; base model direct answer is better | "Qwen2VL-2B-Instruct-GRPO-100step: 82.5%"; direct output gives "a much higher score (86%) on SuperClevr"; CoT "may be not only unnecessary but potentially detrimental" | confirmed (48.0, 82.5, 86%, CoT note, title "Less Than $3") |
| S10 | https://arxiv.org/abs/2505.23678 | Grounded Reinforcement Learning for Visual Reasoning (ViGoRL) | 2025-05, NeurIPS 2025 | Grounded-point RL with zoom | 86.4% on V*Bench (from search summary of the paper; abstract page not fully read) | partly: 86.4% V*Bench confirmed; NeurIPS 2025 not shown on arXiv |
| S11 | https://arxiv.org/abs/2504.13837 | Does RL Really Incentivize Reasoning Capacity in LLMs Beyond the Base Model? (Yue et al.) | 2025-04, v5 2025-11 | RL narrows; distillation adds | "the base models achieve a higher pass@k score when k is large"; "distillation can introduce new reasoning patterns from the teacher" | confirmed |
| S12 | https://arxiv.org/abs/2506.10947 | Spurious Rewards: Rethinking Training Signals in RLVR (Shao et al.) | 2025-06, rev. 2026-02 | Need controls | "improves MATH-500 performance for Qwen2.5-Math-7B by 21.4 percentage points using randomly assigned rewards"; "highly model-dependent" | confirmed |
| S13 | https://arxiv.org/abs/2611.14912 | Rethinking "RL Generalizes, SFT Memorizes": The Role of SFT Data (Hou et al.) | 2026-11-11 | SFT can match RL | "matching the total rollout budget enables SFT to generalize as well as RL." | confirmed (arXiv 2611.14912, 2026-11-11) |
| S14 | https://github.com/xiaofengShi/MechVQA | MechVQA / MechVL (ICML 2026) | 2026 | SFT+DAPO on Qwen3-VL-4B for drawings | Table: "MechVL-4B-SFT ... 76.36", "MechVL-4B-RL ... 84.85"; "Initialize from `Qwen3-VL-Instruct-4B`"; "Apache 2.0 License" | confirmed (76.36, 84.85, Qwen3-VL-Instruct-4B, Apache-2.0, ICML 2026 badge, DAPO, judge-based reward) |
| S15 | https://arxiv.org/abs/2601.04819 | AECV-Bench (Kondratenko et al.) | 2026-01-08 | Frontier VLMs fail door/window counts | "especially reliable counting of doors and windows - remains unsolved"; "(often 0.40-0.55 accuracy)" | confirmed (abstract) |
| S16 | https://github.com/OldDeLorean/rtdetr-floorplan-detector | RT-DETR-L floor-plan detector (Architect Ant, arXiv 2606.10953) | 2026 | Small detector accuracy and cost | Door AP50 89.8, Window 89.3, Wall 82.3; "60 epochs at 1024×1024 on 2×A100, taking about 2.3 hours"; Ultralytics "AGPL-3.0"; "32.8 M parameters" | corrected: AP50 89.8/89.3/82.3, 2.3 h on 2x A100, 32.8M, AGPL-3.0, ~0.1 s GPU and ~2 s CPU confirmed. Classes are only wall, door, window, railing, linkage_point. Repo is part of the Architect-Ant furnishing paper (arXiv 2606.10953), not a detector paper. Trained on the official CubiCasa5K split |
| S17 | https://arxiv.org/abs/2505.20315 | Arctic-Text2SQL-R1 (Yao et al., Snowflake) | 2025-05, rev. 2026-01 | Execution reward RL works for program synthesis | reward "based solely on execution correctness" (abstract wording via fetch); "a reinforcement learning (RL) framework and model family designed to generate accurate, executable SQL" | confirmed (abstract: execution-correctness reward, 7B beats 70B-class, top of BIRD) |
| S18 | https://arxiv.org/abs/2507.19457 | GEPA: Reflective Prompt Evolution Can Outperform RL (Agrawal et al.) | 2025-07, v2 2026-02, ICLR 2026 oral | Prompt optimisation beats GRPO with fewer rollouts | "a prompt optimizer that thoroughly incorporates natural language reflection to learn high-level rules from trial and error"; abstract: beats GRPO by 6% average, up to 20%, up to 35x fewer rollouts | partly: abstract numbers confirmed (6%, 20%, 35x); "ICLR 2026 oral" not verified; repo is MIT |
| S19 | https://huggingface.co/docs/trl/en/grpo_trainer | TRL GRPO Trainer docs (v1.18.0) | 2026 | VLM support list, vLLM | "GRPO supports training Vision-Language Models (VLMs)"; tested: Gemma3, LLaVA-NeXT, Qwen2-VL, Qwen2.5-VL, SmolVLM2; "Compatibility with all VLMs is not guaranteed." | confirmed (v1.18.0 listed, VLM list, dapo default, sapo/cispo/vespo/dr_grpo exist). The example command in the doc uses 8 GPUs and deepspeed zero3 |
| S20 | https://unsloth.ai/docs/get-started/reinforcement-learning-rl-guide/vision-reinforcement-learning-vlm-rl | Unsloth Vision RL guide | 2025-09 (X post date) | Vision GRPO support and caveats | "Unsloth now supports vision/multimodal RL with Qwen3-VL, Gemma 3 and more."; "vLLM does not support LoRA for vision/encoder layers" | confirmed (quotes); date "2025-09" not verified |
| S21 | https://unsloth.ai/docs/models/qwen3.5/fine-tune | Unsloth Qwen3.5 fine-tune guide | 2026 | Qwen3.5 GRPO needs no-vLLM; VRAM | GRPO works "if you disable fast vLLM inference and use Unsloth inference instead"; 4B bf16 LoRA "10GB" | confirmed (fast_inference=False, 4B 10GB, transformers v5, QLoRA note is for MoE) |
| S22 | https://huggingface.co/Qwen/Qwen3.5-4B | Qwen3.5-4B model card | 2026-02 | Licence and counting score | "License: apache-2.0"; CountBench 96.3; RefCOCO(avg) 88.1; OCRBench 85.0 | confirmed (apache-2.0 via HF API and card; 4B 96.3/88.1/85.0, 9B 97.2/89.7/89.2) |
| S23 | https://huggingface.co/allenai/Molmo2-8B | Molmo2-8B model card (Ai2) | 2025-12 | Licence, data caveat, no training code yet | "This model is licensed under Apache 2.0."; "trained on third party datasets that are subject to academic and non-commercial research use only" | confirmed (Apache-2.0 tag, non-commercial data sentence, code "made available at a later date") |
| S24 | https://docs.moondream.ai/ | Moondream docs | 2026 | Licence and vendor count score | "Business Source License 1.1" with "Additional Use Grant" "(No Third-Party Service)"; CountBenchQA "Moondream 3 Preview 93.2" | confirmed (BSL 1.1, No Third-Party Service, CountBenchQA 93.2 in blog/docs; 9B/2B active; Finetuning (beta) in docs nav) |
| S25 | https://huggingface.co/google/gemma-4-E4B-it | Gemma 4 E4B model card | 2026 | Licence and capabilities | "License: apache-2.0"; "handwriting recognition, and pointing." | confirmed (apache-2.0, pointing, 2.3B/4.5B effective) |
| S26 | https://huggingface.co/microsoft/Florence-2-large | Florence-2-large model card | 2023-11 paper | Licence and tasks | "License: mit"; COCO OD AP 39.8 for this checkpoint | confirmed (MIT, 0.77B, COCO OD AP 39.8) |
| S27 | https://www.sota2.com/research/sota/visual-counting-on-pixmo-count-test | PixMo-Count test leaderboard (secondary) | 2026-01 entries | Small-model PixMo-Count scores | figures from the page (Molmo2-4B 88.1, Qwen3-VL-4B 58, Qwen3-VL-8B 65). Opened in the fact check. | confirmed: opened. Molmo2-4B 88.1, Qwen3-VL-4B 58, Qwen3-VL-8B 65, InternVL3.5 62.4/61.9, PLM 63/68 are on the page; Molmo2 values match the Molmo2 paper (arXiv 2601.10611) |
| S28 | https://arxiv.org/abs/2602.06507 | FloorplanVLM (Liu et al.) | 2026-02-06 | SFT then GRPO on floor plans | "Supervised Fine-Tuning (SFT) for structural grounding and quality annealing, followed by Group Relative Policy Optimization (GRPO) for strict geometric alignment"; "92.52%" | confirmed (abstract, 92.52%) |
| S29 | https://arxiv.org/abs/2510.16333 | RL makes MLLMs see better than SFT (Song et al.) | 2025-10, rev. 2026-04 | RL improves visual representations | "RL shows a clear advantage over SFT in strongly vision-related VQA benchmarks" | confirmed |
| S30 | https://www.primeintellect.ai/blog/prime-rl-0-10-verifiers-0-4 | prime-rl 0.10 and verifiers 0.4 | 2026-10-19 | Multimodal RL framework | "Qwen-VL and Kimi K2.5 are supported." | confirmed (2026-10-19, "Qwen-VL and Kimi K2.5 supported") |

Measured facts [M] come from a script over `questions.jsonl` (cubicasa5k English templates: answer share equal to template mode,
and max answer). The cubicasa5k folder holds only PNG files (4,787) [M], so the Stoa data has no point labels.

## Verification

Date: 2026-11-13. Independent fact check by a second agent. Method: arXiv abs and HTML pages, GitHub READMEs and API, Hugging Face model API and cards, vendor docs and blog, all fetched directly.

- Sources opened: 30 of 30 numbered sources (S1-S30), plus 8 sources behind [U] tags: Pixel Reasoner (found), ifc-bench (not found), Tinker docs (partly), OpenPipe ART, EasyR1, DSPy and GEPA repos (licences), Molmo2 paper (found).
- Result: confirmed 25, corrected 3 (S1, S5, S16), partly 2 (S10, S18), not found 0 of the numbered sources. One [U] claim is not found: the "ifc-bench v2 / ECPPM 2026, 78.7%" row, now marked **UNVERIFIED**.
- Findings that rest on corrected or unverified sources: finding 3 (rewritten, see below). Finding 6 rests on S17 and S18, which are confirmed. The ifc-bench 78.7% row is **UNVERIFIED** and no decision depends on it.

Corrections made in this file:

1. Finding 3 and "What does not work": the OOD split in [S5] means images with up to twice the training counts, not a new drawing style. The paper says PtC improves OOD generalisation. The numbers (1-26%, 16-34%, consistency 20.56%) are right.
2. InternVL3.5 OOD synthetic PtC consistency: 99.27%, not 100% (100% is in distribution).
3. Perception-R1 data size: "10k PixMo-Count samples" changed to a 5k-10k subset per task. NeurIPS 2025 and the base model on the arXiv abstract page (Qwen2.5-VL-3B) differ from the HTML body (Qwen2-VL-2B). The tables used are from the HTML body.
4. Finding 4 and item A: the [S16] detector has 5 classes (wall, door, window, railing, linkage_point). It does not count toilets, sinks or kitchens. Title narrowed to doors and windows. The absence claim "no published small-VLM result comes close" was not checked.
5. [S5] quote "at most two days" is not verbatim. The paper says each experiment requires two days. "Up to 2 days" changed to "about 2 days".
6. DeepEyes: added that the text-only RL ablation is 12.2 points behind on HR-8K (72.6 vs 60.8), so "only 1.6 points" holds on V* only.
7. [S8] 36.02% is the mean of pointing models (Molmo-7B-D, Molmo-72B, Moondream-2B), not of all "models trained to count".
8. Pixel Reasoner: the paper exists (arXiv 2505.15966), but the "collapses to zero" wording was not found. Changed to the "learning trap" idea.
9. [U] tags replaced after checking: Qwen3-VL (Apache-2.0), Qwen2.5-VL (3B Qwen research, 7B Apache-2.0), PaliGemma 2 (Gemma terms), LFM2-VL ("other", lfm1.0), InternVL3.5-4B (Apache-2.0), and the PixMo-Count figures (S27 opened, matches the Molmo2 paper).
10. TRL command: the doc example uses 8 GPUs with deepspeed zero3. The report command is adapted. Noted in a comment.
11. Not verified, kept as written: "ICLR 2026 oral" for GEPA, "NeurIPS 2025" for Perception-R1 and ViGoRL, Tinker price and LoRA-only claim, OpenPipe ART having no vision example, DSPy `dspy.Image` for GEPA, "LFM2-VL is deprecated", and the Unsloth post date.
12. Measured facts [M] were not re-run. Local data files were outside this fact check.

