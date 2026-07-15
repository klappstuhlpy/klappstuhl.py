"""The high-level async client.

:class:`Client` is the single entry point. Construct it with an API key and
call a method per endpoint; each returns a typed model from
:mod:`klappstuhl.models` (or raw ``bytes`` for binary results). Use it as an
async context manager so the underlying session is always cleaned up::

    async with klappstuhl.Client("my-api-key") as client:
        result = await client.upload("cat.png")
        print(result.links[0])
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import TracebackType
from typing import Any, Literal, Union, cast, overload

import aiohttp

from .enums import ChartKind, ChartTheme, Effect, ImageFormat, TranscodeFormat, Visibility
from .file import File, FileInput, resolve_file
from .http import DEFAULT_BASE_URL, HTTPClient
from .models import (
    ApiVersions,
    DeleteResult,
    ImageInfo,
    Me,
    Palette,
    Paste,
    PasteRevision,
    RateLimit,
    ScanReport,
    ShareResult,
    ShortLink,
    Unfurl,
    UploadResult,
    Usage,
)

__all__ = ("Client",)

#: One chart data point: a bare y-value, or an ``(x, y)`` pair (line/area/scatter only).
ChartPoint = Union[float, "tuple[float, float]"]


class Client:
    """An asynchronous client for the klappstuhl.me API.

    Parameters
    ----------
    token:
        Your API key (generate one at https://klappstuhl.me/account). Sent
        verbatim as the ``Authorization`` header.
    base_url:
        The site root. Defaults to ``https://klappstuhl.me``; override it to
        target a self-hosted instance.
    session:
        Reuse an existing :class:`aiohttp.ClientSession` instead of letting the
        client own one.
    timeout:
        Per-request timeout in seconds (default ``30``).
    max_retries:
        Retries for transient failures — network errors, ``5xx`` responses, and
        ``429`` rate limits (which are waited out using the reset header).
        Default ``3``.
    user_agent:
        Override the default ``User-Agent``.
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
        self._http = HTTPClient(
            token,
            base_url=base_url,
            session=session,
            timeout=timeout,
            max_retries=max_retries,
            user_agent=user_agent,
        )

    # -- lifecycle -----------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP session (if owned by this client)."""
        await self._http.close()

    async def __aenter__(self) -> Client:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    @property
    def rate_limit(self) -> RateLimit | None:
        """The rate-limit headers from the most recent response, if any."""
        return self._http.rate_limit

    @property
    def api_version(self) -> str | None:
        """The API version (``X-API-Version``) of the most recent response."""
        return self._http.api_version

    # -- discovery -----------------------------------------------------------

    async def versions(self) -> ApiVersions:
        """Return the ``GET /api`` version-discovery document.

        This is the one unauthenticated endpoint; it needs no scope.
        """
        data = await self._http.request("GET", "", expect="json", versioned=False)
        return ApiVersions.from_dict(data)

    # -- account -------------------------------------------------------------

    async def me(self) -> Me:
        """Return the account behind this API key, plus the key's scopes.

        Works with **any** valid key — no specific scope required. Useful for
        "connected as …" UI and for debugging which scopes a key actually holds
        (an empty ``key_scopes`` list means a legacy full-access key).
        """
        data = await self._http.request("GET", "/me")
        return Me.from_dict(data)

    async def usage(self) -> Usage:
        """Return the account's usage snapshot. No specific scope required.

        Includes image/link/paste totals and a zero-filled 30-day upload
        series (:class:`~klappstuhl.UsageSeries`) whose shape drops straight
        into :meth:`render_chart`::

            usage = await client.usage()
            svg = await client.render_chart(
                "line",
                {"uploads": usage.series.uploads},
                labels=usage.series.days,
                title="Uploads, last 30 days",
            )
        """
        data = await self._http.request("GET", "/me/usage")
        return Usage.from_dict(data)

    # -- images (upload / delete / download) ---------------------------------

    async def upload(
        self,
        *files: FileInput,
        expires_in: int | None = None,
    ) -> UploadResult:
        """Upload one or more images. Requires the ``images:write`` scope.

        Accepted types: ``.apng``, ``.png``, ``.jpg``, ``.jpeg``, ``.gif``,
        ``.avif``. Each argument may be a path, ``bytes``, an open binary file,
        or a :class:`~klappstuhl.File`.

        Parameters
        ----------
        *files:
            The images to upload (at least one).
        expires_in:
            Optional time-to-live in seconds; the upload auto-deletes after it
            (capped server-side at 365 days). Omit for a permanent upload.
        """
        if not files:
            raise ValueError("upload() requires at least one file")
        parts = [("file", await resolve_file(f)) for f in files]
        params = {"expires_in": expires_in} if expires_in is not None else None
        data = await self._http.request("POST", "/images/upload", params=params, files=parts)
        return UploadResult.from_dict(data)

    async def delete_image(self, image_id: str) -> DeleteResult:
        """Delete one of your images by id. Requires ``images:write``.

        The ``image_id`` may include the extension (``abc123.png``) or be bare.
        You must be the uploader.
        """
        data = await self._http.request("DELETE", f"/images/{_bare_id(image_id)}")
        return DeleteResult.from_dict(data)

    async def download(self, files: list[str] | None = None) -> bytes:
        """Bundle images into a ZIP archive (bytes). Requires ``images:read``.

        Parameters
        ----------
        files:
            Image IDs to include (extension optional). Pass ``None`` or an empty
            list to download **every** image you own. Unknown/foreign IDs are
            silently skipped; if none resolve, a
            :class:`~klappstuhl.errors.NotFound` is raised.
        """
        payload = {"files": list(files or [])}
        data = await self._http.request("POST", "/images/download", json_body=payload, expect="bytes")
        return cast(bytes, data)

    # -- short links ---------------------------------------------------------

    async def shorten(self, url: str, *, code: str | None = None) -> ShortLink:
        """Create a short link. Requires the ``links:write`` scope.

        Parameters
        ----------
        url:
            The destination URL. A missing scheme defaults to ``https://``.
        code:
            An optional custom alias (``[A-Za-z0-9_-]``, ≤64 chars). Omit for a
            random code. Raises :class:`~klappstuhl.errors.HTTPError` (409) if the
            alias is already taken.
        """
        body: dict[str, Any] = {"url": url}
        if code is not None:
            body["code"] = code
        data = await self._http.request("POST", "/links", json_body=body)
        return ShortLink.from_dict(data)

    async def list_links(
        self,
        *,
        limit: int | None = None,
        before: str | None = None,
        after: str | None = None,
    ) -> list[ShortLink]:
        """List your short links, newest first. Requires ``links:read``.

        Supports cursor pagination via ``limit`` (1–200) and ``before``/``after``
        (a link ``code`` cursor).
        """
        params = _page_params(limit, before, after)
        data = await self._http.request("GET", "/links", params=params)
        return [ShortLink.from_dict(x) for x in data or []]

    async def get_link(self, code: str) -> ShortLink:
        """Fetch one of your short links by code. Requires ``links:read``."""
        data = await self._http.request("GET", f"/links/{code}")
        return ShortLink.from_dict(data)

    async def update_link(self, code: str, url: str) -> ShortLink:
        """Repoint a short link at a new destination. Requires ``links:write``.

        The code stays the same, so anything already sharing the short URL
        keeps working. A missing scheme in ``url`` defaults to ``https://``.
        Returns the updated link.
        """
        data = await self._http.request("PATCH", f"/links/{code}", json_body={"url": url})
        return ShortLink.from_dict(data)

    async def delete_link(self, code: str) -> ShortLink:
        """Delete one of your short links by code. Requires ``links:write``.

        Returns the deleted link.
        """
        data = await self._http.request("DELETE", f"/links/{code}")
        return ShortLink.from_dict(data)

    # -- pastes --------------------------------------------------------------

    async def create_paste(
        self,
        content: str,
        *,
        title: str | None = None,
        language: str | None = None,
        visibility: Visibility | str | None = None,
        burn_after_read: bool = False,
        password: str | None = None,
        expires_in: int | None = None,
        confirm_secrets: bool = False,
    ) -> Paste:
        """Create a hosted paste. Requires the ``pastes:write`` scope.

        Parameters
        ----------
        content:
            The paste body (≤512 KB).
        title:
            Optional title, shown on the ``/p/<id>`` view.
        language:
            Optional syntect language token / extension (``rust``, ``py`` …) used
            to pick a highlighter. Omit for server-side auto-detection.
        visibility:
            :class:`~klappstuhl.Visibility` (or the equivalent string):
            ``public``, ``unlisted`` (the default) or ``private``.
        burn_after_read:
            Destroy the paste the first time it is explicitly revealed.
        password:
            Encrypt the body with this password (Argon2id + ChaCha20-Poly1305).
            It is never stored — lose it and the paste is unreadable.
        expires_in:
            Optional time-to-live in seconds (capped at 365 days). Omit for a
            permanent paste.
        confirm_secrets:
            Publish even though the body trips the secret scanner (otherwise a
            detected credential is rejected with ``400``).
        """
        body: dict[str, Any] = {"content": content}
        if title is not None:
            body["title"] = title
        if language is not None:
            body["language"] = language
        if visibility is not None:
            body["visibility"] = str(visibility)
        if burn_after_read:
            body["burn_after_read"] = True
        if password is not None:
            body["password"] = password
        if expires_in is not None:
            body["expires_in"] = expires_in
        if confirm_secrets:
            body["confirm_secrets"] = True
        data = await self._http.request("POST", "/pastes", json_body=body)
        return Paste.from_dict(data)

    async def list_pastes(
        self,
        *,
        limit: int | None = None,
        before: str | None = None,
        after: str | None = None,
    ) -> list[Paste]:
        """List your pastes, newest first. Requires ``pastes:read``.

        Supports cursor pagination via ``limit`` (1–200) and ``before``/``after``
        (a paste ``id`` cursor).
        """
        params = _page_params(limit, before, after)
        data = await self._http.request("GET", "/pastes", params=params)
        return [Paste.from_dict(x) for x in data or []]

    async def get_paste(self, paste_id: str, *, password: str | None = None) -> Paste:
        """Fetch one of your pastes by id. Requires ``pastes:read``.

        Pass ``password`` to decrypt a password-protected paste; without it the
        returned :attr:`Paste.content` is empty. The body of a burn-after-read
        paste is never returned here — reveal it in a browser.
        """
        params = {"password": password} if password is not None else None
        data = await self._http.request("GET", f"/pastes/{paste_id}", params=params)
        return Paste.from_dict(data)

    async def update_paste(
        self,
        paste_id: str,
        content: str,
        *,
        title: str | None = None,
        language: str | None = None,
        visibility: Visibility | str | None = None,
        expires_in: int | None = None,
        password: str | None = None,
        confirm_secrets: bool = False,
    ) -> Paste:
        """Edit one of your pastes. Requires ``pastes:write``.

        The previous body is snapshotted into the paste's revision history. Only
        the fields you pass change; ``expires_in`` is the exception — omit it and
        the paste becomes permanent. ``password`` is **required** when the paste
        is encrypted (the new body is re-sealed under the same password).
        """
        body: dict[str, Any] = {"content": content}
        if title is not None:
            body["title"] = title
        if language is not None:
            body["language"] = language
        if visibility is not None:
            body["visibility"] = str(visibility)
        if expires_in is not None:
            body["expires_in"] = expires_in
        if password is not None:
            body["password"] = password
        if confirm_secrets:
            body["confirm_secrets"] = True
        data = await self._http.request("PATCH", f"/pastes/{paste_id}", json_body=body)
        return Paste.from_dict(data)

    async def fork_paste(self, paste_id: str, *, password: str | None = None) -> Paste:
        """Copy any paste into a fresh one you own. Requires ``pastes:write``.

        Not limited to your own pastes. The fork is independent and inherits
        neither the source's password nor its burn flag. Pass ``password`` to
        fork an encrypted source; a burn-after-read source cannot be forked (that
        would be a read dodging the burn).
        """
        params = {"password": password} if password is not None else None
        data = await self._http.request("POST", f"/pastes/{paste_id}/fork", params=params)
        return Paste.from_dict(data)

    async def list_paste_revisions(self, paste_id: str) -> list[PasteRevision]:
        """List a paste's superseded versions, newest first. Requires ``pastes:read``.

        Capped at the last 20 revisions. An encrypted paste's history is not
        readable and raises :class:`~klappstuhl.errors.NotFound`.
        """
        data = await self._http.request("GET", f"/pastes/{paste_id}/revisions")
        return [PasteRevision.from_dict(x) for x in data or []]

    async def delete_paste(self, paste_id: str) -> Paste:
        """Delete one of your pastes by id. Requires ``pastes:write``.

        Returns the deleted paste.
        """
        data = await self._http.request("DELETE", f"/pastes/{paste_id}")
        return Paste.from_dict(data)

    # -- qr ------------------------------------------------------------------

    async def render_qr(
        self,
        data: str,
        *,
        size: int | None = None,
        format: Literal["svg", "png"] = "svg",
        ecc: Literal["low", "medium", "quartile", "high"] | None = None,
        margin: bool | None = None,
    ) -> bytes:
        """Render ``data`` as a QR code. Requires the ``images:read`` scope.

        Returns the image bytes — an SVG (``format="svg"``, the default) or a PNG
        (``format="png"``).

        Parameters
        ----------
        data:
            The text or URL to encode (≤4 KB).
        size:
            Target pixel size (64–2048; default 512).
        format:
            ``"svg"`` (default) or ``"png"``.
        ecc:
            Error-correction level: ``low``/``medium``/``quartile``/``high``.
        margin:
            Whether to include the surrounding quiet-zone margin (default on).
        """
        body: dict[str, Any] = {"data": data, "format": format}
        if size is not None:
            body["size"] = size
        if ecc is not None:
            body["ecc"] = ecc
        if margin is not None:
            body["margin"] = margin
        result = await self._http.request("POST", "/render/qr", json_body=body, expect="bytes")
        return cast(bytes, result)

    # -- web -----------------------------------------------------------------

    async def unfurl(self, url: str) -> Unfurl:
        """Unfurl a URL into Open Graph / link-preview metadata.

        Requires the ``images:read`` scope. The target is fetched SSRF-guarded
        (private/reserved addresses are refused).
        """
        data = await self._http.request("GET", "/unfurl", params={"url": url})
        return Unfurl.from_dict(data)

    # -- scan ----------------------------------------------------------------

    async def scan(self, file: FileInput) -> ScanReport:
        """Scan a file for malware (ClamAV + VirusTotal). Requires ``images:read``.

        Any file type is accepted. Nothing is persisted and only the file's
        SHA-256 (never its contents) is sent to VirusTotal.
        """
        data = await self._http.request("POST", "/scan", files=[("file", await resolve_file(file))])
        return ScanReport.from_dict(data)

    # -- media (metadata / manipulate / convert) -----------------------------

    async def metadata(
        self,
        file: FileInput | None = None,
        *,
        url: str | None = None,
    ) -> ImageInfo:
        """Inspect an image's dimensions/format without storing it.

        Requires ``images:read``. Supply exactly one of ``file`` or ``url``
        (a public http(s) image the server fetches; private/reserved addresses
        are refused).
        """
        files, fields = await _image_source(file, url)
        data = await self._http.request("POST", "/metadata", files=files, fields=fields)
        return ImageInfo.from_dict(data)

    async def color_palette(
        self,
        file: FileInput | None = None,
        *,
        url: str | None = None,
        count: int | None = None,
    ) -> Palette:
        """Extract an image's dominant colors. Requires ``images:read``.

        Returns a :class:`~klappstuhl.Palette` with the colors ordered by
        coverage — handy for theming, accent-color picks, or Discord embed
        colors.

        Parameters
        ----------
        file / url:
            The source image (exactly one).
        count:
            How many colors to return (1–12, default 6).
        """
        files, fields = await _image_source(file, url)
        params = {"count": count} if count is not None else None
        data = await self._http.request("POST", "/color/palette", params=params, files=files, fields=fields)
        return Palette.from_dict(data)

    @overload
    async def manipulate(
        self,
        op: Effect | str,
        file: FileInput | None = ...,
        *,
        url: str | None = ...,
        amount: float | None = ...,
        share: Literal[False] = ...,
    ) -> bytes: ...

    @overload
    async def manipulate(
        self,
        op: Effect | str,
        file: FileInput | None = ...,
        *,
        url: str | None = ...,
        amount: float | None = ...,
        share: Literal[True],
    ) -> ShareResult: ...

    async def manipulate(
        self,
        op: Effect | str,
        file: FileInput | None = None,
        *,
        url: str | None = None,
        amount: float | None = None,
        share: bool = False,
    ) -> bytes | ShareResult:
        """Apply a visual effect and get a PNG back. Requires ``images:read``.

        Parameters
        ----------
        op:
            One of ``blur``, ``pixelate``, ``deepfry``, ``invert``,
            ``grayscale`` (see :class:`~klappstuhl.Effect`).
        file / url:
            The source image (exactly one).
        amount:
            Effect strength — ``blur`` sigma (default 8), ``pixelate`` block
            size (default 16), ``deepfry`` intensity 1–100 (default 50).
            Ignored by ``invert`` and ``grayscale``.
        share:
            When ``True``, store the result and return a :class:`ShareResult`
            with a short ``/m/<id>`` link instead of the raw PNG bytes.
        """
        return await self._manipulate(op, file, url=url, amount=amount, share=share)

    async def _manipulate(
        self,
        op: Effect | str,
        file: FileInput | None,
        *,
        url: str | None,
        amount: float | None,
        share: bool,
    ) -> bytes | ShareResult:
        # Non-overloaded worker shared by ``manipulate`` and the per-effect
        # convenience wrappers, so callers never trip the overload resolution.
        files, fields = await _image_source(file, url)
        params: dict[str, Any] = {"amount": amount, "share": share}
        op_name = op.value if isinstance(op, Effect) else op
        return await self._binary_or_share(
            "POST", f"/image/{op_name}", params=params, files=files, fields=fields, share=share,
        )

    # convenience wrappers for each effect
    async def blur(self, file: FileInput | None = None, *, url: str | None = None,
                   amount: float | None = None, share: bool = False) -> bytes | ShareResult:
        """Gaussian blur. See :meth:`manipulate`."""
        return await self._manipulate(Effect.BLUR, file, url=url, amount=amount, share=share)

    async def pixelate(self, file: FileInput | None = None, *, url: str | None = None,
                       amount: float | None = None, share: bool = False) -> bytes | ShareResult:
        """Mosaic/pixelate effect. See :meth:`manipulate`."""
        return await self._manipulate(Effect.PIXELATE, file, url=url, amount=amount, share=share)

    async def deepfry(self, file: FileInput | None = None, *, url: str | None = None,
                      amount: float | None = None, share: bool = False) -> bytes | ShareResult:
        """The crunchy "deep-fried" meme look. See :meth:`manipulate`."""
        return await self._manipulate(Effect.DEEPFRY, file, url=url, amount=amount, share=share)

    async def invert(self, file: FileInput | None = None, *, url: str | None = None,
                     share: bool = False) -> bytes | ShareResult:
        """Invert all colours. See :meth:`manipulate`."""
        return await self._manipulate(Effect.INVERT, file, url=url, amount=None, share=share)

    async def grayscale(self, file: FileInput | None = None, *, url: str | None = None,
                        share: bool = False) -> bytes | ShareResult:
        """Desaturate to gray. See :meth:`manipulate`."""
        return await self._manipulate(Effect.GRAYSCALE, file, url=url, amount=None, share=share)

    @overload
    async def convert(self, to: ImageFormat | str, file: FileInput | None = ..., *,
                      url: str | None = ..., quality: int | None = ...,
                      share: Literal[False] = ...) -> bytes: ...

    @overload
    async def convert(self, to: ImageFormat | str, file: FileInput | None = ..., *,
                      url: str | None = ..., quality: int | None = ...,
                      share: Literal[True]) -> ShareResult: ...

    async def convert(
        self,
        to: ImageFormat | str,
        file: FileInput | None = None,
        *,
        url: str | None = None,
        quality: int | None = None,
        share: bool = False,
    ) -> bytes | ShareResult:
        """Transcode an image to another raster format. Requires ``images:read``.

        Parameters
        ----------
        to:
            Target format: ``png``, ``jpeg`` (alias ``jpg``), ``webp``, ``gif``,
            ``bmp``, ``tiff`` (see :class:`~klappstuhl.ImageFormat`).
        file / url:
            The source image (exactly one).
        quality:
            JPEG quality 1–100 (default 85). Only used when ``to`` is jpeg.
        share:
            Return a :class:`ShareResult` link instead of raw bytes.
        """
        files, fields = await _image_source(file, url)
        params: dict[str, Any] = {
            "to": str(to),
            "quality": quality,
            "share": share,
        }
        return await self._binary_or_share(
            "POST", "/convert", params=params, files=files, fields=fields, share=share
        )

    # -- render (code / screenshot / markdown-pdf) ---------------------------

    @overload
    async def render_code(self, code: str, *, language: str | None = ..., theme: str | None = ...,
                          share: Literal[False] = ...) -> bytes: ...

    @overload
    async def render_code(self, code: str, *, language: str | None = ..., theme: str | None = ...,
                          share: Literal[True]) -> ShareResult: ...

    async def render_code(
        self,
        code: str,
        *,
        language: str | None = None,
        theme: str | None = None,
        share: bool = False,
    ) -> bytes | ShareResult:
        """Render syntax-highlighted code to an SVG. Requires ``images:read``.

        Returns the SVG as ``bytes`` (``image/svg+xml``), or a
        :class:`ShareResult` when ``share=True``. Source is capped at 100 KB.

        Parameters
        ----------
        code:
            The source code to render.
        language:
            Language token or extension (e.g. ``rust``, ``py``, ``js``). Falls
            back to plain text when omitted/unknown.
        theme:
            A syntect theme name (e.g. ``base16-ocean.dark``, ``InspiredGitHub``,
            ``Solarized (dark)``).
        """
        body: dict[str, Any] = {"code": code}
        if language is not None:
            body["language"] = language
        if theme is not None:
            body["theme"] = theme
        return await self._binary_or_share(
            "POST", "/render/code", params={"share": share}, json_body=body, share=share
        )

    @overload
    async def render_chart(self, kind: ChartKind | str, series: Mapping[str, Sequence[ChartPoint]], *,
                           labels: Sequence[str] | None = ..., title: str | None = ...,
                           theme: ChartTheme | str | None = ..., width: int | None = ...,
                           height: int | None = ..., x_label: str | None = ..., y_label: str | None = ...,
                           share: Literal[False] = ...) -> bytes: ...

    @overload
    async def render_chart(self, kind: ChartKind | str, series: Mapping[str, Sequence[ChartPoint]], *,
                           labels: Sequence[str] | None = ..., title: str | None = ...,
                           theme: ChartTheme | str | None = ..., width: int | None = ...,
                           height: int | None = ..., x_label: str | None = ..., y_label: str | None = ...,
                           share: Literal[True]) -> ShareResult: ...

    async def render_chart(
        self,
        kind: ChartKind | str,
        series: Mapping[str, Sequence[ChartPoint]],
        *,
        labels: Sequence[str] | None = None,
        title: str | None = None,
        theme: ChartTheme | str | None = None,
        width: int | None = None,
        height: int | None = None,
        x_label: str | None = None,
        y_label: str | None = None,
        share: bool = False,
    ) -> bytes | ShareResult:
        """Render a chart to an SVG server-side. Requires ``images:read``.

        No client-side charting library needed — the server draws the chart
        with colorblind-validated palettes and returns ``image/svg+xml`` bytes
        (or a :class:`ShareResult` when ``share=True``).

        Parameters
        ----------
        kind:
            The chart form: ``line``, ``area``, ``bar``, ``scatter``, ``pie``,
            or ``donut`` (see :class:`~klappstuhl.ChartKind`). Pie/donut take
            exactly one series with at most 7 non-negative values.
        series:
            Series name → data points, in plot order (at most 7 series). Points
            are numbers (``[3, 1, 4]``; x is the index / matching label) or
            ``(x, y)`` pairs — pairs only for line, area, and scatter.
        labels:
            Category labels along the x-axis, or the slice labels for
            pie/donut.
        title:
            Optional title drawn above the plot (≤120 chars).
        theme:
            ``dark`` (server default) or ``light``
            (see :class:`~klappstuhl.ChartTheme`).
        width / height:
            Image size in px (clamped server-side to 320–1600 × 240–1000;
            defaults 860×480).
        x_label / y_label:
            Optional axis captions.
        share:
            Return a :class:`ShareResult` with a short ``/m/<id>`` link instead
            of the raw SVG bytes.

        Example
        -------
        ::

            svg = await client.render_chart(
                "line",
                {"api": [120, 180, 90], "web": [80, 90, 130]},
                labels=["Mon", "Tue", "Wed"],
                title="Requests per day",
            )
        """
        body: dict[str, Any] = {
            "kind": str(kind),
            "series": [
                {"label": name, "data": [list(p) if isinstance(p, tuple) else p for p in points]}
                for name, points in series.items()
            ],
        }
        if labels is not None:
            body["labels"] = list(labels)
        if title is not None:
            body["title"] = title
        if theme is not None:
            body["theme"] = str(theme)
        if width is not None:
            body["width"] = width
        if height is not None:
            body["height"] = height
        if x_label is not None:
            body["x_label"] = x_label
        if y_label is not None:
            body["y_label"] = y_label
        return await self._binary_or_share(
            "POST", "/render/chart", params={"share": share}, json_body=body, share=share
        )

    @overload
    async def screenshot(self, url: str, *, width: int | None = ..., height: int | None = ...,
                         dark_mode: bool = ..., mobile: bool = ..., full_page: bool = ...,
                         share: Literal[False] = ...) -> bytes: ...

    @overload
    async def screenshot(self, url: str, *, width: int | None = ..., height: int | None = ...,
                         dark_mode: bool = ..., mobile: bool = ..., full_page: bool = ...,
                         share: Literal[True]) -> ShareResult: ...

    async def screenshot(
        self,
        url: str,
        *,
        width: int | None = None,
        height: int | None = None,
        dark_mode: bool = False,
        mobile: bool = False,
        full_page: bool = False,
        share: bool = False,
    ) -> bytes | ShareResult:
        """Render a web page to a PNG via headless Chromium. Requires ``images:read``.

        Raises :class:`~klappstuhl.errors.ServerError` if the server has no
        Chromium binary. Private/reserved URLs are refused.

        Parameters
        ----------
        url:
            Public http(s) page to capture.
        width / height:
            Viewport size in pixels (defaults 1280×800).
        dark_mode / mobile / full_page:
            Emulate dark mode, a mobile viewport, or capture a tall full page.
        share:
            Return a :class:`ShareResult` link instead of raw bytes.
        """
        body: dict[str, Any] = {
            "url": url,
            "dark_mode": dark_mode,
            "mobile": mobile,
            "full_page": full_page,
        }
        if width is not None:
            body["width"] = width
        if height is not None:
            body["height"] = height
        return await self._binary_or_share(
            "POST", "/render/screenshot", params={"share": share}, json_body=body, share=share
        )

    @overload
    async def markdown_pdf(self, markdown: str, *, share: Literal[False] = ...) -> bytes: ...

    @overload
    async def markdown_pdf(self, markdown: str, *, share: Literal[True]) -> ShareResult: ...

    async def markdown_pdf(self, markdown: str, *, share: bool = False) -> bytes | ShareResult:
        """Render Markdown to a PDF via headless Chromium. Requires ``images:read``.

        Raises :class:`~klappstuhl.errors.ServerError` if Chromium is absent.
        """
        return await self._binary_or_share(
            "POST", "/render/markdown-pdf", params={"share": share},
            json_body={"markdown": markdown}, share=share,
        )

    @overload
    async def transcode(self, file: FileInput, *, to: TranscodeFormat | str,
                        share: Literal[False] = ...) -> bytes: ...

    @overload
    async def transcode(self, file: FileInput, *, to: TranscodeFormat | str,
                        share: Literal[True]) -> ShareResult: ...

    async def transcode(
        self,
        file: FileInput,
        *,
        to: TranscodeFormat | str,
        share: bool = False,
    ) -> bytes | ShareResult:
        """Transcode media via ffmpeg (MOV→MP4 or HEIC→JPG). Requires ``images:read``.

        Raises :class:`~klappstuhl.errors.ServerError` if ffmpeg is absent.

        Parameters
        ----------
        file:
            The source media file.
        to:
            ``mp4`` or ``jpg`` (see :class:`~klappstuhl.TranscodeFormat`).
        share:
            Return a :class:`ShareResult` link instead of raw bytes.
        """
        return await self._binary_or_share(
            "POST", "/convert/transcode", params={"to": str(to), "share": share},
            files=[("file", await resolve_file(file))], share=share,
        )

    # -- raw / escape hatch --------------------------------------------------

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        files: list[tuple[str, FileInput]] | None = None,
        fields: dict[str, str] | None = None,
        expect: Literal["json", "bytes", "text", "none"] = "json",
        versioned: bool = True,
    ) -> Any:
        """Send a raw, hand-crafted request to the API — an escape hatch.

        The typed methods above cover every endpoint intended for general use.
        This low-level method exists for endpoints deliberately left out of the
        public surface (for example the ``admin:*`` routes, which only privileged
        keys may call) or for anything added server-side after this release. It
        goes through the same auth, retry, and rate-limit machinery as every
        other call, but returns the *unwrapped* response — you parse it yourself.

        Parameters
        ----------
        method:
            HTTP verb (``"GET"``, ``"POST"``, ``"DELETE"`` …).
        path:
            Path **below** the version prefix, with a leading slash, e.g.
            ``"/admin/updates"``. The ``/api/v1`` prefix is added for you (pass
            ``versioned=False`` to hit the un-versioned ``/api`` root instead).
        params:
            Query-string parameters. ``None`` values are dropped; ``bool`` values
            become ``"true"``/``"false"``.
        json:
            A JSON body (mutually exclusive with ``files``/``fields``).
        files:
            Multipart file parts as ``(field_name, file)`` tuples, where ``file``
            is anything :class:`~klappstuhl.File` accepts (path, bytes, stream…).
        fields:
            Extra multipart text fields to send alongside ``files``.
        expect:
            How to decode the response: ``"json"`` (default), ``"bytes"``,
            ``"text"``, or ``"none"``.
        versioned:
            Whether to prepend ``/api/v1`` (default) or the legacy ``/api`` root.

        Returns
        -------
        The decoded body: a parsed object for ``"json"``, ``bytes``, ``str``, or
        ``None`` — never a :mod:`klappstuhl.models` wrapper.

        Examples
        --------
        Call an admin-only endpoint with a privileged key::

            data = await client.request("GET", "/admin/updates")
        """
        parts = [(name, await resolve_file(f)) for name, f in files] if files else None
        return await self._http.request(
            method,
            path,
            params=params,
            json_body=json,
            files=parts,
            fields=fields,
            expect=expect,
            versioned=versioned,
        )

    # -- internal helpers ----------------------------------------------------

    async def _binary_or_share(
        self,
        method: str,
        path: str,
        *,
        share: bool,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        files: list[Any] | None = None,
        fields: dict[str, str] | None = None,
    ) -> bytes | ShareResult:
        # Endpoints that return raw bytes unless ``share=true`` flips them to a
        # small JSON ``ShareResult``. We branch on the same flag we sent.
        result = await self._http.request(
            method, path, params=params, json_body=json_body,
            files=files, fields=fields, expect="json" if share else "bytes",
        )
        if share:
            return ShareResult.from_dict(result)
        return cast(bytes, result)


def _page_params(limit: int | None, before: str | None, after: str | None) -> dict[str, Any] | None:
    """Build cursor-pagination query params, dropping the unset ones."""
    params = {"limit": limit, "before": before, "after": after}
    params = {k: v for k, v in params.items() if v is not None}
    return params or None


def _bare_id(image_id: str) -> str:
    """Strip a trailing extension from an image id (``abc.png`` -> ``abc``)."""
    return image_id.split("/")[-1].split(".")[0]


async def _image_source(
    file: FileInput | None, url: str | None
) -> tuple[list[tuple[str, File]] | None, dict[str, str] | None]:
    """Build the multipart parts for endpoints that take a ``file`` OR a ``url``."""
    if (file is None) == (url is None):
        raise ValueError("provide exactly one of `file` or `url`")
    if file is not None:
        return [("file", await resolve_file(file))], None
    return None, {"url": url or ""}
