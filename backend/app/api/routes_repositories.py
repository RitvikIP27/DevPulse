from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.events import DeploymentRule, Repository, WorkflowRun
from app.schemas.deployment_rules import (
    DeploymentRuleCreate,
    DeploymentRuleListResponse,
    DeploymentRuleOut,
)
from app.schemas.repositories import RepositoryListResponse
from app.services.deployments import deployment_source, derive_deployments_from_rules
from app.services.repositories import list_repositories

router = APIRouter(prefix="/api/repositories", tags=["repositories"])


def _require_repository(db: Session, repository_id: int) -> Repository:
    repo = db.query(Repository).filter(Repository.id == repository_id).first()
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found.")
    return repo


def _to_out(db: Session, rule: DeploymentRule) -> DeploymentRuleOut:
    matched = (
        db.query(WorkflowRun)
        .filter(WorkflowRun.repository_id == rule.repository_id)
        .filter(WorkflowRun.workflow_name.ilike(f"%{rule.workflow_name_pattern}%"))
        .count()
    )
    return DeploymentRuleOut(
        id=rule.id,
        repository_id=rule.repository_id,
        workflow_name_pattern=rule.workflow_name_pattern,
        environment=rule.environment,
        is_production=rule.is_production,
        matched_run_count=matched,
    )


@router.get("", response_model=RepositoryListResponse)
def get_repositories(db: Session = Depends(get_db)) -> RepositoryListResponse:
    """Tracked repositories with per-stage data coverage."""
    return list_repositories(db)


@router.get("/{repository_id}/deployment-rules", response_model=DeploymentRuleListResponse)
def get_deployment_rules(repository_id: int, db: Session = Depends(get_db)) -> DeploymentRuleListResponse:
    _require_repository(db, repository_id)
    rules = db.query(DeploymentRule).filter(DeploymentRule.repository_id == repository_id).all()
    return DeploymentRuleListResponse(
        rules=[_to_out(db, rule) for rule in rules],
        deployment_source=deployment_source(db, repository_id),
    )


@router.post("/{repository_id}/deployment-rules", response_model=DeploymentRuleListResponse, status_code=201)
def create_deployment_rule(
    repository_id: int, payload: DeploymentRuleCreate, db: Session = Depends(get_db)
) -> DeploymentRuleListResponse:
    """Declare which workflow performs deployment for this repository.

    Creating a rule immediately derives Deployment records from the workflow
    runs already ingested, so the effect is visible without waiting for a sync.
    """
    repo = _require_repository(db, repository_id)

    duplicate = (
        db.query(DeploymentRule)
        .filter_by(
            repository_id=repository_id,
            workflow_name_pattern=payload.workflow_name_pattern,
            environment=payload.environment,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="An identical rule already exists.")

    db.add(DeploymentRule(repository_id=repository_id, **payload.model_dump()))
    db.commit()

    derive_deployments_from_rules(db, repo)

    rules = db.query(DeploymentRule).filter(DeploymentRule.repository_id == repository_id).all()
    return DeploymentRuleListResponse(
        rules=[_to_out(db, rule) for rule in rules],
        deployment_source=deployment_source(db, repository_id),
    )


@router.delete("/{repository_id}/deployment-rules/{rule_id}", status_code=204)
def delete_deployment_rule(repository_id: int, rule_id: int, db: Session = Depends(get_db)) -> None:
    """Remove a rule and the deployments it derived.

    The derived rows are deleted rather than kept, because they were only ever
    an interpretation of CI runs; leaving them would keep metrics alive on a
    mapping the user has withdrawn.
    """
    from app.models.events import Deployment
    from app.services.deployments import PROVIDER_CONFIGURED_WORKFLOW

    rule = db.query(DeploymentRule).filter_by(id=rule_id, repository_id=repository_id).first()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found.")

    db.delete(rule)
    db.commit()

    remaining = db.query(DeploymentRule).filter_by(repository_id=repository_id).all()
    if not remaining:
        db.query(Deployment).filter_by(
            repository_id=repository_id, provider=PROVIDER_CONFIGURED_WORKFLOW
        ).delete()
    else:
        db.query(Deployment).filter_by(
            repository_id=repository_id, provider=PROVIDER_CONFIGURED_WORKFLOW
        ).delete()
        repo = _require_repository(db, repository_id)
        derive_deployments_from_rules(db, repo)
    db.commit()
