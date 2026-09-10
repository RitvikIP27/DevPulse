"""PagerDuty incident connector.

Fetches incidents and maps them onto DevPulse rows. Association with a
repository is by configured service id, never inferred from timing.
"""

from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.events import Incident, Repository
from app.services.errors import ConnectorError, ErrorCode, classify_http_error
from app.services.timestamps import parse_utc

logger = get_logger(__name__)

PROVIDER = "pagerduty"
API = "https://api.pagerduty.com"

_STATUS_MAP = {
    "triggered": "TRIGGERED",
    "acknowledged": "ACKNOWLEDGED",
    "resolved": "RESOLVED",
}


def is_configured() -> bool:
    return bool(settings.pagerduty_token and settings.pagerduty_service_ids)


def sync_incidents(db: Session, repo: Repository, limit: int = 100) -> int:
    """Ingest incidents for the configured services. Returns rows written."""
    if not is_configured():
        return 0

    headers = {
        "Authorization": f"Token token={settings.pagerduty_token}",
        "Accept": "application/vnd.pagerduty+json;version=2",
    }

    written = 0
    with httpx.Client(timeout=30.0, headers=headers) as client:
        try:
            response = client.get(
                f"{API}/incidents",
                params={
                    "service_ids[]": settings.pagerduty_service_id_list,
                    "limit": min(limit, 100),
                    "sort_by": "created_at:desc",
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise classify_http_error(error) from error
        except httpx.TimeoutException as error:
            raise ConnectorError(ErrorCode.TIMEOUT, "PagerDuty timed out.") from error

        for incident in response.json().get("incidents", []):
            started_at = parse_utc(incident.get("created_at"))
            if started_at is None:
                continue

            values = {
                "title": incident.get("title"),
                "severity": (incident.get("priority") or {}).get("summary"),
                "status": _STATUS_MAP.get(incident.get("status", ""), "TRIGGERED"),
                "started_at": started_at,
                "resolved_at": parse_utc(incident.get("resolved_at")),
                "url": incident.get("html_url"),
            }
            existing = (
                db.query(Incident)
                .filter_by(repository_id=repo.id, provider=PROVIDER, external_id=str(incident["id"]))
                .first()
            )
            if existing:
                for field, value in values.items():
                    setattr(existing, field, value)
            else:
                db.add(
                    Incident(
                        repository_id=repo.id, provider=PROVIDER,
                        external_id=str(incident["id"]), **values,
                    )
                )
                written += 1
        db.commit()

    logger.info("pagerduty sync repository=%s incidents=%d", repo.full_name, written)
    return written
