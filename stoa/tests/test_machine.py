from __future__ import annotations

import pytest

from bp.machine import IllegalTransitionError, Machine, MachineError, Run


def toy(table: dict[tuple[str, str], str], finals: frozenset[str] = frozenset({"end"})) -> Machine[str, str]:
    return Machine(name="toy", initial="start", finals=finals, table=table)


def test_valid_machine_runs_and_keeps_a_trace() -> None:
    machine = toy({("start", "go"): "mid", ("mid", "again"): "mid", ("mid", "stop"): "end"})
    machine.verify()
    run = Run(machine)
    run.fire("go")
    run.fire("again")
    run.fire("stop")
    assert run.done
    assert run.events() == ["go", "again", "stop"]
    with pytest.raises(IllegalTransitionError):
        run.fire("go")


def test_verify_rejects_broken_machines() -> None:
    with pytest.raises(MachineError, match="dead end"):
        toy({("start", "go"): "mid", ("start", "skip"): "end"}).verify()
    with pytest.raises(MachineError, match="unreachable"):
        toy({("start", "go"): "end", ("island", "go"): "end"}).verify()
    with pytest.raises(MachineError, match="final state"):
        toy({("start", "go"): "end", ("end", "back"): "start"}).verify()
    with pytest.raises(MachineError, match="cannot reach"):
        toy({("start", "go"): "end", ("start", "trap"): "loop", ("loop", "spin"): "loop"}).verify()
