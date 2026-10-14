"""Password hashing (argon2) and JWT access/refresh tokens.

Tokens carry `type` ("access" | "refresh") and `ver` (the analyst's token_version): a refresh
token is never accepted where an access token is required (a bug in v1), and bumping
token_version on logout revokes every token issued before.
"""

from datetime import timedelta
from typing import Literal

import jwt
from pwdlib import PasswordHash

from app.core.config import Settings
from app.core.errors import ApiError
from app.utils.dates import utc_now

ALGORITHM = "HS256"
TokenType = Literal["access", "refresh"]

_hasher = PasswordHash.recommended()  # argon2id


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _hasher.verify(password, password_hash)


def create_token(settings: Settings, *, subject: int, version: int, kind: TokenType) -> str:
    now = utc_now()
    lifetime = (
        timedelta(minutes=settings.access_token_minutes)
        if kind == "access"
        else timedelta(days=settings.refresh_token_days)
    )
    claims = {"sub": str(subject), "type": kind, "ver": version, "iat": now, "exp": now + lifetime}
    return jwt.encode(claims, settings.secret_key.get_secret_value(), algorithm=ALGORITHM)


def decode_token(settings: Settings, token: str, *, expected: TokenType) -> tuple[int, int]:
    """Validate a token of the expected type; return (analyst id, token version)."""
    try:
        claims = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[ALGORITHM],
            options={"require": ["sub", "type", "ver", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise ApiError(401, "auth.token_expired", "Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise ApiError(401, "auth.token_invalid", "Token is invalid") from exc
    if claims["type"] != expected:
        raise ApiError(401, "auth.token_invalid", f"An {expected} token is required")
    return int(claims["sub"]), int(claims["ver"])
