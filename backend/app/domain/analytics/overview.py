"""Overview: the headline numbers of the library as of the snapshot date, weekly activity."""

import polars as pl

from app.domain.analytics import subscriptions
from app.domain.analytics.common import Context, Frames, activity, number, records
from app.domain.analytics.model import Chart, Dimension, Kpi, Measure, Section


def _activity_weekly(frames: Frames, ctx: Context) -> Chart:
    active = (
        activity(frames)
        .filter(ctx.within("at", None))
        .group_by(week=ctx.week("at"))
        .agg(active_members=pl.col("user_id").n_unique())
    )
    loans = (
        frames["loans"]
        .filter(ctx.within("borrowed_at", None))
        .group_by(week=ctx.week("borrowed_at"))
        .agg(loans=pl.len())
    )
    minutes = (
        frames["reading_sessions"]
        .filter(ctx.within("started_at", None))
        .group_by(week=ctx.week("started_at"))
        .agg(reading_minutes=pl.col("minutes").sum())
    )
    weekly = (
        active.join(loans, on="week", how="full", coalesce=True)
        .join(minutes, on="week", how="full", coalesce=True)
        .with_columns(pl.col("active_members", "loans", "reading_minutes").fill_null(0))
        .filter(ctx.complete_weeks())
        .sort("week")
    )
    return Chart(
        "activity_weekly",
        (Dimension("week", "time"),),
        (
            Measure("active_members", "count"),
            Measure("loans", "count"),
            Measure("reading_minutes", "minutes"),
        ),
        records(weekly.select("week", "active_members", "loans", "reading_minutes")),
    )


def build(frames: Frames, ctx: Context) -> Section:
    recent_loans = frames["loans"].filter(ctx.within("borrowed_at", 30))
    recent_sessions = frames["reading_sessions"].filter(ctx.within("started_at", 30))
    active = activity(frames).filter(ctx.within("at", 30))["user_id"].n_unique()
    return Section(
        "overview",
        kpis=[
            Kpi("members", frames["users"].height, "count"),
            Kpi("active_members", active, "count", 30),
            *subscriptions.current_kpis(frames, ctx),
            Kpi("loans", recent_loans.height, "count", 30),
            Kpi("reading_minutes", number(recent_sessions["minutes"].sum()), "minutes", 30),
        ],
        charts=[_activity_weekly(frames, ctx)],
        notes=[subscriptions.NO_OUTCOMES] if subscriptions.outcomes_missing(frames) else [],
    )
