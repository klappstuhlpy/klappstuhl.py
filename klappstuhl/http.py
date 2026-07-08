"""The low-level HTTP transport: auth, retries, and rate-limit handling.

:class:`HTTPClient` owns the :class:`aiohttp.ClientSession`, attaches the auth
header, retries transient failures with exponential backoff, transparently
waits out ``429`` rate limits, and translates error bodies into typed
exceptions from :mod:`klappstuhl.errors`.
"""

from __future__ import annotations

import asyncio
import json as _json
import random
from collections.abc import Mapping
from typing import Any

import aiohttp

from . import __version__
from .enums import ApiErrorCode
from .errors import TransportError, error_from_response
from .file import File
from .models import RateLimit

__all__ = ("HTTPClient",)

DEFAULT_BASE_URL = "https://klappstuhl.me"
_TRANSIENT_STATUSES = frozenset({500, 502, 503, 504})


class HTTPClient:
    """Manages the aiohttp session and every request to the API.

    Parameters
    ----------
    token:
        The API key, sent verbatim in the ``Authorization`` header.
    base_url:
        The site root (default ``https://klappstuhl.me``). The ``/api/v1``
        prefix is added per request.
    session:
        An existing :class:`aiohttp.ClientSession` to reuse. When omitted one
        is created lazily and owned by this client.
    timeout:
        Total per-request timeout in seconds.
    max_retries:
        How many times to retry a transient failure (network error, 5xx, or a
        rate limit) before giving up.
    user_agent:
        Overrides the default ``User-Agent`` header.
    """

    def __init__(
        self,
        token: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        session: aiohttp.ClientSession | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        user_agent: str | None = None,
    ) -> None:
        if not token:
            raise ValueError("an API token is required")
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.max_retries = max(0, int(max_retries))
        self.user_agent = user_agent or f"klappstuhl.py/{__version__} (+https://github.com/klappstuhlpy/klappstuhl.py)"
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session = session
        self._owns_session = session is None
        #: The rate-limit snapshot from the most recent response, if any.
        self.rate_limit: RateLimit | None = None
        #: The API version reported by the most recent response, if any.
        self.api_version: str | None = None

    # -- session lifecycle ---------------------------------------------------

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the underlying session if this client created it."""
        if self._session is not None and self._owns_session and not self._session.closed:
            await self._session.close()

    # -- request plumbing ----------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {"Authorization": self.token, "User-Agent": self.user_agent}

    @staticmethod
    def _build_form(
        files: list[tuple[str, File]] | None,
        fields: dict[str, str] | None,
    ) -> aiohttp.FormData:
        # Rebuilt on every attempt: an aiohttp payload can only be serialized
        # once, so a retry needs a fresh FormData.
        form = aiohttp.FormData(quote_fields=False)
        # aiohttp only emits a multipart/form-data body once a part carries a
        # filename or content type; a fields-only form would otherwise be sent
        # as application/x-www-form-urlencoded. The API's upload endpoints (and
        # the ``url`` alternative to a file, e.g. image manipulation/metadata)
        # are multipart-only, so tag text fields with a content type to force
        # multipart even when no file part is present.
        force_multipart = bool(fields) and not files
        for name, value in (fields or {}).items():
            if force_multipart:
                form.add_field(name, value, content_type="text/plain")
            else:
                form.add_field(name, value)
        for name, f in files or []:
            form.add_field(name, f.content, filename=f.filename, content_type=f.content_type)
        return form

    @staticmethod
    def _parse_error(status: int, body: bytes, headers: Mapping[str, str]) -> Exception:
        message = "request failed"
        code: ApiErrorCode | None = None
        try:
            payload = _json.loads(body.decode("utf-8"))
            if isinstance(payload, dict):
                message = str(payload.get("error", message))
                if "code" in payload and payload["code"] is not None:
                    code = ApiErrorCode(int(payload["code"]))
        except (ValueError, UnicodeDecodeError):
            text = body.decode("utf-8", "replace").strip()
            if text:
                message = text
        return error_from_response(status, message, code, retry_after=_reset_after(headers))

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        files: list[tuple[str, File]] | None = None,
        fields: dict[str, str] | None = None,
        expect: str = "json",
        versioned: bool = True,
    ) -> Any:
        """Perform a request and return its parsed body.

        ``expect`` selects the return type: ``"json"`` (decoded object),
        ``"bytes"`` (raw payload), ``"text"``, or ``"none"``.
        """

        session = await self._ensure_session()
        prefix = "/api/v1" if versioned else "/api"
        url = f"{self.base_url}{prefix}{path}"
        query = _clean_params(params)

        last_exc: BaseException | None = None
        for attempt in range(self.max_retries + 1):
            data = self._build_form(files, fields) if (files or fields) else None
            try:
                async with session.request(
                    method,
                    url,
                    params=query,
                    json=json_body,
                    data=data,
                    headers=self._headers(),
                ) as resp:
                    body = await resp.read()
                    self.rate_limit = RateLimit.from_headers(resp.headers)
                    self.api_version = resp.headers.get("x-api-version", self.api_version)

                    if resp.status == 429 and attempt < self.max_retries:
                        await asyncio.sleep(self._retry_after(resp.headers, attempt))
                        continue
                    if resp.status in _TRANSIENT_STATUSES and attempt < self.max_retries:
                        await asyncio.sleep(_backoff(attempt))
                        continue
                    if resp.status >= 400:
                        raise self._parse_error(resp.status, body, resp.headers)

                    return _decode(body, expect)
            except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as exc:
                # Network-level failure — retry with backoff, then surface as a
                # TransportError so callers can distinguish it from an HTTP error.
                last_exc = exc
                if attempt < self.max_retries:
                    await asyncio.sleep(_backoff(attempt))
                    continue
                raise TransportError(f"request to {url} failed after {attempt + 1} attempts", original=exc) from exc

        # Only reached if the final attempt was a retryable status.
        raise TransportError(
            f"request to {url} exhausted {self.max_retries + 1} attempts", original=last_exc
        )

    @staticmethod
    def _retry_after(headers: Mapping[str, str], attempt: int) -> float:
        reset = _reset_after(headers)
        if reset is not None:
            return max(0.0, reset) + random.uniform(0, 0.25)
        return _backoff(attempt)


def _clean_params(params: dict[str, Any] | None) -> dict[str, str] | None:
    if not params:
        return None
    out: dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            out[key] = "true" if value else "false"
        else:
            out[key] = str(value)
    return out or None


def _backoff(attempt: int) -> float:
    """Exponential backoff with jitter: ~0.5s, 1s, 2s, ... capped at 10s."""
    base = min(0.5 * (2.0 ** attempt), 10.0)
    return base + random.uniform(0, base / 2)


def _reset_after(headers: Mapping[str, str]) -> float | None:
    """Parse the ``x-ratelimit-reset-after`` header (seconds) if present."""
    raw = headers.get("x-ratelimit-reset-after")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _decode(body: bytes, expect: str) -> Any:
    if expect == "bytes":
        return body
    if expect == "text":
        return body.decode("utf-8")
    if expect == "none":
        return None
    if not body:
        return None
    return _json.loads(body.decode("utf-8"))
