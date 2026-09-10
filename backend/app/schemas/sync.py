"""API contracts for ingestion status."""

from datetime import datetime

from pydantic import BaseModel


class SyncJobSummary(BaseModel):
    id: int
    repository_full_name: str | None
    provider: str
    status: str  # RUNNING / SUCCESS / PARTIAL / FAILED
    started_at: datetime
    finished_at: datetime | None
    pull_requests_written: int
    workflow_runs_written: int
    error_code: str | None
    error_message: str | None


class SyncJobListResponse(BaseModel):
    jobs: list[SyncJobSummary]
