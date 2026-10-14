import pytest
from sqlalchemy import delete
from typer.testing import CliRunner

from app.cli.main import app
from app.core.db import get_sessionmaker
from app.models import Analyst

runner = CliRunner()


@pytest.mark.db
def test_create_user(migrated: None) -> None:
    email = "cli-admin@example.com"
    try:
        result = runner.invoke(
            app,
            ["create-user", "--email", email, "--name", "Адмін", "--admin"],
            env={"DSS_PASSWORD": "long enough password"},
        )
        assert result.exit_code == 0, result.output
        assert "(admin)" in result.output
        again = runner.invoke(
            app,
            ["create-user", "--email", email, "--name", "Адмін"],
            env={"DSS_PASSWORD": "long enough password"},
        )
        assert again.exit_code == 1
        assert "auth.email_taken" in again.output
    finally:
        with get_sessionmaker()() as session:
            session.execute(delete(Analyst).where(Analyst.email == email))
            session.commit()


def test_create_user_rejects_short_password() -> None:
    result = runner.invoke(
        app,
        ["create-user", "--email", "x@example.com", "--name", "X"],
        env={"DSS_PASSWORD": "short"},
    )
    assert result.exit_code == 1
    assert "auth.password_too_short" in result.output
