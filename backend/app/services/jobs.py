"""Background jobs: a `jobs` table used as a queue (no Redis/Celery needed).

The worker claims the oldest queued job with `SELECT … FOR UPDATE SKIP LOCKED`, so several
workers never pick the same job. Progress is written in short separate transactions, which keeps
it visible while the job's own (long) transaction is still open.
"""

import time
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.domain.enums import JobStage
from app.models import Analyst, Dataset, Job
from app.utils.dates import utc_now

SessionFactory = Callable[[], AbstractContextManager[Session]]
Progress = Callable[[float, str], None]  # (fraction 0..1, stage)
TERMINAL = {"succeeded", "failed"}


def enqueue(
    session: Session,
    *,
    kind: str,
    owner_id: int,
    dataset_id: int | None = None,
    params: dict[str, Any] | None = None,
) -> Job:
    job = Job(kind=kind, owner_id=owner_id, dataset_id=dataset_id, params=params or {})
    session.add(job)
    session.flush()
    return job


def get_for(session: Session, job_id: uuid.UUID, analyst: Analyst) -> Job:
    job = session.get(Job, job_id)
    if job is None or job.owner_id != analyst.id:
        raise ApiError(404, "job.not_found", "No such job")
    return job


def _start(session: Session, job: Job) -> None:
    job.status, job.started_at, job.heartbeat_at, job.stage = (
        "running",
        utc_now(),
        utc_now(),
        JobStage.STARTED,
    )
    if job.dataset_id is not None:
        session.execute(
            update(Dataset).where(Dataset.id == job.dataset_id).values(status="importing")
        )
    session.commit()


def claim_next(session_factory: SessionFactory) -> uuid.UUID | None:
    """Atomically take the oldest queued job and mark it running (separate transaction)."""
    with session_factory() as session:
        job = session.scalars(
            select(Job)
            .where(Job.status == "queued")
            .order_by(Job.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        ).first()
        if job is None:
            return None
        _start(session, job)
        return job.id


def claim(session_factory: SessionFactory, job_id: uuid.UUID) -> bool:
    """Take one specific queued job; False when a worker already has it."""
    with session_factory() as session:
        job = session.scalars(
            select(Job)
            .where(Job.id == job_id, Job.status == "queued")
            .with_for_update(skip_locked=True)
        ).first()
        if job is None:
            return False
        _start(session, job)
        return True


def wait(
    session_factory: SessionFactory, job_id: uuid.UUID, *, timeout: float, poll: float = 1.0
) -> Job:
    """Block until a job finishes (for the CLI); TimeoutError after `timeout` seconds."""
    deadline = time.monotonic() + timeout
    while True:
        with session_factory() as session:
            job = session.get_one(Job, job_id)
            if job.status in TERMINAL:
                return job
        if time.monotonic() > deadline:
            raise TimeoutError(f"job {job_id} did not finish in {timeout:.0f} s")
        time.sleep(poll)


def report(session_factory: SessionFactory, job_id: uuid.UUID, progress: float, stage: str) -> None:
    with session_factory() as session:
        session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                progress=round(min(max(progress, 0.0), 1.0), 4), stage=stage, heartbeat_at=utc_now()
            )
        )
        session.commit()


def mark_failed(session_factory: SessionFactory, job_id: uuid.UUID, error: dict[str, Any]) -> None:
    with session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        job.status, job.error, job.finished_at = "failed", error, utc_now()
        if job.dataset_id is not None:
            session.execute(
                update(Dataset)
                .where(Dataset.id == job.dataset_id)
                .values(status="failed", error=error)
            )
        session.commit()


def recover_stale(session_factory: SessionFactory, stale_seconds: int) -> int:
    """Jobs left `running` by a crashed or restarted worker are failed (they cannot resume)."""
    cutoff = utc_now() - timedelta(seconds=stale_seconds)
    with session_factory() as session:
        stale = session.scalars(
            select(Job.id).where(Job.status == "running", Job.heartbeat_at < cutoff)
        ).all()
    for job_id in stale:
        mark_failed(
            session_factory,
            job_id,
            {"code": "job.interrupted", "detail": "The worker stopped while running this job"},
        )
    return len(stale)
