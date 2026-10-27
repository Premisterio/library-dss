"""Run a queued job from the CLI: here when no worker has taken it, otherwise wait for it."""

import uuid

from app.services import jobs
from app.worker import runner

JOB_TIMEOUT_SECONDS = 600


def run_job(session_factory: jobs.SessionFactory, job_id: uuid.UUID) -> None:
    if jobs.claim(session_factory, job_id):
        runner.execute(session_factory, job_id)
    else:
        jobs.wait(session_factory, job_id, timeout=JOB_TIMEOUT_SECONDS)
