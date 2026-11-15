"""The HTTP service between the desk app and the `bp` agent. JSON in, JSON out. It listens on localhost only.

Run from `stoa-desk/`: `pnpm py` (see package.json).
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import zipfile
from functools import partial
from pathlib import Path
from typing import Any

import uvicorn
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request  # noqa: TC002 - starlette reads the annotation
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

from bp.tools import render
from desk import dxfpage, ink, model3d, providers, translate
from desk.store import CACHE, Store

REPO = Path(__file__).resolve().parents[3]
DATASET = REPO / "stoa" / "data" / "junction-dataset" / "data"
EXTERNAL = REPO / "stoa" / "data" / "external" / "sheets"
ROOTS = {"sheets": REPO / "stoa" / "data" / "sheets-test", "discord": EXTERNAL / "discord"}
UPLOADS = Path(__file__).resolve().parents[1] / ".uploads"
FORMATS = {".png": "PNG", ".jpg": "JPG", ".jpeg": "JPG", ".pdf": "PDF", ".ifc": "IFC", ".dxf": "DXF"}
MAX_UPLOAD = 80_000_000
AREA = "What is the floor area of the largest room?"
DOORS = "How many doors are drawn on this drawing?"
SCALE = "What is the scale of this drawing?"
HEIGHT = "What is the ceiling height of the largest room?"
SAMPLES: list[dict[str, Any]] = [
    {"id": "swiss-1000", "name": "Apartment floor", "tag": "Floor plan", "format": "PDF",
     "file": "swiss_dwellings/site1000_bldg2082_floor9385.pdf", "questions": [
         "What is the net floor area of apartment B in m², without balconies?",
         "How many distinct door openings are on this floor plan?",
         AREA,
         "What is the ceiling height of room 2.10?",
     ]},
    {"id": "sheet-dorm", "name": "Dormitory scan", "tag": "Scanned sheet", "format": "PNG", "root": "sheets",
     "file": "us_daf_dorm_sd_drawings_p003.png", "questions": [
         "What is the floor area of the largest room with an outline?",
         "What is the scale of this sheet?",
         "What is the ceiling height of the corridor?",
     ]},
    {"id": "hard-aw-056", "name": "Foundation plan", "tag": "Hard set", "format": "PNG", "root": "discord",
     "file": "discord_us_aw_078-24-33_p056.png", "questions": [SCALE, AREA]},
    {"id": "hard-aw-096", "name": "Piping plan", "tag": "Hard set", "format": "PNG", "root": "discord",
     "file": "us_aw_078-24-28_march_2020_p096.png", "questions": [SCALE, AREA]},
    {"id": "school-primary", "name": "Primary school", "tag": "Scanned sheet", "format": "PNG", "root": "sheets",
     "file": "uk_dfe_pri-dfe-xx-00-d-x-0201-primary_school_ga_plan_level_00-a-c01_p001.png", "questions": [
         "How many classrooms are on this floor?", AREA, SCALE, DOORS,
     ]},
    {"id": "home-10052", "name": "Family home", "tag": "Picture of a plan", "format": "PNG",
     "file": "cubicasa5k/colorful-10052.png", "questions": [
         "How many doors are shown on this floor plan?",
         "How many windows are shown on this floor plan?",
         "What is the floor area of the living room?",
     ]},
    {"id": "duplex-ifc", "name": "Duplex house", "tag": "Building model", "format": "IFC",
     "file": "ifc_bench/duplex_arc.ifc", "questions": [
         "How many doors are in the building?",
         "What is the total floor area of all rooms?",
         "What is the ceiling height of room A203?",
         "How many windows are on the north facade?",
     ]},
]  # fmt: skip
OWN = ["How many rooms are on this drawing?", DOORS, AREA, SCALE]
uploads: dict[str, dict[str, Any]] = {}


def _path(sample: dict[str, Any]) -> Path:
    if "path" in sample:
        return Path(sample["path"])
    return ROOTS.get(sample.get("root", ""), DATASET) / sample["file"]


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", Path(name).name)[-80:] or "drawing"


def _register(path: Path) -> dict[str, Any]:
    digest, _, name = path.name.partition("__")
    sample = {"id": f"up-{digest}", "name": Path(name).stem.replace("-", " ").replace("_", " ")[:60], "tag": "Your drawing",
              "format": FORMATS.get(path.suffix.lower(), "File"), "path": str(path), "file": name, "questions": OWN}  # fmt: skip
    uploads[sample["id"]] = sample
    return sample


def _load_uploads() -> None:
    if UPLOADS.is_dir():
        for path in sorted(UPLOADS.iterdir(), key=lambda p: p.stat().st_mtime):
            if "__" in path.name and path.suffix.lower() in FORMATS:
                _register(path)


def _all() -> list[dict[str, Any]]:
    return [s for s in [*reversed(uploads.values()), *SAMPLES] if _path(s).exists()]


def _sample(ident: str) -> dict[str, Any] | None:
    return next((s for s in _all() if s["id"] == ident), None)


def _listed() -> list[dict[str, Any]]:
    return [{"id": s["id"], "name": s["name"], "format": s["format"], "tag": s["tag"]} for s in _all()]


_load_uploads()
store = Store()


def _fail(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


async def health(_request: Request) -> JSONResponse:
    return JSONResponse({"models": providers.DOOR.state()})


async def samples(_: Request) -> JSONResponse:
    return JSONResponse({"samples": _listed()})


async def open_sample(request: Request) -> JSONResponse:
    body = await request.json()
    sample = _sample(str(body.get("sample", "")))
    if sample is None:
        return _fail(404, "This drawing is not here any more. Add it again.")
    try:
        document = await run_in_threadpool(store.open, _path(sample), sample["name"], partial(stages.__setitem__, sample["id"]))
    except Exception as exc:  # noqa: BLE001 - a file from a person can fail in any reader
        return _fail(422, f"The drawing could not be read: {type(exc).__name__}: {exc}"[:300])
    return JSONResponse(document.public() | {"name": sample["name"], "questions": sample["questions"], "samples": _listed(), "sample": sample["id"]})


async def sample_stage(request: Request) -> JSONResponse:
    return JSONResponse({"stage": stages.get(request.path_params["sample"], 0)}, headers={"Cache-Control": "no-store"})


# How far the reading of each drawing is: 1 file, 2 lines and text, 3 facts, 4 checks.
stages: dict[str, int] = {}


async def upload(request: Request) -> JSONResponse:
    name = _safe(request.query_params.get("name", "drawing"))
    if Path(name).suffix.lower() not in FORMATS:
        return _fail(415, "Use a PNG, JPG, PDF, IFC or DXF file.")
    body = await request.body()
    if not body:
        return _fail(400, "The file is empty.")
    if len(body) > MAX_UPLOAD:
        return _fail(413, "The file is larger than 80 MB.")
    UPLOADS.mkdir(exist_ok=True)
    path = UPLOADS / f"{hashlib.sha256(body).hexdigest()[:12]}__{name}"
    await run_in_threadpool(path.write_bytes, body)
    return JSONResponse({"sample": _register(path)["id"]})


TEST_SET = [
    ("1-apartment-floor.pdf", DATASET / "swiss_dwellings" / "site1000_bldg2082_floor9385.pdf"),
    ("2-dormitory-scan.png", ROOTS["sheets"] / "us_daf_dorm_sd_drawings_p003.png"),
    ("3-hard-set-office-56.png", ROOTS["discord"] / "discord_us_aw_078-24-33_p056.png"),
    ("4-hard-set-office-96.png", ROOTS["discord"] / "us_aw_078-24-28_march_2020_p096.png"),
    ("5-secondary-school.png", ROOTS["sheets"] / "uk_dfe_sec-dfe-xx-00-d-x-0201-secondary_school_ga_plan_level_00-a-c01_p001.png"),
    ("6-family-home.png", DATASET / "cubicasa5k" / "colorful-10062.png"),
    ("7-duplex-house.ifc", DATASET / "ifc_bench" / "duplex_arc.ifc"),
    ("8-apartment-floor.dxf", DATASET / "swiss_dwellings" / "site1000_bldg2082_floor9385.dxf"),
    ("9-historic-survey.jpg", DATASET / "habs" / "ak0015_sheet_00001.jpg"),
]


def _test_set() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for name, path in TEST_SET:
            if path.exists():
                archive.write(path, f"stoa-test-drawings/{name}")
    return buffer.getvalue()


async def sample_file(request: Request) -> Response:
    if request.path_params["sample"] == "test-set":
        body = await run_in_threadpool(_test_set)
        return Response(body, media_type="application/zip",
                        headers={"Content-Disposition": 'attachment; filename="stoa-test-drawings.zip"'})  # fmt: skip
    sample = _sample(request.path_params["sample"])
    if sample is None:
        return _fail(404, "no such drawing")
    path = _path(sample)
    return FileResponse(path, filename=f"{sample['id']}{path.suffix.lower()}")


async def sample_thumb(request: Request) -> Response:
    sample = _sample(request.path_params["sample"])
    if sample is None:
        return _fail(404, "no such drawing")
    png = await run_in_threadpool(_thumb, sample["id"], _path(sample))
    if png is None:
        return _fail(404, "this drawing has no picture")
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=86400"})


def _thumb(ident: str, path: Path) -> bytes | None:
    if ident not in thumbs:
        kept = CACHE / f"thumb.{ident}.png"
        if kept.exists():
            thumbs[ident] = kept.read_bytes()
            return thumbs[ident]
        try:
            if model3d.is_model(path):
                thumbs[ident] = model3d.picture(path)
            elif dxfpage.is_dxf(path):
                thumbs[ident] = dxfpage.render(path, 420)
            else:
                thumbs[ident] = render.render_page(path, 420, 0)
        except Exception:  # noqa: BLE001 - a picture is optional
            thumbs[ident] = None
        if thumbs[ident] is not None:
            CACHE.mkdir(exist_ok=True)
            kept.write_bytes(thumbs[ident])
    return thumbs[ident]


async def remove_sample(request: Request) -> JSONResponse:
    sample = uploads.get(request.path_params["sample"])
    if sample is None:
        return _fail(404, "Only a drawing that you added can be deleted.")
    digest = sample["id"].removeprefix("up-")
    Path(sample["path"]).unlink(missing_ok=True)
    del uploads[sample["id"]]
    thumbs.pop(sample["id"], None)
    (CACHE / f"thumb.{sample['id']}.png").unlink(missing_ok=True)
    shared = store.documents.get(f"doc-{digest}")
    if shared is None or shared.path == Path(sample["path"]):
        store.forget(digest)
    return JSONResponse({"samples": _listed()})


thumbs: dict[str, bytes | None] = {}


async def page(request: Request) -> Response:
    document = store.documents.get(request.path_params["doc"])
    if document is None:
        return _fail(404, "no such document")
    side = min(4000, max(256, int(request.query_params.get("side", "2400"))))
    layer = request.query_params.get("layer", "page")
    if layer not in ink.LAYERS:
        return _fail(400, "layer is page, ink or walls")
    png = await run_in_threadpool(store.page_png, document, int(request.path_params["page"]), side, layer)
    if png is None:
        return _fail(404, "this document has no page image")
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


async def model(request: Request) -> Response:
    document = store.documents.get(request.path_params["doc"])
    if document is None:
        return _fail(404, "no such document")
    if not model3d.is_model(document.path):
        return _fail(404, "This document is not a building model.")
    try:
        body = await run_in_threadpool(model3d.mesh, document.path)
    except Exception as exc:  # noqa: BLE001 - a model from a person can fail in the geometry kernel
        return _fail(422, f"The 3D model could not be built: {type(exc).__name__}: {exc}"[:300])
    return Response(body, media_type="application/octet-stream", headers={"Cache-Control": "private, max-age=3600"})


async def set_scale(request: Request) -> JSONResponse:
    document = store.documents.get(request.path_params["doc"])
    if document is None:
        return _fail(404, "no such document")
    body = await request.json()
    try:
        points = [(float(x), float(y)) for x, y in body.get("points") or []]
        length = float(body.get("lengthM", 0))
    except (TypeError, ValueError):
        points, length = [], 0.0
    apart = len(points) == 2 and points[0] != points[1]  # noqa: PLR2004 - two points
    if not apart or not 0.01 <= length <= 10000:  # noqa: PLR2004 - 1 cm to 10 km
        return _fail(400, "Give two different points on the drawing and their real distance in metres.")
    try:
        await run_in_threadpool(store.calibrate, document, points, length)
    except ValueError as exc:
        return _fail(422, str(exc))
    except Exception as exc:  # noqa: BLE001 - the reading can fail in many ways
        return _fail(500, f"The drawing could not be read again: {type(exc).__name__}: {exc}"[:300])
    return JSONResponse(document.public())


async def ask(request: Request) -> JSONResponse:
    document = store.documents.get(request.path_params["doc"])
    if document is None:
        return _fail(404, "no such document")
    body = await request.json()
    question = str(body.get("question", "")).strip()
    if not question:
        return _fail(400, "the question is empty")
    about = [str(i)[:80] for i in body.get("about") or []][:60]
    return JSONResponse(store.ask(document, question[:500], about).public())


TEXT_FACTS = {"Text", "Name", "Label", "Use"}
MAX_TEXTS = 600
translations: dict[tuple[str, str], dict[str, str]] = {}


def _texts(document: Any) -> list[str]:  # noqa: ANN401 - the Document of desk.store
    found: list[str] = []
    for entity in document.public().get("entities", []):
        found.append(str(entity.get("label", "")))
        for fact in entity.get("facts", []):
            if fact.get("key") in TEXT_FACTS and isinstance(fact.get("value"), str):
                found.append(fact["value"])
    return list(dict.fromkeys(t.strip() for t in found if any(c.isalpha() for c in t)))[:MAX_TEXTS]


def _translated(document: Any, language: str) -> dict[str, str]:  # noqa: ANN401
    key = (document.id, language)
    if key not in translations:
        done = translate.translate(_texts(document), language)
        translations[key] = {k: v for k, v in done.items() if v != k}
    return translations[key]


async def translate_document(request: Request) -> JSONResponse:
    document = store.documents.get(request.path_params["doc"])
    if document is None:
        return _fail(404, "no such document")
    body = await request.json()
    language = str(body.get("language", ""))
    if language not in translate.LANGUAGES:
        return _fail(400, "The language is not one of: " + ", ".join(translate.LANGUAGES) + ".")
    try:
        texts = await run_in_threadpool(_translated, document, language)
    except Exception as exc:  # noqa: BLE001 - the router can fail in many ways
        return _fail(502, f"The translation failed: {type(exc).__name__}. Try again."[:300])
    return JSONResponse({"language": language, "texts": texts})


async def run(request: Request) -> JSONResponse:
    found = store.runs.get(request.path_params["run"])
    if found is None:
        return _fail(404, "no such run")
    return JSONResponse(await run_in_threadpool(found.public))


app = Starlette(
    routes=[
        Route("/health", health),
        Route("/samples", samples),
        Route("/samples/{sample}/file", sample_file),
        Route("/samples/{sample}/thumb", sample_thumb),
        Route("/samples/{sample}/stage", sample_stage),
        Route("/samples/{sample}", remove_sample, methods=["DELETE"]),
        Route("/documents/upload", upload, methods=["POST"]),
        Route("/documents/sample", open_sample, methods=["POST"]),
        Route("/documents/{doc}/pages/{page:int}", page),
        Route("/documents/{doc}/model", model),
        Route("/documents/{doc}/ask", ask, methods=["POST"]),
        Route("/documents/{doc}/scale", set_scale, methods=["POST"]),
        Route("/documents/{doc}/translate", translate_document, methods=["POST"]),
        Route("/runs/{run}", run),
    ]
)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("DESK_PY_PORT", "4722")), log_level="warning")
