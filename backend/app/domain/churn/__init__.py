"""Churn prediction: who is at risk at a cutoff, their features and labels (DESIGN.md §2.9).

`examples` gives the labelled rows of every rolling cutoff; scoring uses `build_features` at
the cutoff of as_of.
"""

from datetime import date

import polars as pl

from app.domain.analytics.common import Frames
from app.domain.churn.features import SCHEMA, build_features
from app.domain.churn.target import history_cutoffs, labels

EXAMPLES_SCHEMA: dict[str, pl.DataType] = {"k": pl.Int32(), **SCHEMA, "churned": pl.Boolean()}


def examples(frames: Frames, as_of: date, timezone: str) -> pl.DataFrame:
    """Labelled rows of every history cutoff: `k`, `user_id`, the features and `churned`."""
    parts = [
        build_features(frames, cutoff)
        .join(labels(frames, cutoff), on="user_id")
        .with_columns(k=pl.lit(k, pl.Int32))
        .select(list(EXAMPLES_SCHEMA))
        for k, cutoff in enumerate(history_cutoffs(frames, as_of, timezone))
    ]
    return pl.concat(parts) if parts else pl.DataFrame(schema=EXAMPLES_SCHEMA)
