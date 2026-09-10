"""The structured evidence package handed to AI reasoning (PRD 3.1, ADR-008).

Everything here is produced deterministically. The AI layer receives this and
nothing else — it never queries the database, never calls a provider, and never
sees raw vendor payloads. That boundary is what stops a model inventing
telemetry: it can only reason about facts that are already established.
"""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.bottlenecks import StageAnalysis
from app.schemas.conflicts import Conflict, RuntimeComparison
from app.schemas.repositories import AnalysisConfidence, PipelineStage


class EvidenceStage(BaseModel):
    stage: PipelineStage
    status: str
    duration_minutes: float | None
    detail: str


class EvidenceIncident(BaseModel):
    title: str | None
    status: str
    started_at: datetime
    resolved_at: datetime | None
    minutes_after_deployment: float | None


class EvidenceCoverage(BaseModel):
    confidence: AnalysisConfidence
    confidence_reason: str
    observed_stages: list[PipelineStage]
    unobserved_stages: list[PipelineStage]


class EvidencePackage(BaseModel):
    """Facts about one deployment, assembled from every deterministic engine."""

    #: Fingerprint of the facts below. Identical evidence reuses a stored
    #: analysis rather than paying for another one.
    evidence_hash: str
    generated_at: datetime

    repository_full_name: str
    service: str
    deployment_id: int
    environment: str
    commit_sha: str | None
    deployment_status: str
    deployed_at: datetime

    pull_request_number: int | None
    pull_request_title: str | None
    author_login: str | None

    stages: list[EvidenceStage]
    bottlenecks: list[StageAnalysis]
    runtime: RuntimeComparison
    incidents: list[EvidenceIncident]
    conflicts: list[Conflict]
    coverage: EvidenceCoverage

    #: What the deterministic layer already knows it cannot answer. Carried into
    #: the prompt so the model is told the limits rather than discovering them.
    known_limitations: list[str]
