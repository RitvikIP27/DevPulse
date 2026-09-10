from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.conflicts import ConflictListResponse
from app.services.conflicts import build_reports

router = APIRouter(prefix="/api/conflicts", tags=["conflicts"])


@router.get("", response_model=ConflictListResponse)
def get_conflicts(
    repository_id: int | None = Query(None),
    window_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> ConflictListResponse:
    """Deployments where systems disagree about what happened."""
    return build_reports(db, repository_id=repository_id, window_days=window_days)
