"""Churn models: the inactivity rule, logistic regression and gradient boosting (DESIGN.md §2.9).

Every model is fitted on labelled rows (`examples`) and predicts churn probabilities for a
features frame.
"""

from collections.abc import Callable
from typing import Any, Literal, Protocol, Self

import numpy as np
import polars as pl
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from app.domain.churn.features import FEATURES, Feature
from app.domain.enums import ENUMS

ModelKey = Literal["inactivity_rule", "logistic", "boosting"]
SKEWED_UNITS = ("count", "minutes", "days", "UAH")  # non-negative, with a long right tail


def _columns(feature: Feature) -> list[tuple[str, pl.Expr]]:
    """Matrix columns of a feature: a number (NaN when missing) or one 0/1 column per code."""
    value = pl.col(feature.key)
    if feature.enum is None:
        return [(feature.key, value.cast(pl.Float64))]
    return [
        (f"{feature.key}={code}", (value == code).fill_null(False).cast(pl.Float64))
        for code in ENUMS[feature.enum]
    ]


MATRIX = [column for feature in FEATURES for column in _columns(feature)]
COLUMNS = tuple(name for name, _ in MATRIX)
SKEWED = [COLUMNS.index(feature.key) for feature in FEATURES if feature.unit in SKEWED_UNITS]


def matrix(features: pl.DataFrame) -> np.ndarray:
    return features.select(expr.alias(name) for name, expr in MATRIX).to_numpy()


def outcomes(rows: pl.DataFrame) -> np.ndarray:
    return rows["churned"].to_numpy()


class Model(Protocol):
    key: ModelKey

    def fit(self, rows: pl.DataFrame) -> Self: ...

    def predict(self, features: pl.DataFrame) -> np.ndarray: ...


class InactivityRule:
    """The baseline: the churn rates of members inactive for 14+ days and of the others."""

    key: ModelKey = "inactivity_rule"

    def __init__(self) -> None:
        self.rates: dict[bool, float] = {}
        self.overall = 0.0

    def fit(self, rows: pl.DataFrame) -> Self:
        by_flag = rows.group_by("inactive_14d").agg(pl.col("churned").mean())
        self.rates = dict(by_flag.iter_rows())
        self.overall = rows.select(pl.col("churned").mean()).item()
        return self

    def predict(self, features: pl.DataFrame) -> np.ndarray:
        flags = features["inactive_14d"].to_list()
        return np.array([self.rates.get(flag, self.overall) for flag in flags])


class Learned:
    """A scikit-learn classifier on the feature matrix, fitted by log-loss."""

    key: ModelKey

    def __init__(self, key: ModelKey, estimator: Any) -> None:
        self.key = key
        self.estimator = estimator

    def fit(self, rows: pl.DataFrame) -> Self:
        self.estimator.fit(matrix(rows), outcomes(rows))
        return self

    def predict(self, features: pl.DataFrame) -> np.ndarray:
        return self.estimator.predict_proba(matrix(features))[:, 1]


def logistic() -> Any:
    """Counts and durations on a log scale; missing values imputed with an indicator."""
    return make_pipeline(
        ColumnTransformer(
            [("log", FunctionTransformer(np.log1p, feature_names_out="one-to-one"), SKEWED)],
            remainder="passthrough",
            verbose_feature_names_out=False,
        ),
        SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
        StandardScaler(),
        LogisticRegression(max_iter=5000),
    )


def boosting() -> Any:
    """Small trees, slow learning: a few thousand rows a year with few churners."""
    return HistGradientBoostingClassifier(
        learning_rate=0.03,
        max_iter=200,
        max_leaf_nodes=4,
        min_samples_leaf=100,
        l2_regularization=1.0,
        early_stopping=False,  # pyright: ignore[reportArgumentType]  (annotated str, takes bool)
        random_state=0,
    )


MODELS: dict[ModelKey, Callable[[], Model]] = {
    "inactivity_rule": InactivityRule,
    "logistic": lambda: Learned("logistic", logistic()),
    "boosting": lambda: Learned("boosting", boosting()),
}
