# Night run state (14 November 2026)

This file lets the lead continue after a wake-up. Update it at each step.

## Goal

Henrik's task: a trustable test harness first, then every experiment worth trying, tracked. Present results in the morning.

## Done

- Harness: `src/bp/` (contract, scorer, sealed sessions in a sandbox, suites, cluster bootstrap, ledger). Trust report: `experiments/TRUST.md` (all checks pass). Gate: `uv run ruff check src tests && uv run ty check && uv run pytest -q`.
- `suites/stoa.jsonl`: 64,110 items from 127,044 public rows (`uv run bp build`, `uv run bp fit-prior`).
- LLM client `src/bp/llm.py` (Hostinger AI Router, cache, spend log `experiments/llm_spend.jsonl`, cap 15 USD).

## State at 06:30 (14 November)

- The morning report is `docs/RESULTS.md`. Read it first.
- Agent v4 is the current solver (`agent`): hard val +0.743, public Swiss val +0.995, public IFC val +0.688, public CubiCasa val +0.688.
- Models in `artifacts/` (git-ignored): count head, RF-DETR Large and YOLO26-M detectors (default YOLO26-M), 85-min U-Net.
- The T3 server restarted at about 05:00 and cancelled the builder workflows. Nothing runs now. No VM runs. Verda balance 199.98 USD.
- Router spend: 956 credits (about 8 to 10 USD; the unit is not certain).

## Next

1. Windows and doors per room on rasters (the U-Net has an opening class).
2. A better doubt rule for the detector: 10 to 11% wrong on raster counts.
3. Henrik decides: YOLO26-M (AGPL-3.0) or RF-DETR (Apache-2.0) as the default detector.
4. Open: sonnet planner comparison, a judge for ifc_bench free text, calibration items, notes files for count head, detector and raster tools.

## Old notes

## Running

- Workflow `wf_ba05faed-f02` (task wuzuh03k5): base-model research -> `docs/research/models/*.md`, `docs/BASE-MODELS.md`.
- Workflow `wf_bc8b4359-e9b` (task wo30v5shz): 5 builders (swiss, ifc, hardcases, vlm-direct, cubicasa-count). Each writes `experiments/notes/<slug>.md`. The cubicasa-count worker uses a Verda VM.

- Workflow `wf_cd486547-d19` (task wvvhl2tqw): cubicasa-detect builder (RF-DETR or YOLO on SVG labels, Verda VM).
- Agent loop is written: `src/bp/agent/` (state machine, provenance rule, calc). It waits for tools.
- Model choices from research: agent on `claude-haiku-5.5` through the router, escalate to `claude-sonnet-5.5`; detector RF-DETR Large at 1024.

## Next (lead)

1. Agent solver `src/bp/solvers/agent.py`: state machine loop, LLM through the router, tools from `src/bp/tools/`.
2. When builders finish: run the gate, register the solvers in `clients.SOLVERS`, run val, commit, push, CRM progress.
3. Run the agent on `suites/hard.jsonl` and on val samples. Benchmark the tools (`src/bp/toolbench/`).
4. Decide on a detector from CubiCasa SVG labels after `docs/BASE-MODELS.md` and the count-model error analysis.
5. Morning report: `docs/RESULTS.md` with the ledger, the trust report, the tool table and the recommendation.
6. Before the end: `cd ../starter && pnpm j gpu ls` (no VM left), stop processes, CRM `progress`, report the router spend.
