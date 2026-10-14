"""Simulation parameters: every planted effect lives here and is copied into ground truth.

Defaults describe a Ukrainian online library (prices in UAH). Presets reshape the planted
structure for the thesis experiments (weak signal, no heterogeneity, misspecification,
licence scarcity). Values that come from real data are marked with their source.
"""

from dataclasses import asdict, dataclass, field, replace
from datetime import date
from typing import Any

PLANS: dict[str, dict[str, Any]] = {
    # code: price per period (UAH), period length (days)
    "monthly": {"price": 149.0, "days": 30},
    "annual": {"price": 1290.0, "days": 365},
    "student": {"price": 79.0, "days": 30},
}
AGE_RANGES = ["16-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
AGE_WEIGHTS = [0.06, 0.2, 0.26, 0.2, 0.13, 0.09, 0.06]
EDUCATION = ["secondary", "student", "bachelor", "master", "phd"]
DEVICES = ["mobile_android", "mobile_ios", "desktop", "tablet", "e_reader"]
DEVICE_WEIGHTS = [0.42, 0.18, 0.2, 0.12, 0.08]

# Planted taste structure: genre-share multipliers by age group (applied to the goodbooks base).
AGE_GENRE_TILT: dict[str, dict[str, float]] = {
    "16-17": {"young_adult": 3.0, "fantasy": 1.6, "children": 1.5, "romance": 1.3, "business": 0.3},
    "18-24": {"young_adult": 2.0, "fantasy": 1.5, "science_fiction": 1.3, "self_help": 1.2},
    "25-34": {"self_help": 1.4, "business": 1.5, "technology": 1.5, "mystery_thriller": 1.1},
    "35-44": {"business": 1.4, "history": 1.3, "mystery_thriller": 1.2, "children": 1.6},
    "45-54": {"history": 1.6, "biography": 1.5, "mystery_thriller": 1.2, "young_adult": 0.4},
    "55-64": {"history": 1.9, "biography": 1.7, "classics": 1.5, "young_adult": 0.3},
    "65+": {
        "history": 2.0,
        "biography": 1.8,
        "classics": 1.8,
        "poetry_drama": 1.5,
        "young_adult": 0.2,
    },
}


@dataclass(frozen=True)
class ChurnParams:
    """logit P(churn at renewal) — churn happens only when a paid period ends."""

    intercept: dict[str, float] = field(
        default_factory=lambda: {"monthly": -2.25, "annual": -0.75, "student": -2.1}
    )
    satisfaction: float = -1.2  # per unit of hidden satisfaction s
    frustrations_30d: float = 0.25  # per lapsed hold / zero-result search in the last 30 days
    log_tenure_months: float = -0.3
    inactivity_14d: float = 0.6  # no reading session in the last 14 days
    hidden_factor: float = 0.0  # "misspecified" preset: unobserved driver


@dataclass(frozen=True)
class TreatmentParams:
    """Heterogeneous action effects on the churn logit (negative = fewer churns)."""

    discount_pct: float = 0.2
    discount_kappa: float = -1.3  # times price sensitivity, for users that are not lost causes
    lost_cause_satisfaction: float = -1.0  # below this s a discount does nothing
    email_declining: float = -0.5  # opted-in users whose engagement is falling
    email_dormant: float = 0.25  # "sleeping dogs": reminding dormant users makes them cancel
    email_other: float = -0.05
    email_cost: float = 2.0  # UAH per email
    heterogeneous: bool = True  # False: every user gets the average effect


@dataclass(frozen=True)
class CampaignParams:
    """A past randomized retention campaign (gives data to estimate uplift)."""

    months: int = 4
    ends_months_before_as_of: int = 3
    arms: dict[str, float] = field(
        default_factory=lambda: {"control": 0.4, "email": 0.3, "discount": 0.3}
    )


@dataclass(frozen=True)
class Params:
    seed: int = 1
    preset: str = "demo"
    users: int = 5000
    months: int = 24
    as_of: date = date(2026, 9, 30)
    horizon_days: int = 30  # ground-truth outcome window after as_of
    timezone: str = "Europe/Kyiv"

    # population
    initial_share: float = 0.35  # members already registered at the start
    growth_per_year: float = 0.25  # registrations trend
    trial_share: float = 0.55  # new members starting a 14-day trial (others: free tier)
    trial_days: int = 14
    email_opt_in: float = 0.7
    uk_only_share: float = 0.5  # read Ukrainian books only
    taste_concentration: float = 11.4  # goodbooks-10k calibration (Dirichlet)
    reading_rate_median: float = 1.1  # books per month for an engaged member
    reading_rate_sigma: float = 0.6  # wider than goodbooks (that one keeps active raters only)
    session_rate_median: float = 0.75  # reading sessions per day while holding a loan
    session_minutes_median: float = 40.0
    reading_speed_median: float = 0.9  # pages per minute
    trial_conversion_intercept: float = -0.8

    # satisfaction s_t: AR(1) towards a personal baseline, with event shocks
    s_persistence: float = 0.985
    s_noise: float = 0.04
    s_baseline_sd: float = 0.35
    shock_good_read: float = 0.18
    shock_bad_read: float = -0.12
    shock_hold_lapsed: float = -0.3
    shock_zero_result: float = -0.12
    activity_gamma: float = 0.9  # activity multiplier exp(gamma * s)

    # catalogue and licences
    held_out_titles: int = 300  # catalogue titles the library does not have
    candidates: int = 60  # of those, offered by a distributor (content DSS alternatives)
    copies_scale: float = 1.0  # "high-scarcity" preset halves it
    under_licensed_share: float = 0.2
    loan_days: int = 21
    hold_days: int = 21
    hold_choice: tuple[float, float, float] = (0.6, 0.3, 0.1)  # hold / substitute / give up
    search_missing_prob: float = 0.75  # a wanted-but-missing title leads to a zero-result search

    churn: ChurnParams = field(default_factory=ChurnParams)
    treatment: TreatmentParams = field(default_factory=TreatmentParams)
    campaign: CampaignParams = field(default_factory=CampaignParams)
    effect_scale: float = 1.0  # "weak-signal" preset shrinks planted effects

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["as_of"] = self.as_of.isoformat()
        return data


def preset(name: str, **overrides: Any) -> Params:
    """Named configurations used by the experiment harness."""
    base = Params(preset=name)
    match name:
        case "demo":
            params = base
        case "weak-signal":
            params = replace(base, effect_scale=0.5, s_noise=0.07)
        case "no-heterogeneity":
            params = replace(base, treatment=replace(base.treatment, heterogeneous=False))
        case "misspecified":
            params = replace(base, churn=replace(base.churn, hidden_factor=1.0))
        case "high-scarcity":
            params = replace(base, copies_scale=0.5, under_licensed_share=0.4)
        case _:
            raise ValueError(f"unknown preset {name!r}; choose from {PRESETS}")
    return replace(params, **overrides)


PRESETS = ("demo", "weak-signal", "no-heterogeneity", "misspecified", "high-scarcity")
