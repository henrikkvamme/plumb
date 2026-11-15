"""Two ways to reach a solver: in this process (for tests) and in a sandboxed worker process (for runs)."""

from __future__ import annotations

import importlib
import json
import os
import select
import shutil
import subprocess
import sys
import time
from typing import IO, TYPE_CHECKING, Any, cast

from pydantic import ValidationError

from bp.contract import AnswerRecord, Calibration, IngestReport, Question, Solver
from bp.paths import FORBIDDEN, STOA
from bp.session import SolverFailureError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

SOLVERS: dict[str, str] = {
    "null": "bp.solvers.baselines:NullSolver",
    "prior": "bp.solvers.baselines:PriorSolver",
    "prior-dev": "bp.solvers.baselines:PriorDevSolver",
    "swiss": "bp.solvers.swiss:SwissSolver",
    "ifc": "bp.solvers.ifc:IfcSolver",
    "agent": "bp.solvers.agent:AgentSolver",
    "vlm": "bp.solvers.vlm_direct:VlmDirectSolver",
    "canary-files": "bp.solvers.baselines:FileCanarySolver",
    "canary-name": "bp.solvers.baselines:NameCanarySolver",
}


def load_factory(spec: str) -> Callable[[], Solver]:
    """`spec` is a registered name or `module:attribute`."""
    target = SOLVERS.get(spec, spec)
    module_name, _, attribute = target.partition(":")
    if not attribute:
        msg = f"unknown solver {spec!r}"
        raise ValueError(msg)
    return cast("Callable[[], Solver]", getattr(importlib.import_module(module_name), attribute))


class InProcessClient:
    """No isolation. For unit tests and for the oracle, which needs the keys."""

    def __init__(self, factory: Callable[[], Solver]) -> None:
        self._factory = factory
        self._solver: Solver | None = None

    def open(self, path: str) -> IngestReport:
        self._solver = self._factory()
        try:
            return self._solver.ingest(path)
        except Exception as exc:
            return IngestReport(ok=False, detail=f"{type(exc).__name__}: {exc}")

    def ask(self, question: Question) -> AnswerRecord:
        if self._solver is None:
            msg = "ask before open"
            raise SolverFailureError(msg)
        try:
            return self._solver.ask(question)
        except Exception as exc:
            raise SolverFailureError(f"{type(exc).__name__}: {exc}") from exc

    def calibrate(self, calibration: Calibration) -> None:
        if self._solver is None:
            msg = "calibrate before open"
            raise SolverFailureError(msg)
        try:
            self._solver.calibrate(calibration)
        except Exception as exc:
            raise SolverFailureError(f"{type(exc).__name__}: {exc}") from exc

    def close(self) -> None:
        self._solver = None


def sandbox_profile() -> str:
    """A macOS sandbox profile that denies every read of the paths that hold keys or labels."""
    lines = ["(version 1)", "(allow default)"]
    lines += [f'(deny file-read* (subpath "{path}"))' for path in FORBIDDEN]
    return "\n".join(lines) + "\n"


def sandbox_available() -> bool:
    return sys.platform == "darwin" and shutil.which("sandbox-exec") is not None


class SubprocessClient:
    """A worker process that holds the solver. JSON lines on stdin and stdout, a time limit on each call."""

    def __init__(
        self,
        spec: str,
        *,
        sandbox: bool,
        log: Path,
        ingest_timeout: float = 600.0,
        ask_timeout: float = 300.0,
        start_timeout: float = 120.0,
    ) -> None:
        self._spec = spec
        self._sandbox = sandbox
        self._log = log
        self._ingest_timeout = ingest_timeout
        self._ask_timeout = ask_timeout
        self._start_timeout = start_timeout
        self._process: subprocess.Popen[bytes] | None = None
        self._buffer = b""

    def _start(self) -> subprocess.Popen[bytes]:
        command = [sys.executable, "-m", "bp.worker", self._spec]
        if self._sandbox:
            command = ["sandbox-exec", "-p", sandbox_profile(), *command]
        self._log.parent.mkdir(parents=True, exist_ok=True)
        with self._log.open("ab") as log:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, cwd=STOA)
        self._process = process
        self._buffer = b""
        reply = self._read(self._start_timeout)
        if reply.get("ready") is not True:
            self._kill()
            msg = f"worker did not start: {reply}"
            raise SolverFailureError(msg)
        return process

    def _kill(self) -> None:
        if self._process is not None:
            self._process.kill()
            self._process.wait()
            self._process = None

    def _read(self, timeout: float) -> dict[str, Any]:
        process = self._process
        if process is None or process.stdout is None:
            msg = "no worker"
            raise SolverFailureError(msg)
        fd = process.stdout.fileno()
        deadline = time.monotonic() + timeout
        while b"\n" not in self._buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
                self._kill()
                msg = f"time limit of {timeout:.0f} s"
                raise SolverFailureError(msg)
            chunk = os.read(fd, 1 << 16)
            if not chunk:
                self._kill()
                msg = "the worker process ended"
                raise SolverFailureError(msg)
            self._buffer += chunk
        line, _, self._buffer = self._buffer.partition(b"\n")
        try:
            reply = json.loads(line)
        except json.JSONDecodeError as exc:
            self._kill()
            msg = f"the worker sent a line that is not JSON: {line[:200]!r}"
            raise SolverFailureError(msg) from exc
        if not isinstance(reply, dict):
            msg = "the worker sent a value that is not an object"
            raise SolverFailureError(msg)
        return cast("dict[str, Any]", reply)

    def _call(self, message: dict[str, Any], timeout: float) -> dict[str, Any]:
        process = self._process or self._start()
        stdin = cast("IO[bytes]", process.stdin)
        try:
            stdin.write(json.dumps(message).encode() + b"\n")
            stdin.flush()
        except OSError as exc:
            self._kill()
            msg = "the worker process ended"
            raise SolverFailureError(msg) from exc
        reply = self._read(timeout)
        if "error" in reply:
            raise SolverFailureError(str(reply["error"]))
        return reply

    def open(self, path: str) -> IngestReport:
        try:
            reply = self._call({"op": "open", "path": path}, self._ingest_timeout)
            return IngestReport.model_validate(reply["report"])
        except (SolverFailureError, ValidationError, KeyError) as exc:
            return IngestReport(ok=False, detail=str(exc)[:500])

    def ask(self, question: Question) -> AnswerRecord:
        reply = self._call({"op": "ask", "question": question.model_dump()}, self._ask_timeout)
        try:
            return AnswerRecord.model_validate(reply["record"])
        except (ValidationError, KeyError) as exc:
            msg = f"not an answer record: {exc}"
            raise SolverFailureError(msg) from exc

    def calibrate(self, calibration: Calibration) -> None:
        self._call({"op": "calibrate", "calibration": calibration.model_dump()}, self._ask_timeout)

    def close(self) -> None:
        if self._process is not None:
            self._call({"op": "close"}, self._ask_timeout)

    def shutdown(self) -> None:
        self._kill()
