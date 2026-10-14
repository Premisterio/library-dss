"""Dataset upload → import job → dataset, end to end through the API (jobs run synchronously)."""

import gzip
from collections.abc import Callable
from typing import Any

import orjson
import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.v1 import jobs as jobs_api
from app.ingest.schema_v2 import DB_TABLE, TABLES
from app.models import Dataset, DatasetFile, Job
from app.services import auth

Headers = dict[str, str]


def upload(
    client: TestClient,
    headers: Headers,
    document: dict[str, Any] | bytes,
    filename: str = "library.json",
    **form: str,
) -> Response:
    content = document if isinstance(document, bytes) else orjson.dumps(document)
    return client.post(
        "/api/v1/datasets",
        headers=headers,
        files={"file": (filename, content, "application/octet-stream")},
        data=form,
    )


def imported(
    client: TestClient, headers: Headers, run_jobs: Callable[[], int], document: dict[str, Any]
) -> dict[str, Any]:
    response = upload(client, headers, document)
    assert response.status_code == 202, response.text
    assert run_jobs() == 1
    return client.get(
        f"/api/v1/datasets/{response.json()['dataset']['id']}", headers=headers
    ).json()


def count(session: Session, table: str, dataset_id: int) -> int:
    query = text(f"SELECT count(*) FROM {table} WHERE dataset_id = :id")  # noqa: S608 (fixed names)
    return session.scalar(query, {"id": dataset_id}) or 0


def test_v2_upload_is_imported(
    client: TestClient,
    auth_headers: Headers,
    run_jobs: Callable[[], int],
    db_session: Session,
    v2_document: dict[str, Any],
) -> None:
    response = upload(
        client, auth_headers, gzip.compress(orjson.dumps(v2_document)), "demo.json.gz", name="Демо"
    )
    assert response.status_code == 202, response.text
    accepted = response.json()
    job_id, dataset_id = accepted["job"]["id"], accepted["dataset"]["id"]
    assert response.headers["location"] == f"/api/v1/jobs/{job_id}"
    assert accepted["dataset"]["status"] == "pending"
    assert accepted["dataset"]["name"] == "Демо"
    assert accepted["job"]["status"] == "queued"

    assert run_jobs() == 1

    dataset = client.get(f"/api/v1/datasets/{dataset_id}", headers=auth_headers).json()
    expected_counts = {name: len(v2_document["tables"][name]["rows"]) for name in TABLES}
    assert dataset["status"] == "ready"
    assert dataset["schema_version"] == 2
    assert dataset["as_of"] == v2_document["meta"]["as_of"]
    assert dataset["timezone"] == "Europe/Kyiv"
    assert dataset["capabilities"] == ["descriptive", "retention", "content"]
    assert dataset["row_counts"] == expected_counts
    assert dataset["meta"]["seed"] == 11
    assert dataset["meta"]["original_filename"] == "demo.json.gz"
    assert dataset["error"] is None
    for name, expected in expected_counts.items():
        assert count(db_session, DB_TABLE[name], dataset_id) == expected, name

    job = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers).json()
    assert job["status"] == "succeeded"
    assert job["progress"] == 1.0
    assert job["result"]["dataset_id"] == dataset_id

    # Values survive COPY unchanged: arrays, booleans, timestamps (UTC), money.
    user = v2_document["tables"]["users"]["rows"][0]
    stored = db_session.execute(
        text(
            "SELECT interests, email_opt_in, to_char(registered_at AT TIME ZONE 'UTC',"
            ' \'YYYY-MM-DD"T"HH24:MI:SS"Z"\') FROM lib_users'
            " WHERE dataset_id = :id AND user_id = :user"
        ),
        {"id": dataset_id, "user": user[0]},
    ).one()
    assert list(stored) == [user[6], user[5], user[1]]


def test_v1_upload_supports_descriptive_analytics_only(
    client: TestClient,
    auth_headers: Headers,
    run_jobs: Callable[[], int],
    db_session: Session,
    v1_document: dict[str, Any],
) -> None:
    dataset = imported(client, auth_headers, run_jobs, v1_document)
    assert dataset["status"] == "ready"
    assert dataset["schema_version"] == 1
    assert dataset["capabilities"] == ["descriptive"]
    assert dataset["as_of"] == "2025-06-18"
    assert dataset["meta"]["warnings"]
    # Audit 2026-10-08 regression: all loans and distinct titles are stored, not a top 10.
    assert count(db_session, "loans", dataset["id"]) == 6
    titles = db_session.scalar(
        text("SELECT count(DISTINCT title) FROM books WHERE dataset_id = :id"),
        {"id": dataset["id"]},
    )
    assert titles == 4
    extra = db_session.scalar(
        text("SELECT extra FROM lib_users WHERE dataset_id = :id AND user_id = 'u2'"),
        {"id": dataset["id"]},
    )
    assert extra["subscription_plan"] == "annual"


def test_invalid_dataset_fails_with_details(
    client: TestClient,
    auth_headers: Headers,
    run_jobs: Callable[[], int],
    db_session: Session,
    v2_document: dict[str, Any],
) -> None:
    v2_document["tables"]["loans"]["rows"][0][2] = "no-such-book"
    dataset = imported(client, auth_headers, run_jobs, v2_document)
    assert dataset["status"] == "failed"
    assert dataset["error"]["code"] == "dataset.invalid"
    assert dataset["error"]["errors"] == ["loans.book_id: 1 rows point to unknown books"]
    assert dataset["row_counts"] == {}
    assert count(db_session, "loans", dataset["id"]) == 0
    job = db_session.scalars(select(Job).where(Job.dataset_id == dataset["id"])).one()
    assert job.status == "failed"
    assert job.error == dataset["error"]


def test_too_long_values_fail_cleanly(
    client: TestClient,
    auth_headers: Headers,
    run_jobs: Callable[[], int],
    v1_document: dict[str, Any],
) -> None:
    """Values the database rejects (here a 41+ character id) fail the job, not the worker."""
    v1_document["users"][2]["user_id"] = "u" * 50
    dataset = imported(client, auth_headers, run_jobs, v1_document)
    assert dataset["status"] == "failed"
    assert dataset["error"]["code"] == "dataset.invalid"
    assert "Table 'users'" in dataset["error"]["detail"]


@pytest.mark.parametrize(
    "content",
    [b"not json at all", b"\x1f\x8b\x08\x00broken gzip", b"[1, 2]"],
    ids=["text", "gzip", "array"],
)
def test_unreadable_upload_is_rejected(
    client: TestClient, auth_headers: Headers, content: bytes
) -> None:
    response = upload(client, auth_headers, content)
    assert response.status_code == 422
    assert response.json()["code"] == "dataset.unreadable"


def test_unsupported_version_fails_the_job(
    client: TestClient, auth_headers: Headers, run_jobs: Callable[[], int]
) -> None:
    dataset = imported(client, auth_headers, run_jobs, {"schema_version": 7})
    assert dataset["error"]["code"] == "dataset.unsupported_version"


def test_duplicate_upload_is_a_conflict(
    client: TestClient, auth_headers: Headers, v1_document: dict[str, Any]
) -> None:
    content = orjson.dumps(v1_document)
    first = upload(client, auth_headers, content)
    assert first.status_code == 202
    again = upload(client, auth_headers, gzip.compress(content), "same.json.gz")  # same JSON
    assert again.status_code == 409
    assert again.json()["code"] == "dataset.duplicate"
    assert f"#{first.json()['dataset']['id']}" in again.json()["detail"]


def test_upload_size_limit(make_client: Callable[..., TestClient], auth_headers: Headers) -> None:
    client = make_client(max_upload_mb=1)
    padded = b'{"users": []' + b" " * 2**20 + b"}"
    for content in (padded, gzip.compress(padded)):  # a small gzip that expands past the limit
        response = upload(client, auth_headers, content)
        assert response.status_code == 413
        assert response.json()["code"] == "dataset.too_large"


def test_datasets_are_private(
    client: TestClient,
    auth_headers: Headers,
    db_session: Session,
    v1_document: dict[str, Any],
) -> None:
    accepted = upload(client, auth_headers, v1_document).json()
    auth.create_analyst(db_session, email="other@example.com", name="Інший", password="password-2")
    token = client.post(
        "/api/v1/auth/login", json={"email": "other@example.com", "password": "password-2"}
    ).json()["access_token"]
    other = {"Authorization": f"Bearer {token}"}
    dataset_id, job_id = accepted["dataset"]["id"], accepted["job"]["id"]
    assert client.get("/api/v1/datasets", headers=other).json()["total"] == 0
    for method, path in [
        ("GET", f"/api/v1/datasets/{dataset_id}"),
        ("DELETE", f"/api/v1/datasets/{dataset_id}"),
        ("GET", f"/api/v1/jobs/{job_id}"),
        ("GET", f"/api/v1/jobs/{job_id}/events"),
    ]:
        response = client.request(method, path, headers=other)
        assert response.status_code == 404, path
        assert response.json()["code"] in {"dataset.not_found", "job.not_found"}
    # The same file is not a duplicate for another analyst.
    assert upload(client, other, v1_document).status_code == 202


def test_list_is_paginated_newest_first(
    client: TestClient, auth_headers: Headers, v1_document: dict[str, Any]
) -> None:
    for n in range(3):
        v1_document["users"][0]["user_id"] = f"u1-{n}"  # different content each time
        assert upload(client, auth_headers, v1_document, name=f"Набір {n}").status_code == 202
    first = client.get("/api/v1/datasets?limit=2", headers=auth_headers).json()
    assert first["total"] == 3
    assert [d["name"] for d in first["items"]] == ["Набір 2", "Набір 1"]
    rest = client.get("/api/v1/datasets?limit=2&offset=2", headers=auth_headers).json()
    assert [d["name"] for d in rest["items"]] == ["Набір 0"]
    bad = client.get("/api/v1/datasets?limit=1000", headers=auth_headers)
    assert bad.status_code == 422


def test_delete_removes_all_data(
    client: TestClient,
    auth_headers: Headers,
    run_jobs: Callable[[], int],
    db_session: Session,
    v1_document: dict[str, Any],
) -> None:
    dataset = imported(client, auth_headers, run_jobs, v1_document)
    response = client.delete(f"/api/v1/datasets/{dataset['id']}", headers=auth_headers)
    assert response.status_code == 204
    assert client.get(f"/api/v1/datasets/{dataset['id']}", headers=auth_headers).status_code == 404
    for table in ("loans", "lib_users", "books", "dataset_files", "jobs"):
        assert count(db_session, table, dataset["id"]) == 0, table


def test_cannot_delete_while_importing(
    client: TestClient, auth_headers: Headers, db_session: Session, v1_document: dict[str, Any]
) -> None:
    dataset_id = upload(client, auth_headers, v1_document).json()["dataset"]["id"]
    dataset = db_session.get_one(Dataset, dataset_id)
    dataset.status = "importing"
    db_session.commit()
    response = client.delete(f"/api/v1/datasets/{dataset_id}", headers=auth_headers)
    assert response.status_code == 409
    assert response.json()["code"] == "dataset.busy"


def test_upload_stores_the_file_compressed(
    client: TestClient, auth_headers: Headers, db_session: Session, v1_document: dict[str, Any]
) -> None:
    content = orjson.dumps(v1_document)
    dataset_id = upload(client, auth_headers, content).json()["dataset"]["id"]
    stored = db_session.get_one(DatasetFile, dataset_id)
    assert stored.size_bytes == len(content)
    assert gzip.decompress(stored.content) == content


def events(response: Response) -> list[dict[str, Any]]:
    return [
        orjson.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


def test_job_events_stream(
    client: TestClient,
    auth_headers: Headers,
    run_jobs: Callable[[], int],
    v1_document: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = upload(client, auth_headers, v1_document).json()["job"]["id"]
    monkeypatch.setattr(jobs_api, "POLL_SECONDS", 0.01)
    monkeypatch.setattr(jobs_api, "STREAM_MAX_SECONDS", 0.2)
    pending = client.get(f"/api/v1/jobs/{job_id}/events", headers=auth_headers)
    assert pending.headers["content-type"].startswith("text/event-stream")
    assert [e["status"] for e in events(pending)] == ["queued"]  # sent once, then bounded

    run_jobs()
    finished = client.get(f"/api/v1/jobs/{job_id}/events", headers=auth_headers)
    assert [e["status"] for e in events(finished)] == ["succeeded"]  # closes when finished


def test_endpoints_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/datasets").status_code == 401
    assert client.post("/api/v1/datasets").status_code == 401
