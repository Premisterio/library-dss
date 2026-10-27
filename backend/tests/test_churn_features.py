"""Churn target and features: exact values on a hand-made file, no leakage on a simulated one.

The expected values below are derived by hand from `churn_document` (as of 2026-06-30 in Kyiv,
UTC+3 all summer). Its cutoff k = 0 is the end of 2026-05-31, 2026-05-31T21:00Z: the last 7
days start 05-24T21:00Z, 14 days 05-17T21:00Z, 30 days 05-01T21:00Z, the 30 days before those
04-01T21:00Z, 90 days 03-02T21:00Z; the risk window ends 2026-06-30T21:00Z.
"""

import itertools
import math
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import orjson
import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from polars.testing import assert_frame_equal

from app.domain.analytics.common import Context, Frames
from app.domain.churn import EXAMPLES_SCHEMA, examples
from app.domain.churn.features import FEATURES, SCHEMA, build_features
from app.domain.churn.target import at_risk, history_cutoffs, horizon_end, labels
from app.domain.enums import ENUMS
from app.ingest import reader
from app.ingest.frames import ParsedDataset
from app.ingest.schema import TABLES
from app.utils.dates import end_of_day_utc, parse_utc

TIMEZONE = "Europe/Kyiv"
CUTOFF = Context.at(date(2026, 5, 31), TIMEZONE)

# A member with no activity before the cutoff: counts are 0, undefined values are missing.
QUIET: dict[str, Any] = {
    "discount": 0.0,
    "sessions_7d": 0.0,
    "sessions_30d": 0.0,
    "reading_minutes_30d": 0.0,
    "sessions_trend": 0.0,
    "days_since_last_session": None,
    "inactive_14d": True,
    "active_days_30d": 0.0,
    "loans_30d": 0.0,
    "open_loans": 0.0,
    "searches_30d": 0.0,
    "completed_90d": 0.0,
    "completion_rate_90d": None,
    "avg_rating_90d": None,
    "low_ratings_90d": 0.0,
    "lapsed_holds_30d": 0.0,
    "open_holds": 0.0,
    "zero_result_searches_30d": 0.0,
}


@pytest.fixture
def churn(churn_document: dict[str, Any]) -> ParsedDataset:
    return reader.parse(reader.decode(orjson.dumps(churn_document)))


def test_features_by_hand(churn: ParsedDataset) -> None:
    features = build_features(churn.frames, CUTOFF)
    assert dict(features.schema) == SCHEMA
    assert features.rows_by_key("user_id", named=True, unique=True) == {
        "u1": pytest.approx(
            {
                "plan": "monthly",
                "monthly_price": 119.2,  # the running period is discounted
                "discount": 0.2,
                "tenure_days": 89,  # paying since 03-03T21:00Z
                "days_to_renewal": 1,  # the period ends 06-01T21:00Z
                "sessions_7d": 1,  # 05-30; the session at the cutoff and the one on 06-05 are later
                "sessions_30d": 3,  # 05-10, 05-20, 05-30
                "reading_minutes_30d": 50 + 40 + 30,
                "sessions_trend": math.log((1 + 3) / (1 + 1)),  # one session on 04-20 before
                "days_since_last_session": 1.125,  # 05-30T18:00Z
                "inactive_14d": False,
                # Kyiv days 05-05, 05-10, 05-15, 05-20, 05-25, 05-30 (the search at 05-29T22:00Z
                # is 05-30 in Kyiv, the day of a session)
                "active_days_30d": 6,
                "loans_30d": 2,  # l2, l3
                "open_loans": 1,  # l3 comes back on 06-08, after the cutoff
                "searches_30d": 2,  # the search at the cutoff is later
                "completed_90d": 1,  # l1; l3's completion is not known yet
                "completion_rate_90d": 0.5,  # l1 of l1, l2
                "avg_rating_90d": 3.5,  # 5 and 2
                "low_ratings_90d": 1,
                "lapsed_holds_30d": 1,  # h1 lapsed on 05-11
                "open_holds": 1,  # h2 is served on 06-10
                "zero_result_searches_30d": 1,
                "age_range": "25-34",
                "education": "master",
                "language_pref": "uk+en",
                "email_opt_in": True,
            }
        ),
        "u2": pytest.approx(
            {
                **QUIET,
                "plan": "student",
                "monthly_price": 79,
                "tenure_days": 23,  # the trial does not count
                "days_to_renewal": 7,
                "open_holds": 1,  # h3 lapses on 06-01, after the cutoff
                "age_range": "18-24",
                "education": "student",
                "language_pref": "uk",
                "email_opt_in": False,
            }
        ),
        "u4": pytest.approx(
            {
                **QUIET,
                "plan": "monthly",
                "monthly_price": 149,
                "tenure_days": 21,
                "days_to_renewal": 9,
                "age_range": "35-44",
                "education": "phd",
                "language_pref": "uk+en",
                "email_opt_in": True,
            }
        ),
        "u5": pytest.approx(
            {
                **QUIET,
                "plan": "monthly",
                "monthly_price": 149,
                "tenure_days": 19,
                "days_to_renewal": 11,
                "age_range": "55-64",
                "education": "secondary",
                "language_pref": "uk",
                "email_opt_in": False,
            }
        ),
    }


def test_scoring_scores_the_members_renewing_next(churn: ParsedDataset) -> None:
    """At as_of: u1, u4 and u6 renew in July; u2 and u5 churned, u3 renews next year."""
    scoring = Context.at(churn.as_of, churn.timezone)
    assert build_features(churn.frames, scoring)["user_id"].to_list() == ["u1", "u4", "u6"]
    assert labels(churn.frames, scoring).is_empty()  # nothing has ended yet


def test_risk_group_is_who_the_simulator_renews_next(
    tabular_dataset: ParsedDataset, tabular_truth: dict[str, Any]
) -> None:
    """At as_of, the risk group is the members libsim renews in the next 30 days."""
    scoring = Context.at(tabular_dataset.as_of, tabular_dataset.timezone)
    risk = at_risk(tabular_dataset.frames, scoring)["user_id"].to_list()
    assert risk == sorted(row["user_id"] for row in tabular_truth["at_risk"])


def test_labels_are_churn_without_an_action(churn: ParsedDataset) -> None:
    """u4's renewal got a campaign discount; u5 was in the e-mail arm but got nothing."""
    assert labels(churn.frames, CUTOFF).rows() == [("u1", False), ("u2", True), ("u5", True)]


def periods(*rows: tuple[str, str, str, str]) -> Frames:
    columns = [col for col, _, _ in TABLES["subscription_periods"]]
    frame = pl.DataFrame(
        [[user, plan, start, end, 149.0, 149.0, None, "open"] for user, plan, start, end in rows],
        schema=columns,
        orient="row",
    )
    return {
        "subscription_periods": frame.with_columns(
            parse_utc("period_start"), parse_utc("period_end")
        )
    }


def test_risk_window_boundaries() -> None:
    frames = periods(
        ("ended", "monthly", "2026-05-01T21:00:00Z", "2026-05-31T20:59:59Z"),
        ("at_cutoff", "monthly", "2026-05-01T21:00:00Z", "2026-05-31T21:00:00Z"),
        ("last_moment", "monthly", "2026-05-31T20:59:59Z", "2026-06-30T20:59:59Z"),
        ("after_window", "monthly", "2026-05-31T20:00:00Z", "2026-06-30T21:00:00Z"),
        ("starts_later", "monthly", "2026-05-31T21:00:00Z", "2026-06-10T21:00:00Z"),
        ("trial", "trial", "2026-05-20T21:00:00Z", "2026-06-03T21:00:00Z"),
        ("overlap", "monthly", "2026-04-20T21:00:00Z", "2026-06-20T21:00:00Z"),
        ("overlap", "annual", "2026-05-10T21:00:00Z", "2026-06-05T21:00:00Z"),
    )
    risk = at_risk(frames, CUTOFF)
    assert risk.select("user_id", "plan").rows() == [
        ("at_cutoff", "monthly"),
        ("last_moment", "monthly"),
        ("overlap", "annual"),  # the period that started last
    ]


def test_history_cutoffs_tile_the_past(churn: ParsedDataset) -> None:
    cutoffs = history_cutoffs(churn.frames, churn.as_of, churn.timezone)
    # back to the first paid period, u3's of 2026-01-10
    assert [cutoff.as_of for cutoff in cutoffs] == [
        date(2026, 5, 31),
        date(2026, 5, 1),
        date(2026, 4, 1),
        date(2026, 3, 2),
        date(2026, 1, 31),
    ]
    assert horizon_end(cutoffs[0]) == end_of_day_utc(churn.as_of, churn.timezone)
    assert all(horizon_end(older) == newer.end for newer, older in itertools.pairwise(cutoffs))


def test_examples_of_every_cutoff(churn: ParsedDataset) -> None:
    rows = examples(churn.frames, churn.as_of, churn.timezone)
    assert dict(rows.schema) == EXAMPLES_SCHEMA
    assert rows.select("k", "user_id", "churned").rows() == [
        (0, "u1", False),
        (0, "u2", True),
        (0, "u5", True),
        (1, "u1", False),
        (2, "u1", False),
    ]
    # u1's features are computed at each cutoff: paying since 03-03T21:00Z
    assert rows["tenure_days"].to_list() == [89, 23, 19, 59, 29]


def test_no_paid_periods_no_examples(churn: ParsedDataset) -> None:
    frames = {**churn.frames}
    frames["subscription_periods"] = frames["subscription_periods"].filter(
        pl.col("plan") == "trial"
    )
    assert history_cutoffs(frames, churn.as_of, churn.timezone) == []
    assert dict(examples(frames, churn.as_of, churn.timezone).schema) == EXAMPLES_SCHEMA


def test_every_feature_is_described() -> None:
    keys = [feature.key for feature in FEATURES]
    assert len(set(keys)) == len(keys)
    assert set(ENUMS["churn_feature"]) == set(keys)
    for feature in FEATURES:
        assert (feature.enum is not None) == (feature.kind == "category"), feature
        assert feature.enum is None or feature.enum in ENUMS, feature
        assert feature.unit is None or (feature.kind == "number" and feature.unit in ENUMS["unit"])


# When each row happened: rows from after a moment are history that was not known then.
HAPPENED_AT = {
    "subscription_periods": "period_start",
    "loans": "borrowed_at",
    "reading_sessions": "started_at",
    "searches": "searched_at",
    "holds": "placed_at",
    "campaign_assignments": "assigned_at",
}
HORIZON_SECONDS = 60 * 86400


def rewrite_after(
    frames: Frames, at: datetime, rng: np.random.Generator
) -> dict[str, pl.DataFrame]:
    """Another history after `at`: later rows dropped or invented, later outcomes redrawn."""

    def later(n: int) -> pl.Expr:
        """A moment in the 60 days after `at`, or never."""
        seconds = pl.lit(pl.Series(rng.integers(0, HORIZON_SECONDS, n)))
        happened = pl.lit(pl.Series(rng.random(n) < 0.8))
        return pl.when(happened).then(pl.lit(at) + pl.duration(seconds=seconds))

    def drawn(values: list[Any], n: int) -> pl.Expr:
        return pl.lit(pl.Series([values[i] for i in rng.integers(0, len(values), n)]))

    def redraw(table: str, began: str, resolved: str, values: dict[str, pl.Expr]) -> None:
        """New values for what began before `at` and was not resolved by then."""
        unresolved = (pl.col(began) < at) & ~(pl.col(resolved) < at).fill_null(False)
        rewritten[table] = rewritten[table].with_columns(
            pl.when(unresolved).then(value).otherwise(column).alias(column)
            for column, value in values.items()
        )

    rewritten = dict(frames)
    for table, column in HAPPENED_AT.items():
        frame = frames[table]
        before, after = frame.filter(pl.col(column) < at), frame.filter(pl.col(column) >= at)
        kept = after.filter(pl.Series(rng.random(after.height) < 0.5))
        invented = before.sample(min(before.height, 30), seed=int(rng.integers(2**32)))
        moved = later(invented.height).fill_null(pl.lit(at))  # at the moment itself counts too
        rewritten[table] = pl.concat([before, kept, invented.with_columns(moved.alias(column))])

    n = rewritten["loans"].height
    redraw(
        "loans",
        "borrowed_at",
        "returned_at",
        {
            "returned_at": later(n),
            "completed": drawn([True, False, None], n),
            "rating": drawn([1, 2, 3, 4, 5, None], n),
        },
    )
    n = rewritten["holds"].height
    redraw(
        "holds",
        "placed_at",
        "resolved_at",
        {"resolved_at": later(n), "outcome": drawn(list(ENUMS["hold_outcome"]), n)},
    )
    n = rewritten["subscription_periods"].height  # a period's end is set when it starts
    redraw(
        "subscription_periods",
        "period_start",
        "period_end",
        {"outcome": drawn(list(ENUMS["period_outcome"]), n)},
    )
    return rewritten


@settings(max_examples=60, deadline=None)
@given(days_back=st.integers(0, 220), seed=st.integers(0, 2**32 - 1))
def test_history_after_the_cutoff_changes_no_feature(
    tabular_dataset: ParsedDataset, days_back: int, seed: int
) -> None:
    frames = tabular_dataset.frames
    cutoff = Context.at(tabular_dataset.as_of - timedelta(days=days_back), tabular_dataset.timezone)
    rewritten = rewrite_after(frames, cutoff.end, np.random.default_rng(seed))
    assert any(not rewritten[name].equals(frames[name]) for name in HAPPENED_AT)
    assert_frame_equal(build_features(rewritten, cutoff), build_features(frames, cutoff))
