from klappstuhl.enums import ApiErrorCode
from klappstuhl.errors import (
    BadRequest,
    EntryAlreadyExists,
    Forbidden,
    HTTPError,
    NotFound,
    RateLimited,
    ServerError,
    Unauthorized,
    error_from_response,
)


def test_status_mapping():
    assert isinstance(error_from_response(400, "bad", None), BadRequest)
    assert isinstance(error_from_response(401, "no", None), Unauthorized)
    assert isinstance(error_from_response(403, "scope", None), Forbidden)
    assert isinstance(error_from_response(404, "gone", None), NotFound)
    assert isinstance(error_from_response(409, "dup", None), EntryAlreadyExists)
    assert isinstance(error_from_response(500, "boom", None), ServerError)
    assert isinstance(error_from_response(429, "slow", None), RateLimited)


def test_code_mapping_overrides_generic_status():
    # A 400 body carrying NO_PERMISSIONS should still surface as Forbidden.
    err = error_from_response(400, "nope", ApiErrorCode.NO_PERMISSIONS)
    assert isinstance(err, Forbidden)


def test_rate_limited_carries_retry_after():
    err = error_from_response(429, "slow down", ApiErrorCode.RATE_LIMITED, retry_after=1.5)
    assert isinstance(err, RateLimited)
    assert err.retry_after == 1.5


def test_http_error_message_format():
    err = HTTPError(418, "teapot", code=ApiErrorCode.BAD_REQUEST)
    assert "418" in str(err)
    assert "teapot" in str(err)
    assert err.status == 418
    assert err.code is ApiErrorCode.BAD_REQUEST


def test_unknown_code_degrades():
    assert ApiErrorCode(999) is ApiErrorCode.SERVER_ERROR
