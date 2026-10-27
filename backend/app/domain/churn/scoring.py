"""Scores of the members at risk at as_of: probability, rank and reasons (DESIGN.md §2.9)."""

from dataclasses import dataclass
from datetime import date, datetime

import polars as pl

from app.domain.analytics.common import Context, Frames
from app.domain.churn.explain import Reason, Value, reasons
from app.domain.churn.features import FEATURES, build_features
from app.domain.churn.target import at_risk
from app.domain.churn.training import Training


@dataclass(frozen=True)
class Score:
    user_id: str
    rank: int  # 1 is the highest probability; ties go by user id
    probability: float
    plan: str
    period_end: datetime
    features: dict[str, Value]
    reasons: list[Reason]


def score(training: Training, frames: Frames, as_of: date, timezone: str) -> list[Score]:
    """Every member at risk at the end of as_of, the riskiest first."""
    cutoff = Context.at(as_of, timezone)
    features = build_features(frames, cutoff)
    if features.is_empty():
        return []
    explained = reasons(training.model, features, training.typical)
    ordered = (
        features.with_columns(probability=pl.Series(training.model.predict(features)))
        .join(at_risk(frames, cutoff).select("user_id", "period_end"), on="user_id")
        .sort(["probability", "user_id"], descending=[True, False])
    )
    return [
        Score(
            user_id=row["user_id"],
            rank=rank,
            probability=row["probability"],
            plan=row["plan"],
            period_end=row["period_end"],
            features={feature.key: row[feature.key] for feature in FEATURES},
            reasons=explained[row["user_id"]],
        )
        for rank, row in enumerate(ordered.iter_rows(named=True), start=1)
    ]
