"""Descriptive analytics use cases: compute at import, serve stored sections, recompute."""

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.domain.analytics import SECTIONS, compute_all
from app.domain.analytics.common import Frames
from app.ingest import reader
from app.models import Dataset, DatasetAnalytics, DatasetFile


def store(session: Session, dataset: Dataset, frames: Frames) -> None:
    """Compute every section as of the dataset's as_of and replace the stored ones."""
    if dataset.as_of is None:
        raise ValueError("the dataset has no as_of date yet")
    sections = compute_all(frames, dataset.as_of, dataset.timezone)
    session.execute(delete(DatasetAnalytics).where(DatasetAnalytics.dataset_id == dataset.id))
    session.add_all(
        DatasetAnalytics(dataset_id=dataset.id, section=key, payload=section.to_dict())
        for key, section in sections.items()
    )
    session.flush()


def refresh(session: Session, dataset: Dataset) -> None:
    """Recompute from the stored upload, e.g. after the analytics code changed."""
    file = session.get_one(DatasetFile, dataset.id)
    parsed = reader.parse(reader.decode(file.content))
    store(session, dataset, parsed.frames)
    session.commit()


def _ready(dataset: Dataset) -> None:
    if dataset.status != "ready":
        raise ApiError(409, "dataset.not_ready", f"The dataset is {dataset.status}, not ready")


def sections_for(session: Session, dataset: Dataset) -> list[dict[str, Any]]:
    """Every stored section, in the canonical order."""
    _ready(dataset)
    stored = {
        row.section: row.payload
        for row in session.scalars(
            select(DatasetAnalytics).where(DatasetAnalytics.dataset_id == dataset.id)
        )
    }
    if set(stored) != set(SECTIONS):
        raise ApiError(
            409,
            "analytics.missing",
            "Analytics of this dataset are missing or outdated; run `dss refresh-analytics`",
        )
    return [stored[key] for key in SECTIONS]


def section_for(session: Session, dataset: Dataset, key: str) -> dict[str, Any]:
    _ready(dataset)
    row = session.get(DatasetAnalytics, (dataset.id, key))
    if row is None:
        raise ApiError(
            409,
            "analytics.missing",
            "Analytics of this dataset are missing or outdated; run `dss refresh-analytics`",
        )
    return row.payload
