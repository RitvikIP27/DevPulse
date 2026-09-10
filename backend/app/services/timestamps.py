"""Timestamp normalization at the provider boundary (rules.md 4).

Every external timestamp is parsed as timezone-aware, converted to UTC, and
stored as a naive UTC datetime. The database columns are ``TIMESTAMP WITHOUT
TIME ZONE``, so a consistent representation has to be enforced in code: mixing
aware and naive values is what produces comparisons that raise at runtime or,
worse, silently compare local time against UTC.

The MVP used ``datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")``, which produced
naive datetimes and raised outright on any offset form or fractional seconds
that GitHub is entitled to return.
"""

from __future__ import annotations

from datetime import datetime, timezone


def parse_utc(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp into naive UTC. Returns None if unparseable.

    Accepts the ``Z`` suffix, explicit offsets and fractional seconds. A value
    that cannot be parsed yields None rather than an exception, because one
    malformed field should not abort an entire sync.
    """
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        # A provider that omits an offset is documenting UTC by convention.
        return parsed
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def utc_now() -> datetime:
    """Current time in the same representation used for stored timestamps."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
