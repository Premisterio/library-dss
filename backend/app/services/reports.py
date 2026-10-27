"""Reports: titled, frozen copies of a dataset's analytics, exported as PDF, XLSX, CSV or JSON."""

import re
from collections.abc import Sequence
from typing import Any
from urllib.parse import quote

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.domain.analytics import SECTIONS
from app.exports import EXTENSIONS, ExportFormat, ReportDocument, render
from app.models import Analyst, Dataset, Report
from app.services import analytics, datasets

FILENAME_LIMIT = 100


def create(
    session: Session,
    analyst: Analyst,
    *,
    dataset_id: int,
    title: str,
    sections: Sequence[str] | None = None,
) -> Report:
    dataset = datasets.get_for(session, dataset_id, analyst)
    wanted = set(sections or SECTIONS)
    payloads = [p for p in analytics.sections_for(session, dataset) if p["key"] in wanted]
    return freeze(session, analyst, dataset, kind="analytics", title=title, payloads=payloads)


def freeze(
    session: Session,
    analyst: Analyst,
    dataset: Dataset,
    *,
    kind: str,
    title: str,
    payloads: list[dict[str, Any]],
    params: dict[str, Any] | None = None,
) -> Report:
    """A report of these section payloads as they are now; a decision keeps its parameters."""
    report = Report(
        owner_id=analyst.id,
        dataset_id=dataset.id,
        kind=kind,
        title=title.strip(),
        sections=[p["key"] for p in payloads],
        content={
            "dataset_name": dataset.name,
            "as_of": dataset.as_of.isoformat() if dataset.as_of else None,
            "timezone": dataset.timezone,
            "sections": payloads,
        },
        params=params,
    )
    session.add(report)
    session.commit()
    return report


def get_for(session: Session, report_id: int, analyst: Analyst) -> Report:
    report = session.get(Report, report_id)
    if report is None or report.owner_id != analyst.id:
        raise ApiError(404, "report.not_found", "No such report")
    return report


def list_for(
    session: Session,
    analyst: Analyst,
    *,
    dataset_id: int | None,
    kind: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[Report], int]:
    query = select(Report).where(Report.owner_id == analyst.id)
    if dataset_id is not None:
        query = query.where(Report.dataset_id == dataset_id)
    if kind is not None:
        query = query.where(Report.kind == kind)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = session.scalars(
        query.order_by(Report.created_at.desc(), Report.id.desc()).limit(limit).offset(offset)
    )
    return list(items), total


def delete(session: Session, report: Report) -> None:
    session.delete(report)
    session.commit()


def document(report: Report) -> ReportDocument:
    content = report.content
    return ReportDocument(
        title=report.title,
        dataset_name=content["dataset_name"],
        as_of=content["as_of"],
        timezone=content["timezone"],
        created_at=report.created_at,
        sections=content["sections"],
    )


def export(report: Report, fmt: ExportFormat) -> tuple[bytes, str]:
    """The file and its Content-Disposition header."""
    return render(document(report), fmt), content_disposition(report, fmt)


def content_disposition(report: Report, fmt: ExportFormat) -> str:
    """Attachment named after the title (RFC 6266), with an ASCII fallback for old clients."""
    stem = re.sub(r"[^\w\s.-]", "-", report.title)  # "/" and friends never reach the name
    stem = re.sub(r"\s+", " ", stem).strip(" .-")[:FILENAME_LIMIT] or "report"
    extension = EXTENSIONS[fmt]
    fallback = f"report-{report.id}.{extension}"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(f'{stem}.{extension}')}"
