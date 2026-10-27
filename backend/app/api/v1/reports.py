"""Reports: frozen, titled copies of a dataset's analytics that can be exported as files."""

from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentAnalyst
from app.api.schemas import Page, Text
from app.api.v1.analytics import AnalyticsKey, ReportSectionOut, SectionKey
from app.core.db import SessionDep
from app.core.errors import PROBLEM_JSON_RESPONSES
from app.exports import MEDIA_TYPES, ExportFormat
from app.models import Report
from app.services import reports

router = APIRouter(prefix="/reports", tags=["reports"])

ReportKind = Literal["analytics", "retention", "content"]


class ReportIn(BaseModel):
    dataset_id: int
    title: Text = Field(min_length=1, max_length=200)
    sections: list[AnalyticsKey] | None = Field(
        default=None, min_length=1, description="Sections to include; all when omitted."
    )


class ReportOut(BaseModel):
    id: int
    dataset_id: int
    dataset_name: str
    kind: ReportKind = Field(
        description="`analytics`, or an approved decision: `retention` (a plan of actions) or "
        "`content` (a portfolio of titles). Label in enums `report_kind`."
    )
    title: str
    sections: list[SectionKey]
    params: dict[str, Any] | None = Field(description="What a decision was made with.")
    as_of: date
    timezone: str
    created_at: datetime


class ReportDetailOut(ReportOut):
    content: list[ReportSectionOut] = Field(description="The sections as they were when created.")


class ReportPage(Page[ReportOut]):
    pass


def report_out(report: Report) -> dict:
    return {
        "id": report.id,
        "dataset_id": report.dataset_id,
        "dataset_name": report.content["dataset_name"],
        "kind": report.kind,
        "title": report.title,
        "sections": report.sections,
        "params": report.params,
        "as_of": report.content["as_of"],
        "timezone": report.content["timezone"],
        "created_at": report.created_at,
    }


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create a report from a dataset")
def create_report(body: ReportIn, analyst: CurrentAnalyst, session: SessionDep) -> ReportOut:
    report = reports.create(
        session, analyst, dataset_id=body.dataset_id, title=body.title, sections=body.sections
    )
    return ReportOut.model_validate(report_out(report))


@router.get("", summary="Your reports, newest first")
def list_reports(
    analyst: CurrentAnalyst,
    session: SessionDep,
    dataset_id: int | None = None,
    kind: ReportKind | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReportPage:
    items, total = reports.list_for(
        session, analyst, dataset_id=dataset_id, kind=kind, limit=limit, offset=offset
    )
    return ReportPage(
        items=[ReportOut.model_validate(report_out(r)) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{report_id}", summary="One report with its sections")
def get_report(report_id: int, analyst: CurrentAnalyst, session: SessionDep) -> ReportDetailOut:
    report = reports.get_for(session, report_id, analyst)
    content = report.content
    return ReportDetailOut.model_validate(
        {
            **report_out(report),
            "content": [
                {**section, "as_of": content["as_of"], "timezone": content["timezone"]}
                for section in content["sections"]
            ],
        }
    )


@router.delete(
    "/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a report",
)
def delete_report(report_id: int, analyst: CurrentAnalyst, session: SessionDep) -> Response:
    reports.delete(session, reports.get_for(session, report_id, analyst))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{report_id}/export",
    response_class=Response,
    responses={
        200: {
            "description": "The report file (`Content-Disposition: attachment`).",
            "content": {media: {} for media in MEDIA_TYPES.values()},
        },
        **PROBLEM_JSON_RESPONSES,
    },
    summary="Download a report as PDF, XLSX, CSV (zip of tables) or JSON",
)
def export_report(
    report_id: int,
    analyst: CurrentAnalyst,
    session: SessionDep,
    export_format: Annotated[ExportFormat, Query(alias="format")] = "pdf",
) -> Response:
    report = reports.get_for(session, report_id, analyst)
    content, disposition = reports.export(report, export_format)
    return Response(
        content,
        media_type=MEDIA_TYPES[export_format],
        headers={"Content-Disposition": disposition},
    )
