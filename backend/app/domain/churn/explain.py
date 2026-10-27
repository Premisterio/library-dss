"""Why a churn model predicts what it does: importance, coefficients, reasons (DESIGN.md §2.9)."""

from dataclasses import dataclass

import numpy as np
import polars as pl

from app.domain.churn.features import FEATURES, SCHEMA, FeatureGroup
from app.domain.churn.models import COLUMNS, Learned, Model, outcomes

PERMUTATION_REPEATS = 5
REASONS_PER_MEMBER = 3
MIN_EFFECT = 0.001  # a reason lowers the probability by at least this much when typical
NOT_REASONS: tuple[FeatureGroup, ...] = ("profile",)  # who a member is, not why they leave
MISSING_PREFIX = "missingindicator_"  # scikit-learn's name for an indicator column

Value = float | str | bool | None


@dataclass(frozen=True)
class Importance:
    feature: str
    brier_increase: float  # how much worse the Brier score gets when the feature is shuffled


@dataclass(frozen=True)
class Coefficient:
    feature: str
    code: str | None  # the category code of a one-hot column
    missing: bool  # the column says the value is missing
    value: float  # change of the log-odds per standard deviation of the column


@dataclass(frozen=True)
class Reason:
    feature: str
    value: Value  # the member's value
    typical: Value  # the typical value in the training rows
    effect: float  # how much lower the probability would be with the typical value


def typical_values(rows: pl.DataFrame) -> dict[str, Value]:
    """The median of each number, the most common flag or category (None: never known)."""
    typical: dict[str, Value] = {}
    for feature in FEATURES:
        known = rows[feature.key].drop_nulls()
        if known.is_empty():
            typical[feature.key] = None
        elif feature.kind == "number":
            typical[feature.key] = known.to_frame().select(pl.first().median()).item()
        else:
            typical[feature.key] = known.mode().sort()[0]
    return typical


def permutation_importance(model: Model, rows: pl.DataFrame, seed: int = 0) -> list[Importance]:
    """Brier score increase when each feature is shuffled across `rows`, most important first."""
    churned = outcomes(rows)
    rng = np.random.default_rng(seed)
    shuffled = pl.concat(
        rows.with_columns(rows[feature.key].gather(rng.permutation(rows.height)))
        for feature in FEATURES
        for _ in range(PERMUTATION_REPEATS)
    )
    predicted = model.predict(shuffled).reshape(len(FEATURES), PERMUTATION_REPEATS, rows.height)
    brier = ((predicted - churned) ** 2).mean(axis=2).mean(axis=1)
    base = float(np.mean((model.predict(rows) - churned) ** 2))
    importance = [
        Importance(feature.key, float(score - base))
        for feature, score in zip(FEATURES, brier, strict=True)
    ]
    return sorted(importance, key=lambda item: -item.brier_increase)


def coefficients(model: Model) -> list[Coefficient]:
    """The standardized coefficients of logistic regression; none for other models."""
    if not (isinstance(model, Learned) and model.key == "logistic"):
        return []
    pipeline = model.estimator
    names = pipeline[:-1].get_feature_names_out(list(COLUMNS))
    values = pipeline[-1].coef_[0]
    return [
        _coefficient(str(name), float(value)) for name, value in zip(names, values, strict=True)
    ]


def _coefficient(column: str, value: float) -> Coefficient:
    missing = column.startswith(MISSING_PREFIX)
    feature, _, code = column.removeprefix(MISSING_PREFIX).partition("=")
    return Coefficient(feature, code or None, missing, value)


def reasons(
    model: Model, features: pl.DataFrame, typical: dict[str, Value]
) -> dict[str, list[Reason]]:
    """Up to `REASONS_PER_MEMBER` reasons per member: the features whose typical value would
    lower the probability most, at most one per group, profile features never."""
    candidates = [
        feature
        for feature in FEATURES
        if feature.group not in NOT_REASONS and typical[feature.key] is not None
    ]
    if not candidates or features.is_empty():
        return {user: [] for user in features["user_id"]}
    as_typical = pl.concat(
        features.with_columns(pl.lit(typical[f.key], SCHEMA[f.key]).alias(f.key))
        for f in candidates
    )
    lower = model.predict(as_typical).reshape(len(candidates), features.height)
    effects = model.predict(features) - lower
    explained: dict[str, list[Reason]] = {}
    for i, row in enumerate(features.iter_rows(named=True)):
        chosen: list[Reason] = []
        groups: set[FeatureGroup] = set()
        for j in np.argsort(-effects[:, i], kind="stable"):
            feature = candidates[j]
            if effects[j, i] < MIN_EFFECT or len(chosen) == REASONS_PER_MEMBER:
                break
            if feature.group in groups:
                continue
            groups.add(feature.group)
            chosen.append(
                Reason(feature.key, row[feature.key], typical[feature.key], float(effects[j, i]))
            )
        explained[row["user_id"]] = chosen
    return explained
