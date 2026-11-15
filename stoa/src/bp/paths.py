"""Where things are. One place, so the sandbox profile and the code agree."""

from __future__ import annotations

from pathlib import Path

STOA = Path(__file__).resolve().parents[2]
REPO = STOA.parent
DATA = STOA / "data"
DATASET = DATA / "junction-dataset"
QUESTIONS = DATASET / "questions.jsonl"
ANALYSIS = STOA / "analysis"
SPLIT = ANALYSIS / "questions" / "split_v0.json"
SUITES = STOA / "suites"  # items with keys; never in git
ARTIFACTS = STOA / "artifacts"  # fitted tables and model weights that a solver may read
EXPERIMENTS = STOA / "experiments"
RUNS = EXPERIMENTS / "runs"
SESSIONS = EXPERIMENTS / "sessions"  # sealed copies of documents, removed after a run
LEDGER = EXPERIMENTS / "LEDGER.md"

# A solver process cannot read these. They hold keys, labels or the original file names.
FORBIDDEN: tuple[Path, ...] = (DATA, SUITES, ANALYSIS, RUNS, STOA / "docs", REPO / ".git")
