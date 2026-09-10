from pydantic import BaseModel


class ServiceDoraMetrics(BaseModel):
    """The five current DORA metrics for one service.

    Every metric is nullable. A metric that cannot be computed from the
    available data reports ``None`` with a reason, rather than a zero that would
    read as a healthy result (PRD 2.7, rules.md 11).
    """

    service: str

    #: GITHUB_DEPLOYMENTS | CONFIGURED_WORKFLOW | NONE
    deployment_source: str
    #: Why deployment-derived metrics are unavailable, when they are.
    unavailable_reason: str | None = None

    deployment_frequency_per_week: float | None
    lead_time_hours: float | None
    change_failure_rate_pct: float | None
    failed_deployment_recovery_hours: float | None
    deployment_rework_rate_pct: float | None

    total_deployments: int
    total_failures: int

    class Config:
        from_attributes = True


class DoraMetricsResponse(BaseModel):
    window_days: int
    services: list[ServiceDoraMetrics]
