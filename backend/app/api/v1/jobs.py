"""Long-running operations: read the current state or follow it as Server-Sent Events."""

import time
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

import anyio
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.sse import EventSourceResponse
from sqlalchemy.orm import Session

from app.api.deps import CurrentAnalyst
from app.api.schemas import JobOut
from app.core.db import SessionDep
from app.core.errors import PROBLEM_JSON_RESPONSES
from app.models import Job
from app.services import jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])

POLL_SECONDS = 0.5
STREAM_MAX_SECONDS = 600  # EventSource reconnects by itself after the stream ends


def owned_job(job_id: uuid.UUID, analyst: CurrentAnalyst, session: SessionDep) -> Job:
    # A dependency, so a 404 is sent before an event stream would start.
    return jobs.get_for(session, job_id, analyst)


OwnedJob = Annotated[Job, Depends(owned_job)]


@router.get("/{job_id}", summary="Current state of a job")
def get_job(job: OwnedJob) -> JobOut:
    return JobOut.model_validate(job)


def _snapshot(session: Session, job: Job) -> JobOut:
    session.refresh(job)
    session.commit()  # end the read transaction: no connection is held between polls
    return JobOut.model_validate(job)


@router.get(
    "/{job_id}/events",
    response_class=EventSourceResponse,
    responses=PROBLEM_JSON_RESPONSES,
    summary="Follow a job as Server-Sent Events",
    description="Sends the job whenever it changes and closes the stream once it has finished. "
    "Each event's `data` is a `JobOut` object.",
)
async def stream_job_events(job: OwnedJob, session: SessionDep) -> AsyncIterator[JobOut]:
    deadline = time.monotonic() + STREAM_MAX_SECONDS
    last: JobOut | None = None
    while time.monotonic() < deadline:  # a client disconnect cancels this generator
        current = await run_in_threadpool(_snapshot, session, job)
        if current != last:
            yield current
            last = current
        if current.status in jobs.TERMINAL:
            return
        await anyio.sleep(POLL_SECONDS)
