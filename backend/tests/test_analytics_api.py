"""Analytics endpoints: computed during the import job, served as stored sections."""

from collections.abc import Callable
from typing import Any

import orjson
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.domain.analytics import SECTIONS
from app.models import Dataset, DatasetAnalytics
from app.services import analytics

Headers = dict[str, str]


def import_dataset(
    client: TestClient, headers: Headers, run_jobs: Callable[[], int], document: dict[str, Any]
) -> int:
    response = client.post(
        "/api/v1/datasets",
        headers=headers,
        files={"file": ("mini.json", orjson.dumps(document), "application/json")},
    )
    assert response.status_code == 202, response.text
    run_jobs()
    return response.json()["dataset"]["id"]


def test_sections_are_served_after_import(
    client: TestClient,
    auth_headers: Headers,
    run_jobs: Callable[[], int],
    mini_document: dict[str, Any],
) -> None:
    dataset_id = import_dataset(client, auth_headers, run_jobs, mini_document)
    response = client.get(f"/api/v1/datasets/{dataset_id}/analytics/overview", headers=auth_headers)
    assert response.status_code == 200, response.text
    overview = response.json()
    assert overview["key"] == "overview"
    assert overview["as_of"] == "2026-03-31"
    assert overview["timezone"] == "Europe/Kyiv"
    assert {k["key"]: k["value"] for k in overview["kpis"]}["paying_subscribers"] == 2
    assert overview["kpis"][1] == {
        "key": "active_members",
        "value": 4,
        "unit": "count",
        "window_days": 30,
    }
    weekly = overview["charts"][0]
    assert weekly["dimensions"] == [{"key": "week", "kind": "time", "enum": None, "order": None}]

    everything = client.get(f"/api/v1/datasets/{dataset_id}/analytics", headers=auth_headers)
    assert [s["key"] for s in everything.json()["sections"]] == list(SECTIONS)


def test_unknown_section_is_a_validation_error(client: TestClient, auth_headers: Headers) -> None:
    response = client.get("/api/v1/datasets/1/analytics/horoscope", headers=auth_headers)
    assert response.status_code == 422


def test_analytics_need_a_ready_dataset(
    client: TestClient, auth_headers: Headers, mini_document: dict[str, Any]
) -> None:
    accepted = client.post(
        "/api/v1/datasets",
        headers=auth_headers,
        files={"file": ("mini.json", orjson.dumps(mini_document), "application/json")},
    ).json()
    response = client.get(
        f"/api/v1/datasets/{accepted['dataset']['id']}/analytics/usage", headers=auth_headers
    )
    assert response.status_code == 409
    assert response.json()["code"] == "dataset.not_ready"


def test_missing_analytics_can_be_refreshed(
    client: TestClient,
    auth_headers: Headers,
    run_jobs: Callable[[], int],
    db_session: Session,
    mini_document: dict[str, Any],
) -> None:
    dataset_id = import_dataset(client, auth_headers, run_jobs, mini_document)
    db_session.execute(delete(DatasetAnalytics).where(DatasetAnalytics.dataset_id == dataset_id))
    db_session.commit()
    path = f"/api/v1/datasets/{dataset_id}/analytics"
    for url in (path, f"{path}/search"):
        response = client.get(url, headers=auth_headers)
        assert response.status_code == 409
        assert response.json()["code"] == "analytics.missing"

    analytics.refresh(db_session, db_session.get_one(Dataset, dataset_id))
    assert client.get(f"{path}/search", headers=auth_headers).status_code == 200


def test_analytics_are_private(
    client: TestClient,
    auth_headers: Headers,
    run_jobs: Callable[[], int],
    mini_document: dict[str, Any],
) -> None:
    dataset_id = import_dataset(client, auth_headers, run_jobs, mini_document)
    client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "name": "Інший", "password": "password-2"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": "other@example.com", "password": "password-2"}
    ).json()["access_token"]
    response = client.get(
        f"/api/v1/datasets/{dataset_id}/analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
