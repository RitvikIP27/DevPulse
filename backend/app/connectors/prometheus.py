"""Prometheus runtime connector.

Per AGENTS.md 7 a connector only fetches and maps. It performs no correlation,
no scoring and no conflict analysis — those operate on the normalized rows this
writes.

Queries are configured rather than hard-coded, because no two organisations name
their metrics alike. A DevPulse deployment that has not configured Prometheus
reports runtime as NOT_CONFIGURED; it never substitutes a default.
"""

from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.events import Repository, RuntimeObservation
from app.services.errors import ConnectorError, ErrorCode, classify_http_error
from app.services.timestamps import utc_now

logger = get_logger(__name__)

PROVIDER = "prometheus"

#: metric name -> PromQL. Overridable per deployment via settings.
DEFAULT_QUERIES = {
    "error_rate_pct": (
        'sum(rate(http_requests_total{status=~"5.."}[5m])) '
        '/ sum(rate(http_requests_total[5m])) * 100'
    ),
    "latency_p95_ms": (
        'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) '
        'by (le)) * 1000'
    ),
}


def is_configured() -> bool:
    return bool(settings.prometheus_url)


def _query_range(
    client: httpx.Client, query: str, start_epoch: float, end_epoch: float, step_seconds: int
) -> list[tuple[float, float]]:
    try:
        response = client.get(
            f"{settings.prometheus_url.rstrip('/')}/api/v1/query_range",
            params={"query": query, "start": start_epoch, "end": end_epoch, "step": step_seconds},
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        raise classify_http_error(error) from error
    except httpx.TimeoutException as error:
        raise ConnectorError(ErrorCode.TIMEOUT, "Prometheus timed out.") from error
    except httpx.HTTPError as error:
        raise ConnectorError(ErrorCode.PROVIDER_ERROR, str(error)) from error

    payload = response.json()
    if payload.get("status") != "success":
        raise ConnectorError(
            ErrorCode.PROVIDER_ERROR, f"Prometheus rejected the query: {payload.get('error')}"
        )

    samples: list[tuple[float, float]] = []
    for series in payload.get("data", {}).get("result", []):
        for timestamp, raw_value in series.get("values", []):
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                continue
            # Prometheus returns NaN as a string for empty windows; a NaN is an
            # absence of data, not a measurement of zero.
            if value != value:
                continue
            samples.append((float(timestamp), value))
    return samples


def sync_runtime_observations(
    db: Session, repo: Repository, lookback_hours: int = 24, step_seconds: int = 300
) -> int:
    """Ingest runtime samples for one repository. Returns rows written."""
    if not is_configured():
        return 0

    end = utc_now()
    start_epoch = (end.timestamp() - lookback_hours * 3600)
    end_epoch = end.timestamp()

    written = 0
    with httpx.Client(timeout=30.0) as client:
        for metric, query in DEFAULT_QUERIES.items():
            for timestamp, value in _query_range(client, query, start_epoch, end_epoch, step_seconds):
                observed_at = __import__("datetime").datetime.utcfromtimestamp(timestamp)
                exists = (
                    db.query(RuntimeObservation)
                    .filter_by(
                        repository_id=repo.id, provider=PROVIDER,
                        metric=metric, observed_at=observed_at,
                    )
                    .first()
                )
                if exists:
                    exists.value = value
                    continue
                db.add(
                    RuntimeObservation(
                        repository_id=repo.id, provider=PROVIDER,
                        environment="production", metric=metric,
                        value=value, observed_at=observed_at,
                    )
                )
                written += 1
        db.commit()

    logger.info("prometheus sync repository=%s observations=%d", repo.full_name, written)
    return written
