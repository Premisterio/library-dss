"""Cohorts: of the members who joined in a month, how many are still active N months later."""

import polars as pl

from app.domain.analytics.common import (
    Context,
    Frames,
    activity,
    month_index,
    records,
    safe_div,
)
from app.domain.analytics.model import Chart, Dimension, Measure, Section

COHORT_MONTHS = 24  # cohorts shown: the last two years
MAX_OFFSET = 12  # months after joining


def build(frames: Frames, ctx: Context) -> Section:
    last = month_index(ctx.as_of)
    first = last - COHORT_MONTHS + 1
    joined = (
        frames["users"]
        .filter(ctx.within("registered_at", None))
        .select("user_id", cohort=ctx.month_index("registered_at"))
        .filter(pl.col("cohort") >= first)
    )
    active = (
        activity(frames)
        .filter(ctx.within("at", None))
        .select("user_id", month=ctx.month_index("at"))
        .unique()
        .join(joined, on="user_id")
        .with_columns(month_offset=pl.col("month") - pl.col("cohort"))
        .filter(pl.col("month_offset").is_between(0, MAX_OFFSET))
        .group_by("cohort", "month_offset")
        .agg(active_members=pl.col("user_id").n_unique())
    )
    sizes = joined.group_by("cohort").agg(members=pl.len())
    grid = pl.DataFrame(
        [
            {"cohort": cohort, "month_offset": offset}
            for cohort in sorted(sizes["cohort"].to_list())
            for offset in range(min(MAX_OFFSET, last - cohort) + 1)
        ],
        schema={"cohort": pl.Int32, "month_offset": pl.Int32},
    )
    table = (
        grid.join(sizes, on="cohort")
        .join(active, on=["cohort", "month_offset"], how="left")
        .with_columns(pl.col("active_members").fill_null(0))
        .with_columns(retention=safe_div(pl.col("active_members"), pl.col("members")))
        .sort("cohort", "month_offset")
        .with_columns(
            cohort=pl.date(pl.col("cohort") // 12, pl.col("cohort") % 12 + 1, 1),
            month_offset=pl.col("month_offset").cast(pl.Int64),
        )
    )
    return Section(
        "cohorts",
        kpis=[],
        charts=[
            Chart(
                "activity_retention",
                (Dimension("cohort", "time"), Dimension("month_offset", "number")),
                (
                    Measure("members", "count"),
                    Measure("active_members", "count"),
                    Measure("retention", "ratio"),
                ),
                records(table),
            )
        ],
    )
