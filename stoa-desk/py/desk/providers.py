"""More than one model service behind the one door of `bp.llm`, so a service with no credit does not stop the desk.

`bp.llm.chat` posts to one endpoint. This module replaces its `httpx` with a wrapper: when the endpoint says that
the key has no credit or is not valid, the same request goes to the next service in the list. A service that
failed is skipped for ten minutes. The list comes from the environment:

- the first service is `AI_ROUTER_BASE_URL` with `AI_ROUTER_API_KEY`
- `OPENROUTER_API_KEY`: OpenRouter, with a vendor prefix on each model name
- `VERDA_INFERENCE_API_KEY`: the Verda Inference API, with the model `DESK_VERDA_MODEL` for each request
- `HOSTINGER_ROUTER_BASE_URL` with `HOSTINGER_ROUTER_API_KEY`: the Hostinger AI Router, with bare model names
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx

OPENROUTER = "https://openrouter.ai/api/v1"
VERDA = "https://inference.verda.com/v1"
VERDA_MODEL = "deepseek-4-1-flash-1017"
VENDORS = (("claude-", "anthropic"), ("gpt-", "openai"), ("gemini-", "google"))
NO_CREDIT = {401, 402, 403}
QUOTA_WORDS = ("credit", "quota", "insufficient", "balance")
REST_S = 600.0


@dataclass(frozen=True)
class Service:
    name: str
    base: str
    key: str

    def model(self, asked: str) -> str:
        bare = asked.rsplit("/", 1)[-1]
        if "openrouter.ai" in self.base:
            return next((f"{vendor}/{bare}" for start, vendor in VENDORS if bare.startswith(start)), asked)
        if self.base.startswith(VERDA):
            return os.environ.get("DESK_VERDA_MODEL", VERDA_MODEL)
        return bare


def services() -> list[Service]:
    env = os.environ
    found = [
        Service("first", env.get("AI_ROUTER_BASE_URL", "").rstrip("/"), env.get("AI_ROUTER_API_KEY", "")),
        Service("OpenRouter", OPENROUTER, env.get("OPENROUTER_API_KEY", "")),
        Service("Verda Inference", VERDA, env.get("VERDA_INFERENCE_API_KEY", "")),
        Service("Hostinger AI Router", env.get("HOSTINGER_ROUTER_BASE_URL", "").rstrip("/"),
                env.get("HOSTINGER_ROUTER_API_KEY", "")),
    ]  # fmt: skip
    out: list[Service] = []
    for service in found:
        if service.base and service.key and all(service.base != other.base for other in out):
            out.append(service)
    return out


def _spent(reply: httpx.Response) -> bool:
    if reply.status_code in NO_CREDIT:
        return True
    return reply.status_code == 429 and any(word in reply.text.lower() for word in QUOTA_WORDS)


class Door:
    """Stands in for the `httpx` module inside `bp.llm`: `post` tries each service, the rest is `httpx` itself."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._resting: dict[str, float] = {}
        self.last = ""

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401 - the attributes of the httpx module
        return getattr(httpx, name)

    def state(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        with self._lock:
            return [{"name": s.name, "host": s.base.split("/")[2], "resting": self._resting.get(s.base, 0.0) > now,
                     "last": s.base == self.last} for s in services()]  # fmt: skip

    def post(self, _url: str, *, json: dict[str, Any], headers: dict[str, str], timeout: float) -> httpx.Response:
        listed = services()
        now = time.monotonic()
        with self._lock:
            awake = [s for s in listed if self._resting.get(s.base, 0.0) <= now]
        reply: httpx.Response | None = None
        for service in awake or listed:
            target = f"{service.base}/chat/completions"
            body = {**json, "model": service.model(str(json.get("model", "")))}
            try:
                reply = httpx.post(target, json=body, headers={**headers, "Authorization": f"Bearer {service.key}"},
                                   timeout=timeout)  # fmt: skip
            except httpx.TransportError:
                if service is (awake or listed)[-1]:
                    raise
                continue
            if not _spent(reply):
                with self._lock:
                    self.last = service.base
                return reply
            with self._lock:
                self._resting[service.base] = time.monotonic() + REST_S
        if reply is None:
            msg = "no model service is set: AI_ROUTER_BASE_URL and AI_ROUTER_API_KEY are empty"
            raise httpx.ConnectError(msg)
        return reply


DOOR = Door()


def install() -> None:
    import bp.llm  # noqa: PLC0415 - bp loads slowly; the service imports it at start

    bp.llm.httpx = DOOR  # type: ignore[assignment]
