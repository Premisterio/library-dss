"""Authentication use cases: shared by the HTTP API and the `dss` CLI."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import Settings
from app.core.errors import ApiError
from app.models import Analyst

MIN_PASSWORD_LENGTH = 8


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int  # seconds (access token)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def create_analyst(
    session: Session, *, email: str, name: str, password: str, role: str = "analyst"
) -> Analyst:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ApiError(422, "auth.password_too_short", f"At least {MIN_PASSWORD_LENGTH} characters")
    email = normalize_email(email)
    if session.scalar(select(Analyst.id).where(Analyst.email == email)) is not None:
        raise ApiError(409, "auth.email_taken", "An account with this e-mail already exists")
    analyst = Analyst(
        email=email, name=name.strip(), password_hash=security.hash_password(password), role=role
    )
    session.add(analyst)
    session.commit()
    return analyst


def authenticate(session: Session, *, email: str, password: str) -> Analyst:
    analyst = session.scalar(select(Analyst).where(Analyst.email == normalize_email(email)))
    if analyst is None or not security.verify_password(password, analyst.password_hash):
        raise ApiError(401, "auth.invalid_credentials", "Wrong e-mail or password")
    return analyst


def issue_tokens(settings: Settings, analyst: Analyst) -> TokenPair:
    version = analyst.token_version
    return TokenPair(
        access_token=security.create_token(
            settings, subject=analyst.id, version=version, kind="access"
        ),
        refresh_token=security.create_token(
            settings, subject=analyst.id, version=version, kind="refresh"
        ),
        expires_in=settings.access_token_minutes * 60,
    )


def analyst_from_token(
    session: Session, settings: Settings, token: str, *, kind: security.TokenType
) -> Analyst:
    analyst_id, version = security.decode_token(settings, token, expected=kind)
    analyst = session.get(Analyst, analyst_id)
    if analyst is None or analyst.token_version != version:
        raise ApiError(401, "auth.token_revoked", "Token is no longer valid; sign in again")
    return analyst


def revoke_tokens(session: Session, analyst: Analyst) -> None:
    """Log out everywhere: every previously issued token stops working."""
    analyst.token_version += 1
    session.commit()
