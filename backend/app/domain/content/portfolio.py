"""The titles to license: the most total score within the budget, with a cap per genre."""

from dataclasses import dataclass

import numpy as np

from app.domain.optimize import Limit, choose


@dataclass(frozen=True)
class Portfolio:
    chosen: np.ndarray  # bool per title
    value: float  # the chosen titles' total score
    spend: float


def portfolio(
    score: np.ndarray,
    cost: np.ndarray,
    genre: np.ndarray,
    budget: float,
    max_per_genre: int | None = None,
) -> Portfolio:
    """A 0/1 knapsack over the titles (the solver shared with the retention plan). Only titles
    with a positive score are worth a licence."""
    worth = np.flatnonzero(score > 0)
    limits = [Limit(cost[worth].astype(float), budget)]
    if max_per_genre is not None:
        limits += [
            Limit((genre[worth] == g).astype(float), float(max_per_genre))
            for g in np.unique(genre[worth])
        ]
    share, value = choose(score[worth].astype(float), limits)
    chosen = np.zeros(score.size, dtype=bool)
    chosen[worth[share > 0.5]] = True
    return Portfolio(chosen=chosen, value=value, spend=float(cost[chosen].sum()))
