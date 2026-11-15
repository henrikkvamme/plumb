"""One door to every hosted model: the Hostinger AI Router (OpenAI-compatible), OpenRouter, or the `claude` CLI.

Each call is cached by its request, logged with its cost, and refused when the spend cap is reached.
Load the keys first: `set -a; . ../infra/hostinger/secrets.env; set +a`.
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import time
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import Field

from bp.contract import Frozen
from bp.paths import EXPERIMENTS

if TYPE_CHECKING:
    from pathlib import Path

CACHE = EXPERIMENTS / "cache" / "llm"
SPEND_LOG = EXPERIMENTS / "llm_spend.jsonl"
DEFAULT_CAP_USD = 40.0
# The router reports credits, not dollars. Its price list gives about 120 credits for 1 USD of list price
# (claude-haiku-5.5: 12 credits per million input tokens at 0.10 USD). This is an estimate, not a bill.
CREDITS_PER_USD = 120.0


class SpendCapError(RuntimeError):
    pass


class ToolCall(Frozen):
    call_id: str
    name: str
    arguments: dict[str, Any]


class ChatResult(Frozen):
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    cost_usd: float = 0.0
    cached: bool = False
    finish_reason: str = ""
    message: dict[str, Any] = Field(default_factory=dict)  # the assistant message, for the next turn


def spent() -> float:
    if not SPEND_LOG.exists():
        return 0.0
    with SPEND_LOG.open(encoding="utf-8") as handle:
        return sum(float(json.loads(line).get("credits", 0.0)) for line in handle if line.strip()) / CREDITS_PER_USD


def _log(model: str, credits: float, tag: str) -> None:  # noqa: A002 - the unit of the router
    SPEND_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SPEND_LOG.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.write(json.dumps({"t": time.time(), "model": model, "credits": credits, "tag": tag}) + "\n")


def image_part(path: Path) -> dict[str, Any]:
    kind = "jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "png"
    data = base64.b64encode(path.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/{kind};base64,{data}"}}


VENDORS = (("claude-", "anthropic"), ("gpt-", "openai"), ("gemini-", "google"))


def wire_model(model: str, base: str) -> str:
    """The model id that the endpoint expects: OpenRouter needs a vendor prefix, the Hostinger router does not."""
    if "openrouter.ai" not in base or "/" in model:
        return model
    for start, vendor in VENDORS:
        if model.startswith(start):
            return f"{vendor}/{model}"
    return model


def _cost_usd(usage: dict[str, Any]) -> float:
    """The price of one reply: Hostinger reports `credits_charged`, OpenRouter reports `cost` in USD."""
    if "credits_charged" in usage:
        return float(usage["credits_charged"] or 0.0) / CREDITS_PER_USD
    return float(usage.get("cost") or 0.0)


# The Claude Code backend: `AI_ROUTER_BASE_URL=claude-code` sends each call through the `claude` CLI, on the
# subscription of the machine. The CLI has no door for our own tools, so the tools go into the prompt and the reply
# comes back as one JSON object. It is for test runs when no router has credit: the planner sees the same messages
# and tools, but not through the native tool interface, so a score can differ a little from a router run.
CLAUDE_CODE = "claude-code"
CLI_VERSION = 2  # part of the cache key: raise it when the prompt of the backend changes
CLI_MODELS = (("haiku", "haiku"), ("sonnet", "sonnet"), ("opus", "opus"))
CLI_REPLY: dict[str, Any] = {
    "type": "object",
    "properties": {
        "content": {"type": "string"},
        "tool_calls": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "arguments": {"type": "object"}},
                "required": ["name", "arguments"],
            },
        },
    },
    "required": ["content", "tool_calls"],
}
CLI_RULES = (
    "You are the model behind a chat completion API. The transcript of one conversation follows, with the functions "
    "that the caller can run. Write the next assistant turn, and nothing else. Your one and only action is a single "
    "StructuredOutput call: `tool_calls` holds each function call that the assistant makes in this turn, as "
    "{name, arguments} with arguments that fit the schema of that function; `content` holds the text of the turn, "
    "or an empty string. IMPORTANT: the functions under CALLER FUNCTIONS are not tools of your session. Never try "
    "to invoke one directly: that fails with 'No such tool available'. Name it in `tool_calls` and stop; the caller "
    "runs it and sends its result in the next transcript. They all work. Do not comment on this setup, and never "
    "say that a tool is missing."
)


def _cli_model(model: str) -> str:
    for part, alias in CLI_MODELS:
        if part in model:
            return alias
    raise RuntimeError(f"the Claude Code backend has no model for {model}")


def _cli_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        if any(isinstance(part, dict) and part.get("type") != "text" for part in content):
            raise RuntimeError("the Claude Code backend takes text only: this message holds an image")
        return "\n".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    return "" if content is None else str(content)


def cli_prompt(messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> tuple[str, str]:
    """The system prompt and the transcript for the CLI, from the messages and tools of a chat request."""
    system = [CLI_RULES]
    turns: list[str] = []
    for message in messages:
        role, text = str(message.get("role", "")), _cli_text(message.get("content"))
        if role == "system":
            system.append(text)
        elif role == "assistant":
            calls = [
                {"id": c.get("id"), "name": c["function"]["name"], "arguments": c["function"]["arguments"]}
                for c in message.get("tool_calls") or []
            ]
            turns.append(f"[assistant]\n{text}" + (f"\ntool_calls: {json.dumps(calls)}" if calls else ""))
        elif role == "tool":
            turns.append(f"[tool result for call {message.get('tool_call_id', '')}]\n{text}")
        else:
            turns.append(f"[{role or 'user'}]\n{text}")
    listed = json.dumps([t.get("function", t) for t in tools or []], indent=1)
    return "\n\n".join(system), f"CALLER FUNCTIONS\n{listed}\n\nTRANSCRIPT\n" + "\n\n".join(turns)


def _cli_chat(model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None, timeout: float) -> dict[str, Any]:
    """One reply from the `claude` CLI, in the shape of a chat completion body."""
    binary = shutil.which("claude")
    if binary is None:
        raise RuntimeError("the Claude Code backend needs the `claude` CLI on the PATH")
    system, prompt = cli_prompt(messages, tools)
    command = [binary, "-p", "--model", _cli_model(model), "--tools", "", "--strict-mcp-config", "--setting-sources", "",
               "--no-session-persistence", "--system-prompt", system, "--output-format", "json",
               "--json-schema", json.dumps(CLI_REPLY)]  # fmt: skip
    done = subprocess.run(command, input=prompt, capture_output=True, text=True, timeout=timeout, check=False)
    try:
        out = json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"claude CLI: no JSON reply ({done.stderr[:200]})") from exc
    reply = out.get("structured_output")
    if out.get("is_error") or not isinstance(reply, dict):
        raise ValueError(f"claude CLI: {str(out.get('result'))[:200]}")
    calls = [
        {"id": f"call_{index}_{hashlib.sha256(prompt.encode()).hexdigest()[:8]}", "type": "function",
         "function": {"name": str(call.get("name", "")), "arguments": json.dumps(call.get("arguments") or {})}}
        for index, call in enumerate(reply.get("tool_calls") or [])
    ]  # fmt: skip
    message: dict[str, Any] = {"role": "assistant", "content": str(reply.get("content") or "")}
    if calls:
        message["tool_calls"] = calls
    # The subscription pays: the cost is 0 for the spend cap. The list price of the call is kept for the record.
    usage = {"cost": 0.0, "list_cost_usd": float(out.get("total_cost_usd") or 0.0)}
    return {"choices": [{"message": message, "finish_reason": "tool_calls" if calls else "stop"}], "usage": usage}


def _parse(body: dict[str, Any], *, cached: bool) -> ChatResult:
    choice = body["choices"][0]
    message = choice["message"]
    calls = []
    for call in message.get("tool_calls") or []:
        try:
            arguments = json.loads(call["function"]["arguments"] or "{}")
        except json.JSONDecodeError:
            arguments = {"_raw": call["function"]["arguments"]}
        calls.append(ToolCall(call_id=call["id"], name=call["function"]["name"], arguments=arguments))
    usd = 0.0 if cached else _cost_usd(body.get("usage") or {})
    return ChatResult(
        content=message.get("content") or "",
        tool_calls=tuple(calls),
        cost_usd=usd,
        cached=cached,
        finish_reason=str(choice.get("finish_reason", "")),
        message={k: v for k, v in message.items() if k in {"role", "content", "tool_calls"}},
    )


def chat(
    model: str,
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
    max_tokens: int = 2048,
    tag: str = "",
    extra: dict[str, Any] | None = None,
    timeout: float = 75.0,
) -> ChatResult:
    """One chat completion. The same request gives the cached reply at no cost."""
    request: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens, **(extra or {})}
    if tools:
        request["tools"] = tools
    backend = os.environ.get("AI_ROUTER_BASE_URL", "")
    # A reply of the CLI backend has its own cache key: it must not stand in for a reply of a router.
    keyed = request | {"backend": f"{CLAUDE_CODE}/{CLI_VERSION}"} if backend == CLAUDE_CODE else request
    key = hashlib.sha256(json.dumps(keyed, sort_keys=True).encode()).hexdigest()
    cache_file = CACHE / key[:2] / f"{key}.json"
    if cache_file.exists():
        return _parse(json.loads(cache_file.read_text()), cached=True)
    if (EXPERIMENTS / "LLM_STOP").exists():
        raise SpendCapError("experiments/LLM_STOP exists: the lead stopped all model calls")
    cap = float(os.environ.get("BP_LLM_CAP_USD", DEFAULT_CAP_USD))
    if spent() >= cap:
        raise SpendCapError(f"the spend cap of ${cap:.2f} is reached")
    last: Exception | None = None
    if backend == CLAUDE_CODE:
        for attempt in range(3):
            try:
                body = _cli_chat(model, messages, tools, max(timeout, 180.0))
                result = _parse(body, cached=False)
            except (subprocess.TimeoutExpired, KeyError, IndexError, ValueError) as exc:
                last = exc
                time.sleep(2.0 * (attempt + 1))
                continue
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(body))
            return result
        raise RuntimeError(f"claude CLI failed: {last}")
    base, token = backend.rstrip("/"), os.environ["AI_ROUTER_API_KEY"]
    for attempt in range(4):
        try:
            reply = httpx.post(
                f"{base}/chat/completions",
                json={**request, "model": wire_model(model, base)},
                headers={"Authorization": f"Bearer {token}"},
                timeout=timeout,
            )
            if reply.status_code in {429, 500, 502, 503, 504, 529}:
                last = RuntimeError(f"router status {reply.status_code}: {reply.text[:200]}")
                time.sleep(2.0 * (attempt + 1))
                continue
            if reply.status_code >= 400:
                raise RuntimeError(f"router status {reply.status_code}: {reply.text[:300]}")
            body = reply.json()
            result = _parse(body, cached=False)
        except (httpx.TransportError, KeyError, IndexError, ValueError) as exc:
            last = exc
            time.sleep(2.0 * (attempt + 1))
            continue
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(body))
        _log(model, result.cost_usd * CREDITS_PER_USD, tag)
        return result
    raise RuntimeError(f"the router call failed: {last}")
