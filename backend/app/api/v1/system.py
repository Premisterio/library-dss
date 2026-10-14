"""Service endpoints: liveness and readiness probes."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import __version__
from app.core.db import SessionDep
from app.core.errors import ApiError
from app.core.migrations import migration_head, migration_revision

router = APIRouter(tags=["system"])


class HealthOut(BaseModel):
    status: Literal["ok"] = "ok"
    version: str


class ReadyOut(BaseModel):
    status: Literal["ready"] = "ready"
    database: Literal["ok"] = "ok"
    migrations: Literal["ok"] = "ok"


@router.get("/health", summary="Liveness probe")
def get_health() -> HealthOut:
    return HealthOut(version=__version__)


@router.get("/ready", summary="Readiness probe: database reachable, migrations applied")
def get_ready(session: SessionDep) -> ReadyOut:
    try:
        session.execute(text("SELECT 1"))
        current = migration_revision(session.connection())
    except SQLAlchemyError as exc:
        raise ApiError(503, "system.database_unavailable", "Database is not reachable") from exc
    head = migration_head()
    if current != head:
        raise ApiError(
            503,
            "system.migrations_pending",
            f"Database is at revision {current}, the code expects {head}",
        )
    return ReadyOut()
