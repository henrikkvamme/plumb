"""Record what the agent did: each tool call with its arguments, the facts it returned and its evidence.

The agent loop in `bp.agent.core` keeps only the tool name and the arguments of a step. The desk needs the
returned facts too, so this module wraps the tools and the chat function. It does not change the loop:
the message list of the loop is the source of truth, and the wrapped tools add the evidence and the timing.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from bp.agent.core import Chat, ToolOutput, ToolSpec
    from bp.llm import ChatResult

TERMINAL = frozenset({"submit_answer", "abstain"})


@dataclass
class ToolRun:
    name: str
    arguments: dict[str, Any]
    output: ToolOutput | None
    error: str
    ms: float


@dataclass
class Recorder:
    """Collects the tool runs and the message list of one question."""

    on_change: Callable[[], None] = lambda: None
    runs: list[ToolRun] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    last_reply: ChatResult | None = None
    activity: str = "reading the question"
    turns: int = 0

    def tool(self, spec: ToolSpec) -> ToolSpec:
        def run(arguments: dict[str, Any]) -> ToolOutput:
            self.activity = f"running {spec.name}"
            self.on_change()
            started = time.perf_counter()
            try:
                output = spec.run(arguments)
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000.0
                self.runs.append(ToolRun(spec.name, arguments, None, f"{type(exc).__name__}: {exc}", elapsed))
                self.on_change()
                raise
            elapsed = (time.perf_counter() - started) * 1000.0
            self.runs.append(ToolRun(spec.name, arguments, output, "", elapsed))
            self.on_change()
            return output

        return replace(spec, run=run)

    def chat(self, chat: Chat) -> Chat:
        def call(messages: list[dict[str, Any]], schemas: list[dict[str, Any]]) -> ChatResult:
            self.messages = messages
            self.activity = "choosing the next tool" if self.turns else "planning"
            self.on_change()
            reply = chat(messages, schemas)
            self.turns += 1
            self.last_reply = reply
            self.on_change()
            return reply

        return call


def _json(text: str) -> Any:  # noqa: ANN401 - JSON
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text


def _calls(message: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    out = []
    for call in message.get("tool_calls") or []:
        function = call.get("function", {})
        arguments = _json(function.get("arguments") or "{}")
        out.append((str(call.get("id", "")), str(function.get("name", "")), arguments if isinstance(arguments, dict) else {}))
    return out


def _thought(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return " ".join(str(part.get("text", "")) for part in content if isinstance(part, dict)).strip()
    return ""


def raw_steps(recorder: Recorder, tool_names: set[str]) -> list[dict[str, Any]]:
    """The steps so far, in the order of the loop. A step is one tool call, one calc, one refused or final answer."""
    messages = list(recorder.messages)
    reply = recorder.last_reply
    if reply is not None and reply.message and (not messages or messages[-1] is not reply.message):
        if not any(m is reply.message for m in messages):
            messages.append(reply.message)
    results = {m.get("tool_call_id"): m.get("content") for m in messages if m.get("role") == "tool"}
    runs = list(recorder.runs)
    cursor = 0
    steps: list[dict[str, Any]] = []
    for message in messages:
        if message.get("role") != "assistant":
            continue
        thought = _thought(message)
        for call_id, name, arguments in _calls(message):
            step: dict[str, Any] = {
                "call_id": call_id,
                "tool": name,
                "arguments": arguments,
                "thought": thought,
                "result": _json(results[call_id]) if call_id in results else None,
                "done": call_id in results,
                "run": None,
            }
            thought = ""
            if name in tool_names and cursor < len(runs) and runs[cursor].name == name:
                step["run"] = runs[cursor]
                step["done"] = True
                cursor += 1
            steps.append(step)
    return steps
