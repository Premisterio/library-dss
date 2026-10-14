"""The job queue and worker with real, committed transactions (as in production).

These tests commit to the test database, so each one cleans up after itself by deleting its
analyst (datasets, jobs and library rows cascade).
"""

import threading
import time
import uuid
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import orjson
import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.ingest import load
from app.ingest.schema import DB_TABLE
from app.models import Analyst, Dataset, Job
from app.services import auth, datasets, jobs
from app.utils.dates import utc_now
from app.worker import runner


@pytest.fixture
def factory(migrated: None) -> sessionmaker[Session]:
    return get_sessionmaker()


@pytest.fixture
def owner(factory: sessionmaker[Session]) -> Iterator[Analyst]:
    with factory() as session:
        analyst = auth.create_analyst(
            session,
            email=f"worker-{uuid.uuid4().hex[:8]}@example.com",
            name="Worker test",
            password="password-1",
        )
    yield analyst
    with factory() as session:
        session.execute(delete(Analyst).where(Analyst.id == analyst.id))
        session.commit()


def enqueue(factory: sessionmaker[Session], owner: Analyst, kind: str = "noop") -> uuid.UUID:
    with factory() as session:
        job = jobs.enqueue(session, kind=kind, owner_id=owner.id)
        session.commit()
        return job.id


def get_job(factory: sessionmaker[Session], job_id: uuid.UUID) -> Job:
    with factory() as session:
        return session.get_one(Job, job_id)


def test_claim_skips_jobs_locked_by_another_worker(
    factory: sessionmaker[Session], owner: Analyst
) -> None:
    first, second = enqueue(factory, owner), enqueue(factory, owner)
    with factory() as other_worker:
        other_worker.scalars(select(Job).where(Job.id == first).with_for_update()).one()
        assert jobs.claim_next(factory) == second  # no waiting on the locked job
    assert jobs.claim_next(factory) == first
    assert jobs.claim_next(factory) is None
    claimed = get_job(factory, first)
    assert claimed.status == "running"
    assert claimed.started_at is not None


def test_unknown_job_kind_fails(factory: sessionmaker[Session], owner: Analyst) -> None:
    job_id = enqueue(factory, owner, kind="mystery")
    assert runner.run_once(factory)
    job = get_job(factory, job_id)
    assert job.status == "failed"
    assert job.error is not None
    assert job.error["code"] == "job.unknown_kind"


def test_failed_import_leaves_no_rows(
    factory: sessionmaker[Session],
    owner: Analyst,
    tabular_document: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A crash halfway through loading rolls back every table; progress stays visible."""
    with factory() as session:
        dataset, job = datasets.create_from_upload(
            session,
            get_settings(),
            owner,
            filename="demo.json",
            content=orjson.dumps(tabular_document),
        )
    calls = 0
    real_csv = load._csv

    def flaky_csv(frame: Any, dataset_id: int) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("disk full")
        return real_csv(frame, dataset_id)

    monkeypatch.setattr(load, "_csv", flaky_csv)
    assert runner.run_once(factory)

    failed = get_job(factory, job.id)
    assert failed.status == "failed"
    assert failed.error == {
        "code": "job.crashed",
        "detail": "Unexpected error; see the worker log",
        "errors": [],
    }
    assert failed.stage is not None
    assert failed.stage.startswith("load:")  # reported from a separate transaction
    with factory() as session:
        assert session.get_one(Dataset, dataset.id).status == "failed"
        for table in DB_TABLE.values():
            rows = session.scalar(
                text(f"SELECT count(*) FROM {table} WHERE dataset_id = :id"),  # noqa: S608
                {"id": dataset.id},
            )
            assert rows == 0, table


def test_abandoned_jobs_are_recovered(factory: sessionmaker[Session], owner: Analyst) -> None:
    with factory() as session:
        dataset = Dataset(owner_id=owner.id, name="x", sha256="0" * 64)
        session.add(dataset)
        session.flush()
        stale = jobs.enqueue(session, kind="noop", owner_id=owner.id, dataset_id=dataset.id)
        fresh = jobs.enqueue(session, kind="noop", owner_id=owner.id)
        stale.status, stale.heartbeat_at = "running", utc_now() - timedelta(hours=1)
        fresh.status, fresh.heartbeat_at = "running", utc_now()
        dataset.status = "importing"
        session.commit()

    assert jobs.recover_stale(factory, stale_seconds=300) == 1
    recovered = get_job(factory, stale.id)
    assert recovered.status == "failed"
    assert recovered.error is not None
    assert recovered.error["code"] == "job.interrupted"
    assert get_job(factory, fresh.id).status == "running"
    with factory() as session:
        assert session.get_one(Dataset, dataset.id).status == "failed"


def test_worker_loop_recovers_runs_and_stops(
    factory: sessionmaker[Session], owner: Analyst
) -> None:
    with factory() as session:
        abandoned = jobs.enqueue(session, kind="noop", owner_id=owner.id)
        abandoned.status, abandoned.heartbeat_at = "running", utc_now() - timedelta(hours=1)
        session.commit()
    queued = enqueue(factory, owner, kind="mystery")
    stop = threading.Event()
    worker = threading.Thread(
        target=runner.run_forever,
        args=(factory,),
        kwargs={"poll_seconds": 0.01, "stale_seconds": 300, "stop": stop},
    )
    worker.start()
    deadline = time.monotonic() + 10
    while get_job(factory, queued).status == "queued" and time.monotonic() < deadline:
        time.sleep(0.02)
    stop.set()
    worker.join(timeout=10)
    assert not worker.is_alive()
    assert get_job(factory, queued).status == "failed"
    assert get_job(factory, abandoned.id).status == "failed"


def test_a_specific_job_is_claimed_once(factory: sessionmaker[Session], owner: Analyst) -> None:
    job_id = enqueue(factory, owner)
    assert jobs.claim(factory, job_id)
    assert not jobs.claim(factory, job_id)  # already running: someone else has it
    assert get_job(factory, job_id).status == "running"


def test_waiting_for_a_job(factory: sessionmaker[Session], owner: Analyst) -> None:
    job_id = enqueue(factory, owner, kind="mystery")
    with pytest.raises(TimeoutError):
        jobs.wait(factory, job_id, timeout=0.05, poll=0.01)
    runner.run_once(factory)
    assert jobs.wait(factory, job_id, timeout=1, poll=0.01).status == "failed"
