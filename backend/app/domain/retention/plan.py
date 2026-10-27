"""The best retention action for each member at risk under a budget (DESIGN.md §2.9).

Members come as a frame: `user_id`, `probability` (of churn without an action), `segment`,
`email_opt_in`, `discounted` (the running period already is), `monthly_value` (the list price
per month) and `period_price` (the list price of the renewal; null when unknown).
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import polars as pl
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_array

from app.domain.retention.effects import ACTIONS, SEGMENTS, Action, Effect, Segment

EffectTable = dict[tuple[Action, Segment], float]
CURVE_STEPS = 8
MIP_GAP = 1e-4  # HiGHS's default relative gap: optimal within 0.01%


@dataclass(frozen=True)
class Scenario:
    budget: float  # UAH: the expected spend on e-mails and discounts
    horizon_months: int = 12  # how many months of a kept member's price count as gained
    discount_pct: float = 0.2  # off the price of the next period
    email_cost: float = 2.0  # UAH per e-mail
    max_emails: int | None = None
    max_discounts: int | None = None
    cautious: bool = False  # take the least favourable bound of each effect
    assumed: dict[Action, float] | None = None  # the analyst's effects, used instead


@dataclass(frozen=True)
class Plan:
    chosen: pl.DataFrame  # the options taken, highest gain first (see `options`)
    value: float  # expected net gain, UAH
    spend: float  # expected spend, UAH
    saved: float  # expected members kept
    greedy_value: float  # what filling the budget by gain per hryvnia would gain


def effect_table(
    effects: list[Effect], scenario: Scenario, campaign_discount: float | None
) -> EffectTable:
    """The effect of each action per segment the plan uses.

    The analyst's assumed effects apply to every segment. Otherwise the campaign's shrunk
    segment effects (or their cautious bounds) are used, and a discount's effect is scaled by
    its size against the campaign's discount. Missing estimates count as no effect.
    """
    if scenario.assumed is not None:
        return {(a, s): scenario.assumed.get(a, 0.0) for a in ACTIONS for s in SEGMENTS}
    table: EffectTable = {(a, s): 0.0 for a in ACTIONS for s in SEGMENTS}
    for effect in effects:
        value = effect.cautious if scenario.cautious else effect.shrunk
        if effect.segment is None or value is None:
            continue
        if effect.action == "discount":
            value = value * scenario.discount_pct / campaign_discount if campaign_discount else 0.0
        table[effect.action, effect.segment] = value
    return table


def options(members: pl.DataFrame, effects: EffectTable, scenario: Scenario) -> pl.DataFrame:
    """Every action worth taking for a member: `user_id`, `action`, `p_none`, `p_action`,
    `gain` and expected `spend`.

    gain = (p_none − p_action)·monthly_value·horizon − spend, where a discount's spend is the
    price it gives away if the member renews and an e-mail's is its cost.
    """
    parts = []
    for action in ACTIONS:
        effect = pl.col("segment").replace_strict(
            {segment: effects[action, segment] for segment in SEGMENTS}, return_dtype=pl.Float64
        )
        p_action = (pl.col("probability") + effect).clip(0.0, 1.0)
        if action == "email":
            eligible = pl.col("email_opt_in").fill_null(False)
            spend = pl.lit(scenario.email_cost)
        else:
            eligible = ~pl.col("discounted") & pl.col("period_price").is_not_null()
            spend = (1 - p_action) * scenario.discount_pct * pl.col("period_price")
        kept = (
            (pl.col("probability") - p_action) * pl.col("monthly_value") * scenario.horizon_months
        )
        parts.append(
            members.filter(eligible).select(
                "user_id",
                action=pl.lit(action),
                p_none="probability",
                p_action=p_action,
                gain=kept - spend,
                spend=spend,
            )
        )
    return pl.concat(parts).filter(pl.col("gain") > 0).sort("user_id", "action")


def _limits(scenario: Scenario) -> dict[Action, int | None]:
    return {"email": scenario.max_emails, "discount": scenario.max_discounts}


def _optimize(choices: pl.DataFrame, scenario: Scenario, budget: float, *, integral: bool) -> Any:
    """A multiple-choice knapsack (HiGHS): at most one action per member, the expected spend
    within the budget, and the per-action limits. `integral=False` solves the LP relaxation."""
    n = choices.height
    every = np.arange(n)
    member = choices["user_id"].rank("dense").cast(pl.Int64).to_numpy() - 1
    upper = [1.0] * (int(member.max()) + 1)  # one action per member
    rows, columns, values = [member, np.full(n, len(upper))], [every, every], [np.ones(n)]
    values.append(choices["spend"].to_numpy())  # the budget
    upper.append(budget)
    actions = choices["action"].to_numpy()
    for action, limit in _limits(scenario).items():
        if limit is not None:
            taken = np.flatnonzero(actions == action)
            rows.append(np.full(taken.size, len(upper)))
            columns.append(taken)
            values.append(np.ones(taken.size))
            upper.append(float(limit))
    matrix = coo_array(
        (np.concatenate(values), (np.concatenate(rows), np.concatenate(columns))),
        shape=(len(upper), n),
    )
    result = milp(
        c=-choices["gain"].to_numpy(),
        constraints=LinearConstraint(matrix, -np.inf, np.array(upper)),
        integrality=np.full(n, 1 if integral else 0),
        bounds=Bounds(0, 1),
        options={"mip_rel_gap": MIP_GAP},
    )
    if result.x is None:
        raise RuntimeError(f"the plan could not be solved: {result.message}")
    return result


def solve(choices: pl.DataFrame, scenario: Scenario, budget: float) -> np.ndarray:
    """Which options to take (a 0/1 mask), optimal within `MIP_GAP`."""
    if choices.is_empty():
        return np.zeros(0, dtype=bool)
    return _optimize(choices, scenario, budget, integral=True).x > 0.5


def greedy(choices: pl.DataFrame, scenario: Scenario, budget: float) -> np.ndarray:
    """The baseline: options by gain per hryvnia of spend, while the budget and limits allow."""
    users, actions, spends = (choices[c].to_list() for c in ("user_id", "action", "spend"))
    ratio = (choices["gain"] / choices["spend"].clip(lower_bound=1e-9)).to_numpy()
    limits = _limits(scenario)
    counts = dict.fromkeys(ACTIONS, 0)
    members: set[str] = set()
    taken = np.zeros(choices.height, dtype=bool)
    spent = 0.0
    for i in np.argsort(-ratio, kind="stable").tolist():
        limit = limits[actions[i]]
        if users[i] in members or spent + spends[i] > budget:
            continue
        if limit is not None and counts[actions[i]] >= limit:
            continue
        taken[i] = True
        members.add(users[i])
        counts[actions[i]] += 1
        spent += spends[i]
    return taken


def plan(members: pl.DataFrame, effects: EffectTable, scenario: Scenario) -> Plan:
    choices = options(members, effects, scenario)
    best = choices.filter(pl.Series(solve(choices, scenario, scenario.budget), dtype=pl.Boolean))
    baseline = choices.filter(
        pl.Series(greedy(choices, scenario, scenario.budget), dtype=pl.Boolean)
    )
    return Plan(
        chosen=best.sort("gain", descending=True),
        value=float(best["gain"].sum()),
        spend=float(best["spend"].sum()),
        saved=float((best["p_none"] - best["p_action"]).sum()),
        greedy_value=float(baseline["gain"].sum()),
    )


def curve(
    members: pl.DataFrame, effects: EffectTable, scenario: Scenario
) -> list[tuple[float, float]]:
    """The value at budgets from 0 to the spend of every worthwhile action. It is the LP
    relaxation's: a hair above the integer optimum (only a few options end up fractional), and
    fast enough for every point."""
    choices = options(members, effects, scenario)
    if choices.is_empty():
        return [(0.0, 0.0)]
    full = choices.sort("gain", descending=True).unique("user_id", keep="first")["spend"].sum()
    return [
        (float(b), float(-_optimize(choices, scenario, float(b), integral=False).fun))
        for b in np.linspace(0.0, float(full), CURVE_STEPS + 1)
    ]
