"""Candidates: the titles a distributor offers, with the evidence of demand the content decision
weighs (DESIGN.md §2.10). Only signals that track libsim's true demand are kept."""

import polars as pl

from app.domain.analytics.common import RECENT_DAYS, Context, Frames, number, records, safe_div
from app.domain.analytics.model import Chart, Dimension, Kpi, Measure, Note, Section

NO_CANDIDATES = Note(
    "candidates.none",
    "У датасеті немає пропозицій дистриб'ютора, тому кандидатів на закупівлю немає.",
)
TITLE = Dimension("title", "category")
ATTRIBUTES = (
    Dimension("authors", "category"),
    Dimension("genre", "category", enum="genre"),
    Dimension("language", "category", enum="language"),
    Dimension("candidate_id", "category"),
)
# The criteria, all "more is better"; the licence cost is the portfolio's budget, not a criterion.
CRITERIA = (
    Measure("demand_searches", "count"),  # zero-result searches for the title or an author
    Measure("author_loans", "count"),  # loans of the library's books by the same authors
    Measure("genre_loans", "count"),  # loans in the genre
    Measure("genre_holds_per_copy", "ratio"),  # holds in the genre per licensed copy
)
COST = Measure("license_cost", "UAH")


def _key(text: pl.Expr) -> pl.Expr:
    """Text compared the way the search section groups queries: trimmed, any case."""
    return text.str.strip_chars().str.to_lowercase()


def _authors(frame: pl.DataFrame, id_column: str) -> pl.DataFrame:
    """One row per (id, author key) from the comma-separated `authors`."""
    return (
        frame.select(id_column, author=pl.col("authors").str.split(", "))
        .explode("author")
        .select(id_column, author=_key(pl.col("author")))
        .unique()
    )


def criteria(frames: Frames, ctx: Context) -> pl.DataFrame:
    """Every candidate with its criteria over the last `RECENT_DAYS` days and its licence cost."""
    offered = frames["candidate_titles"]
    books = frames["books"]
    by_author = _authors(offered, "candidate_id")

    missed = (
        frames["searches"]
        .filter(ctx.within("searched_at", RECENT_DAYS) & (pl.col("results_count") == 0))
        .select(key=_key(pl.col("query")))
    )
    targets = pl.concat(
        [
            offered.select("candidate_id", key=_key(pl.col("title"))),
            by_author.select("candidate_id", key="author"),
        ]
    ).unique()
    searches = targets.join(missed, on="key").group_by("candidate_id").agg(demand_searches=pl.len())

    loans = (
        frames["loans"]
        .filter(ctx.within("borrowed_at", RECENT_DAYS))
        .select("book_id")
        .join(books.select("book_id", "genre"), on="book_id")
    )
    author_loans = (
        by_author.join(_authors(books, "book_id"), on="author")
        .select("candidate_id", "book_id")
        .unique()
        .join(loans, on="book_id")
        .group_by("candidate_id")
        .agg(author_loans=pl.len())
    )
    holds = (
        frames["holds"]
        .filter(ctx.within("placed_at", RECENT_DAYS))
        .join(books.select("book_id", "genre"), on="book_id")
        .group_by("genre")
        .agg(holds=pl.len())
    )
    genres = (
        books.group_by("genre")
        .agg(copies=pl.col("copies").sum())
        .join(loans.group_by("genre").agg(genre_loans=pl.len()), on="genre", how="left")
        .join(holds, on="genre", how="left")
        .select(
            "genre",
            pl.col("genre_loans").fill_null(0),
            genre_holds_per_copy=safe_div(pl.col("holds").fill_null(0), pl.col("copies")),
        )
    )
    counts = [m.key for m in CRITERIA if m.unit == "count"]
    return (
        offered.select(TITLE.key, *(d.key for d in ATTRIBUTES), COST.key)
        .join(searches, on="candidate_id", how="left")
        .join(author_loans, on="candidate_id", how="left")
        .join(genres, on="genre", how="left")
        .with_columns(pl.col(counts).fill_null(0), pl.col("genre_holds_per_copy").fill_null(0.0))
        .sort(pl.col("demand_searches"), pl.col("candidate_id"), descending=[True, False])
    )


def build(frames: Frames, ctx: Context) -> Section:
    if frames["candidate_titles"].is_empty():
        return Section(
            "candidates", kpis=[Kpi("candidates", 0, "count")], charts=[], notes=[NO_CANDIDATES]
        )
    table = criteria(frames, ctx)
    return Section(
        "candidates",
        kpis=[
            Kpi("candidates", table.height, "count"),
            Kpi(
                "candidates_searched",
                table.filter(pl.col("demand_searches") > 0).height,
                "count",
                RECENT_DAYS,
            ),
            Kpi("candidates_cost", number(table[COST.key].sum()), "UAH"),
        ],
        charts=[
            Chart(
                "candidate_criteria",
                (TITLE,),
                (*CRITERIA, COST),
                records(table),
                attributes=ATTRIBUTES,
                window_days=RECENT_DAYS,
            )
        ],
    )
