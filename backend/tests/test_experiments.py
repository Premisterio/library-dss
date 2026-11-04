"""The experiment harness: true gains by hand, the baselines' order and budget, the oracles
against brute force, the DSS with the truth in place of its estimates, the content policies, the
tables' number style, Wilcoxon test and gap decomposition, the figures, and a small grid end to
end, serial and in parallel (DESIGN.md §6)."""

import itertools
import json
import pickle
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import openpyxl
import polars as pl
import pytest
from typer.testing import CliRunner

from app.domain.content import ahp
from app.domain.optimize import MIP_GAP
from app.domain.retention.effects import ACTIONS, SEGMENTS, Effect
from app.ingest import IngestError
from experiments import content, figures, grid, retention, tables
from experiments.__main__ import app
from experiments.config import (
    CAMPAIGN_MONTHS,
    CampaignConfig,
    Config,
    ContentConfig,
    RetentionConfig,
    load,
)
from experiments.retention import (
    POLICIES,
    RiskGroup,
    decide,
    discount_for_all,
    judge,
    true_options,
)

PEOPLE_SCHEMA = {
    "user_id": pl.String,
    "probability": pl.Float64,
    "segment": pl.String,
    "email_opt_in": pl.Boolean,
    "discounted": pl.Boolean,
    "monthly_value": pl.Float64,
    "period_price": pl.Float64,
    "inactive_14d": pl.Boolean,
    "days_since_last_session": pl.Float64,
    "true_none": pl.Float64,
    "true_email": pl.Float64,
    "true_discount": pl.Float64,
    "churned": pl.Boolean,
}
RETENTION = RetentionConfig(
    budget_shares=(0.1, 0.4),
    horizon_months=12,
    email_cost=2.0,
    assumed={"email": -0.02, "discount": -0.05},
)
CONTENT = ContentConfig(budget_shares=(0.1, 0.4), max_per_genre=5)
SMALL_GRID = Config(
    seeds=2,
    presets=("demo",),
    members=800,
    months=10,
    horizon_days=180,
    retention=RETENTION,
    content=CONTENT,
    campaign=CampaignConfig(preset="demo", months=(2, CAMPAIGN_MONTHS), budget_share=0.1),
)
TITLE_SCHEMA = {
    "candidate_id": pl.String,
    "genre": pl.String,
    "license_cost": pl.Float64,
    "demand_searches": pl.Int64,
    "author_loans": pl.Int64,
    "genre_loans": pl.Int64,
    "genre_holds_per_copy": pl.Float64,
    "demand": pl.Int64,
}


def group(*rows: dict[str, Any]) -> RiskGroup:
    defaults = {
        "probability": 0.1,
        "segment": "steady",
        "email_opt_in": True,
        "discounted": False,
        "monthly_value": 100.0,
        "period_price": 100.0,
        "inactive_14d": False,
        "days_since_last_session": 1.0,
        "true_none": 0.1,
        "true_email": 0.1,
        "true_discount": 0.1,
        "churned": False,
    }
    people = pl.DataFrame([{**defaults, **row} for row in rows], schema=PEOPLE_SCHEMA)
    return RiskGroup(people=people, effects=[], true_effects={}, discount_pct=0.2, seed=1)


def random_group(seed: int) -> RiskGroup:
    """30 random members whose predicted risk is not their true one, and a campaign that found
    −2 percentage points for e-mail and −8 for the discount."""
    rng = np.random.default_rng(seed)
    at_risk = group(
        *(
            {
                "user_id": f"u{i}",
                "probability": float(rng.uniform(0.02, 0.5)),
                "email_opt_in": bool(rng.random() < 0.7),
                "discounted": bool(rng.random() < 0.15),
                "period_price": float(rng.choice([79.0, 149.0, 1290.0])),
                "true_none": float(rng.uniform(0.02, 0.5)),
            }
            for i in range(30)
        )
    )
    return replace(at_risk, effects=campaign(email=-0.02, discount=-0.08))


def exact_model(at_risk: RiskGroup) -> RiskGroup:
    """The group as a churn model that predicts the true risk would score it."""
    return replace(at_risk, people=at_risk.people.with_columns(probability=pl.col("true_none")))


def campaign(email: float, discount: float) -> list[Effect]:
    """Each action's campaign effect on everyone and in every segment, against a control churn
    rate of 30%."""
    effects = []
    for action, value in zip(ACTIONS, (email, discount), strict=True):
        churned = round(100 * (0.3 + value))
        for segment in (None, *SEGMENTS):
            effects.append(
                Effect(action, segment, 100, 100, churned, 30, value, None, None, value, value)
            )
    return effects


def chosen(*pairs: tuple[str, str]) -> pl.DataFrame:
    return pl.DataFrame(pairs, schema={"user_id": pl.String, "action": pl.String}, orient="row")


def test_true_gain_by_hand() -> None:
    two = group(
        {"user_id": "a", "true_none": 0.10, "true_email": 0.08, "true_discount": 0.05},
        {
            "user_id": "b",
            "email_opt_in": False,
            "period_price": 1200.0,
            "true_none": 0.20,
            "true_email": 0.20,
            "true_discount": 0.10,
        },
    )
    truth = true_options(two, RETENTION)
    # a: e-mail 0.02·100·12 − 2 = 22; discount 0.05·1200 − 0.95·0.2·100 = 41. b: no e-mail
    # without consent; discount 0.1·1200 − 0.9·0.2·1200 = −96.
    assert truth.sort("user_id", "action").select("user_id", "action", "gain").rows() == [
        ("a", "discount", pytest.approx(41.0)),
        ("a", "email", pytest.approx(22.0)),
        ("b", "discount", pytest.approx(-96.0)),
    ]
    result = judge(chosen(("a", "email"), ("b", "discount")), truth)
    assert result == {
        "value": pytest.approx(-74.0),
        "spend": pytest.approx(218.0),
        "emails": 1,
        "discounts": 1,
        "precision": 0.5,
        "kept": pytest.approx(0.12),
    }
    assert judge(chosen(), truth)["precision"] is None
    with pytest.raises(ValueError, match="cannot get"):
        judge(chosen(("b", "email")), truth)


def test_budget_is_a_share_of_a_discount_for_everyone_who_can_get_one() -> None:
    people = group(
        {"user_id": "a", "period_price": 100.0},
        {"user_id": "b", "period_price": 1200.0},
        {"user_id": "c", "discounted": True},
        {"user_id": "d", "period_price": None},
    )
    assert discount_for_all(people) == pytest.approx(0.2 * 1300)


def test_discounts_by_risk_in_order_until_the_budget_runs_out() -> None:
    people = group(
        {"user_id": "skipped-discounted", "probability": 0.9, "discounted": True},
        {"user_id": "skipped-no-price", "probability": 0.8, "period_price": None},
        {"user_id": "first", "probability": 0.5},  # expected spend 0.5·0.2·100 = 10
        {"user_id": "second", "probability": 0.3},  # 14, 24 in all
        {"user_id": "third", "probability": 0.1},  # 18 more would exceed 25
    )
    taken = decide(people, "risk", 25.0, RETENTION, true_options(people, RETENTION))
    assert taken.rows() == [("first", "discount"), ("second", "discount")]


def test_the_inactivity_rule_discounts_inactive_members_longest_idle_first() -> None:
    people = group(
        {"user_id": "active", "probability": 0.9},
        {"user_id": "idle-20", "inactive_14d": True, "days_since_last_session": 20.0},
        {"user_id": "idle-40", "inactive_14d": True, "days_since_last_session": 40.0},
        {"user_id": "never-read", "inactive_14d": True, "days_since_last_session": None},
    )
    taken = decide(people, "inactive", 1000.0, RETENTION, true_options(people, RETENTION))
    assert taken["user_id"].to_list() == ["never-read", "idle-40", "idle-20"]


def test_random_discounts_fit_the_budget_and_repeat_with_the_seed() -> None:
    people = group(*({"user_id": f"u{i}", "probability": 0.5} for i in range(20)))
    truth = true_options(people, RETENTION)
    first = decide(people, "random", 50.0, RETENTION, truth)
    assert first.height == 5  # 10 UAH each
    assert first.equals(decide(people, "random", 50.0, RETENTION, truth))


def test_the_oracle_takes_the_best_true_choice() -> None:
    one = group({"user_id": "a", "true_none": 0.10, "true_email": 0.08, "true_discount": 0.05})
    truth = true_options(one, RETENTION)  # e-mail gains 22 for 2 UAH, a discount 41 for 19
    assert decide(one, "oracle", 25.0, RETENTION, truth).rows() == [("a", "discount")]
    assert decide(one, "oracle", 10.0, RETENTION, truth).rows() == [("a", "email")]


def test_the_oracle_equals_brute_force_on_small_problems() -> None:
    rng = np.random.default_rng(7)
    for _ in range(40):
        people = group(
            *(
                {
                    "user_id": f"u{i}",
                    "email_opt_in": bool(rng.random() < 0.7),
                    "discounted": bool(rng.random() < 0.15),
                    "period_price": float(rng.choice([79.0, 149.0, 1290.0])),
                    "true_none": (p := float(rng.uniform(0.02, 0.4))),
                    "true_email": float(np.clip(p + rng.normal(0, 0.03), 0, 1)),
                    "true_discount": float(np.clip(p + rng.normal(-0.05, 0.05), 0, 1)),
                }
                for i in range(5)
            )
        )
        truth = true_options(people, RETENTION)
        budget = float(rng.uniform(0, 300))
        options = {
            user: [(0.0, 0.0)] + [(g, s) for _, g, s in rows]
            for user, rows in itertools.groupby(
                truth.sort("user_id").select("user_id", "gain", "spend").rows(),
                key=lambda row: row[0],
            )
        }
        best = max(
            sum(g for g, _ in combo)
            for combo in itertools.product(*options.values())
            if sum(s for _, s in combo) <= budget
        )
        value = judge(decide(people, "oracle", budget, RETENTION, truth), truth)["value"]
        assert value == pytest.approx(best, rel=MIP_GAP, abs=1e-6)


def test_with_the_true_risk_the_dss_plans_on_libsim_s_probabilities() -> None:
    # The model takes b for the riskier member, the truth a. A discount's expected spend is
    # about 10 UAH at a risk of 0.6 and 19 at 0.05, so 15 UAH buy only the riskier one's.
    two = replace(
        group(
            {"user_id": "a", "email_opt_in": False, "probability": 0.05, "true_none": 0.6},
            {"user_id": "b", "email_opt_in": False, "probability": 0.6, "true_none": 0.05},
        ),
        effects=campaign(email=-0.02, discount=-0.08),
    )
    truth = true_options(two, RETENTION)
    assert decide(two, "dss", 15.0, RETENTION, truth).rows() == [("b", "discount")]
    assert decide(two, "dss_true_risk", 15.0, RETENTION, truth).rows() == [("a", "discount")]
    # a model as good as the truth: the same plan
    exact = exact_model(random_group(seed=4))
    truth = true_options(exact, RETENTION)
    budget = 0.2 * discount_for_all(exact)
    dss = decide(exact, "dss", budget, RETENTION, truth)
    assert dss.height > 0
    assert decide(exact, "dss_true_risk", budget, RETENTION, truth).equals(dss)


def test_with_the_true_effects_the_dss_plans_as_on_a_campaign_that_found_them() -> None:
    at_risk = replace(random_group(seed=5), true_effects={"email": -0.01, "discount": -0.04})
    found = replace(at_risk, effects=campaign(email=-0.01, discount=-0.04))
    truth = true_options(at_risk, RETENTION)
    budget = 0.2 * discount_for_all(at_risk)
    on_found = decide(found, "dss", budget, RETENTION, truth)
    assert on_found.height > 0
    assert not on_found.equals(decide(at_risk, "dss", budget, RETENTION, truth))
    # the truth takes the estimate's place at the same control rate, not at the members' risk
    assert decide(at_risk, "dss_true_effects", budget, RETENTION, truth).equals(on_found)
    # both: the true average effects on the true probabilities
    both = decide(at_risk, "dss_true_both", budget, RETENTION, truth)
    assert both.equals(decide(exact_model(found), "dss", budget, RETENTION, truth))
    # an action without a true effect (nobody it compares took part) has none
    no_email = replace(at_risk, true_effects={"discount": -0.04})
    without = replace(at_risk, effects=campaign(email=0.0, discount=-0.04))
    assert decide(no_email, "dss_true_effects", budget, RETENTION, truth).equals(
        decide(without, "dss", budget, RETENTION, truth)
    )


def test_the_true_average_effects_are_over_the_participants_each_action_compares() -> None:
    participants = pl.DataFrame(
        {
            "user_id": ["a", "b", "c"],
            "arm": ["email", "control", "discount"],
            "email_opt_in": [True, True, False],
        }
    )
    truth = {
        "campaign": [
            {"user_id": "a", "p_true": {"none": 0.30, "email": 0.28, "discount": 0.20}},
            {"user_id": "b", "p_true": {"none": 0.20, "email": 0.16, "discount": 0.10}},
            {"user_id": "c", "p_true": {"none": 0.40, "email": 0.40, "discount": 0.34}},
        ]
    }
    # e-mail among a and b, who agreed to e-mails; the discount among all three
    assert retention.true_effects(participants, truth) == {
        "email": pytest.approx((-0.02 - 0.04) / 2),
        "discount": pytest.approx((-0.10 - 0.10 - 0.06) / 3),
    }
    nobody_agreed = participants.with_columns(email_opt_in=pl.lit(False))
    assert set(retention.true_effects(nobody_agreed, truth)) == {"discount"}


def offer(*rows: dict[str, Any]) -> pl.DataFrame:
    defaults = {
        "genre": "fantasy",
        "license_cost": 100.0,
        "demand_searches": 0,
        "author_loans": 0,
        "genre_loans": 0,
        "genre_holds_per_copy": 0.0,
        "demand": 0,
    }
    return pl.DataFrame([{**defaults, **row} for row in rows], schema=TITLE_SCHEMA)


def licensed(titles: pl.DataFrame, policy: str, budget: float) -> set[str]:
    chosen = content.choose_titles(titles, policy, budget, CONTENT)
    return set(titles.filter(pl.Series(chosen))["candidate_id"].to_list())


def test_content_baselines_take_titles_in_their_order_while_they_fit() -> None:
    four = offer(
        {"candidate_id": "c1", "license_cost": 100.0, "demand_searches": 5, "genre_loans": 10},
        {
            "candidate_id": "c2",
            "genre": "history",
            "license_cost": 300.0,
            "demand_searches": 9,
            "genre_loans": 50,
        },
        {"candidate_id": "c3", "genre": "history", "license_cost": 50.0, "genre_loans": 50},
        {"candidate_id": "c4", "license_cost": 200.0, "demand_searches": 2, "genre_loans": 10},
    )
    # cheapest: 50 + 100 + 200; the 300 no longer fits 350
    assert licensed(four, "cheapest", 350.0) == {"c3", "c1", "c4"}
    # most searched: 300, then only the 50 still fits
    assert licensed(four, "most_searched", 350.0) == {"c2", "c3"}
    # searches per hryvnia: 0.05 (100), 0.03 (300 no longer fits), 0.01 (200), 0 (50)
    assert licensed(four, "searches_per_uah", 350.0) == {"c1", "c4", "c3"}
    # the genre with the most loans first, its most searched title first
    assert licensed(four, "top_genre", 350.0) == {"c2", "c3"}


def test_the_content_oracle_equals_brute_force_on_small_offers() -> None:
    rng = np.random.default_rng(3)
    for _ in range(30):
        titles = offer(
            *(
                {
                    "candidate_id": f"c{i}",
                    "license_cost": float(rng.integers(50, 400)),
                    "demand": int(rng.integers(0, 40)),
                }
                for i in range(8)
            )
        )
        cost, demand = titles["license_cost"].to_numpy(), titles["demand"].to_numpy()
        budget = float(rng.uniform(100, 1500))
        best = max(
            demand[list(subset)].sum()
            for size in range(len(cost) + 1)
            for subset in itertools.combinations(range(len(cost)), size)
            if cost[list(subset)].sum() <= budget
        )
        chosen = content.choose_titles(titles, "oracle", budget, CONTENT)
        assert demand[chosen].sum() == pytest.approx(best, rel=MIP_GAP)


def test_the_dss_portfolio_keeps_the_cap_per_genre() -> None:
    titles = offer(
        *({"candidate_id": f"a{i}", "demand_searches": 10 + i} for i in range(4)),
        {"candidate_id": "b", "genre": "history", "demand_searches": 2},
        {"candidate_id": "z", "genre": "poetry"},  # the worst title: a TOPSIS score of 0
    )
    two = ContentConfig(budget_shares=(0.1,), max_per_genre=2)
    chosen = content.choose_titles(titles, "dss", 10_000.0, two)
    assert set(titles.filter(pl.Series(chosen))["candidate_id"].to_list()) == {"a3", "a2", "b"}


def test_searches_first_gives_the_searches_half_the_weight() -> None:
    weights = ahp.weigh(ahp.comparisons(len(content.KEYS), content.SEARCHES_FIRST))
    assert content.KEYS[0] == "demand_searches"
    assert weights.weights == pytest.approx([0.5, 1 / 6, 1 / 6, 1 / 6])
    assert weights.cr == pytest.approx(0.0, abs=1e-9)


def test_random_titles_are_judged_by_their_mean_over_many_orders() -> None:
    titles = offer(*({"candidate_id": f"c{i}", "demand": i} for i in range(10)))

    def random_rows() -> list[dict[str, Any]]:
        rows = content.evaluate_policies(titles, CONTENT, seed=1)
        return [row for row in rows if row["policy"] == "random"]

    first = random_rows()
    assert [row["titles"] for row in first] == [1.0, 4.0]  # 10% and 40% of 1,000 UAH
    assert 0 < first[0]["demand"] < 9  # a mean over orders, not one draw's titles
    assert first == random_rows()


def test_numbers_in_ukrainian_style() -> None:
    assert tables.number(19872.4) == "19 872"
    assert tables.number(-1234.56, 1) == "−1 234,6"
    assert tables.number(-0.3) == "0"
    # mean 2, sd 1, t(0.975, 2) = 4.303: half-width 4.303/√3 = 2.48
    assert tables.summary(np.array([1.0, 2.0, 3.0]), 1) == "2,0 ± 2,5"
    assert tables.summary(np.array([0.25])) == "0"
    assert tables.summary(np.array([])) == "—"


def test_a_failing_library_is_named_in_an_error_a_worker_can_send_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: an IngestError raised in a worker process could not be unpickled, which broke
    the whole pool and hid which library failed (high-scarcity, seed 9)."""
    problem = "reading_sessions.started_at: 1 values after as_of 2026-09-30"

    def invalid(*_: object, **__: object) -> None:
        raise IngestError("dataset.invalid", "The dataset has 1 problem(s)", [problem])

    monkeypatch.setattr(grid.engine, "simulate", invalid)
    with pytest.raises(RuntimeError) as caught:
        grid.library("high-scarcity", 9, CAMPAIGN_MONTHS, SMALL_GRID)
    sent = pickle.loads(pickle.dumps(caught.value))  # noqa: S301 - what a worker sends back
    assert str(sent).startswith("high-scarcity seed 9: IngestError: The dataset has 1 problem(s)")
    assert problem in str(sent)


def test_the_wilcoxon_table_compares_the_dss_with_the_best_baseline() -> None:
    def row(seed: int, share: float, policy: str, value: float) -> dict[str, Any]:
        return {
            "preset": "demo",
            "seed": seed,
            "budget_share": share,
            "policy": policy,
            "value": value,
        }

    frame = pl.DataFrame(
        [
            line
            for seed in range(1, 7)
            for line in (
                row(seed, 0.1, "dss", 100.0 + seed),
                row(seed, 0.1, "random", 10.0),
                row(seed, 0.1, "inactive", 50.0),
                row(seed, 0.1, "risk", 40.0),
                row(seed, 0.4, "dss", 70.0),
                row(seed, 0.4, "random", 10.0),
                row(seed, 0.4, "inactive", 70.0),
                row(seed, 0.4, "risk", 0.0),
            )
        ]
    )
    header, rows = tables.wilcoxon_table(
        frame, "value", tables.RETENTION_LABELS, retention.BASELINES, "грн"
    )
    assert header[-1] == "p, тест Вілкоксона (n = 6)"
    # differences 51…56: mean 53.5, half-width 2.571·1.871/√6 = 1.96; all six positive, so the
    # exact two-sided p = 2 / 2⁶
    assert rows == [
        ["Базовий", "10 %", "Знижки неактивним 14+ днів", "54 ± 2", "0,031"],
        ["", "40 %", "Знижки неактивним 14+ днів", "0 ± 0", "—"],
    ]


def test_the_gap_table_puts_the_dss_next_to_its_plans_with_the_truth() -> None:
    def row(seed: int, policy: str, value: float) -> dict[str, Any]:
        return {
            "preset": "demo",
            "seed": seed,
            "campaign_months": CAMPAIGN_MONTHS,
            "budget_share": 0.1,
            "policy": policy,
            "value": value,
        }

    shares = {  # % of the oracle's 200 UAH in seeds 1, 2 and 3
        "dss": (40, 50, 60),
        "dss_true_risk": (55, 60, 65),
        "dss_true_effects": (60, 60, 60),
        "dss_true_both": (70, 75, 80),
        "dss_assumed": (90, 90, 90),  # not in this table
    }
    frame = pl.DataFrame(
        [row(seed, "oracle", 200.0) for seed in (1, 2, 3)]
        + [
            row(seed, policy, 2.0 * share)
            for policy, values in shares.items()
            for seed, share in zip((1, 2, 3), values, strict=True)
        ]
    )
    header, rows = tables.gap_table(frame)
    assert header == [
        "Сценарій",
        "Бюджет",
        "СППР, % від оракула",
        "З істинним ризиком, % від оракула",
        "З істинними середніми ефектами, % від оракула",
        "З обома, % від оракула",
    ]
    # half-widths t(0.975, 2) · sd / √3: 4.303 · 10 / √3 = 25 and 4.303 · 5 / √3 = 12
    assert rows == [["Базовий", "10 %", "50 ± 25", "60 ± 12", "60 ± 0", "75 ± 12"]]


def test_the_committed_grid_loads() -> None:
    config = load()
    assert config.seeds == 20
    assert config.members == 5000
    assert config.horizon_days == 180
    assert set(config.retention.assumed) == {"email", "discount"}
    assert config.content.max_per_genre == 5
    assert CAMPAIGN_MONTHS in config.campaign.months


def test_the_campaign_lengths_add_libraries_after_the_grid() -> None:
    assert SMALL_GRID.cases() == [("demo", 1, 4), ("demo", 2, 4), ("demo", 1, 2), ("demo", 2, 2)]


@pytest.fixture(scope="module")
def results(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("results")
    grid.run(SMALL_GRID, out, workers=1, echo=lambda _: None)
    return out


def test_a_small_grid_writes_every_policy_and_budget(results: Path) -> None:
    retention = pl.read_csv(results / "retention.csv")
    assert retention.height == 2 * 2 * 2 * len(POLICIES)  # campaigns × seeds × budgets × policies
    assert retention["policy"].unique(maintain_order=True).to_list() == list(POLICIES)
    oracle = retention.filter(pl.col("policy") == "oracle")
    assert (oracle["spend"] <= oracle["budget"] + 1e-6).all()
    assert (oracle["precision"] == 1.0).all()
    # Policies count the spend with their own probabilities, so only a choice whose true spend
    # fits the budget is one the oracle could make; none of those gains more.
    library = ["preset", "seed", "campaign_months", "budget_share"]
    fits = retention.filter(pl.col("spend") <= pl.col("budget") + 1e-6).join(
        oracle.select(*library, best="value"), on=library
    )
    assert fits.height > 0
    assert (fits["value"] * (1 - MIP_GAP) <= fits["best"] + 1e-6).all()
    models = pl.read_csv(results / "models.csv")
    assert models.select("seed", "campaign_months").rows() == [
        (seed, months) for _, seed, months in SMALL_GRID.cases()
    ]
    # the risk group is libsim's next renewals, though the truth runs 180 days past as_of
    assert (models["unmatched"] == 0).all()
    assert ((models["roc_auc_best"] > 0.5) & (models["roc_auc_best"] <= 1)).all()
    assert models["discount_covered"].dtype == pl.Boolean
    assert json.loads((results / "config.json").read_text())["presets"] == ["demo"]


def test_a_small_grid_judges_every_content_policy_within_its_budget(results: Path) -> None:
    offers = pl.read_csv(results / "content.csv")
    assert offers.height == 2 * 2 * len(content.POLICIES)
    assert offers["policy"].unique(maintain_order=True).to_list() == list(content.POLICIES)
    assert (offers["spend"] <= offers["budget"] + 1e-6).all()
    best = offers.group_by("seed", "budget_share").agg(best=pl.col("demand").max())
    oracle = offers.filter(pl.col("policy") == "oracle").join(best, on=["seed", "budget_share"])
    assert (oracle["demand"] >= oracle["best"] * (1 - MIP_GAP)).all()


def test_the_report_goes_to_a_workbook_figures_and_the_terminal(results: Path) -> None:
    outcome = CliRunner().invoke(app, ["report", "--out", str(results)])
    assert outcome.exit_code == 0, outcome.output
    assert "Оракул" in outcome.output
    for name in [*figures.FIGURES, "campaign.png"]:
        png = (results / figures.FOLDER / name).read_bytes()
        assert png.startswith(b"\x89PNG\r\n\x1a\n")
        assert str(results / figures.FOLDER / name) in outcome.output
    first = {path: path.read_bytes() for path in figures.write(results)}
    assert first == {path: path.read_bytes() for path in figures.write(results)}
    workbook = openpyxl.load_workbook(results / tables.WORKBOOK)
    assert workbook.sheetnames == [
        "Утримання, виграш, грн",
        "Утримання, частка оракула, %",
        "Утримання, точність дій, %",
        "Утримання, тест Вілкоксона",
        "Утримання, джерела відставання",
        "Закупівля, обслужений попит",
        "Закупівля, частка оракула, %",
        "Закупівля, тест Вілкоксона",
        "Модель і ефекти",
        "Розмір кампанії",
    ]
    sheet = workbook["Утримання, частка оракула, %"]
    assert sheet.max_row == 1 + len(tables.RETENTION_LABELS)  # the decomposition is not here
    assert sheet.cell(row=9, column=2).value == "Оракул"
    assert sheet.cell(row=9, column=3).value == "100 ± 0"
    gap = [[cell.value for cell in row] for row in workbook["Утримання, джерела відставання"]]
    assert [line[:2] for line in gap] == [
        ["Сценарій", "Бюджет"],
        ["Базовий", "10 %"],
        [None, "40 %"],
    ]
    assert gap[0][2:] == [f"{label}, % від оракула" for label in tables.GAP_LABELS.values()]
    shares = [cell for line in gap[1:] for cell in line[2:]]
    assert all(isinstance(cell, str) and re.fullmatch(r"−?\d+ ± \d+", cell) for cell in shares)


def test_a_longer_campaign_has_more_participants_and_narrower_intervals(results: Path) -> None:
    header, rows = tables.campaign_table(
        pl.read_csv(results / "retention.csv"), pl.read_csv(results / "models.csv"), "demo", 0.1
    )
    assert header[0] == "Кампанія, місяців"
    assert [row[0] for row in rows] == ["2", "4"]
    models = pl.read_csv(results / "models.csv")
    by_length = models.group_by("campaign_months").agg(
        pl.col("participants").mean(), (pl.col("discount_high") - pl.col("discount_low")).mean()
    )
    short, usual = by_length.sort("campaign_months").rows()
    assert short[1] < usual[1]  # more members took part
    assert short[2] > usual[2]  # and the discount's interval is narrower


def test_a_parallel_run_gives_the_same_results(results: Path, tmp_path: Path) -> None:
    grid.run(SMALL_GRID, tmp_path, workers=2, echo=lambda _: None)
    for name in ("retention.csv", "models.csv", "content.csv"):
        assert (tmp_path / name).read_text() == (results / name).read_text()
