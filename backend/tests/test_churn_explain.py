"""Explanations of churn models: reasons and importance by hand with a stub model, the shape of
the explanations of a model trained on the libsim demo (DESIGN.md §2.9)."""

from datetime import date
from typing import Any

import numpy as np
import orjson
import polars as pl
import pytest

from app.domain.analytics.common import Context
from app.domain.churn import examples
from app.domain.churn.explain import (
    MIN_EFFECT,
    NOT_REASONS,
    REASONS_PER_MEMBER,
    permutation_importance,
    reasons,
    typical_values,
)
from app.domain.churn.features import FEATURES, build_features
from app.domain.churn.models import MODELS, ModelKey
from app.domain.churn.training import Training
from app.domain.enums import ENUMS
from app.ingest import reader
from app.ingest.frames import ParsedDataset

GROUP = {feature.key: feature.group for feature in FEATURES}


class Stub:
    """A model with known effects: each term raises the probability by its weight."""

    key: ModelKey = "logistic"

    def fit(self, rows: pl.DataFrame) -> Stub:
        return self

    def predict(self, features: pl.DataFrame) -> np.ndarray:
        return (
            features.select(
                0.05
                + 0.2 * (pl.col("plan") == "annual")
                + 0.03 * pl.col("lapsed_holds_30d")
                + 0.01 * pl.col("open_holds")
                + 0.02 * pl.col("inactive_14d")
                + 0.005 * pl.col("low_ratings_90d")
                + 0.0005 * pl.col("searches_30d")
                + 0.04 * (pl.col("age_range") == "65+")
            )
            .to_series()
            .to_numpy()
        )


@pytest.fixture
def churn(churn_document: dict[str, Any]) -> ParsedDataset:
    return reader.parse(reader.decode(orjson.dumps(churn_document)))


@pytest.fixture
def features(churn: ParsedDataset) -> pl.DataFrame:
    """u1, u2, u4 and u5 at the end of 2026-05-31; u4 made annual, frustrated and 65+."""
    at_cutoff = build_features(churn.frames, Context.at(date(2026, 5, 31), churn.timezone))
    u4 = pl.col("user_id") == "u4"
    return at_cutoff.with_columns(
        plan=pl.when(u4).then(pl.lit("annual")).otherwise("plan"),
        lapsed_holds_30d=pl.when(u4).then(2.0).otherwise("lapsed_holds_30d"),
        low_ratings_90d=pl.when(u4).then(1.0).otherwise("low_ratings_90d"),
        age_range=pl.when(u4).then(pl.lit("65+")).otherwise("age_range"),
    )


def test_typical_values(features: pl.DataFrame) -> None:
    typical = typical_values(features)
    assert typical["tenure_days"] == 22  # median of 89, 23, 21, 19
    assert typical["plan"] == "monthly"  # u1 and u5; u2 student, u4 annual
    assert typical["inactive_14d"] is True  # all but u1
    assert typical["email_opt_in"] is False  # a tie: the first in order
    assert typical["days_since_last_session"] == 1.125  # only u1 ever read
    without_u1 = typical_values(features.filter(pl.col("user_id") != "u1"))
    assert without_u1["days_since_last_session"] is None  # never known


def test_reasons_by_hand(features: pl.DataFrame) -> None:
    typical = {**typical_values(features), "lapsed_holds_30d": 0.0, "open_holds": 0.0}
    typical |= {"inactive_14d": False, "low_ratings_90d": 0.0, "searches_30d": 1.0}
    explained = {
        user: [(r.feature, r.value, r.typical, pytest.approx(r.effect)) for r in found]
        for user, found in reasons(Stub(), features, typical).items()
    }
    assert explained == {
        # open_holds (0.01) shares the frustration group; searches (0.0005) is too small
        "u1": [("lapsed_holds_30d", 1.0, 0.0, 0.03), ("low_ratings_90d", 1.0, 0.0, 0.005)],
        "u2": [("inactive_14d", True, False, 0.02), ("open_holds", 1.0, 0.0, 0.01)],
        # three reasons at most, and never the age (0.04)
        "u4": [
            ("plan", "annual", "monthly", 0.2),
            ("lapsed_holds_30d", 2.0, 0.0, 0.06),
            ("inactive_14d", True, False, 0.02),
        ],
        "u5": [("inactive_14d", True, False, 0.02)],
    }


def test_permutation_importance_by_hand(features: pl.DataFrame) -> None:
    rows = features.with_columns(churned=pl.col("lapsed_holds_30d") > 0)
    importance = permutation_importance(Stub(), rows)
    increase = {item.feature: item.brier_increase for item in importance}
    assert len(importance) == len(FEATURES)
    assert list(increase.values()) == sorted(increase.values(), reverse=True)
    assert increase["plan"] > 0  # the annual member churned
    assert increase["lapsed_holds_30d"] > 0  # the members with lapsed holds churned
    for unused in ("discount", "tenure_days", "sessions_30d", "education", "email_opt_in"):
        assert increase[unused] == 0


def test_logistic_coefficients_name_every_column(tabular_dataset: ParsedDataset) -> None:
    from app.domain.churn.explain import coefficients

    rows = examples(tabular_dataset.frames, tabular_dataset.as_of, tabular_dataset.timezone)
    found = coefficients(MODELS["logistic"]().fit(rows))
    assert {c.feature for c in found} == {f.key for f in FEATURES}
    assert {c.code for c in found if c.feature == "plan"} == set(ENUMS["plan"])
    may_be_missing = {f.key for f in FEATURES if f.missing}
    assert {c.feature for c in found if c.missing} <= may_be_missing
    assert coefficients(MODELS["boosting"]().fit(rows)) == []


@pytest.mark.slow
def test_explanations_of_the_demo_model(
    demo_simulation: tuple[ParsedDataset, dict[str, Any], pl.DataFrame], demo_training: Training
) -> None:
    parsed, _, _ = demo_simulation
    increases = [item.brier_increase for item in demo_training.importance]
    assert increases == sorted(increases, reverse=True)
    assert increases[0] > 0
    assert bool(demo_training.coefficients) == (demo_training.chosen == "logistic")

    features = build_features(parsed.frames, Context.at(parsed.as_of, parsed.timezone))
    explained = reasons(demo_training.model, features, demo_training.typical)
    assert set(explained) == set(features["user_id"])
    assert sum(bool(found) for found in explained.values()) > features.height / 2
    for found in explained.values():
        groups = [GROUP[r.feature] for r in found]
        assert len(found) <= REASONS_PER_MEMBER
        assert len(set(groups)) == len(groups)
        assert not set(groups) & set(NOT_REASONS)
        effects = [r.effect for r in found]
        assert effects == sorted(effects, reverse=True)
        assert all(effect >= MIN_EFFECT for effect in effects)


def test_no_reasons_without_members_or_known_values(features: pl.DataFrame) -> None:
    assert reasons(Stub(), features.clear(), typical_values(features)) == {}
    unknown = dict.fromkeys(typical_values(features))
    assert reasons(Stub(), features, unknown) == {user: [] for user in features["user_id"]}
