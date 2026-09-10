from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.repositories import RepositoryListResponse
from app.services.repositories import list_repositories

router = APIRouter(prefix="/api/repositories", tags=["repositories"])


@router.get("", response_model=RepositoryListResponse)
def get_repositories(db: Session = Depends(get_db)) -> RepositoryListResponse:
    """Tracked repositories with per-stage data coverage."""
    return list_repositories(db)
