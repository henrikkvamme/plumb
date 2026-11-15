"""Start the desk service in the role that the environment names.

- `DESK_TOKEN` set: the reader on the GPU server. It serves the whole desk service on every interface, and each
  request must carry `Authorization: Bearer <DESK_TOKEN>`.
- `DESK_REMOTE_URL` and `DESK_REMOTE_TOKEN` set: the front on the web server. PNG and JPG drawings go to the reader on
  the GPU server; vector PDF, DXF and IFC drawings stay in this process. It listens on localhost only.
- Neither set: the plain desk service, as `python -m desk.service` starts it.
"""

from __future__ import annotations

import hmac
import json
import os
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs

import httpx
import uvicorn
from starlette.responses import JSONResponse, Response

from desk import service

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

RASTER = {"PNG", "JPG"}
KEPT_HEADERS = ("content-type", "cache-control", "content-disposition")
OFFLINE = (
    "Scanned and photographed drawings (PNG and JPG) are read on our GPU server, and it does not answer now. "
    "Vector PDF, DXF and IFC drawings still work. Try one of those, or try again later."
)


class Guard:
    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.expected = f"Bearer {token}".encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            given = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(given, self.expected):
                await JSONResponse({"error": "unauthorized"}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


async def _read(receive: Receive) -> bytes:
    chunks: list[bytes] = []
    more = True
    while more:
        message = await receive()
        chunks.append(message.get("body", b""))
        more = message.get("more_body", False)
    return b"".join(chunks)


def _replay(body: bytes, receive: Receive) -> Receive:
    pending = [True]

    async def again() -> Message:
        if pending:
            pending.clear()
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()

    return again


def _is_raster(ident: str) -> bool:
    sample = service._sample(ident)  # noqa: SLF001 - the front shares the sample list of the service
    return sample is not None and sample["format"] in RASTER


def _route(method: str, parts: list[str]) -> str:
    head = parts[0] if parts else ""
    if method == "POST" and parts in (["documents", "sample"], ["documents", "upload"]):
        return "open" if parts[1] == "sample" else "upload"
    remote = (
        (head == "documents" and len(parts) >= 2 and parts[1] not in service.store.documents)
        or (head == "runs" and len(parts) == 2 and parts[1] not in service.store.runs)
        or (head == "samples" and len(parts) == 3 and parts[2] == "stage" and _is_raster(parts[1]))
    )
    if remote:
        return "remote"
    if method == "DELETE" and head == "samples" and len(parts) == 2 and _is_raster(parts[1]):
        return "delete"
    return "local"


class Split:
    def __init__(self, app: ASGIApp, url: str, token: str) -> None:
        self.app = app
        self.client = httpx.AsyncClient(
            base_url=url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(900.0, connect=5.0),
        )
        self.remote_ids: set[str] = set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method, parts = scope["method"], [p for p in scope["path"].split("/") if p]
        route = _route(method, parts)
        if route == "open":
            await self._open(scope, receive, send)
        elif route == "upload":
            await self._upload(scope, receive, send)
        elif route == "remote":
            await self._remote_or_local(scope, receive, send, known=parts[1] in self.remote_ids)
        elif route == "delete":
            await self._quietly(method, scope["path"])
            await self.app(scope, receive, send)
        else:
            await self.app(scope, receive, send)

    async def _forward(self, method: str, path: str, query: bytes = b"", body: bytes = b"") -> httpx.Response:
        target = path + (f"?{query.decode()}" if query else "")
        return await self.client.request(method, target, content=body or None)

    async def _quietly(self, method: str, path: str, query: bytes = b"", body: bytes = b"") -> None:
        try:
            await self._forward(method, path, query, body)
        except httpx.HTTPError:
            pass

    async def _remote_or_local(self, scope: Scope, receive: Receive, send: Send, *, known: bool) -> None:
        body = await _read(receive) if scope["method"] in {"POST", "PUT"} else b""
        try:
            answer = await self._forward(scope["method"], scope["path"], scope["query_string"], body)
        except httpx.HTTPError:
            if known:
                await JSONResponse({"error": OFFLINE}, status_code=503)(scope, receive, send)
            else:
                await self.app(scope, _replay(body, receive), send)
            return
        if scope["path"].endswith("/ask") and answer.status_code == 200:
            self.remote_ids.add(str(answer.json().get("id", "")))
        await self._send(answer, scope, receive, send)

    async def _upload(self, scope: Scope, receive: Receive, send: Send) -> None:
        body = await _read(receive)
        name = parse_qs(scope["query_string"].decode()).get("name", [""])[0]
        if service.FORMATS.get(os.path.splitext(name)[1].lower()) in RASTER:  # noqa: PTH122 - a name, not a path
            await self._quietly("POST", scope["path"], scope["query_string"], body)
        await self.app(scope, _replay(body, receive), send)

    async def _open(self, scope: Scope, receive: Receive, send: Send) -> None:
        body = await _read(receive)
        try:
            ident = str(json.loads(body or b"{}").get("sample", ""))
        except ValueError:
            ident = ""
        sample = service._sample(ident)  # noqa: SLF001
        if sample is None or sample["format"] not in RASTER:
            await self.app(scope, _replay(body, receive), send)
            return
        try:
            answer = await self._forward("POST", scope["path"], body=body)
            if answer.status_code == 404 and "path" in sample:
                upload = service._path(sample).read_bytes()  # noqa: SLF001
                await self._forward("POST", "/documents/upload", f"name={sample['file']}".encode(), upload)
                answer = await self._forward("POST", scope["path"], body=body)
        except httpx.HTTPError:
            await JSONResponse({"error": OFFLINE}, status_code=503)(scope, receive, send)
            return
        if answer.status_code != 200:
            await self._send(answer, scope, receive, send)
            return
        document: dict[str, Any] = answer.json()
        self.remote_ids.add(str(document.get("id", "")))
        await JSONResponse(document | {"samples": service._listed()})(scope, receive, send)  # noqa: SLF001

    async def _send(self, answer: httpx.Response, scope: Scope, receive: Receive, send: Send) -> None:
        if answer.status_code >= 500:
            await JSONResponse({"error": OFFLINE}, status_code=503)(scope, receive, send)
            return
        headers = {k: v for k, v in answer.headers.items() if k.lower() in KEPT_HEADERS}
        await Response(answer.content, status_code=answer.status_code, headers=headers)(scope, receive, send)


def main() -> None:
    token = os.environ.get("DESK_TOKEN", "")
    url, remote_token = os.environ.get("DESK_REMOTE_URL", ""), os.environ.get("DESK_REMOTE_TOKEN", "")
    port = int(os.environ.get("DESK_PY_PORT", "4722"))
    if token:
        uvicorn.run(Guard(service.app, token), host="0.0.0.0", port=port, log_level="warning")  # noqa: S104 - the GPU reader is reached over the internet, with a token
    elif url and remote_token:
        uvicorn.run(Split(service.app, url, remote_token), host="127.0.0.1", port=port, log_level="warning")
    else:
        uvicorn.run(service.app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
