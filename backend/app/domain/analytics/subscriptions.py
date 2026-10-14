"""Subscriptions: paying members, MRR, churn at renewal, trial conversion and their history."""

from datetime import datetime

import polars as pl

from app.domain.analytics.common import (
    DAYS_PER_MONTH,
    RECENT_DAYS,
    Context,
    Frames,
    index_to_month,
    month_index,
    number,
    ratio,
    records,
    safe_div,
    sort_by_codes,
)
from app.domain.analytics.model import Chart, Dimension, Kpi, Measure, Note, Section
from app.domain.enums import ENUMS
from app.utils.dates import UTC_DATETIME, start_of_day_utc

HISTORY_MONTHS = 24
RENEWAL_OUTCOMES = ("renewed", "churned")
TRIAL_OUTCOMES = ("converted", "expired")
NO_OUTCOMES = Note(
    "subscriptions.no_outcomes",
    "У датасеті немає результатів продовження підписок (формат v1), "
    "тому відтік і конверсію пробного періоду не пораховано.",
)
MONTH = Dimension("month", "time")
PLAN = Dimension("plan", "category", enum="plan", order=tuple(ENUMS["plan"]))


def paid_periods(frames: Frames) -> pl.DataFrame:
    """Paid subscription periods with their monthly value (a 12-month period counts 1/12)."""
    length = (pl.col("period_end") - pl.col("period_start")).dt.total_seconds() / 86400
    months = (length / DAYS_PER_MONTH).round().clip(lower_bound=1)
    return (
        frames["subscription_periods"]
        .filter(pl.col("plan") != "trial")
        .with_columns(monthly_amount=pl.col("paid_amount") / months)
    )


def active_at(periods: pl.DataFrame, at: datetime) -> pl.DataFrame:
    """Periods that cover the instant just before `at`."""
    return periods.filter((pl.col("period_start") < at) & (pl.col("period_end") >= at))


def churn_rate(periods: pl.DataFrame, ctx: Context, days: int | None) -> float | None:
    """Share of renewal decisions in the window that ended in churn."""
    decided = periods.filter(
        ctx.within("period_end", days) & pl.col("outcome").is_in(RENEWAL_OUTCOMES)
    )
    return ratio(decided.filter(pl.col("outcome") == "churned").height, decided.height)


def outcomes_missing(frames: Frames) -> bool:
    periods = frames["subscription_periods"]
    return periods.height > 0 and periods["outcome"].null_count() == periods.height


def current_kpis(frames: Frames, ctx: Context) -> list[Kpi]:
    """Paying subscribers and MRR at the end of as_of, churn over the last 30 days."""
    periods = paid_periods(frames)
    current = active_at(periods, ctx.end)
    return [
        Kpi("paying_subscribers", current["user_id"].n_unique(), "count"),
        Kpi("mrr", number(current["monthly_amount"].sum()), "UAH"),
        Kpi("churn_rate", churn_rate(periods, ctx, 30), "ratio", 30),
    ]


def _plans(current: pl.DataFrame) -> Chart:
    by_plan = current.group_by("plan").agg(
        paying_subscribers=pl.col("user_id").n_unique(), mrr=pl.col("monthly_amount").sum()
    )
    return Chart(
        "plans",
        (PLAN,),
        (Measure("paying_subscribers", "count"), Measure("mrr", "UAH")),
        records(sort_by_codes(by_plan, "plan", ENUMS["plan"])),
    )


def _month_ends(ctx: Context, first_index: int) -> pl.DataFrame:
    """One snapshot per month: the end of the month (or of as_of for the current month)."""
    last = month_index(ctx.as_of)
    rows = [
        {
            "month": index_to_month(i),
            "at": min(start_of_day_utc(index_to_month(i + 1), ctx.timezone), ctx.end),
        }
        for i in range(max(first_index, last - HISTORY_MONTHS + 1), last + 1)
    ]
    return pl.DataFrame(rows, schema={"month": pl.Date, "at": UTC_DATETIME})


def _subscribers_monthly(periods: pl.DataFrame, ctx: Context) -> Chart:
    measures = (Measure("paying_subscribers", "count"), Measure("mrr", "UAH"))
    if periods.is_empty():
        return Chart("subscribers_monthly", (MONTH, PLAN), measures, [])
    first = periods.select(ctx.month_index("period_start").min()).item()
    snapshots = (
        _month_ends(ctx, first)
        .join(periods, how="cross")
        .filter((pl.col("period_start") < pl.col("at")) & (pl.col("period_end") >= pl.col("at")))
        .group_by("month", "plan")
        .agg(paying_subscribers=pl.col("user_id").n_unique(), mrr=pl.col("monthly_amount").sum())
    )
    return Chart(
        "subscribers_monthly",
        (MONTH, PLAN),
        measures,
        records(sort_by_codes(snapshots, "plan", ENUMS["plan"]).sort("month", maintain_order=True)),
    )


def _churn_monthly(periods: pl.DataFrame, ctx: Context) -> Chart:
    since = month_index(ctx.as_of) - HISTORY_MONTHS + 1
    decided = (
        periods.filter(ctx.within("period_end", None) & pl.col("outcome").is_in(RENEWAL_OUTCOMES))
        .filter(ctx.month_index("period_end") >= since)
        .group_by(month=ctx.month("period_end"), plan=pl.col("plan"))
        .agg(
            renewals=(pl.col("outcome") == "renewed").sum(),
            churned=(pl.col("outcome") == "churned").sum(),
        )
        .with_columns(
            churn_rate=safe_div(pl.col("churned"), pl.col("renewals") + pl.col("churned"))
        )
    )
    return Chart(
        "churn_monthly",
        (MONTH, PLAN),
        (Measure("renewals", "count"), Measure("churned", "count"), Measure("churn_rate", "ratio")),
        records(sort_by_codes(decided, "plan", ENUMS["plan"]).sort("month", maintain_order=True)),
    )


def build(frames: Frames, ctx: Context) -> Section:
    periods = paid_periods(frames)
    current = active_at(periods, ctx.end)
    trials = frames["subscription_periods"].filter(
        (pl.col("plan") == "trial")
        & ctx.within("period_end", RECENT_DAYS)
        & pl.col("outcome").is_in(TRIAL_OUTCOMES)
    )
    converted = trials.filter(pl.col("outcome") == "converted").height
    discounted = current.filter(pl.col("discount_pct") > 0).height
    return Section(
        "subscriptions",
        kpis=[
            *current_kpis(frames, ctx),
            Kpi("trial_conversion_rate", ratio(converted, trials.height), "ratio", RECENT_DAYS),
            Kpi("discounted_share", ratio(discounted, current.height), "ratio"),
        ],
        charts=[
            _plans(current),
            _subscribers_monthly(periods, ctx),
            _churn_monthly(periods, ctx),
        ],
        notes=[NO_OUTCOMES] if outcomes_missing(frames) else [],
    )
