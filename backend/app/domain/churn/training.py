"""Backtest the churn models over the rolling cutoffs and choose one (DESIGN.md §2.9)."""

from dataclasses import dataclass

import numpy as np
import polars as pl

from app.domain.churn.metrics import Metrics, evaluate
from app.domain.churn.models import MODELS, Model, ModelKey, outcomes

LEARNED: tuple[ModelKey, ...] = ("logistic", "boosting")  # the inactivity rule is the baseline
BACKTEST_ORIGINS = 6


class NotEnoughHistoryError(ValueError):
    """The newest cutoffs have no churn or no renewal to learn from or to test on."""


@dataclass(frozen=True)
class Split:
    """Cutoff `origin` tests; every older cutoff trains."""

    origin: int
    train: pl.DataFrame
    test: pl.DataFrame

    @classmethod
    def at(cls, rows: pl.DataFrame, origin: int) -> Split:
        return cls(origin, rows.filter(pl.col("k") > origin), rows.filter(pl.col("k") == origin))

    def usable(self) -> bool:
        return all(_both_outcomes(part) for part in (self.train, self.test))


@dataclass(frozen=True)
class Evaluation:
    origin: int
    model: ModelKey
    metrics: Metrics


@dataclass(frozen=True)
class Training:
    evaluations: list[Evaluation]  # every model at every usable backtest origin
    chosen: ModelKey
    model: Model  # the chosen model refitted on every cutoff, for scoring

    def mean(self, model: ModelKey, metric: str) -> float:
        """A metric of a model averaged over the backtest origins."""
        values = [getattr(e.metrics, metric) for e in self.evaluations if e.model == model]
        return float(np.mean(values))


def backtest(rows: pl.DataFrame, origins: int = BACKTEST_ORIGINS) -> list[Evaluation]:
    """Every model trained and tested at origins 0, 1, …, skipping unusable ones but origin 0."""
    if not Split.at(rows, 0).usable():
        raise NotEnoughHistoryError("Need churn and renewals at the newest cutoff and before it")
    evaluations: list[Evaluation] = []
    for origin in range(origins):
        split = Split.at(rows, origin)
        if not split.usable():
            continue
        base_rate = float(outcomes(split.train).mean())
        for key, make in MODELS.items():
            predicted = make().fit(split.train).predict(split.test)
            evaluations.append(
                Evaluation(origin, key, evaluate(outcomes(split.test), predicted, base_rate))
            )
    return evaluations


def train(rows: pl.DataFrame, origins: int = BACKTEST_ORIGINS) -> Training:
    """Choose the learned model with the lowest mean Brier score over the backtest (then the
    lowest mean ECE) and refit it on every cutoff."""
    evaluations = backtest(rows, origins)

    def score(key: ModelKey) -> tuple[float, float]:
        mine = [e.metrics for e in evaluations if e.model == key]
        return float(np.mean([m.brier for m in mine])), float(np.mean([m.ece for m in mine]))

    chosen = min(LEARNED, key=score)
    return Training(evaluations, chosen, MODELS[chosen]().fit(rows))


def _both_outcomes(rows: pl.DataFrame) -> bool:
    return bool(rows["churned"].any()) and not rows["churned"].all()
