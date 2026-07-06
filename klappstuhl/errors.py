"""Exception hierarchy for the klappstuhl.me wrapper.

Every failed request raises a subclass of :class:`KlappstuhlError`. HTTP errors
carry the parsed ``error`` message and machine-readable
:class:`~klappstuhl.enums.ApiErrorCode`, and are dispatched to the most specific
subclass via :func:`error_from_response`.
"""

from __future__ import annotations

from .enums import ApiErrorCode

__all__ = (
    "BadRequest",
    "EntryAlreadyExists",
    "Forbidden",
    "HTTPError",
    "KlappstuhlError",
    "NotFound",
    "RateLimited",
    "ServerError",
    "TransportError",
    "Unauthorized",
    "error_from_response",
)


class KlappstuhlError(Exception):
    """Base class for every exception raised by this library."""


class TransportError(KlappstuhlError):
    """A network-level failure (connection reset, DNS, timeout) that survived
    all configured retries. Wraps the underlying :class:`Exception`."""

    def __init__(self, message: str, *, original: BaseException | None = None) -> None:
        super().__init__(message)
        self.original = original


class HTTPError(KlappstuhlError):
    """Raised when the API returns a non-2xx response.

    Attributes
    ----------
    status:
        The HTTP status code.
    message:
        The human-readable ``error`` field from the response body (or the raw
        body / reason phrase when it was not a structured error).
    code:
        The :class:`~klappstuhl.enums.ApiErrorCode` from the response body, if
        present.
    """

    def __init__(
        self,
        status: int,
        message: str,
        *,
        code: ApiErrorCode | None = None,
    ) -> None:
        self.status = status
        self.message = message
        self.code = code
        suffix = f" (code {int(code)})" if code is not None else ""
        super().__init__(f"HTTP {status}: {message}{suffix}")


class BadRequest(HTTPError):
    """400 — the request was malformed or the input was invalid."""


class Unauthorized(HTTPError):
    """401 — the API key was missing or invalid."""


class Forbidden(HTTPError):
    """403 — the API key is valid but lacks the required scope."""


class NotFound(HTTPError):
    """404 — the requested resource does not exist."""


class EntryAlreadyExists(HTTPError):
    """409 — the resource already exists."""


class RateLimited(HTTPError):
    """429 — the IP-level rate limit was exceeded.

    ``retry_after`` is the number of seconds to wait before retrying, taken
    from the ``x-ratelimit-reset-after`` header when available. This is only
    raised once the client's own automatic retries are exhausted.
    """

    def __init__(
        self,
        status: int,
        message: str,
        *,
        code: ApiErrorCode | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(status, message, code=code)
        self.retry_after = retry_after


class ServerError(HTTPError):
    """5xx — the server failed to process an otherwise valid request.

    Also raised for feature endpoints (screenshot, markdown-pdf, transcode)
    when the required external tool (Chromium / ffmpeg) is not installed on the
    server.
    """


def error_from_response(
    status: int,
    message: str,
    code: ApiErrorCode | None,
    *,
    retry_after: float | None = None,
) -> HTTPError:
    """Map a status code / error code to the most specific :class:`HTTPError`."""

    if status == 429 or code is ApiErrorCode.RATE_LIMITED:
        return RateLimited(status, message, code=code, retry_after=retry_after)
    if status == 401 or code is ApiErrorCode.UNAUTHORIZED:
        return Unauthorized(status, message, code=code)
    if status == 403 or code is ApiErrorCode.NO_PERMISSIONS:
        return Forbidden(status, message, code=code)
    if status == 404 or code is ApiErrorCode.NOT_FOUND:
        return NotFound(status, message, code=code)
    if status == 409 or code is ApiErrorCode.ENTRY_ALREADY_EXISTS:
        return EntryAlreadyExists(status, message, code=code)
    if status >= 500 or code is ApiErrorCode.SERVER_ERROR:
        return ServerError(status, message, code=code)
    if status == 400 or code is ApiErrorCode.BAD_REQUEST:
        return BadRequest(status, message, code=code)
    return HTTPError(status, message, code=code)
