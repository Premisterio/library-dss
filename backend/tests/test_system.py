import pytest
from fastapi.testclient import TestClient

from app import __version__
from app.core.errors import PROBLEM_MEDIA_TYPE


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


@pytest.mark.db
def test_ready_when_database_is_migrated(client: TestClient) -> None:
    response = client.get("/api/v1/ready")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ready", "database": "ok", "migrations": "ok"}


def test_unknown_route_is_a_problem_document(client: TestClient) -> None:
    response = client.get("/api/v1/definitely-missing")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    body = response.json()
    assert body["code"] == "http.not_found"
    assert body["status"] == 404


def test_api_docs_page(client: TestClient) -> None:
    response = client.get("/api/docs")
    assert response.status_code == 200
    assert "/api/v1/openapi.json" in response.text
