"""Churn models and metrics: metrics by hand, the training procedure, quality against libsim.

The quality test runs the demo simulation (5k members, 24 months) and compares the chosen
model with libsim's ground truth on the members at risk at as_of (DESIGN.md §2.9).
"""

from datetime import date
from typing import Any

import numpy as np
import orjson
import polars as pl
import pytest
from sklearn.metrics import roc_auc_score

from app.domain.analytics.common import Context
from app.domain.churn import examples
from app.domain.churn.features import build_features
from app.domain.churn.metrics import evaluate
from app.domain.churn.models import COLUMNS, MODELS, InactivityRule, matrix
from app.domain.churn.training import LEARNED, NotEnoughHistoryError, backtest, train
from app.ingest import reader
from app.ingest.frames import ParsedDataset

# Ten bins of two members with the same probability; churners per bin.
BIN_P = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]
BIN_CHURNED = [0, 0, 0, 1, 0, 1, 1, 1, 2, 2]


def test_metrics_by_hand() -> None:
    predicted = np.repeat(BIN_P, 2)
    churned = np.array([flag for c in BIN_CHURNED for flag in (c >= 1, c >= 2)])
    metrics = evaluate(churned, predicted, base_rate=0.4)
    assert metrics.members == 20
    assert metrics.churned == 8
    # positives beat 86 of 96 (positive, negative) pairs, counting ties as halves
    assert metrics.roc_auc == pytest.approx(86 / 96)
    # precision at each new recall: 1, 1, 5/6, 6/8, 7/10, 8/14
    assert metrics.pr_auc == pytest.approx((2 + 2 + 5 / 6 + 6 / 8 + 7 / 10 + 8 / 14) / 8)
    assert metrics.brier == pytest.approx(2.85 / 20)
    # always 0.4: 8 churners off by 0.6, 12 others by 0.4
    assert metrics.brier_skill == pytest.approx(1 - (2.85 / 20) / ((8 * 0.36 + 12 * 0.16) / 20))
    third = metrics.calibration[3]
    assert (third.predicted, third.observed, third.members) == (pytest.approx(0.35), 0.5, 2)
    assert metrics.ece == pytest.approx(1.7 / 10)
    assert metrics.lift == pytest.approx(1 / 0.4)  # the riskiest 10%: both 0.95 churned


def test_metrics_of_one_class() -> None:
    metrics = evaluate(np.zeros(4, dtype=bool), np.array([0.1, 0.2, 0.3, 0.4]), base_rate=0.0)
    assert (metrics.roc_auc, metrics.pr_auc, metrics.lift, metrics.brier_skill) == (None,) * 4
    assert metrics.brier == pytest.approx((0.01 + 0.04 + 0.09 + 0.16) / 4)
    assert len(metrics.calibration) == 4


@pytest.fixture
def churn(churn_document: dict[str, Any]) -> ParsedDataset:
    return reader.parse(reader.decode(orjson.dumps(churn_document)))


def test_matrix_columns(churn: ParsedDataset) -> None:
    features = build_features(churn.frames, Context.at(date(2026, 5, 31), churn.timezone))
    rows = dict(zip(features["user_id"], matrix(features), strict=True))
    u2 = dict(zip(COLUMNS, rows["u2"], strict=True))
    assert u2["plan=student"] == 1
    assert u2["plan=monthly"] == 0
    assert u2["inactive_14d"] == 1
    assert u2["email_opt_in"] == 0
    assert np.isnan(u2["days_since_last_session"])  # never read: missing, not 0
    assert u2["open_holds"] == 1


def test_inactivity_rule_predicts_the_rates_it_saw() -> None:
    rows = pl.DataFrame(
        {
            "inactive_14d": [True, True, True, False, False],
            "churned": [True, False, False, False, False],
        }
    )
    rule = InactivityRule().fit(rows)
    assert rule.predict(rows).tolist() == pytest.approx([1 / 3] * 3 + [0.0] * 2)


@pytest.fixture(scope="module")
def simulated() -> tuple[ParsedDataset, dict[str, Any], pl.DataFrame]:
    from libsim import engine, writer
    from libsim.params import preset

    result = engine.simulate(preset("demo", seed=1))
    parsed = reader.parse(reader.decode(orjson.dumps(writer.build_dataset(result))))
    rows = examples(parsed.frames, parsed.as_of, parsed.timezone)
    return parsed, writer.build_ground_truth(result), rows


@pytest.mark.slow
def test_chosen_model_is_close_to_the_best_achievable(
    simulated: tuple[ParsedDataset, dict[str, Any], pl.DataFrame],
) -> None:
    """Done criteria of M4a: within 0.05 AUC of the true probabilities, a better Brier score
    than the inactivity rule, on members whose renewal comes after as_of."""
    parsed, truth, rows = simulated
    training = train(rows)
    assert training.chosen in LEARNED
    assert training.mean(training.chosen, "brier") < training.mean("inactivity_rule", "brier")

    features = build_features(parsed.frames, Context.at(parsed.as_of, parsed.timezone))
    outcome = {
        row["user_id"]: (row["p_true"]["none"], row["outcome"]["none"]) for row in truth["at_risk"]
    }
    assert features["user_id"].to_list() == sorted(outcome)
    p_true, churned = map(np.array, zip(*(outcome[u] for u in features["user_id"]), strict=True))
    predicted = training.model.predict(features)
    best = roc_auc_score(churned, p_true)
    assert roc_auc_score(churned, predicted) >= best - 0.05
    rule = MODELS["inactivity_rule"]().fit(rows).predict(features)
    assert np.mean((predicted - churned) ** 2) < np.mean((rule - churned) ** 2)


@pytest.mark.slow
def test_backtest_covers_every_model_and_origin(
    simulated: tuple[ParsedDataset, dict[str, Any], pl.DataFrame],
) -> None:
    _, _, rows = simulated
    evaluations = backtest(rows, origins=3)
    assert [(e.origin, e.model) for e in evaluations] == [
        (origin, model) for origin in range(3) for model in MODELS
    ]
    for e in evaluations:
        assert e.metrics.members == rows.filter(pl.col("k") == e.origin).height
        assert 0 < e.metrics.brier < 0.25
    without_churn = rows.filter((pl.col("k") != 1) | ~pl.col("churned"))
    assert {e.origin for e in backtest(without_churn, origins=3)} == {0, 2}


@pytest.mark.slow
def test_training_is_deterministic(
    simulated: tuple[ParsedDataset, dict[str, Any], pl.DataFrame],
) -> None:
    _, _, rows = simulated
    features = rows.filter(pl.col("k") == 0)
    first, second = train(rows, origins=1), train(rows, origins=1)
    assert first.chosen == second.chosen
    assert first.model.predict(features).tolist() == second.model.predict(features).tolist()


def test_too_little_history(churn: ParsedDataset) -> None:
    rows = examples(churn.frames, churn.as_of, churn.timezone)  # five rows over three cutoffs
    with pytest.raises(NotEnoughHistoryError):
        train(rows)
