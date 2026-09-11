"""Webhook ingestion (PRD 3.5, Stage 22).

Webhooks give DevPulse near-real-time data without polling. They do not replace
backfill: a webhook only ever tells you about events that happen *after* it is
configured, so historical synchronisation remains the only way to learn about
the past. The two are complementary, and the product needs both.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.events import Repository, WebhookEvent
from app.services.timestamps import parse_utc, utc_now

logger = get_logger(__name__)

PROVIDER = "github"


class WebhookStatus:
    RECEIVED = "RECEIVED"
    PROCESSED = "PROCESSED"
    IGNORED = "IGNORED"
    FAILED = "FAILED"


#: Events DevPulse acts on. Anything else is recorded as IGNORED rather than
#: dropped, so the log shows what GitHub is sending even when it is unused.
HANDLED_EVENTS = {"pull_request", "workflow_run", "deployment", "deployment_status", "ping"}


def record_event(
    db: Session, *, delivery_id: str, event_type: str, payload: dict
) -> tuple[WebhookEvent, bool]:
    """Persist a delivery. Returns (event, is_new).

    GitHub retries a delivery it believes failed, so the same delivery_id can
    arrive more than once. Recognising the repeat is what stops one real event
    being counted twice.
    """
    existing = (
        db.query(WebhookEvent)
        .filter_by(provider=PROVIDER, delivery_id=delivery_id)
        .first()
    )
    if existing is not None:
        logger.info("duplicate webhook delivery %s ignored", delivery_id)
        return existing, False

    repository = (payload.get("repository") or {}).get("full_name")
    event = WebhookEvent(
        provider=PROVIDER,
        delivery_id=delivery_id,
        event_type=event_type,
        repository_full_name=repository,
        received_at=utc_now(),
        status=WebhookStatus.RECEIVED,
        payload_json=json.dumps(payload)[:200_000],
    )
    db.add(event)
    db.commit()
    return event, True


def process_event(db: Session, event: WebhookEvent) -> str:
    """Apply a recorded delivery to the domain model.

    Only repositories DevPulse already tracks are touched. A webhook naming an
    unknown repository is not an instruction to start tracking it — accepting
    that would let anyone with the secret add repositories.
    """
    payload = json.loads(event.payload_json)

    if event.event_type == "ping":
        event.status = WebhookStatus.PROCESSED
        event.detail = "Ping acknowledged."
        event.processed_at = utc_now()
        db.commit()
        return event.status

    if event.event_type not in HANDLED_EVENTS:
        event.status = WebhookStatus.IGNORED
        event.detail = f"No handler for '{event.event_type}'."
        event.processed_at = utc_now()
        db.commit()
        return event.status

    repo = (
        db.query(Repository)
        .filter(Repository.full_name == event.repository_full_name)
        .first()
        if event.repository_full_name
        else None
    )
    if repo is None:
        event.status = WebhookStatus.IGNORED
        event.detail = (
            f"Repository '{event.repository_full_name}' is not tracked by DevPulse."
        )
        event.processed_at = utc_now()
        db.commit()
        return event.status

    # Rewind the cursor so the next sync definitely re-reads this window. The
    # webhook is used as a SIGNAL that something changed, not as the source of
    # truth: the REST API is authoritative and complete, whereas a payload can
    # be partial or arrive out of order.
    changed_at = (
        parse_utc((payload.get("pull_request") or {}).get("updated_at"))
        or parse_utc((payload.get("workflow_run") or {}).get("updated_at"))
        or parse_utc((payload.get("deployment") or {}).get("updated_at"))
    )
    if changed_at is not None and repo.last_synced_at is not None:
        repo.last_synced_at = min(repo.last_synced_at, changed_at)
    else:
        repo.last_synced_at = None

    event.status = WebhookStatus.PROCESSED
    event.detail = f"Marked {repo.full_name} for re-sync."
    event.processed_at = utc_now()
    db.commit()

    logger.info(
        "webhook processed provider=%s event=%s repository=%s",
        PROVIDER, event.event_type, repo.full_name,
    )
    return event.status


def recent_events(db: Session, limit: int = 25) -> list[WebhookEvent]:
    return (
        db.query(WebhookEvent)
        .order_by(WebhookEvent.received_at.desc())
        .limit(limit)
        .all()
    )
