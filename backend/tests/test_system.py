import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app import __version__
from app.core.db import get_engine
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


@pytest.mark.db
def test_sessions_run_in_utc_whatever_the_server_default(
    migrated: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: on a server whose default time zone is not UTC (a Homebrew PostgreSQL takes the
    machine's), the API answered timestamps such as 2026-11-02T14:19:54+01:00."""
    monkeypatch.setenv("PGOPTIONS", "-c TimeZone=Asia/Tokyo")  # stands in for that server default
    engine = get_engine.__wrapped__()
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SHOW TimeZone")) == "UTC"
    finally:
        engine.dispose()


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
