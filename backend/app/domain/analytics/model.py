"""Building blocks of an analytics section: KPIs, tidy charts and notes.

Everything is UI-agnostic: numbers are raw with a unit, categories are codes (labels come from
`GET /meta/enums`), charts are tidy tables that fit any chart library or a plain table.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

# count: a number of things · ratio: a fraction 0..1 (show as %) · UAH: money
# minutes, days: durations · rating: average of 1..5 ratings
Unit = Literal["count", "ratio", "UAH", "minutes", "days", "rating"]
DimensionKind = Literal["category", "time", "number"]


@dataclass(frozen=True)
class Kpi:
    key: str  # metric code, label in enums "metric"
    value: float | None  # None: cannot be computed from this dataset (see the notes)
    unit: Unit
    # Last N days up to as_of; None: the whole history, or the state at the end of as_of
    # for counts of current things (paying subscribers, MRR).
    window_days: int | None = None


@dataclass(frozen=True)
class Dimension:
    key: str  # column of the rows, label in enums "dimension"
    kind: DimensionKind
    enum: str | None = None  # enums group with labels for the values (genre, age_range, ...)
    order: tuple[str, ...] | None = None  # display order of category values


@dataclass(frozen=True)
class Measure:
    key: str  # column of the rows, label in enums "metric"
    unit: Unit
    window_days: int | None = None  # its own window when it differs from the chart's


@dataclass(frozen=True)
class Chart:
    """A tidy table: one row per combination of dimension values."""

    key: str  # label in enums "chart"
    dimensions: tuple[Dimension, ...]
    measures: tuple[Measure, ...]
    rows: list[dict[str, Any]]
    attributes: tuple[Dimension, ...] = ()  # descriptive columns that are not plotted
    window_days: int | None = None  # rows cover the last N days; None: the whole history


@dataclass(frozen=True)
class Note:
    """Why something is missing or how to read it, e.g. v1 files have no hold data."""

    code: str
    message_uk: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Section:
    key: str
    kpis: list[Kpi]
    charts: list[Chart]
    notes: list[Note] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
