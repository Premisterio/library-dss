"""Dates and timestamps. Everything is stored and exchanged in UTC; local time only via a zone."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import polars as pl

ISO_UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"  # timestamps in dataset files: 2026-09-30T18:42:05Z
DATE_FORMAT = "%Y-%m-%d"
UTC_DATETIME = pl.Datetime("us", "UTC")  # Polars dtype of every parsed timestamp


def utc_now() -> datetime:
    return datetime.now(UTC)


def zone(name: str) -> ZoneInfo:
    """IANA time zone by name; ValueError for an unknown one."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Unknown time zone '{name}'") from exc


def start_of_day_utc(day: date, tz_name: str) -> datetime:
    """Local midnight at the start of `day` in the given zone, in UTC."""
    return datetime.combine(day, time.min, tzinfo=zone(tz_name)).astimezone(UTC)


def end_of_day_utc(day: date, tz_name: str) -> datetime:
    """The first instant after `day` ends in the given zone, in UTC."""
    return start_of_day_utc(day + timedelta(days=1), tz_name)


def month_start(day: date, months_later: int = 0) -> date:
    """First day of the month of `day`, shifted by whole months."""
    index = day.year * 12 + day.month - 1 + months_later
    return date(index // 12, index % 12 + 1, 1)


def parse_utc(column: str, fmt: str = ISO_UTC_FORMAT) -> pl.Expr:
    """String column → UTC datetime; a value that does not match `fmt` raises."""
    return pl.col(column).str.to_datetime(fmt, time_zone="UTC", time_unit="us")
