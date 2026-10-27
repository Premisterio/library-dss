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
from app.domain.enums import JobKind
from app.models import Analyst, Dataset, Job, Report
from app.services import jobs

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


def test_a_demo_dataset_trains_a_churn_model(email: str) -> None:
    seeded = runner.invoke(
        app,
        ["seed-demo", "--email", email, "--users", "800", "--months", "10", "--seed", "1"],
        env=ENV,
    )
    assert seeded.exit_code == 0, seeded.output
    dataset_id, _ = ids(seeded.output)

    trained = runner.invoke(app, ["train-churn", "--dataset", str(dataset_id), "--activate"])
    assert trained.exit_code == 0, trained.output
    assert re.search(r"run #\d+: (logistic|boosting) chosen", trained.output), trained.output
    assert "inactivity_rule" in trained.output
    assert re.search(r"scored \d+ members at risk, active", trained.output), trained.output


def test_training_needs_an_existing_dataset_with_retention_data(
    email: str, tmp_path: Path, nested_document: dict[str, Any]
) -> None:
    missing = runner.invoke(app, ["train-churn", "--dataset", "0"])
    assert missing.exit_code == 1
    assert "does not exist" in missing.output

    file = tmp_path / "library.json"
    file.write_bytes(orjson.dumps(nested_document))
    seeded = runner.invoke(app, ["seed-demo", "--email", email, "--file", str(file)], env=ENV)
    dataset_id, _ = ids(seeded.output)
    unsupported = runner.invoke(app, ["train-churn", "--dataset", str(dataset_id)])
    assert unsupported.exit_code == 1
    assert "churn.not_supported" in unsupported.output


def test_seed_demo_never_runs_a_training_job(email: str) -> None:
    """Regression: seed-demo took the newest job of the dataset, whatever its kind, so a queued
    churn training ran (or was waited for) inside seed-demo."""
    args = ["seed-demo", "--email", email, "--users", "150", "--months", "4", "--seed", "3"]
    dataset_id, _ = ids(runner.invoke(app, args, env=ENV).output)
    with get_sessionmaker()() as session:
        owner = session.get_one(Dataset, dataset_id).owner_id
        job = jobs.enqueue(session, kind=JobKind.TRAIN_CHURN, owner_id=owner, dataset_id=dataset_id)
        session.commit()
        job_id = job.id
    again = runner.invoke(app, args, env=ENV)
    assert again.exit_code == 0, again.output
    with get_sessionmaker()() as session:
        assert session.get_one(Job, job_id).status == "queued"
