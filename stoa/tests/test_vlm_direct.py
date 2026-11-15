"""The direct VLM baseline: reply parsing, rendering, and the record that each kind of reply gives. No network."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pymupdf
import pytest
from PIL import Image

from bp.contract import MissingReason, Question
from bp.llm import ChatResult
from bp.solvers import vlm_direct
from bp.solvers.vlm_direct import VlmDirectSolver, coerce_answer, parse_reply
from bp.tools.render import page_count, render_page

if TYPE_CHECKING:
    from pathlib import Path

QUESTION = Question(qid="q-1", text="How many windows are shown on this floor plan?")


def _png(path: Path, size: tuple[int, int]) -> Path:
    Image.new("RGB", size, "white").save(path)
    return path


def _pdf(path: Path, size: tuple[float, float], pages: int = 1) -> Path:
    with pymupdf.open() as doc:
        for _ in range(pages):
            doc.new_page(width=size[0], height=size[1])
        doc.save(str(path))
    return path


def _size(png: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(png)).size


class TestRender:
    def test_pdf_longest_side_is_exact(self, tmp_path: Path) -> None:
        png = render_page(_pdf(tmp_path / "a.pdf", (842, 595)), 1568)
        assert png is not None
        width, height = _size(png)
        assert width == 1568
        assert abs(height - 1568 * 595 / 842) <= 1

    def test_pdf_uses_the_first_page_and_counts_pages(self, tmp_path: Path) -> None:
        path = _pdf(tmp_path / "a.pdf", (400, 600), pages=3)
        png = render_page(path, 900)
        assert png is not None
        assert _size(png)[1] == 900
        assert page_count(path) == 3

    def test_large_image_is_reduced(self, tmp_path: Path) -> None:
        png = render_page(_png(tmp_path / "a.png", (4000, 3000)), 1568)
        assert png is not None
        assert _size(png) == (1568, 1176)

    def test_small_image_is_not_enlarged(self, tmp_path: Path) -> None:
        png = render_page(_png(tmp_path / "a.png", (500, 400)), 1568)
        assert png is not None
        assert _size(png) == (500, 400)

    def test_transparent_image_goes_onto_white(self, tmp_path: Path) -> None:
        path = tmp_path / "a.png"
        Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(path)
        png = render_page(path, 100)
        assert png is not None
        assert Image.open(io.BytesIO(png)).convert("RGB").getpixel((5, 5)) == (255, 255, 255)

    @pytest.mark.parametrize("name", ["a.ifc", "a.dxf", "a.txt"])
    def test_model_files_are_not_rendered(self, tmp_path: Path, name: str) -> None:
        path = tmp_path / name
        path.write_bytes(b"x")
        assert render_page(path, 1568) is None
        assert page_count(path) == 0


class TestParse:
    def test_plain_json(self) -> None:
        assert parse_reply('{"answer": 3, "confidence": 0.7}')["answer"] == 3

    def test_fenced_json_with_prose(self) -> None:
        reply = 'Here you go:\n```json\n{"answer": "K1", "confidence": 0.5}\n```'
        assert parse_reply(reply)["answer"] == "K1"

    @pytest.mark.parametrize("reply", ["", "three", '{"confidence": 1}', "{broken"])
    def test_bad_replies_raise(self, reply: str) -> None:
        with pytest.raises(ValueError, match=r"JSON|Expecting|answer|delimiter|property"):
            parse_reply(reply)

    @pytest.mark.parametrize(
        ("raw", "want"),
        [(3, 3), (3.0, 3), (3.5, 3.5), ("12", 12), ("12,5", 12.5), ("K1", "K1"), (None, None), ("null", None),
         ("", None), (True, None)],
    )  # fmt: skip
    def test_coerce(self, raw: object, want: object) -> None:
        assert coerce_answer(raw) == want


class TestSolver:
    @staticmethod
    def _solver(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, content: str, **env: str) -> VlmDirectSolver:
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setattr(vlm_direct, "chat", lambda *_a, **_k: ChatResult(content=content, cost_usd=0.25))
        solver = VlmDirectSolver()
        assert solver.ingest(str(_png(tmp_path / "a.png", (100, 80)))).ok
        return solver

    def test_answer(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        solver = self._solver(monkeypatch, tmp_path, '{"answer": 7, "unit": null, "confidence": 0.9}')
        record = solver.ask(QUESTION)
        assert (record.status, record.value, record.confidence, record.cost_usd) == ("answered", 7, 0.9, 0.25)

    def test_null_answer_abstains(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        solver = self._solver(monkeypatch, tmp_path, '{"answer": null, "confidence": 0.1, "reason_if_null": "no scale"}')
        record = solver.ask(QUESTION)
        assert record.status == "abstained"
        assert record.abstain is not None
        assert record.abstain.reason is MissingReason.NO_SCALE
        assert record.cost_usd == 0.25

    def test_low_confidence_abstains_and_keeps_the_estimate(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        solver = self._solver(monkeypatch, tmp_path, '{"answer": 4, "confidence": 0.3}', BP_VLM_MIN_CONF="0.5")
        record = solver.ask(QUESTION)
        assert (record.status, record.best_estimate, record.value) == ("abstained", 4, None)

    def test_confidence_at_the_threshold_answers(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        solver = self._solver(monkeypatch, tmp_path, '{"answer": 4, "confidence": 0.5}', BP_VLM_MIN_CONF="0.5")
        assert solver.ask(QUESTION).status == "answered"

    def test_parse_failure_is_an_error(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        solver = self._solver(monkeypatch, tmp_path, "I think there are seven windows.")
        record = solver.ask(QUESTION)
        assert record.status == "error"
        assert "parse failure" in record.detail
        assert record.cost_usd == 0.25

    def test_a_failed_call_is_an_error(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        def boom(*_a: object, **_k: object) -> ChatResult:
            msg = "router down"
            raise RuntimeError(msg)

        monkeypatch.setattr(vlm_direct, "chat", boom)
        solver = VlmDirectSolver()
        solver.ingest(str(_png(tmp_path / "a.png", (10, 10))))
        assert solver.ask(QUESTION).status == "error"

    def test_environment_picks_the_variant(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BP_VLM_MODEL", "claude-haiku-5.5")
        monkeypatch.setenv("BP_VLM_SIDE", "2400")
        monkeypatch.setenv("BP_VLM_MIN_CONF", "0.7")
        solver = VlmDirectSolver()
        assert (solver.model, solver.side, solver.min_conf) == ("claude-haiku-5.5", 2400, 0.7)

    def test_model_file_abstains_as_unsupported(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(vlm_direct, "chat", lambda *_a, **_k: pytest.fail("no call for an IFC file"))
        path = tmp_path / "a.ifc"
        path.write_bytes(b"ISO-10303-21;")
        solver = VlmDirectSolver()
        assert solver.ingest(str(path)).ok
        record = solver.ask(QUESTION)
        assert record.status == "abstained"
        assert record.abstain is not None
        assert record.abstain.reason is MissingReason.UNSUPPORTED
