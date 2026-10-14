"""Dataset use cases: upload (enqueue an import), import (worker), list, get, delete."""

import gzip
import hashlib
from pathlib import PurePath
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.ingest import IngestError, load, reader
from app.models import Analyst, Dataset, DatasetFile, Job
from app.services import analytics, jobs

IMPORT_JOB = "import_dataset"


def create_from_upload(
    session: Session,
    settings: Settings,
    owner: Analyst,
    *,
    filename: str,
    content: bytes,
    name: str | None = None,
) -> tuple[Dataset, Job]:
    """Store the file and queue its import; parsing happens in the worker."""
    try:
        raw = reader.decompress(content, limit=settings.max_upload_mb * 2**20)
    except IngestError as exc:
        raise ApiError(
            413 if exc.code == "dataset.too_large" else 422, exc.code, exc.detail
        ) from exc
    if raw.lstrip()[:1] != b"{":
        raise ApiError(422, "dataset.unreadable", "The file must contain a JSON object")
    digest = hashlib.sha256(raw).hexdigest()
    existing = session.scalar(
        select(Dataset).where(Dataset.owner_id == owner.id, Dataset.sha256 == digest)
    )
    if existing is not None:
        raise ApiError(
            409, "dataset.duplicate", f"This file is already uploaded as dataset #{existing.id}"
        )
    filename = PurePath(filename).name[:255]
    stem = filename.removesuffix(".gz").removesuffix(".json") or "dataset"
    dataset = Dataset(
        owner_id=owner.id,
        name=(name or stem)[:200],
        sha256=digest,
        meta={"original_filename": filename},
    )
    session.add(dataset)
    try:
        session.flush()
    except IntegrityError as exc:  # the same file uploaded twice at the same moment
        session.rollback()
        raise ApiError(409, "dataset.duplicate", "This file is already uploaded") from exc
    stored = content if content[:2] == reader.GZIP_MAGIC else gzip.compress(raw, mtime=0)
    session.add(
        DatasetFile(
            dataset_id=dataset.id, original_name=filename, size_bytes=len(raw), content=stored
        )
    )
    job = jobs.enqueue(session, kind=IMPORT_JOB, owner_id=owner.id, dataset_id=dataset.id)
    session.commit()
    return dataset, job


def run_import(session: Session, job: Job, progress: jobs.Progress) -> dict[str, Any]:
    """Worker handler: parse, validate and load one dataset in a single transaction."""
    dataset = session.get(Dataset, job.dataset_id)
    file = session.get(DatasetFile, job.dataset_id)
    if dataset is None or file is None:
        raise IngestError("dataset.missing", "The dataset was deleted before it was imported")
    progress(0.05, "parse")
    parsed = reader.parse(reader.decode(file.content))
    progress(0.3, "load")
    load.load(session, dataset.id, parsed.frames, lambda f, stage: progress(0.3 + 0.55 * f, stage))
    dataset.format = parsed.format
    dataset.schema_version = parsed.schema_version
    dataset.as_of = parsed.as_of
    dataset.timezone = parsed.timezone
    dataset.meta = {**dataset.meta, **parsed.meta}
    dataset.capabilities = parsed.capabilities
    dataset.row_counts = parsed.row_counts
    progress(0.85, "analytics")
    analytics.store(session, dataset, parsed.frames)
    dataset.status = "ready"
    dataset.error = None
    progress(1.0, "done")
    return {
        "dataset_id": dataset.id,
        "row_counts": parsed.row_counts,
        "capabilities": parsed.capabilities,
    }


def get_for(session: Session, dataset_id: int, analyst: Analyst) -> Dataset:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None or dataset.owner_id != analyst.id:
        raise ApiError(404, "dataset.not_found", "No such dataset")
    return dataset


def list_for(
    session: Session, analyst: Analyst, *, limit: int, offset: int
) -> tuple[list[Dataset], int]:
    query = select(Dataset).where(Dataset.owner_id == analyst.id)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = session.scalars(
        query.order_by(Dataset.created_at.desc(), Dataset.id.desc()).limit(limit).offset(offset)
    )
    return list(items), total


def delete(session: Session, dataset: Dataset) -> None:
    if dataset.status == "importing":
        raise ApiError(
            409, "dataset.busy", "The dataset is being imported; try again when it finishes"
        )
    session.delete(
        dataset
    )  # library rows, analytics, file, jobs and reports cascade in the database
    session.commit()
    session.expire_all()  # copies of cascaded rows already loaded in this session are gone
