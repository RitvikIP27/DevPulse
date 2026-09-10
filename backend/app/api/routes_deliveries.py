from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.deliveries import DeliveryDetail, DeliveryListResponse
from app.services.deliveries import DEFAULT_DELIVERY_LIMIT, get_delivery, list_deliveries

router = APIRouter(prefix="/api/deliveries", tags=["deliveries"])


@router.get("", response_model=DeliveryListResponse)
def get_deliveries(
    repository_id: int | None = Query(None),
    limit: int = Query(DEFAULT_DELIVERY_LIMIT, ge=1, le=100),
    db: Session = Depends(get_db),
) -> DeliveryListResponse:
    """Delivery traces, most recently merged first."""
    return list_deliveries(db, repository_id=repository_id, limit=limit)


@router.get("/{delivery_id}", response_model=DeliveryDetail)
def get_delivery_detail(delivery_id: str, db: Session = Depends(get_db)) -> DeliveryDetail:
    delivery = get_delivery(db, delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found or not correlatable.")
    return delivery
