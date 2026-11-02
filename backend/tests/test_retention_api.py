"""Retention plans through the API: the preview, its modes, and approval as a decision (a report
of kind `retention`) that exports like any report."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.domain.enums import ENUMS
from app.models import ChurnRun, ChurnScore
from app.services import auth

Headers = dict[str, str]
PLAN = {"budget": 3000, "max_emails": 100}


@pytest.fixture
def run(
    import_document: Callable[[dict[str, Any]], dict[str, Any]],
    train_run: Callable[[int], dict[str, Any]],
    trainable_document: dict[str, Any],
) -> dict[str, Any]:
    trained = train_run(import_document(trainable_document)["id"])
    assert trained["status"] == "succeeded"
    return trained


def detail_of(client: TestClient, headers: Headers, report_id: int) -> dict[str, Any]:
    return client.get(f"/api/v1/reports/{report_id}", headers=headers).json()["content"][0]


def kpis(section: dict[str, Any]) -> dict[str, Any]:
    return {kpi["key"]: kpi["value"] for kpi in section["kpis"]}


def chart(section: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return next(c["rows"] for c in section["charts"] if c["key"] == key)


def preview(client: TestClient, headers: Headers, run_id: int, **body: Any) -> dict[str, Any]:
    response = client.post(f"/api/v1/churn-runs/{run_id}/plan", headers=headers, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_the_preview_is_a_plan_within_the_budget(
    client: TestClient, auth_headers: Headers, run: dict[str, Any]
) -> None:
    section = preview(client, auth_headers, run["id"], **PLAN)
    assert section["key"] == "retention_plan"
    assert [note["code"] for note in section["notes"]] == ["retention.noisy_effects"]
    found = kpis(section)
    assert found["members_at_risk"] == run["summary"]["scored"]
    assert found["plan_spend"] <= 3000 + 1e-6
    assert found["planned_emails"] <= 100
    assert found["plan_value"] >= found["greedy_value"] - 1e-6
    planned = chart(section, "planned_members")
    assert len(planned) == found["planned_emails"] + found["planned_discounts"]
    assert all(row["gain"] > 0 for row in planned)
    # Regression: a join lost the order, so the table and the PDF's first rows were arbitrary.
    gains = [row["gain"] for row in planned]
    assert gains == sorted(gains, reverse=True)
    curve = [row["plan_value"] for row in chart(section, "budget_curve")]
    assert curve == sorted(curve)
    effects = chart(section, "action_effects")
    assert {(row["action"], row["segment"]) for row in effects} == {
        (action, segment)
        for action in ENUMS["retention_action"]
        for segment in ENUMS["retention_segment"]  # "all": the overall effect plans use
    }
    overall = [row for row in effects if row["segment"] == "all"]
    assert all(row["effect_shrunk"] == row["effect"] for row in overall)


def test_cautious_and_assumed_effects(
    client: TestClient, auth_headers: Headers, run: dict[str, Any]
) -> None:
    usual = kpis(preview(client, auth_headers, run["id"], **PLAN))
    cautious = preview(client, auth_headers, run["id"], **PLAN, cautious=True)
    assert [note["code"] for note in cautious["notes"]] == [
        "retention.noisy_effects",
        "retention.cautious",
    ]
    assert kpis(cautious)["plan_value"] <= usual["plan_value"] + 1e-6  # less favourable effects
    assumed = preview(
        client,
        auth_headers,
        run["id"],
        budget=3000,
        assumed={"email": -0.01, "discount": -0.02, "discount_pct": 0.3},
    )
    assert [note["code"] for note in assumed["notes"]] == ["retention.assumed_effects"]
    assert kpis(assumed)["planned_emails"] + kpis(assumed)["planned_discounts"] > 0
    assert kpis(assumed)["offered_discount"] == 0.3
    # An effect larger than 90% of the churn is capped, and the plan says which.
    huge = preview(client, auth_headers, run["id"], budget=3000, assumed={"discount": -0.9})
    assert [note["code"] for note in huge["notes"]] == [
        "retention.assumed_effects",
        "retention.effect_capped",
    ]
    assert huge["notes"][1]["params"] == {"actions": ["discount"]}


def test_every_code_of_the_plan_has_a_label(
    client: TestClient, auth_headers: Headers, run: dict[str, Any]
) -> None:
    section = preview(client, auth_headers, run["id"], **PLAN)
    assert section["key"] in ENUMS["analytics_section"]
    for kpi in section["kpis"]:
        assert kpi["key"] in ENUMS["metric"], kpi["key"]
    for drawn in section["charts"]:
        assert drawn["key"] in ENUMS["chart"], drawn["key"]
        for column in drawn["dimensions"] + drawn["attributes"]:
            assert column["key"] in ENUMS["dimension"], column["key"]
        for measure in drawn["measures"]:
            assert measure["key"] in ENUMS["metric"], measure["key"]


def test_approval_freezes_a_decision(
    client: TestClient, auth_headers: Headers, run: dict[str, Any]
) -> None:
    body = {"title": "Утримання, жовтень", "plan": PLAN}
    url = f"/api/v1/churn-runs/{run['id']}/plan/approve"
    inactive = client.post(url, headers=auth_headers, json=body)
    assert inactive.status_code == 409
    assert inactive.json()["code"] == "retention.not_active"

    client.post(f"/api/v1/churn-runs/{run['id']}/activate", headers=auth_headers)
    approved = client.post(url, headers=auth_headers, json=body)
    assert approved.status_code == 201, approved.text
    report = approved.json()
    assert (report["kind"], report["title"], report["sections"]) == (
        "retention",
        "Утримання, жовтень",
        ["retention_plan"],
    )
    assert report["params"]["run_id"] == run["id"]
    assert report["params"]["budget"] == 3000
    # Regression: the campaign's discount was logged as the unused default of assumed effects.
    offered = kpis(detail_of(client, auth_headers, report["id"]))["offered_discount"]
    assert report["params"]["discount_pct"] == offered
    assert "assumed_discount_pct" not in report["params"]

    decisions = client.get(
        "/api/v1/reports", headers=auth_headers, params={"kind": "retention"}
    ).json()
    assert [item["id"] for item in decisions["items"]] == [report["id"]]
    analytics = client.get(
        "/api/v1/reports", headers=auth_headers, params={"kind": "analytics"}
    ).json()
    assert analytics["total"] == 0
    detail = client.get(f"/api/v1/reports/{report['id']}", headers=auth_headers).json()
    assert kpis(detail["content"][0]) == kpis(preview(client, auth_headers, run["id"], **PLAN))
    for fmt in ("pdf", "xlsx", "csv", "json"):
        export = client.get(
            f"/api/v1/reports/{report['id']}/export",
            headers=auth_headers,
            params={"format": fmt},
        )
        assert export.status_code == 200, (fmt, export.text)


def test_a_run_without_scores_has_nobody_to_plan_for(
    client: TestClient, auth_headers: Headers, db_session: Session, run: dict[str, Any]
) -> None:
    """Regression: a run without scores answered 500 instead of 409."""
    db_session.execute(delete(ChurnScore).where(ChurnScore.run_id == run["id"]))
    db_session.commit()
    response = client.post(f"/api/v1/churn-runs/{run['id']}/plan", headers=auth_headers, json=PLAN)
    assert response.status_code == 409
    assert response.json()["code"] == "retention.nobody_at_risk"


def test_runs_without_effects_or_other_owners(
    client: TestClient, auth_headers: Headers, db_session: Session, run: dict[str, Any]
) -> None:
    stored = db_session.get_one(ChurnRun, run["id"])
    stored.result = {key: value for key, value in (stored.result or {}).items() if key != "effects"}
    db_session.commit()
    old = client.post(f"/api/v1/churn-runs/{run['id']}/plan", headers=auth_headers, json=PLAN)
    assert old.status_code == 409
    assert old.json()["code"] == "retention.no_effects"

    auth.create_analyst(db_session, email="other@example.com", name="Інша", password="x" * 12)
    login = client.post(
        "/api/v1/auth/login", json={"email": "other@example.com", "password": "x" * 12}
    )
    other = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.post(f"/api/v1/churn-runs/{run['id']}/plan", headers=other, json=PLAN)
    assert response.status_code == 404


def test_inputs_are_checked(client: TestClient, auth_headers: Headers, run: dict[str, Any]) -> None:
    url = f"/api/v1/churn-runs/{run['id']}/plan"
    for body in ({"budget": -1}, {"budget": 10, "horizon_months": 0}, {}):
        response = client.post(url, headers=auth_headers, json=body)
        assert response.status_code == 422, body
