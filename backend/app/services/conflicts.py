"""Runtime correlation and cross-system conflict detection (PRD 2.11-2.13).

This is the capability that distinguishes DevPulse from a delivery dashboard. A
deployment platform reporting SUCCESS is describing its own control plane, not
the health of the application it shipped. When monitoring disagrees, saying
"everything is healthy" is worse than saying nothing.

The engine is deterministic. It states what each system reported, whether they
disagree, and what remains unknown. It never asserts causation: temporal
proximity is evidence, not proof (ADR-011, rules.md 10).
"""

from __future__ import annotations

from datetime import timedelta
from statistics import median

from sqlalchemy.orm import Session

from app.services import providers
from app.models.events import Deployment, Incident, Repository, RuntimeObservation
from app.schemas.conflicts import (
    Conflict,
    ConflictListResponse,
    ConflictType,
    DeploymentConflictReport,
    MetricShift,
    RelationStrength,
    RuntimeComparison,
)
from app.services.deployments import DeploymentStatus, production_deployments
from app.services.timestamps import utc_now

#: How long either side of a deployment is compared. Long enough for a
#: regression to appear, short enough that unrelated drift does not dominate.
COMPARISON_WINDOW_MINUTES = 30

#: An incident opening within this window of a deployment is reported alongside
#: it. This is an association for a human to judge, not a causal finding.
INCIDENT_ASSOCIATION_MINUTES = 60

#: Relative worsening that counts as degradation rather than noise.
DEGRADATION_THRESHOLD_PCT = 50.0

#: Minimum samples on each side before a comparison is meaningful.
MIN_SAMPLES_PER_SIDE = 3

#: Metrics where a higher value is worse. Availability, for instance, is not.
_HIGHER_IS_WORSE = {"error_rate_pct", "latency_p95_ms", "restart_count"}


def _median_of(observations: list[RuntimeObservation]) -> float | None:
    return round(median([o.value for o in observations]), 3) if observations else None


def compare_runtime_around(
    db: Session, deployment: Deployment, window_minutes: int = COMPARISON_WINDOW_MINUTES
) -> RuntimeComparison:
    """Compare runtime metrics before a deployment against after it."""
    if not providers.runtime_available():
        return RuntimeComparison(
            available=False,
            unavailable_reason=(
                "No monitoring provider is connected, so DevPulse cannot determine "
                "whether this deployment affected production health."
            ),
            window_minutes=window_minutes,
            shifts=[],
        )

    anchor = deployment.finished_at or deployment.started_at
    before_start = anchor - timedelta(minutes=window_minutes)
    after_end = anchor + timedelta(minutes=window_minutes)

    observations = (
        db.query(RuntimeObservation)
        .filter(RuntimeObservation.repository_id == deployment.repository_id)
        .filter(RuntimeObservation.observed_at >= before_start)
        .filter(RuntimeObservation.observed_at <= after_end)
        .all()
    )
    if not observations:
        return RuntimeComparison(
            available=False,
            unavailable_reason=(
                "Monitoring is connected, but no runtime samples exist around this "
                "deployment."
            ),
            window_minutes=window_minutes,
            shifts=[],
        )

    shifts: list[MetricShift] = []
    for metric in sorted({o.metric for o in observations}):
        for_metric = [o for o in observations if o.metric == metric]
        before = [o for o in for_metric if o.observed_at < anchor]
        after = [o for o in for_metric if o.observed_at >= anchor]

        before_value = _median_of(before)
        after_value = _median_of(after)

        change_pct = None
        is_degradation = False
        if (
            before_value is not None
            and after_value is not None
            and before_value != 0
            and len(before) >= MIN_SAMPLES_PER_SIDE
            and len(after) >= MIN_SAMPLES_PER_SIDE
        ):
            change_pct = round((after_value - before_value) / abs(before_value) * 100, 1)
            worsened = change_pct if metric in _HIGHER_IS_WORSE else -change_pct
            is_degradation = worsened >= DEGRADATION_THRESHOLD_PCT

        shifts.append(
            MetricShift(
                metric=metric,
                before_value=before_value,
                after_value=after_value,
                change_pct=change_pct,
                sample_count_before=len(before),
                sample_count_after=len(after),
                is_degradation=is_degradation,
            )
        )

    return RuntimeComparison(
        available=True, unavailable_reason=None, window_minutes=window_minutes, shifts=shifts
    )


def _incidents_after(db: Session, deployment: Deployment) -> list[Incident]:
    anchor = deployment.finished_at or deployment.started_at
    return (
        db.query(Incident)
        .filter(Incident.repository_id == deployment.repository_id)
        .filter(Incident.started_at >= anchor)
        .filter(Incident.started_at <= anchor + timedelta(minutes=INCIDENT_ASSOCIATION_MINUTES))
        .order_by(Incident.started_at.asc())
        .all()
    )


def _detect(
    deployment: Deployment, runtime: RuntimeComparison, incidents: list[Incident]
) -> list[Conflict]:
    conflicts: list[Conflict] = []
    degradations = [shift for shift in runtime.shifts if shift.is_degradation]

    if deployment.status == DeploymentStatus.SUCCESS and degradations:
        evidence = [
            f"Deployment reported {deployment.status} to {deployment.environment}.",
            *[
                f"{shift.metric} moved from {shift.before_value} to {shift.after_value} "
                f"({shift.change_pct:+}%) across the {runtime.window_minutes} minutes "
                f"either side."
                for shift in degradations
            ],
        ]
        conflicts.append(
            Conflict(
                type=ConflictType.DEPLOYMENT_SUCCESS_RUNTIME_DEGRADED,
                strength=RelationStrength.CORRELATED,
                title="Deployment succeeded but runtime health degraded",
                description=(
                    "The deployment control plane reported success while monitoring "
                    "reported degradation. Control-plane success describes the rollout "
                    "mechanism, not the health of the application it shipped."
                ),
                evidence=evidence,
                unknowns=[
                    "Whether the deployment caused the degradation, or the two merely "
                    "coincided.",
                    "Whether an external dependency degraded at the same time.",
                ],
            )
        )

    if deployment.status == DeploymentStatus.SUCCESS and incidents:
        conflicts.append(
            Conflict(
                type=ConflictType.DEPLOYMENT_SUCCESS_INCIDENT_OPENED,
                strength=RelationStrength.POTENTIALLY_RELATED,
                title="An incident opened shortly after a successful deployment",
                description=(
                    f"{len(incidents)} incident(s) opened within "
                    f"{INCIDENT_ASSOCIATION_MINUTES} minutes of a deployment that "
                    "reported success."
                ),
                evidence=[
                    f'Incident "{incident.title}" opened at '
                    f"{incident.started_at.isoformat()} ({incident.status})."
                    for incident in incidents
                ],
                unknowns=[
                    "Whether the incident relates to this deployment at all.",
                    "Which change, if any, introduced the fault.",
                ],
            )
        )

    return conflicts


def build_reports(
    db: Session, repository_id: int | None = None, window_days: int = 30
) -> ConflictListResponse:
    since = utc_now() - timedelta(days=window_days)

    repositories = db.query(Repository).all()
    if repository_id is not None:
        repositories = [r for r in repositories if r.id == repository_id]

    reports: list[DeploymentConflictReport] = []
    for repo in repositories:
        for deployment in production_deployments(db, repo.id, since=since):
            runtime = compare_runtime_around(db, deployment)
            incidents = _incidents_after(db, deployment)
            conflicts = _detect(deployment, runtime, incidents)

            # Deployments with nothing to report are omitted; a page listing
            # every uneventful deployment obscures the ones that matter.
            if not conflicts and not incidents and not runtime.available:
                continue

            reports.append(
                DeploymentConflictReport(
                    deployment_id=deployment.id,
                    repository_full_name=repo.full_name,
                    environment=deployment.environment,
                    commit_sha=deployment.commit_sha,
                    deployment_status=deployment.status,
                    deployed_at=deployment.finished_at or deployment.started_at,
                    runtime=runtime,
                    incidents_after=len(incidents),
                    conflicts=conflicts,
                )
            )

    reports.sort(key=lambda report: report.deployed_at, reverse=True)
    conflict_count = sum(len(report.conflicts) for report in reports)

    runtime_available = providers.runtime_available()
    incidents_available = providers.incidents_available()
    unavailable_reason = None
    if not runtime_available and not incidents_available:
        unavailable_reason = (
            "Neither a monitoring provider nor an incident-management provider is "
            "connected. DevPulse can confirm that a deployment reported success, but "
            "cannot determine whether production stayed healthy afterwards. Conflict "
            "detection needs at least one of them."
        )

    return ConflictListResponse(
        reports=reports,
        conflict_count=conflict_count,
        runtime_available=runtime_available,
        incidents_available=incidents_available,
        unavailable_reason=unavailable_reason,
    )
