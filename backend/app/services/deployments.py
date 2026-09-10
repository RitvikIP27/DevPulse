"""Deployment resolution (ADR-010).

A successful CI run is not a production deployment. DevPulse establishes
deployments from one of two sources, in order of authority:

1. ``github_deployments`` — the provider's own Deployments API. Authoritative:
   the platform is stating that a commit was deployed to an environment.
2. ``configured_workflow`` — a rule a human declared, naming which workflow
   performs deployment. Used only when no deployment provider exists.

When neither source yields anything, the repository has no deployment data and
every deployment-derived metric reports as unavailable. It never falls back to
counting CI runs, which is what produced the MVP's inflated figures.
"""

from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.events import Deployment, DeploymentRule, Repository, WorkflowRun
from app.services.timestamps import parse_utc

logger = get_logger(__name__)

GITHUB_API = "https://api.github.com"

PROVIDER_GITHUB_DEPLOYMENTS = "github_deployments"
PROVIDER_CONFIGURED_WORKFLOW = "configured_workflow"


class DeploymentStatus:
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    IN_PROGRESS = "IN_PROGRESS"


class DeploymentSource:
    GITHUB_DEPLOYMENTS = "GITHUB_DEPLOYMENTS"
    CONFIGURED_WORKFLOW = "CONFIGURED_WORKFLOW"
    NONE = "NONE"


#: GitHub deployment_status states that mean the deployment finished badly.
_FAILED_STATES = {"failure", "error"}
_SUCCESS_STATES = {"success"}


def _upsert(db: Session, repository_id: int, provider: str, external_id: str, values: dict) -> bool:
    existing = (
        db.query(Deployment)
        .filter_by(repository_id=repository_id, provider=provider, external_id=external_id)
        .first()
    )
    if existing:
        for field, value in values.items():
            setattr(existing, field, value)
        return False

    db.add(Deployment(repository_id=repository_id, provider=provider, external_id=external_id, **values))
    return True


def sync_github_deployments(db: Session, repo: Repository, client: httpx.Client) -> int:
    """Ingest from the GitHub Deployments API. Returns rows written.

    Most repositories have none; that is a normal, reported outcome rather than
    an error.
    """
    response = client.get(
        f"{GITHUB_API}/repos/{repo.full_name}/deployments", params={"per_page": 100}
    )
    response.raise_for_status()
    deployments = response.json()
    if not isinstance(deployments, list) or not deployments:
        return 0

    written = 0
    for deployment in deployments:
        statuses_response = client.get(
            f"{GITHUB_API}/repos/{repo.full_name}/deployments/{deployment['id']}/statuses",
            params={"per_page": 100},
        )
        statuses_response.raise_for_status()
        statuses = statuses_response.json()

        # Statuses arrive newest first; the latest one is the current verdict.
        latest = statuses[0] if statuses else None
        state = (latest or {}).get("state")
        if state in _SUCCESS_STATES:
            status = DeploymentStatus.SUCCESS
        elif state in _FAILED_STATES:
            status = DeploymentStatus.FAILED
        else:
            status = DeploymentStatus.IN_PROGRESS

        environment = deployment.get("environment") or "unknown"
        started_at = parse_utc(deployment.get("created_at"))
        if started_at is None:
            continue

        written += _upsert(
            db, repo.id, PROVIDER_GITHUB_DEPLOYMENTS, str(deployment["id"]),
            {
                "environment": environment,
                "is_production": environment.lower() in {"production", "prod"},
                "commit_sha": deployment.get("sha"),
                "status": status,
                "started_at": started_at,
                "finished_at": parse_utc((latest or {}).get("created_at")),
                "url": deployment.get("url"),
            },
        )

    db.commit()
    return written


def derive_deployments_from_rules(db: Session, repo: Repository) -> int:
    """Turn workflow runs matching a declared rule into Deployment records.

    Only runs the user explicitly designated become deployments. Everything else
    stays a CI run.
    """
    rules = db.query(DeploymentRule).filter(DeploymentRule.repository_id == repo.id).all()
    if not rules:
        return 0

    written = 0
    for rule in rules:
        pattern = f"%{rule.workflow_name_pattern}%"
        runs = (
            db.query(WorkflowRun)
            .filter(WorkflowRun.repository_id == repo.id)
            .filter(WorkflowRun.workflow_name.ilike(pattern))
            .all()
        )
        for run in runs:
            if run.conclusion == "success":
                status = DeploymentStatus.SUCCESS
            elif run.conclusion == "failure":
                status = DeploymentStatus.FAILED
            elif run.completed_at is None:
                status = DeploymentStatus.IN_PROGRESS
            else:
                # cancelled or skipped: the deployment never actually ran, so it
                # is neither a success nor a failure and is not recorded.
                continue

            written += _upsert(
                db, repo.id, PROVIDER_CONFIGURED_WORKFLOW, run.github_run_id,
                {
                    "environment": rule.environment,
                    "is_production": rule.is_production,
                    "commit_sha": run.head_sha,
                    "status": status,
                    "started_at": run.started_at,
                    "finished_at": run.completed_at,
                    "url": run.html_url,
                },
            )

    db.commit()
    return written


def deployment_source(db: Session, repository_id: int) -> str:
    """Which source, if any, provides deployments for this repository."""
    has_provider = (
        db.query(Deployment)
        .filter_by(repository_id=repository_id, provider=PROVIDER_GITHUB_DEPLOYMENTS)
        .first()
        is not None
    )
    if has_provider:
        return DeploymentSource.GITHUB_DEPLOYMENTS

    has_configured = (
        db.query(Deployment)
        .filter_by(repository_id=repository_id, provider=PROVIDER_CONFIGURED_WORKFLOW)
        .first()
        is not None
    )
    return DeploymentSource.CONFIGURED_WORKFLOW if has_configured else DeploymentSource.NONE


def production_deployments(db: Session, repository_id: int, since=None) -> list[Deployment]:
    """Production deployments, oldest first.

    When the provider API supplied any deployment, rules-derived rows are
    ignored: an authoritative source must not be mixed with a declared one.
    """
    source = deployment_source(db, repository_id)
    if source == DeploymentSource.NONE:
        return []

    provider = (
        PROVIDER_GITHUB_DEPLOYMENTS
        if source == DeploymentSource.GITHUB_DEPLOYMENTS
        else PROVIDER_CONFIGURED_WORKFLOW
    )

    query = (
        db.query(Deployment)
        .filter(Deployment.repository_id == repository_id)
        .filter(Deployment.provider == provider)
        .filter(Deployment.is_production.is_(True))
    )
    if since is not None:
        query = query.filter(Deployment.started_at >= since)

    return query.order_by(Deployment.started_at.asc()).all()
