"""Look at a scan with a vision model: for questions that need eyes, not text (windows on a facade, the kind of drawing).

A look is a model reading, not a measurement. Two models read the same image on their own. A count is given only
when both give the same number and both say they are sure; else the readings are given as estimates, and the agent
abstains with a best estimate. The models and the rule were picked by a small test on hand-labelled scans
(the comment at LOOK_MODELS), not by memory.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
from typing import TYPE_CHECKING, Any

from PIL import Image

from bp import llm, rates
from bp.contract import Frozen

if TYPE_CHECKING:
    import numpy as np

# The two readers, from two model families so that their errors do not go together. Test on 15 November 2026:
# 23 hand-labelled questions on 12 historic scans outside the historic suite (counts of drawings, sections, windows,
# doors, roof openings, stairs, footings and labelled rooms; years and names in print and handwriting; is it a
# floor plan; 2 questions that the scan cannot answer). Six models read the whole image at 1600 px:
#   alone, right of 23: claude-haiku-5.5 22, gpt-6-luna 20, gemini-3.8-flash 18, gemini-3.1-pro-preview 19,
#   gpt-6.1-sol 19, claude-sonnet-5.5 17 (the last three lost 4 to 6 items to router errors).
#   alone, sure and wrong: haiku 1 (a handwritten name), luna 1, gemini-3.8-flash 2, the others 0.
#   a pair, agree and sure: no pair gave a wrong answer. haiku with luna answered 18 of 23, all right, and
#   abstained on 5 (2 of them the questions with no answer); one look costs about 0.001 USD.
# The larger models were not more right on this test and cost 10 to 30 times more.
LOOK_MODELS = ("claude-haiku-5.5", "gpt-6-luna")
LOOK_MODELS_ENV = "BP_LOOK_MODELS"  # comma-separated model names in place of LOOK_MODELS, such as "a,b"
LOOK_AGREED = rates.Rate(
    confidence=0.82,
    basis="18 of 18 answers where two vision models agreed and were sure were right, on 23 test questions on 12 "
    "historic scans; 0.82 is the lower 95% bound of that share, because the test is small",
)
LOOK_SINGLE = rates.unmeasured("a vision model reading that the second model does not confirm", confidence=0.3)
MAX_SIDE = 1600  # px of the long side of the image sent; a crop of a small region is enlarged up to this
MIN_CROP = 64
MAX_TOKENS = 3000  # reasoning models spend most of this before they answer; 600 cut answers off

PROMPT = """You look at a scan of an old architectural drawing (a floor plan, an elevation, a section, a site plan, a \
title page or a page that is not a drawing). Answer one question about it by looking carefully.

Question: {question}

Rules:
- Count only what you can see on the image. Do not guess what is outside the image or hidden.
- If the question asks for text, copy the text exactly as it is written, in its own language.
- If you cannot see the answer for sure (too small, faded, ambiguous, not on the image), say so with sure=false.

Reply with JSON only, no other text:
{{"answer": "<short answer as text>", "count": <integer or null>, "sure": <true or false>, \
"seen": "<one sentence: what you looked at>"}}"""


class Reading(Frozen):
    model: str
    answer: str
    count: int | None
    sure: bool
    seen: str
    cost_usd: float = 0.0
    error: str = ""


class Look(Frozen):
    """Two readings of the same image, and what they agree on."""

    question: str
    region: tuple[int, int, int, int] | None  # x0, y0, x1, y1 in pixels, or None for the whole image
    readings: tuple[Reading, ...]
    available: bool  # False: no vision model answered (the router failed or has no credit)
    agreed_answer: str | None  # the answer when the readers agree and are sure
    agreed_count: int | None  # the count when both give the same count and both are sure

    @property
    def cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.readings)


def image_part(rgb: np.ndarray, region: tuple[int, int, int, int] | None = None) -> dict[str, Any]:
    """The image (or a crop of it) as a JPEG part for the chat request, at most MAX_SIDE px on the long side."""
    image = Image.fromarray(rgb)
    if region is not None:
        image = image.crop(region)
    scale = MAX_SIDE / max(image.size)
    if scale < 1 or region is not None:
        size = (max(1, round(image.width * min(scale, 4.0))), max(1, round(image.height * min(scale, 4.0))))
        image = image.resize(size, Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=88)
    data = base64.b64encode(buffer.getvalue()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}"}}


def _parse(content: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match is None:
        return {}
    try:
        found = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return found if isinstance(found, dict) else {}


def read_once(model: str, part: dict[str, Any], question: str) -> Reading:
    """One reading by one model. A failed call is a reading with an error, never an exception."""
    messages = [{"role": "user", "content": [{"type": "text", "text": PROMPT.format(question=question)}, part]}]
    try:
        reply = llm.chat(model, messages, max_tokens=MAX_TOKENS, tag=f"scan-look:{model}", timeout=90.0)
    except Exception as error:  # the router can fail or the spend cap be reached: the agent then abstains
        return Reading(model=model, answer="", count=None, sure=False, seen="", error=str(error)[:200])
    found = _parse(reply.content)
    count = found.get("count")
    count = int(count) if isinstance(count, (int, float)) and not isinstance(count, bool) else None
    return Reading(
        model=model, answer=str(found.get("answer", ""))[:300], count=count, sure=found.get("sure") is True,
        seen=str(found.get("seen", ""))[:300], cost_usd=reply.cost_usd,
        error="" if found else "the reply was not JSON",
    )  # fmt: skip


def _same(a: str, b: str) -> bool:
    def norm(text: str) -> str:
        return re.sub(r"[^\w]+", " ", text.lower()).strip()

    na, nb = norm(a), norm(b)
    return bool(na) and (na == nb or (min(len(na), len(nb)) >= 3 and (na in nb or nb in na)))


def look_models() -> tuple[str, ...]:
    """The readers: from BP_LOOK_MODELS when it is set, else LOOK_MODELS."""
    given = tuple(m.strip() for m in os.environ.get(LOOK_MODELS_ENV, "").split(",") if m.strip())
    return given or LOOK_MODELS


def look(
    rgb: np.ndarray,
    question: str,
    region: tuple[int, int, int, int] | None = None,
    models: tuple[str, ...] | None = None,
) -> Look:
    """Read the image (or a region) with each model, and keep what they agree on."""
    models = models or look_models()
    if region is not None:
        height, width = rgb.shape[:2]
        x0, y0 = max(0, min(region[0], region[2])), max(0, min(region[1], region[3]))
        x1, y1 = min(width, max(region[0], region[2])), min(height, max(region[1], region[3]))
        region = (x0, y0, x1, y1) if x1 - x0 >= MIN_CROP and y1 - y0 >= MIN_CROP else None
    part = image_part(rgb, region)
    readings = tuple(read_once(m, part, question) for m in models)
    good = [r for r in readings if not r.error]
    sure = len(good) == len(models) and all(r.sure for r in good)
    counts = {r.count for r in good}
    agreed_count = next(iter(counts)) if sure and len(counts) == 1 and None not in counts else None
    agreed_answer = None
    if sure and all(_same(good[0].answer, r.answer) for r in good[1:]):
        agreed_answer = good[0].answer
    return Look(question=question, region=region, readings=readings, available=bool(good),
                agreed_answer=agreed_answer, agreed_count=agreed_count)  # fmt: skip
