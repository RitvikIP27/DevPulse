"""API contracts for engineering health scoring (PRD 2.14)."""

from enum import Enum

from pydantic import BaseModel


class HealthDimension(str, Enum):
    DELIVERY = "DELIVERY"          # how fast and how often changes reach production
    STABILITY = "STABILITY"        # how often they break, and how fast they recover
    PIPELINE = "PIPELINE"          # whether CI itself is reliable and quick
    RUNTIME = "RUNTIME"            # whether production stays healthy afterwards
    OBSERVABILITY = "OBSERVABILITY"  # how much of the picture DevPulse can even see


class DimensionInput(BaseModel):
    """One measurement feeding a dimension, with how it was turned into points."""

    label: str
    value: float | None
    unit: str | None
    points: float | None
    max_points: float
    explanation: str


class DimensionScore(BaseModel):
    dimension: HealthDimension
    score: float | None
    #: Share of the dimension's inputs that could actually be measured.
    coverage_pct: float
    unavailable_reason: str | None
    inputs: list[DimensionInput]


class ServiceHealth(BaseModel):
    service: str
    repository_full_name: str
    overall_score: float | None
    #: Overall is the mean of scorable dimensions only, so this says how many.
    dimensions_scored: int
    dimensions_total: int
    unavailable_reason: str | None
    dimensions: list[DimensionScore]


class HealthResponse(BaseModel):
    window_days: int
    services: list[ServiceHealth]
