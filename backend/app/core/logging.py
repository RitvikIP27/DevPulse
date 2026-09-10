"""Logging configuration for DevPulse.

Ingestion runs in the background, where a swallowed exception is invisible unless
something writes it down. The MVP used bare ``print()``, which never reached the
container logs at all because stdout was buffered. Everything now logs through
the standard library so that operations are attributable to a provider, a
resource and an outcome (rules.md 17).
"""

import logging
import sys

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def configure_logging(level: int = logging.INFO) -> None:
    """Install a single stderr handler. Idempotent, so repeated calls are safe."""
    root = logging.getLogger()
    root.setLevel(level)

    already_configured = any(
        getattr(handler, "_devpulse_handler", False) for handler in root.handlers
    )
    if already_configured:
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    handler._devpulse_handler = True  # type: ignore[attr-defined]
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
