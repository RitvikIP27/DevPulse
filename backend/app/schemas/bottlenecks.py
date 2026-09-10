"""API contracts for deterministic bottleneck detection (PRD 2.9)."""

from pydantic import BaseModel

from app.schemas.repositories import PipelineStage


class ScoreComponent(BaseModel):
    """One weighted signal contributing to a bottleneck score.

    Exposed individually because PRD constraint 9 requires every score to be
    explainable from its inputs — a number no one can decompose is not evidence.
    """

    name: str
    value: float
    weight: float
    contribution: float
    explanation: str


class StageBaseline(BaseModel):
    sample_count: int
    median_minutes: float | None
    p90_minutes: float | None


class StageAnalysis(BaseModel):
    stage: PipelineStage
    score: float
    impact: str  # HIGH / MEDIUM / LOW
    current: StageBaseline
    baseline: StageBaseline
    change_pct: float | None
    is_regression: bool
    latency_contribution_pct: float
    failure_rate_pct: float
    affected_deliveries: int
    total_deliveries: int
    components: list[ScoreComponent]
    evidence: list[str]


class BottleneckResponse(BaseModel):
    window_days: int
    deliveries_analysed: int
    primary_bottleneck: StageAnalysis | None
    stages: list[StageAnalysis]
    #: Present when the engine declines to draw a conclusion.
    unavailable_reason: str | None = None
