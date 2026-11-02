"""The experiment harness: true gains by hand, the baselines' order and budget, the oracle
against brute force, the tables' number style, and a small grid end to end, serial and in
parallel (DESIGN.md §6)."""

import itertools
import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import openpyxl
import polars as pl
import pytest
from typer.testing import CliRunner

from app.domain.optimize import MIP_GAP
from app.ingest import IngestError
from experiments import grid, tables
from experiments.__main__ import app
from experiments.config import Config, RetentionConfig, load
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
SMALL_GRID = Config(seeds=2, presets=("demo",), members=800, months=10, retention=RETENTION)


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
    return RiskGroup(people=people, effects=[], discount_pct=0.2, seed=1)


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
        grid.library("high-scarcity", 9, SMALL_GRID)
    sent = pickle.loads(pickle.dumps(caught.value))  # noqa: S301 - what a worker sends back
    assert str(sent).startswith("high-scarcity seed 9: IngestError: The dataset has 1 problem(s)")
    assert problem in str(sent)


def test_the_committed_grid_loads() -> None:
    config = load()
    assert config.seeds == 20
    assert config.members == 5000
    assert set(config.retention.assumed) == {"email", "discount"}


@pytest.fixture(scope="module")
def results(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("results")
    grid.run(SMALL_GRID, out, workers=1, echo=lambda _: None)
    return out


def test_a_small_grid_writes_every_policy_and_budget(results: Path) -> None:
    retention = pl.read_csv(results / "retention.csv")
    assert retention.height == 2 * 2 * len(POLICIES)
    assert retention["policy"].unique(maintain_order=True).to_list() == list(POLICIES)
    oracle = retention.filter(pl.col("policy") == "oracle")
    assert (oracle["spend"] <= oracle["budget"] + 1e-6).all()
    assert (oracle["precision"] == 1.0).all()
    models = pl.read_csv(results / "models.csv")
    assert models["seed"].to_list() == [1, 2]
    assert (models["unmatched"] == 0).all()  # the risk group is libsim's renewals
    assert ((models["roc_auc_best"] > 0.5) & (models["roc_auc_best"] <= 1)).all()
    assert models["discount_covered"].dtype == pl.Boolean
    assert json.loads((results / "config.json").read_text())["presets"] == ["demo"]


def test_tables_go_to_a_workbook_and_the_terminal(results: Path) -> None:
    outcome = CliRunner().invoke(app, ["tables", "--out", str(results)])
    assert outcome.exit_code == 0, outcome.output
    assert "Оракул" in outcome.output
    workbook = openpyxl.load_workbook(results / tables.WORKBOOK)
    assert workbook.sheetnames == [
        "Виграш, грн",
        "Частка оракула, %",
        "Точність дій, %",
        "Модель і ефекти",
    ]
    sheet = workbook["Частка оракула, %"]
    assert sheet.max_row == 1 + len(POLICIES)
    assert sheet.cell(row=9, column=2).value == "Оракул"
    assert sheet.cell(row=9, column=3).value == "100 ± 0"


def test_a_parallel_run_gives_the_same_results(results: Path, tmp_path: Path) -> None:
    grid.run(SMALL_GRID, tmp_path, workers=2, echo=lambda _: None)
    for name in ("retention.csv", "models.csv"):
        assert (tmp_path / name).read_text() == (results / name).read_text()
