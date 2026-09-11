"""Authentication dependencies.

FastAPI's dependency injection lets a route declare what it needs rather than
fetch it. `current_user` is declared on every protected route; FastAPI resolves
it before the handler runs, so a handler can never accidentally execute
unauthenticated.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import InvalidToken, decode_access_token
from app.models.events import User

# auto_error=False so a missing header reaches our own handler, which can then
# decide whether auth is required at all (it is not, when disabled).
_bearer = HTTPBearer(auto_error=False)

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated.",
    headers={"WWW-Authenticate": "Bearer"},
)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User | None:
    """Resolve the signed-in user.

    When auth is disabled the request proceeds with no user, so a single-user
    local install is not forced through a login it does not need. When auth is
    enabled a missing or invalid token is rejected before the handler runs.
    """
    if not settings.auth_enabled:
        return None

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _UNAUTHENTICATED

    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidToken as error:
        raise _UNAUTHENTICATED from error

    user = db.query(User).filter(User.id == user_id).first()
    # A token for a deleted or deactivated account must stop working
    # immediately, which a signature check alone would not catch.
    if user is None or not user.is_active:
        raise _UNAUTHENTICATED

    return user
