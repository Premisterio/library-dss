import os
from collections.abc import Callable, Iterator
from typing import Any

# Defaults for running tests on the host against the dev compose database (port 5433).
# CI and the api container provide their own values.
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-0123456789abcdef0123")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://dss:dss@localhost:5433/dss")
os.environ.setdefault("COOKIE_SECURE", "false")  # TestClient talks plain HTTP
# (the imports below read these defaults)

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.db import get_engine, get_session
from app.core.migrations import ALEMBIC_INI
from app.main import create_app


@pytest.fixture(scope="session")
def migrated() -> None:
    """Bring the test database to the latest migration once per test run."""
    command.upgrade(Config(str(ALEMBIC_INI)), "head")


@pytest.fixture
def db_session(migrated: None) -> Iterator[Session]:
    """A session inside a transaction that is rolled back after the test.

    Application code may call commit(): with `create_savepoint` those commits release
    savepoints and the outer transaction still discards everything.
    """
    connection = get_engine().connect()
    outer = connection.begin()
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def make_client(db_session: Session) -> Iterator[Callable[..., TestClient]]:
    """Factory for clients of an app built with optional setting overrides."""
    clients: list[TestClient] = []

    def factory(**overrides: Any) -> TestClient:
        settings = Settings(**overrides) if overrides else None
        app: FastAPI = create_app(settings)
        app.dependency_overrides[get_session] = lambda: db_session
        test_client = TestClient(app, raise_server_exceptions=False)
        clients.append(test_client)
        return test_client

    yield factory
    for test_client in clients:
        test_client.close()


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()
