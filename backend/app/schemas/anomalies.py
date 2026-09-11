"""API contracts for anomaly detection (PRD 2.10)."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class AnomalyDirection(str, Enum):
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"


class AnomalySeverity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AnomalyOut(BaseModel):
    id: int
    repository_full_name: str
    metric: str
    stage: str | None
    direction: AnomalyDirection
    severity: AnomalySeverity

    current_value: float
    baseline_value: float
    change_pct: float
    sample_count: int
    baseline_sample_count: int

    window_start: datetime
    window_end: datetime
    detected_at: datetime
    acknowledged_at: datetime | None

    evidence: list[str]


class AnomalyListResponse(BaseModel):
    anomalies: list[AnomalyOut]
    window_days: int
    detected_now: int
    unavailable_reason: str | None = None
