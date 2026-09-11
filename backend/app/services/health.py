"""Engineering health scoring (PRD 2.14, Stage 18).

Every score here is the sum of named, bounded inputs, and every input carries
the measurement it came from and the sentence explaining how it became points.
PRD constraint 9 requires it, and there is a practical reason too: a composite
number nobody can decompose gets argued with rather than acted on.

A dimension with no measurable inputs scores `null`, not zero. Zero means "we
measured, and it is bad"; null means "we cannot see". Conflating them is the
failure the Stage 0 audit found, where an empty repository ranked as the
healthiest service.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.events import Repository
from app.schemas.health import (
    DimensionInput,
    DimensionScore,
    HealthDimension,
    HealthResponse,
    ServiceHealth,
)
from app.schemas.repositories import CoverageStatus
from app.services.bottlenecks import detect_bottlenecks
from app.services.conflicts import build_reports
from app.services.dora_metrics import compute_service_metrics
from app.services.repositories import list_repositories

# --- Scoring bands -----------------------------------------------------------
# Thresholds are stated as named constants rather than inline numbers so the
# rubric is visible and arguable (rules.md 3). They are deliberately generous:
# the aim is to separate "healthy" from "needs attention", not to rank teams.

DEPLOY_FREQUENCY_GOOD_PER_WEEK = 3.0
DEPLOY_FREQUENCY_FAIR_PER_WEEK = 1.0

LEAD_TIME_GOOD_HOURS = 24.0
LEAD_TIME_FAIR_HOURS = 168.0  # one week

CHANGE_FAIL_GOOD_PCT = 15.0
CHANGE_FAIL_FAIR_PCT = 30.0

RECOVERY_GOOD_HOURS = 1.0
RECOVERY_FAIR_HOURS = 24.0

CI_FAILURE_GOOD_PCT = 10.0
CI_FAILURE_FAIR_PCT = 25.0

POINTS_PER_INPUT = 100.0


def _band(value: float | None, good: float, fair: float, lower_is_better: bool) -> float | None:
    """Map a measurement onto 0-100 using two thresholds.

    Linear between the bands rather than a step function, so a service just
    outside "good" does not look identical to one far outside it.
    """
    if value is None:
        return None

    if lower_is_better:
        if value <= good:
            return 100.0
        if value >= fair:
            return max(0.0, 40.0 * (1 - (value - fair) / max(fair, 1.0)))
        return 100.0 - 60.0 * (value - good) / max(fair - good, 1e-9)

    if value >= good:
        return 100.0
    if value <= fair:
        return max(0.0, 40.0 * value / max(fair, 1e-9))
    return 40.0 + 60.0 * (value - fair) / max(good - fair, 1e-9)


def _input(
    label: str, value: float | None, unit: str | None, points: float | None, explanation: str
) -> DimensionInput:
    return DimensionInput(
        label=label,
        value=round(value, 2) if value is not None else None,
        unit=unit,
        points=round(points, 1) if points is not None else None,
        max_points=POINTS_PER_INPUT,
        explanation=explanation,
    )


def _score_dimension(
    dimension: HealthDimension, inputs: list[DimensionInput], unavailable_reason: str
) -> DimensionScore:
    scorable = [i for i in inputs if i.points is not None]
    coverage_pct = round(len(scorable) / len(inputs) * 100, 1) if inputs else 0.0

    return DimensionScore(
        dimension=dimension,
        score=round(sum(i.points for i in scorable) / len(scorable), 1) if scorable else None,
        coverage_pct=coverage_pct,
        unavailable_reason=None if scorable else unavailable_reason,
        inputs=inputs,
    )


def compute_service_health(db: Session, repo: Repository, window_days: int) -> ServiceHealth:
    dora = compute_service_metrics(db, repo, window_days)
    bottlenecks = detect_bottlenecks(db, repository_id=repo.id, window_days=window_days)
    coverage = next(
        (s.coverage for s in list_repositories(db).repositories if s.id == repo.id), None
    )

    # --- DELIVERY: how fast and how often changes reach production ---
    frequency_points = _band(
        dora.deployment_frequency_per_week,
        DEPLOY_FREQUENCY_GOOD_PER_WEEK, DEPLOY_FREQUENCY_FAIR_PER_WEEK,
        lower_is_better=False,
    )
    lead_points = _band(
        dora.lead_time_hours, LEAD_TIME_GOOD_HOURS, LEAD_TIME_FAIR_HOURS,
        lower_is_better=True,
    )
    delivery = _score_dimension(
        HealthDimension.DELIVERY,
        [
            _input(
                "Deployment frequency", dora.deployment_frequency_per_week, "/week",
                frequency_points,
                f"{DEPLOY_FREQUENCY_GOOD_PER_WEEK}/week or more scores full marks; "
                f"{DEPLOY_FREQUENCY_FAIR_PER_WEEK}/week is the lower band.",
            ),
            _input(
                "Change lead time", dora.lead_time_hours, "hours", lead_points,
                f"Under {LEAD_TIME_GOOD_HOURS}h scores full marks; "
                f"{LEAD_TIME_FAIR_HOURS}h is the lower band.",
            ),
        ],
        "No deployment source is configured, so delivery speed cannot be measured.",
    )

    # --- STABILITY: how often changes break, and how fast they recover ---
    fail_points = _band(
        dora.change_failure_rate_pct, CHANGE_FAIL_GOOD_PCT, CHANGE_FAIL_FAIR_PCT,
        lower_is_better=True,
    )
    recovery_points = _band(
        dora.failed_deployment_recovery_hours, RECOVERY_GOOD_HOURS, RECOVERY_FAIR_HOURS,
        lower_is_better=True,
    )
    stability = _score_dimension(
        HealthDimension.STABILITY,
        [
            _input(
                "Change fail rate", dora.change_failure_rate_pct, "%", fail_points,
                f"Under {CHANGE_FAIL_GOOD_PCT}% scores full marks; "
                f"{CHANGE_FAIL_FAIR_PCT}% is the lower band.",
            ),
            _input(
                "Failed deployment recovery", dora.failed_deployment_recovery_hours,
                "hours", recovery_points,
                f"Under {RECOVERY_GOOD_HOURS}h scores full marks; "
                f"{RECOVERY_FAIR_HOURS}h is the lower band.",
            ),
        ],
        "No concluded production deployments, so stability cannot be measured.",
    )

    # --- PIPELINE: is CI itself reliable and quick ---
    ci_stage = next((s for s in bottlenecks.stages if s.stage.value == "CI"), None)
    ci_failure_points = _band(
        ci_stage.failure_rate_pct if ci_stage else None,
        CI_FAILURE_GOOD_PCT, CI_FAILURE_FAIR_PCT, lower_is_better=True,
    )
    # A regression is penalised on top of the absolute rate: a pipeline that is
    # degrading is a different problem from one that is merely slow.
    regression_points = None
    if ci_stage is not None and ci_stage.change_pct is not None:
        regression_points = max(0.0, 100.0 - max(0.0, ci_stage.change_pct) / 2.0)

    pipeline = _score_dimension(
        HealthDimension.PIPELINE,
        [
            _input(
                "CI failure rate", ci_stage.failure_rate_pct if ci_stage else None, "%",
                ci_failure_points,
                f"Under {CI_FAILURE_GOOD_PCT}% scores full marks; "
                f"{CI_FAILURE_FAIR_PCT}% is the lower band.",
            ),
            _input(
                "CI duration trend",
                ci_stage.change_pct if ci_stage else None, "% vs baseline",
                regression_points,
                "A stable or improving median scores full marks; a doubling scores 50.",
            ),
        ],
        "No CI activity in this window, so pipeline health cannot be measured.",
    )

    # --- RUNTIME: does production stay healthy after a deployment ---
    reports = build_reports(db, repository_id=repo.id, window_days=window_days)
    runtime_reports = [r for r in reports.reports if r.runtime.available]
    runtime_points = None
    clean = None
    if runtime_reports:
        clean = sum(1 for r in runtime_reports if not r.conflicts)
        runtime_points = clean / len(runtime_reports) * 100

    runtime = _score_dimension(
        HealthDimension.RUNTIME,
        [
            _input(
                "Deployments without runtime conflict",
                (clean / len(runtime_reports) * 100) if runtime_reports else None, "%",
                runtime_points,
                "Share of observed deployments where runtime did not degrade.",
            )
        ],
        "No monitoring provider is connected, so runtime health cannot be measured.",
    )

    # --- OBSERVABILITY: how much of the picture DevPulse can even see ---
    available_stages = (
        sum(1 for s in coverage.stages if s.status is CoverageStatus.AVAILABLE)
        if coverage else 0
    )
    total_stages = len(coverage.stages) if coverage else 0
    observability_points = (
        available_stages / total_stages * 100 if total_stages else None
    )
    observability = _score_dimension(
        HealthDimension.OBSERVABILITY,
        [
            _input(
                "Pipeline stages with data", observability_points, "%",
                observability_points,
                f"{available_stages} of {total_stages} logical delivery stages report data. "
                "This dimension scores DevPulse's visibility, not the team.",
            )
        ],
        "Coverage could not be determined.",
    )

    dimensions = [delivery, stability, pipeline, runtime, observability]
    scored = [d for d in dimensions if d.score is not None]

    return ServiceHealth(
        service=repo.display_name or repo.full_name,
        repository_full_name=repo.full_name,
        # The mean of scorable dimensions only. Treating an unmeasurable
        # dimension as zero would punish a team for DevPulse's blind spots.
        overall_score=round(sum(d.score for d in scored) / len(scored), 1) if scored else None,
        dimensions_scored=len(scored),
        dimensions_total=len(dimensions),
        unavailable_reason=(
            None if scored else "No dimension has enough data to score."
        ),
        dimensions=dimensions,
    )


def compute_health(db: Session, window_days: int = 30) -> HealthResponse:
    services = [
        compute_service_health(db, repo, window_days) for repo in db.query(Repository).all()
    ]
    # Lowest score first — the point of the page is to surface what needs work.
    # Unscorable services sort last: they are not healthy, they are unknown.
    services.sort(key=lambda s: (s.overall_score is None, s.overall_score or 0))
    return HealthResponse(window_days=window_days, services=services)
