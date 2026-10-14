"""Excel workbook: a summary sheet with every KPI, then one sheet per chart."""

import io
import re
from datetime import date
from typing import Any

import xlsxwriter
from xlsxwriter.workbook import Workbook
from xlsxwriter.worksheet import Worksheet

from app.exports import ReportDocument
from app.exports.labels import Column, chart_title, columns, label, window_text

NUMBER_FORMATS = {
    "count": "#,##0.##",
    "ratio": "0.0%",
    "UAH": "#,##0.00",
    "minutes": "#,##0.#",
    "days": "#,##0.0",
    "rating": "0.00",
}
SHEET_NAME_LIMIT = 31


def _sheet_name(title: str, used: set[str]) -> str:
    base = re.sub(r"[\[\]:*?/\\]", " ", title).strip()[:SHEET_NAME_LIMIT] or "Аркуш"
    name, n = base, 2
    while name.lower() in used:
        suffix = f" ({n})"
        name, n = base[: SHEET_NAME_LIMIT - len(suffix)] + suffix, n + 1
    used.add(name.lower())
    return name


def _write_cell(
    sheet: Worksheet, row: int, col: int, column: Column, value: Any, formats: dict[str, Any]
) -> None:
    if value is None:
        return
    if column.unit is not None:
        sheet.write_number(row, col, value, formats[column.unit])
    elif column.kind == "time":
        sheet.write_datetime(row, col, date.fromisoformat(value), formats["date"])
    elif column.enum:
        sheet.write_string(row, col, label(column.enum, value))
    elif isinstance(value, int | float):
        sheet.write_number(row, col, value)
    else:
        sheet.write_string(row, col, str(value))


def _summary(workbook: Workbook, document: ReportDocument, formats: dict[str, Any]) -> None:
    sheet = workbook.add_worksheet("Звіт")
    sheet.write_string(0, 0, document.title, formats["title"])
    details = [
        ("Датасет", document.dataset_name),
        ("Дата зрізу", document.as_of),
        ("Часовий пояс", document.timezone),
        ("Створено", document.created_at.strftime("%Y-%m-%d %H:%M UTC")),
    ]
    for i, (name, value) in enumerate(details, start=2):
        sheet.write_string(i, 0, name, formats["bold"])
        sheet.write_string(i, 1, value)
    top = len(details) + 3
    for col, header in enumerate(("Розділ", "Показник", "Значення", "Період")):
        sheet.write_string(top, col, header, formats["header"])
    row = top + 1
    for section in document.sections:
        for kpi in section["kpis"]:
            sheet.write_string(row, 0, label("analytics_section", section["key"]))
            sheet.write_string(row, 1, label("metric", kpi["key"]))
            if kpi["value"] is not None:
                sheet.write_number(row, 2, kpi["value"], formats[kpi["unit"]])
            sheet.write_string(row, 3, window_text(kpi["window_days"]))
            row += 1
    sheet.set_column(0, 0, 22)
    sheet.set_column(1, 1, 36)
    sheet.set_column(2, 3, 18)


def render_xlsx(document: ReportDocument) -> bytes:
    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})
    workbook.set_properties({"title": document.title, "created": document.created_at})
    formats: dict[str, Any] = {
        unit: workbook.add_format({"num_format": f}) for unit, f in NUMBER_FORMATS.items()
    }
    formats["date"] = workbook.add_format({"num_format": "yyyy-mm-dd"})
    formats["bold"] = workbook.add_format({"bold": True})
    formats["title"] = workbook.add_format({"bold": True, "font_size": 14})
    formats["header"] = workbook.add_format(
        {"bold": True, "bg_color": "#EEEEEE", "border": 1, "text_wrap": True, "valign": "top"}
    )
    _summary(workbook, document, formats)
    used = {"звіт"}
    for section in document.sections:
        for chart in section["charts"]:
            title = f"{label('analytics_section', section['key'])} · {label('chart', chart['key'])}"
            sheet = workbook.add_worksheet(_sheet_name(title, used))
            cols = columns(chart)
            sheet.write_string(0, 0, chart_title(chart), formats["bold"])
            for col, column in enumerate(cols):
                sheet.write_string(1, col, column.title, formats["header"])
                sheet.set_column(col, col, 14 if column.unit else 24)
            for r, values in enumerate(chart["rows"], start=2):
                for col, column in enumerate(cols):
                    _write_cell(sheet, r, col, column, values.get(column.key), formats)
            sheet.freeze_panes(2, 0)
            if chart["rows"]:
                sheet.autofilter(1, 0, len(chart["rows"]) + 1, len(cols) - 1)
    workbook.close()
    return buffer.getvalue()
