"""Deterministic bottleneck detection (PRD 2.9).

A bottleneck is not simply the slowest stage. A stage that always takes twenty
minutes and always has is a cost, not a constraint; a stage that used to take
five and now takes forty is where delivery is actually being lost. The engine
therefore combines four independent signals and shows its working.

No AI is involved (AGENTS.md 5-6). Every number here is reproducible from the
stored delivery traces.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.schemas.bottlenecks import (
    BottleneckResponse,
    ScoreComponent,
    StageAnalysis,
    StageBaseline,
)
from app.schemas.deliveries import StageStatus
from app.schemas.repositories import PipelineStage
from app.services.baselines import (
    Baseline,
    compare,
    regression_signal,
    summarise,
)
from app.services.deliveries import build_traces
from app.services.timestamps import utc_now

#: Below this, per-stage medians describe anecdotes rather than a pattern.
MIN_DELIVERIES_FOR_ANALYSIS = 3

#: Signal weights. They sum to 1.0, and are renormalised across whichever
#: signals are actually available so a missing baseline cannot silently deflate
#: a score. Latency dominates because a stage that consumes most of the delivery
#: time is a constraint even when it is behaving normally; regression is second
#: because a stage that has degraded is where the change happened.
WEIGHT_LATENCY = 0.40
WEIGHT_REGRESSION = 0.25
WEIGHT_FAILURE = 0.20
WEIGHT_FREQUENCY = 0.15

IMPACT_HIGH_SCORE = 60.0
IMPACT_MEDIUM_SCORE = 35.0

#: Stages whose duration is meaningful. SOURCE is instantaneous, and the
#: unobserved stages have no timings at all.
_TIMED_STAGES = (PipelineStage.REVIEW, PipelineStage.CI, PipelineStage.DEPLOYMENT)


def _impact(score: float) -> str:
    if score >= IMPACT_HIGH_SCORE:
        return "HIGH"
    if score >= IMPACT_MEDIUM_SCORE:
        return "MEDIUM"
    return "LOW"


def _to_stage_baseline(baseline: Baseline) -> StageBaseline:
    return StageBaseline(
        sample_count=baseline.sample_count,
        median_minutes=baseline.median_value,
        p90_minutes=baseline.p90_value,
    )


def _durations(traces, stage: PipelineStage) -> list[float]:
    values: list[float] = []
    for _, stages in traces:
        entry = next((s for s in stages if s.stage is stage), None)
        if entry and entry.duration_minutes is not None:
            values.append(entry.duration_minutes)
    return values


def _failure_rate(traces, stage: PipelineStage) -> tuple[float, int]:
    observed = 0
    failed = 0
    for _, stages in traces:
        entry = next((s for s in stages if s.stage is stage), None)
        if entry is None or entry.status is StageStatus.NOT_OBSERVED:
            continue
        observed += 1
        if entry.status is StageStatus.FAILED:
            failed += 1
    return (round(failed / observed * 100, 1) if observed else 0.0), failed


def _analyse_stage(
    stage: PipelineStage, current_traces, baseline_traces, total_stage_minutes: float
) -> StageAnalysis | None:
    current_durations = _durations(current_traces, stage)
    if not current_durations:
        return None

    comparison = compare(current_durations, _durations(baseline_traces, stage))
    failure_rate_pct, _ = _failure_rate(current_traces, stage)

    stage_total = sum(current_durations)
    latency_contribution_pct = (
        round(stage_total / total_stage_minutes * 100, 1) if total_stage_minutes else 0.0
    )
    affected = len(current_durations)
    total = len(current_traces)
    frequency_pct = round(affected / total * 100, 1) if total else 0.0

    components: list[ScoreComponent] = [
        ScoreComponent(
            name="Latency contribution",
            value=latency_contribution_pct,
            weight=WEIGHT_LATENCY,
            contribution=0.0,
            explanation=(
                f"This stage accounts for {latency_contribution_pct}% of all measured "
                f"delivery time in the window."
            ),
        ),
        ScoreComponent(
            name="Failure impact",
            value=failure_rate_pct,
            weight=WEIGHT_FAILURE,
            contribution=0.0,
            explanation=f"{failure_rate_pct}% of observations of this stage failed.",
        ),
        ScoreComponent(
            name="Frequency",
            value=frequency_pct,
            weight=WEIGHT_FREQUENCY,
            contribution=0.0,
            explanation=f"{affected} of {total} deliveries passed through this stage.",
        ),
    ]

    # The regression signal only participates when a baseline exists. Scoring a
    # missing baseline as zero would penalise a genuinely constrained stage
    # simply for lacking history, so the weight is redistributed instead.
    if comparison.change_pct is not None:
        components.insert(
            1,
            ScoreComponent(
                name="Historical regression",
                value=regression_signal(comparison.change_pct),
                weight=WEIGHT_REGRESSION,
                contribution=0.0,
                explanation=(
                    f"Median moved from {comparison.baseline.median_value}m to "
                    f"{comparison.current.median_value}m ({comparison.change_pct:+}%)."
                ),
            ),
        )

    total_weight = sum(component.weight for component in components)
    scored = [
        component.model_copy(
            update={
                "weight": round(component.weight / total_weight, 3),
                "contribution": round(component.value * component.weight / total_weight, 1),
            }
        )
        for component in components
    ]
    score = round(sum(component.contribution for component in scored), 1)

    evidence = [
        f"Median duration {comparison.current.median_value}m across {affected} deliveries "
        f"(p90 {comparison.current.p90_value}m).",
        f"Accounts for {latency_contribution_pct}% of measured delivery time.",
    ]
    if comparison.change_pct is not None:
        direction = "slower" if comparison.change_pct > 0 else "faster"
        evidence.append(
            f"{abs(comparison.change_pct)}% {direction} than the previous period "
            f"({comparison.baseline.median_value}m across "
            f"{comparison.baseline.sample_count} deliveries)."
        )
    elif comparison.reason:
        evidence.append(f"No historical comparison: {comparison.reason}")
    if failure_rate_pct > 0:
        evidence.append(f"{failure_rate_pct}% of observations of this stage failed.")

    return StageAnalysis(
        stage=stage,
        score=score,
        impact=_impact(score),
        current=_to_stage_baseline(comparison.current),
        baseline=_to_stage_baseline(comparison.baseline),
        change_pct=comparison.change_pct,
        is_regression=comparison.is_regression,
        latency_contribution_pct=latency_contribution_pct,
        failure_rate_pct=failure_rate_pct,
        affected_deliveries=affected,
        total_deliveries=total,
        components=scored,
        evidence=evidence,
    )


def detect_bottlenecks(
    db: Session, repository_id: int | None = None, window_days: int = 30
) -> BottleneckResponse:
    now = utc_now()
    window_start = now - timedelta(days=window_days)
    # The baseline is the equally long period immediately before the window, so
    # like is compared with like rather than against all of history.
    baseline_start = window_start - timedelta(days=window_days)

    current_traces = build_traces(db, repository_id, since=window_start)
    baseline_traces = build_traces(db, repository_id, since=baseline_start, until=window_start)

    if len(current_traces) < MIN_DELIVERIES_FOR_ANALYSIS:
        return BottleneckResponse(
            window_days=window_days,
            deliveries_analysed=len(current_traces),
            primary_bottleneck=None,
            stages=[],
            unavailable_reason=(
                f"Only {len(current_traces)} delivery(s) in the last {window_days} days. "
                f"At least {MIN_DELIVERIES_FOR_ANALYSIS} are needed before per-stage "
                "medians describe a pattern rather than an anecdote."
            ),
        )

    total_stage_minutes = sum(
        sum(_durations(current_traces, stage)) for stage in _TIMED_STAGES
    )

    analyses = [
        analysis
        for analysis in (
            _analyse_stage(stage, current_traces, baseline_traces, total_stage_minutes)
            for stage in _TIMED_STAGES
        )
        if analysis is not None
    ]
    analyses.sort(key=lambda analysis: analysis.score, reverse=True)

    return BottleneckResponse(
        window_days=window_days,
        deliveries_analysed=len(current_traces),
        primary_bottleneck=analyses[0] if analyses else None,
        stages=analyses,
        unavailable_reason=None if analyses else "No stage reported a measurable duration.",
    )
