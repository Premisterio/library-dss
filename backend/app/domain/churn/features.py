"""Features of the churn model: what was known about a member at a cutoff (DESIGN.md §2.9).

`build_features` is the only feature code, for training and scoring alike.
"""

from dataclasses import dataclass
from typing import Literal

import polars as pl

from app.domain.analytics.common import Context, Frames, activity, safe_div
from app.domain.analytics.model import Unit
from app.domain.analytics.subscriptions import paid_periods
from app.domain.churn.target import at_risk

FeatureKind = Literal["number", "flag", "category"]


@dataclass(frozen=True)
class Feature:
    key: str  # column of the features frame, label in enums "churn_feature"
    kind: FeatureKind
    unit: Unit | None = None  # numbers only; None: a unitless number
    enum: str | None = None  # categories: the enums group of their codes
    missing: bool = False  # may be null (unknown or undefined), never replaced by 0


FEATURES: tuple[Feature, ...] = (
    # the running paid period
    Feature("plan", "category", enum="plan"),
    Feature("monthly_price", "number", "UAH"),
    Feature("discount", "number", "ratio", missing=True),
    Feature("tenure_days", "number", "days"),
    Feature("days_to_renewal", "number", "days"),
    # activity
    Feature("sessions_7d", "number", "count"),
    Feature("sessions_30d", "number", "count"),
    Feature("reading_minutes_30d", "number", "minutes"),
    Feature("sessions_trend", "number"),
    Feature("days_since_last_session", "number", "days", missing=True),
    Feature("inactive_14d", "flag"),
    Feature("active_days_30d", "number", "count"),
    Feature("loans_30d", "number", "count"),
    Feature("open_loans", "number", "count"),
    Feature("searches_30d", "number", "count"),
    # what the member read
    Feature("completed_90d", "number", "count"),
    Feature("completion_rate_90d", "number", "ratio", missing=True),
    Feature("avg_rating_90d", "number", "rating", missing=True),
    Feature("low_ratings_90d", "number", "count"),
    # frustrations
    Feature("lapsed_holds_30d", "number", "count"),
    Feature("open_holds", "number", "count"),
    Feature("zero_result_searches_30d", "number", "count"),
    # profile
    Feature("age_range", "category", enum="age_range", missing=True),
    Feature("education", "category", enum="education", missing=True),
    Feature("language_pref", "category", enum="language_pref", missing=True),
    Feature("email_opt_in", "flag", missing=True),
)
DTYPES = {"number": pl.Float64, "flag": pl.Boolean, "category": pl.String}
SCHEMA: dict[str, pl.DataType] = {
    "user_id": pl.String(),
    **{feature.key: DTYPES[feature.kind]() for feature in FEATURES},
}
# Event counts: no events means 0, not unknown.
COUNTS = (
    "sessions_7d",
    "sessions_30d",
    "sessions_previous_30d",
    "reading_minutes_30d",
    "active_days_30d",
    "loans_30d",
    "open_loans",
    "searches_30d",
    "completed_90d",
    "low_ratings_90d",
    "lapsed_holds_30d",
    "open_holds",
    "zero_result_searches_30d",
)


def build_features(frames: Frames, cutoff: Context) -> pl.DataFrame:
    """One row per member at risk at the cutoff: `user_id` and every feature, by user id."""
    members = at_risk(frames, cutoff)
    ids = members.select("user_id")
    features = ids
    for part in (
        _subscription(frames, members, cutoff),
        _reading(frames, ids, cutoff),
        _activity(frames, ids, cutoff),
        _loans(frames, ids, cutoff),
        _holds(frames, ids, cutoff),
        _searches(frames, ids, cutoff),
        _profile(frames, ids),
    ):
        features = features.join(part, on="user_id", how="left")
    return (
        features.with_columns(pl.col(COUNTS).fill_null(0))
        .with_columns(
            sessions_trend=(
                (1 + pl.col("sessions_30d")) / (1 + pl.col("sessions_previous_30d"))
            ).log(),
            days_since_last_session=_days(pl.lit(cutoff.end) - pl.col("last_session")),
            inactive_14d=pl.col("last_session").is_null()
            | (pl.col("last_session") < cutoff.since(14)),
        )
        .select(pl.col(name).cast(dtype) for name, dtype in SCHEMA.items())
        .sort("user_id")
    )


def _days(duration: pl.Expr) -> pl.Expr:
    return duration.dt.total_seconds() / 86400


def _events(
    frames: Frames, table: str, ids: pl.DataFrame, at: str, cutoff: Context
) -> pl.DataFrame:
    """Rows of the at-risk members dated before the cutoff."""
    return frames[table].join(ids, on="user_id", how="semi").filter(pl.col(at) < cutoff.end)


def _still_open(resolved: str, cutoff: Context) -> pl.Expr:
    """Not resolved at the cutoff, even if it was resolved later."""
    return pl.col(resolved).is_null() | (pl.col(resolved) >= cutoff.end)


def _subscription(frames: Frames, members: pl.DataFrame, cutoff: Context) -> pl.DataFrame:
    first_paid = (
        paid_periods(frames)
        .filter(pl.col("period_start") < cutoff.end)
        .group_by("user_id")
        .agg(first_paid=pl.col("period_start").min())
    )
    return members.join(first_paid, on="user_id").select(
        "user_id",
        "plan",
        monthly_price="monthly_amount",
        discount=safe_div(pl.col("list_price") - pl.col("paid_amount"), pl.col("list_price")).clip(
            lower_bound=0
        ),
        tenure_days=_days(pl.lit(cutoff.end) - pl.col("first_paid")),
        days_to_renewal=_days(pl.col("period_end") - pl.lit(cutoff.end)),
    )


def _reading(frames: Frames, ids: pl.DataFrame, cutoff: Context) -> pl.DataFrame:
    previous = (pl.col("started_at") >= cutoff.since(60)) & (
        pl.col("started_at") < cutoff.since(30)
    )
    recent = cutoff.within("started_at", 30)
    return (
        _events(frames, "reading_sessions", ids, "started_at", cutoff)
        .group_by("user_id")
        .agg(
            sessions_7d=cutoff.within("started_at", 7).sum(),
            sessions_30d=recent.sum(),
            sessions_previous_30d=previous.sum(),
            reading_minutes_30d=pl.col("minutes").filter(recent).sum(),
            last_session=pl.col("started_at").max(),
        )
    )


def _activity(frames: Frames, ids: pl.DataFrame, cutoff: Context) -> pl.DataFrame:
    return (
        activity(frames)
        .join(ids, on="user_id", how="semi")
        .filter(cutoff.within("at", 30))
        .group_by("user_id")
        .agg(active_days_30d=cutoff.local("at").dt.date().n_unique())
    )


def _loans(frames: Frames, ids: pl.DataFrame, cutoff: Context) -> pl.DataFrame:
    returned = cutoff.within("returned_at", 90)
    return (
        _events(frames, "loans", ids, "borrowed_at", cutoff)
        .group_by("user_id")
        .agg(
            loans_30d=cutoff.within("borrowed_at", 30).sum(),
            open_loans=_still_open("returned_at", cutoff).sum(),
            completed_90d=(returned & pl.col("completed")).sum(),
            completion_rate_90d=pl.col("completed").cast(pl.Float64).filter(returned).mean(),
            avg_rating_90d=pl.col("rating").filter(returned).mean(),
            low_ratings_90d=(returned & (pl.col("rating") <= 2)).sum(),
        )
    )


def _holds(frames: Frames, ids: pl.DataFrame, cutoff: Context) -> pl.DataFrame:
    lapsed = cutoff.within("resolved_at", 30) & (pl.col("outcome") == "lapsed")
    return (
        _events(frames, "holds", ids, "placed_at", cutoff)
        .group_by("user_id")
        .agg(lapsed_holds_30d=lapsed.sum(), open_holds=_still_open("resolved_at", cutoff).sum())
    )


def _searches(frames: Frames, ids: pl.DataFrame, cutoff: Context) -> pl.DataFrame:
    return (
        _events(frames, "searches", ids, "searched_at", cutoff)
        .filter(cutoff.within("searched_at", 30))
        .group_by("user_id")
        .agg(
            searches_30d=pl.len(),
            zero_result_searches_30d=(pl.col("results_count") == 0).sum(),
        )
    )


def _profile(frames: Frames, ids: pl.DataFrame) -> pl.DataFrame:
    return (
        frames["users"]
        .join(ids, on="user_id", how="semi")
        .select("user_id", "age_range", "education", "language_pref", "email_opt_in")
    )
