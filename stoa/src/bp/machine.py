"""A small typed state machine.

We use machines where an order of steps must hold: a harness session (ingest, then ask) and the agent loop
(plan, call a tool, check, answer or abstain). A machine is data: `verify()` proves at import time that every
state is reachable, that every state that is not final has a way out, and that a final state has none. A run
keeps its trace, so a test can assert the exact path.
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping
from dataclasses import dataclass, field


class MachineError(Exception):
    pass


class IllegalTransitionError(MachineError):
    pass


@dataclass(frozen=True)
class Machine[S: Hashable, E: Hashable]:
    name: str
    initial: S
    finals: frozenset[S]
    table: Mapping[tuple[S, E], S]

    def states(self) -> frozenset[S]:
        found = {self.initial, *self.finals}
        for (src, _), dst in self.table.items():
            found.add(src)
            found.add(dst)
        return frozenset(found)

    def step(self, state: S, event: E) -> S:
        try:
            return self.table[(state, event)]
        except KeyError:
            msg = f"{self.name}: event {event!r} is not allowed in state {state!r}"
            raise IllegalTransitionError(msg) from None

    def allowed(self, state: S) -> frozenset[E]:
        return frozenset(event for (src, event) in self.table if src == state)

    def verify(self) -> None:
        """Raise when the machine has an unreachable state, a dead end, or a final state with a way out."""
        reachable: set[S] = {self.initial}
        frontier = [self.initial]
        while frontier:
            current = frontier.pop()
            for (src, _), dst in self.table.items():
                if src == current and dst not in reachable:
                    reachable.add(dst)
                    frontier.append(dst)
        unreachable = self.states() - reachable
        if unreachable:
            msg = f"{self.name}: unreachable states {sorted(map(repr, unreachable))}"
            raise MachineError(msg)
        for state in self.states():
            has_exit = bool(self.allowed(state))
            if state in self.finals and has_exit:
                msg = f"{self.name}: final state {state!r} has a transition out"
                raise MachineError(msg)
            if state not in self.finals and not has_exit:
                msg = f"{self.name}: state {state!r} is a dead end and is not final"
                raise MachineError(msg)
        if not self.finals:
            msg = f"{self.name}: no final state"
            raise MachineError(msg)
        # Every state must be able to reach a final state.
        can_finish: set[S] = set(self.finals)
        changed = True
        while changed:
            changed = False
            for (src, _), dst in self.table.items():
                if dst in can_finish and src not in can_finish:
                    can_finish.add(src)
                    changed = True
        stuck = self.states() - can_finish
        if stuck:
            msg = f"{self.name}: states that cannot reach a final state {sorted(map(repr, stuck))}"
            raise MachineError(msg)


@dataclass
class Run[S: Hashable, E: Hashable]:
    """One execution of a machine. It records each event and refuses an illegal one."""

    machine: Machine[S, E]
    state: S = field(init=False)
    trace: list[tuple[S, E, S]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.state = self.machine.initial

    def fire(self, event: E) -> S:
        nxt = self.machine.step(self.state, event)
        self.trace.append((self.state, event, nxt))
        self.state = nxt
        return nxt

    @property
    def done(self) -> bool:
        return self.state in self.machine.finals

    def events(self) -> list[E]:
        return [event for _, event, _ in self.trace]
