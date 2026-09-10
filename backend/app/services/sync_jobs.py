"""Reads ingestion history so the UI can report what a sync actually did."""

from sqlalchemy.orm import Session

from app.models.events import Repository, SyncJob
from app.schemas.sync import SyncJobListResponse, SyncJobSummary

DEFAULT_JOB_LIMIT = 20


def _to_summary(job: SyncJob, repository_names: dict[int, str]) -> SyncJobSummary:
    return SyncJobSummary(
        id=job.id,
        repository_full_name=repository_names.get(job.repository_id) if job.repository_id else None,
        provider=job.provider,
        status=job.status,
        started_at=job.started_at,
        finished_at=job.finished_at,
        pull_requests_written=job.pull_requests_written or 0,
        workflow_runs_written=job.workflow_runs_written or 0,
        error_code=job.error_code,
        error_message=job.error_message,
    )


def _repository_names(db: Session) -> dict[int, str]:
    return {repo.id: repo.full_name for repo in db.query(Repository).all()}


def list_recent_jobs(db: Session, limit: int = DEFAULT_JOB_LIMIT) -> SyncJobListResponse:
    jobs = db.query(SyncJob).order_by(SyncJob.started_at.desc(), SyncJob.id.desc()).limit(limit).all()
    names = _repository_names(db)
    return SyncJobListResponse(jobs=[_to_summary(job, names) for job in jobs])


def latest_job_for_repository(db: Session, repository_id: int) -> SyncJob | None:
    return (
        db.query(SyncJob)
        .filter(SyncJob.repository_id == repository_id)
        .order_by(SyncJob.started_at.desc(), SyncJob.id.desc())
        .first()
    )
