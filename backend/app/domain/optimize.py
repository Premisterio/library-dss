"""Choosing items under linear limits: a 0/1 program solved with HiGHS (DESIGN.md §2.9).

Shared by the retention plan (a member gets at most one action) and the content portfolio.
"""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_array, vstack

# Stop within 0.5% of the best possible gain. Proving 0.01% took minutes on some ordinary
# 2k-member plans; 0.5% takes about a second, and stopping on the gap keeps results
# deterministic (a time limit would not).
MIP_GAP = 5e-3
TIME_LIMIT = 20.0  # seconds; only a safety net, the best plan found by then is used


@dataclass(frozen=True)
class Limit:
    coefficients: np.ndarray  # one per item: spend, cost, or 1 for the items a cap counts
    upper: float


def choose(
    gain: np.ndarray,
    limits: list[Limit],
    groups: np.ndarray | None = None,
    *,
    integral: bool = True,
) -> tuple[np.ndarray, float]:
    """Maximize the total gain of the chosen items under every limit (Σ coefficient ≤ upper),
    taking at most one item per group (items with the same `groups` value).

    Returns each item's share (0 or 1; between them for `integral=False`, the LP relaxation)
    and the total gain.
    """
    n = gain.size
    if n == 0:
        return np.zeros(0), 0.0
    rows = [coo_array(np.vstack([limit.coefficients for limit in limits]))] if limits else []
    upper = [limit.upper for limit in limits]
    if groups is not None:
        group = np.unique(groups, return_inverse=True)[1]
        rows.append(coo_array((np.ones(n), (group, np.arange(n))), shape=(group.max() + 1, n)))
        upper += [1.0] * (int(group.max()) + 1)
    result = milp(
        c=-gain,
        constraints=LinearConstraint(
            vstack(rows),
            -np.inf,
            np.array(upper),  # pyright: ignore[reportArgumentType]  (annotated float, takes arrays)
        )
        if rows
        else None,
        integrality=np.full(n, 1 if integral else 0),
        bounds=Bounds(0, 1),
        options={"mip_rel_gap": MIP_GAP, "time_limit": TIME_LIMIT},
    )
    if result.x is None:
        raise RuntimeError(f"no choice could be made: {result.message}")
    share = np.round(result.x) if integral else result.x
    return share, float(gain @ share)
