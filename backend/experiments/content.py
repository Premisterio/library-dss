"""Content acquisition policies on a simulated library, judged by libsim's true demand for the
titles on offer (DESIGN.md §6)."""

from datetime import date
from typing import Any

import numpy as np
import polars as pl

from app.domain.analytics.candidates import CRITERIA, criteria
from app.domain.analytics.common import Context, Frames
from app.domain.content import ahp, ranking
from app.domain.content.portfolio import portfolio
from app.domain.optimize import Limit, choose
from experiments.config import ContentConfig

POLICIES = (
    "random",
    "cheapest",
    "most_searched",
    "searches_per_uah",
    "top_genre",
    "saw",
    "dss",
    "dss_searches",
    "oracle",
)
KEYS = tuple(m.key for m in CRITERIA)  # the zero-result searches come first
RANDOM_ORDERS = 100  # the random policy is judged by its mean over this many orders
# `dss_searches`: the searches judged 3 times as important as each other criterion, which gives
# them half the weight (DESIGN §2.9: the searches alone track true demand closely).
SEARCHES_FIRST = [ahp.Judgement(0, k, 3.0) for k in range(1, len(KEYS))]


def offer(frames: Frames, as_of: date, timezone: str, truth: dict[str, Any]) -> pl.DataFrame:
    """The titles on offer with their criteria, genre and licence cost as the `candidates` section
    has them, and libsim's true `demand` for each: the requests in the simulated future."""
    demand = pl.DataFrame(
        [
            {"candidate_id": cid, "demand": row["demand_future_window"]}
            for cid, row in truth["candidates"].items()
        ]
    )
    return (
        criteria(frames, Context.at(as_of, timezone))
        .join(demand, on="candidate_id")
        .sort("candidate_id")
    )


def choose_titles(
    titles: pl.DataFrame, policy: str, budget: float, config: ContentConfig
) -> np.ndarray:
    """The titles a policy licenses (a mask over `titles`); `random` takes one order of many."""
    cost = titles["license_cost"].to_numpy()
    searches = titles["demand_searches"].to_numpy().astype(float)
    match policy:
        case "cheapest":
            return _fill(np.argsort(cost, kind="stable"), cost, budget)
        case "most_searched":
            return _fill(np.argsort(-searches, kind="stable"), cost, budget)
        case "searches_per_uah":
            return _fill(np.argsort(-searches / cost, kind="stable"), cost, budget)
        case "top_genre":
            genre_loans = titles["genre_loans"].to_numpy()
            return _fill(np.lexsort((-searches, -genre_loans)), cost, budget)
        case "oracle":
            demand = titles["demand"].to_numpy().astype(float)
            share, _ = choose(demand, [Limit(cost.astype(float), budget)])
            return share > 0.5
        case _:
            return _mcda(titles, policy, budget, config)


def evaluate_policies(
    titles: pl.DataFrame, config: ContentConfig, seed: int
) -> list[dict[str, Any]]:
    """Every policy at every budget: the true demand the licensed titles meet, how many titles
    they are and what they cost. The random policy's numbers are means over `RANDOM_ORDERS`
    orders, the same orders at every budget."""
    cost = titles["license_cost"].to_numpy()
    demand = titles["demand"].to_numpy()
    full = float(cost.sum())
    rows = []
    for share in config.budget_shares:
        budget = share * full
        for policy in POLICIES:
            if policy == "random":
                rng = np.random.default_rng(seed)
                masks = [
                    _fill(rng.permutation(cost.size), cost, budget) for _ in range(RANDOM_ORDERS)
                ]
            else:
                masks = [choose_titles(titles, policy, budget, config)]
            rows.append(
                {
                    "budget_share": share,
                    "budget": budget,
                    "policy": policy,
                    "demand": float(np.mean([demand[m].sum() for m in masks])),
                    "titles": float(np.mean([m.sum() for m in masks])),
                    "spend": float(np.mean([cost[m].sum() for m in masks])),
                }
            )
    return rows


def _fill(order: np.ndarray, cost: np.ndarray, budget: float) -> np.ndarray:
    """Titles in this order, each one that still fits the budget."""
    chosen = np.zeros(cost.size, dtype=bool)
    spent = 0.0
    for i in order.tolist():
        if spent + cost[i] <= budget:
            chosen[i] = True
            spent += cost[i]
    return chosen


def _mcda(titles: pl.DataFrame, policy: str, budget: float, config: ContentConfig) -> np.ndarray:
    """The DSS's portfolio: AHP weights (equal, or the searches first for `dss_searches`), TOPSIS
    scores (SAW for `saw`) and the knapsack with the cap per genre."""
    matrix = titles.select(KEYS).to_numpy().astype(float)
    judgements = SEARCHES_FIRST if policy == "dss_searches" else []
    weights = ahp.weigh(ahp.comparisons(len(KEYS), judgements)).weights
    benefit = np.ones(len(KEYS), dtype=bool)
    rank = ranking.saw if policy == "saw" else ranking.topsis
    return portfolio(
        rank(matrix, weights, benefit),
        titles["license_cost"].to_numpy(),
        titles["genre"].to_numpy(),
        budget,
        config.max_per_genre,
    ).chosen
