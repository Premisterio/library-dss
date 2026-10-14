"""Parse and validate a dataset into typed Polars frames (no database access)."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import polars as pl

from app.ingest import IngestError
from app.ingest.schema import (
    ENUM_COLUMNS,
    MAY_EXCEED_AS_OF,
    NESTED_MAY_BE_EMPTY,
    REFERENCES,
    TABLES,
    UNIQUE_KEYS,
    DatasetFormat,
)
from app.utils.dates import UTC_DATETIME, end_of_day_utc, parse_utc

_POLARS_TYPES: dict[str, Any] = {
    "string": pl.String,
    "integer": pl.Int64,
    "number": pl.Float64,
    "boolean": pl.Boolean,
    "timestamp": pl.String,  # parsed after loading
    "string[]": pl.List(pl.String),
}
MAX_REPORTED_ERRORS = 20


@dataclass
class ParsedDataset:
    format: DatasetFormat
    schema_version: int | None  # declared by tabular files
    meta: dict[str, Any]
    as_of: date
    timezone: str
    frames: dict[str, pl.DataFrame]
    capabilities: list[str] = field(default_factory=list)

    @property
    def row_counts(self) -> dict[str, int]:
        return {name: frame.height for name, frame in self.frames.items()}


def empty_frame(table: str) -> pl.DataFrame:
    schema = {
        col: (UTC_DATETIME if kind == "timestamp" else _POLARS_TYPES[kind])
        for col, kind, _ in TABLES[table]
    }
    return pl.DataFrame(schema=schema)


def frames_from_tables(document: dict[str, Any]) -> dict[str, pl.DataFrame]:
    tables = document.get("tables")
    if not isinstance(tables, dict):
        raise IngestError("dataset.invalid", "The file has no 'tables' object")
    missing = [name for name in TABLES if name not in tables]
    if missing:
        raise IngestError("dataset.invalid", f"Missing tables: {', '.join(missing)}")
    frames: dict[str, pl.DataFrame] = {}
    for name, spec in TABLES.items():
        table = tables[name]
        expected = [col for col, _, _ in spec]
        if table.get("columns") != expected:
            raise IngestError(
                "dataset.invalid",
                f"Table '{name}' must have columns {expected}, got {table.get('columns')}",
            )
        rows = table.get("rows", [])
        bad = next((i for i, row in enumerate(rows) if len(row) != len(expected)), None)
        if bad is not None:
            raise IngestError("dataset.invalid", f"Table '{name}' row {bad} has a wrong length")
        schema = {col: _POLARS_TYPES[kind] for col, kind, _ in spec}
        try:
            frame = pl.DataFrame(rows, schema=schema, orient="row", strict=False)
        except (pl.exceptions.PolarsError, TypeError, ValueError) as exc:
            raise IngestError(
                "dataset.invalid", f"Table '{name}' has values of the wrong type"
            ) from exc
        frames[name] = _parse_timestamps(name, frame)
    return frames


def _parse_timestamps(table: str, frame: pl.DataFrame) -> pl.DataFrame:
    stamps = [col for col, kind, _ in TABLES[table] if kind == "timestamp"]
    try:
        return frame.with_columns(parse_utc(col) for col in stamps)
    except pl.exceptions.PolarsError as exc:
        raise IngestError(
            "dataset.invalid", f"Table '{table}': timestamps must look like 2026-09-30T18:42:05Z"
        ) from exc


def validate(parsed: ParsedDataset, *, strict: bool = True) -> None:
    """Collect every problem before failing, so the analyst can fix the file in one go.

    `strict=False` (nested files) skips the enum checks and allows the fields that format does
    not have, since its codes differ; ids, references and the as_of bound are always checked.
    """
    errors: list[str] = []
    frames = parsed.frames
    for table, spec in TABLES.items():
        frame = frames[table]
        for col, _, nullable in spec:
            if nullable or (not strict and (table, col) in NESTED_MAY_BE_EMPTY):
                continue
            if frame.height and (nulls := frame[col].null_count()):
                errors.append(f"{table}.{col}: {nulls} empty values")
    for (table, col), allowed in ENUM_COLUMNS.items():
        if not strict and (table, col) != ("books", "genre"):
            continue
        unknown = set(frames[table][col].drop_nulls().unique().to_list()) - allowed
        if unknown:
            errors.append(f"{table}.{col}: unknown codes {sorted(unknown)[:5]}")
    for table, key in UNIQUE_KEYS.items():
        if (dups := frames[table].height - frames[table].select(key).n_unique()) > 0:
            errors.append(f"{table}.{'+'.join(key)}: {dups} duplicate ids")
    for (table, col), (ref_table, ref_col) in REFERENCES.items():
        known = frames[ref_table][ref_col]
        dangling = frames[table].filter(~pl.col(col).is_in(known.implode()))
        if dangling.height:
            errors.append(f"{table}.{col}: {dangling.height} rows point to unknown {ref_table}")
    try:
        limit = end_of_day_utc(parsed.as_of, parsed.timezone)
    except ValueError as exc:
        raise IngestError("dataset.invalid", str(exc)) from exc
    for table, spec in TABLES.items():
        for col, kind, _ in spec:
            if kind != "timestamp" or (table, col) in MAY_EXCEED_AS_OF:
                continue
            late = frames[table].filter(pl.col(col) > limit).height
            if late:
                errors.append(f"{table}.{col}: {late} values after as_of {parsed.as_of}")
    if errors:
        raise IngestError(
            "dataset.invalid",
            f"The dataset has {len(errors)} problem(s)",
            errors[:MAX_REPORTED_ERRORS],
        )


def capabilities_for(frames: dict[str, pl.DataFrame], fmt: DatasetFormat) -> list[str]:
    """Which DSS modules the data supports (nested files allow descriptive analytics only)."""
    caps = ["descriptive"]
    if fmt == "nested":
        return caps
    if frames["subscription_periods"].height and frames["campaign_assignments"].height:
        caps.append("retention")
    if frames["candidate_titles"].height and frames["searches"].height:
        caps.append("content")
    return caps
