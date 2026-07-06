"""Shared test fixtures.

Instead of mocking aiohttp internals (brittle across versions), the client
tests run against a *real* local aiohttp server on an ephemeral port. This
exercises the full request/response stack — auth header, query params,
multipart bodies, status handling — for real.
"""

from __future__ import annotations

import json as _json
from typing import Any

import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestServer

import klappstuhl


class MockServer:
    """A tiny programmable HTTP server.

    Queue responses per ``(method, path)`` with :meth:`add`; each request is
    recorded in :attr:`requests` for assertions. When several responses are
    queued for one route they are consumed in order (the last one repeats),
    which lets a test model "429 then 200".
    """

    def __init__(self) -> None:
        self.responses: dict[tuple[str, str], list[tuple[int, bytes, dict[str, str], str]]] = {}
        self.requests: list[dict[str, Any]] = []
        self.base_url: str = ""

    def add(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        body: bytes | None = None,
        status: int = 200,
        headers: dict[str, str] | None = None,
        content_type: str = "application/json",
    ) -> None:
        if json is not None:
            payload = _json.dumps(json).encode()
        elif body is not None:
            payload = body
        else:
            payload = b""
        self.responses.setdefault((method.upper(), path), []).append(
            (status, payload, headers or {}, content_type)
        )

    async def _handle(self, request: web.Request) -> web.Response:
        raw = await request.read()
        self.requests.append(
            {
                "method": request.method,
                "path": request.path,
                "query": dict(request.query),
                "headers": dict(request.headers),
                "body": raw,
            }
        )
        queue = self.responses.get((request.method, request.path))
        if not queue:
            return web.Response(
                status=404,
                body=_json.dumps({"error": "no mock registered", "code": 6}).encode(),
                content_type="application/json",
            )
        status, payload, headers, content_type = queue.pop(0) if len(queue) > 1 else queue[0]
        return web.Response(status=status, body=payload, headers=headers, content_type=content_type)

    def last_request(self) -> dict[str, Any]:
        return self.requests[-1]


@pytest_asyncio.fixture
async def server():
    mock = MockServer()
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", mock._handle)
    test_server = TestServer(app)
    await test_server.start_server()
    mock.base_url = f"http://127.0.0.1:{test_server.port}"
    try:
        yield mock
    finally:
        await test_server.close()


@pytest_asyncio.fixture
async def client(server: MockServer):
    async with klappstuhl.Client("test-token", base_url=server.base_url) as c:
        yield c
