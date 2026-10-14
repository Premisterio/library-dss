"""Machine-readable exports: a zip of CSV tables (codes and raw numbers) and JSON."""

import csv
import io
import zipfile
from typing import Any

import orjson

from app.exports import ReportDocument
from app.exports.labels import columns, label


def _csv(header: list[str], rows: list[list[Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")  # the BOM makes Excel read UTF-8


def render_csv_zip(document: ReportDocument) -> bytes:
    """kpis.csv plus one CSV per chart, named `<section>-<chart>.csv`."""
    kpis = [
        [
            section["key"],
            kpi["key"],
            label("metric", kpi["key"]),
            kpi["value"],
            kpi["unit"],
            kpi["window_days"],
        ]
        for section in document.sections
        for kpi in section["kpis"]
    ]
    files = {"kpis.csv": _csv(["section", "metric", "label", "value", "unit", "window_days"], kpis)}
    for section in document.sections:
        for chart in section["charts"]:
            keys = [c.key for c in columns(chart)]
            rows = [[row.get(key) for key in keys] for row in chart["rows"]]
            files[f"{section['key']}-{chart['key']}.csv"] = _csv(keys, rows)

    stamp = document.created_at.timetuple()[:6]  # fixed entry dates: same report, same bytes
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(zipfile.ZipInfo(name, date_time=stamp), content)
    return buffer.getvalue()


def render_json(document: ReportDocument) -> bytes:
    return orjson.dumps(
        {
            "title": document.title,
            "dataset": document.dataset_name,
            "as_of": document.as_of,
            "timezone": document.timezone,
            "created_at": document.created_at,
            "sections": document.sections,
        },
        option=orjson.OPT_INDENT_2,
    )
