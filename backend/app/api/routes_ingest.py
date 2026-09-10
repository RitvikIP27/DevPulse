from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.sync import SyncJobListResponse
from app.services.github_client import sync_all
from app.services.sync_jobs import DEFAULT_JOB_LIMIT, list_recent_jobs

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("/sync", status_code=202)
def trigger_sync(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Start a GitHub sync in the background.

    202 rather than 200: the work has been accepted, not completed. The outcome
    is recorded as a SyncJob and read back from /api/ingest/jobs — the MVP
    returned 200 and then discarded any failure that followed.
    """
    background_tasks.add_task(sync_all)
    return {
        "status": "accepted",
        "detail": "Ingestion started. Poll /api/ingest/jobs for the outcome.",
    }


@router.get("/jobs", response_model=SyncJobListResponse)
def get_sync_jobs(
    limit: int = Query(DEFAULT_JOB_LIMIT, ge=1, le=100),
    db: Session = Depends(get_db),
) -> SyncJobListResponse:
    """Recent ingestion runs, newest first."""
    return list_recent_jobs(db, limit=limit)
