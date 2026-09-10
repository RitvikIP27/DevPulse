"""API contracts for delivery traces (PRD 2.4)."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from app.schemas.repositories import PipelineStage


class StageStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    IN_PROGRESS = "IN_PROGRESS"
    #: No integration reports this stage, so DevPulse cannot say what happened.
    #: Deliberately distinct from FAILED — absence of evidence is not failure.
    NOT_OBSERVED = "NOT_OBSERVED"


class CorrelationMethod(str, Enum):
    #: Strongest available signal: the same commit appears in both records.
    COMMIT_SHA = "COMMIT_SHA"


class CorrelationConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class StageRun(BaseModel):
    """One provider record contributing to a stage — the evidence behind it."""

    name: str
    status: str | None
    started_at: datetime | None
    completed_at: datetime | None
    url: str | None
    provider: str


class DeliveryStage(BaseModel):
    stage: PipelineStage
    status: StageStatus
    started_at: datetime | None
    completed_at: datetime | None
    duration_minutes: float | None
    provider: str | None
    detail: str
    runs: list[StageRun] = []


class Correlation(BaseModel):
    """Why DevPulse believes these records describe one change (rules.md 9)."""

    method: CorrelationMethod
    confidence: CorrelationConfidence
    evidence: str
    commit_sha: str


class DeliverySummary(BaseModel):
    id: str
    repository_full_name: str
    service: str
    commit_sha: str
    pull_request_number: int
    title: str | None
    author_login: str | None
    started_at: datetime
    completed_at: datetime | None
    total_duration_minutes: float | None
    status: StageStatus
    stage_count_observed: int
    stage_count_total: int


class DeliveryDetail(DeliverySummary):
    stages: list[DeliveryStage]
    correlation: Correlation


class DeliveryListResponse(BaseModel):
    deliveries: list[DeliverySummary]
    #: Merged pull requests that carry no merge commit SHA and therefore cannot
    #: be correlated. Reported rather than silently dropped.
    uncorrelatable_count: int
