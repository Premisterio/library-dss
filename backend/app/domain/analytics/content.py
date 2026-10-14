"""Content: what is read, how it is rated and finished, and where readers wait in queues."""

import polars as pl

from app.domain.analytics.common import (
    RECENT_DAYS,
    TOP_N,
    Context,
    Frames,
    number,
    records,
    safe_div,
)
from app.domain.analytics.model import Chart, Dimension, Kpi, Measure, Note, Section

NO_LICENCES = Note(
    "content.no_licences",
    "У датасеті немає даних про ліцензії й черги (формат v1), "
    "тому кількість копій і черги не показано.",
)
GENRE = Dimension("genre", "category", enum="genre")
RESOLVED_HOLDS = ("fulfilled", "lapsed", "cancelled")


def _reading_stats() -> list[pl.Expr]:
    return [
        pl.len().alias("loans"),
        pl.col("user_id").n_unique().alias("readers"),
        pl.col("rating").mean().alias("avg_rating"),
        pl.col("completed").cast(pl.Float64).mean().alias("completion_rate"),
    ]


def _hold_stats() -> list[pl.Expr]:
    wait_days = (pl.col("resolved_at") - pl.col("placed_at")).dt.total_seconds() / 86400
    return [
        pl.len().alias("holds"),
        wait_days.filter(pl.col("outcome") == "fulfilled").mean().alias("avg_hold_wait_days"),
        safe_div(
            (pl.col("outcome") == "lapsed").sum(), pl.col("outcome").is_in(RESOLVED_HOLDS).sum()
        ).alias("hold_lapse_rate"),
    ]


READING_MEASURES = (
    Measure("loans", "count"),
    Measure("readers", "count"),
    Measure("avg_rating", "rating"),
    Measure("completion_rate", "ratio"),
)


def _genres(loans: pl.DataFrame, holds: pl.DataFrame, books: pl.DataFrame, licensed: bool) -> Chart:
    catalogue = books.group_by("genre").agg(titles=pl.len(), copies=pl.col("copies").sum())
    reading = loans.group_by("genre").agg(_reading_stats())
    queued = holds.group_by("genre").agg(holds=pl.len())
    genres = (
        catalogue.join(reading, on="genre", how="full", coalesce=True)
        .join(queued, on="genre", how="left")
        .with_columns(pl.col("loans", "readers", "holds").fill_null(0))
        .with_columns(holds_per_copy=safe_div(pl.col("holds"), pl.col("copies")))
        .sort(pl.col("loans"), pl.col("genre"), descending=[True, False])
    )
    measures = READING_MEASURES
    columns = ["genre", "loans", "readers", "avg_rating", "completion_rate"]
    if licensed:
        measures += (
            Measure("holds", "count"),
            Measure("copies", "count"),
            Measure("holds_per_copy", "ratio"),
        )
        columns += ["holds", "copies", "holds_per_copy"]
    return Chart(
        "genres", (GENRE,), measures, records(genres.select(columns)), window_days=RECENT_DAYS
    )


def _top_titles(loans: pl.DataFrame) -> Chart:
    top = (
        loans.group_by("title", "authors")
        .agg(*_reading_stats(), genre=pl.col("genre").min())
        .sort(pl.col("loans"), pl.col("title"), descending=[True, False])
        .head(TOP_N)
        .select("title", "authors", "genre", "loans", "readers", "avg_rating", "completion_rate")
    )
    return Chart(
        "top_titles",
        (Dimension("title", "category"),),
        READING_MEASURES,
        records(top),
        attributes=(Dimension("authors", "category"), GENRE),
        window_days=RECENT_DAYS,
    )


def _queues(holds: pl.DataFrame) -> Chart:
    queues = (
        holds.group_by("title", "authors")
        .agg(*_hold_stats(), genre=pl.col("genre").min(), copies=pl.col("copies").max())
        .with_columns(holds_per_copy=safe_div(pl.col("holds"), pl.col("copies")))
        .sort(pl.col("holds"), pl.col("title"), descending=[True, False])
        .head(TOP_N)
        .select(
            "title",
            "authors",
            "genre",
            "holds",
            "copies",
            "holds_per_copy",
            "avg_hold_wait_days",
            "hold_lapse_rate",
        )
    )
    return Chart(
        "queues",
        (Dimension("title", "category"),),
        (
            Measure("holds", "count"),
            Measure("copies", "count"),
            Measure("holds_per_copy", "ratio"),
            Measure("avg_hold_wait_days", "days"),
            Measure("hold_lapse_rate", "ratio"),
        ),
        records(queues),
        attributes=(Dimension("authors", "category"), GENRE),
        window_days=RECENT_DAYS,
    )


def build(frames: Frames, ctx: Context) -> Section:
    books = frames["books"]
    info = books.select("book_id", "title", "authors", "genre", "copies")
    loans = frames["loans"].filter(ctx.within("borrowed_at", None)).join(info, on="book_id")
    recent_loans = loans.filter(ctx.within("borrowed_at", RECENT_DAYS))
    holds = frames["holds"].join(info, on="book_id")
    recent_holds = holds.filter(ctx.within("placed_at", RECENT_DAYS))
    # v1 files have no licence data at all; a v2 file always has copies per title.
    licensed = books.height > 0 and books["copies"].null_count() < books.height
    hold_stats = recent_holds.select(_hold_stats()).row(0, named=True)

    charts = [_genres(recent_loans, recent_holds, books, licensed), _top_titles(recent_loans)]
    if licensed:
        charts.append(_queues(recent_holds))
    return Section(
        "content",
        kpis=[
            Kpi("titles_in_catalog", books.select("title", "authors").n_unique(), "count"),
            Kpi("titles_borrowed", loans.select("title", "authors").n_unique(), "count"),
            Kpi("loans", loans.height, "count"),
            Kpi(
                "completion_rate",
                number(loans["completed"].cast(pl.Float64).mean()),
                "ratio",
            ),
            Kpi("avg_rating", number(loans["rating"].mean()), "rating"),
            Kpi("holds", recent_holds.height if licensed else None, "count", RECENT_DAYS),
            Kpi(
                "avg_hold_wait_days",
                number(hold_stats["avg_hold_wait_days"]) if licensed else None,
                "days",
                RECENT_DAYS,
            ),
            Kpi(
                "hold_lapse_rate",
                number(hold_stats["hold_lapse_rate"]) if licensed else None,
                "ratio",
                RECENT_DAYS,
            ),
        ],
        charts=charts,
        notes=[] if licensed else [NO_LICENCES],
    )
