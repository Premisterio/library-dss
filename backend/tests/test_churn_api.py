"""Churn runs through the API: train (a job), quality and explanations, activation, scores."""

from collections.abc import Callable
from functools import cache
from typing import Any

import orjson
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.domain.churn.features import FEATURES
from app.domain.enums import JobKind
from app.models import Analyst
from app.services import auth, churn, jobs

Headers = dict[str, str]


def upload(client: TestClient, headers: Headers, document: dict[str, Any]) -> dict[str, Any]:
    response = client.post(
        "/api/v1/datasets",
        headers=headers,
        files={"file": ("library.json", orjson.dumps(document), "application/json")},
    )
    assert response.status_code == 202, response.text
    return response.json()["dataset"]


def imported(
    client: TestClient, headers: Headers, run_jobs: Callable[[], int], document: dict[str, Any]
) -> dict[str, Any]:
    dataset = upload(client, headers, document)
    assert run_jobs() == 1
    return client.get(f"/api/v1/datasets/{dataset['id']}", headers=headers).json()


@cache
def _trainable() -> dict[str, Any]:
    from libsim import engine, writer
    from libsim.params import preset

    return writer.build_dataset(engine.simulate(preset("demo", users=800, months=10, seed=1)))


@pytest.fixture
def dataset(
    client: TestClient, auth_headers: Headers, run_jobs: Callable[[], int]
) -> dict[str, Any]:
    """A libsim dataset with enough renewals to train on (800 members, 10 months)."""
    return imported(client, auth_headers, run_jobs, _trainable())


def train(
    client: TestClient, headers: Headers, run_jobs: Callable[[], int], dataset_id: int
) -> dict[str, Any]:
    response = client.post(f"/api/v1/datasets/{dataset_id}/churn-runs", headers=headers)
    assert response.status_code == 202, response.text
    assert run_jobs() == 1
    return client.get(f"/api/v1/churn-runs/{response.json()['run']['id']}", headers=headers).json()


def test_a_run_is_trained_explained_and_scored(
    client: TestClient,
    auth_headers: Headers,
    run_jobs: Callable[[], int],
    dataset: dict[str, Any],
) -> None:
    accepted = client.post(f"/api/v1/datasets/{dataset['id']}/churn-runs", headers=auth_headers)
    assert accepted.status_code == 202, accepted.text
    body = accepted.json()
    assert body["run"]["status"] == "queued"
    assert body["run"]["chosen_model"] is None
    assert body["job"]["kind"] == "train_churn"
    assert accepted.headers["Location"] == f"/api/v1/jobs/{body['job']['id']}"
    assert run_jobs() == 1

    run = client.get(f"/api/v1/churn-runs/{body['run']['id']}", headers=auth_headers).json()
    assert run["status"] == "succeeded"
    assert run["chosen_model"] in {"logistic", "boosting"}
    assert run["active"] is False
    assert run["summary"]["scored"] > 0
    assert 0 < run["summary"]["expected_churners"] < run["summary"]["scored"]
    assert [m["model"] for m in run["models"]] == ["inactivity_rule", "logistic", "boosting"]
    assert len(run["backtest"]) == 6 * 3
    assert len(run["importance"]) == len(FEATURES)
    assert bool(run["coefficients"]) == (run["chosen_model"] == "logistic")
    # training does not touch the dataset
    dataset_now = client.get(f"/api/v1/datasets/{dataset['id']}", headers=auth_headers).json()
    assert dataset_now["status"] == "ready"

    page = client.get(
        f"/api/v1/churn-runs/{run['id']}/scores", headers=auth_headers, params={"limit": 100}
    ).json()
    assert page["total"] == run["summary"]["scored"]
    assert [s["rank"] for s in page["items"]] == list(range(1, len(page["items"]) + 1))
    probabilities = [s["probability"] for s in page["items"]]
    assert probabilities == sorted(probabilities, reverse=True)
    assert all(len(s["reasons"]) <= 3 for s in page["items"])

    top = page["items"][0]
    detail = client.get(
        f"/api/v1/churn-runs/{run['id']}/scores/{top['user_id']}", headers=auth_headers
    ).json()
    assert detail["probability"] == top["probability"]
    assert [
        (f["feature"], f["group"], f["kind"], f["unit"], f["enum"]) for f in detail["features"]
    ] == [(f.key, f.group, f.kind, f.unit, f.enum) for f in FEATURES]
    spec = {f.key: f for f in FEATURES}
    for reason in (r for s in page["items"] for r in s["reasons"]):
        assert (reason["kind"], reason["unit"]) == (
            spec[reason["feature"]].kind,
            spec[reason["feature"]].unit,
        )


def test_activation_keeps_one_run_per_dataset(
    client: TestClient,
    auth_headers: Headers,
    run_jobs: Callable[[], int],
    dataset: dict[str, Any],
) -> None:
    first = train(client, auth_headers, run_jobs, dataset["id"])
    second = train(client, auth_headers, run_jobs, dataset["id"])
    for run in (first, second):
        response = client.post(f"/api/v1/churn-runs/{run['id']}/activate", headers=auth_headers)
        assert response.status_code == 200, response.text
        assert response.json()["active"] is True
    runs = client.get(
        "/api/v1/churn-runs", headers=auth_headers, params={"dataset_id": dataset["id"]}
    ).json()
    assert runs["total"] == 2
    assert {(r["id"], r["active"]) for r in runs["items"]} == {
        (first["id"], False),
        (second["id"], True),
    }


def test_a_run_needs_retention_data(
    client: TestClient,
    auth_headers: Headers,
    run_jobs: Callable[[], int],
    mini_document: dict[str, Any],
) -> None:
    mini = imported(client, auth_headers, run_jobs, mini_document)  # no retention campaign
    response = client.post(f"/api/v1/datasets/{mini['id']}/churn-runs", headers=auth_headers)
    assert response.status_code == 409
    assert response.json()["code"] == "churn.not_supported"

    pending = upload(client, auth_headers, _trainable())
    response = client.post(f"/api/v1/datasets/{pending['id']}/churn-runs", headers=auth_headers)
    assert response.status_code == 409
    assert response.json()["code"] == "dataset.not_ready"


def test_too_little_history_fails_the_run_not_the_dataset(
    client: TestClient,
    auth_headers: Headers,
    run_jobs: Callable[[], int],
    tabular_document: dict[str, Any],
) -> None:
    small = imported(client, auth_headers, run_jobs, tabular_document)  # one churn in 8 months
    run = train(client, auth_headers, run_jobs, small["id"])
    assert run["status"] == "failed"
    assert run["error"]["code"] == "churn.not_enough_history"
    assert run["chosen_model"] is None
    dataset_now = client.get(f"/api/v1/datasets/{small['id']}", headers=auth_headers).json()
    assert dataset_now["status"] == "ready"
    for method, path in (
        ("GET", f"/api/v1/churn-runs/{run['id']}/scores"),
        ("POST", f"/api/v1/churn-runs/{run['id']}/activate"),
    ):
        response = client.request(method, path, headers=auth_headers)
        assert response.status_code == 409
        assert response.json()["code"] == "churn.not_trained"


def test_runs_are_private_and_deletable(
    client: TestClient,
    auth_headers: Headers,
    run_jobs: Callable[[], int],
    db_session: Session,
    dataset: dict[str, Any],
) -> None:
    queued = client.post(f"/api/v1/datasets/{dataset['id']}/churn-runs", headers=auth_headers)
    busy = client.delete(f"/api/v1/churn-runs/{queued.json()['run']['id']}", headers=auth_headers)
    assert busy.status_code == 409
    assert busy.json()["code"] == "churn.busy"
    run_jobs()
    run_id = queued.json()["run"]["id"]
    missing = client.get(f"/api/v1/churn-runs/{run_id}/scores/u999999", headers=auth_headers)
    assert missing.status_code == 404
    assert missing.json()["code"] == "churn.member_not_scored"

    auth.create_analyst(db_session, email="other@example.com", name="Інша", password="x" * 12)
    login = client.post(
        "/api/v1/auth/login", json={"email": "other@example.com", "password": "x" * 12}
    )
    other = {"Authorization": f"Bearer {login.json()['access_token']}"}
    for path in (f"/api/v1/churn-runs/{run_id}", f"/api/v1/churn-runs/{run_id}/scores"):
        response = client.get(path, headers=other)
        assert response.status_code == 404
        assert response.json()["code"] == "churn.not_found"
    started = client.post(f"/api/v1/datasets/{dataset['id']}/churn-runs", headers=other)
    assert started.status_code == 404
    assert client.get("/api/v1/churn-runs", headers=other).json()["total"] == 0

    assert client.delete(f"/api/v1/churn-runs/{run_id}", headers=auth_headers).status_code == 204
    gone = client.get(f"/api/v1/churn-runs/{run_id}", headers=auth_headers)
    assert gone.status_code == 404


def test_a_job_without_its_run_fails(
    db_session: Session, analyst: Analyst, dataset: dict[str, Any]
) -> None:
    job = jobs.enqueue(
        db_session, kind=JobKind.TRAIN_CHURN, owner_id=analyst.id, dataset_id=dataset["id"]
    )
    with pytest.raises(ApiError) as raised:
        churn.run_training(db_session, job, lambda *_: None)
    assert raised.value.code == "churn.missing"
