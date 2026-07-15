"""Enumerations mirroring the constants used by the klappstuhl.me API."""

from __future__ import annotations

from enum import Enum, IntEnum

__all__ = (
    "ApiErrorCode",
    "ChartKind",
    "ChartTheme",
    "Effect",
    "ImageFormat",
    "Scope",
    "TranscodeFormat",
    "UpdateState",
    "Visibility",
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
    #: Request body failed validation; see the error's ``errors`` field map.
    VALIDATION = 9
    #: The request payload exceeded the maximum accepted size.
    PAYLOAD_TOO_LARGE = 10
    #: The request's media type is not supported for this endpoint.
    UNSUPPORTED_MEDIA = 11

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

    :attr:`IMAGES_READ` and :attr:`IMAGES_WRITE` are user-grantable on the account
    page. :attr:`GUILD_IMAGES` and the two ``ADMIN_*`` scopes are **privileged**:
    the server does not grant them to a personal key. ``images:guild`` keys are
    minted per Discord guild by the operator's service (e.g. Percy's bot), and
    ``admin:*`` is reserved for the operator — reach admin routes with
    :meth:`Client.request`.
    """

    IMAGES_READ = "images:read"
    IMAGES_WRITE = "images:write"
    LINKS_READ = "links:read"
    LINKS_WRITE = "links:write"
    PASTES_READ = "pastes:read"
    PASTES_WRITE = "pastes:write"
    # Privileged — not grantable to a personal key (see the class docstring).
    GUILD_IMAGES = "images:guild"
    ADMIN_READ = "admin:read"
    ADMIN_WRITE = "admin:write"

    @property
    def is_privileged(self) -> bool:
        """Whether the server refuses to grant this scope to a personal key.

        Privileged scopes exist so responses that *mention* scopes (error
        bodies, ``GET /me`` ``key_scopes``) can always be interpreted — they do
        not imply the endpoints behind them are callable through this client.
        """
        return self in (Scope.GUILD_IMAGES, Scope.ADMIN_READ, Scope.ADMIN_WRITE)

    def __str__(self) -> str:
        return self.value


class Visibility(str, Enum):
    """Who can find a paste.

    ``PUBLIC`` pastes are indexable and listed on your ``/user/<name>`` profile;
    ``UNLISTED`` (the default) and ``PRIVATE`` are link-only. Accepted by
    :meth:`Client.create_paste` and :meth:`Client.update_paste`.
    """

    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"

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


class ChartKind(str, Enum):
    """Chart forms accepted by :meth:`Client.render_chart`.

    Pick by the data's job: :attr:`LINE`/:attr:`AREA` for change over time,
    :attr:`BAR` for magnitude comparison, :attr:`SCATTER` for correlation,
    :attr:`PIE`/:attr:`DONUT` for a part-to-whole split (single series,
    at most 7 slices).
    """

    LINE = "line"
    AREA = "area"
    BAR = "bar"
    SCATTER = "scatter"
    PIE = "pie"
    DONUT = "donut"

    def __str__(self) -> str:
        return self.value


class ChartTheme(str, Enum):
    """Color themes accepted by :meth:`Client.render_chart`.

    ``DARK`` (the server default) matches the site; ``LIGHT`` uses a palette
    stepped for a light surface. Both are colorblind-validated.
    """

    DARK = "dark"
    LIGHT = "light"

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
