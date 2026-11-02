"""The content decision as a section in the shape of the analytics (DESIGN.md §2.9): the weights,
both rankings with their stability, how far each weight can move before the leader changes, and
the portfolio, so every client and report export can show it."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import polars as pl

from app.domain.analytics.candidates import COST
from app.domain.analytics.candidates import CRITERIA as CRITERION_MEASURES
from app.domain.analytics.common import records
from app.domain.analytics.model import Chart, Dimension, Kpi, Measure, Note, Section
from app.domain.content import ahp, ranking
from app.domain.content.portfolio import portfolio

CRITERIA = tuple(m.key for m in CRITERION_MEASURES)
CRITERION = Dimension("criterion", "category", enum="content_criterion", order=CRITERIA)
COMPARED = Dimension("compared_with", "category", enum="content_criterion", order=CRITERIA)
CHOICES = ("licensed", "skipped")
INCONSISTENT = Note(
    "content.inconsistent",
    "Судження суперечать одне одному (CR понад 0,1). Перегляньте найменш узгоджені, перш ніж "
    "затверджувати рішення.",
)
EQUAL_WEIGHTS = Note(
    "content.equal_weights",
    "Критерії ще не порівняно, тому всі вони мають однакову вагу.",
)


@dataclass(frozen=True)
class Choice:
    judgements: Sequence[ahp.Judgement]  # rows and columns index CRITERIA
    budget: float
    max_per_genre: int | None = None


@dataclass(frozen=True)
class Decision:
    section: Section
    weights: ahp.Weights


def _records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return records(pl.DataFrame(rows, infer_schema_length=None)) if rows else []


def _stable_range(
    grid: np.ndarray, leaders: np.ndarray, leader: int, weight: float
) -> tuple[float, float]:
    """The weights around `weight` over which `leader` stays first (on the sweep's grid)."""
    at = int(np.argmin(np.abs(grid - weight)))
    if leaders[at] != leader:
        return weight, weight
    low, high = at, at
    while low > 0 and leaders[low - 1] == leader:
        low -= 1
    while high < grid.size - 1 and leaders[high + 1] == leader:
        high += 1
    return float(grid[low]), float(grid[high])


def decide(offer: list[dict[str, Any]], choice: Choice) -> Decision:
    """Weigh the criteria, rank the titles on offer (rows of the `candidates` section) and pick
    the portfolio within the budget."""
    matrix = np.array([[float(row[key] or 0) for key in CRITERIA] for row in offer])
    benefit = np.ones(len(CRITERIA), dtype=bool)
    weights = ahp.weigh(ahp.comparisons(len(CRITERIA), choice.judgements))
    w = weights.weights
    closeness = ranking.topsis(matrix, w, benefit)
    simple = ranking.saw(matrix, w, benefit)
    cost = np.array([float(row[COST.key]) for row in offer])
    genre = np.array([row["genre"] for row in offer])
    chosen = portfolio(closeness, cost, genre, choice.budget, choice.max_per_genre).chosen
    stability = ranking.stability(matrix, w, benefit, top=max(int(chosen.sum()), 1))
    grid, leaders = ranking.sweep(matrix, w, benefit)
    leader = int(np.argmax(closeness))
    by_topsis, by_saw = ranking.ranks(closeness), ranking.ranks(simple)
    searches = np.array([float(row["demand_searches"] or 0) for row in offer])

    ranked = pl.DataFrame(
        [
            {
                "title": offer[i]["title"],
                "authors": offer[i]["authors"],
                "genre": offer[i]["genre"],
                "candidate_id": offer[i]["candidate_id"],
                "choice": CHOICES[0] if chosen[i] else CHOICES[1],
                "rank_topsis": int(by_topsis[i]),
                "topsis": float(closeness[i]),
                "rank_saw": int(by_saw[i]),
                "saw": float(simple[i]),
                "stability": float(stability[i]),
                "demand_searches": float(searches[i]),
                COST.key: float(cost[i]),
            }
            for i in np.argsort(-closeness, kind="stable")
        ],
        infer_schema_length=None,
    )
    ranges = [_stable_range(grid, leaders[k], leader, float(w[k])) for k in range(len(CRITERIA))]
    notes = [] if weights.consistent_enough else [INCONSISTENT]
    if not choice.judgements:
        notes.append(EQUAL_WEIGHTS)
    section = Section(
        "content_portfolio",
        kpis=[
            Kpi("consistency_ratio", weights.cr, "ratio"),
            Kpi("portfolio_titles", int(chosen.sum()), "count"),
            Kpi("portfolio_spend", float(cost[chosen].sum()), "UAH"),
            Kpi("portfolio_searches", float(searches[chosen].sum()), "count"),
            Kpi("ranking_agreement", ranking.agreement(closeness, simple), "ratio"),
        ],
        charts=[
            Chart(
                "criterion_weights",
                (CRITERION,),
                (
                    Measure("weight", "ratio"),
                    Measure("stable_from", "ratio"),
                    Measure("stable_to", "ratio"),
                ),
                _records(
                    [
                        {
                            "criterion": key,
                            "weight": float(w[k]),
                            "stable_from": low,
                            "stable_to": high,
                        }
                        for k, (key, (low, high)) in enumerate(zip(CRITERIA, ranges, strict=True))
                    ]
                ),
            ),
            Chart(
                "title_ranking",
                (Dimension("title", "category"),),
                (
                    Measure("rank_topsis", "count"),
                    Measure("topsis", "ratio"),
                    Measure("rank_saw", "count"),
                    Measure("saw", "ratio"),
                    Measure("stability", "ratio"),
                    Measure("demand_searches", "count"),
                    COST,
                ),
                records(ranked),
                attributes=(
                    Dimension("authors", "category"),
                    Dimension("genre", "category", enum="genre"),
                    Dimension("candidate_id", "category"),
                    Dimension("choice", "category", enum="content_choice", order=CHOICES),
                ),
            ),
            Chart(
                "inconsistent_judgements",
                (CRITERION, COMPARED),
                (Measure("judgement_given", "count"), Measure("judgement_consistent", "count")),
                _records(
                    [
                        {
                            "criterion": CRITERIA[j.row],
                            "compared_with": CRITERIA[j.column],
                            "judgement_given": j.given,
                            "judgement_consistent": j.consistent,
                        }
                        for j in weights.inconsistent
                    ]
                    if not weights.consistent_enough
                    else []
                ),
            ),
        ],
        notes=notes,
    )
    return Decision(section, weights)
