from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.health import HealthResponse
from app.services.health import compute_health

router = APIRouter(prefix="/api/health-score", tags=["health"])


@router.get("", response_model=HealthResponse)
def get_health(
    window_days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)
) -> HealthResponse:
    """Composite engineering health, decomposed into explainable dimensions."""
    return compute_health(db, window_days=window_days)
