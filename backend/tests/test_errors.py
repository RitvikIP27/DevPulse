"""Provider error classification (architecture.md 11)."""

import httpx
import pytest

from app.services.errors import ErrorCode, classify_http_error


def _http_error(status: int, headers: dict[str, str] | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.github.com/repos/o/r/pulls")
    response = httpx.Response(status, headers=headers or {}, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


@pytest.mark.parametrize(
    "status,expected",
    [
        (401, ErrorCode.AUTHENTICATION_ERROR),
        (404, ErrorCode.NOT_FOUND),
        (429, ErrorCode.RATE_LIMIT),
        (500, ErrorCode.PROVIDER_ERROR),
        (502, ErrorCode.PROVIDER_ERROR),
    ],
)
def test_status_codes_map_to_the_taxonomy(status, expected):
    assert classify_http_error(_http_error(status)).code is expected


def test_403_with_exhausted_quota_is_a_rate_limit_not_a_permission_problem():
    """GitHub reuses 403 for both. Misclassifying sends someone to rotate a
    perfectly good token instead of waiting for the quota to reset."""
    error = classify_http_error(_http_error(403, {"x-ratelimit-remaining": "0"}))
    assert error.code is ErrorCode.RATE_LIMIT


def test_403_with_quota_remaining_is_a_permission_problem():
    error = classify_http_error(_http_error(403, {"x-ratelimit-remaining": "4321"}))
    assert error.code is ErrorCode.AUTHORIZATION_ERROR


def test_every_classified_error_carries_an_actionable_message():
    for status in (401, 403, 404, 429, 500):
        assert classify_http_error(_http_error(status)).message
