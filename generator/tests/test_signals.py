"""Planted effects must be recoverable from the dataset the DSS will see (thesis validity).

These run a larger simulation (marked `slow`). Thresholds are deliberately loose: they check
that each signal is present and points the right way, not its exact size. The same metrics
are printed by `libsim validate` for the thesis.
"""

from typing import Any

import pytest

from libsim import engine, validate, writer
from libsim.params import preset

pytestmark = pytest.mark.slow
Sim = tuple[dict[str, Any], dict[str, Any]]


@pytest.fixture(scope="module")
def sim() -> Sim:
    result = engine.simulate(preset("demo", users=3000, months=18, seed=11))
    return writer.build_dataset(result), writer.build_ground_truth(result)


def test_churn_rates_are_realistic(sim: Sim) -> None:
    rate = validate.churn_rates(sim[0])
    assert 0.04 <= rate["monthly"] <= 0.12, rate
    assert 0.12 <= rate["annual"] <= 0.40, rate


def test_inactive_members_churn_more(sim: Sim) -> None:
    rate = validate.inactivity_churn(sim[0])
    assert rate["inactive"] >= 1.5 * rate["active"], rate


def test_discount_effect_is_recoverable_from_the_campaign(sim: Sim) -> None:
    effect = validate.campaign_effect(*sim, arm="discount")
    assert effect["true"] < 0, "discounts should reduce churn on average"
    assert abs(effect["estimate"] - effect["true"]) <= 2.5 * effect["se"] + 0.01, effect


def test_effects_are_heterogeneous(sim: Sim) -> None:
    h = validate.heterogeneity(sim[1])
    assert h["email_backfires_share"] > 0, "no sleeping dogs: e-mail never backfires"
    assert h["email_helps_share"] > 0
    assert h["discount_tau_sd"] > 0.1  # varies with price sensitivity


def test_genre_taste_differs_by_age(sim: Sim) -> None:
    s = validate.age_genre(sim[0])
    assert s["history_old"] - s["history_young"] >= 0.03, s
    assert s["young_adult_young"] - s["young_adult_old"] >= 0.01, s
    assert s["fantasy_young"] > s["fantasy_old"], s


def test_ratings_follow_book_quality(sim: Sim) -> None:
    r = validate.rating_quality(*sim)
    assert r["books"] >= 30
    assert r["spearman"] >= 0.4, r


def test_zero_result_searches_reveal_candidate_demand(sim: Sim) -> None:
    assert validate.candidate_demand(*sim)["spearman"] >= 0.6


def test_weekly_and_daily_rhythm(sim: Sim) -> None:
    r = validate.rhythm(sim[0])
    assert r["weekend_to_workday"] > 1.1, r
    assert r["evening_share_19_23"] > 0.3 > r["night_share_2_5"], r
