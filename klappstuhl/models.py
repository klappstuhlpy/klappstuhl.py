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
    "ImageInfo",
    "ImageUpdate",
    "Me",
    "Palette",
    "PaletteColor",
    "Paste",
    "RateLimit",
    "ResourceUsage",
    "ScanReport",
    "ShareResult",
    "ShortLink",
    "Unfurl",
    "UploadResult",
    "Usage",
    "UsageSeries",
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
class ShortLink:
    """A short link (URL shortener entry)."""

    code: str
    short_url: str
    target_url: str
    clicks: int
    created_at: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ShortLink:
        return cls(
            code=str(data["code"]),
            short_url=str(data["short_url"]),
            target_url=str(data["target_url"]),
            clicks=int(data.get("clicks", 0)),
            created_at=str(data.get("created_at", "")),
        )


@dataclass(frozen=True)
class Paste:
    """A hosted text/code paste."""

    id: str
    url: str
    raw_url: str
    content: str
    views: int
    created_at: str
    language: str | None = None
    expires_at: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Paste:
        return cls(
            id=str(data["id"]),
            url=str(data["url"]),
            raw_url=str(data["raw_url"]),
            content=str(data.get("content", "")),
            views=int(data.get("views", 0)),
            created_at=str(data.get("created_at", "")),
            language=data.get("language"),
            expires_at=data.get("expires_at"),
        )


@dataclass(frozen=True)
class Unfurl:
    """Open Graph / link-preview metadata for a URL."""

    url: str
    title: str | None = None
    description: str | None = None
    image: str | None = None
    site_name: str | None = None
    favicon: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Unfurl:
        return cls(
            url=str(data.get("url", "")),
            title=data.get("title"),
            description=data.get("description"),
            image=data.get("image"),
            site_name=data.get("site_name"),
            favicon=data.get("favicon"),
        )


@dataclass(frozen=True)
class Me:
    """The calling account (from :meth:`Client.me`)."""

    id: int
    name: str
    admin: bool
    totp_enabled: bool
    discord_linked: bool
    #: The scopes granted to the key making the request. Values match
    #: :class:`~klappstuhl.Scope`; an empty list means a legacy full-access key.
    #: Kept as plain strings so a scope added server-side never breaks parsing.
    key_scopes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Me:
        return cls(
            id=int(data["id"]),
            name=str(data["name"]),
            admin=bool(data.get("admin", False)),
            totp_enabled=bool(data.get("totp_enabled", False)),
            discord_linked=bool(data.get("discord_linked", False)),
            key_scopes=[str(s) for s in data.get("key_scopes", []) or []],
        )


@dataclass(frozen=True)
class ResourceUsage:
    """Totals for one resource kind (images, links, or pastes)."""

    count: int
    #: Total stored bytes (images only; ``0`` elsewhere).
    bytes: int
    #: Aggregate views (images/pastes) or clicks (links).
    views: int

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ResourceUsage:
        return cls(
            count=int(data.get("count", 0)),
            bytes=int(data.get("bytes", 0)),
            views=int(data.get("views", 0)),
        )


@dataclass(frozen=True)
class UsageSeries:
    """A zero-filled per-day activity series, oldest first.

    Shaped to feed straight into :meth:`Client.render_chart`: use ``days`` as
    ``labels`` and ``uploads`` / ``upload_bytes`` as series data.
    """

    #: The day of each bucket (``YYYY-MM-DD``, UTC), oldest first.
    days: list[str] = field(default_factory=list)
    #: Images uploaded on each day.
    uploads: list[int] = field(default_factory=list)
    #: Bytes uploaded on each day.
    upload_bytes: list[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> UsageSeries:
        return cls(
            days=[str(d) for d in data.get("days", []) or []],
            uploads=[int(v) for v in data.get("uploads", []) or []],
            upload_bytes=[int(v) for v in data.get("upload_bytes", []) or []],
        )


@dataclass(frozen=True)
class Usage:
    """The account's usage snapshot (from :meth:`Client.usage`)."""

    images: ResourceUsage
    links: ResourceUsage
    pastes: ResourceUsage
    series: UsageSeries

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Usage:
        return cls(
            images=ResourceUsage.from_dict(data.get("images", {}) or {}),
            links=ResourceUsage.from_dict(data.get("links", {}) or {}),
            pastes=ResourceUsage.from_dict(data.get("pastes", {}) or {}),
            series=UsageSeries.from_dict(data.get("series", {}) or {}),
        )


@dataclass(frozen=True)
class PaletteColor:
    """One extracted dominant color."""

    #: ``#rrggbb`` hex string.
    hex: str
    #: The color as an ``(r, g, b)`` tuple.
    rgb: tuple[int, int, int]
    #: Share of sampled pixels this color covers (``0.0``–``1.0``).
    proportion: float

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PaletteColor:
        r, g, b = (int(c) for c in data.get("rgb", (0, 0, 0)))
        return cls(
            hex=str(data["hex"]),
            rgb=(r, g, b),
            proportion=float(data.get("proportion", 0.0)),
        )


@dataclass(frozen=True)
class Palette:
    """Dominant colors of an image (from :meth:`Client.color_palette`)."""

    #: The colors, most dominant first.
    colors: list[PaletteColor] = field(default_factory=list)
    #: How many pixels were sampled (transparent pixels are skipped).
    pixels_sampled: int = 0

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Palette:
        return cls(
            colors=[PaletteColor.from_dict(c) for c in data.get("colors", []) or []],
            pixels_sampled=int(data.get("pixels_sampled", 0)),
        )


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
