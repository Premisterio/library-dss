"""Shared pieces of the descriptive analytics: the as-of context and Polars helpers."""

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import polars as pl

from app.utils.dates import end_of_day_utc, start_of_day_utc

Frames = Mapping[str, pl.DataFrame]  # dataset tables by name

RECENT_DAYS = 90  # window of the "recent" charts
TOP_N = 20
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAYS_PER_MONTH = 365.25 / 12


@dataclass(frozen=True)
class Context:
    """The analysis moment: everything is computed as of the end of `as_of` in `timezone`."""

    as_of: date
    timezone: str
    end: datetime  # first instant after as_of, UTC

    @classmethod
    def at(cls, as_of: date, timezone: str) -> Context:
        return cls(as_of, timezone, end_of_day_utc(as_of, timezone))

    def since(self, days: int) -> datetime:
        """The start of the last `days` local days up to as_of (local midnight, so a window
        that crosses a clock change still holds whole days)."""
        return start_of_day_utc(self.as_of - timedelta(days=days - 1), self.timezone)

    def within(self, column: str, days: int | None) -> pl.Expr:
        """Rows dated in the last `days` days up to as_of (the whole history when None)."""
        before_end = pl.col(column) < self.end
        return before_end if days is None else before_end & (pl.col(column) >= self.since(days))

    def local(self, column: str) -> pl.Expr:
        return pl.col(column).dt.convert_time_zone(self.timezone)

    def week(self, column: str) -> pl.Expr:
        """Monday of the local week."""
        return self.local(column).dt.truncate("1w").dt.date()

    def complete_weeks(self) -> pl.Expr:
        """Weeks (by their Monday) that ended by as_of: a partial last week looks like a drop."""
        return pl.col("week") <= self.as_of - timedelta(days=6)

    def month(self, column: str) -> pl.Expr:
        """First day of the local month."""
        return self.local(column).dt.truncate("1mo").dt.date()

    def month_index(self, column: str) -> pl.Expr:
        local = self.local(column)
        return local.dt.year().cast(pl.Int32) * 12 + local.dt.month().cast(pl.Int32) - 1


def month_index(day: date) -> int:
    return day.year * 12 + day.month - 1


def index_to_month(index: int) -> date:
    return date(index // 12, index % 12 + 1, 1)


def activity(frames: Frames) -> pl.DataFrame:
    """Every dated action of a member: reading sessions, loans and searches."""
    return pl.concat(
        [
            frames["reading_sessions"].select("user_id", at="started_at"),
            frames["loans"].select("user_id", at="borrowed_at"),
            frames["searches"].select("user_id", at="searched_at"),
        ]
    )


def ratio(part: float | None, whole: float | None) -> float | None:
    """part / whole, or None when undefined (never 0 in place of "unknown")."""
    if part is None or not whole:
        return None
    return part / whole


def number(value: Any) -> float | None:
    """A Polars scalar (sum, mean, ...) as float; None for null/NaN."""
    if value is None:
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def records(frame: pl.DataFrame) -> list[dict[str, Any]]:
    """Frame → JSON-ready rows: dates as ISO strings, floats rounded, NaN/inf as null."""

    def clean(value: Any) -> Any:
        if isinstance(value, float):
            return round(value, 4) if math.isfinite(value) else None
        if isinstance(value, date):  # datetime included
            return value.isoformat()
        return value

    return [{key: clean(value) for key, value in row.items()} for row in frame.to_dicts()]


def safe_div(numerator: pl.Expr, denominator: pl.Expr) -> pl.Expr:
    """Element-wise ratio that is null (not inf/NaN) when the denominator is 0 or null."""
    return pl.when(denominator > 0).then(numerator / denominator).otherwise(None)


def sort_by_codes(frame: pl.DataFrame, column: str, codes: Iterable[str]) -> pl.DataFrame:
    """Sort rows by the position of `column` in `codes` (unknown codes last, then by value)."""
    positions = {code: i for i, code in enumerate(codes)}
    position = pl.col(column).replace_strict(
        positions, default=len(positions), return_dtype=pl.Int32
    )
    return frame.sort(position, pl.col(column), nulls_last=True)
