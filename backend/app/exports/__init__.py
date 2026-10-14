"""Report exports: PDF, XLSX, CSV (zip) and JSON, rendered from a report's frozen sections."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

ExportFormat = Literal["pdf", "xlsx", "csv", "json"]

MEDIA_TYPES: dict[ExportFormat, str] = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "application/zip",
    "json": "application/json",
}
EXTENSIONS: dict[ExportFormat, str] = {"pdf": "pdf", "xlsx": "xlsx", "csv": "zip", "json": "json"}


@dataclass(frozen=True)
class ReportDocument:
    title: str
    dataset_name: str
    as_of: str  # ISO date
    timezone: str
    created_at: datetime
    sections: list[dict[str, Any]]  # stored analytics section payloads


def render(document: ReportDocument, fmt: ExportFormat) -> bytes:
    # Imported lazily: each renderer pulls a sizeable library.
    match fmt:
        case "pdf":
            from app.exports.pdf import render_pdf

            return render_pdf(document)
        case "xlsx":
            from app.exports.xlsx import render_xlsx

            return render_xlsx(document)
        case "csv":
            from app.exports.tables import render_csv_zip

            return render_csv_zip(document)
        case "json":
            from app.exports.tables import render_json

            return render_json(document)
