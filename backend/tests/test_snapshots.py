"""Snapshots of key API responses on the hand-made dataset: any change to the contract or to a
number shows up as a reviewable diff (`pytest --snapshot-update` after an intended change)."""

from collections.abc import Callable
from typing import Any

import orjson
import pytest
from fastapi.testclient import TestClient
from syrupy.assertion import SnapshotAssertion
from syrupy.extensions.json import JSONSnapshotExtension

Headers = dict[str, str]
VOLATILE = {"id", "dataset_id", "created_at", "updated_at", "started_at", "finished_at"}


@pytest.fixture
def snapshot_json(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    return snapshot.use_extension(JSONSnapshotExtension)


def stable(value: Any) -> Any:
    """Mask ids and timestamps, which differ between runs."""
    if isinstance(value, dict):
        return {k: (f"<{k}>" if k in VOLATILE else stable(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [stable(v) for v in value]
    return value


@pytest.fixture
def dataset(
    client: TestClient,
    auth_headers: Headers,
    run_jobs: Callable[[], int],
    mini_document: dict[str, Any],
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/datasets",
        headers=auth_headers,
        files={"file": ("mini.json", orjson.dumps(mini_document), "application/json")},
        data={"name": "Ручний набір"},
    )
    run_jobs()
    dataset_id = response.json()["dataset"]["id"]
    return client.get(f"/api/v1/datasets/{dataset_id}", headers=auth_headers).json()


def test_dataset(dataset: dict[str, Any], snapshot_json: SnapshotAssertion) -> None:
    assert stable(dataset) == snapshot_json


def test_analytics(
    client: TestClient,
    auth_headers: Headers,
    dataset: dict[str, Any],
    snapshot_json: SnapshotAssertion,
) -> None:
    response = client.get(f"/api/v1/datasets/{dataset['id']}/analytics", headers=auth_headers)
    assert stable(response.json()) == snapshot_json


def test_report(
    client: TestClient,
    auth_headers: Headers,
    dataset: dict[str, Any],
    snapshot_json: SnapshotAssertion,
) -> None:
    report = client.post(
        "/api/v1/reports",
        headers=auth_headers,
        json={"dataset_id": dataset["id"], "title": "Звіт", "sections": ["overview"]},
    ).json()
    response = client.get(f"/api/v1/reports/{report['id']}", headers=auth_headers)
    assert stable(response.json()) == snapshot_json


def test_enums(client: TestClient, snapshot_json: SnapshotAssertion) -> None:
    assert client.get("/api/v1/meta/enums").json() == snapshot_json
