from sqlalchemy import (
    Boolean,
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
