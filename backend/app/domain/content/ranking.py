"""Rankings of the alternatives by weighted criteria (TOPSIS, SAW) and how much they depend on the
weights: a sweep of one weight and a Monte Carlo over weights around the analyst's."""

import numpy as np

STABILITY_DRAWS = 2000
# Dirichlet concentration around the weights: each weight's spread is about
# sqrt(w (1 − w) / (CONCENTRATION + 1)), 0.09 for four equal weights.
CONCENTRATION = 20.0
SWEEP_STEPS = 101


def topsis(matrix: np.ndarray, weights: np.ndarray, benefit: np.ndarray) -> np.ndarray:
    """Closeness to the ideal (Hwang & Yoon): vector-normalized, weighted columns; the distance to
    the worst over the sum of the distances to the best and the worst. 0.5 when all are equal."""
    norms = np.sqrt((matrix**2).sum(axis=0))
    weighted = np.divide(matrix, norms, out=np.zeros_like(matrix, dtype=float), where=norms > 0)
    weighted = weighted * weights
    return _closeness(weighted, benefit)


def _closeness(weighted: np.ndarray, benefit: np.ndarray) -> np.ndarray:
    """Closeness for weighted, normalized scores; the last two axes are alternatives × criteria."""
    best = np.where(
        benefit, weighted.max(axis=-2, keepdims=True), weighted.min(axis=-2, keepdims=True)
    )
    worst = np.where(
        benefit, weighted.min(axis=-2, keepdims=True), weighted.max(axis=-2, keepdims=True)
    )
    to_best = np.sqrt(((weighted - best) ** 2).sum(axis=-1))
    to_worst = np.sqrt(((weighted - worst) ** 2).sum(axis=-1))
    total = to_best + to_worst
    return np.divide(to_worst, total, out=np.full_like(total, 0.5), where=total > 0)


def saw(matrix: np.ndarray, weights: np.ndarray, benefit: np.ndarray) -> np.ndarray:
    """Simple additive weighting with linear normalization: x / max for a benefit, min / x for a
    cost (a cost of 0 is the best possible)."""
    top = matrix.max(axis=0)
    low = matrix.min(axis=0)
    gains = np.divide(matrix, top, out=np.zeros_like(matrix, dtype=float), where=top > 0)
    costs = np.divide(
        np.broadcast_to(low, matrix.shape),
        matrix,
        out=np.ones_like(matrix, dtype=float),
        where=matrix > 0,
    )
    return np.where(benefit, gains, costs) @ weights


def ranks(scores: np.ndarray) -> np.ndarray:
    """1 for the best score; ties share the better rank."""
    order = (-scores).argsort(kind="stable")
    ranked = np.empty(scores.size, dtype=int)
    ranked[order] = np.arange(1, scores.size + 1)
    for value in np.unique(scores):
        tied = scores == value
        ranked[tied] = ranked[tied].min()
    return ranked


def agreement(first: np.ndarray, second: np.ndarray) -> float | None:
    """Kendall's τ-b between two scorings of the same alternatives: (concordant − discordant
    pairs) / √(pairs untied in the first × pairs untied in the second). None when a scoring
    ranks nothing apart."""
    i, j = np.triu_indices(first.size, k=1)
    a, b = np.sign(first[i] - first[j]), np.sign(second[i] - second[j])
    untied = np.count_nonzero(a) * np.count_nonzero(b)
    return float((a * b).sum() / np.sqrt(untied)) if untied else None


def with_weight(weights: np.ndarray, criterion: int, value: float) -> np.ndarray:
    """`weights` with one criterion's weight set to `value` and the others scaled to fill the
    rest in their old proportions (equally, if they were all 0)."""
    others = np.delete(np.arange(weights.size), criterion)
    rest = weights[others]
    shares = rest / rest.sum() if rest.sum() > 0 else np.full(rest.size, 1 / max(rest.size, 1))
    result = np.empty_like(weights, dtype=float)
    result[criterion] = value
    result[others] = shares * (1 - value)
    return result


def sweep(
    matrix: np.ndarray, weights: np.ndarray, benefit: np.ndarray, steps: int = SWEEP_STEPS
) -> tuple[np.ndarray, np.ndarray]:
    """The TOPSIS leader as each criterion's weight runs from 0 to 1 (the others keep their
    proportions): the grid of weights and the leader's index per criterion and grid point."""
    grid = np.linspace(0.0, 1.0, steps)
    leaders = np.array(
        [
            [int(np.argmax(topsis(matrix, with_weight(weights, k, t), benefit))) for t in grid]
            for k in range(weights.size)
        ]
    )
    return grid, leaders


def stability(
    matrix: np.ndarray,
    weights: np.ndarray,
    benefit: np.ndarray,
    top: int,
    *,
    draws: int = STABILITY_DRAWS,
    seed: int = 0,
) -> np.ndarray:
    """How often each alternative stays among the `top` by TOPSIS when the weights are drawn from
    a Dirichlet distribution centred on `weights` (0..1 per alternative)."""
    n = matrix.shape[0]
    if n == 0 or top <= 0:
        return np.zeros(n)
    rng = np.random.default_rng(seed)
    alpha = np.maximum(weights * CONCENTRATION, 1e-3)
    drawn = rng.dirichlet(alpha, size=draws)  # draws × criteria
    norms = np.sqrt((matrix**2).sum(axis=0))
    normalized = np.divide(matrix, norms, out=np.zeros_like(matrix, dtype=float), where=norms > 0)
    scores = _closeness(normalized[None, :, :] * drawn[:, None, :], benefit)  # draws × n
    order = np.argsort(-scores, axis=1, kind="stable")[:, : min(top, n)]
    counts = np.bincount(order.ravel(), minlength=n)
    return counts / draws
