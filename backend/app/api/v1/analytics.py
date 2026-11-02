"""Descriptive analytics of a dataset: precomputed sections of KPIs and tidy charts.

Every section is computed once when the dataset is imported, as of the dataset's `as_of` date.
Codes (metrics, dimensions, categories, units) have Ukrainian labels in `GET /meta/enums`.
"""

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentAnalyst
from app.core.db import SessionDep
from app.domain.analytics.model import DimensionKind, Unit
from app.services import analytics, datasets

router = APIRouter(prefix="/datasets/{dataset_id}/analytics", tags=["analytics"])

AnalyticsKey = Literal[
    "overview", "usage", "content", "segments", "search", "subscriptions", "cohorts", "candidates"
]
# Every section the API serves: the analytics, and the sections of decisions.
SectionKey = Literal[
    "overview",
    "usage",
    "content",
    "segments",
    "search",
    "subscriptions",
    "cohorts",
    "candidates",
    "retention_plan",
    "content_portfolio",
]
WINDOW = Field(
    description="The value covers the last N days up to as_of; null: the whole history, "
    "or the state at the end of as_of for current counts (paying subscribers, MRR)."
)


class KpiOut(BaseModel):
    key: str = Field(description="Metric code; label in enums `metric`.")
    value: int | float | None = Field(
        description="null when this dataset cannot provide it (see notes)."
    )
    unit: Unit = Field(description="`ratio` is a fraction 0..1 (show as a percentage).")
    window_days: int | None = WINDOW


class DimensionOut(BaseModel):
    key: str = Field(description="Column of the rows; label in enums `dimension`.")
    kind: DimensionKind = Field(
        description="`time` values are ISO dates (week or month start, local time)."
    )
    enum: str | None = Field(description="Enums group with labels for the values.")
    order: list[str] | None = Field(description="Display order of category values.")


class MeasureOut(BaseModel):
    key: str = Field(description="Column of the rows; label in enums `metric`.")
    unit: Unit
    window_days: int | None = Field(description="Set when it differs from the chart's window.")


class ChartOut(BaseModel):
    """A tidy table: one row per combination of dimension values."""

    key: str = Field(description="Chart code; title in enums `chart`.")
    dimensions: list[DimensionOut]
    measures: list[MeasureOut]
    attributes: list[DimensionOut] = Field(description="Descriptive columns that are not plotted.")
    window_days: int | None = WINDOW
    rows: list[dict[str, str | int | float | None]]


class NoteOut(BaseModel):
    code: str
    message_uk: str
    params: dict[str, Any]


class SectionOut(BaseModel):
    key: AnalyticsKey
    as_of: date
    timezone: str
    kpis: list[KpiOut]
    charts: list[ChartOut]
    notes: list[NoteOut]


class ReportSectionOut(BaseModel):
    """A section of a report: an analytics section, or the section of a decision."""

    key: SectionKey
    as_of: date
    timezone: str
    kpis: list[KpiOut]
    charts: list[ChartOut]
    notes: list[NoteOut]


class AnalyticsOut(BaseModel):
    dataset_id: int
    sections: list[SectionOut]


def _section(payload: dict[str, Any], as_of: date, timezone: str) -> SectionOut:
    return SectionOut.model_validate({**payload, "as_of": as_of, "timezone": timezone})


@router.get("", summary="Every analytics section of a dataset")
def get_analytics(dataset_id: int, analyst: CurrentAnalyst, session: SessionDep) -> AnalyticsOut:
    dataset = datasets.get_for(session, dataset_id, analyst)
    sections = analytics.sections_for(session, dataset)
    as_of, timezone = dataset.as_of, dataset.timezone
    assert as_of is not None  # noqa: S101 (ready datasets always have it)
    return AnalyticsOut(
        dataset_id=dataset.id, sections=[_section(s, as_of, timezone) for s in sections]
    )


@router.get("/{section}", summary="One analytics section")
def get_analytics_section(
    dataset_id: int, section: AnalyticsKey, analyst: CurrentAnalyst, session: SessionDep
) -> SectionOut:
    dataset = datasets.get_for(session, dataset_id, analyst)
    payload = analytics.section_for(session, dataset, section)
    assert dataset.as_of is not None  # noqa: S101 (ready datasets always have it)
    return _section(payload, dataset.as_of, dataset.timezone)
