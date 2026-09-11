from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.logging import get_logger
from app.core.webhook_security import SIGNATURE_HEADER, is_valid_signature
from app.services.webhooks import process_event, recent_events, record_event

logger = get_logger(__name__)

# Two routers, because the two endpoints have genuinely different audiences.
#
# `public_router` receives deliveries from GitHub, which cannot present a bearer
# token — the HMAC signature is the authentication there. Splitting it out keeps
# that exception explicit rather than leaving a public hole in a router someone
# later assumes is protected.
public_router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

# `router` is the operator-facing side and is mounted with the protected group.
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@public_router.post("/github", status_code=202)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(default=""),
    x_github_delivery: str = Header(default=""),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Receive a GitHub webhook delivery.

    Returns 202 as soon as the delivery is recorded, and processes it in the
    background. GitHub times out quickly and retries on timeout, so doing the
    work first would turn a slow sync into duplicate deliveries.
    """
    if not settings.github_webhook_secret or settings.github_webhook_secret == "change_me":
        # Refusing is the safe default. Accepting unverified payloads would let
        # anyone forge the data every metric is built on.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhooks are not configured. Set GITHUB_WEBHOOK_SECRET.",
        )

    # The RAW body must be read before parsing: the signature covers the exact
    # bytes GitHub sent, and re-serialising parsed JSON would not reproduce them.
    raw_body = await request.body()
    signature = request.headers.get(SIGNATURE_HEADER)

    if not is_valid_signature(raw_body, signature, settings.github_webhook_secret):
        logger.warning("rejected webhook delivery %s: bad signature", x_github_delivery)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature.")

    if not x_github_delivery:
        raise HTTPException(status_code=400, detail="Missing delivery id.")

    try:
        payload = await request.json()
    except Exception as error:
        raise HTTPException(status_code=400, detail="Body is not valid JSON.") from error

    event, is_new = record_event(
        db, delivery_id=x_github_delivery, event_type=x_github_event, payload=payload
    )
    if not is_new:
        return {"status": "duplicate", "detail": "This delivery was already received."}

    background_tasks.add_task(_process_in_background, event.id)
    return {"status": "accepted", "detail": "Delivery recorded."}


def _process_in_background(event_id: int) -> None:
    """Process a recorded delivery after the response has been sent.

    Opens its own session on purpose: the request-scoped session is already
    closed by the time a background task runs, so reusing it would fail. The
    factory is read from the module namespace rather than imported inside the
    function so tests can substitute it.
    """
    from app.models.events import WebhookEvent

    db = SessionLocal()
    try:
        event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
        if event is not None:
            process_event(db, event)
    finally:
        db.close()


@router.get("/events")
def get_events(db: Session = Depends(get_db)) -> dict:
    """Recent deliveries, so webhook configuration can be debugged."""
    return {
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "repository_full_name": e.repository_full_name,
                "status": e.status,
                "detail": e.detail,
                "received_at": e.received_at,
                "processed_at": e.processed_at,
            }
            for e in recent_events(db)
        ]
    }
