from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import current_user
from app.core.security import TOKEN_TYPE, create_access_token, hash_password, verify_password
from app.core.logging import get_logger
from app.models.events import User
from app.schemas.auth import (
    AuthStatus,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.services.timestamps import utc_now

logger = get_logger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status", response_model=AuthStatus)
def get_status(db: Session = Depends(get_db)) -> AuthStatus:
    """Unauthenticated by design: the UI needs this to render a login screen."""
    return AuthStatus(
        auth_required=settings.auth_enabled,
        has_users=db.query(User).first() is not None,
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Create an account.

    Open only while no account exists, so a fresh install can bootstrap its first
    user. After that it is closed — an unauthenticated endpoint that mints
    accounts on a running instance would make authentication pointless.
    """
    if db.query(User).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is closed. An account already exists.",
        )

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        created_at=utc_now(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("user registered id=%s", user.id)
    return TokenResponse(
        access_token=create_access_token(user.id),
        token_type=TOKEN_TYPE,
        expires_in_minutes=settings.access_token_expire_minutes,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email.lower()).first()

    # One message for every failure. Distinguishing "no such account" from
    # "wrong password" would let anyone enumerate which emails are registered.
    if user is None or not user.is_active or not verify_password(
        payload.password, user.password_hash
    ):
        logger.warning("failed login attempt for %s", payload.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    user.last_login_at = utc_now()
    db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id),
        token_type=TOKEN_TYPE,
        expires_in_minutes=settings.access_token_expire_minutes,
    )


@router.get("/me", response_model=UserOut)
def me(user: User | None = Depends(current_user)) -> UserOut:
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return UserOut(
        id=user.id, email=user.email, display_name=user.display_name,
        created_at=user.created_at, last_login_at=user.last_login_at,
    )
