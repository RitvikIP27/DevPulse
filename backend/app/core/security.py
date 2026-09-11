"""Password hashing and JSON Web Token issuing.

Two separate concerns that are easy to confuse:

*Hashing* proves someone knows a password without ever storing it. bcrypt is
deliberately slow — that slowness is the whole defence, because it makes testing
billions of guesses against a stolen database impractical. A fast hash like
SHA-256 would be the wrong tool here precisely because it is fast.

*Tokens* let the server recognise a caller on later requests without holding
server-side session state. A JWT is signed, not encrypted: anyone can read its
contents, so it must never carry a secret — only a user id and an expiry.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"
TOKEN_TYPE = "bearer"

#: bcrypt truncates silently at 72 bytes, so a longer password would have its
#: tail ignored. Rejecting is safer than silently weakening.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LENGTH = 12


class InvalidToken(Exception):
    pass


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes; bcrypt would "
            "silently ignore anything beyond that."
        )
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # A malformed stored hash must fail closed, never raise into the request.
        return False


def create_access_token(user_id: int, expires_minutes: int | None = None) -> str:
    expires = expires_minutes or settings.access_token_expire_minutes
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int:
    """Return the user id carried by a valid token, or raise InvalidToken.

    Expiry is verified by the library. A token that is expired, tampered with,
    or signed with a different key all fail the same way — the caller must not
    be able to tell which, since that distinction leaks information.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        subject = payload.get("sub")
        if subject is None:
            raise InvalidToken("Token carries no subject.")
        return int(subject)
    except (JWTError, ValueError) as error:
        raise InvalidToken("Token is invalid or has expired.") from error
