"""Response models shared by several routers."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

JobStatus = Literal["queued", "running", "succeeded", "failed"]


class Page[T](BaseModel):
    """One page of a list; subclass it per item type so clients get a named schema."""

    items: list[T]
    total: int = Field(description="Number of items across all pages.")
    limit: int
    offset: int


class TaskError(BaseModel):
    """Why a job (and the dataset it worked on) failed."""

    code: str = Field(description="Stable error code, e.g. `dataset.invalid`.")
    detail: str | None = None
    errors: list[str] = Field(
        default_factory=list, description="Individual problems found in the file (at most 20)."
    )


class JobOut(BaseModel):
    """A long-running operation; poll it or follow `GET /jobs/{id}/events`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str = Field(description="What the job does, e.g. `import_dataset`.")
    status: JobStatus
    dataset_id: int | None
    progress: float = Field(ge=0, le=1)
    stage: str | None = Field(description="Current step, e.g. `parse` or `load:loans`.")
    result: dict[str, Any] | None
    error: TaskError | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
