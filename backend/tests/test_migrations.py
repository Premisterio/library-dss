from alembic import command
from alembic.config import Config

from app.core.migrations import ALEMBIC_INI


def test_models_and_migrations_are_in_sync(migrated: None) -> None:
    """Fails when a model changed without a matching Alembic migration."""
    command.check(Config(str(ALEMBIC_INI)))
