"""Segments: who the members are and what each age group reads."""

import polars as pl

from app.domain.analytics import subscriptions
from app.domain.analytics.common import Context, Frames, activity, records, sort_by_codes
from app.domain.analytics.model import Chart, Dimension, Measure, Section
from app.domain.enums import ENUMS

AGE = Dimension("age_range", "category", enum="age_range", order=tuple(ENUMS["age_range"]))
EDUCATION = Dimension("education", "category", enum="education", order=tuple(ENUMS["education"]))
MEMBER_MEASURES = (
    Measure("members", "count"),
    Measure("active_members", "count", window_days=30),
    Measure("paying_subscribers", "count"),
)


def _age_genre(frames: Frames, ctx: Context) -> Chart:
    loans = (
        frames["loans"]
        .filter(ctx.within("borrowed_at", None))
        .join(frames["users"].select("user_id", "age_range"), on="user_id")
        .join(frames["books"].select("book_id", "genre"), on="book_id")
        .group_by("age_range", "genre")
        .agg(loans=pl.len())
        .with_columns(share=pl.col("loans") / pl.col("loans").sum().over("age_range"))
        .sort(pl.col("loans"), pl.col("genre"), descending=[True, False])
    )
    return Chart(
        "age_genre",
        (AGE, Dimension("genre", "category", enum="genre")),
        (Measure("loans", "count"), Measure("share", "ratio")),
        records(sort_by_codes(loans, "age_range", ENUMS["age_range"])),
    )


def _members_by(column: str, members: pl.DataFrame, dimension: Dimension) -> Chart:
    by_group = members.group_by(column).agg(
        members=pl.len(),
        active_members=pl.col("active").sum(),
        paying_subscribers=pl.col("paying").sum(),
    )
    return Chart(
        f"members_by_{column.removesuffix('_range')}",
        (dimension,),
        MEMBER_MEASURES,
        records(sort_by_codes(by_group, column, dimension.order or ())),
    )


def build(frames: Frames, ctx: Context) -> Section:
    active = activity(frames).filter(ctx.within("at", 30))["user_id"].unique()
    paying = subscriptions.active_at(subscriptions.paid_periods(frames), ctx.end)["user_id"]
    members = frames["users"].with_columns(
        active=pl.col("user_id").is_in(active.implode()),
        paying=pl.col("user_id").is_in(paying.unique().implode()),
    )
    return Section(
        "segments",
        kpis=[],
        charts=[
            _age_genre(frames, ctx),
            _members_by("age_range", members, AGE),
            _members_by("education", members, EDUCATION),
        ],
    )
