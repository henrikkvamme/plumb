"""The command line: build suites, run a solver, compare two runs, write the ledger, prove the harness."""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from typing import Annotated, Any

import typer

from bp import selftest as selftest_module
from bp.clients import SubprocessClient, sandbox_available
from bp.contract import CountKey, Item, MeasureKey
from bp.paths import ARTIFACTS, DATASET, RUNS, SESSIONS
from bp.runner import run_items
from bp.session import Client, ItemResult
from bp.stats import Summary, paired, summarise
from bp.suites import build_stoa_items, read_items, select, suite_hash, write_items
from bp.track import Meta, git_state, host, load_results, new_run_id, save_run, write_ledger

app = typer.Typer(add_completion=False, no_args_is_help=True)


def run_solver(
    solver: str,
    items: list[Item],
    *,
    suite: str,
    selector: dict[str, Any],
    note: str = "",
    jobs: int = 4,
    sandbox: bool = True,
    save: bool = True,
) -> tuple[Summary, list[ItemResult], str]:
    """Run `solver` in worker processes on `items`, save the run, and return the summary."""
    run_id, started = new_run_id(solver, suite)
    sealed = sandbox and sandbox_available()
    if sandbox and not sealed:
        typer.echo("warning: no sandbox on this machine, the run is not sealed", err=True)
    directory = RUNS / run_id

    def make(index: int) -> Client:
        return SubprocessClient(solver, sandbox=sealed, log=directory / f"worker-{index}.log")

    def close(client: Client) -> None:
        if isinstance(client, SubprocessClient):
            client.shutdown()

    begun = time.monotonic()
    results = run_items(items, make, root=DATASET, workdir=SESSIONS / run_id, jobs=jobs, close_client=close)
    summary = summarise(results)
    sha, dirty = git_state()
    meta = Meta(
        run_id=run_id, solver=solver, suite=suite, suite_hash=suite_hash(items), selector=selector, note=note,
        sealed=sealed, jobs=jobs, git_sha=sha, git_dirty=dirty, started=started,
        seconds=time.monotonic() - begun, host=host(),
    )  # fmt: skip
    if save:
        save_run(meta, summary, results)
        write_ledger()
    return summary, results, run_id


def show(summary: Summary) -> None:
    s = summary
    typer.echo(
        f"items {s.items}  rows {s.rows}  groups {s.groups}\n"
        f"score {s.score.value:+.4f} [{s.score.low:+.4f}, {s.score.high:+.4f}]\n"
        f"accuracy {100 * s.accuracy.value:.2f}% [{100 * s.accuracy.low:.2f}, {100 * s.accuracy.high:.2f}]"
        f"  row accuracy {100 * s.row_accuracy:.2f}% ({s.rows_right} rows)\n"
        f"answered {100 * s.answered:.2f}%  wrong {100 * s.wrong:.2f}%  errors {100 * s.errors:.2f}%"
        f"  cost ${s.cost_usd:.2f}  p50 {s.latency_p50_ms:.0f} ms"
    )
    for axis in ("source", "cell"):
        for name, part in s.by[axis].items():
            typer.echo(
                f"  {axis}={name}: n={part.items} score={part.score:+.3f} acc={100 * part.accuracy:.2f}% "
                f"answered={100 * part.answered:.1f}% wrong={100 * part.wrong:.1f}%"
            )


@app.command()
def build() -> None:
    """Build suites/stoa.jsonl from the public questions."""
    items = build_stoa_items()
    path = write_items("stoa", items)
    rows = sum(1 + len(it.twins) for it in items)
    typer.echo(f"{len(items)} items from {rows} rows -> {path}  hash {suite_hash(items)}")
    typer.echo(json.dumps(Counter(f"{it.source}/{it.partition}" for it in items).most_common()))


@app.command()
def fit_prior() -> None:
    """Fit the prior tables: the most frequent answer for each exact question text."""
    items = read_items("stoa")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for name, pool in (("prior-all", items), ("prior-dev", [it for it in items if it.partition == "dev"])):
        votes: dict[str, Counter[tuple[float | int, str | None]]] = defaultdict(Counter)
        for it in pool:
            if isinstance(it.key, CountKey):
                answer: tuple[float | int, str | None] = (it.key.value, None)
            elif isinstance(it.key, MeasureKey):
                answer = (it.key.value, it.key.unit)
            else:
                continue
            for text in (it.question, *it.twins):
                votes[text][answer] += 1
        table = {text: list(counter.most_common(1)[0][0]) for text, counter in votes.items()}
        (ARTIFACTS / f"{name}.json").write_text(json.dumps(table, ensure_ascii=False))
        typer.echo(f"{name}: {len(table)} question texts")


@app.command()
def run(
    solver: str,
    suite: Annotated[str, typer.Option()] = "stoa",
    source: Annotated[list[str] | None, typer.Option()] = None,
    partition: Annotated[list[str] | None, typer.Option()] = None,
    cell: Annotated[list[str] | None, typer.Option()] = None,
    docs: Annotated[int, typer.Option(help="Keep this number of whole documents. 0 keeps all.")] = 0,
    seed: Annotated[str, typer.Option()] = "s0",
    jobs: Annotated[int, typer.Option()] = 4,
    note: Annotated[str, typer.Option()] = "",
    sandbox: Annotated[bool, typer.Option()] = True,
) -> None:
    """Run a solver on a suite in sealed sessions and record the run."""
    items = select(
        read_items(suite), sources=tuple(source or ()), partitions=tuple(partition or ()),
        cells=tuple(cell or ()), docs=docs, seed=seed,
    )  # fmt: skip
    if not items:
        raise typer.BadParameter("the selection is empty")
    selector = {
        "source": source,
        "partition": partition,
        "cell": cell,
        "docs": docs,
        "seed": seed if docs else "",
    }
    summary, _, run_id = run_solver(
        solver, items, suite=suite, selector=selector, note=note, jobs=jobs, sandbox=sandbox
    )
    typer.echo(f"run {run_id}")
    show(summary)


@app.command()
def diff(a: str, b: str) -> None:
    """Compare two runs on their common items: b minus a, with a paired cluster bootstrap."""
    result = paired(load_results(a), load_results(b))
    d = result.score_difference
    typer.echo(
        f"items {result.items}\nscore difference {d.value:+.4f} [{d.low:+.4f}, {d.high:+.4f}]"
        f"  {'significant' if result.significant else 'not significant'}\n"
        f"accuracy difference {100 * result.accuracy_difference.value:+.2f} points\n"
        f"right only in a: {result.a_only_right}   right only in b: {result.b_only_right}"
    )


@app.command()
def ledger() -> None:
    """Write experiments/LEDGER.md again."""
    typer.echo(f"{write_ledger()} runs")


@app.command()
def selftest(
    full: Annotated[bool, typer.Option(help="Also run the slow checks on every public item.")] = True,
) -> None:
    """Prove that the harness can be trusted. It writes experiments/TRUST.md."""
    ok = selftest_module.run(full=full)
    raise typer.Exit(code=0 if ok else 1)
