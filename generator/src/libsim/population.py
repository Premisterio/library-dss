"""Library members: observable profile plus hidden traits that drive behaviour.

Observable (written to the dataset): registration date, age range, education, language
preference, e-mail opt-in, declared interests. Hidden (ground truth only): genre taste vector,
reading rate, baseline satisfaction, price sensitivity and the "misspecified" hidden factor.
"""

from dataclasses import dataclass

import numpy as np

from libsim.params import AGE_GENRE_TILT, AGE_RANGES, AGE_WEIGHTS, DEVICE_WEIGHTS, EDUCATION, Params
from libsim.world import GENRE_CODES

# Genres missing from goodbooks-10k's base share get a small floor.
GENRE_FLOOR = 0.01
EDUCATION_BY_AGE = {
    "16-17": [0.9, 0.1, 0.0, 0.0, 0.0],
    "18-24": [0.2, 0.55, 0.2, 0.05, 0.0],
}
EDUCATION_ADULT = [0.25, 0.03, 0.4, 0.27, 0.05]


@dataclass
class Population:
    n: int
    registered_day: np.ndarray
    age: np.ndarray  # index into AGE_RANGES
    education: np.ndarray  # index into EDUCATION
    uk_only: np.ndarray
    email_opt_in: np.ndarray
    taste: np.ndarray  # (n, genres) — hidden
    interests: np.ndarray  # (n, 3) declared top genres (observable, noisy)
    reading_rate: np.ndarray  # books/day when fully engaged — hidden
    session_rate: np.ndarray  # reading sessions/day while holding a loan — hidden
    speed: np.ndarray  # pages per minute — hidden
    device: np.ndarray  # preferred device index
    chronotype: np.ndarray  # 0 morning, 1 evening, 2 night owl
    baseline_s: np.ndarray  # satisfaction set point — hidden
    price_sensitivity: np.ndarray  # in (0, 1) — hidden
    hidden_factor: np.ndarray  # unobserved churn driver ("misspecified") — hidden
    starts_trial: np.ndarray  # bool: trial (else free tier) at registration


def base_genre_share(calibration: dict) -> np.ndarray:
    share = calibration["genre_taste"]["genre_base_share"]
    base = np.array([max(share.get(g, 0.0), GENRE_FLOOR) for g in GENRE_CODES])
    return base / base.sum()


def make_population(
    params: Params, total_days: int, calibration: dict, rng: np.random.Generator
) -> Population:
    n = params.users
    age = rng.choice(len(AGE_RANGES), size=n, p=AGE_WEIGHTS)
    education = np.array(
        [
            rng.choice(len(EDUCATION), p=EDUCATION_BY_AGE.get(AGE_RANGES[a], EDUCATION_ADULT))
            for a in age
        ]
    )

    # Registrations: an initial cohort plus arrivals with an exponential growth trend.
    initial = rng.random(n) < params.initial_share
    g = np.log1p(params.growth_per_year) / 365.0
    u = rng.random(n)
    arrival = np.log1p(u * np.expm1(g * total_days)) / g  # inverse CDF of intensity ∝ exp(g t)
    registered_day = np.where(initial, 0, np.floor(arrival)).astype(int)

    base = base_genre_share(calibration)
    taste = np.empty((n, len(GENRE_CODES)))
    for i, a in enumerate(age):
        tilt = AGE_GENRE_TILT[AGE_RANGES[a]]
        mean = base * np.array([tilt.get(code, 1.0) for code in GENRE_CODES])
        taste[i] = rng.dirichlet(params.taste_concentration * mean / mean.sum())
    # Declared interests: the top-3 taste genres, each replaced by a random one 25% of the time.
    top3 = np.argsort(-taste, axis=1)[:, :3]
    noise = rng.random(top3.shape) < 0.25
    interests = np.where(noise, rng.integers(0, len(GENRE_CODES), top3.shape), top3)

    young = age <= AGE_RANGES.index("18-24")
    student = education == EDUCATION.index("student")
    ps_logit = -0.6 + 1.3 * student + 0.6 * young - 0.4 * (education >= 3) + rng.normal(0, 0.6, n)

    return Population(
        n=n,
        registered_day=registered_day,
        age=age,
        education=education,
        uk_only=rng.random(n) < params.uk_only_share,
        email_opt_in=rng.random(n) < params.email_opt_in,
        taste=taste,
        interests=interests,
        reading_rate=rng.lognormal(
            np.log(params.reading_rate_median / 30.0), params.reading_rate_sigma, n
        ),
        session_rate=rng.lognormal(np.log(params.session_rate_median), 0.35, n),
        speed=rng.lognormal(np.log(params.reading_speed_median), 0.25, n),
        device=rng.choice(len(DEVICE_WEIGHTS), size=n, p=DEVICE_WEIGHTS),
        chronotype=rng.choice(3, size=n, p=[0.3, 0.55, 0.15]),
        baseline_s=rng.normal(0.0, params.s_baseline_sd, n),
        price_sensitivity=1.0 / (1.0 + np.exp(-ps_logit)),
        hidden_factor=rng.normal(0.0, 1.0, n),
        starts_trial=rng.random(n) < params.trial_share,
    )
