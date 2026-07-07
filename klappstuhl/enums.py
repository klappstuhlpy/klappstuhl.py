"""Enumerations mirroring the constants used by the klappstuhl.me API."""

from __future__ import annotations

from enum import Enum, IntEnum

__all__ = (
    "ApiErrorCode",
    "Effect",
    "ImageFormat",
    "Scope",
    "TranscodeFormat",
    "UpdateState",
)


class ApiErrorCode(IntEnum):
    """The machine-readable ``code`` returned in every API error body.

    A client can branch on this instead of parsing the human-readable
    ``error`` string. Each value maps to a dedicated exception subclass
    (see :mod:`klappstuhl.errors`).
    """

    SERVER_ERROR = 0
    BAD_REQUEST = 1
    #: Deprecated internal code — do not rely on it.
    USERNAME_REGISTERED = 2
    #: Deprecated internal code — do not rely on it.
    INCORRECT_LOGIN = 3
    NO_PERMISSIONS = 4
    ENTRY_ALREADY_EXISTS = 5
    NOT_FOUND = 6
    UNAUTHORIZED = 7
    RATE_LIMITED = 8

    @classmethod
    def _missing_(cls, value: object) -> ApiErrorCode:
        # Forward-compatible: unknown numeric codes degrade to SERVER_ERROR
        # rather than raising, so a new server-side code never crashes a client.
        return cls.SERVER_ERROR


class Scope(str, Enum):
    """API-key permission scopes.

    A key with *no* scopes is treated by the server as legacy / unrestricted
    (full access). Otherwise every endpoint requires a specific scope; calling
    it without that scope raises :class:`~klappstuhl.errors.Forbidden`.
    """

    IMAGES_READ = "images:read"
    IMAGES_WRITE = "images:write"
    GUILD_IMAGES = "images:guild"
    ADMIN_READ = "admin:read"
    ADMIN_WRITE = "admin:write"

    def __str__(self) -> str:
        return self.value


class Effect(str, Enum):
    """Visual effects accepted by :meth:`Client.manipulate`."""

    BLUR = "blur"
    PIXELATE = "pixelate"
    DEEPFRY = "deepfry"
    INVERT = "invert"
    GRAYSCALE = "grayscale"

    def __str__(self) -> str:
        return self.value


class ImageFormat(str, Enum):
    """Target raster formats accepted by :meth:`Client.convert`."""

    PNG = "png"
    JPEG = "jpeg"
    JPG = "jpg"
    WEBP = "webp"
    GIF = "gif"
    BMP = "bmp"
    TIFF = "tiff"

    def __str__(self) -> str:
        return self.value


class TranscodeFormat(str, Enum):
    """Target formats accepted by :meth:`Client.transcode` (ffmpeg-backed)."""

    MP4 = "mp4"
    JPG = "jpg"

    def __str__(self) -> str:
        return self.value


class UpdateState(str, Enum):
    """Container image-update state, as returned by the admin ``/admin/updates`` route.

    That route is admin-only and has no typed client method; reach it via
    :meth:`Client.request` and parse the payload with :class:`ImageUpdate`.
    """

    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"
    UNKNOWN = "unknown"

    @classmethod
    def _missing_(cls, value: object) -> UpdateState:
        return cls.UNKNOWN

    def __str__(self) -> str:
        return self.value
