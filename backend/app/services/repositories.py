"""Repository listing and data-coverage reporting.

Coverage exists so the product never presents absent telemetry as healthy
telemetry (PRD 2.6, rules.md 11). It is computed from what has actually been
ingested, not declared by hand.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.events import PullRequest, Repository, WorkflowRun
from app.schemas.repositories import (
    AnalysisConfidence,
    CoverageStatus,
    LastSync,
    PipelineStage,
    RepositoryCoverage,
    RepositoryListResponse,
    RepositorySummary,
    StageCoverage,
)
from app.services.sync_jobs import latest_job_for_repository

# Stages that a GitHub + GitHub Actions integration can populate today.
# Everything else has no connector, so it is NOT_CONFIGURED rather than empty.
_CONNECTED_STAGES = {PipelineStage.SOURCE, PipelineStage.CI}

# Delivery analysis is only as trustworthy as the stages that bound it: where a
# change came from, whether it built, whether it actually reached production, and
# whether production stayed healthy afterwards. Confidence is the fraction of
# these four that DevPulse can actually see.
_CRITICAL_STAGES = (
    PipelineStage.SOURCE,
    PipelineStage.CI,
    PipelineStage.DEPLOYMENT,
    PipelineStage.RUNTIME,
)

_NOT_CONFIGURED_DETAIL = {
    PipelineStage.REVIEW: "Pull requests are ingested, but review events are not.",
    PipelineStage.QUALITY: "No code-quality or security integration is connected.",
    PipelineStage.BUILD: "Build events are not distinguished from CI runs yet.",
    PipelineStage.ARTIFACT: "No artifact registry is connected.",
    PipelineStage.DEPLOYMENT: "No deployment provider is connected. Deployment "
    "frequency, lead time and change failure rate are derived from CI runs "
    "standing in for deployments, and are not production measurements.",
    PipelineStage.ROLLOUT: "No orchestrator is connected.",
    PipelineStage.RUNTIME: "No monitoring provider is connected. DevPulse cannot "
    "tell whether a successful deployment degraded production.",
    PipelineStage.INCIDENT: "No incident-management provider is connected.",
}


def _stage_coverage(pull_request_count: int, workflow_run_count: int) -> list[StageCoverage]:
    counts = {
        PipelineStage.SOURCE: pull_request_count,
        PipelineStage.CI: workflow_run_count,
    }
    detail_when_present = {
        PipelineStage.SOURCE: "Pull requests ingested from GitHub.",
        PipelineStage.CI: "Workflow runs ingested from GitHub Actions.",
    }

    coverage: list[StageCoverage] = []
    for stage in PipelineStage:
        if stage in _CONNECTED_STAGES:
            count = counts[stage]
            coverage.append(
                StageCoverage(
                    stage=stage,
                    status=CoverageStatus.AVAILABLE if count else CoverageStatus.NO_DATA,
                    detail=(
                        detail_when_present[stage]
                        if count
                        else "Integration connected, but nothing has been ingested yet."
                    ),
                    record_count=count,
                )
            )
        else:
            coverage.append(
                StageCoverage(
                    stage=stage,
                    status=CoverageStatus.NOT_CONFIGURED,
                    detail=_NOT_CONFIGURED_DETAIL[stage],
                )
            )
    return coverage


def _confidence(stages: list[StageCoverage]) -> tuple[AnalysisConfidence, str]:
    by_stage = {entry.stage: entry for entry in stages}
    available = [
        stage
        for stage in _CRITICAL_STAGES
        if by_stage[stage].status is CoverageStatus.AVAILABLE
    ]
    missing = [stage.value for stage in _CRITICAL_STAGES if stage not in available]

    if len(available) == len(_CRITICAL_STAGES):
        return AnalysisConfidence.HIGH, "All four critical delivery stages report data."

    reason = (
        f"{len(available)} of {len(_CRITICAL_STAGES)} critical delivery stages report "
        f"data. Missing: {', '.join(missing)}."
    )
    level = (
        AnalysisConfidence.LIMITED if len(available) >= 2 else AnalysisConfidence.MINIMAL
    )
    return level, reason


def list_repositories(db: Session) -> RepositoryListResponse:
    repositories = db.query(Repository).order_by(Repository.full_name).all()

    summaries: list[RepositorySummary] = []
    for repository in repositories:
        pull_request_count = (
            db.query(func.count(PullRequest.id))
            .filter(PullRequest.repository_id == repository.id)
            .scalar()
            or 0
        )
        workflow_run_count = (
            db.query(func.count(WorkflowRun.id))
            .filter(WorkflowRun.repository_id == repository.id)
            .scalar()
            or 0
        )
        last_activity_at = (
            db.query(func.max(WorkflowRun.started_at))
            .filter(WorkflowRun.repository_id == repository.id)
            .scalar()
        )

        correlatable = (
            db.query(func.count(WorkflowRun.id))
            .filter(WorkflowRun.repository_id == repository.id)
            .filter(WorkflowRun.head_sha.isnot(None))
            .scalar()
            or 0
        )
        correlatable_run_pct = (
            round(correlatable / workflow_run_count * 100, 1) if workflow_run_count else None
        )

        job = latest_job_for_repository(db, repository.id)
        last_sync = (
            LastSync(
                status=job.status,
                started_at=job.started_at,
                finished_at=job.finished_at,
                error_code=job.error_code,
                error_message=job.error_message,
            )
            if job
            else None
        )

        stages = _stage_coverage(pull_request_count, workflow_run_count)
        confidence, confidence_reason = _confidence(stages)

        summaries.append(
            RepositorySummary(
                id=repository.id,
                full_name=repository.full_name,
                display_name=repository.display_name,
                pull_request_count=pull_request_count,
                workflow_run_count=workflow_run_count,
                last_activity_at=last_activity_at,
                last_sync=last_sync,
                correlatable_run_pct=correlatable_run_pct,
                coverage=RepositoryCoverage(
                    stages=stages,
                    confidence=confidence,
                    confidence_reason=confidence_reason,
                ),
            )
        )

    return RepositoryListResponse(repositories=summaries)
