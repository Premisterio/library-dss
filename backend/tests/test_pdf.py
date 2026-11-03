"""Report exports on hand-made documents, without a database: a missing as-of date, the
creation time and number dimensions."""

import io
from datetime import datetime, timedelta, timezone
from typing import Any

import openpyxl
import orjson
from pypdf import PdfReader

from app.domain.analytics.model import Chart, Dimension, Kpi, Measure, Section
from app.exports import ReportDocument
from app.exports.pdf import render_pdf
from app.exports.tables import render_json
from app.exports.xlsx import render_xlsx

TITLE = "Перевірка звіту"
CREATED = datetime(2026, 11, 2, 14, 19, tzinfo=timezone(timedelta(hours=1)))  # 13:19 UTC

USAGE = Section(
    "usage",
    kpis=[Kpi("sessions", 1234, "count", 30)],
    charts=[
        Chart(
            "devices",
            (Dimension("device", "category"),),
            (Measure("sessions", "count"),),
            [{"device": "Android", "sessions": 800}, {"device": "iPhone", "sessions": 434}],
        )
    ],
)
PLAN = Section(
    "retention_plan",
    kpis=[Kpi("plan_value", 1900.0, "UAH")],
    charts=[
        Chart(
            "budget_curve",
            (Dimension("budget", "number"),),
            (Measure("plan_value", "UAH"),),
            [
                {"budget": budget, "plan_value": value}
                for budget, value in [(0.0, 0.0), (1500.0, 900.0), (3000.0, 1500.0)]
            ],
        )
    ],
)


def stored(section: Section) -> dict[str, Any]:
    """A section as a report keeps it (JSON)."""
    return orjson.loads(orjson.dumps(section.to_dict()))


def document(*sections: Section, **fields: Any) -> ReportDocument:
    defaults: dict[str, Any] = {
        "title": TITLE,
        "dataset_name": "Демо-бібліотека",
        "as_of": "2026-09-30",
        "timezone": "Europe/Kyiv",
        "created_at": CREATED,
    }
    return ReportDocument(sections=[stored(s) for s in sections], **(defaults | fields))


def pdf_text(pdf: bytes) -> str:
    """The text of every page, with no-break spaces as plain ones."""
    pages = PdfReader(io.BytesIO(pdf)).pages
    return "\n".join(page.extract_text() for page in pages).replace("\xa0", " ")


def summary_value(xlsx: bytes, key: str) -> Any:
    sheet = openpyxl.load_workbook(io.BytesIO(xlsx))["Звіт"]
    return next(row[1] for row in sheet.iter_rows(values_only=True) if row[0] == key)


def test_a_dataset_without_an_as_of_date() -> None:
    """Regression: a report on a dataset without an as-of date printed "None" in the PDF and
    its XLSX export failed."""
    report = document(USAGE, as_of=None)
    assert "None" not in pdf_text(render_pdf(report))
    assert summary_value(render_xlsx(report), "Дата зрізу") == "—"
    assert orjson.loads(render_json(report))["as_of"] is None


def test_the_creation_time_is_in_utc() -> None:
    """Regression: the creation time was shown in the database session's time zone and
    labelled UTC."""
    report = document(USAGE)  # created at 14:19 +01:00
    assert "2026-11-02 13:19 UTC" in pdf_text(render_pdf(report))
    xlsx = render_xlsx(report)
    assert summary_value(xlsx, "Створено") == "2026-11-02 13:19 UTC"
    created = openpyxl.load_workbook(io.BytesIO(xlsx)).properties.created
    assert created == datetime(2026, 11, 2, 13, 19)  # the workbook's own field, in UTC


def test_number_dimensions_are_formatted() -> None:
    """Regression: a number dimension showed as "3000.0"."""
    lines = [line.strip() for line in pdf_text(render_pdf(document(PLAN))).splitlines()]
    assert "3 000" in lines
    assert not any("3000.0" in line for line in lines)
