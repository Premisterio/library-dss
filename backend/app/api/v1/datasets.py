"""Upload, list and delete datasets. Imports run in the worker; follow them via /jobs."""

from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Form, Query, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import CurrentAnalyst, SettingsDep
from app.api.schemas import JobOut, Page, TaskError, Text
from app.core.db import SessionDep
from app.core.errors import ApiError
from app.services import datasets

router = APIRouter(prefix="/datasets", tags=["datasets"])

Capability = Literal["descriptive", "retention", "content"]


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: Literal["pending", "importing", "ready", "failed"]
    format: Literal["tabular", "nested"] | None = Field(
        description="File structure: `tabular` (tables of rows, as libsim writes them) or "
        "`nested` (one object per user). null until the file is parsed."
    )
    schema_version: int | None = Field(description="Format version declared by a tabular file.")
    as_of: date | None = Field(description="Snapshot date: the data ends on this day.")
    timezone: str = Field(description="IANA time zone of the library, e.g. `Europe/Kyiv`.")
    capabilities: list[Capability] = Field(description="Modules this dataset supports.")
    row_counts: dict[str, int]
    meta: dict[str, Any] = Field(description="File metadata (generator, seed, ...).")
    error: TaskError | None
    created_at: datetime
    updated_at: datetime


class DatasetPage(Page[DatasetOut]):
    pass


class UploadAccepted(BaseModel):
    dataset: DatasetOut
    job: JobOut


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a dataset file and queue its import",
    description="Accepts the tabular format (libsim) or the nested per-user format, "
    "as `.json` or `.json.gz`. "
    "The `Location` header points to the import job.",
)
def upload_dataset(
    file: Annotated[UploadFile, File(description="Dataset JSON, optionally gzip-compressed.")],
    response: Response,
    analyst: CurrentAnalyst,
    session: SessionDep,
    settings: SettingsDep,
    name: Annotated[Text | None, Form(min_length=1, max_length=200)] = None,
) -> UploadAccepted:
    limit = settings.max_upload_mb * 2**20
    content = file.file.read(limit + 1)
    if len(content) > limit:
        raise ApiError(
            413, "dataset.too_large", f"Uploads are limited to {settings.max_upload_mb} MB"
        )
    dataset, job = datasets.create_from_upload(
        session,
        settings,
        analyst,
        filename=file.filename or "dataset.json",
        content=content,
        name=name,
    )
    response.headers["Location"] = f"/api/v1/jobs/{job.id}"
    return UploadAccepted(
        dataset=DatasetOut.model_validate(dataset), job=JobOut.model_validate(job)
    )


@router.get("", summary="Your datasets, newest first")
def list_datasets(
    analyst: CurrentAnalyst,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DatasetPage:
    items, total = datasets.list_for(session, analyst, limit=limit, offset=offset)
    return DatasetPage(
        items=[DatasetOut.model_validate(d) for d in items], total=total, limit=limit, offset=offset
    )


@router.get("/{dataset_id}", summary="One dataset")
def get_dataset(dataset_id: int, analyst: CurrentAnalyst, session: SessionDep) -> DatasetOut:
    return DatasetOut.model_validate(datasets.get_for(session, dataset_id, analyst))


@router.delete(
    "/{dataset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a dataset with all its data, analytics, jobs and reports",
)
def delete_dataset(dataset_id: int, analyst: CurrentAnalyst, session: SessionDep) -> Response:
    datasets.delete(session, datasets.get_for(session, dataset_id, analyst))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
