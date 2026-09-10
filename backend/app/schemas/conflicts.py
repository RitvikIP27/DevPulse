"""API contracts for runtime correlation and cross-system conflict detection."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ConflictType(str, Enum):
    #: Control plane reported success while runtime health degraded.
    DEPLOYMENT_SUCCESS_RUNTIME_DEGRADED = "DEPLOYMENT_SUCCESS_RUNTIME_DEGRADED"
    #: Control plane reported success and an incident opened shortly after.
    DEPLOYMENT_SUCCESS_INCIDENT_OPENED = "DEPLOYMENT_SUCCESS_INCIDENT_OPENED"
    #: CI passed but the deployment of that same commit failed.
    CI_SUCCESS_DEPLOYMENT_FAILED = "CI_SUCCESS_DEPLOYMENT_FAILED"


class RelationStrength(str, Enum):
    """How strongly two observations are related.

    Never CAUSED. Temporal proximity is evidence, not proof (ADR-011), and the
    vocabulary is deliberately constrained so no caller can promote a
    correlation into a causal claim.
    """

    CORRELATED = "CORRELATED"
    POTENTIALLY_RELATED = "POTENTIALLY_RELATED"


class MetricShift(BaseModel):
    metric: str
    before_value: float | None
    after_value: float | None
    change_pct: float | None
    sample_count_before: int
    sample_count_after: int
    is_degradation: bool


class RuntimeComparison(BaseModel):
    """Runtime health before a deployment versus after it."""

    available: bool
    unavailable_reason: str | None
    window_minutes: int
    shifts: list[MetricShift]


class Conflict(BaseModel):
    type: ConflictType
    strength: RelationStrength
    title: str
    description: str
    evidence: list[str]
    #: What DevPulse still cannot determine. Stated so the reader knows the
    #: limits of the claim rather than inferring more than is supported.
    unknowns: list[str]


class DeploymentConflictReport(BaseModel):
    deployment_id: int
    repository_full_name: str
    environment: str
    commit_sha: str | None
    deployment_status: str
    deployed_at: datetime
    runtime: RuntimeComparison
    incidents_after: int
    conflicts: list[Conflict]


class ConflictListResponse(BaseModel):
    reports: list[DeploymentConflictReport]
    conflict_count: int
    runtime_available: bool
    incidents_available: bool
    unavailable_reason: str | None
