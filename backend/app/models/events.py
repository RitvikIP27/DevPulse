from sqlalchemy import (
    Boolean,
    Float,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Repository(Base):
    """One row per tracked service/repo, e.g. 'your-org/payments-service'."""

    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, unique=True, index=True, nullable=False)  # owner/repo
    display_name = Column(String, nullable=True)  # e.g. "payments-service"

    pull_requests = relationship("PullRequest", back_populates="repository")
    workflow_runs = relationship("WorkflowRun", back_populates="repository")
    sync_jobs = relationship("SyncJob", back_populates="repository")


class PullRequest(Base):
    """A pull request, and the commits that identify the change it carried.

    ``merge_commit_sha`` is the important field for delivery correlation: it is
    the commit that actually landed on the base branch, and therefore the commit
    a later build or deployment will report having shipped.
    """

    __tablename__ = "pull_requests"
    __table_args__ = (
        # The connector upserts by (repository, number). Without this constraint
        # the read-then-write was racy and concurrent syncs could duplicate rows.
        UniqueConstraint("repository_id", "github_pr_number", name="uq_pull_request_number"),
        Index("ix_pull_requests_merge_commit_sha", "merge_commit_sha"),
        Index("ix_pull_requests_head_sha", "head_sha"),
    )

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    github_pr_number = Column(Integer, nullable=False)
    title = Column(String, nullable=True)
    opened_at = Column(DateTime, nullable=False)
    merged_at = Column(DateTime, nullable=True)
    is_merged = Column(Boolean, default=False)

    # --- correlation keys -------------------------------------------------
    head_sha = Column(String, nullable=True)
    merge_commit_sha = Column(String, nullable=True)
    base_branch = Column(String, nullable=True)
    head_branch = Column(String, nullable=True)

    # --- provenance -------------------------------------------------------
    author_login = Column(String, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    html_url = Column(String, nullable=True)

    repository = relationship("Repository", back_populates="pull_requests")


class WorkflowRun(Base):
    """A CI/CD run reported by GitHub Actions.

    ``head_sha`` is the join key that makes cross-system correlation possible:
    it is the same commit identifier a build, artifact or deployment will carry,
    and is what lets a run be attached to the change it was testing.

    ``event`` and ``head_branch`` matter because they are how a deployment-like
    run will eventually be told apart from a pull-request check.
    """

    __tablename__ = "workflow_runs"
    __table_args__ = (Index("ix_workflow_runs_head_sha", "head_sha"),)

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    github_run_id = Column(String, unique=True, nullable=False)
    workflow_name = Column(String, nullable=False)
    conclusion = Column(String, nullable=True)  # success / failure / cancelled / null
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # --- correlation keys -------------------------------------------------
    head_sha = Column(String, nullable=True)
    head_branch = Column(String, nullable=True)
    event = Column(String, nullable=True)  # push / pull_request / workflow_dispatch / ...

    # --- provenance -------------------------------------------------------
    status = Column(String, nullable=True)  # queued / in_progress / completed
    run_attempt = Column(Integer, nullable=True)
    html_url = Column(String, nullable=True)

    repository = relationship("Repository", back_populates="workflow_runs")


class DeploymentRule(Base):
    """Declares which CI workflow represents a deployment for a repository.

    DevPulse prefers a real deployment provider. When none exists — no GitHub
    Deployments, no ArgoCD — the alternative is either to guess, or to let a
    human state the mapping. ADR-009 chooses explicit configuration: guessing is
    what produced the MVP's inflated deployment counts.

    A rule turns matching workflow runs into Deployment records. Without a rule,
    and without a deployment provider, deployment-derived metrics report as
    unavailable rather than falling back to counting every CI run.
    """

    __tablename__ = "deployment_rules"
    __table_args__ = (
        UniqueConstraint("repository_id", "workflow_name_pattern", "environment",
                         name="uq_deployment_rule"),
    )

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    #: Case-insensitive substring matched against the workflow name.
    workflow_name_pattern = Column(String, nullable=False)
    environment = Column(String, nullable=False, default="production")
    is_production = Column(Boolean, nullable=False, default=True)

    repository = relationship("Repository")


class Deployment(Base):
    """A deployment of a specific commit into a specific environment.

    Deliberately separate from WorkflowRun. A workflow run is a CI fact; a
    deployment is a delivery fact. Conflating them is ADR-010, and the audit
    measured the cost: deployment frequency overstated roughly 5.7x.
    """

    __tablename__ = "deployments"
    __table_args__ = (
        UniqueConstraint("repository_id", "provider", "external_id", name="uq_deployment_external"),
        Index("ix_deployments_commit_sha", "commit_sha"),
    )

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)

    #: github_deployments (authoritative) or configured_workflow (declared).
    provider = Column(String, nullable=False)
    external_id = Column(String, nullable=False)

    environment = Column(String, nullable=False)
    is_production = Column(Boolean, nullable=False, default=True)

    commit_sha = Column(String, nullable=True)
    status = Column(String, nullable=False)  # SUCCESS / FAILED / IN_PROGRESS
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    url = Column(String, nullable=True)

    repository = relationship("Repository")


class RuntimeObservation(Base):
    """A runtime health measurement for a service at a point in time.

    Stored as a time series so a deployment can be compared against the window
    before it and the window after it. Without this, DevPulse can report that a
    deployment succeeded but never whether production stayed healthy.
    """

    __tablename__ = "runtime_observations"
    __table_args__ = (Index("ix_runtime_observations_repo_time", "repository_id", "observed_at"),)

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    provider = Column(String, nullable=False)  # e.g. "prometheus"
    environment = Column(String, nullable=False, default="production")

    #: error_rate_pct, latency_p95_ms, availability_pct, restart_count ...
    metric = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    observed_at = Column(DateTime, nullable=False)

    repository = relationship("Repository")


class Incident(Base):
    """An operational incident, from an incident-management provider."""

    __tablename__ = "incidents"
    __table_args__ = (
        UniqueConstraint("repository_id", "provider", "external_id", name="uq_incident_external"),
        Index("ix_incidents_started_at", "started_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    provider = Column(String, nullable=False)  # e.g. "pagerduty"
    external_id = Column(String, nullable=False)

    title = Column(String, nullable=True)
    severity = Column(String, nullable=True)
    status = Column(String, nullable=False)  # TRIGGERED / ACKNOWLEDGED / RESOLVED
    started_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    url = Column(String, nullable=True)

    repository = relationship("Repository")


class RcaAnalysis(Base):
    """A stored AI analysis of one evidence package.

    Persisted for reproducibility and cost control. ``evidence_hash`` is the
    fingerprint of the deterministic evidence the analysis was produced from: if
    the evidence has not changed, the stored analysis is reused rather than paid
    for again, and an analysis can always be traced back to the exact facts that
    produced it.
    """

    __tablename__ = "rca_analyses"
    __table_args__ = (Index("ix_rca_analyses_evidence_hash", "evidence_hash"),)

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    deployment_id = Column(Integer, ForeignKey("deployments.id"), nullable=True)

    evidence_hash = Column(String, nullable=False)
    provider = Column(String, nullable=False)      # e.g. "anthropic"
    model = Column(String, nullable=False)
    prompt_version = Column(String, nullable=False)

    confidence = Column(String, nullable=False)    # HIGH / MEDIUM / LOW
    result_json = Column(Text, nullable=False)
    evidence_json = Column(Text, nullable=False)

    created_at = Column(DateTime, nullable=False)

    repository = relationship("Repository")


class Anomaly(Base):
    """A detected deviation from a historical baseline.

    Persisted rather than recomputed on every request so that an anomaly has a
    life cycle: it was first seen at a point in time, it can be acknowledged,
    and the record survives even after the metric returns to normal. A purely
    derived anomaly could never answer "when did this start?".
    """

    __tablename__ = "anomalies"
    __table_args__ = (
        UniqueConstraint(
            "repository_id", "metric", "window_start", name="uq_anomaly_window"
        ),
        Index("ix_anomalies_detected_at", "detected_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)

    metric = Column(String, nullable=False)       # e.g. "ci_duration_minutes"
    stage = Column(String, nullable=True)         # pipeline stage, when applicable
    direction = Column(String, nullable=False)    # INCREASE / DECREASE
    severity = Column(String, nullable=False)     # HIGH / MEDIUM / LOW

    current_value = Column(Float, nullable=False)
    baseline_value = Column(Float, nullable=False)
    change_pct = Column(Float, nullable=False)
    sample_count = Column(Integer, nullable=False)
    baseline_sample_count = Column(Integer, nullable=False)

    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)
    detected_at = Column(DateTime, nullable=False)

    evidence_json = Column(Text, nullable=False)
    acknowledged_at = Column(DateTime, nullable=True)

    repository = relationship("Repository")


class SyncJob(Base):
    """The outcome of one ingestion run.

    The MVP reported ``{"status": "sync started"}`` and then discarded whatever
    happened next: a 401 raised inside the background task reached no log, no
    database row and no user. Persisting the result is what makes it possible to
    say honestly whether the data behind a metric is complete.
    """

    __tablename__ = "sync_jobs"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=True)
    provider = Column(String, nullable=False)  # e.g. "github"

    status = Column(String, nullable=False)  # RUNNING / SUCCESS / PARTIAL / FAILED
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)

    pull_requests_written = Column(Integer, nullable=False, default=0)
    workflow_runs_written = Column(Integer, nullable=False, default=0)

    error_code = Column(String, nullable=True)  # taxonomy in services/errors.py
    error_message = Column(Text, nullable=True)

    repository = relationship("Repository", back_populates="sync_jobs")
