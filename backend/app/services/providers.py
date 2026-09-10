"""Which observability providers this deployment can actually read from.

Kept in one place so every surface answers the question identically. Demo mode
makes the synthetic reference scenarios (PRD 5) readable without pretending a
real provider is connected — ``is_demo`` exists so the UI can label the data.
"""

from app.connectors import pagerduty, prometheus
from app.core.config import settings


def runtime_available() -> bool:
    return prometheus.is_configured() or settings.demo_mode


def incidents_available() -> bool:
    return pagerduty.is_configured() or settings.demo_mode


def is_demo() -> bool:
    """True when observability data is synthetic rather than from a provider."""
    return settings.demo_mode and not (
        prometheus.is_configured() or pagerduty.is_configured()
    )
