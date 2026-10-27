"""The retention plan: gains by hand, the MILP against brute force on small problems, the effect
table and the speed on a realistic risk group (DESIGN.md §2.9)."""

import itertools
import math
import time
from typing import Any

import numpy as np
import polars as pl
import pytest

from app.domain.optimize import MIP_GAP
from app.domain.retention.effects import ACTIONS, SEGMENTS, Effect
from app.domain.retention.plan import (
    EffectTable,
    Scenario,
    capped,
    curve,
    effect_table,
    greedy,
    members,
    options,
    plan,
    shift,
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


def group(*rows: dict[str, Any]) -> pl.DataFrame:
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


def total(frame: pl.DataFrame, column: str) -> float:
    return frame.select(pl.col(column).sum()).item()


ONE = group({"user_id": "u1", "probability": 0.3})
# shifts that take a churn probability of 0.3 to exactly 0.25 and 0.2
EFFECTS = table(email=shift(0.3, -0.05), discount=shift(0.3, -0.1))


def scenario(budget: float, **overrides: Any) -> Scenario:
    return Scenario(budget=budget, discount_pct=0.2, **overrides)


def test_gains_by_hand() -> None:
    found = options(ONE, EFFECTS, scenario(100))
    assert found.select("action", "p_action", "gain", "spend").rows() == [
        # 0.1 · 100 UAH · 12 months kept, minus 20% of the renewal if the member renews (0.8)
        ("discount", pytest.approx(0.2), pytest.approx(120 - 16), pytest.approx(16)),
        # 0.05 · 1200 kept, minus the e-mail
        ("email", pytest.approx(0.25), pytest.approx(60 - 2), 2.0),
    ]


def test_an_effect_moves_a_risky_member_more() -> None:
    """The same logit shift lowers a higher probability by more."""
    two = group({"user_id": "low", "probability": 0.05}, {"user_id": "high", "probability": 0.5})
    found = options(two, EFFECTS, scenario(100)).filter(pl.col("action") == "email")
    drop = dict(found.select("user_id", pl.col("p_none") - pl.col("p_action")).iter_rows())
    assert drop["high"] > drop["low"] > 0


def test_the_best_action_within_the_budget() -> None:
    assert plan(ONE, EFFECTS, scenario(100)).chosen["action"].to_list() == ["discount"]
    assert plan(ONE, EFFECTS, scenario(10)).chosen["action"].to_list() == ["email"]
    limited = scenario(100, max_discounts=0)
    assert plan(ONE, EFFECTS, limited).chosen["action"].to_list() == ["email"]
    assert plan(ONE, EFFECTS, scenario(1)).chosen.is_empty()


def test_who_can_get_what() -> None:
    three = group(
        {"user_id": "no_consent", "probability": 0.3, "email_opt_in": False},
        {"user_id": "discounted", "probability": 0.3, "discounted": True},
        {"user_id": "no_price", "probability": 0.3, "period_price": None},
    )
    found = {(r[0], r[1]) for r in options(three, EFFECTS, scenario(1)).iter_rows()}
    assert found == {("no_consent", "discount"), ("discounted", "email"), ("no_price", "email")}


def test_harmful_actions_are_never_taken() -> None:
    """An e-mail that makes a dormant member more likely to leave gains nothing."""
    effects: EffectTable = {**EFFECTS, ("email", "dormant"): 0.3}
    dormant = group({"user_id": "u1", "probability": 0.3, "segment": "dormant"})
    assert options(dormant, effects, scenario(100))["action"].to_list() == ["discount"]


def test_members_from_scores() -> None:
    """A kept member is worth the list price per month: the renewal's over the plan's months,
    or, without it, what they pay undone by their discount."""
    scored = pl.DataFrame(
        {
            "user_id": ["u1", "u2", "u3"],
            "probability": [0.2, 0.1, 0.3],
            "plan": ["annual", "monthly", "monthly"],
            "period_price": [1290.0, None, 149.0],
            "days_since_last_session": [40.0, 1.0, 2.0],
            "sessions_trend": [0.0, 0.5, -0.5],
            "email_opt_in": [True, None, True],
            "discount": [0.2, 0.0, 1.0],
            "monthly_price": [86.0, 149.0, 0.0],
        }
    )
    assert members(scored).rows() == [
        ("u1", 0.2, "dormant", True, True, pytest.approx(107.5), 1290.0),
        ("u2", 0.1, "steady", None, False, 149.0, None),
        # Regression: a free running period made the member worth nothing to keep.
        ("u3", 0.3, "declining", True, True, 149.0, 149.0),
    ]


def test_effect_table() -> None:
    def effect(
        action: Any, segment: Any, shrunk: float, cautious: float, control: int = 10
    ) -> Effect:
        return Effect(action, segment, 100, 100, 5, control, shrunk, None, None, shrunk, cautious)

    effects = [
        effect("discount", None, -0.03, 0.01),
        effect("discount", "steady", -0.04, -0.01),
        effect("discount", "dormant", -0.06, -0.02, control=30),
        effect("email", "steady", -0.02, 0.005),
    ]
    # The arm's overall effect shifts at its control rate, 10 of 100, in every segment.
    overall = effect_table(effects, scenario(100), base_rate=0.5)
    assert overall["discount", "steady"] == pytest.approx(shift(0.1, -0.03))
    assert overall["discount", "dormant"] == pytest.approx(shift(0.1, -0.03))
    assert overall["discount", "declining"] == 0.0  # no segment row: no effect
    assert overall["email", "steady"] == pytest.approx(shift(0.1, -0.02))  # no overall row
    # Regression: a segment's own effect shifted at the arm's rate, not the segment's (30%).
    found = effect_table(effects, scenario(100, by_segment=True), base_rate=0.5)
    assert found["discount", "steady"] == pytest.approx(shift(0.1, -0.04))
    assert found["discount", "dormant"] == pytest.approx(shift(0.3, -0.06))
    assert found["email", "dormant"] == 0.0  # no estimate: no effect
    cautious = effect_table(effects, scenario(100, cautious=True), base_rate=0.5)
    assert cautious["discount", "steady"] == pytest.approx(shift(0.1, 0.01))
    by_segment = effect_table(effects, scenario(100, cautious=True, by_segment=True), 0.5)
    assert by_segment["discount", "steady"] == pytest.approx(shift(0.1, -0.01))
    assumed = effect_table(effects, scenario(100, assumed={"email": -0.01}), base_rate=0.2)
    assert assumed["email", "dormant"] == pytest.approx(shift(0.2, -0.01))
    assert assumed["discount", "steady"] == 0.0


def test_an_action_prevents_at_most_ninety_percent() -> None:
    """Regression: an effect at least as large as the base rate (a treated arm without churns,
    an assumption larger than the risk) clipped the rate to 1e-6, so the action removed churn
    for everyone. It now prevents at most 90% at its base rate, and the plan says so."""
    assert shift(0.148, -0.2) == pytest.approx(shift(0.148, -0.9 * 0.148))
    assert shift(0.148, -0.2) > -3
    assert shift(0.148, -0.1) == pytest.approx(math.log(0.048 / 0.952) - math.log(0.148 / 0.852))
    big = scenario(100, assumed={"email": -0.01, "discount": -0.2})
    assert capped([], big, base_rate=0.1) == ["discount"]
    assert capped([], scenario(100, assumed={"email": -0.01}), base_rate=0.1) == []


def random_problem(rng: np.random.Generator) -> tuple[pl.DataFrame, EffectTable, Scenario]:
    n = int(rng.integers(1, 7))
    people = group(
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
    effects = {(a, s): float(rng.uniform(-1.0, 0.4)) for a in ACTIONS for s in SEGMENTS}
    cap = lambda: None if rng.random() < 0.5 else int(rng.integers(0, 4))  # noqa: E731
    return (
        people,
        effects,
        Scenario(
            budget=float(rng.uniform(0, 300)),
            discount_pct=float(rng.uniform(0.1, 0.5)),
            horizon_months=int(rng.integers(1, 25)),
            email_cost=float(rng.uniform(0, 10)),
            max_emails=cap(),
            max_discounts=cap(),
        ),
    )


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
    """Done criteria of M4b: the MILP finds the optimum, within its 0.5% gap (200 problems)."""
    rng = np.random.default_rng(7)
    for _ in range(200):
        people, effects, chosen_scenario = random_problem(rng)
        choices = options(people, effects, chosen_scenario)
        budget = chosen_scenario.budget
        best = choices.filter(pl.Series(solve(choices, chosen_scenario, budget), dtype=pl.Boolean))
        baseline = choices.filter(
            pl.Series(greedy(choices, chosen_scenario, budget), dtype=pl.Boolean)
        )
        assert total(best, "gain") == pytest.approx(
            brute_force(choices, chosen_scenario), rel=MIP_GAP
        )
        assert total(baseline, "gain") <= total(best, "gain") + 1e-9
        assert total(best, "spend") <= budget + 1e-6


def test_value_grows_with_the_budget() -> None:
    people, effects, chosen_scenario = random_problem(np.random.default_rng(3))
    values = [value for _, value in curve(people, effects, chosen_scenario)]
    assert values == sorted(values)


def test_the_curve_runs_until_more_money_gains_nothing() -> None:
    """Regression: the curve ended at the spend of every member's best action, ignoring the
    per-action limits, so with e-mails capped it stopped long before it levelled off."""
    people = group(*({"user_id": f"u{i}", "probability": 0.3} for i in range(100)))
    limited = scenario(5000, max_emails=0)
    points = curve(people, EFFECTS, limited)
    best = plan(people, EFFECTS, limited)
    assert best.chosen["action"].unique().to_list() == ["discount"]
    assert points[-1][0] == pytest.approx(best.spend, rel=1e-6)
    assert points[-1][1] >= best.value - 1e-6


def test_a_plan_for_two_thousand_members_is_quick() -> None:
    """The what-if preview must answer within a second for 2k members at risk (DESIGN.md)."""
    rng = np.random.default_rng(1)
    people = group(
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
            for i, p in enumerate(rng.beta(1.2, 12, 2000))
        )
    )
    effects: EffectTable = {
        **table(email=shift(0.08, -0.02), discount=shift(0.08, -0.04)),
        ("email", "dormant"): shift(0.08, 0.02),
    }
    started = time.perf_counter()
    result = plan(people, effects, scenario(5000, max_emails=500))
    points = curve(people, effects, scenario(5000, max_emails=500))
    elapsed = time.perf_counter() - started
    assert result.spend <= 5000 + 1e-6
    assert result.value >= result.greedy_value - 1e-6
    assert (result.chosen["action"] == "email").sum() <= 500
    assert len(points) == 9
    assert elapsed < 2.0, elapsed  # about 0.6 s here; the margin keeps slow CI machines green


@pytest.mark.parametrize(("seed", "budget", "max_emails"), [(0, 1000, 200), (2, 1000, None)])
def test_hard_plans_stop_at_the_gap(seed: int, budget: float, max_emails: int | None) -> None:
    """Regression: proving these 2k-member plans optimal to 0.01% took over a minute (seed 0)
    and over six (seed 2); within the 0.5% gap they take about a second."""
    rng = np.random.default_rng(seed)
    n = 2000
    people = pl.DataFrame(
        {
            "user_id": [f"u{i:05d}" for i in range(n)],
            "probability": rng.beta(1.2, 12, n),
            "segment": rng.choice(list(SEGMENTS), n),
            "email_opt_in": rng.random(n) < 0.7,
            "discounted": rng.random(n) < 0.05,
            "monthly_value": rng.choice([79, 107.5, 149], n).astype(float),
            "period_price": rng.choice([79.0, 149.0, 1290.0], n),
        }
    )
    effects = table(email=shift(0.08, -0.02), discount=shift(0.08, -0.04))
    started = time.perf_counter()
    result = plan(people, effects, scenario(budget, max_emails=max_emails))
    assert time.perf_counter() - started < 10
    assert result.value >= result.greedy_value


@pytest.mark.slow
def test_the_plan_beats_a_random_one_on_the_truth(
    demo_simulation: tuple[Any, dict[str, Any], pl.DataFrame], demo_training: Any
) -> None:
    """On libsim's true churn probabilities under each action, the plan gains more than a
    random plan of the same budget (DESIGN.md §2.9 has the full comparison)."""
    from app.domain.churn.scoring import score
    from app.domain.retention.effects import estimate, participants

    parsed, truth, _ = demo_simulation
    scored = score(demo_training, parsed.frames, parsed.as_of, parsed.timezone)
    people = members(
        pl.DataFrame(
            [
                {
                    "user_id": s.user_id,
                    "probability": s.probability,
                    "period_price": s.period_price,
                    **s.features,
                }
                for s in scored
            ],
            infer_schema_length=None,
        )
    )
    effects = estimate(participants(parsed.frames, parsed.timezone))
    chosen = scenario(3000)
    table = effect_table(effects, chosen, base_rate=total(people, "probability") / people.height)
    p_true = {row["user_id"]: row["p_true"] for row in truth["at_risk"]}
    value = dict(people.select("user_id", "monthly_value").iter_rows())
    price = dict(people.select("user_id", "period_price").iter_rows())

    def true_gain(taken: pl.DataFrame) -> float:
        gained = 0.0
        for user, action in taken.select("user_id", "action").iter_rows():
            p0, pa = p_true[user]["none"], p_true[user][action]
            cost = 2.0 if action == "email" else (1 - pa) * chosen.discount_pct * price[user]
            gained += (p0 - pa) * value[user] * chosen.horizon_months - cost
        return gained

    best = plan(people, table, chosen).chosen
    taken, members_taken, spent = [], set(), 0.0
    for row in (
        options(people, table, chosen)
        .sample(fraction=1.0, shuffle=True, seed=0)
        .iter_rows(named=True)
    ):
        if row["user_id"] not in members_taken and spent + row["spend"] <= chosen.budget:
            taken.append(row)
            members_taken.add(row["user_id"])
            spent += row["spend"]
    randomly = pl.DataFrame(taken)
    assert true_gain(best) > max(true_gain(randomly), 0.0)
