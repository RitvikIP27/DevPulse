"""Deterministic anomaly detection (PRD 2.10).

An anomaly is a metric that has moved far enough from its own recent history to
be worth a human's attention. The statistics come from services/baselines.py
rather than being reimplemented here — one definition of "median", "baseline"
and "regression" for the whole product, so a number shown on the Bottlenecks
page and the same number shown here can never disagree.

Detection is deliberately conservative. A monitoring surface that cries wolf is
ignored, and an ignored surface is worse than none: it costs attention and
returns nothing.
"""

from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.events import Anomaly, Deployment, Repository
from app.schemas.anomalies import (
    AnomalyDirection,
    AnomalyListResponse,
    AnomalyOut,
    AnomalySeverity,
)
from app.schemas.repositories import PipelineStage
from app.services.baselines import MIN_BASELINE_SAMPLES, compare
from app.services.deliveries import build_traces
from app.services.deployments import DeploymentStatus, production_deployments
from app.services.timestamps import utc_now

logger = get_logger(__name__)

#: Severity thresholds on absolute percentage change. Chosen so that HIGH means
#: "this roughly tripled or worse", which is hard to dismiss as noise.
SEVERITY_HIGH_PCT = 200.0
SEVERITY_MEDIUM_PCT = 75.0

#: Below this, a change is not reported at all. Matches the regression threshold
#: used by the bottleneck engine so the two surfaces agree.
MIN_REPORTABLE_PCT = 25.0

#: Metrics where a rise is the bad direction.
_INCREASE_IS_BAD = {
    "review_duration_minutes",
    "ci_duration_minutes",
    "deployment_failure_rate_pct",
}

_STAGE_METRICS = {
    PipelineStage.REVIEW: "review_duration_minutes",
    PipelineStage.CI: "ci_duration_minutes",
}


def _severity(change_pct: float) -> AnomalySeverity:
    magnitude = abs(change_pct)
    if magnitude >= SEVERITY_HIGH_PCT:
        return AnomalySeverity.HIGH
    if magnitude >= SEVERITY_MEDIUM_PCT:
        return AnomalySeverity.MEDIUM
    return AnomalySeverity.LOW


def _stage_durations(traces, stage: PipelineStage) -> list[float]:
    values = []
    for _, stages in traces:
        entry = next((s for s in stages if s.stage is stage), None)
        if entry and entry.duration_minutes is not None:
            values.append(entry.duration_minutes)
    return values


def _deployment_failure_rate(deployments) -> float | None:
    concluded = [
        d for d in deployments
        if d.status in (DeploymentStatus.SUCCESS, DeploymentStatus.FAILED)
    ]
    if not concluded:
        return None
    failed = sum(1 for d in concluded if d.status == DeploymentStatus.FAILED)
    return failed / len(concluded) * 100


def _record(
    db: Session,
    repo: Repository,
    *,
    metric: str,
    stage: str | None,
    comparison,
    window_start,
    window_end,
    evidence: list[str],
) -> Anomaly | None:
    """Persist an anomaly, or update the existing one for the same window.

    Keyed on (repository, metric, window_start) so re-running detection refreshes
    rather than duplicating — detection is expected to run repeatedly.
    """
    change_pct = comparison.change_pct
    if change_pct is None or abs(change_pct) < MIN_REPORTABLE_PCT:
        return None

    direction = (
        AnomalyDirection.INCREASE if change_pct > 0 else AnomalyDirection.DECREASE
    )
    # Only a move in the harmful direction is an anomaly. CI getting faster is
    # good news, and reporting it as an anomaly would train people to ignore the
    # page (rules.md 11 in spirit: do not manufacture alarm).
    if metric in _INCREASE_IS_BAD and direction is AnomalyDirection.DECREASE:
        return None

    existing = (
        db.query(Anomaly)
        .filter_by(repository_id=repo.id, metric=metric, window_start=window_start)
        .first()
    )
    values = {
        "stage": stage,
        "direction": direction.value,
        "severity": _severity(change_pct).value,
        "current_value": comparison.current.median_value,
        "baseline_value": comparison.baseline.median_value,
        "change_pct": change_pct,
        "sample_count": comparison.current.sample_count,
        "baseline_sample_count": comparison.baseline.sample_count,
        "window_end": window_end,
        "detected_at": utc_now(),
        "evidence_json": json.dumps(evidence),
    }

    if existing:
        for field, value in values.items():
            setattr(existing, field, value)
        return existing

    anomaly = Anomaly(
        repository_id=repo.id, metric=metric, window_start=window_start, **values
    )
    db.add(anomaly)
    return anomaly


def detect_anomalies(
    db: Session, repository_id: int | None = None, window_days: int = 7
) -> int:
    """Run detection and persist results. Returns how many were recorded.

    The window is short by default: an anomaly is about something changing
    recently, and a 30-day window would dilute a three-day regression into
    invisibility.
    """
    now = utc_now()
    # Truncated to the hour. The uniqueness key includes window_start, so a
    # microsecond-precise value would make every run a different window and
    # insert a duplicate row instead of refreshing the existing one. Detection
    # runs on every page load, so idempotence is a requirement, not a nicety.
    window_start = (now - timedelta(days=window_days)).replace(
        minute=0, second=0, microsecond=0
    )
    baseline_start = window_start - timedelta(days=window_days * 3)

    repositories = db.query(Repository).all()
    if repository_id is not None:
        repositories = [r for r in repositories if r.id == repository_id]

    detected = 0
    for repo in repositories:
        current_traces = build_traces(db, repo.id, since=window_start)
        baseline_traces = build_traces(
            db, repo.id, since=baseline_start, until=window_start
        )

        for stage, metric in _STAGE_METRICS.items():
            comparison = compare(
                _stage_durations(current_traces, stage),
                _stage_durations(baseline_traces, stage),
            )
            if comparison.change_pct is None:
                continue

            evidence = [
                f"Median {stage.value.lower()} duration is "
                f"{comparison.current.median_value}m across "
                f"{comparison.current.sample_count} deliveries.",
                f"The preceding {window_days * 3} days had a median of "
                f"{comparison.baseline.median_value}m across "
                f"{comparison.baseline.sample_count} deliveries.",
                f"That is a change of {comparison.change_pct:+}%.",
            ]
            if _record(
                db, repo, metric=metric, stage=stage.value, comparison=comparison,
                window_start=window_start, window_end=now, evidence=evidence,
            ):
                detected += 1

        # Deployment failure rate is a rate, not a duration, so it is compared
        # as a single-value series against the baseline period.
        current_rate = _deployment_failure_rate(
            production_deployments(db, repo.id, since=window_start)
        )
        baseline_deployments = [
            d for d in production_deployments(db, repo.id, since=baseline_start)
            if d.started_at < window_start
        ]
        baseline_rate = _deployment_failure_rate(baseline_deployments)

        if (
            current_rate is not None
            and baseline_rate is not None
            and len(baseline_deployments) >= MIN_BASELINE_SAMPLES
        ):
            comparison = compare([current_rate], [baseline_rate] * MIN_BASELINE_SAMPLES)
            if comparison.change_pct is not None:
                evidence = [
                    f"Production deployment failure rate is {round(current_rate, 1)}%.",
                    f"The preceding period was {round(baseline_rate, 1)}% across "
                    f"{len(baseline_deployments)} deployments.",
                ]
                if _record(
                    db, repo, metric="deployment_failure_rate_pct", stage="DEPLOYMENT",
                    comparison=comparison, window_start=window_start, window_end=now,
                    evidence=evidence,
                ):
                    detected += 1

    db.commit()
    logger.info("anomaly detection complete window_days=%d detected=%d", window_days, detected)
    return detected


def list_anomalies(
    db: Session, repository_id: int | None = None, window_days: int = 7, refresh: bool = True
) -> AnomalyListResponse:
    detected = detect_anomalies(db, repository_id, window_days) if refresh else 0

    names = {repo.id: repo.full_name for repo in db.query(Repository).all()}
    query = db.query(Anomaly)
    if repository_id is not None:
        query = query.filter(Anomaly.repository_id == repository_id)

    rows = query.order_by(Anomaly.detected_at.desc()).limit(100).all()
    severity_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    rows.sort(key=lambda row: (severity_rank.get(row.severity, 3), -abs(row.change_pct)))

    anomalies = [
        AnomalyOut(
            id=row.id,
            repository_full_name=names.get(row.repository_id, "unknown"),
            metric=row.metric,
            stage=row.stage,
            direction=row.direction,
            severity=row.severity,
            current_value=row.current_value,
            baseline_value=row.baseline_value,
            change_pct=row.change_pct,
            sample_count=row.sample_count,
            baseline_sample_count=row.baseline_sample_count,
            window_start=row.window_start,
            window_end=row.window_end,
            detected_at=row.detected_at,
            acknowledged_at=row.acknowledged_at,
            evidence=json.loads(row.evidence_json),
        )
        for row in rows
    ]

    reason = None
    if not anomalies:
        reason = (
            f"No metric deviated by more than {MIN_REPORTABLE_PCT}% from its "
            f"baseline, or there is not yet {MIN_BASELINE_SAMPLES} deliveries of "
            "history to compare against."
        )

    return AnomalyListResponse(
        anomalies=anomalies,
        window_days=window_days,
        detected_now=detected,
        unavailable_reason=reason,
    )


def acknowledge(db: Session, anomaly_id: int) -> Anomaly | None:
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if anomaly is None:
        return None
    anomaly.acknowledged_at = utc_now()
    db.commit()
    return anomaly
