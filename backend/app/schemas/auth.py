"""API contracts for authentication."""

from datetime import datetime
from typing import Annotated

import re

from pydantic import BaseModel, Field, field_validator

from app.core.security import MIN_PASSWORD_LENGTH


# Syntax only: one local part, an @, and a domain of one or more dot-separated
# labels. Deliberately permissive about the domain.
_EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+"     # local part
    r"@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"  # optional subdomains
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"         # final label
)


def _normalise_email(value: str) -> str:
    """Validate an address by syntax only, and lower-case it.

    DevPulse is self-hosted and frequently runs on internal domains, so this
    deliberately does NOT check deliverability. Pydantic's EmailStr (and the
    email-validator library behind it) rejects admin@devpulse.local outright —
    .local is on a hard-coded special-use list with no flag to bypass — and
    refusing a perfectly good internal address at sign-up is a worse failure
    than accepting one that happens to be undeliverable. Whether mail can
    actually be delivered is a mail-server concern, not a sign-up concern.

    Doing this in seven lines also removes a dependency (rules.md 16).
    """
    candidate = value.strip()
    if ".." in candidate or candidate.startswith(".") or "@." in candidate:
        raise ValueError("Not a valid email address.")
    if not _EMAIL_PATTERN.match(candidate):
        raise ValueError("Not a valid email address.")
    return candidate.lower()


Email = Annotated[str, Field(max_length=254)]


class RegisterRequest(BaseModel):
    email: Email
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=72)
    display_name: str | None = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return _normalise_email(value)


class LoginRequest(BaseModel):
    email: Email
    password: str

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return _normalise_email(value)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in_minutes: int


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str | None
    created_at: datetime
    last_login_at: datetime | None


class AuthStatus(BaseModel):
    """Lets the UI decide what to render before anyone signs in."""

    auth_required: bool
    #: False on a fresh install, so the UI can offer to create the first account.
    has_users: bool
