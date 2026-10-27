"""The content decision's maths: textbook examples (Saaty; Hwang & Yoon), properties that must
hold for any data, the portfolio against brute force, and the whole decision against libsim's
true demand."""

from itertools import combinations
from typing import Any

import numpy as np
import polars as pl
import pytest
from hypothesis import given
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from app.domain.analytics import candidates
from app.domain.analytics.common import Context
from app.domain.content import ahp, ranking
from app.domain.content.portfolio import portfolio
from app.domain.optimize import MIP_GAP

# Hwang & Yoon (1981): four fighter aircraft by maximum speed, ferry range, maximum payload,
# price (a cost), reliability and manoeuvrability (the last two from a 1..9 scale).
AIRCRAFT = np.array(
    [
        [2.0, 1500, 20000, 5.5, 5, 9],
        [2.5, 2700, 18000, 6.5, 3, 5],
        [1.8, 2000, 21000, 4.5, 7, 7],
        [2.2, 1800, 20000, 5.0, 5, 5],
    ]
)
AIRCRAFT_WEIGHTS = np.array([0.2, 0.1, 0.1, 0.1, 0.2, 0.3])
AIRCRAFT_BENEFIT = np.array([True, True, True, False, True, True])


def test_saaty_three_criteria() -> None:
    """Saaty's classic example: weights 0.637, 0.258, 0.105; λmax 3.039; CR 0.033."""
    weights = ahp.weigh(np.array([[1, 3, 5], [1 / 3, 1, 3], [1 / 5, 1 / 3, 1]]))
    assert weights.weights == pytest.approx([0.637, 0.258, 0.105], abs=1e-3)
    assert weights.lambda_max == pytest.approx(3.039, abs=1e-3)
    assert weights.cr == pytest.approx(0.033, abs=1e-3)
    assert weights.consistent_enough


def _judgements(truth: np.ndarray) -> list[ahp.Judgement]:
    n = truth.size
    return [ahp.Judgement(i, j, truth[i] / truth[j]) for i, j in combinations(range(n), 2)]


def test_consistent_judgements_give_their_weights() -> None:
    truth = np.array([0.4, 0.3, 0.2, 0.1])
    weights = ahp.weigh(ahp.comparisons(4, _judgements(truth)))
    assert weights.weights == pytest.approx(truth)
    assert weights.cr == pytest.approx(0, abs=1e-9)
    assert weights.inconsistent == []


def test_an_inconsistent_judgement_is_named_first() -> None:
    """Five judgements agree on 0.4, 0.3, 0.2, 0.1, but one says criterion 3 beats criterion 0
    by 5: the ratio fails, and that judgement leads the list. The weights, which every judgement
    shaped, ask for a larger value than the one given."""
    judgements = _judgements(np.array([0.4, 0.3, 0.2, 0.1]))
    judgements[2] = ahp.Judgement(0, 3, 1 / 5)  # (0, 3) was 4
    weights = ahp.weigh(ahp.comparisons(4, judgements))
    assert not weights.consistent_enough
    first = weights.inconsistent[0]
    assert (first.row, first.column, first.given) == (0, 3, pytest.approx(0.2))
    assert first.consistent > 3 * first.given
    assert len(weights.inconsistent) == ahp.SHOWN_INCONSISTENT


def test_judgements_are_checked() -> None:
    with pytest.raises(ValueError, match="itself"):
        ahp.comparisons(3, [ahp.Judgement(1, 1, 2)])
    with pytest.raises(ValueError, match="outside"):
        ahp.comparisons(3, [ahp.Judgement(0, 1, 10)])
    unjudged = ahp.weigh(ahp.comparisons(3, []))
    assert unjudged.weights == pytest.approx([1 / 3] * 3)
    assert unjudged.cr == 0


@given(arrays(np.float64, st.integers(2, 6), elements=st.floats(0.05, 1)))
def test_any_consistent_judgements_are_recovered(raw: np.ndarray) -> None:
    truth = raw / raw.sum()
    if (truth.max() / truth.min()) > ahp.SCALE_MAX:
        return  # not expressible on the 1/9..9 scale
    weights = ahp.weigh(ahp.comparisons(truth.size, _judgements(truth)))
    assert weights.weights == pytest.approx(truth, abs=1e-9)
    assert weights.cr == pytest.approx(0, abs=1e-9)


def test_topsis_fighter_aircraft() -> None:
    """Hwang & Yoon's closeness: 0.643, 0.268, 0.614, 0.312, so A1 ≻ A3 ≻ A4 ≻ A2."""
    closeness = ranking.topsis(AIRCRAFT, AIRCRAFT_WEIGHTS, AIRCRAFT_BENEFIT)
    assert closeness == pytest.approx([0.643, 0.268, 0.614, 0.312], abs=1e-3)
    assert ranking.ranks(closeness).tolist() == [1, 4, 2, 3]


def test_saw_fighter_aircraft() -> None:
    """By hand, x / max and min / x for the price: A1 = 0.2·0.8 + 0.1·0.556 + 0.1·0.952 +
    0.1·0.818 + 0.2·0.714 + 0.3·1 = 0.836; likewise 0.707, 0.851 and 0.737. SAW puts A3 first,
    TOPSIS A1: one swapped pair of six, Kendall's τ = (5 − 1) / 6."""
    scores = ranking.saw(AIRCRAFT, AIRCRAFT_WEIGHTS, AIRCRAFT_BENEFIT)
    assert scores == pytest.approx([0.836, 0.707, 0.851, 0.737], abs=1e-3)
    closeness = ranking.topsis(AIRCRAFT, AIRCRAFT_WEIGHTS, AIRCRAFT_BENEFIT)
    assert ranking.agreement(closeness, scores) == pytest.approx(2 / 3)


def test_ranks_and_agreement_with_ties() -> None:
    assert ranking.ranks(np.array([0.2, 0.9, 0.2, 0.5])).tolist() == [3, 1, 3, 2]
    # τ-b: pairs (0,2) and (1,2) agree, the first scoring ties 0 and 1: 2 / √(2 · 3)
    assert ranking.agreement(np.array([1, 1, 2]), np.array([1, 2, 3])) == pytest.approx(
        2 / np.sqrt(6)
    )
    assert ranking.agreement(np.array([1, 1, 1]), np.array([1, 2, 3])) is None


@st.composite
def problems(draw: st.DrawFn) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = draw(st.integers(2, 8))
    m = draw(st.integers(1, 5))
    values = st.one_of(st.just(0.0), st.floats(1e-3, 1000))  # no subnormals to underflow
    matrix = draw(arrays(np.float64, (n, m), elements=values))
    weights = draw(arrays(np.float64, m, elements=st.floats(0.01, 1)))
    benefit = draw(arrays(np.bool_, m))
    return matrix, weights / weights.sum(), benefit


METHODS = (ranking.topsis, ranking.saw)


@given(problems(), st.data())
def test_a_dominated_alternative_never_beats_its_dominator(
    problem: tuple[np.ndarray, np.ndarray, np.ndarray], data: st.DataObject
) -> None:
    matrix, weights, benefit = problem
    worse = data.draw(arrays(np.float64, matrix.shape[1], elements=st.floats(0, 100)))
    dominated = matrix[0] + np.where(benefit, -worse, worse)  # worse or equal everywhere
    both = np.vstack([matrix, np.clip(dominated, 0, None)])
    for method in METHODS:
        scores = method(both, weights, benefit)
        assert scores[0] >= scores[-1] - 1e-9, method.__name__


@given(problems(), st.data())
def test_units_and_order_do_not_matter(
    problem: tuple[np.ndarray, np.ndarray, np.ndarray], data: st.DataObject
) -> None:
    matrix, weights, benefit = problem
    n, m = matrix.shape
    scale = data.draw(arrays(np.float64, m, elements=st.floats(0.001, 1000)))
    rows = np.array(data.draw(st.permutations(range(n))))
    columns = np.array(data.draw(st.permutations(range(m))))
    for method in METHODS:
        scores = method(matrix, weights, benefit)
        assert method(matrix * scale, weights, benefit) == pytest.approx(scores, abs=1e-9)
        assert method(matrix[rows], weights, benefit) == pytest.approx(scores[rows], abs=1e-9)
        shuffled = method(matrix[:, columns], weights[columns], benefit[columns])
        assert shuffled == pytest.approx(scores, abs=1e-9)


def test_the_sweep_ends_with_the_best_on_one_criterion() -> None:
    """With all the weight on one criterion, the leader is the best on it alone; at the
    analyst's own weights, it is the TOPSIS leader."""
    grid, leaders = ranking.sweep(AIRCRAFT, AIRCRAFT_WEIGHTS, AIRCRAFT_BENEFIT)
    assert (grid[0], grid[-1]) == (0, 1)
    best_alone = [
        int(np.argmax(c)) if b else int(np.argmin(c))
        for c, b in zip(AIRCRAFT.T, AIRCRAFT_BENEFIT, strict=True)
    ]
    assert leaders[:, -1].tolist() == best_alone
    leader = int(np.argmax(ranking.topsis(AIRCRAFT, AIRCRAFT_WEIGHTS, AIRCRAFT_BENEFIT)))
    for k, weight in enumerate(AIRCRAFT_WEIGHTS):
        assert leaders[k, int(np.argmin(np.abs(grid - weight)))] == leader


def test_stability_counts_the_draws_in_the_top() -> None:
    shares = ranking.stability(AIRCRAFT, AIRCRAFT_WEIGHTS, AIRCRAFT_BENEFIT, top=2, seed=1)
    assert shares.sum() == pytest.approx(2)  # every draw puts two aircraft in the top two
    assert shares == pytest.approx(
        ranking.stability(AIRCRAFT, AIRCRAFT_WEIGHTS, AIRCRAFT_BENEFIT, top=2, seed=1)
    )
    # A1 and A3 lead at the analyst's weights and stay there; A2 and A4 rarely get in.
    assert shares[[0, 2]].min() > 0.9
    assert shares[[1, 3]].max() < 0.1
    dominant = np.vstack([AIRCRAFT, AIRCRAFT.max(axis=0) * np.where(AIRCRAFT_BENEFIT, 1, 0.5)])
    alone = ranking.stability(dominant, AIRCRAFT_WEIGHTS, AIRCRAFT_BENEFIT, top=1)
    assert alone[-1] == 1.0  # best on every criterion: first under any weights


def _brute_force(
    score: np.ndarray, cost: np.ndarray, genre: np.ndarray, budget: float, cap: int
) -> float:
    best = 0.0
    for size in range(1, score.size + 1):
        for items in combinations(range(score.size), size):
            picked = list(items)
            fits = cost[picked].sum() <= budget + 1e-9
            capped = np.bincount(genre[picked]).max() <= cap
            if fits and capped:
                best = max(best, float(np.where(score > 0, score, 0)[picked].sum()))
    return best


def test_the_portfolio_equals_brute_force() -> None:
    rng = np.random.default_rng(3)
    for _ in range(150):
        n = int(rng.integers(1, 10))
        score = rng.uniform(-0.1, 1, n)
        cost = rng.uniform(100, 1000, n).round()
        genre = rng.integers(0, 3, n)
        budget = float(rng.uniform(0, cost.sum()))
        cap = int(rng.integers(1, 4))
        chosen = portfolio(score, cost, genre, budget, cap)
        assert chosen.spend <= budget + 1e-6
        assert not chosen.chosen[score <= 0].any()
        assert np.bincount(genre[chosen.chosen], minlength=3).max() <= cap
        best = _brute_force(score, cost, genre, budget, cap)
        assert chosen.value == pytest.approx(best, rel=MIP_GAP, abs=1e-9)


def test_an_empty_or_worthless_offer_gives_an_empty_portfolio() -> None:
    empty = portfolio(np.zeros(0), np.zeros(0), np.zeros(0, dtype=int), 1000)
    assert (empty.value, empty.spend, empty.chosen.size) == (0.0, 0.0, 0)
    worthless = portfolio(np.zeros(3), np.full(3, 10.0), np.zeros(3, dtype=int), 1000)
    assert not worthless.chosen.any()


@pytest.mark.slow
def test_the_decision_finds_more_true_demand_than_chance(
    demo_simulation: tuple[Any, dict[str, Any], pl.DataFrame],
) -> None:
    """On the demo (seed 1), titles ranked by TOPSIS with equal weights and packed under a
    budget of a quarter of the offer will be asked for more in the next 30 days than random
    portfolios of the same budget."""
    parsed, truth, _ = demo_simulation
    table = candidates.criteria(parsed.frames, Context.at(parsed.as_of, parsed.timezone))
    keys = [m.key for m in candidates.CRITERIA]
    matrix = table.select(keys).to_numpy().astype(float)
    benefit = np.ones(len(keys), dtype=bool)
    score = ranking.topsis(matrix, np.full(len(keys), 1 / len(keys)), benefit)
    cost = table["license_cost"].to_numpy()
    genre = np.unique(table["genre"].to_numpy(), return_inverse=True)[1]
    budget = float(cost.sum()) / 4
    chosen = portfolio(score, cost, genre, budget, max_per_genre=5).chosen
    demand = np.array(
        [truth["candidates"][cid]["demand_future_window"] for cid in table["candidate_id"]]
    )
    rng = np.random.default_rng(0)
    chance = []
    for _ in range(500):
        picked, spent = [], 0.0
        for i in rng.permutation(cost.size):
            if spent + cost[i] <= budget:
                picked.append(i)
                spent += cost[i]
        chance.append(demand[picked].sum())
    assert demand[chosen].sum() > np.mean(chance)
