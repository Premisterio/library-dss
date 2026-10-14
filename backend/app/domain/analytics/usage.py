"""Usage: when and on what members read, and how recently they were active."""

import polars as pl

from app.domain.analytics.common import (
    RECENT_DAYS,
    WEEKDAYS,
    Context,
    Frames,
    activity,
    number,
    ratio,
    records,
)
from app.domain.analytics.model import Chart, Dimension, Kpi, Measure, Section

# Days since the last activity, counted back from the end of as_of (never from "today").
RECENCY = ("days_0_7", "days_8_30", "days_31_90", "days_91_plus", "never")


def _heatmap(sessions: pl.DataFrame, ctx: Context) -> Chart:
    local = ctx.local("started_at")
    counts = (
        sessions.filter(ctx.within("started_at", RECENT_DAYS))
        .group_by(weekday=local.dt.weekday().cast(pl.Int8), hour=local.dt.hour().cast(pl.Int8))
        .agg(sessions=pl.len(), reading_minutes=pl.col("minutes").sum())
    )
    grid = pl.DataFrame({"weekday": range(1, 8)}, schema={"weekday": pl.Int8}).join(
        pl.DataFrame({"hour": range(24)}, schema={"hour": pl.Int8}), how="cross"
    )
    cells = (
        grid.join(counts, on=["weekday", "hour"], how="left")
        .with_columns(pl.col("sessions", "reading_minutes").fill_null(0))
        .sort("weekday", "hour")
        .with_columns(
            weekday=pl.col("weekday").replace_strict(
                dict(enumerate(WEEKDAYS, start=1)), return_dtype=pl.String
            ),
            hour=pl.col("hour").cast(pl.Int64),
        )
    )
    return Chart(
        "reading_heatmap",
        (
            Dimension("weekday", "category", enum="weekday", order=WEEKDAYS),
            Dimension("hour", "number"),
        ),
        (Measure("sessions", "count"), Measure("reading_minutes", "minutes")),
        records(cells),
        window_days=RECENT_DAYS,
    )


def _devices(sessions: pl.DataFrame, ctx: Context) -> Chart:
    by_device = (
        sessions.filter(ctx.within("started_at", RECENT_DAYS))
        .group_by("device")
        .agg(sessions=pl.len(), reading_minutes=pl.col("minutes").sum())
        .with_columns(share=pl.col("sessions") / pl.col("sessions").sum())
        .sort(pl.col("sessions"), pl.col("device"), descending=[True, False], nulls_last=True)
    )
    return Chart(
        "devices",
        (Dimension("device", "category", enum="device"),),
        (
            Measure("sessions", "count"),
            Measure("reading_minutes", "minutes"),
            Measure("share", "ratio"),
        ),
        records(by_device),
        window_days=RECENT_DAYS,
    )


def _recency(frames: Frames, ctx: Context) -> Chart:
    last = (
        activity(frames).filter(ctx.within("at", None)).group_by("user_id").agg(last=pl.max("at"))
    )
    bucket = (
        pl.when(pl.col("last").is_null())
        .then(pl.lit("never"))
        .when(pl.col("last") >= ctx.since(7))
        .then(pl.lit("days_0_7"))
        .when(pl.col("last") >= ctx.since(30))
        .then(pl.lit("days_8_30"))
        .when(pl.col("last") >= ctx.since(90))
        .then(pl.lit("days_31_90"))
        .otherwise(pl.lit("days_91_plus"))
    )
    counts = (
        frames["users"]
        .select("user_id")
        .join(last, on="user_id", how="left")
        .group_by(recency=bucket)
        .agg(members=pl.len())
    )
    buckets = (
        pl.DataFrame({"recency": RECENCY})
        .join(counts, on="recency", how="left")
        .with_columns(pl.col("members").fill_null(0))
        .with_columns(share=pl.col("members") / pl.col("members").sum())
    )
    return Chart(
        "recency",
        (Dimension("recency", "category", enum="recency", order=RECENCY),),
        (Measure("members", "count"), Measure("share", "ratio")),
        records(buckets),
    )


def build(frames: Frames, ctx: Context) -> Section:
    sessions = frames["reading_sessions"]
    recent = sessions.filter(ctx.within("started_at", 30))
    minutes = number(recent["minutes"].sum())
    active = activity(frames).filter(ctx.within("at", 30))["user_id"].n_unique()
    return Section(
        "usage",
        kpis=[
            Kpi("sessions", recent.height, "count", 30),
            Kpi("reading_minutes", minutes, "minutes", 30),
            Kpi("avg_session_minutes", number(recent["minutes"].mean()), "minutes", 30),
            Kpi("minutes_per_active_member", ratio(minutes, active), "minutes", 30),
        ],
        charts=[_heatmap(sessions, ctx), _devices(sessions, ctx), _recency(frames, ctx)],
    )
