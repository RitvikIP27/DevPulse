"""
Computes the four DORA metrics per repository/service:

  - Deployment Frequency : successful 'deploy' workflow runs per week
  - Lead Time for Changes: median time from PR merge -> next successful deploy
  - Change Failure Rate  : failed deploy runs / total deploy runs (%)
  - MTTR                 : median time from a failed deploy -> the next successful deploy

This treats a workflow run whose name contains "deploy" as a deployment event.
Adjust `workflow_name_filter` in github_client.py if your pipelines are named differently.
"""
from datetime import datetime, timedelta, timezone
from statistics import median

from sqlalchemy.orm import Session

from app.models.events import Repository, PullRequest, WorkflowRun
from app.schemas.metrics import ServiceDoraMetrics, DoraMetricsResponse


def _hours_between(a: datetime, b: datetime) -> float:
    return abs((b - a).total_seconds()) / 3600.0


def compute_service_metrics(db: Session, repo: Repository, window_days: int) -> ServiceDoraMetrics:
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=window_days)

    runs = (
        db.query(WorkflowRun)
        .filter(WorkflowRun.repository_id == repo.id)
        .filter(WorkflowRun.started_at >= since)
        .filter(WorkflowRun.completed_at.isnot(None))
        .order_by(WorkflowRun.started_at.asc())
        .all()
    )

    successful = [r for r in runs if r.conclusion == "success"]
    failed = [r for r in runs if r.conclusion == "failure"]
    total = len(runs)

    # 1. Deployment Frequency (successful deploys per week)
    weeks = max(window_days / 7.0, 1.0)
    deployment_frequency = round(len(successful) / weeks, 2)

    # 2. Change Failure Rate
    change_failure_rate = round((len(failed) / total) * 100, 1) if total else 0.0

    # 3. MTTR — median time between a failed run and the next successful run after it
    recovery_times = []
    for f in failed:
        next_success = next((s for s in successful if s.started_at > f.started_at), None)
        if next_success:
            recovery_times.append(_hours_between(f.completed_at or f.started_at, next_success.started_at))
    mttr_hours = round(median(recovery_times), 1) if recovery_times else None

    # 4. Lead Time for Changes — median time from PR merge to the next successful deploy
    merged_prs = (
        db.query(PullRequest)
        .filter(PullRequest.repository_id == repo.id)
        .filter(PullRequest.is_merged.is_(True))
        .filter(PullRequest.merged_at >= since)
        .all()
    )
    lead_times = []
    for pr in merged_prs:
        next_deploy = next((s for s in successful if s.started_at > pr.merged_at), None)
        if next_deploy:
            lead_times.append(_hours_between(pr.merged_at, next_deploy.started_at))
    lead_time_hours = round(median(lead_times), 1) if lead_times else None

    return ServiceDoraMetrics(
        service=repo.display_name or repo.full_name,
        deployment_frequency_per_week=deployment_frequency,
        lead_time_hours=lead_time_hours,
        change_failure_rate_pct=change_failure_rate,
        mttr_hours=mttr_hours,
        total_deployments=len(successful),
        total_failures=len(failed),
    )


def compute_all_metrics(db: Session, window_days: int = 30) -> DoraMetricsResponse:
    repos = db.query(Repository).all()
    services = [compute_service_metrics(db, r, window_days) for r in repos]
    # worst-performing services first: highest change-failure rate, then longest lead time
    services.sort(key=lambda s: (-s.change_failure_rate_pct, -(s.lead_time_hours or 0)))
    return DoraMetricsResponse(window_days=window_days, services=services)
