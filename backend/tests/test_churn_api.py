"""Churn runs through the API: train (a job), quality and explanations, activation, scores."""

from collections.abc import Callable
from typing import Any

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.migrations import ALEMBIC_INI
from app.domain.churn.features import FEATURES
from app.domain.enums import JobKind
from app.models import Analyst, ChurnRun
from app.services import auth, churn, jobs

Headers = dict[str, str]


@pytest.fixture
def dataset(
    import_document: Callable[[dict[str, Any]], dict[str, Any]],
    trainable_document: dict[str, Any],
) -> dict[str, Any]:
    return import_document(trainable_document)


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
    train_run: Callable[[int], dict[str, Any]],
    dataset: dict[str, Any],
) -> None:
    first = train_run(dataset["id"])
    second = train_run(dataset["id"])
    for run in (first, second):
        response = client.post(f"/api/v1/churn-runs/{run['id']}/activate", headers=auth_headers)
        assert response.status_code == 200, response.text
        assert response.json()["active"] is True
    runs = client.get(
        "/api/v1/churn-runs", headers=auth_headers, params={"dataset_id": dataset["id"]}
    ).json()
    assert runs["total"] == 2
    only_active = client.get(
        "/api/v1/churn-runs",
        headers=auth_headers,
        params={"dataset_id": dataset["id"], "active": True},
    ).json()
    assert [run["id"] for run in only_active["items"]] == [second["id"]]
    assert {(r["id"], r["active"]) for r in runs["items"]} == {
        (first["id"], False),
        (second["id"], True),
    }


def test_a_run_needs_retention_data(
    client: TestClient,
    auth_headers: Headers,
    import_document: Callable[[dict[str, Any]], dict[str, Any]],
    upload_document: Callable[[dict[str, Any]], dict[str, Any]],
    mini_document: dict[str, Any],
    trainable_document: dict[str, Any],
) -> None:
    mini = import_document(mini_document)  # no retention campaign
    response = client.post(f"/api/v1/datasets/{mini['id']}/churn-runs", headers=auth_headers)
    assert response.status_code == 409
    assert response.json()["code"] == "churn.not_supported"

    pending = upload_document(trainable_document)
    response = client.post(f"/api/v1/datasets/{pending['id']}/churn-runs", headers=auth_headers)
    assert response.status_code == 409
    assert response.json()["code"] == "dataset.not_ready"


def test_too_little_history_fails_the_run_not_the_dataset(
    client: TestClient,
    auth_headers: Headers,
    import_document: Callable[[dict[str, Any]], dict[str, Any]],
    train_run: Callable[[int], dict[str, Any]],
    tabular_document: dict[str, Any],
) -> None:
    small = import_document(tabular_document)  # one churn in 8 months
    run = train_run(small["id"])
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


def test_older_runs_get_their_expected_churners(
    client: TestClient,
    auth_headers: Headers,
    db_session: Session,
    train_run: Callable[[int], dict[str, Any]],
    dataset: dict[str, Any],
) -> None:
    """Regression: runs trained before summaries had `expected_churners` gave 500; migration
    0007 fills it in the way training does."""
    run = train_run(dataset["id"])
    stored = db_session.get_one(ChurnRun, run["id"])
    result = dict(stored.result or {})
    result["summary"] = {k: v for k, v in result["summary"].items() if k != "expected_churners"}
    stored.result = result
    db_session.commit()

    migration = ScriptDirectory.from_config(Config(str(ALEMBIC_INI))).get_revision("0007")
    assert migration is not None
    with Operations.context(MigrationContext.configure(db_session.connection())):
        migration.module.upgrade()
    db_session.expire_all()
    response = client.get(f"/api/v1/churn-runs/{run['id']}", headers=auth_headers)
    assert response.status_code == 200, response.text
    expected = run["summary"]["expected_churners"]
    assert response.json()["summary"]["expected_churners"] == pytest.approx(expected)
