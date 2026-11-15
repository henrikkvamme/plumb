"""The worker process. It holds one solver at a time and answers JSON lines. Run: python -m bp.worker <spec>."""

from __future__ import annotations

import json
import os
import sys
from typing import TYPE_CHECKING, Any

from bp.clients import load_factory
from bp.contract import Calibration, Question

if TYPE_CHECKING:
    from collections.abc import Callable

    from bp.contract import Solver


def _handle(message: dict[str, Any], factory: Callable[[], Solver], held: list[Solver]) -> dict[str, Any]:
    op = message.get("op")
    if op == "open":
        held.clear()
        held.append(factory())
        return {"report": held[0].ingest(str(message["path"])).model_dump(mode="json")}
    if op == "close":
        held.clear()
        return {"closed": True}
    if not held:
        return {"error": f"{op} before open"}
    if op == "ask":
        record = held[0].ask(Question.model_validate(message["question"]))
        return {"record": record.model_dump(mode="json")}
    if op == "calibrate":
        held[0].calibrate(Calibration.model_validate(message["calibration"]))
        return {"calibrated": True}
    return {"error": f"unknown op {op!r}"}


def main() -> None:
    # The protocol keeps the real stdout. Everything that a solver prints goes to stderr.
    protocol = os.fdopen(os.dup(1), "w")
    os.dup2(2, 1)
    factory = load_factory(sys.argv[1])
    held: list[Solver] = []
    protocol.write(json.dumps({"ready": True}) + "\n")
    protocol.flush()
    for line in sys.stdin:
        try:
            reply = _handle(json.loads(line), factory, held)
        except Exception as exc:
            reply = {"error": f"{type(exc).__name__}: {exc}"[:500]}
        protocol.write(json.dumps(reply) + "\n")
        protocol.flush()


if __name__ == "__main__":
    main()
