"""Criterion weights from pairwise judgements: Saaty's analytic hierarchy process."""

import math
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

# Saaty's random consistency index by the number of criteria (n = 0..10).
RANDOM_INDEX = (0.0, 0.0, 0.0, 0.58, 0.90, 1.12, 1.24, 1.32, 1.41, 1.45, 1.49)
MAX_CR = 0.10  # judgements above it are too inconsistent to approve
SCALE_MAX = 9.0  # judgements go from 1/9 to 9
SHOWN_INCONSISTENT = 3


@dataclass(frozen=True)
class Judgement:
    row: int
    column: int
    value: float  # how many times more important criterion `row` is than `column`


@dataclass(frozen=True)
class Inconsistency:
    row: int
    column: int
    given: float
    consistent: float  # the judgement that would agree with the weights: w_row / w_column


@dataclass(frozen=True)
class Weights:
    weights: np.ndarray  # sum to 1
    lambda_max: float
    ci: float  # consistency index (λmax − n) / (n − 1)
    cr: float  # consistency ratio CI / RI; 0 for two criteria or fewer
    inconsistent: list[Inconsistency]  # the judgements least in line with the weights, worst first

    @property
    def consistent_enough(self) -> bool:
        return self.cr <= MAX_CR


def comparisons(n: int, judgements: Iterable[Judgement]) -> np.ndarray:
    """The reciprocal comparison matrix; pairs without a judgement count as equally important."""
    matrix = np.ones((n, n))
    for j in judgements:
        if j.row == j.column:
            raise ValueError("a criterion is not compared with itself")
        if not 1 / SCALE_MAX <= j.value <= SCALE_MAX:
            raise ValueError(f"judgement {j.value} is outside 1/9..9")
        matrix[j.row, j.column] = j.value
        matrix[j.column, j.row] = 1 / j.value
    return matrix


def weigh(matrix: np.ndarray) -> Weights:
    """Weights from the principal eigenvector, with the consistency ratio and the judgements that
    disagree with the weights the most (their error a_ij · w_j / w_i is furthest from 1)."""
    n = matrix.shape[0]
    values, vectors = np.linalg.eig(matrix)
    k = int(np.argmax(np.real(values)))
    weights = np.abs(np.real(vectors[:, k]))
    weights = weights / weights.sum()
    lambda_max = float(np.real(values[k]))
    ci = (lambda_max - n) / (n - 1) if n > 1 else 0.0
    cr = max(ci, 0.0) / RANDOM_INDEX[n] if n < len(RANDOM_INDEX) and RANDOM_INDEX[n] else 0.0
    errors = [
        (abs(math.log(matrix[i, j] * weights[j] / weights[i])), i, j)
        for i in range(n)
        for j in range(i + 1, n)
    ]
    worst = sorted((e for e in errors if e[0] > 1e-9), reverse=True)[:SHOWN_INCONSISTENT]
    return Weights(
        weights=weights,
        lambda_max=lambda_max,
        ci=ci,
        cr=cr,
        inconsistent=[
            Inconsistency(i, j, float(matrix[i, j]), float(weights[i] / weights[j]))
            for _, i, j in worst
        ],
    )
