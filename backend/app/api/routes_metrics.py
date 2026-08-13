from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.dora_metrics import compute_all_metrics
from app.schemas.metrics import DoraMetricsResponse

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/dora", response_model=DoraMetricsResponse)
def get_dora_metrics(
    window_days: int = Query(30, ge=1, le=365, description="Look-back window in days"),
    db: Session = Depends(get_db),
):
    """Per-service DORA metrics, worst-performing service first — this is the
    endpoint the dashboard's bottleneck-comparison table calls."""
    return compute_all_metrics(db, window_days=window_days)
