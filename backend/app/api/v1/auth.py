"""Sign-up, sign-in and token lifecycle.

Browsers get the refresh token only as an httpOnly cookie (rotated on every refresh) and keep
the short-lived access token in memory. CLI tools and scripts can ask for the refresh token in
the body (`include_refresh_token`) and send it back as a Bearer token to /refresh.
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.api.deps import BearerDep, CurrentAnalyst, SettingsDep
from app.core.config import Settings
from app.core.db import SessionDep
from app.core.errors import ApiError
from app.services import auth

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "dss_refresh"
COOKIE_PATH = "/api/v1/auth"


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=auth.MIN_PASSWORD_LENGTH, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)
    include_refresh_token: bool = Field(
        default=False,
        description="Also return the refresh token in the body (CLI/scripts). "
        "Browsers rely on the httpOnly cookie instead.",
    )


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 (OAuth token type, not a secret)
    expires_in: int = Field(description="Access token lifetime in seconds.")
    refresh_token: str | None = None


class AnalystOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    role: str
    created_at: datetime


def _set_refresh_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path=COOKIE_PATH,
    )


@router.post("/register", status_code=status.HTTP_201_CREATED, summary="Create an account")
def register(body: RegisterIn, session: SessionDep, settings: SettingsDep) -> AnalystOut:
    if not settings.allow_registration:
        raise ApiError(403, "auth.registration_disabled", "Ask an administrator for an account")
    analyst = auth.create_analyst(session, email=body.email, name=body.name, password=body.password)
    return AnalystOut.model_validate(analyst)


@router.post("/login", summary="Sign in with e-mail and password")
def login(
    body: LoginIn, response: Response, session: SessionDep, settings: SettingsDep
) -> TokenOut:
    analyst = auth.authenticate(session, email=body.email, password=body.password)
    pair = auth.issue_tokens(settings, analyst)
    _set_refresh_cookie(response, settings, pair.refresh_token)
    return TokenOut(
        access_token=pair.access_token,
        expires_in=pair.expires_in,
        refresh_token=pair.refresh_token if body.include_refresh_token else None,
    )


@router.post("/refresh", summary="Exchange a refresh token (cookie or Bearer) for new tokens")
def refresh_tokens(
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    credentials: BearerDep,
) -> TokenOut:
    from_header = credentials.credentials if credentials else None
    token = from_header or request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise ApiError(401, "auth.not_authenticated", "No refresh token")
    analyst = auth.analyst_from_token(session, settings, token, kind="refresh")
    pair = auth.issue_tokens(settings, analyst)
    _set_refresh_cookie(response, settings, pair.refresh_token)
    return TokenOut(
        access_token=pair.access_token,
        expires_in=pair.expires_in,
        refresh_token=pair.refresh_token if from_header else None,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Sign out everywhere (revokes all tokens)",
)
def logout(analyst: CurrentAnalyst, session: SessionDep) -> Response:
    auth.revoke_tokens(session, analyst)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
    return response


@router.get("/me", summary="The signed-in analyst")
def get_me(analyst: CurrentAnalyst) -> AnalystOut:
    return AnalystOut.model_validate(analyst)
