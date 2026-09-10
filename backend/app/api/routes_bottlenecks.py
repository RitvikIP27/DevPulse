from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.bottlenecks import BottleneckResponse
from app.services.bottlenecks import detect_bottlenecks

router = APIRouter(prefix="/api/bottlenecks", tags=["bottlenecks"])


@router.get("", response_model=BottleneckResponse)
def get_bottlenecks(
    repository_id: int | None = Query(None),
    window_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> BottleneckResponse:
    """Deterministic bottleneck analysis with the evidence behind each score."""
    return detect_bottlenecks(db, repository_id=repository_id, window_days=window_days)
