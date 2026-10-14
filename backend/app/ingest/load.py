"""Write validated frames into PostgreSQL with COPY (fast bulk load in the caller's transaction)."""

import io
from collections.abc import Callable

import polars as pl
import psycopg
from sqlalchemy.orm import Session

from app.ingest import IngestError
from app.ingest.schema import DB_TABLE

NULL = r"\N"
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%.6f%:z"
Progress = Callable[[float, str], None]


def _array_literal(col: str) -> pl.Expr:
    """List[str] → PostgreSQL array literal {"a","b"} (quotes/backslashes escaped)."""
    quoted = (
        pl.element()
        .str.replace_all("\\", "\\\\", literal=True)
        .str.replace_all('"', '\\"', literal=True)
    )
    return pl.concat_str(
        pl.lit("{"),
        pl.col(col).list.eval(pl.concat_str(pl.lit('"'), quoted, pl.lit('"'))).list.join(","),
        pl.lit("}"),
    ).alias(col)


def _csv(frame: pl.DataFrame, dataset_id: int) -> bytes:
    lists = [name for name, dtype in frame.schema.items() if isinstance(dtype, pl.List)]
    prepared = frame.with_columns(_array_literal(col) for col in lists).select(
        pl.lit(dataset_id, pl.Int64).alias("dataset_id"), pl.all()
    )
    buffer = io.BytesIO()
    prepared.write_csv(
        buffer, include_header=False, null_value=NULL, datetime_format=DATETIME_FORMAT
    )
    return buffer.getvalue()


def load(
    session: Session, dataset_id: int, frames: dict[str, pl.DataFrame], progress: Progress
) -> None:
    connection = session.connection().connection.driver_connection
    assert isinstance(connection, psycopg.Connection)  # noqa: S101 (psycopg 3 is the only driver)
    total = sum(frame.height for frame in frames.values()) or 1
    done = 0
    for table, frame in frames.items():
        if frame.height:
            columns = ", ".join(f'"{c}"' for c in ("dataset_id", *frame.columns))
            sql = f"COPY {DB_TABLE[table]} ({columns}) FROM STDIN WITH (FORMAT csv, NULL '{NULL}')"
            try:
                with connection.cursor() as cursor, cursor.copy(sql) as copy:  # type: ignore[arg-type]
                    copy.write(_csv(frame, dataset_id))
            except (psycopg.errors.DataError, psycopg.errors.IntegrityError) as exc:
                # e.g. an id longer than the column allows; the transaction is rolled back
                reason = exc.diag.message_primary or type(exc).__name__
                raise IngestError("dataset.invalid", f"Table '{table}': {reason}") from exc
        done += frame.height
        progress(done / total, f"load:{table}")
