"""klappstuhl.py — a fast, fully-typed async wrapper for the klappstuhl.me API.

Example
-------
::

    import asyncio
    import klappstuhl

    async def main():
        async with klappstuhl.Client("my-api-key") as client:
            result = await client.upload("cat.png")
            print("uploaded:", result.links[0])

            png = await client.blur("cat.png", amount=12)
            open("blurred.png", "wb").write(png)

    asyncio.run(main())
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    #: The installed package version — single-sourced from the distribution
    #: metadata (see ``version`` in ``pyproject.toml``).
    __version__ = _pkg_version("klappstuhl")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0+unknown"

__author__ = "klappstuhlpy"
__license__ = "MIT"

from .client import ChartPoint, Client
from .enums import (
    ApiErrorCode,
    ChartKind,
    ChartTheme,
    Effect,
    ImageFormat,
    Scope,
    TranscodeFormat,
    UpdateState,
)
from .errors import (
    BadRequest,
    EntryAlreadyExists,
    Forbidden,
    HTTPError,
    KlappstuhlError,
    NotFound,
    RateLimited,
    ServerError,
    TransportError,
    Unauthorized,
)
from .file import File, FileInput
from .models import (
    ApiVersions,
    DeleteResult,
    ImageInfo,
    ImageUpdate,
    Me,
    Palette,
    PaletteColor,
    Paste,
    RateLimit,
    ResourceUsage,
    ScanReport,
    ShareResult,
    ShortLink,
    Unfurl,
    UploadResult,
    Usage,
    UsageSeries,
    VersionInfo,
)

__all__ = (
    # enums
    "ApiErrorCode",
    "ApiVersions",
    "BadRequest",
    "ChartKind",
    "ChartPoint",
    "ChartTheme",
    "Client",
    "DeleteResult",
    "Effect",
    "EntryAlreadyExists",
    "File",
    "FileInput",
    "Forbidden",
    "HTTPError",
    "ImageFormat",
    "ImageInfo",
    "ImageUpdate",
    # errors
    "KlappstuhlError",
    "Me",
    "NotFound",
    "Palette",
    "PaletteColor",
    "Paste",
    # models
    "RateLimit",
    "RateLimited",
    "ResourceUsage",
    "ScanReport",
    "Scope",
    "ServerError",
    "ShareResult",
    "ShortLink",
    "TranscodeFormat",
    "TransportError",
    "Unauthorized",
    "Unfurl",
    "UpdateState",
    "UploadResult",
    "Usage",
    "UsageSeries",
    "VersionInfo",
    "__version__",
)
