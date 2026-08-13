from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
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


class PullRequest(Base):
    """Used to compute Lead Time for Changes (PR opened -> merged)."""
    __tablename__ = "pull_requests"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    github_pr_number = Column(Integer, nullable=False)
    title = Column(String, nullable=True)
    opened_at = Column(DateTime, nullable=False)
    merged_at = Column(DateTime, nullable=True)
    is_merged = Column(Boolean, default=False)

    repository = relationship("Repository", back_populates="pull_requests")


class WorkflowRun(Base):
    """
    One row per CI/CD run of the tracked 'deploy' workflow.
    Used for Deployment Frequency, Change Failure Rate, and MTTR.
    conclusion: 'success' | 'failure' | 'cancelled' etc. (mirrors GitHub Actions)
    """
    __tablename__ = "workflow_runs"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    github_run_id = Column(String, unique=True, nullable=False)
    workflow_name = Column(String, nullable=False)
    conclusion = Column(String, nullable=True)  # success / failure / cancelled / null=in-progress
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    repository = relationship("Repository", back_populates="workflow_runs")
