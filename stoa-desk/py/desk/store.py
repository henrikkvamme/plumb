"""Open documents and runs, kept in memory. One document has one agent solver, as in the evaluation harness."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bp.agent.core import run_agent
from bp.llm import ChatResult, chat
from bp.solvers.agent import AgentSolver
from bp.tools import render
from desk import dxfpage, explain, facts, ink, providers, trust
from desk.trace import Recorder, raw_steps

if TYPE_CHECKING:
    from collections.abc import Callable

Json = dict[str, Any]

# What the desk keeps on disk between starts: the facts of each opened drawing and its page pictures.
providers.install()

CACHE = Path(__file__).resolve().parents[1] / ".cache"
CACHE_VERSION = 5
SELECTION_LIMIT = 30

KIND_LABELS = {
    "plan_pdf": "Vector floor plan (PDF)",
    "bim_sheet": "Sheet from a BIM model (PDF)",
    "ifc": "IFC building model",
    "dxf": "CAD drawing (DXF)",
    "raster_rooms": "Raster floor plan",
    "raster_counts": "Raster floor plan",
    "raster_rooms+counts": "Raster floor plan",
    "none": "No reader for this document yet",
}


USER_SCALE_S = float(os.environ.get("DESK_USER_SCALE_S", "1200"))


@dataclass
class Document:
    id: str
    name: str
    path: Path
    solver: AgentSolver | None
    facts: facts.DocumentFacts | None
    ingest_ms: float
    stored: Json | None = None
    error: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock)
    ready: threading.Event = field(default_factory=threading.Event)
    scale_given: float = 0.0

    def public(self) -> Json:
        if self.solver is None:
            return (self.stored or {}) | {"id": self.id, "name": self.name}
        known = self.facts
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.solver.kind,
            "kindLabel": KIND_LABELS.get(self.solver.kind, self.solver.kind),
            "ingestMs": round(self.ingest_ms),
            "pages": known.pages if known else [],
            "entities": known.entities if known else [],
            "summary": known.summary if known else [],
            "unknown": known.unknown if known else [],
            "conflicts": known.conflicts if known else [],
            "tools": [{"name": t.name, "title": explain.TITLES.get(t.name, t.name), "description": t.description,
                       "method": t.method} for t in self.solver.tools],
        }  # fmt: skip


@dataclass
class Run:
    id: str
    document: Document
    question: str
    recorder: Recorder
    about: list[str] = field(default_factory=list)
    started: float = field(default_factory=time.perf_counter)
    status: str = "running"
    answer: Json | None = None
    error: str = ""
    version: int = 0

    def public(self) -> Json:
        solver = self.document.solver
        tools = {t.name: t for t in solver.tools} if solver is not None else {}
        steps = explain.build_steps(raw_steps(self.recorder, set(tools)), tools, self.document.facts) if tools or solver else []
        for step in steps:
            del step["data"]
        return {
            "id": self.id,
            "documentId": self.document.id,
            "question": self.question,
            "about": [e["label"] for e in _chosen(self.document, self.about)],
            "status": self.status,
            "activity": self.recorder.activity if self.status == "running" else "",
            "steps": steps,
            "answer": self.answer,
            "error": self.error,
            "elapsedMs": round((time.perf_counter() - self.started) * 1000.0),
        }


class Store:
    def __init__(self) -> None:
        self.documents: dict[str, Document] = {}
        self.runs: dict[str, Run] = {}
        self.images: dict[tuple[str, int, int, str], bytes] = {}
        self.lock = threading.Lock()

    def open(self, path: Path, name: str | None = None, note: Callable[[int], None] = lambda _step: None) -> Document:
        """Open a drawing. One that was open before comes from the disk at once. A scale from a person ends after a time."""
        note(1)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        ident = f"doc-{digest}"
        with self.lock:
            known = self.documents.get(ident)
            if known is not None and not 0.0 < known.scale_given < time.monotonic() - USER_SCALE_S:
                return known
            self.documents.pop(ident, None)
        stored = _stored(ident)
        document = Document(ident, name or path.name, path, None, None, 0.0, stored)
        if stored is None:
            self._ingest(document, note=note)
        else:
            threading.Thread(target=self._ingest, args=(document, True), daemon=True).start()
        with self.lock:
            return self.documents.setdefault(ident, document)

    def _ingest(
        self, document: Document, quiet: bool = False, note: Callable[[int], None] = lambda _step: None  # noqa: FBT001, FBT002
    ) -> None:
        started = time.perf_counter()
        try:
            note(2)
            solver = AgentSolver()
            solver.ingest(str(document.path))
            note(3)
            known = facts.read(solver.kind, str(document.path))
            note(4)
            if known is not None:
                trust.rate(solver.kind, known)
            document.facts = known
            document.ingest_ms = (time.perf_counter() - started) * 1000.0
            document.solver = solver
            CACHE.mkdir(exist_ok=True)
            _file(document.id).write_text(json.dumps(document.public()))
        except Exception as exc:
            document.error = f"{type(exc).__name__}: {exc}"[:300]
            if not quiet:
                raise
        finally:
            document.ready.set()

    def calibrate(self, document: Document, points: list[tuple[float, float]], length_m: float) -> None:
        """Set the scale that the person gives, and read the facts again with it."""
        from bp.contract import Calibration  # noqa: PLC0415

        self.wait(document)
        solver = document.solver
        if document.path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}:
            raise ValueError("The scale of this file comes from the file itself. A scale can be set on an image or a scan.")
        given = Calibration(points=(points[0], points[1]), real_length_m=length_m)
        with document.lock:
            solver.calibrate(given)
            known = facts.read(solver.kind, str(document.path), given)
            if known is not None:
                trust.rate(solver.kind, known)
            document.facts = known
            document.scale_given = time.monotonic()

    def wait(self, document: Document) -> None:
        """Block until the agent of the document is loaded."""
        document.ready.wait()
        if document.solver is None:
            raise RuntimeError(document.error or "the drawing could not be read")

    def forget(self, digest: str) -> None:
        """Drop a drawing from memory and from the disk cache."""
        ident = f"doc-{digest}"
        with self.lock:
            self.documents.pop(ident, None)
            for key in [k for k in self.images if k[0] == ident]:
                del self.images[key]
        for found in CACHE.glob(f"{ident}*"):
            found.unlink(missing_ok=True)

    def page_png(self, document: Document, page: int, side: int, layer: str = "page") -> bytes | None:
        key = (document.id, page, side, layer)
        with self.lock:
            cached = self.images.get(key)
        if cached is not None:
            return cached
        kept = CACHE / f"{document.id}.{page}.{side}.{layer}.png"
        if kept.exists():
            image = kept.read_bytes()
            with self.lock:
                self.images[key] = image
            return image
        png = dxfpage.render(document.path, side) if dxfpage.is_dxf(document.path) else render.render_page(document.path, side, page)
        if png is None:
            return None
        self.wait(document)
        known = document.facts
        rooms = [
            [(float(x), float(y)) for x, y in entity["points"]]
            for entity in (known.entities if known is not None else [])
            if entity["kind"] == "room" and entity.get("geometry") == "polygon" and entity["page"] == page
        ]
        width = next((float(p["width"]) for p in (known.pages if known is not None else []) if p["index"] == page), 1.0)
        image = ink.layer(png, layer, rooms, width)
        CACHE.mkdir(exist_ok=True)
        kept.write_bytes(image)
        with self.lock:
            self.images[key] = image
        return image

    def ask(self, document: Document, question: str, about: list[str] | None = None) -> Run:
        run = Run(id=uuid.uuid4().hex[:12], document=document, question=question, recorder=Recorder(), about=about or [])
        with self.lock:
            self.runs[run.id] = run
        threading.Thread(target=self._work, args=(run,), daemon=True).start()
        return run

    def _work(self, run: Run) -> None:
        recorder = run.recorder
        try:
            self.wait(run.document)
            solver = run.document.solver
            chosen = _selection(run.document, run.about)
            if not solver.tools:
                record = solver.ask(_question((chosen + "\n\nQuestion: " if chosen else "") + run.question))
                rejections = 0
            else:
                def call(messages: list[Json], schemas: list[Json]) -> ChatResult:
                    return chat(solver.model, messages, tools=schemas, max_tokens=1500, tag=f"desk:{solver.kind}")

                with run.document.lock:
                    result = run_agent(
                        run.question, [recorder.tool(t) for t in solver.tools], recorder.chat(call), context="\n\n".join(part for part in (solver.context, chosen) if part)
                    )
                record, rejections = result.record, result.rejections
            tools = {t.name: t for t in solver.tools}
            steps = explain.build_steps(raw_steps(recorder, set(tools)), tools, run.document.facts)
            source = explain.derivation(record, steps, run.document.facts)
            abstain = record.abstain
            run.answer = {
                "status": record.status,
                "value": record.value,
                "unit": record.unit,
                "margin": trust.margin(solver.kind, record.value, record.unit)
                if record.status == "answered" and source is not None and source["stepId"] is not None else None,
                "convention": record.convention,
                "abstain": None if abstain is None else {"reason": abstain.reason.value, "detail": abstain.detail,
                                                         "request": abstain.request},
                "bestEstimate": record.best_estimate,
                "costUsd": record.cost_usd,
                "derivation": source,
                "confidence": explain.confidence(record, steps, solver.kind, run.document.facts, source, rejections, run.question),
                "rejections": rejections,
            }  # fmt: skip
            run.status = record.status
        except Exception as exc:  # the desk shows the failure; it must not hang on "running"
            run.error = _problem(exc)
            run.status = "error"


def _chosen(document: Document, about: list[str]) -> list[Json]:
    facts = document.facts
    if facts is None or not about:
        return []
    by_id = {e["id"]: e for e in facts.entities}
    return [by_id[i] for i in about if i in by_id]


def _selection(document: Document, about: list[str]) -> str:
    """What the person selected on the drawing, as context for the agent."""
    chosen = _chosen(document, about)
    if not chosen:
        return ""
    lines = []
    for entity in chosen[:SELECTION_LIMIT]:
        known = "; ".join(f"{f['key']}: {f['value']}{' ' + f['unit'] if f.get('unit') else ''}"
                          for f in entity["facts"] if f.get("value") is not None)  # fmt: skip
        lines.append(f'- {entity['kind']} "{entity['label']}" (id {entity['id']}){': ' + known if known else ''}')
    more = len(chosen) - SELECTION_LIMIT
    return ('The person selected these items on the drawing. In the question, "this", "these", "here", "it" and '
            '"the selection" mean these items. A question that does not point at the selection is about the whole '
            "drawing: a ranking such as the largest or the second largest room, a total, or a count of all rooms "
            "covers every room, the selected ones too. Get each number of the answer from a tool call, not from "
            "this list.\n"
            + "\n".join(lines) + (f"\n- and {more} more" if more > 0 else ""))  # fmt: skip


def _question(text: str) -> Any:  # noqa: ANN401 - the frozen Question type of bp
    from bp.contract import Question  # noqa: PLC0415

    return Question(qid="desk", text=text)


def _problem(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}"[:500]
    if "402" in text or "nsufficient" in text:
        return ("The AI model service has no credit left, so the agent cannot plan this answer now. "
                "The facts of the drawing still work. Try again when the credit is back.")  # fmt: skip
    return text


def _file(ident: str) -> Path:
    return CACHE / f"{ident}.v{CACHE_VERSION}.json"


def _stored(ident: str) -> Json | None:
    try:
        return json.loads(_file(ident).read_text())
    except (OSError, ValueError):
        return None
