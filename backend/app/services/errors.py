"""Provider error taxonomy (architecture.md 11).

External systems fail in ways that mean different things to a user: a bad token
is not a rate limit, and a rate limit is not a deleted repository. Collapsing
them into "sync failed" makes the difference invisible, so each is classified and
persisted with the sync job.
"""

from __future__ import annotations

from enum import Enum

import httpx


class ErrorCode(str, Enum):
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    NOT_FOUND = "NOT_FOUND"
    TIMEOUT = "TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"


class ConnectorError(Exception):
    """A provider failure classified into the taxonomy above."""

    def __init__(self, code: ErrorCode, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def classify_http_error(error: httpx.HTTPStatusError) -> ConnectorError:
    response = error.response
    status = response.status_code

    if status == 401:
        return ConnectorError(
            ErrorCode.AUTHENTICATION_ERROR,
            "GitHub rejected the credentials. Check GITHUB_TOKEN.",
        )
    if status == 403:
        # GitHub returns 403 both for genuine permission failures and for
        # exhausted rate limits; the remaining-quota header is what separates
        # them, and treating a rate limit as a permission error would send
        # someone to regenerate a perfectly good token.
        if response.headers.get("x-ratelimit-remaining") == "0":
            return ConnectorError(
                ErrorCode.RATE_LIMIT,
                "GitHub API rate limit exhausted. Try again after it resets.",
            )
        return ConnectorError(
            ErrorCode.AUTHORIZATION_ERROR,
            "The token lacks permission for this resource.",
        )
    if status == 404:
        return ConnectorError(
            ErrorCode.NOT_FOUND,
            "Repository not found, or the token cannot see it.",
        )
    if status == 429:
        return ConnectorError(ErrorCode.RATE_LIMIT, "GitHub asked us to slow down.")
    if status >= 500:
        return ConnectorError(
            ErrorCode.PROVIDER_ERROR, f"GitHub returned a server error ({status})."
        )
    return ConnectorError(
        ErrorCode.PROVIDER_ERROR, f"Unexpected GitHub response ({status})."
    )
