"""How good churn probabilities are: ranking, calibration and lift (DESIGN.md §2.9)."""

import math
from dataclasses import dataclass

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

CALIBRATION_BINS = 10
TOP_SHARE = 0.1  # lift is measured on this share of members with the highest risk


@dataclass(frozen=True)
class CalibrationBin:
    predicted: float  # mean predicted probability
    observed: float  # share that churned
    members: int


@dataclass(frozen=True)
class Metrics:
    members: int
    churned: int
    roc_auc: float | None  # None: undefined, the members all churned or all stayed
    pr_auc: float | None
    brier: float
    brier_skill: float | None  # against always predicting the training churn rate
    ece: float  # expected calibration error over equal-count bins
    lift: float | None  # churn rate in the riskiest TOP_SHARE / overall churn rate
    calibration: tuple[CalibrationBin, ...]


def evaluate(churned: np.ndarray, predicted: np.ndarray, base_rate: float) -> Metrics:
    """Metrics of `predicted` probabilities against outcomes; `base_rate` from the training data."""
    y = churned.astype(float)
    both_classes = 0 < y.sum() < y.size
    brier = float(np.mean((predicted - y) ** 2))
    reference = float(np.mean((base_rate - y) ** 2))
    bins = calibration_bins(y, predicted)
    return Metrics(
        members=int(y.size),
        churned=int(y.sum()),
        roc_auc=float(roc_auc_score(y, predicted)) if both_classes else None,
        pr_auc=float(average_precision_score(y, predicted)) if both_classes else None,
        brier=brier,
        brier_skill=1 - brier / reference if reference > 0 else None,
        ece=sum(b.members * abs(b.predicted - b.observed) for b in bins) / y.size,
        lift=lift(y, predicted),
        calibration=bins,
    )


def calibration_bins(churned: np.ndarray, predicted: np.ndarray) -> tuple[CalibrationBin, ...]:
    """Members sorted by predicted risk, cut into `CALIBRATION_BINS` bins of equal size."""
    order = np.argsort(predicted, kind="stable")
    return tuple(
        CalibrationBin(float(predicted[i].mean()), float(churned[i].mean()), int(i.size))
        for i in np.array_split(order, min(CALIBRATION_BINS, order.size))
    )


def lift(churned: np.ndarray, predicted: np.ndarray) -> float | None:
    if not churned.any():
        return None
    top = np.argsort(-predicted, kind="stable")[: math.ceil(TOP_SHARE * churned.size)]
    return float(churned[top].mean() / churned.mean())
