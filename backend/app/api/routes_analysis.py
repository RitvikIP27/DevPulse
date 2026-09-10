from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.events import Deployment, Repository
from app.schemas.evidence import EvidencePackage
from app.schemas.rca import RcaResponse
from app.services.ai.rca import generate_rca
from app.services.conflicts import _detect, _incidents_after, compare_runtime_around
from app.services.deployments import production_deployments
from app.services.evidence import build_evidence

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/candidates")
def get_candidates(
    limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)
) -> dict:
    """Deployments worth analysing, most conflicted first.

    Deliberately does NOT assemble a full evidence package per deployment.
    Doing so ran bottleneck detection once per row, which turned a listing into
    dozens of aggregate queries; the counts shown here come from the two cheap
    lookups the ordering actually needs.
    """
    candidates = []
    for repo in db.query(Repository).all():
        for deployment in production_deployments(db, repo.id):
            runtime = compare_runtime_around(db, deployment)
            incidents = _incidents_after(db, deployment)
            conflicts = _detect(deployment, runtime, incidents)

            candidates.append(
                {
                    "deployment_id": deployment.id,
                    "repository_full_name": repo.full_name,
                    "service": repo.display_name or repo.full_name,
                    "environment": deployment.environment,
                    "commit_sha": deployment.commit_sha,
                    "deployment_status": deployment.status,
                    "deployed_at": deployment.finished_at or deployment.started_at,
                    "conflict_count": len(conflicts),
                    "incident_count": len(incidents),
                    "coverage_confidence": (
                        "HIGH" if runtime.available else "LIMITED"
                    ),
                }
            )

    # Conflicts first, then most recent: analysis costs money, and the
    # deployments where systems disagree are where it pays off.
    candidates.sort(key=lambda c: (-c["conflict_count"], c["deployed_at"].timestamp() * -1))
    return {"candidates": candidates[:limit]}


@router.get("/evidence/{deployment_id}", response_model=EvidencePackage)
def get_evidence(deployment_id: int, db: Session = Depends(get_db)) -> EvidencePackage:
    """The deterministic evidence package. Always available, with or without AI."""
    evidence = build_evidence(db, deployment_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    return evidence


@router.post("/rca/{deployment_id}", response_model=RcaResponse)
def post_rca(
    deployment_id: int,
    force: bool = Query(False, description="Bypass the cached analysis and pay again."),
    db: Session = Depends(get_db),
) -> RcaResponse:
    """Generate (or return a cached) evidence-backed analysis.

    POST rather than GET because an uncached call spends money on a model.
    """
    if db.query(Deployment).filter(Deployment.id == deployment_id).first() is None:
        raise HTTPException(status_code=404, detail="Deployment not found.")
    return generate_rca(db, deployment_id, force=force)
