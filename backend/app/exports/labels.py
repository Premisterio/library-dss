"""Ukrainian labels and value texts for exported reports (labels come from the enums)."""

from dataclasses import dataclass
from typing import Any

from app.domain.enums import ENUMS
from app.utils.format import decimals_for, number, percent

EMPTY = "—"


@dataclass(frozen=True)
class Column:
    key: str
    title: str
    enum: str | None = None  # enums group of a category column
    kind: str | None = None  # dimension kind: category | time | number
    unit: str | None = None  # set for measures


def label(group: str, code: Any) -> str:
    return ENUMS.get(group, {}).get(str(code), str(code))


def columns(chart: dict[str, Any]) -> list[Column]:
    """Dimensions, then attributes, then measures: the column order of every export."""
    described = [
        Column(d["key"], label("dimension", d["key"]), enum=d.get("enum"), kind=d.get("kind"))
        for d in (*chart["dimensions"], *chart.get("attributes", []))
    ]
    measured = [
        Column(m["key"], label("metric", m["key"]), unit=m["unit"]) for m in chart["measures"]
    ]
    return described + measured


def value_text(value: Any, unit: str) -> str:
    if value is None:
        return EMPTY
    match unit:
        case "ratio":
            return percent(value)
        case "UAH":
            return f"{number(value, 2)} грн"
        case "minutes":
            return f"{number(value, decimals_for(value))} хв"
        case "days":
            return f"{number(value, 1)} дн."
        case "rating":
            return number(value, 2)
        case _:
            return number(value, decimals_for(value))


MONTHLY = {"month", "cohort"}  # time dimensions whose values are month starts


def cell_text(column: Column, value: Any) -> str:
    if column.unit is not None:
        return value_text(value, column.unit)
    if value is None:
        return EMPTY
    if column.kind == "time" and column.key in MONTHLY:
        return str(value)[:7]
    return label(column.enum, value) if column.enum else str(value)


def window_text(days: int | None) -> str:
    return f"останні {days} днів" if days else ""


def chart_title(chart: dict[str, Any]) -> str:
    window = window_text(chart.get("window_days"))
    title = label("chart", chart["key"])
    return f"{title} ({window})" if window else title
