"""GitHub webhook signature verification.

A webhook endpoint is a URL on the public internet that anyone can POST to.
Without verification, anybody could invent deployments, pull requests and
incidents — every metric in DevPulse would become forgeable.

GitHub signs each delivery with HMAC-SHA256 over the raw body using a shared
secret. Recomputing that signature proves the payload came from GitHub and was
not altered in transit.
"""

from __future__ import annotations

import hashlib
import hmac

SIGNATURE_HEADER = "X-Hub-Signature-256"
SIGNATURE_PREFIX = "sha256="


def is_valid_signature(raw_body: bytes, signature_header: str | None, secret: str) -> bool:
    """Verify a GitHub webhook signature.

    Comparison uses `hmac.compare_digest`, which takes the same amount of time
    whether the first byte differs or the last. A normal `==` returns early on
    the first mismatch, and that timing difference is enough to let an attacker
    recover a valid signature byte by byte.
    """
    if not secret or not signature_header:
        return False
    if not signature_header.startswith(SIGNATURE_PREFIX):
        return False

    expected = hmac.new(
        secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256
    ).hexdigest()
    provided = signature_header[len(SIGNATURE_PREFIX):]

    return hmac.compare_digest(expected, provided)
