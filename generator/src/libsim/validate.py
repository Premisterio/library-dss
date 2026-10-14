"""Planted vs recovered: measure the planted effects using only what the DSS can observe.

Each metric reads the dataset (and, where a true value exists, the ground truth). Tests assert
thresholds on these numbers; `libsim validate` prints them as a table for the thesis.
"""

import bisect
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

Dataset = dict[str, Any]


def rows(dataset: Dataset, table: str) -> list[dict[str, Any]]:
    data = dataset["tables"][table]
    return [dict(zip(data["columns"], row, strict=True)) for row in data["rows"]]


def spearman(a: Any, b: Any) -> float:
    x, y = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if x.size < 3 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return float("nan")  # undefined for constant or tiny samples
    ra, rb = np.argsort(np.argsort(x)), np.argsort(np.argsort(y))
    return float(np.corrcoef(ra, rb)[0, 1])


def _ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _decided(dataset: Dataset) -> list[dict[str, Any]]:
    return [
        p
        for p in rows(dataset, "subscription_periods")
        if p["plan"] != "trial" and p["outcome"] in ("renewed", "churned")
    ]


def churn_rates(dataset: Dataset) -> dict[str, float]:
    by_plan: dict[str, Counter] = defaultdict(Counter)
    for p in _decided(dataset):
        by_plan[p["plan"]][p["outcome"]] += 1
    return {
        plan: c["churned"] / (c["churned"] + c["renewed"]) for plan, c in sorted(by_plan.items())
    }


def inactivity_churn(dataset: Dataset, days: int = 14) -> dict[str, float]:
    sessions: dict[str, list[datetime]] = defaultdict(list)
    for s in rows(dataset, "reading_sessions"):
        sessions[s["user_id"]].append(_ts(s["started_at"]))
    for times in sessions.values():
        times.sort()
    churn = {"active": Counter(), "inactive": Counter()}
    for p in _decided(dataset):
        end, times = _ts(p["period_end"]), sessions.get(p["user_id"], [])
        i = bisect.bisect_right(times, end)
        active = i > 0 and times[i - 1] > end - timedelta(days=days)
        churn["active" if active else "inactive"][p["outcome"]] += 1
    return {k: c["churned"] / max(1, sum(c.values())) for k, c in churn.items()}


def campaign_effect(
    dataset: Dataset, truth: dict[str, Any], arm: str = "discount"
) -> dict[str, float]:
    """Difference in churn (arm − control) estimated from the randomized campaign vs the truth."""
    outcome = {(p["user_id"], p["period_end"]): p["outcome"] for p in _decided(dataset)}
    groups: dict[str, list[bool]] = defaultdict(list)
    for a in rows(dataset, "campaign_assignments"):
        result = outcome.get((a["user_id"], a["target_period_end"]))
        if result is not None:
            groups[a["arm"]].append(result == "churned")
    n1, n0 = len(groups[arm]), len(groups["control"])
    if not n1 or not n0:
        return {
            "estimate": float("nan"),
            "se": float("nan"),
            "true": float("nan"),
            "n_arm": n1,
            "n_control": n0,
        }
    p1, p0 = float(np.mean(groups[arm])), float(np.mean(groups["control"]))
    # Intention-to-treat truth: what members of this arm actually received (e-mail only reaches
    # opted-in members) versus no action, averaged over the arm.
    true = float(
        np.mean(
            [
                r["p_true"][r["received"]] - r["p_true"]["none"]
                for r in truth["campaign"]
                if r["arm"] == arm
            ]
        )
    )
    return {
        "estimate": p1 - p0,
        "se": float(np.sqrt(p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0)),
        "true": true,
        "n_arm": n1,
        "n_control": n0,
    }


def heterogeneity(truth: dict[str, Any]) -> dict[str, float]:
    if not truth["campaign"]:
        return {
            "email_backfires_share": float("nan"),
            "email_helps_share": float("nan"),
            "discount_tau_sd": float("nan"),
        }
    email = np.array([r["tau"]["email"] for r in truth["campaign"]])
    discount = np.array([r["tau"]["discount"] for r in truth["campaign"]])
    return {
        "email_backfires_share": float((email > 0).mean()),
        "email_helps_share": float((email < 0).mean()),
        "discount_tau_sd": float(discount.std()),
    }


def age_genre(dataset: Dataset) -> dict[str, float]:
    age = {u["user_id"]: u["age_range"] for u in rows(dataset, "users")}
    genre = {b["book_id"]: b["genre"] for b in rows(dataset, "books")}
    young, old = Counter(), Counter()
    for loan in rows(dataset, "loans"):
        group = age[loan["user_id"]]
        if group in ("16-17", "18-24"):
            young[genre[loan["book_id"]]] += 1
        elif group in ("55-64", "65+"):
            old[genre[loan["book_id"]]] += 1

    def share(c: Counter, g: str) -> float:
        return c[g] / max(1, sum(c.values()))

    return {
        f"{g}_{side}": share(c, g)
        for g in ("history", "young_adult", "fantasy", "biography")
        for side, c in (("young", young), ("old", old))
    }


def rating_quality(
    dataset: Dataset, truth: dict[str, Any], min_ratings: int = 10
) -> dict[str, float]:
    ratings: dict[str, list[int]] = defaultdict(list)
    for loan in rows(dataset, "loans"):
        if loan["rating"] is not None:
            ratings[loan["book_id"]].append(loan["rating"])
    rated = [b for b, r in ratings.items() if len(r) >= min_ratings]
    quality = [truth["books"]["quality"][b] for b in rated]
    return {
        "spearman": spearman([np.mean(ratings[b]) for b in rated], quality),
        "books": len(rated),
    }


def candidate_demand(dataset: Dataset, truth: dict[str, Any], days: int = 90) -> dict[str, float]:
    as_of = datetime.fromisoformat(dataset["meta"]["as_of"]).replace(tzinfo=UTC)
    counts = Counter(
        s["query"]
        for s in rows(dataset, "searches")
        if s["results_count"] == 0 and _ts(s["searched_at"]) > as_of - timedelta(days=days)
    )
    candidates = rows(dataset, "candidate_titles")
    observed = [counts[c["title"]] + counts[c["authors"].split(", ")[0]] for c in candidates]
    demand = [
        truth["candidates"][c["candidate_id"]]["demand_last_90d_per_month"] for c in candidates
    ]
    return {"spearman": spearman(observed, demand), "candidates": len(candidates)}


def rhythm(dataset: Dataset, timezone: str = "Europe/Kyiv") -> dict[str, float]:
    tz = ZoneInfo(timezone)
    local = [_ts(s["started_at"]).astimezone(tz) for s in rows(dataset, "reading_sessions")]
    if not local:
        return {
            "weekend_to_workday": float("nan"),
            "evening_share_19_23": float("nan"),
            "night_share_2_5": float("nan"),
        }
    weekday = Counter(t.weekday() for t in local)
    per_weekend = (weekday[5] + weekday[6]) / 2
    per_workday = sum(weekday[d] for d in range(5)) / 5
    return {
        "weekend_to_workday": per_weekend / per_workday,
        "evening_share_19_23": sum(1 for t in local if 19 <= t.hour <= 23) / len(local),
        "night_share_2_5": sum(1 for t in local if 2 <= t.hour <= 5) / len(local),
    }


def report(dataset: Dataset, truth: dict[str, Any]) -> dict[str, dict[str, float]]:
    return {
        "churn_rates": churn_rates(dataset),
        "inactivity_churn": inactivity_churn(dataset),
        "campaign_discount": campaign_effect(dataset, truth, "discount"),
        "campaign_email": campaign_effect(dataset, truth, "email"),
        "heterogeneity": heterogeneity(truth),
        "age_genre": age_genre(dataset),
        "rating_quality": rating_quality(dataset, truth),
        "candidate_demand": candidate_demand(dataset, truth),
        "rhythm": rhythm(dataset),
    }


def markdown(rep: dict[str, dict[str, float]]) -> str:
    lines = ["| Перевірка | Показник | Значення |", "| --- | --- | --- |"]
    for section, values in rep.items():
        for key, value in values.items():
            shown = f"{value:.4f}" if isinstance(value, float) else str(value)
            lines.append(f"| {section} | {key} | {shown} |")
    return "\n".join(lines)
