"""The best retention action for each member at risk under a budget (DESIGN.md §2.9).

Members come as a frame: `user_id`, `probability` (of churn without an action), `segment`,
`email_opt_in`, `discounted` (the running period already is), `monthly_value` (the list price
per month) and `period_price` (the list price of the renewal; null when unknown).
"""

import math
from dataclasses import dataclass

import numpy as np
import polars as pl

from app.domain.optimize import Limit, choose
from app.domain.retention.effects import ACTIONS, SEGMENTS, Action, Effect, Segment, segment_of

EffectTable = dict[tuple[Action, Segment], float]  # shifts of the churn logit
CURVE_STEPS = 8
P_CLIP = 1e-6  # keeps logits finite
# An action prevents at most this share of the churn at its base rate. A larger estimated or
# assumed effect (a treated arm without churns, a typo) would make it remove churn for everyone.
MAX_PREVENTED = 0.9
PLAN_MONTHS = {"annual": 12}  # a list price is per period; the other paid plans are monthly


@dataclass(frozen=True)
class Scenario:
    budget: float  # UAH: the expected spend on e-mails and discounts
    discount_pct: float  # off the renewal price: the campaign's, unless effects are assumed
    horizon_months: int = 12  # how many months of a kept member's price count as gained
    email_cost: float = 2.0  # UAH per e-mail
    max_emails: int | None = None
    max_discounts: int | None = None
    cautious: bool = False  # take the least favourable bound of each effect
    by_segment: bool = False  # each segment's shrunk effect instead of the action's overall one
    assumed: dict[Action, float] | None = None  # the analyst's effects, as differences of rates


@dataclass(frozen=True)
class Plan:
    chosen: pl.DataFrame  # the options taken, highest gain first (see `options`)
    value: float  # expected net gain, UAH
    spend: float  # expected spend, UAH
    saved: float  # expected members kept
    greedy_value: float  # what filling the budget by gain per hryvnia would gain


def members(scored: pl.DataFrame) -> pl.DataFrame:
    """The plan's members from scored ones: `user_id`, `probability`, `period_price` and the
    churn features (as the churn scores keep them). A kept member is worth the list price per
    month: the renewal's price over the plan's months or, without it, what they pay undone by
    their discount (unknown when the period is free)."""
    discount = pl.col("discount").fill_null(0.0)
    months = pl.col("plan").replace_strict(PLAN_MONTHS, default=1, return_dtype=pl.Float64)
    paid = pl.when(discount < 1).then(pl.col("monthly_price") / (1 - discount))
    return scored.select(
        "user_id",
        "probability",
        segment=segment_of(),
        email_opt_in="email_opt_in",
        discounted=discount > 0,
        monthly_value=pl.coalesce(pl.col("period_price") / months, paid),
        period_price="period_price",
    )


def _logit(p: float) -> float:
    p = min(max(p, P_CLIP), 1 - P_CLIP)
    return math.log(p / (1 - p))


def _prevented_too_much(base: float, difference: float) -> bool:
    return base + difference < base * (1 - MAX_PREVENTED)


def shift(base: float, difference: float) -> float:
    """The change of the churn logit that moves the churn rate `base` by `difference`, with at
    most `MAX_PREVENTED` of the churn prevented."""
    return _logit(max(base + difference, base * (1 - MAX_PREVENTED))) - _logit(base)


def _differences(
    effects: list[Effect], scenario: Scenario, base_rate: float
) -> dict[tuple[Action, Segment], tuple[float, float]]:
    """The base rate and the difference of churn rates each action makes per segment.

    The analyst's assumed effects apply to every segment at `base_rate`. Otherwise each
    action's overall campaign effect (or its cautious bound) applies to every segment at the
    control group's churn rate, or with `by_segment` each segment's shrunk effect at the
    segment's own control rate. Missing estimates count as no effect.
    """
    if scenario.assumed is not None:
        assumed = scenario.assumed
        return {(a, s): (base_rate, assumed.get(a, 0.0)) for a in ACTIONS for s in SEGMENTS}
    overall = {e.action: e for e in effects if e.segment is None}
    table: dict[tuple[Action, Segment], tuple[float, float]] = {
        (a, s): (base_rate, 0.0) for a in ACTIONS for s in SEGMENTS
    }
    for effect in effects:
        if effect.segment is None:
            continue
        used = effect if scenario.by_segment else overall.get(effect.action, effect)
        value = used.cautious if scenario.cautious else used.shrunk
        if value is None:
            continue
        control = next((e for e in (used, overall.get(effect.action)) if e and e.control), None)
        base = control.control_churned / control.control if control else base_rate
        table[effect.action, effect.segment] = (base, value)
    return table


def effect_table(effects: list[Effect], scenario: Scenario, base_rate: float) -> EffectTable:
    """The shift of the churn logit each action makes per segment. An effect is measured as a
    difference of churn rates; it becomes a logit shift at its base rate, so the same action
    moves a high-risk member more than a low-risk one."""
    return {
        key: shift(base, difference)
        for key, (base, difference) in _differences(effects, scenario, base_rate).items()
    }


def capped(effects: list[Effect], scenario: Scenario, base_rate: float) -> list[Action]:
    """The actions whose effect is larger than `MAX_PREVENTED` allows in some segment."""
    differences = _differences(effects, scenario, base_rate)
    return [a for a in ACTIONS if any(_prevented_too_much(*differences[a, s]) for s in SEGMENTS)]


def options(members: pl.DataFrame, effects: EffectTable, scenario: Scenario) -> pl.DataFrame:
    """Every action worth taking for a member: `user_id`, `action`, `p_none`, `p_action`,
    `gain` and expected `spend`.

    gain = (p_none − p_action)·monthly_value·horizon − spend, where a discount's spend is the
    price it gives away if the member renews and an e-mail's is its cost.
    """
    p = pl.col("probability").clip(P_CLIP, 1 - P_CLIP)
    parts = []
    for action in ACTIONS:
        effect = pl.col("segment").replace_strict(
            {segment: effects[action, segment] for segment in SEGMENTS}, return_dtype=pl.Float64
        )
        p_action = 1 / (1 + (-((p / (1 - p)).log() + effect)).exp())
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


def _limits(choices: pl.DataFrame, scenario: Scenario, budget: float) -> list[Limit]:
    action = choices["action"].to_numpy()
    limits = [Limit(choices["spend"].to_numpy(), budget)]
    for name, cap in (("email", scenario.max_emails), ("discount", scenario.max_discounts)):
        if cap is not None:
            limits.append(Limit((action == name).astype(float), float(cap)))
    return limits


def solve(choices: pl.DataFrame, scenario: Scenario, budget: float) -> np.ndarray:
    """Which options to take (a 0/1 mask): at most one per member, the expected spend within
    the budget and the per-action limits, the most gain (a MILP, `domain.optimize`)."""
    share, _ = choose(
        choices["gain"].to_numpy(),
        _limits(choices, scenario, budget),
        groups=choices["user_id"].to_numpy(),
    )
    return share > 0.5


def greedy(choices: pl.DataFrame, scenario: Scenario, budget: float) -> np.ndarray:
    """The baseline: options by gain per hryvnia of spend, while the budget and limits allow."""
    users, actions, spends = (choices[c].to_list() for c in ("user_id", "action", "spend"))
    ratio = (choices["gain"] / choices["spend"].clip(lower_bound=1e-9)).to_numpy()
    caps: dict[str, int | None] = {"email": scenario.max_emails, "discount": scenario.max_discounts}
    counts = dict.fromkeys(ACTIONS, 0)
    taken_members: set[str] = set()
    taken = np.zeros(choices.height, dtype=bool)
    spent = 0.0
    for i in np.argsort(-ratio, kind="stable").tolist():
        cap = caps[actions[i]]
        if users[i] in taken_members or spent + spends[i] > budget:
            continue
        if cap is not None and counts[actions[i]] >= cap:
            continue
        taken[i] = True
        taken_members.add(users[i])
        counts[actions[i]] += 1
        spent += spends[i]
    return taken


def plan(members: pl.DataFrame, effects: EffectTable, scenario: Scenario) -> Plan:
    """The solver's plan, or the greedy one in the rare case the solver stopped (within its
    gap) below it."""
    choices = options(members, effects, scenario)
    best = choices.filter(pl.Series(solve(choices, scenario, scenario.budget), dtype=pl.Boolean))
    baseline = choices.filter(
        pl.Series(greedy(choices, scenario, scenario.budget), dtype=pl.Boolean)
    )
    if baseline.select(pl.col("gain").sum()).item() > best.select(pl.col("gain").sum()).item():
        best = baseline
    return Plan(
        chosen=best.sort("gain", descending=True),
        value=best.select(pl.col("gain").sum()).item(),
        spend=best.select(pl.col("spend").sum()).item(),
        saved=best.select((pl.col("p_none") - pl.col("p_action")).sum()).item(),
        greedy_value=baseline.select(pl.col("gain").sum()).item(),
    )


def curve(
    members: pl.DataFrame, effects: EffectTable, scenario: Scenario
) -> list[tuple[float, float]]:
    """The value at budgets from 0 to the spend beyond which more money gains nothing (the
    best plan without a budget, within the per-action limits). It is the LP relaxation's: a
    hair above the integer optimum (only a few options end up fractional), and fast enough
    for every point."""
    choices = options(members, effects, scenario)
    if choices.is_empty():
        return [(0.0, 0.0)]
    gain, groups = choices["gain"].to_numpy(), choices["user_id"].to_numpy()
    spend = choices["spend"].to_numpy()
    unlimited = _limits(choices, scenario, float(spend.sum()))
    full = float(choose(gain, unlimited, groups, integral=False)[0] @ spend)
    return [
        (
            float(budget),
            choose(gain, _limits(choices, scenario, float(budget)), groups, integral=False)[1],
        )
        for budget in np.linspace(0.0, float(full), CURVE_STEPS + 1)
    ]
