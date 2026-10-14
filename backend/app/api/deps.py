"""Shared FastAPI dependencies: settings of the running app and the signed-in analyst."""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings
from app.core.db import SessionDep
from app.core.errors import ApiError
from app.models import Analyst
from app.services import auth

bearer = HTTPBearer(auto_error=False, description="Access token from POST /api/v1/auth/login")
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def current_analyst(session: SessionDep, settings: SettingsDep, credentials: BearerDep) -> Analyst:
    if credentials is None:
        raise ApiError(401, "auth.not_authenticated", "Sign in first")
    return auth.analyst_from_token(session, settings, credentials.credentials, kind="access")


CurrentAnalyst = Annotated[Analyst, Depends(current_analyst)]
