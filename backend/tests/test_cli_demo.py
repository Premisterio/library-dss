"""`dss seed-demo` against the test database (real, committed transactions; cleaned up after)."""

import re
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import orjson
import pytest
from sqlalchemy import delete, func, select
from typer.testing import CliRunner

from app.cli.main import app
from app.core.db import get_sessionmaker
from app.models import Analyst, Dataset, Report

runner = CliRunner()
ENV = {"DSS_PASSWORD": "long enough password"}


@pytest.fixture
def email(migrated: None) -> Iterator[str]:
    address = f"seed-{uuid.uuid4().hex[:8]}@example.com"
    yield address
    with get_sessionmaker()() as session:
        session.execute(delete(Analyst).where(Analyst.email == address))
        session.commit()


def ids(output: str) -> tuple[int, int]:
    dataset = re.search(r"dataset\s+#(\d+)", output)
    report = re.search(r"report\s+#(\d+)", output)
    assert dataset, output
    assert report, output
    return int(dataset.group(1)), int(report.group(1))


def counts(email: str) -> tuple[int, int]:
    with get_sessionmaker()() as session:
        owner = select(Analyst.id).where(Analyst.email == email).scalar_subquery()
        datasets = session.scalar(select(func.count()).where(Dataset.owner_id == owner))
        reports = session.scalar(select(func.count()).where(Report.owner_id == owner))
        return datasets or 0, reports or 0


def test_seed_demo_simulates_imports_and_is_idempotent(email: str) -> None:
    args = ["seed-demo", "--email", email, "--users", "150", "--months", "4", "--seed", "3"]
    first = runner.invoke(app, args, env=ENV)
    assert first.exit_code == 0, first.output
    assert "(created)" in first.output
    assert "ready (imported)" in first.output

    again = runner.invoke(app, args, env=ENV)
    assert again.exit_code == 0, again.output
    assert "password unchanged" in again.output
    assert "already there" in again.output
    assert ids(again.output) == ids(first.output)
    assert counts(email) == (1, 1)


def test_seed_demo_imports_a_given_file(
    email: str, tmp_path: Path, nested_document: dict[str, Any]
) -> None:
    file = tmp_path / "library.json"
    file.write_bytes(orjson.dumps(nested_document))
    result = runner.invoke(app, ["seed-demo", "--email", email, "--file", str(file)], env=ENV)
    assert result.exit_code == 0, result.output
    assert "ready (imported)" in result.output
    assert counts(email) == (1, 1)


def test_seed_demo_reports_a_failed_import(email: str, tmp_path: Path) -> None:
    file = tmp_path / "broken.json"
    file.write_bytes(b'{"schema_version": 7}')
    result = runner.invoke(app, ["seed-demo", "--email", email, "--file", str(file)], env=ENV)
    assert result.exit_code == 1
    assert "failed" in result.output
