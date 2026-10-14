"""Descriptive analytics: exact numbers on hand-made files, contract checks on a simulated one.

The expected values below are computed by hand from the `mini_document` fixture (as of
2026-03-31 in Kyiv: the window "last 30 days" starts 2026-03-01T21:00Z, "last 90 days"
starts 2025-12-31T21:00Z).
"""

import math
from typing import Any

import orjson
import pytest

from app.domain.analytics import SECTIONS, compute_all
from app.domain.analytics.model import Section
from app.domain.enums import ENUMS
from app.ingest import reader


def analyse(document: dict[str, Any]) -> dict[str, Section]:
    parsed = reader.parse(reader.decode(orjson.dumps(document)))
    return compute_all(parsed.frames, parsed.as_of, parsed.timezone)


def kpis(section: Section) -> dict[str, float | None]:
    return {kpi.key: kpi.value for kpi in section.kpis}


def chart(section: Section, key: str) -> list[dict[str, Any]]:
    return next(c.rows for c in section.charts if c.key == key)


@pytest.fixture
def mini(mini_document: dict[str, Any]) -> dict[str, Section]:
    return analyse(mini_document)


def test_overview_numbers(mini: dict[str, Section]) -> None:
    assert kpis(mini["overview"]) == {
        "members": 5,
        "active_members": 4,  # u5 never did anything
        "paying_subscribers": 2,  # u1 (monthly) and u3 (annual); u2 churned, u4 is on trial
        "mrr": pytest.approx(119.2 + 1290 / 12),  # discounted monthly + annual / 12
        "churn_rate": 0.5,  # u1 renewed on 03-06, u2 churned on 03-12
        "loans": 4,
        "reading_minutes": 225,
    }
    assert mini["overview"].notes == []


def test_usage_numbers(mini: dict[str, Section]) -> None:
    usage = mini["usage"]
    assert kpis(usage) == {
        "sessions": 5,
        "reading_minutes": 225,
        "avg_session_minutes": 45,
        "minutes_per_active_member": 225 / 4,
    }
    busy = {
        (row["weekday"], row["hour"]): row["sessions"]
        for row in chart(usage, "reading_heatmap")
        if row["sessions"]
    }
    # Local Kyiv time; 2026-03-30 is already summer time (UTC+3).
    assert busy == {
        ("tue", 19): 1,
        ("wed", 19): 1,
        ("sat", 8): 1,
        ("sun", 21): 1,
        ("sun", 14): 1,
        ("mon", 9): 1,
    }
    assert len(chart(usage, "reading_heatmap")) == 7 * 24
    # Audit 2026-10-08: recency is counted back from as_of, not from today.
    recency = {row["recency"]: row["members"] for row in chart(usage, "recency")}
    assert recency == {
        "days_0_7": 1,
        "days_8_30": 3,
        "days_31_90": 0,
        "days_91_plus": 0,
        "never": 1,
    }


def test_content_numbers(mini: dict[str, Section]) -> None:
    content = mini["content"]
    assert kpis(content) == {
        "titles_in_catalog": 4,
        "titles_borrowed": 3,
        "loans": 6,
        "completion_rate": 0.75,
        "avg_rating": 4.0,
        "holds": 3,
        "avg_hold_wait_days": 15.0,
        "hold_lapse_rate": 0.5,
    }
    assert chart(content, "genres")[:3] == [
        {
            "genre": "poetry_drama",
            "loans": 2,
            "readers": 2,
            "avg_rating": 4.5,
            "completion_rate": 1.0,
            "holds": 0,
            "copies": 3,
            "holds_per_copy": 0.0,
        },
        {
            "genre": "science_fiction",
            "loans": 2,
            "readers": 2,
            "avg_rating": 3.0,
            "completion_rate": 0.0,
            "holds": 2,
            "copies": 1,
            "holds_per_copy": 2.0,
        },
        {
            "genre": "mystery_thriller",
            "loans": 1,
            "readers": 1,
            "avg_rating": None,  # unknown, not 0
            "completion_rate": None,
            "holds": 1,
            "copies": 1,
            "holds_per_copy": 1.0,
        },
    ]
    assert [row["title"] for row in chart(content, "top_titles")] == ["Dune", "Кобзар", "Тигролови"]
    # Audit 2026-10-08: the earlier "top books" table invented authors, genres and downloads.
    assert chart(content, "top_titles")[2] == {
        "title": "Тигролови",
        "authors": "Іван Багряний",
        "genre": "mystery_thriller",
        "loans": 1,
        "readers": 1,
        "avg_rating": None,
        "completion_rate": None,
    }
    assert chart(content, "queues")[0] == {
        "title": "Dune",
        "authors": "Frank Herbert",
        "genre": "science_fiction",
        "holds": 2,
        "copies": 1,
        "holds_per_copy": 2.0,
        "avg_hold_wait_days": None,
        "hold_lapse_rate": 1.0,
    }


def test_segments_numbers(mini: dict[str, Section]) -> None:
    age_genre = {
        (row["age_range"], row["genre"]): row["share"]
        for row in chart(mini["segments"], "age_genre")
    }
    assert age_genre == {
        ("18-24", "science_fiction"): 1.0,
        ("25-34", "poetry_drama"): pytest.approx(2 / 3, abs=1e-4),
        ("25-34", "science_fiction"): pytest.approx(1 / 3, abs=1e-4),
        ("35-44", "mystery_thriller"): 0.5,
        ("35-44", "poetry_drama"): 0.5,
    }
    by_age = {row["age_range"]: row for row in chart(mini["segments"], "members_by_age")}
    assert list(by_age) == ["18-24", "25-34", "35-44", "65+"]  # enum order
    assert by_age["25-34"] == {
        "age_range": "25-34",
        "members": 2,
        "active_members": 2,
        "paying_subscribers": 1,
    }


def test_search_numbers(mini: dict[str, Section]) -> None:
    search = mini["search"]
    assert kpis(search) == {
        "searches": 3,
        "searchers": 3,
        "zero_result_share": pytest.approx(2 / 3),
    }
    assert chart(search, "top_queries") == [
        {"query": "Дюна", "searches": 2, "searchers": 2, "zero_result_share": 1.0},
        {"query": "Багряний", "searches": 1, "searchers": 1, "zero_result_share": 0.0},
        {"query": "Кобзар", "searches": 1, "searchers": 1, "zero_result_share": 0.0},
    ]
    assert chart(search, "zero_result_queries") == [
        {"query": "Дюна", "searches": 2, "searchers": 2}
    ]


def test_subscriptions_numbers(mini: dict[str, Section]) -> None:
    subscriptions = mini["subscriptions"]
    assert kpis(subscriptions) == {
        "paying_subscribers": 2,
        "mrr": pytest.approx(226.7),
        "churn_rate": 0.5,
        "trial_conversion_rate": 1.0,  # u3 converted; u4 still on trial; u5 is too old
        "discounted_share": 0.5,
    }
    assert chart(subscriptions, "plans") == [
        {"plan": "monthly", "paying_subscribers": 1, "mrr": 119.2},
        {"plan": "annual", "paying_subscribers": 1, "mrr": 107.5},
    ]
    january = [r for r in chart(subscriptions, "subscribers_monthly") if r["month"] == "2026-01-01"]
    assert january == [
        {"month": "2026-01-01", "plan": "monthly", "paying_subscribers": 1, "mrr": 149.0},
        {"month": "2026-01-01", "plan": "annual", "paying_subscribers": 1, "mrr": 107.5},
    ]
    assert chart(subscriptions, "churn_monthly") == [
        {"month": "2026-02-01", "plan": "monthly", "renewals": 1, "churned": 0, "churn_rate": 0.0},
        {"month": "2026-03-01", "plan": "monthly", "renewals": 1, "churned": 0, "churn_rate": 0.0},
        # 2026-03-12T22:00Z is already March 13 in Kyiv
        {"month": "2026-03-01", "plan": "student", "renewals": 0, "churned": 1, "churn_rate": 1.0},
    ]


def test_cohort_numbers(mini: dict[str, Section]) -> None:
    rows = chart(mini["cohorts"], "activity_retention")
    october = [r for r in rows if r["cohort"] == "2025-10-01"]
    assert [r["month_offset"] for r in october] == [0, 1, 2, 3, 4, 5]  # up to March 2026
    assert [r["active_members"] for r in october] == [0, 0, 0, 0, 0, 1]
    assert october[5] == {
        "cohort": "2025-10-01",
        "month_offset": 5,
        "members": 2,
        "active_members": 1,
        "retention": 0.5,
    }
    march = [r for r in rows if r["cohort"] == "2026-03-01"]
    assert march == [
        {
            "cohort": "2026-03-01",
            "month_offset": 0,
            "members": 1,
            "active_members": 1,
            "retention": 1.0,
        }
    ]


def test_nested_dataset_explains_what_is_missing(nested_document: dict[str, Any]) -> None:
    sections = analyse(nested_document)
    overview = kpis(sections["overview"])
    assert overview["members"] == 3
    assert overview["churn_rate"] is None  # no renewal outcomes: unknown, not 0
    content = kpis(sections["content"])
    # Audit 2026-10-08: every loan and distinct title counts, not a top 10.
    assert content["loans"] == 6
    assert content["titles_borrowed"] == 4
    assert content["holds"] is None
    assert {c.key for c in sections["content"].charts} == {"genres", "top_titles"}
    assert kpis(sections["search"])["zero_result_share"] is None
    notes = {note.code for section in sections.values() for note in section.notes}
    assert notes == {
        "subscriptions.no_outcomes",
        "content.no_licences",
        "search.no_result_counts",
    }


@pytest.fixture(scope="module")
def simulated() -> dict[str, Section]:
    from libsim import engine, writer
    from libsim.params import preset

    return analyse(writer.build_dataset(engine.simulate(preset("demo", users=300, months=12))))


def _values(section: Section) -> list[Any]:
    values: list[Any] = [kpi.value for kpi in section.kpis]
    for c in section.charts:
        values += [v for row in c.rows for v in row.values()]
    return values


def test_every_section_is_json_without_nan(simulated: dict[str, Section]) -> None:
    assert list(simulated) == list(SECTIONS)
    for section in simulated.values():
        orjson.dumps(section.to_dict())  # raises on unsupported types
        floats = [v for v in _values(section) if isinstance(v, float)]
        assert all(math.isfinite(v) for v in floats), section.key


def test_every_code_has_a_ukrainian_label(simulated: dict[str, Section]) -> None:
    """Clients label everything from GET /meta/enums, so every code must be there."""
    for section in simulated.values():
        assert section.key in ENUMS["analytics_section"]
        for kpi in section.kpis:
            assert kpi.key in ENUMS["metric"], kpi.key
            assert kpi.unit in ENUMS["unit"]
        for c in section.charts:
            assert c.key in ENUMS["chart"], c.key
            for measure in c.measures:
                assert measure.key in ENUMS["metric"], measure.key
                assert measure.unit in ENUMS["unit"]
            for dimension in (*c.dimensions, *c.attributes):
                assert dimension.key in ENUMS["dimension"], dimension.key
                if dimension.enum:
                    assert dimension.enum in ENUMS
                    values = {row[dimension.key] for row in c.rows} - {None}
                    assert values <= set(ENUMS[dimension.enum]), (c.key, values)
                if dimension.order:
                    assert set(dimension.order) <= set(ENUMS[dimension.enum or ""]), c.key
            columns = {d.key for d in (*c.dimensions, *c.attributes)} | {m.key for m in c.measures}
            assert all(set(row) == columns for row in c.rows), c.key


def test_simulated_kpis_are_plausible(simulated: dict[str, Section]) -> None:
    overview = kpis(simulated["overview"])
    members, active, churn = (overview[k] for k in ("members", "active_members", "churn_rate"))
    assert members is not None
    assert active is not None
    assert churn is not None
    assert 0 < active <= members
    assert 0 < churn < 0.5
    conversion = kpis(simulated["subscriptions"])["trial_conversion_rate"]
    assert conversion is not None
    assert 0.2 < conversion < 0.7
