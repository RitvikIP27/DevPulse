from pydantic import BaseModel


class ServiceDoraMetrics(BaseModel):
    service: str
    deployment_frequency_per_week: float
    lead_time_hours: float | None
    change_failure_rate_pct: float
    mttr_hours: float | None
    total_deployments: int
    total_failures: int

    class Config:
        from_attributes = True


class DoraMetricsResponse(BaseModel):
    window_days: int
    services: list[ServiceDoraMetrics]
