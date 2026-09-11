from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.anomalies import AnomalyListResponse
from app.services.anomalies import acknowledge, list_anomalies

router = APIRouter(prefix="/api/anomalies", tags=["anomalies"])


@router.get("", response_model=AnomalyListResponse)
def get_anomalies(
    repository_id: int | None = Query(None),
    window_days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
) -> AnomalyListResponse:
    """Detected deviations, most severe first."""
    return list_anomalies(db, repository_id=repository_id, window_days=window_days)


@router.post("/{anomaly_id}/acknowledge", status_code=204)
def post_acknowledge(anomaly_id: int, db: Session = Depends(get_db)) -> None:
    """Mark an anomaly as seen. It stays on record; it stops demanding attention."""
    if acknowledge(db, anomaly_id) is None:
        raise HTTPException(status_code=404, detail="Anomaly not found.")
