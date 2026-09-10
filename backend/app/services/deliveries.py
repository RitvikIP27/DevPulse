"""Delivery trace reconstruction (PRD 2.4, ADR-007).

A delivery is one change moving through the engineering system. DevPulse builds
one by correlating records that share a commit: the merge commit a pull request
produced is the commit a later CI run, build or deployment reports having
processed.

Correlation here uses only the strongest signal available — an exact commit SHA
match. Timestamp proximity is never used to establish identity (rules.md 9), so
a record that cannot be matched on a commit is reported as uncorrelatable rather
than attached to whichever delivery happens to be nearest in time.

Traces are derived on read rather than persisted. The inputs are already stored,
the computation is deterministic, and deriving means a change to the correlation
rules takes effect immediately instead of requiring a backfill. Persisting them
becomes worthwhile when traces span providers that arrive out of order.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.events import PullRequest, Repository, WorkflowRun
from app.schemas.deliveries import (
    Correlation,
    CorrelationConfidence,
    CorrelationMethod,
    DeliveryDetail,
    DeliveryListResponse,
    DeliveryStage,
    DeliverySummary,
    StageRun,
    StageStatus,
)
from app.schemas.repositories import PipelineStage

DEFAULT_DELIVERY_LIMIT = 25

# Stages a GitHub + Actions integration can observe. The rest are reported as
# NOT_OBSERVED so a trace shows its own gaps (PRD 2.6).
_OBSERVABLE_STAGES = (PipelineStage.SOURCE, PipelineStage.REVIEW, PipelineStage.CI)
_UNOBSERVED_STAGES = (
    (PipelineStage.QUALITY, "No code-quality integration is connected."),
    (PipelineStage.BUILD, "Build events are not yet distinguished from CI runs."),
    (PipelineStage.ARTIFACT, "No artifact registry is connected."),
    (PipelineStage.DEPLOYMENT, "No deployment provider is connected, so DevPulse cannot confirm this change reached production."),
    (PipelineStage.ROLLOUT, "No orchestrator is connected."),
    (PipelineStage.RUNTIME, "No monitoring provider is connected."),
    (PipelineStage.INCIDENT, "No incident-management provider is connected."),
)


def _minutes(start, end) -> float | None:
    if start is None or end is None:
        return None
    return round((end - start).total_seconds() / 60.0, 1)


def _run_status(runs: list[WorkflowRun]) -> StageStatus:
    if any(run.conclusion == "failure" for run in runs):
        return StageStatus.FAILED
    if any(run.completed_at is None for run in runs):
        return StageStatus.IN_PROGRESS
    return StageStatus.SUCCESS


def _to_stage_run(run: WorkflowRun) -> StageRun:
    return StageRun(
        name=run.workflow_name,
        status=run.conclusion or run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        url=run.html_url,
        provider="github_actions",
    )


def _build_stages(pr: PullRequest, runs: list[WorkflowRun]) -> list[DeliveryStage]:
    stages: list[DeliveryStage] = []

    # SOURCE — the commit itself. Instantaneous, so it has no duration.
    stages.append(
        DeliveryStage(
            stage=PipelineStage.SOURCE,
            status=StageStatus.SUCCESS,
            started_at=pr.opened_at,
            completed_at=pr.opened_at,
            duration_minutes=None,
            provider="github",
            detail=f"Commit {(pr.merge_commit_sha or '')[:10]} on {pr.base_branch or 'the base branch'}.",
        )
    )

    # REVIEW — opened to merged. Individual review events are not ingested yet,
    # so this measures elapsed time, not reviewer effort.
    stages.append(
        DeliveryStage(
            stage=PipelineStage.REVIEW,
            status=StageStatus.SUCCESS if pr.merged_at else StageStatus.IN_PROGRESS,
            started_at=pr.opened_at,
            completed_at=pr.merged_at,
            duration_minutes=_minutes(pr.opened_at, pr.merged_at),
            provider="github",
            detail=(
                f"Pull request #{pr.github_pr_number} open for review. "
                "Elapsed time only — individual review events are not ingested yet."
            ),
        )
    )

    # CI — every run that reported this commit.
    if runs:
        started = min(run.started_at for run in runs)
        completions = [run.completed_at for run in runs if run.completed_at]
        completed = max(completions) if completions else None
        stages.append(
            DeliveryStage(
                stage=PipelineStage.CI,
                status=_run_status(runs),
                started_at=started,
                completed_at=completed,
                duration_minutes=_minutes(started, completed),
                provider="github_actions",
                detail=f"{len(runs)} workflow run(s) reported this commit.",
                runs=[_to_stage_run(run) for run in sorted(runs, key=lambda r: r.started_at)],
            )
        )
    else:
        stages.append(
            DeliveryStage(
                stage=PipelineStage.CI,
                status=StageStatus.NOT_OBSERVED,
                started_at=None,
                completed_at=None,
                duration_minutes=None,
                provider=None,
                detail="No workflow run reported this commit.",
            )
        )

    for stage, detail in _UNOBSERVED_STAGES:
        stages.append(
            DeliveryStage(
                stage=stage,
                status=StageStatus.NOT_OBSERVED,
                started_at=None,
                completed_at=None,
                duration_minutes=None,
                provider=None,
                detail=detail,
            )
        )

    return stages


def _overall_status(stages: list[DeliveryStage]) -> StageStatus:
    """Status across observed stages only.

    A delivery is not FAILED because runtime telemetry is missing; unobserved
    stages carry no verdict (ADR-011).
    """
    observed = [s for s in stages if s.status is not StageStatus.NOT_OBSERVED]
    if any(s.status is StageStatus.FAILED for s in observed):
        return StageStatus.FAILED
    if any(s.status is StageStatus.IN_PROGRESS for s in observed):
        return StageStatus.IN_PROGRESS
    return StageStatus.SUCCESS


def _summary(repo: Repository, pr: PullRequest, stages: list[DeliveryStage]) -> DeliverySummary:
    observed = [s for s in stages if s.status is not StageStatus.NOT_OBSERVED]
    ends = [s.completed_at for s in observed if s.completed_at]
    completed_at = max(ends) if ends else None

    return DeliverySummary(
        id=f"{repo.id}-{pr.github_pr_number}",
        repository_full_name=repo.full_name,
        service=repo.display_name or repo.full_name,
        commit_sha=pr.merge_commit_sha or "",
        pull_request_number=pr.github_pr_number,
        title=pr.title,
        author_login=pr.author_login,
        started_at=pr.opened_at,
        completed_at=completed_at,
        total_duration_minutes=_minutes(pr.opened_at, completed_at),
        status=_overall_status(stages),
        stage_count_observed=len(observed),
        stage_count_total=len(stages),
    )


def _correlation(pr: PullRequest, runs: list[WorkflowRun]) -> Correlation:
    return Correlation(
        method=CorrelationMethod.COMMIT_SHA,
        confidence=CorrelationConfidence.HIGH,
        evidence=(
            f"{len(runs)} workflow run(s) reported head_sha "
            f"{(pr.merge_commit_sha or '')[:10]}, exactly matching the merge commit of "
            f"pull request #{pr.github_pr_number}. Matched on commit identity, not "
            "timestamp proximity."
        ),
        commit_sha=pr.merge_commit_sha or "",
    )


def _runs_for(db: Session, repo_id: int, commit_sha: str) -> list[WorkflowRun]:
    return (
        db.query(WorkflowRun)
        .filter(WorkflowRun.repository_id == repo_id)
        .filter(WorkflowRun.head_sha == commit_sha)
        .order_by(WorkflowRun.started_at.asc())
        .all()
    )


def list_deliveries(
    db: Session, repository_id: int | None = None, limit: int = DEFAULT_DELIVERY_LIMIT
) -> DeliveryListResponse:
    query = db.query(PullRequest).filter(PullRequest.is_merged.is_(True))
    if repository_id is not None:
        query = query.filter(PullRequest.repository_id == repository_id)

    merged = query.order_by(PullRequest.merged_at.desc().nullslast()).all()

    # A merged PR with no merge commit has no join key. It is counted and
    # reported rather than dropped, so the list never looks more complete than
    # the data behind it.
    correlatable = [pr for pr in merged if pr.merge_commit_sha]
    uncorrelatable = len(merged) - len(correlatable)

    repositories = {repo.id: repo for repo in db.query(Repository).all()}
    deliveries = [
        _summary(
            repositories[pr.repository_id],
            pr,
            _build_stages(pr, _runs_for(db, pr.repository_id, pr.merge_commit_sha)),
        )
        for pr in correlatable[:limit]
        if pr.repository_id in repositories
    ]

    return DeliveryListResponse(deliveries=deliveries, uncorrelatable_count=uncorrelatable)


def get_delivery(db: Session, delivery_id: str) -> DeliveryDetail | None:
    try:
        repo_id_text, pr_number_text = delivery_id.split("-", 1)
        repo_id, pr_number = int(repo_id_text), int(pr_number_text)
    except ValueError:
        return None

    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    pr = (
        db.query(PullRequest)
        .filter(PullRequest.repository_id == repo_id, PullRequest.github_pr_number == pr_number)
        .first()
    )
    if repo is None or pr is None or not pr.merge_commit_sha:
        return None

    runs = _runs_for(db, repo_id, pr.merge_commit_sha)
    stages = _build_stages(pr, runs)
    summary = _summary(repo, pr, stages)

    return DeliveryDetail(**summary.model_dump(), stages=stages, correlation=_correlation(pr, runs))
