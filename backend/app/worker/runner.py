"""Claim queued jobs and run their handlers; record results, failures and progress."""

import logging
import signal
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.ingest import IngestError
from app.models import Job
from app.services import datasets, jobs
from app.utils.dates import utc_now

logger = logging.getLogger("app.worker")

Handler = Callable[[Session, Job, jobs.Progress], dict[str, Any]]
HANDLERS: dict[str, Handler] = {datasets.IMPORT_JOB: datasets.run_import}
RECOVERY_INTERVAL_SECONDS = 60


def execute(session_factory: jobs.SessionFactory, job_id: uuid.UUID) -> None:
    """Run one claimed job. The handler's work commits atomically with the job's success."""

    def progress(fraction: float, stage: str) -> None:
        jobs.report(session_factory, job_id, fraction, stage)

    with session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        handler = HANDLERS.get(job.kind)
        try:
            if handler is None:
                raise IngestError("job.unknown_kind", f"No handler for job kind {job.kind!r}")
            result = handler(session, job, progress)
            job.status, job.result, job.progress, job.stage = "succeeded", result, 1.0, "done"
            job.finished_at = utc_now()
            session.commit()
            logger.info("job %s (%s) succeeded", job_id, job.kind)
            return
        except (IngestError, ApiError) as exc:
            session.rollback()
            error: dict[str, Any] = (
                exc.as_problem()
                if isinstance(exc, IngestError)
                else {"code": exc.code, "detail": exc.detail, "errors": []}
            )
        except Exception:
            session.rollback()
            logger.exception("job %s crashed", job_id)
            error = {
                "code": "job.crashed",
                "detail": "Unexpected error; see the worker log",
                "errors": [],
            }
    jobs.mark_failed(session_factory, job_id, error)
    logger.info("job %s failed: %s", job_id, error["code"])


def run_once(session_factory: jobs.SessionFactory) -> bool:
    """Claim and execute one job; False when the queue is empty."""
    job_id = jobs.claim_next(session_factory)
    if job_id is None:
        return False
    execute(session_factory, job_id)
    return True


def run_forever(
    session_factory: jobs.SessionFactory,
    *,
    poll_seconds: float,
    stale_seconds: int,
    stop: threading.Event | None = None,
) -> None:
    """Poll the queue until `stop` is set (by default on SIGINT/SIGTERM).

    A running job is finished before stopping.
    """
    if stop is None:
        stop = threading.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: stop.set())
    logger.info("worker started")
    next_recovery = 0.0
    while not stop.is_set():
        if time.monotonic() >= next_recovery:
            if recovered := jobs.recover_stale(session_factory, stale_seconds):
                logger.warning("failed %d job(s) abandoned by a stopped worker", recovered)
            next_recovery = time.monotonic() + RECOVERY_INTERVAL_SECONDS
        if not run_once(session_factory):
            stop.wait(poll_seconds)
    logger.info("worker stopped")
