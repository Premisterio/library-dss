"""Effects of retention actions, estimated from the past randomized campaign (DESIGN.md §2.9).

An effect is a difference of churn rates: with the action minus without (negative: fewer churn).
"""

import math
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Literal

import polars as pl

from app.domain.analytics.common import Context, Frames
from app.domain.analytics.subscriptions import RENEWAL_OUTCOMES
from app.domain.churn.features import build_features

Action = Literal["email", "discount"]
Segment = Literal["dormant", "declining", "steady"]
ACTIONS: tuple[Action, ...] = ("email", "discount")
SEGMENTS: tuple[Segment, ...] = ("dormant", "declining", "steady")
DORMANT_DAYS = 30
Z = 1.959963984540054  # two-sided 95%


def segment_of() -> pl.Expr:
    """dormant: no reading for 30 days (or never); declining: fewer sessions in the last 30 days
    than in the 30 before; steady: the rest. Reads the churn features of a member."""
    days = pl.col("days_since_last_session")
    return (
        pl.when(days.is_null() | (days >= DORMANT_DAYS))
        .then(pl.lit("dormant"))
        .when(pl.col("sessions_trend") < 0)
        .then(pl.lit("declining"))
        .otherwise(pl.lit("steady"))
    )


def participants(frames: Frames, timezone: str) -> pl.DataFrame:
    """Every campaign participant: `user_id`, `arm`, `email_opt_in`, the `segment` on the day
    before the assignment and whether the renewal it targeted ended in `churned`."""
    outcomes = (
        frames["subscription_periods"]
        .filter(pl.col("outcome").is_in(RENEWAL_OUTCOMES))
        .select("user_id", "period_end", churned=pl.col("outcome") == "churned")
    )
    assigned = (
        frames["campaign_assignments"]
        .join(
            outcomes,
            left_on=["user_id", "target_period_end"],
            right_on=["user_id", "period_end"],
        )
        .with_columns(
            day=pl.col("assigned_at").dt.convert_time_zone(timezone).dt.date() - timedelta(days=1)
        )
    )
    segments = [
        build_features(_members(frames, users), Context.at(day, timezone))
        .select("user_id", "email_opt_in", segment=segment_of())
        .with_columns(day=pl.lit(day))
        for day, users in assigned.group_by("day").agg("user_id").sort("day").iter_rows()
    ]
    if not segments:
        return pl.DataFrame(
            schema={
                "user_id": pl.String,
                "arm": pl.String,
                "email_opt_in": pl.Boolean,
                "segment": pl.String,
                "churned": pl.Boolean,
            }
        )
    return (
        assigned.join(pl.concat(segments), on=["user_id", "day"])
        .select("user_id", "arm", "email_opt_in", "segment", "churned")
        .sort("user_id")
    )


def _members(frames: Frames, users: list[str]) -> dict[str, pl.DataFrame]:
    """The tables of these members only, which keeps one cutoff's features fast."""
    ids = pl.Series(users)
    return {
        name: frame.filter(pl.col("user_id").is_in(ids.implode()))
        if "user_id" in frame.columns
        else frame
        for name, frame in frames.items()
    }


@dataclass(frozen=True)
class Effect:
    action: Action
    segment: Segment | None  # None: every participant
    treated: int
    control: int
    treated_churned: int
    control_churned: int
    difference: float | None  # churn rate with the action minus without; None: no data
    low: float | None  # 95% interval (Newcombe)
    high: float | None
    shrunk: float | None  # segments: pulled toward the effect on every participant
    cautious: float | None  # the least favourable 95% bound of `shrunk`


def wilson(churned: int, n: int) -> tuple[float, float]:
    """95% Wilson score interval of a proportion."""
    p = churned / n
    centre = (p + Z * Z / (2 * n)) / (1 + Z * Z / n)
    half = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / (1 + Z * Z / n)
    return centre - half, centre + half


def compare(
    action: Action, segment: Segment | None, treated: pl.DataFrame, control: pl.DataFrame
) -> Effect:
    """The difference of churn rates with a 95% Newcombe hybrid score interval (method 10)."""
    n1, n2 = treated.height, control.height
    k1, k2 = (int(group["churned"].cast(pl.Int64).sum()) for group in (treated, control))
    if n1 == 0 or n2 == 0:
        return Effect(action, segment, n1, n2, k1, k2, None, None, None, None, None)
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    difference = p1 - p2
    low = difference - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    high = difference + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return Effect(action, segment, n1, n2, k1, k2, difference, low, high, difference, high)


def estimate(people: pl.DataFrame) -> list[Effect]:
    """Every action on every participant, then per segment, shrunk toward the former.

    E-mail is compared among members who agreed to e-mails only, since nobody else gets one.
    """
    effects: list[Effect] = []
    for action in ACTIONS:
        eligible = people.filter(pl.col("email_opt_in")) if action == "email" else people
        treated = eligible.filter(pl.col("arm") == action)
        control = eligible.filter(pl.col("arm") == "control")
        overall = compare(action, None, treated, control)
        by_segment = [
            compare(
                action,
                segment,
                treated.filter(pl.col("segment") == segment),
                control.filter(pl.col("segment") == segment),
            )
            for segment in SEGMENTS
        ]
        effects += [overall, *shrink(overall, by_segment)]
    return effects


def _se(effect: Effect) -> float | None:
    """Standard error implied by the 95% interval."""
    if effect.low is None or effect.high is None:
        return None
    return (effect.high - effect.low) / (2 * Z)


def shrink(overall: Effect, segments: list[Effect]) -> list[Effect]:
    """Empirical Bayes: each segment's difference is pulled toward the overall one, the more the
    noisier it is and the less the segments differ (DerSimonian–Laird between-segment variance).
    A segment without data takes the overall effect."""
    centre, centre_se = overall.difference, _se(overall)
    if centre is None or centre_se is None:
        return segments
    known = [(e.difference, se) for e in segments if e.difference is not None and (se := _se(e))]
    weights = [1 / se**2 for _, se in known]
    tau2 = 0.0
    if len(known) > 1:
        total = sum(weights)
        pooled = sum(w * d for w, (d, _) in zip(weights, known, strict=True)) / total
        q = sum(w * (d - pooled) ** 2 for w, (d, _) in zip(weights, known, strict=True))
        tau2 = max(0.0, (q - (len(known) - 1)) / (total - sum(w * w for w in weights) / total))
    shrunk = []
    for effect in segments:
        se = _se(effect)
        if effect.difference is None or not se:
            pull, value, own = 1.0, centre, 0.0
        else:
            pull = se**2 / (se**2 + tau2)  # 1: all the way to the overall effect
            value, own = pull * centre + (1 - pull) * effect.difference, se
        spread = math.sqrt((1 - pull) * own**2 + pull**2 * centre_se**2)
        shrunk.append(replace(effect, shrunk=value, cautious=value + Z * spread))
    return shrunk
