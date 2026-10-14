"""Search: what members look for and what the library does not have (zero results)."""

import polars as pl

from app.domain.analytics.common import RECENT_DAYS, TOP_N, Context, Frames, ratio, records
from app.domain.analytics.model import Chart, Dimension, Kpi, Measure, Note, Section

NO_RESULT_COUNTS = Note(
    "search.no_result_counts",
    "У датасеті не записано кількість результатів пошуку, тому пошуки без результатів не показано.",
)
QUERY = Dimension("query", "category")
ZERO = pl.col("results_count") == 0


def _by_query(searches: pl.DataFrame, *extra: pl.Expr) -> pl.DataFrame:
    """Queries grouped case-insensitively; the shown text is the first spelling alphabetically."""
    return (
        searches.group_by(key=pl.col("query").str.strip_chars().str.to_lowercase())
        .agg(
            *extra,
            query=pl.col("query").str.strip_chars().min(),
            searches=pl.len(),
            searchers=pl.col("user_id").n_unique(),
        )
        .sort(pl.col("searches"), pl.col("key"), descending=[True, False])
        .head(TOP_N)
        .select("query", "searches", "searchers", *(e.meta.output_name() for e in extra))
    )


def build(frames: Frames, ctx: Context) -> Section:
    searches = frames["searches"].filter(ctx.within("searched_at", None))
    # Nested-format files do not record how many results a search returned.
    counted = searches.is_empty() or searches["results_count"].null_count() < searches.height
    last_30 = searches.filter(ctx.within("searched_at", 30))
    recent = searches.filter(ctx.within("searched_at", RECENT_DAYS))

    top_measures = (Measure("searches", "count"), Measure("searchers", "count"))
    top_extra = []
    if counted:
        top_measures += (Measure("zero_result_share", "ratio"),)
        top_extra.append(ZERO.cast(pl.Float64).mean().alias("zero_result_share"))
    charts = [
        Chart(
            "top_queries",
            (QUERY,),
            top_measures,
            records(_by_query(recent, *top_extra)),
            window_days=RECENT_DAYS,
        )
    ]
    if counted:
        charts.append(
            Chart(
                "zero_result_queries",
                (QUERY,),
                (Measure("searches", "count"), Measure("searchers", "count")),
                records(_by_query(recent.filter(ZERO))),
                window_days=RECENT_DAYS,
            )
        )
    weekly = searches.group_by(week=ctx.week("searched_at")).agg(
        searches=pl.len(), zero_result_searches=ZERO.sum()
    )
    weekly_measures = (Measure("searches", "count"),)
    if counted:
        weekly_measures += (Measure("zero_result_searches", "count"),)
    charts.append(
        Chart(
            "searches_weekly",
            (Dimension("week", "time"),),
            weekly_measures,
            records(weekly.sort("week").select("week", *(m.key for m in weekly_measures))),
        )
    )
    zero_share = ratio(last_30.filter(ZERO).height, last_30.height) if counted else None
    return Section(
        "search",
        kpis=[
            Kpi("searches", last_30.height, "count", 30),
            Kpi("searchers", last_30["user_id"].n_unique(), "count", 30),
            Kpi("zero_result_share", zero_share, "ratio", 30),
        ],
        charts=charts,
        notes=[] if counted else [NO_RESULT_COUNTS],
    )
