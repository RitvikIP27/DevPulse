"""DORA delivery metrics, computed from deployments (PRD 2.7).

These are the five metrics current DORA defines, derived from Deployment records
rather than from CI workflow runs. A repository with no deployment source
reports every deployment-derived metric as unavailable, with a reason.

This replaces the MVP behaviour, which treated every workflow run as a
deployment. On a real repository that overstated deployment frequency by roughly
5.7x and collapsed lead time to about 0.1 minutes per pull request, because the
run matched after a merge was the CI job the merge itself triggered
(docs/architecture-audit.md section 3).
"""

from datetime import datetime, timedelta
from statistics import median

from sqlalchemy.orm import Session

from app.models.events import Deployment, PullRequest, Repository
from app.schemas.metrics import DoraMetricsResponse, ServiceDoraMetrics
from app.services.deployments import (
    DeploymentSource,
    DeploymentStatus,
    deployment_source,
    production_deployments,
)
from app.services.timestamps import utc_now

NO_DEPLOYMENT_SOURCE_REASON = (
    "No deployment provider is connected and no deployment workflow has been "
    "configured, so DevPulse cannot identify production deployments. Configure a "
    "deployment rule on the Settings page, or connect a deployment provider."
)

#: A deployment following a failed one within this window is treated as the
#: remediation of that failure. Beyond it, the two are considered unrelated
#: rather than assumed to be a recovery.
MAX_RECOVERY_WINDOW_HOURS = 48.0


def _hours(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 3600.0


def _unavailable(service: str, reason: str) -> ServiceDoraMetrics:
    return ServiceDoraMetrics(
        service=service,
        deployment_source=DeploymentSource.NONE,
        unavailable_reason=reason,
        deployment_frequency_per_week=None,
        lead_time_hours=None,
        change_failure_rate_pct=None,
        failed_deployment_recovery_hours=None,
        deployment_rework_rate_pct=None,
        total_deployments=0,
        total_failures=0,
    )


def _lead_time_hours(db: Session, repo_id: int, successful: list[Deployment]) -> float | None:
    """Median time from a change merging to the deployment that shipped it.

    A deployment is matched to its change by commit, never by time order. This
    is the correction that matters: the MVP took the next successful run after a
    merge, which was always the CI job that merge triggered.
    """
    if not successful:
        return None

    merged = (
        db.query(PullRequest)
        .filter(PullRequest.repository_id == repo_id)
        .filter(PullRequest.is_merged.is_(True))
        .filter(PullRequest.merge_commit_sha.isnot(None))
        .all()
    )
    merged_at_by_sha = {pr.merge_commit_sha: pr.merged_at for pr in merged if pr.merged_at}

    lead_times = [
        _hours(merged_at_by_sha[deployment.commit_sha], deployment.started_at)
        for deployment in successful
        if deployment.commit_sha in merged_at_by_sha
        and deployment.started_at >= merged_at_by_sha[deployment.commit_sha]
    ]
    return round(median(lead_times), 2) if lead_times else None


def _recovery_hours(deployments: list[Deployment]) -> float | None:
    """Median time from a failed production deployment to the next success."""
    recoveries: list[float] = []

    for index, deployment in enumerate(deployments):
        if deployment.status != DeploymentStatus.FAILED:
            continue
        failed_at = deployment.finished_at or deployment.started_at

        for candidate in deployments[index + 1:]:
            if candidate.status != DeploymentStatus.SUCCESS:
                continue
            gap = _hours(failed_at, candidate.started_at)
            if gap <= MAX_RECOVERY_WINDOW_HOURS:
                recoveries.append(gap)
            break

    return round(median(recoveries), 2) if recoveries else None


def _rework_rate_pct(deployments: list[Deployment], successful: list[Deployment]) -> float | None:
    """Share of production deployments made to remediate a previous failure.

    DevPulse can only observe remediation that follows an observed failure.
    Rework prompted by a user-reported defect that never failed a deployment is
    invisible without incident data, and the figure is a lower bound until an
    incident provider is connected.
    """
    if not deployments:
        return None

    remediation = 0
    for index, deployment in enumerate(deployments):
        if deployment.status != DeploymentStatus.SUCCESS or index == 0:
            continue
        if deployments[index - 1].status == DeploymentStatus.FAILED:
            remediation += 1

    return round(remediation / len(deployments) * 100, 1)


def compute_service_metrics(db: Session, repo: Repository, window_days: int) -> ServiceDoraMetrics:
    service = repo.display_name or repo.full_name
    source = deployment_source(db, repo.id)

    if source == DeploymentSource.NONE:
        return _unavailable(service, NO_DEPLOYMENT_SOURCE_REASON)

    since = utc_now() - timedelta(days=window_days)
    deployments = production_deployments(db, repo.id, since=since)

    successful = [d for d in deployments if d.status == DeploymentStatus.SUCCESS]
    failed = [d for d in deployments if d.status == DeploymentStatus.FAILED]
    concluded = len(successful) + len(failed)

    if concluded == 0:
        return ServiceDoraMetrics(
            service=service,
            deployment_source=source,
            unavailable_reason=(
                f"No production deployment completed in the last {window_days} days."
            ),
            deployment_frequency_per_week=None,
            lead_time_hours=None,
            change_failure_rate_pct=None,
            failed_deployment_recovery_hours=None,
            deployment_rework_rate_pct=None,
            total_deployments=0,
            total_failures=0,
        )

    weeks = max(window_days / 7.0, 1.0)

    return ServiceDoraMetrics(
        service=service,
        deployment_source=source,
        unavailable_reason=None,
        deployment_frequency_per_week=round(len(successful) / weeks, 2),
        lead_time_hours=_lead_time_hours(db, repo.id, successful),
        change_failure_rate_pct=round(len(failed) / concluded * 100, 1),
        failed_deployment_recovery_hours=_recovery_hours(deployments),
        deployment_rework_rate_pct=_rework_rate_pct(deployments, successful),
        total_deployments=len(successful),
        total_failures=len(failed),
    )


def compute_all_metrics(db: Session, window_days: int = 30) -> DoraMetricsResponse:
    repos = db.query(Repository).all()
    services = [compute_service_metrics(db, repo, window_days) for repo in repos]

    # Worst first, but services with no data sort last: an unmeasurable service
    # is not a well-performing one, and must not top a "healthiest" ranking.
    services.sort(
        key=lambda s: (
            s.change_failure_rate_pct is None,
            -(s.change_failure_rate_pct or 0),
            -(s.lead_time_hours or 0),
        )
    )
    return DoraMetricsResponse(window_days=window_days, services=services)
