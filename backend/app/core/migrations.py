"""Alembic helpers used by the readiness probe."""

from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


@lru_cache
def migration_head() -> str | None:
    """Latest revision shipped with the code (None while there are no migrations)."""
    return ScriptDirectory.from_config(Config(str(ALEMBIC_INI))).get_current_head()


def migration_revision(connection: Connection) -> str | None:
    """Revision the database is currently at (None before the first migration)."""
    return MigrationContext.configure(connection).get_current_revision()
