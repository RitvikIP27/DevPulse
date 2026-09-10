"""API contracts for repositories and their data coverage."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class PipelineStage(str, Enum):
    """Logical delivery stages, independent of any vendor (PRD 2.5).

    Only the stages DevPulse can currently say something truthful about are
    reported. The remainder arrive with the integrations that populate them.
    """

    SOURCE = "SOURCE"
    REVIEW = "REVIEW"
    CI = "CI"
    QUALITY = "QUALITY"
    BUILD = "BUILD"
    ARTIFACT = "ARTIFACT"
    DEPLOYMENT = "DEPLOYMENT"
    ROLLOUT = "ROLLOUT"
    RUNTIME = "RUNTIME"
    INCIDENT = "INCIDENT"


class CoverageStatus(str, Enum):
    """Why a stage does or does not have data.

    The distinction between NO_DATA and NOT_CONFIGURED matters: the first means
    DevPulse is watching and has seen nothing, the second means DevPulse is not
    watching at all. Collapsing them into a single "0" is exactly the failure
    mode rules.md 11 forbids.
    """

    AVAILABLE = "AVAILABLE"
    NO_DATA = "NO_DATA"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class AnalysisConfidence(str, Enum):
    HIGH = "HIGH"
    LIMITED = "LIMITED"
    MINIMAL = "MINIMAL"


class StageCoverage(BaseModel):
    stage: PipelineStage
    status: CoverageStatus
    detail: str
    record_count: int | None = None


class RepositoryCoverage(BaseModel):
    stages: list[StageCoverage]
    confidence: AnalysisConfidence
    confidence_reason: str


class LastSync(BaseModel):
    status: str
    started_at: datetime
    finished_at: datetime | None
    error_code: str | None
    error_message: str | None


class RepositorySummary(BaseModel):
    id: int
    full_name: str
    display_name: str | None
    pull_request_count: int
    workflow_run_count: int
    last_activity_at: datetime | None
    last_sync: LastSync | None
    # Share of ingested workflow runs that carry a commit SHA. Runs stored before
    # correlation keys existed have none, and cannot be joined to anything.
    correlatable_run_pct: float | None
    coverage: RepositoryCoverage


class RepositoryListResponse(BaseModel):
    repositories: list[RepositorySummary]
