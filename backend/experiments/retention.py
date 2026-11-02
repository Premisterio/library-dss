"""Retention policies on a simulated library, judged by libsim's true churn probabilities
(DESIGN.md §6)."""

from dataclasses import dataclass
from typing import Any

import polars as pl

from app.domain.churn.metrics import evaluate
from app.domain.churn.scoring import Score
from app.domain.optimize import Limit, choose
from app.domain.retention.effects import ACTIONS, Action, Effect
from app.domain.retention.plan import Scenario, effect_table, members, plan
from experiments.config import RetentionConfig

POLICIES = (
    "random",
    "inactive",
    "risk",
    "dss_assumed",
    "dss",
    "dss_segments",
    "dss_cautious",
    "oracle",
)


@dataclass(frozen=True)
class RiskGroup:
    """The members at risk of one library, what the DSS knows about them and the truth."""

    people: pl.DataFrame  # see `people_at_risk`
    effects: list[Effect]  # estimated from the library's campaign
    discount_pct: float  # the campaign's discount, the one its effect was measured for
    seed: int  # the library's, for the random policy


def people_at_risk(scores: list[Score], truth: dict[str, Any]) -> pl.DataFrame:
    """The members at risk as the plan sees them (`members`), with the two features the
    inactivity rule reads, libsim's true churn probabilities under each action (`true_none`,
    `true_email`, `true_discount`) and whether they churned without an action (`churned`)."""
    scored = pl.DataFrame(
        [
            {
                "user_id": s.user_id,
                "probability": s.probability,
                "period_price": s.period_price,
                **s.features,
            }
            for s in scores
        ],
        infer_schema_length=None,
    )
    true = pl.DataFrame(
        [
            {
                "user_id": row["user_id"],
                **{f"true_{action}": p for action, p in row["p_true"].items()},
                "churned": row["outcome"]["none"],
            }
            for row in truth["at_risk"]
        ]
    )
    return (
        members(scored)
        .join(scored.select("user_id", "inactive_14d", "days_since_last_session"), on="user_id")
        .join(true, on="user_id")
        .sort("user_id")
    )


def discount_for_all(group: RiskGroup) -> float:
    """What a discount for every member at risk who can get one costs if they all renew."""
    eligible = group.people.filter(_discountable())
    return group.discount_pct * float(eligible["period_price"].sum())


def true_options(group: RiskGroup, config: RetentionConfig) -> pl.DataFrame:
    """Every action each member can get, judged by the plan's formula on the true probabilities:
    `user_id`, `action`, members `kept`, true expected `spend` and `gain` (UAH)."""
    parts = []
    for action in ACTIONS:
        p_action = pl.col(f"true_{action}")
        if action == "email":
            eligible, spend = pl.col("email_opt_in").fill_null(False), pl.lit(config.email_cost)
        else:
            eligible = _discountable()
            spend = (1 - p_action) * group.discount_pct * pl.col("period_price")
        kept = pl.col("true_none") - p_action
        parts.append(
            group.people.filter(eligible).select(
                "user_id",
                action=pl.lit(action),
                kept=kept,
                spend=spend,
                gain=kept * pl.col("monthly_value") * config.horizon_months - spend,
            )
        )
    return pl.concat(parts)


def decide(
    group: RiskGroup, policy: str, budget: float, config: RetentionConfig, truth: pl.DataFrame
) -> pl.DataFrame:
    """Whom a policy acts on and how: `user_id`, `action`. `truth` is `true_options`, which only
    the oracle reads."""
    people = group.people
    match policy:
        case "random":
            order = people.sample(fraction=1.0, shuffle=True, seed=group.seed)
        case "inactive":
            order = people.filter("inactive_14d").sort(
                ["days_since_last_session", "user_id"], descending=[True, False], nulls_last=False
            )
        case "risk":
            order = people.sort(["probability", "user_id"], descending=[True, False])
        case "oracle":
            return _oracle(truth, budget)
        case _:
            return _dss(group, policy, budget, config)
    return _discounts(order, budget, group.discount_pct)


def judge(chosen: pl.DataFrame, truth: pl.DataFrame) -> dict[str, Any]:
    """What a choice truly achieves: net `value` and `spend` (UAH), the e-mails and discounts,
    the share of actions that truly pay off (`precision`) and the members `kept`."""
    rows = chosen.join(truth, on=["user_id", "action"], how="left")
    if rows["gain"].null_count():
        raise ValueError("a policy chose an action a member cannot get")
    return {
        "value": float(rows["gain"].sum()),
        "spend": float(rows["spend"].sum()),
        "emails": int((rows["action"] == "email").sum()),
        "discounts": int((rows["action"] == "discount").sum()),
        "precision": rows.select((pl.col("gain") > 0).mean()).item() if rows.height else None,
        "kept": float(rows["kept"].sum()),
    }


def evaluate_policies(group: RiskGroup, config: RetentionConfig) -> list[dict[str, Any]]:
    """Every policy at every budget, judged against the truth."""
    truth = true_options(group, config)
    full = discount_for_all(group)
    rows = []
    for share in config.budget_shares:
        budget = share * full
        for policy in POLICIES:
            chosen = decide(group, policy, budget, config, truth)
            rows.append(
                {"budget_share": share, "budget": budget, "policy": policy} | judge(chosen, truth)
            )
    return rows


def model_quality(group: RiskGroup, base_rate: float) -> dict[str, Any]:
    """How well the churn model ranks and predicts the members at risk, next to the best
    possible: libsim's true probabilities. `base_rate` is the training churn rate."""
    churned = group.people["churned"].to_numpy()
    model = evaluate(churned, group.people["probability"].to_numpy(), base_rate)
    best = evaluate(churned, group.people["true_none"].to_numpy(), base_rate)
    return {
        "members_at_risk": model.members,
        "churned": model.churned,
        "roc_auc": model.roc_auc,
        "roc_auc_best": best.roc_auc,
        "brier": model.brier,
        "brier_best": best.brier,
    }


def effect_coverage(
    effects: list[Effect], participants: pl.DataFrame, truth: dict[str, Any]
) -> dict[str, Any]:
    """Each action's estimated effect with its 95% interval, the true average effect on the
    campaign participants it compares (e-mail: those who agreed to e-mails), and whether the
    interval contains it."""
    true = pl.DataFrame(
        [
            {"user_id": row["user_id"], **{f"true_{a}": p for a, p in row["p_true"].items()}}
            for row in truth["campaign"]
        ]
    )
    joined = participants.join(true, on="user_id")
    row: dict[str, Any] = {}
    for effect in effects:
        if effect.segment is not None:
            continue
        action = effect.action
        compared = joined.filter(pl.col("email_opt_in")) if action == "email" else joined
        actual = compared.select((pl.col(f"true_{action}") - pl.col("true_none")).mean()).item()
        covered = None
        if effect.low is not None and effect.high is not None:
            covered = effect.low <= actual <= effect.high
        row |= {
            f"{action}_estimate": effect.difference,
            f"{action}_low": effect.low,
            f"{action}_high": effect.high,
            f"{action}_true": actual,
            f"{action}_covered": covered,
        }
    return row


def _discountable() -> pl.Expr:
    return ~pl.col("discounted") & pl.col("period_price").is_not_null()


def _discounts(order: pl.DataFrame, budget: float, discount_pct: float) -> pl.DataFrame:
    """A discount for each member in this order while the expected spend fits the budget,
    counted as the plan counts it: with the churn model's probability of renewing."""
    spend = (1 - pl.col("probability")) * discount_pct * pl.col("period_price")
    return (
        order.filter(_discountable())
        .filter(spend.cum_sum() <= budget)
        .select("user_id", action=pl.lit("discount"))
    )


def _dss(group: RiskGroup, policy: str, budget: float, config: RetentionConfig) -> pl.DataFrame:
    """The DSS's plan: with the campaign's effects (as the plan form's switches choose them) or,
    for `dss_assumed`, with the analyst's assumed effects."""
    assumed: dict[Action, float] = {a: config.assumed.get(a, 0.0) for a in ACTIONS}
    scenario = Scenario(
        budget=budget,
        discount_pct=group.discount_pct,
        horizon_months=config.horizon_months,
        email_cost=config.email_cost,
        cautious=policy == "dss_cautious",
        by_segment=policy == "dss_segments",
        assumed=assumed if policy == "dss_assumed" else None,
    )
    base_rate = group.people.select(pl.col("probability").mean()).item()
    table = effect_table(group.effects, scenario, base_rate=base_rate)
    return plan(group.people, table, scenario).chosen.select("user_id", "action")


def _oracle(truth: pl.DataFrame, budget: float) -> pl.DataFrame:
    """The best choice if the true effects were known: the plan's solver on the true gains,
    within the budget of true spend."""
    worth = truth.filter(pl.col("gain") > 0)
    share, _ = choose(
        worth["gain"].to_numpy(),
        [Limit(worth["spend"].to_numpy(), budget)],
        groups=worth["user_id"].to_numpy(),
    )
    return worth.filter(pl.Series(share > 0.5, dtype=pl.Boolean)).select("user_id", "action")
