"""Typed response models.

Every model is a frozen dataclass with a ``from_dict`` constructor that reads
the exact JSON shape returned by the API. Unknown keys are ignored so a
server-side additive change never breaks deserialization.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .enums import UpdateState

__all__ = (
    "ApiVersions",
    "DeleteResult",
    "GuildImageInfo",
    "GuildImagesResult",
    "ImageInfo",
    "ImageUpdate",
    "RateLimit",
    "ScanReport",
    "ShareResult",
    "UploadResult",
    "VersionInfo",
)


@dataclass(frozen=True)
class RateLimit:
    """A snapshot of the rate-limit headers on the most recent response."""

    limit: int | None = None
    remaining: int | None = None
    reset: float | None = None
    reset_after: float | None = None

    @classmethod
    def from_headers(cls, headers: Mapping[str, str]) -> RateLimit | None:
        def num(key: str) -> float | None:
            raw = headers.get(key)
            if raw is None:
                return None
            try:
                return float(raw)
            except ValueError:
                return None

        limit = num("x-ratelimit-limit")
        remaining = num("x-ratelimit-remaining")
        reset = num("x-ratelimit-reset")
        reset_after = num("x-ratelimit-reset-after")
        if limit is None and remaining is None and reset is None and reset_after is None:
            return None
        return cls(
            limit=int(limit) if limit is not None else None,
            remaining=int(remaining) if remaining is not None else None,
            reset=reset,
            reset_after=reset_after,
        )


@dataclass(frozen=True)
class UploadResult:
    """The outcome of an upload of one or more images."""

    total: int
    errors: int
    skipped: int
    infected: int
    links: list[str]
    raw_links: list[str]

    @property
    def successful(self) -> int:
        """Number of files that uploaded cleanly."""
        return max(self.total - self.errors - self.infected, 0)

    @property
    def is_success(self) -> bool:
        """``True`` when every attempted file uploaded without error/skip."""
        return self.total > 0 and self.errors == 0 and self.skipped == 0 and self.infected == 0

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> UploadResult:
        return cls(
            total=int(data.get("total", 0)),
            errors=int(data.get("errors", 0)),
            skipped=int(data.get("skipped", 0)),
            infected=int(data.get("infected", 0)),
            links=list(data.get("links", []) or []),
            raw_links=list(data.get("raw_links", []) or []),
        )


@dataclass(frozen=True)
class DeleteResult:
    """The outcome of deleting a single image."""

    file: str
    failed: bool

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DeleteResult:
        return cls(file=str(data.get("file", "")), failed=bool(data.get("failed", False)))


@dataclass(frozen=True)
class ImageInfo:
    """Metadata about a decoded image (from :meth:`Client.metadata`)."""

    width: int
    height: int
    format: str
    color: str
    file_size: int

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ImageInfo:
        return cls(
            width=int(data["width"]),
            height=int(data["height"]),
            format=str(data["format"]),
            color=str(data["color"]),
            file_size=int(data["file_size"]),
        )


@dataclass(frozen=True)
class ShareResult:
    """A stored, shareable result (returned when ``share=True``)."""

    id: str
    url: str
    content_type: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ShareResult:
        return cls(
            id=str(data["id"]),
            url=str(data["url"]),
            content_type=str(data["content_type"]),
        )


@dataclass(frozen=True)
class ScanReport:
    """The combined ClamAV + VirusTotal verdict for a scanned file."""

    sha256: str
    file_size: int
    verdict: str
    clamav_clean: bool | None = None
    clamav_virus: str | None = None
    vt_status: str | None = None
    vt_positives: int | None = None
    vt_total: int | None = None
    vt_url: str | None = None

    @property
    def is_infected(self) -> bool:
        return self.verdict == "infected"

    @property
    def is_clean(self) -> bool:
        return self.verdict == "clean"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ScanReport:
        return cls(
            sha256=str(data["sha256"]),
            file_size=int(data["file_size"]),
            verdict=str(data.get("verdict", "unknown")),
            clamav_clean=data.get("clamav_clean"),
            clamav_virus=data.get("clamav_virus"),
            vt_status=data.get("vt_status"),
            vt_positives=data.get("vt_positives"),
            vt_total=data.get("vt_total"),
            vt_url=data.get("vt_url"),
        )


@dataclass(frozen=True)
class GuildImageInfo:
    """A single image in a Discord guild's shared gallery."""

    id: str
    ext: str
    mimetype: str
    size: int
    uploaded_at: str
    url: str
    raw_url: str
    original_name: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> GuildImageInfo:
        return cls(
            id=str(data["id"]),
            ext=str(data["ext"]),
            mimetype=str(data["mimetype"]),
            size=int(data["size"]),
            uploaded_at=str(data["uploaded_at"]),
            url=str(data["url"]),
            raw_url=str(data["raw_url"]),
            original_name=data.get("original_name"),
        )


@dataclass(frozen=True)
class GuildImagesResult:
    """A listing of a guild's gallery."""

    images: list[GuildImageInfo]
    total: int

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> GuildImagesResult:
        images = [GuildImageInfo.from_dict(i) for i in data.get("images", []) or []]
        return cls(images=images, total=int(data.get("total", len(images))))


@dataclass(frozen=True)
class ImageUpdate:
    """Container image-update status for one service (admin scope)."""

    service: str
    image: str
    state: UpdateState
    checked_at: int
    current_digest: str | None = None
    latest_digest: str | None = None
    error: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ImageUpdate:
        return cls(
            service=str(data["service"]),
            image=str(data["image"]),
            state=UpdateState(data.get("state", "unknown")),
            checked_at=int(data.get("checked_at", 0)),
            current_digest=data.get("current_digest"),
            latest_digest=data.get("latest_digest"),
            error=data.get("error"),
        )


@dataclass(frozen=True)
class VersionInfo:
    """One advertised API version from the discovery document."""

    version: str
    status: str
    base_path: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> VersionInfo:
        return cls(
            version=str(data["version"]),
            status=str(data["status"]),
            base_path=str(data["base_path"]),
        )


@dataclass(frozen=True)
class ApiVersions:
    """The ``GET /api`` version-discovery document."""

    current: str
    versions: list[VersionInfo] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ApiVersions:
        return cls(
            current=str(data["current"]),
            versions=[VersionInfo.from_dict(v) for v in data.get("versions", []) or []],
        )
