"""Who the churn model scores and what it predicts, at a cutoff (see DESIGN.md §2.9).

A cutoff is the end of a local day, a `Context`: the moment a prediction is made.
"""

from datetime import date, datetime, timedelta
from typing import Literal

import polars as pl

from app.domain.analytics.common import Context, Frames
from app.domain.analytics.subscriptions import RENEWAL_OUTCOMES, active_at, paid_periods
from app.utils.dates import end_of_day_utc

RISK_WINDOW_DAYS = 30
Role = Literal["train", "calibration", "test"]


def horizon_end(cutoff: Context) -> datetime:
    """The end of the risk window: the end of the local day `RISK_WINDOW_DAYS` later."""
    return end_of_day_utc(cutoff.as_of + timedelta(days=RISK_WINDOW_DAYS), cutoff.timezone)


def at_risk(frames: Frames, cutoff: Context) -> pl.DataFrame:
    """The running paid period of every member whose period ends in the risk window."""
    running = (
        active_at(paid_periods(frames), cutoff.end)
        .sort("period_start")
        .unique("user_id", keep="last")
    )
    return running.filter(pl.col("period_end") < horizon_end(cutoff)).sort("user_id")


def labels(frames: Frames, cutoff: Context) -> pl.DataFrame:
    """`user_id`, `churned`: how the at-risk periods ended, for renewals without an action."""
    treated = (
        frames["campaign_assignments"]
        .filter(pl.col("delivered"))
        .select("user_id", period_end="target_period_end")
    )
    return (
        at_risk(frames, cutoff)
        .filter(pl.col("outcome").is_in(RENEWAL_OUTCOMES))
        .join(treated, on=["user_id", "period_end"], how="anti")
        .select("user_id", churned=pl.col("outcome") == "churned")
    )


def history_cutoffs(frames: Frames, as_of: date, timezone: str) -> list[Context]:
    """Labelled cutoffs, newest first, back to the first paid period.

    Cutoff k is `RISK_WINDOW_DAYS · (k + 1)` days before as_of, so the risk window of k = 0
    ends at as_of and the windows never overlap.
    """
    first = paid_periods(frames).select(pl.col("period_start").min()).item()
    cutoffs: list[Context] = []
    while first is not None:
        days = RISK_WINDOW_DAYS * (len(cutoffs) + 1)
        cutoff = Context.at(as_of - timedelta(days=days), timezone)
        if cutoff.end <= first:
            break
        cutoffs.append(cutoff)
    return cutoffs


def role(k: int) -> Role:
    """What cutoff k is for: the newest tests, the one before calibrates, older ones train."""
    return "test" if k == 0 else "calibration" if k == 1 else "train"
