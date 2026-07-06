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

__version__ = "0.1.0"
__author__ = "klappstuhlpy"
__license__ = "MIT"

from .client import Client
from .enums import (
    ApiErrorCode,
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
    GuildImageInfo,
    GuildImagesResult,
    ImageInfo,
    ImageUpdate,
    RateLimit,
    ScanReport,
    ShareResult,
    UploadResult,
    VersionInfo,
)

__all__ = (
    # enums
    "ApiErrorCode",
    "ApiVersions",
    "BadRequest",
    "Client",
    "DeleteResult",
    "Effect",
    "EntryAlreadyExists",
    "File",
    "FileInput",
    "Forbidden",
    "GuildImageInfo",
    "GuildImagesResult",
    "HTTPError",
    "ImageFormat",
    "ImageInfo",
    "ImageUpdate",
    # errors
    "KlappstuhlError",
    "NotFound",
    # models
    "RateLimit",
    "RateLimited",
    "ScanReport",
    "Scope",
    "ServerError",
    "ShareResult",
    "TranscodeFormat",
    "TransportError",
    "Unauthorized",
    "UpdateState",
    "UploadResult",
    "VersionInfo",
    "__version__",
)
