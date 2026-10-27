"""The retention plan: gains by hand, the MILP against brute force on small problems, the effect
table and the speed on a realistic risk group (DESIGN.md §2.9)."""

import itertools
import time
from typing import Any

import numpy as np
import polars as pl
import pytest

from app.domain.retention.effects import ACTIONS, SEGMENTS, Effect
from app.domain.retention.plan import (
    MIP_GAP,
    EffectTable,
    Scenario,
    curve,
    effect_table,
    greedy,
    options,
    plan,
    solve,
)

MEMBER_SCHEMA = {
    "user_id": pl.String,
    "probability": pl.Float64,
    "segment": pl.String,
    "email_opt_in": pl.Boolean,
    "discounted": pl.Boolean,
    "monthly_value": pl.Float64,
    "period_price": pl.Float64,
}


def members(*rows: dict[str, Any]) -> pl.DataFrame:
    defaults = {
        "segment": "steady",
        "email_opt_in": True,
        "discounted": False,
        "monthly_value": 100.0,
        "period_price": 100.0,
    }
    return pl.DataFrame([{**defaults, **row} for row in rows], schema=MEMBER_SCHEMA)


def table(email: float, discount: float) -> EffectTable:
    return {(a, s): email if a == "email" else discount for a in ACTIONS for s in SEGMENTS}


ONE = members({"user_id": "u1", "probability": 0.3})
EFFECTS = table(email=-0.05, discount=-0.1)


def test_gains_by_hand() -> None:
    found = options(ONE, EFFECTS, Scenario(budget=100))
    assert found.select("action", "p_action", "gain", "spend").rows() == [
        # 0.25 · nothing given away; kept: 0.05 · 100 UAH · 12 months = 60, minus the e-mail
        (
            "discount",
            pytest.approx(0.2),
            pytest.approx(0.1 * 1200 - 0.8 * 0.2 * 100),
            pytest.approx(16),
        ),
        ("email", pytest.approx(0.25), pytest.approx(58.0), 2.0),
    ]


def test_the_best_action_within_the_budget() -> None:
    assert plan(ONE, EFFECTS, Scenario(budget=100)).chosen["action"].to_list() == ["discount"]
    assert plan(ONE, EFFECTS, Scenario(budget=10)).chosen["action"].to_list() == ["email"]
    limited = Scenario(budget=100, max_discounts=0)
    assert plan(ONE, EFFECTS, limited).chosen["action"].to_list() == ["email"]
    assert plan(ONE, EFFECTS, Scenario(budget=1)).chosen.is_empty()


def test_who_can_get_what() -> None:
    group = members(
        {"user_id": "no_consent", "probability": 0.3, "email_opt_in": False},
        {"user_id": "discounted", "probability": 0.3, "discounted": True},
        {"user_id": "no_price", "probability": 0.3, "period_price": None},
    )
    found = {
        (r["user_id"], r["action"])
        for r in options(group, EFFECTS, Scenario(1)).iter_rows(named=True)
    }
    assert found == {("no_consent", "discount"), ("discounted", "email"), ("no_price", "email")}


def test_harmful_actions_are_never_taken() -> None:
    """An e-mail that makes a dormant member more likely to leave gains nothing."""
    effects: EffectTable = {**EFFECTS, ("email", "dormant"): 0.03}
    dormant = members({"user_id": "u1", "probability": 0.3, "segment": "dormant"})
    assert options(dormant, effects, Scenario(100))["action"].to_list() == ["discount"]


def test_effect_table() -> None:
    def effect(action: Any, segment: Any, shrunk: float, cautious: float) -> Effect:
        return Effect(action, segment, 9, 9, 1, 1, shrunk, None, None, shrunk, cautious)

    effects = [
        effect("discount", None, -0.03, 0.01),
        effect("discount", "steady", -0.04, -0.01),
        effect("email", "steady", -0.02, 0.005),
    ]
    found = effect_table(effects, Scenario(100, discount_pct=0.1), campaign_discount=0.2)
    assert found["discount", "steady"] == pytest.approx(-0.02)  # half the campaign's discount
    assert found["email", "steady"] == pytest.approx(-0.02)
    assert found["email", "dormant"] == 0.0  # no estimate: no effect
    cautious = effect_table(effects, Scenario(100, cautious=True), campaign_discount=0.2)
    assert cautious["email", "steady"] == pytest.approx(0.005)
    assumed = effect_table(effects, Scenario(100, assumed={"email": -0.01}), 0.2)
    assert assumed["email", "dormant"] == -0.01
    assert assumed["discount", "steady"] == 0.0


def random_problem(rng: np.random.Generator) -> tuple[pl.DataFrame, EffectTable, Scenario]:
    n = int(rng.integers(1, 7))
    group = members(
        *(
            {
                "user_id": f"u{i}",
                "probability": float(rng.uniform(0.02, 0.6)),
                "segment": str(rng.choice(SEGMENTS)),
                "email_opt_in": bool(rng.random() < 0.7),
                "discounted": bool(rng.random() < 0.2),
                "monthly_value": float(rng.uniform(50, 200)),
                "period_price": float(rng.uniform(50, 200) * rng.choice([1, 12])),
            }
            for i in range(n)
        )
    )
    effects = {(a, s): float(rng.uniform(-0.15, 0.08)) for a in ACTIONS for s in SEGMENTS}
    limit = lambda: None if rng.random() < 0.5 else int(rng.integers(0, 4))  # noqa: E731
    scenario = Scenario(
        budget=float(rng.uniform(0, 300)),
        horizon_months=int(rng.integers(1, 25)),
        discount_pct=float(rng.uniform(0.1, 0.5)),
        email_cost=float(rng.uniform(0, 10)),
        max_emails=limit(),
        max_discounts=limit(),
    )
    return group, effects, scenario


def total(frame: pl.DataFrame, column: str) -> float:
    return frame.select(pl.col(column).sum()).item()


def brute_force(choices: pl.DataFrame, scenario: Scenario) -> float:
    """The best total gain over every way to give each member at most one action."""
    per_member = [list(rows.iter_rows(named=True)) for _, rows in choices.group_by("user_id")]
    best = 0.0
    for combo in itertools.product(*[[None, *rows] for rows in per_member]):
        taken = [row for row in combo if row is not None]
        counts = {a: sum(row["action"] == a for row in taken) for a in ACTIONS}
        if sum(row["spend"] for row in taken) > scenario.budget + 1e-9:
            continue
        if scenario.max_emails is not None and counts["email"] > scenario.max_emails:
            continue
        if scenario.max_discounts is not None and counts["discount"] > scenario.max_discounts:
            continue
        best = max(best, sum(row["gain"] for row in taken))
    return best


def test_milp_equals_brute_force_on_small_problems() -> None:
    """Done criteria of M4b: the MILP finds the optimum, within its 0.01% gap (200 problems)."""
    rng = np.random.default_rng(7)
    for _ in range(200):
        group, effects, scenario = random_problem(rng)
        choices = options(group, effects, scenario)
        best = choices.filter(
            pl.Series(solve(choices, scenario, scenario.budget), dtype=pl.Boolean)
        )
        baseline = choices.filter(
            pl.Series(greedy(choices, scenario, scenario.budget), dtype=pl.Boolean)
        )
        assert total(best, "gain") == pytest.approx(brute_force(choices, scenario), rel=MIP_GAP)
        assert total(baseline, "gain") <= total(best, "gain") + 1e-9
        assert total(best, "spend") <= scenario.budget + 1e-6


def test_value_grows_with_the_budget() -> None:
    rng = np.random.default_rng(3)
    group, effects, scenario = random_problem(rng)
    values = [value for _, value in curve(group, effects, scenario)]
    assert values == sorted(values)
    assert values[0] <= values[-1]


def test_a_plan_for_two_thousand_members_is_quick() -> None:
    """The what-if preview must answer within a second for 2k members at risk."""
    rng = np.random.default_rng(1)
    n = 2000
    group = members(
        *(
            {
                "user_id": f"u{i:05d}",
                "probability": float(p),
                "segment": str(rng.choice(SEGMENTS)),
                "email_opt_in": bool(rng.random() < 0.7),
                "discounted": bool(rng.random() < 0.05),
                "monthly_value": float(rng.choice([79, 107.5, 149])),
                "period_price": float(rng.choice([79, 149, 1290])),
            }
            for i, p in enumerate(rng.beta(1.2, 12, n))
        )
    )
    effects: EffectTable = {**table(email=-0.02, discount=-0.04), ("email", "dormant"): 0.02}
    started = time.perf_counter()
    result = plan(group, effects, Scenario(budget=5000, max_emails=500))
    elapsed = time.perf_counter() - started
    assert result.spend <= 5000 + 1e-6
    assert result.value >= result.greedy_value - 1e-6
    assert (result.chosen["action"] == "email").sum() <= 500
    assert elapsed < 1.0, elapsed
