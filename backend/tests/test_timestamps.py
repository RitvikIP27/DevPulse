"""Timestamp normalization at the provider boundary."""

from datetime import datetime

import pytest

from app.services.timestamps import parse_utc


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2026-07-09T20:31:46Z", datetime(2026, 7, 9, 20, 31, 46)),
        ("2026-07-09T20:31:46+00:00", datetime(2026, 7, 9, 20, 31, 46)),
        # Offsets must be converted, not truncated: 22:31+02:00 is 20:31 UTC.
        ("2026-07-09T22:31:46+02:00", datetime(2026, 7, 9, 20, 31, 46)),
        ("2026-07-09T20:31:46.123456Z", datetime(2026, 7, 9, 20, 31, 46, 123456)),
        # No offset means UTC by provider convention.
        ("2026-07-09T20:31:46", datetime(2026, 7, 9, 20, 31, 46)),
    ],
)
def test_supported_timestamp_forms_normalise_to_naive_utc(value, expected):
    parsed = parse_utc(value)
    assert parsed == expected
    assert parsed.tzinfo is None, "stored timestamps must be naive UTC"


@pytest.mark.parametrize("value", [None, "", "not-a-timestamp", "2026-13-45T99:99:99Z"])
def test_unparseable_values_return_none_rather_than_raising(value):
    """One malformed field must not abort an entire sync."""
    assert parse_utc(value) is None


def test_offset_form_would_have_crashed_the_mvp_parser():
    """Regression guard for audit finding 14.

    The MVP used strptime with a literal Z, which raised on any offset form.
    """
    with pytest.raises(ValueError):
        datetime.strptime("2026-07-09T22:31:46+02:00", "%Y-%m-%dT%H:%M:%SZ")

    assert parse_utc("2026-07-09T22:31:46+02:00") is not None
