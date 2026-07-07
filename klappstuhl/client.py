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

from types import TracebackType
from typing import Any, Literal, cast, overload

import aiohttp

from .enums import Effect, ImageFormat, TranscodeFormat
from .file import File, FileInput, resolve_file
from .http import DEFAULT_BASE_URL, HTTPClient
from .models import (
    ApiVersions,
    DeleteResult,
    GuildImagesResult,
    ImageInfo,
    RateLimit,
    ScanReport,
    ShareResult,
    UploadResult,
)

__all__ = ("Client",)


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
        parts = [("file", resolve_file(f)) for f in files]
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

    # -- guild galleries -----------------------------------------------------

    async def upload_guild_images(
        self,
        guild_id: int | str,
        *files: FileInput,
        expires_in: int | None = None,
    ) -> UploadResult:
        """Upload images into a Discord guild's shared gallery.

        Requires the ``images:guild`` scope. Identical to :meth:`upload` but
        every row is tagged with ``guild_id`` so it appears in that guild's
        gallery.
        """
        if not files:
            raise ValueError("upload_guild_images() requires at least one file")
        parts = [("file", resolve_file(f)) for f in files]
        params = {"expires_in": expires_in} if expires_in is not None else None
        data = await self._http.request(
            "POST", f"/guilds/{guild_id}/images/upload", params=params, files=parts
        )
        return UploadResult.from_dict(data)

    async def list_guild_images(self, guild_id: int | str) -> GuildImagesResult:
        """List a guild's gallery, newest first. Requires ``images:guild``."""
        data = await self._http.request("GET", f"/guilds/{guild_id}/images")
        return GuildImagesResult.from_dict(data)

    async def delete_guild_image(self, guild_id: int | str, image_id: str) -> DeleteResult:
        """Delete an image from a guild's gallery. Requires ``images:guild``."""
        data = await self._http.request("DELETE", f"/guilds/{guild_id}/images/{_bare_id(image_id)}")
        return DeleteResult.from_dict(data)

    # -- scan ----------------------------------------------------------------

    async def scan(self, file: FileInput) -> ScanReport:
        """Scan a file for malware (ClamAV + VirusTotal). Requires ``images:read``.

        Any file type is accepted. Nothing is persisted and only the file's
        SHA-256 (never its contents) is sent to VirusTotal.
        """
        data = await self._http.request("POST", "/scan", files=[("file", resolve_file(file))])
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
        files, fields = _image_source(file, url)
        data = await self._http.request("POST", "/metadata", files=files, fields=fields)
        return ImageInfo.from_dict(data)

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
        files, fields = _image_source(file, url)
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
        files, fields = _image_source(file, url)
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
            files=[("file", resolve_file(file))], share=share,
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
        parts = [(name, resolve_file(f)) for name, f in files] if files else None
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


def _bare_id(image_id: str) -> str:
    """Strip a trailing extension from an image id (``abc.png`` -> ``abc``)."""
    return image_id.split("/")[-1].split(".")[0]


def _image_source(
    file: FileInput | None, url: str | None
) -> tuple[list[tuple[str, File]] | None, dict[str, str] | None]:
    """Build the multipart parts for endpoints that take a ``file`` OR a ``url``."""
    if (file is None) == (url is None):
        raise ValueError("provide exactly one of `file` or `url`")
    if file is not None:
        return [("file", resolve_file(file))], None
    return None, {"url": url or ""}
