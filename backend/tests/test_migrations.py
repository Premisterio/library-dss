from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.migrations import ALEMBIC_INI


def test_models_and_migrations_are_in_sync(migrated: None) -> None:
    """Fails when a model changed without a matching Alembic migration."""
    command.check(Config(str(ALEMBIC_INI)))


def test_migrations_are_numbered_in_one_chain() -> None:
    """Revisions are 0001, 0002, ... in one line of history, each in `<rev>_<slug>.py`."""
    script = ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))
    revisions = list(reversed(list(script.walk_revisions())))  # oldest first
    assert len(script.get_heads()) == 1
    for number, revision in enumerate(revisions, start=1):
        assert revision.revision == f"{number:04d}"
        assert revision.down_revision == (f"{number - 1:04d}" if number > 1 else None)
        assert Path(revision.path).name.startswith(f"{revision.revision}_")
