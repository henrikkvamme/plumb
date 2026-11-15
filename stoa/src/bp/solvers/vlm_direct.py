"""The direct VLM baseline: show a hosted model the first page and the question. No tools, no checks.

One class serves every variant. The environment picks the variant, so a run note can name it:

- `BP_VLM_MODEL`: the router model id (default `gemini-3.5-flash-lite`).
- `BP_VLM_SIDE`: the longest side of the page image in pixels (default 1568).
- `BP_VLM_MIN_CONF`: an answer with a lower confidence becomes an abstention (default 0, so only a null answer abstains).
- `BP_VLM_EFFORT`: a `reasoning_effort` value for models that take one (default: not sent).
- `BP_VLM_MAX_TOKENS`: the reply limit, in tokens (default 2048).

The reply is JSON: `{"answer": ..., "unit": ..., "confidence": 0..1, "reason_if_null": ...}`. A reply that
is not that JSON gives status "error". An abstention keeps the model's own answer as `best_estimate`, so a
later study can tell what a different threshold would have scored, with no new calls.
"""

from __future__ import annotations

import base64
import json
import os
import re
from typing import Any

from bp.contract import Abstain, AnswerRecord, Calibration, IngestReport, MissingReason, Question
from bp.llm import chat
from bp.tools.render import render_page

DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_SIDE = 1568
SYSTEM_PROMPT = (
    "You answer one question about a building drawing. The drawing is the image. "
    "Look at the drawing with care, and answer from what it shows. "
    "Reply with one JSON object and nothing else: "
    '{"answer": <number or string or null>, "unit": <unit text or null>, '
    '"confidence": <number from 0 to 1>, "reason_if_null": <short text or null>}. '
    "For a count, the answer is an integer. For a length or an area, the answer is a number in the unit that the "
    'question asks (m2 for an area when no unit is named), and "unit" names it. '
    "For a code or a name, the answer is the text as printed. "
    "The confidence is your chance that the answer is exactly right. "
    "If the drawing does not let you answer with confidence, for example no scale or text you cannot read, "
    'set "answer" to null and put the reason in "reason_if_null".'
)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_NUMBER = re.compile(r"^[-+]?\d+(?:[.,]\d+)?$")


def _reason(text: str) -> MissingReason:
    lowered = text.lower()
    if "scale" in lowered:
        return MissingReason.NO_SCALE
    if any(word in lowered for word in ("unread", "illegible", "blurry", "too small", "cannot read")):
        return MissingReason.UNREADABLE
    if any(word in lowered for word in ("not shown", "not on", "no such", "not visible", "not present")):
        return MissingReason.NOT_ON_DOCUMENT
    return MissingReason.AMBIGUOUS


def parse_reply(content: str) -> dict[str, Any]:
    """The JSON object in a model reply. It raises ValueError when there is none."""
    text = _FENCE.sub("", content.strip())
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        msg = f"no JSON object in the reply: {content[:120]!r}"
        raise ValueError(msg)
    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict) or "answer" not in parsed:
        msg = f"the JSON has no 'answer': {content[:120]!r}"
        raise ValueError(msg)
    return parsed


def coerce_answer(raw: object) -> float | int | str | None:
    """A number stays a number, a numeric string becomes one, other text stays text."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return int(raw) if float(raw).is_integer() else float(raw)
    text = str(raw).strip()
    if not text or text.lower() in {"null", "none", "n/a", "unknown"}:
        return None
    if _NUMBER.match(text):
        number = float(text.replace(",", "."))
        return int(number) if number.is_integer() else number
    return text


class VlmDirectSolver:
    """Reads the environment once. It renders the first page at ingest and sends it with each question."""

    name = "vlm-direct"

    def __init__(self) -> None:
        self.model = os.environ.get("BP_VLM_MODEL", DEFAULT_MODEL)
        self.side = int(os.environ.get("BP_VLM_SIDE", str(DEFAULT_SIDE)))
        self.min_conf = float(os.environ.get("BP_VLM_MIN_CONF", "0"))
        self.effort = os.environ.get("BP_VLM_EFFORT", "")
        self.max_tokens = int(os.environ.get("BP_VLM_MAX_TOKENS", "2048"))
        self._image_url: str | None = None

    def ingest(self, path: str) -> IngestReport:
        png = render_page(path, self.side)
        if png is not None:
            self._image_url = "data:image/png;base64," + base64.b64encode(png).decode()
        detail = f"{self.model} side {self.side}" if png is not None else "not rendered: no image of this file type"
        return IngestReport(ok=True, detail=detail)

    def calibrate(self, calibration: Calibration) -> None:
        del calibration  # a direct baseline has no scale to set

    def _abstain(self, reason: MissingReason, detail: str, *, estimate: float | str | None = None,
                 cost: float = 0.0, confidence: float = 0.0, unit: str | None = None) -> AnswerRecord:  # fmt: skip
        abstain = Abstain(reason=reason, detail=detail[:300], request="give a clearer drawing, or the scale")
        return AnswerRecord(status="abstained", abstain=abstain, best_estimate=estimate, cost_usd=cost,
                            confidence=confidence, unit=unit, detail=detail[:300])  # fmt: skip

    def ask(self, question: Question) -> AnswerRecord:
        if self._image_url is None:
            return self._abstain(MissingReason.UNSUPPORTED, "this file type is not rendered by the baseline")
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": self._image_url}},
                    {"type": "text", "text": question.text},
                ],
            },
        ]
        extra = {"reasoning_effort": self.effort} if self.effort else None
        try:
            result = chat(self.model, messages, max_tokens=self.max_tokens, tag=f"vlm-direct:{self.model}", extra=extra)
        except Exception as exc:
            return AnswerRecord(status="error", detail=f"{type(exc).__name__}: {exc}"[:300])
        try:
            reply = parse_reply(result.content)
            confidence = min(1.0, max(0.0, float(reply.get("confidence", 0.5) or 0.0)))
        except (ValueError, TypeError) as exc:
            return AnswerRecord(status="error", cost_usd=result.cost_usd, detail=f"parse failure: {exc}"[:300])
        value = coerce_answer(reply["answer"])
        unit = reply.get("unit")
        unit_text = str(unit) if unit not in {None, ""} else None
        if value is None:
            why = str(reply.get("reason_if_null") or "the model gave no answer")
            return self._abstain(_reason(why), why, cost=result.cost_usd, confidence=confidence)
        if confidence < self.min_conf:
            return self._abstain(MissingReason.AMBIGUOUS, f"confidence {confidence:.2f} under {self.min_conf:.2f}",
                                 estimate=value, cost=result.cost_usd, confidence=confidence, unit=unit_text)  # fmt: skip
        return AnswerRecord(status="answered", value=value, unit=unit_text, confidence=confidence,
                            cost_usd=result.cost_usd, detail=self.model)  # fmt: skip
