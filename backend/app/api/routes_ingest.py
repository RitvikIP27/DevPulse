from fastapi import APIRouter, BackgroundTasks

from app.services.github_client import sync_all

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("/sync")
def trigger_sync(background_tasks: BackgroundTasks):
    """
    Kicks off a GitHub sync in the background (pulls PRs + workflow runs for
    every repo in GITHUB_REPOS). For a real deployment, replace this with a
    scheduled job (cron / Celery beat) or a GitHub webhook receiver instead
    of polling on demand.
    """
    background_tasks.add_task(sync_all)
    return {"status": "sync started"}
