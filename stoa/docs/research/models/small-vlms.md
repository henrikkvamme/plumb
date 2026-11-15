# Small open vision-language models for pointing at drawings

Date: 2026-11-14. Scope: open VLMs of about 2B to 12B parameters that one A100 80 GB can fine-tune in a few hours. Task: "point at every door", count by pointing, read labels, answer from a crop.

Labels: SOURCED = I opened the source on 2026-11-14 (id in brackets, see Sources). ESTIMATE = my own judgement, not measured. UNVERIFIED = I could not open a source, or I did not run it.

Scores from different papers use different protocols. Do not compare them across papers. No model here was tested on construction drawings by its authors.

## In short

1. Primary: `tencent/WeVisOne-VL-4B` (Qwen3-VL-4B base, Apache-2.0, dense pointing with up to 500 points per answer). [S1, S2] SOURCED.
2. Fallback: `allenai/Molmo2-4B` (Apache-2.0, pointing is a core pre-training task, 4B, own training code). `allenai/Molmo2-8B` if time allows. [S3, S4] SOURCED.
3. GRPO with a per-point matching reward: no vendor recipe exists for these models. It works in tooling for the Qwen3-VL class (ms-swift, EasyR1/verl, TRL, Unsloth), so WeVisOne can use it with a custom reward function. Molmo2 has no GRPO path. [S5-S9] SOURCED for the tools, UNVERIFIED that it runs on WeVisOne.
4. Do SFT first. Run a 1-hour check before you commit (see "Risks"). Count = number of points returned, never a number the model states.
5. Do not start from plain Qwen3-VL or Qwen3.5 for dense pointing. They miss most instances on dense scenes. Dense200 pointing F1: 42.2 for Qwen3-VL-8B, 10.5 for Qwen3.5-9B, against 87.0 for WeVisOne-VL-4B. Dense200 box-detection mean F1: 13.8, 18.0 and 71.3. [S1, arXiv 2610.31329 v2 tables 2 and 5] CORRECTED in verification (the first draft quoted the box-detection F1 as if it were a pointing score). The claim "loop above 40 to 50 objects" is UNVERIFIED: the paper only says its stage 1 data was capped at 50 points per category to avoid repetitive output collapse.
6. Verification result (2026-11-14): the primary recommendation stands. LocateAnything-3B is slightly ahead of WeVisOne-VL-4B on Dense200 pointing (87.6 vs 87.0), and WeVisOne leads on detection and on rejection. See "Verification".

Context from the earlier team reports: DECISION.md says no RL this weekend, a detector may be the main path, and a VLM pointer is the second witness. This report fits that plan: SFT of a pointer first, RL only if there is time. Prior public result on drawings: AECV-Bench door counts 0.09 to 0.12 for general VLMs (Qwen3-VL-8B 0.09 and 0.10). [S10] SOURCED (prior report).

## Candidates

Sizes and ids are from the model cards. "Point/box" is the native output format. Fine-tune VRAM and hours are ESTIMATES, not measured.

| Model (exact id) | Params | Licence | Point/box output | Max image / tiling | Tuning tools | Serving | Published counting / pointing |
|---|---|---|---|---|---|---|---|
| `tencent/WeVisOne-VL-4B` (also `-2B`) | 4B in name; HF lists 5B params incl. vision encoder, plus 9.6M mask decoder | Apache-2.0 [S1] | Text with coordinate tokens `<0>`..`<1000>`: `<ref>door</ref><point><x><y>,...</point>`; up to 500 points; returns `None` if absent [S1, S2] | Trained to 1,960 visual tokens (about 2 MP); Qwen3-VL processor allows more; tile big sheets [S1, S11] | Qwen3-VL architecture: ms-swift, TRL, Unsloth should load it (UNVERIFIED, not run). Vendor repo has no training script [S2] | Needs vendor package `wevisone_vl` for masks; text pointing should work in vLLM as Qwen3-VL (UNVERIFIED) | PixMo-Count test 89.6 acc; PointBench 71.9; Dense200 point F1 87.0 (LocateAnything-3B 87.6); Dense200 detection mean F1 71.3 [S1] (vendor numbers, confirmed) |
| `allenai/Molmo2-4B` / `Molmo2-8B` | 4B / 8B (Qwen3 LLM + SigLIP2) | Apache-2.0 [S3, S4] | Text points, `x y` in 0-1000 with object index; last index is the count [S3, S4] | Multi-crop tiling inside the model; image resolution fixed by recipe [S4] | Own repo `allenai/molmo2`: pretrain, SFT and long-context SFT scripts [S4]. HF transformers path exists. No GRPO | vLLM support: UNVERIFIED | Strong open-model results on counting and pointing in the Molmo2 paper (Tables 6, 7) [S4]. I did not copy values: protocols differ |
| `allenai/MolmoPoint-8B` | 8B | Apache-2.0 [S3] | Grounding tokens, not text coordinates; sets a new state of the art on PointBench and PixMo-Points [S3] | as Molmo2 | Training code in `allenai/molmo2` (MolmoPoint README) [S3] | UNVERIFIED | PointBench 70.7 reported in the paper abstract [S3] |
| `Qwen/Qwen3-VL-4B-Instruct`, `-8B-Instruct` | 4B / 8B | Apache-2.0 [S11] | JSON `bbox_2d` / `point_2d`, relative 0-1000 [S11] | Patch 16, merge 2, so 32 px per token; processor up to 16.7 MP [S11] | ms-swift, TRL, Unsloth, LLaMA-Factory, 2U1 repo, EasyR1 [S5-S9, S12] | vLLM (mature) [S13] | Weak on dense output: loops above 40-50 instances [S1] |
| `Qwen/Qwen3.5-2B/4B/9B` | 2-9B | Apache-2.0 [S14] | Boxes as Qwen3-VL (UNVERIFIED for points) | Large | Unsloth: GRPO needs `fast_inference=False` [S8] | vLLM recipe exists [S13] | CountBench 96.3 for 4B on easy, sparse images [S14]; Dense200 F1 18.0 for 9B [S1] |
| `google/gemma-4-E4B-it`, `gemma-4-12B-it` (12B id UNVERIFIED) | 4.5B eff. (8B with embeddings) / 12B | Apache-2.0 for E4B-it per the model card (CORRECTED, was "Gemma 4 licence") [S15] | Boxes `box_2d` [y1,x1,y2,x2] 0-1000; no native point format found | Variable token budget | Unsloth supports it; GRPO needs `fast_inference=False` [S8] | vLLM, HF | No pointing or counting score found for small sizes. UNVERIFIED |
| `OpenGVLab/InternVL3_5-8B` | 8B | Apache-2.0 | Boxes in text (UNVERIFIED) | 448 px tiles, up to 12 tiles | Own scripts, ms-swift | LMDeploy, vLLM | Appears in the Molmo2 paper tables [S4] |
| `zai-org/GLM-4.6V-Flash` | 9B | See card | Boxes (UNVERIFIED) | - | - | vLLM | Not checked in depth. UNVERIFIED |
| `LiquidAI/LFM2.5-VL-3B` | 3B | LFM licence (not read in detail) | Boxes 0-1000 | - | TRL doc exists | - | Not checked. UNVERIFIED |
| Moondream (`moondream3.1-9B-A2B`) | 9B MoE, 2B active | Not read | Native `point` and `detect` | - | No open fine-tune path found. UNVERIFIED | Own runtime | Not checked. UNVERIFIED |
| `nvidia/LocateAnything-3B`, `GroundingPI` | 3B | Not read in full | Dense detection and pointing | - | - | - | Used as baselines in [S1] only. UNVERIFIED otherwise |
| SmolVLM, PaliGemma, Florence-2 | 0.2-3B | - | Boxes via location tokens | Florence-2 is low resolution (about 768 px, from memory) | HF scripts | - | No newer release found for any of them in Nov 2026. Too small or too coarse for A0 sheets. ESTIMATE |

Why WeVisOne ranks first (SOURCED [S1, S2]):

- It starts from Qwen3-VL, so the tooling is mature.
- It is trained on dense detection, pointing, counting and OCR, with an explicit "no target" answer (96.4 rejection rate on WeRef-Bench).
- It has the best published dense numbers in the 4B class against LocateAnything-3B, Rex-Omni-3B, Qwen3-VL-8B and Qwen3.5-9B. These are vendor numbers on natural images, not drawings.
- Cost: it is new (October 2026). The vendor repo has inference and evaluation code, but no SFT recipe. I did not load it in ms-swift, TRL or vLLM.

Why Molmo2 is the fallback (SOURCED [S3, S4]): pointing is a pre-training task, the point list ends with a count, the training code is public, and a matched-LoRA test on another domain showed Molmo2 learns pointing faster than Qwen3-VL (single study, different domain, treat as a hint). Cost: no GRPO path, no tiling control, and weaker serving support.

## Recommendation and recipe

Model: `tencent/WeVisOne-VL-4B`. Task framing: one call per sheet or tile with the prompt `point to: door`. Answer = the list of points. Count = `len(points)`, after you remove duplicates in tile overlaps.

### Data (ESTIMATE of effort, 1 to 2 hours)

- One training sample = image (tile) plus `<image>point to: door` and the answer `<ref>door</ref><point><512><640>,<...><...></point>`. Bins are x and y times 1000 divided by width and height (parser in the vendor repo [S2]).
- Use door centres from your labels (IFC, DXF, or the labelled PNG sets). Use box centres when you only have boxes.
- Add negative tiles with the answer `None`. Add other classes (window, room label, text) so the model keeps general skills.
- Tile at about 1,400 px square (about 1,960 visual tokens), with 15 percent overlap. Keep the tile scale the same at test time.

### SFT with ms-swift (version 4.6.1 docs, [S5])

Flag names are from the docs. The whole command is UNVERIFIED as run on WeVisOne.

```
IMAGE_MAX_TOKEN_NUM=1960 swift sft \
  --model tencent/WeVisOne-VL-4B \
  --dataset doors.jsonl \
  --tuner_type lora --lora_rank 32 --lora_alpha 64 --target_modules all-linear \
  --freeze_vit false --freeze_aligner false \
  --torch_dtype bfloat16 --attn_impl flash_attn --padding_free true \
  --gradient_checkpointing true \
  --num_train_epochs 3 --learning_rate 1e-4 \
  --per_device_train_batch_size 1 --gradient_accumulation_steps 8 \
  --output_dir out/doors-sft
```

- Check: `--tuner_type` is the current flag (not `--train_type`). `IMAGE_MAX_TOKEN_NUM` caps image tokens per image. [S5] SOURCED.
- The `<0>`..`<1000>` tokens are real tokens in the tokenizer, so do not add them again. [S2] SOURCED (tokenizer inspected).
- Keep the 9.6M-parameter mask decoder out of training. You do not need masks.
- Learning rate, rank and epochs are ESTIMATES. Start with LoRA rank 32, 3 epochs, and stop when the validation F1 stops rising.
- Time and VRAM: ESTIMATE 2 to 4 hours for about 3,000 tiles at 1,960 tokens. Peak about 40 to 60 GB with gradient checkpointing. Cost about 5 to 10 USD at 2.37 USD per hour.
- Run it with `pnpm j gpu up 1A100.22V --hours 4`, then `pnpm j gpu run`, and `pnpm j gpu down` when the adapter is local.

Other tools that load the Qwen3-VL class (SOURCED as supported for Qwen3-VL, UNVERIFIED for WeVisOne): 2U1/Qwen-VL-Series-Finetune [S12], TRL 1.18.0 SFTTrainer, Unsloth 2026.11.4 [S8], LLaMA-Factory.

### Inference

- Use HF transformers with the vendor package, or vLLM 0.33.0 as a Qwen3-VL model. [S13] vLLM path UNVERIFIED for WeVisOne.
- Greedy decoding, temperature 0, `max_new_tokens` of about 4,000 (500 points need roughly 6 tokens each).
- ESTIMATE: 4B in bf16 needs about 10 GB for weights. One tile takes a few seconds. Cost per document stays far below the 10 cent target.

### Is GRPO with a per-point matching reward supported?

| Model class | Tooling today | Verdict |
|---|---|---|
| WeVisOne-VL-4B (Qwen3-VL) | ms-swift `swift rlhf --rlhf_type grpo` with vLLM colocate and external reward plugins [S5, S6]; EasyR1/verl 0.9.1 [S9]; TRL 1.18.0 GRPOTrainer (Qwen3-VL not in its CI tests) [S7]; Unsloth: vLLM cannot LoRA the vision layers, so use `fast_inference=False` [S8] | Supported for the architecture. You must write the reward. Not run on WeVisOne. UNVERIFIED |
| Molmo2 / MolmoPoint | Training code is SFT only [S4]. No GRPO in TRL, ms-swift or verl for the Molmo2 architecture was found | Not supported. You would write your own loop |
| Qwen3.5, Gemma 4 | Unsloth GRPO works with `fast_inference=False` [S8] | Possible, slower |

ms-swift GRPO pattern (SOURCED from the docs [S6], reward body is mine):

```
swift rlhf --rlhf_type grpo --model out/doors-sft-merged --tuner_type lora \
  --use_vllm true --vllm_mode colocate --vllm_gpu_memory_utilization 0.5 \
  --external_plugins plugin.py --reward_funcs point_match format \
  --num_generations 8 --max_completion_length 1024 \
  --learning_rate 1e-6 --sleep_level 1 --temperature 1.0
```

```
# plugin.py
from swift.rewards import ORM, orms
class PointMatchReward(ORM):
    def __call__(self, completions, solution=None, **kwargs):
        # parse points, match one-to-one (Hungarian) to the gold points with a
        # distance threshold, return F1 or 2*matched/(N_gt+N_pred) per completion
        ...
orms['point_match'] = PointMatchReward
```

- Use one-to-one matching, so extra points cost reward. A "count is right" 0/1 reward does worse than SFT in prior work. [S10, prior report] SOURCED.
- Start RL from the SFT adapter. Group samples that all agree teach nothing, so filter easy tiles.
- ESTIMATE: RL with 8 samples of up to 1,000 tokens on a 4B model takes 4 to 8 hours for a few hundred steps. It does not fit "a few hours" with the SFT run. Keep it as a stretch goal.

### Fallback recipe (Molmo2-4B)

- Use the `allenai/molmo2` repo: `scripts/prepare_pretrained_model.py`, then `launch_scripts/sft.py` from the released SFT checkpoint [S4]. This is full fine-tuning in the vendor format, not LoRA. Memory on one A100: UNVERIFIED, ESTIMATE 60 to 80 GB for 4B.
- Or fine-tune through HF transformers with LoRA. Not tested.
- Output format: points with the object index. Count = last index.

## Risks and how to test them in 1 hour

| Risk | Test (about minutes) | Pass rule |
|---|---|---|
| WeVisOne loads and points on a drawing zero-shot | Load with the vendor package. Run `point to: door` on 5 labelled tiles (10) | At least some points land on doors. If the output is empty or garbage, swap to Qwen3-VL-4B-Instruct (same code) or Molmo2-4B |
| ms-swift, TRL or vLLM cannot load WeVisOne (custom coordinate tokens, `<OBJ>` token, remote code) | `swift sft` with 20 samples and 5 steps (10) | Loss is finite and the tokens print as `<512>` in a decoded sample. Else use the vendor Qwen3-VL config and add the tokens by hand, or use Qwen3-VL-4B-Instruct |
| Tile scale: doors are tiny on a full sheet | Run the zero-shot on a full sheet and on 1,400 px tiles (10) | Tiles find more doors. Choose the tile size on this test |
| Dense loops or very long output | Set `max_new_tokens` and count tokens on a crowded tile (5) | Output ends cleanly. Else lower the tile size |
| Fine-tuning loses OCR and general reading | Ask 10 label questions before and after SFT on 5 tiles (10) | No large drop. Else mix 20 percent general samples into the data |
| Duplicate points across tile overlaps | Merge with a distance threshold and compare with hand counts on 3 sheets (10) | Count error within one door |
| Moderate cost and speed | Time one tile on the A100 and read VRAM (5) | Under 10 s per tile, under 60 GB in training |
| Reward plugin bug (if RL) | Unit test the matcher on 3 hand cases before launch (10) | Perfect points give 1.0, none give 0.0, extra points lower the score |

Open items I could not close (all UNVERIFIED): WeVisOne loading in ms-swift, TRL, Unsloth and vLLM; TRL GRPO with Qwen3-VL in CI; MolmoPoint in vLLM; Moondream open fine-tuning; licence details of GroundingPI and LFM2.5-VL; Florence-2 resolution; general VQA retention of WeVisOne. All hours, VRAM and cost numbers above are ESTIMATES.

## Sources

Access date for all: 2026-11-14. Publication dates are as shown on the page where I found one.

| Id | Title | URL | Date | Supports |
|---|---|---|---|---|
| S1 | WeVisOne-VL model card and README (benchmarks, Apache-2.0, coordinate tokens, rejection, tokens limit) | https://huggingface.co/tencent/WeVisOne-VL-4B and https://github.com/Tencent/WeVisOne-VL | 2026-10 | WeVisOne scores, format, licence, Dense200 baselines, 1,960 token budget |
| S2 | WeVisOne-VL repo: tokenizer, chat template, parser, prompt builder, paper arXiv 2610.31329 | https://github.com/Tencent/WeVisOne-VL ; https://arxiv.org/abs/2610.31329 ; https://huggingface.co/tencent/WeVisOne-VL-4B/raw/main/chat_template.jinja | 2026-10 | Training sample format, `<0>`..`<1000>` tokens, 500 points, no training script in repo |
| S3 | MolmoPoint and Molmo2 model cards, MolmoPoint paper and blog | https://huggingface.co/allenai/MolmoPoint-8B ; https://allenai.org/papers/molmopoint ; https://github.com/allenai/molmo2/blob/main/MOLMO_POINT_README.md | 2026 | MolmoPoint tokens, PointBench 70.7, Apache-2.0 |
| S4 | Molmo2 paper (arXiv 2601.10611), model cards, training README | https://arxiv.org/abs/2601.10611 ; https://huggingface.co/allenai/Molmo2-4B ; https://github.com/allenai/molmo2 | 2026-01 | Molmo2 format, tables of counting and pointing, SFT training stages, licence |
| S5 | ms-swift command-line parameters (4.6.1) | https://raw.githubusercontent.com/modelscope/ms-swift/main/docs/source_en/Instruction/Command-line-parameters.md | 2026-11 | `--tuner_type`, `IMAGE_MAX_TOKEN_NUM`, `--freeze_vit`, `--max_pixels` |
| S6 | ms-swift GRPO docs and reward plugin example | https://swift.readthedocs.io/en/latest/Instruction/GRPO/GetStarted/GRPO.html ; https://github.com/modelscope/ms-swift/blob/main/examples/train/grpo/plugin/plugin.py ; https://raw.githubusercontent.com/modelscope/ms-swift/main/docs/source_en/Instruction/GRPO/DeveloperGuide/reward_function.md | 2026-11 | GRPO flags, ORM plugin pattern, vLLM colocate |
| S7 | TRL GRPO trainer docs and test file | https://huggingface.co/docs/trl/en/grpo_trainer ; https://raw.githubusercontent.com/huggingface/trl/main/tests/test_grpo_trainer.py | 2026-11 | GRPOTrainer 1.18.0, VLM tests (Qwen3-VL not covered) |
| S8 | Unsloth docs: vision RL, Qwen3.5 and Gemma 4 | https://unsloth.ai/docs/get-started/reinforcement-learning-rl-guide/vision-reinforcement-learning-vlm-rl ; https://unsloth.ai/docs/models/qwen3.5/fine-tune ; https://unsloth.ai/docs/models/gemma-4/train | 2026-11 | vLLM cannot LoRA vision layers; `fast_inference=False` |
| S9 | verl / EasyR1 README | https://raw.githubusercontent.com/volcengine/verl/main/README.md | 2026-11 | VLM GRPO support (verl 0.9.1) |
| S10 | Prior team reports: DECISION.md, STATE-OF-THE-ART.md, small-models-rl.md, vlm-on-drawings.md; AECV-Bench arXiv 2601.04819; MechVL | https://arxiv.org/abs/2601.04819 ; https://github.com/xiaofengShi/MechVQA | 2026-01 and repo files | Door counts on drawings, RL with point reward vs 0/1 reward, MechVL SFT to RL |
| S11 | Qwen3-VL README and model cards | https://raw.githubusercontent.com/QwenLM/Qwen3-VL/main/README.md ; https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct ; https://github.com/QwenLM/Qwen3-VL/blob/main/cookbooks/2d_grounding.ipynb | 2025-2026 | JSON grounding, 0-1000 coordinates, patch and merge sizes |
| S12 | 2U1/Qwen-VL-Series-Finetune README | https://github.com/2U1/Qwen-VL-Series-Finetune | 2026 | Community SFT and GRPO scripts for Qwen3-VL |
| S13 | vLLM supported models and Qwen3.5 recipe | https://raw.githubusercontent.com/vllm-project/vllm/main/docs/models/supported_models.md ; https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html | 2026-11 | Serving support (vLLM 0.33.0) |
| S14 | Qwen3.5 model card and blog | https://huggingface.co/Qwen/Qwen3.5-4B ; https://qwen.ai/blog?id=qwen3.5 | 2026 | Qwen3.5 sizes, Apache-2.0, CountBench 96.3 |
| S15 | Gemma 4 model card and licence | https://huggingface.co/google/gemma-4-E4B-it ; https://ai.google.dev/gemma/docs/gemma_4_license ; https://ai.google.dev/gemma/docs/capabilities/vision/image | 2026 | Gemma 4 box format, licence |

## Verification

Checked on 2026-11-14 by an independent reader who opened the primary sources. Models are 5B or 9B on the Hub when the vision encoder is counted. The names (4B, 8B) give the LLM size.

| Claim | Verdict | Evidence |
|---|---|---|
| `tencent/WeVisOne-VL-4B` exists, Apache-2.0, built on Qwen3-VL | CONFIRMED (card lists 5B params with vision encoder; third-party parts keep own licences) | https://huggingface.co/tencent/WeVisOne-VL-4B |
| WeVisOne paper arXiv 2610.31329 exists, 22 Oct 2026 | CONFIRMED | https://arxiv.org/abs/2610.31329 |
| WeVisOne PixMo-Count 89.6, PointBench 71.9, Dense200 point 87.0 | CONFIRMED (README). Dense200 point 87.0 is not the best: LocateAnything-3B has 87.6 | https://github.com/Tencent/WeVisOne-VL ; https://arxiv.org/html/2610.31329v2 |
| Dense200 F1 13.8 (Qwen3-VL-8B), 18.0 (Qwen3.5-9B), 71.3 (WeVisOne) | CORRECTED: these are box-detection mean F1, not pointing. Pointing F1 is 42.2, 10.5, 87.0 | https://arxiv.org/html/2610.31329v2 (tables 2, 5) |
| Up to 500 points per answer | CONFIRMED as a training-time maximum, not an inference limit | https://arxiv.org/html/2610.31329v2 |
| Trained to 1,960 visual tokens | CONFIRMED | https://github.com/Tencent/WeVisOne-VL |
| WeRef-Bench rejection 96.4 | CONFIRMED | https://github.com/Tencent/WeVisOne-VL |
| No training script in vendor repo | CONFIRMED (fine-tuning code is on the TODO list) | https://github.com/Tencent/WeVisOne-VL |
| Qwen3-VL loops above 40-50 objects | UNVERIFIED (paper only shows a 50-point cap in stage 1 data) | https://arxiv.org/html/2610.31329v2 |
| `allenai/Molmo2-4B` exists, Apache-2.0, Qwen3 LLM + SigLIP2, points scaled by 1000 | CONFIRMED (card also says research and educational use, third-party data limited to non-commercial) | https://huggingface.co/allenai/Molmo2-4B |
| Molmo2 paper arXiv 2601.10611 | CONFIRMED (abstract names the 8B only; 4B not seen) | https://arxiv.org/abs/2601.10611 |
| `allenai/MolmoPoint-8B` exists, Apache-2.0, PointBench 70.7 | CONFIRMED (score from paper arXiv 2603.28069 via search; card has no score; Hub lists 9B) | https://huggingface.co/allenai/MolmoPoint-8B ; https://allenai.org/blog/molmopoint |
| `Qwen/Qwen3-VL-4B-Instruct` exists, Apache-2.0 | CONFIRMED | https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct |
| `Qwen/Qwen3.5-4B` exists, Apache-2.0, CountBench 96.3 | CONFIRMED | https://huggingface.co/Qwen/Qwen3.5-4B |
| `google/gemma-4-E4B-it` exists; licence "Gemma 4 licence" | CORRECTED: card says Apache-2.0 | https://huggingface.co/google/gemma-4-E4B-it |
| `gemma-4-12B-it` id | UNVERIFIED | not opened |
| Tool versions (ms-swift 4.6.1, TRL 1.18.0, vLLM 0.33.0, Unsloth 2026.11.4) and GRPO claims | UNVERIFIED | not opened |

Conclusion: the primary recommendation (WeVisOne-VL-4B, Molmo2-4B fallback) survives. The draft quoted the wrong F1 metric for the Qwen baselines, but the gap is still large on pointing.
