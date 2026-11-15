"""Translate the texts of a drawing with the small model, in a few batched calls."""

from __future__ import annotations

import json
import os
import re
import threading

from bp.llm import chat

BATCH = 150
TAG = "desk:translate"
LANGUAGES = ["English", "Finnish", "Swedish", "German", "French", "Spanish", "Norwegian", "Romanian"]
PROMPT = (
    "These texts are labels from an architectural drawing: room names, notes and abbreviations such as WC, MH, Whg. "
    "Translate each text to {language} as an architect would write it. "
    "Keep numbers, codes and units unchanged. "
    "Return a text unchanged when it is already in {language} or when it is a code or a number. "
    "Answer with JSON only: one object from each source text to its translation. Use the source texts as the keys, exactly as given."
)
_cache: dict[tuple[str, str], str] = {}
_lock = threading.Lock()


def _model() -> str:
    return os.environ.get("BP_AGENT_MODEL", "claude-haiku-5.5")


def _parse(content: str) -> dict[str, str]:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(text[start : end + 1])
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v.strip() for k, v in data.items() if isinstance(k, str) and isinstance(v, str) and v.strip()}


def _batch(texts: list[str], language: str) -> dict[str, str]:
    messages = [
        {"role": "system", "content": PROMPT.format(language=language)},
        {"role": "user", "content": json.dumps(texts, ensure_ascii=False)},
    ]
    result = chat(_model(), messages, max_tokens=min(6000, 200 + 40 * len(texts)), tag=TAG)
    asked = set(texts)
    return {k: v for k, v in _parse(result.content).items() if k in asked}


def translate(texts: list[str], language: str) -> dict[str, str]:
    distinct = list(dict.fromkeys(t.strip() for t in texts if re.search(r"[^\W\d_]", t)))
    with _lock:
        missing = [t for t in distinct if (language, t) not in _cache]
    for start in range(0, len(missing), BATCH):
        part = missing[start : start + BATCH]
        done = _batch(part, language)
        with _lock:
            for text in part:
                _cache[(language, text)] = done.get(text, text)
    with _lock:
        return {t: _cache[(language, t)] for t in distinct if (language, t) in _cache}
