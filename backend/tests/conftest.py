import os
from collections.abc import Callable, Iterator
from typing import Any

# Defaults for running tests on the host: a separate `dss_test` database on the dev compose
# server (port 5433), created on first use, so the dev worker never picks up test jobs.
# CI provides its own values.
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-0123456789abcdef0123")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://dss:dss@localhost:5433/dss_test")
os.environ.setdefault("COOKIE_SECURE", "false")  # TestClient talks plain HTTP
# (the imports below read these defaults)

import copy
from functools import cache

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import CONNECT_TIMEOUT_SECONDS, get_engine, get_session
from app.core.migrations import ALEMBIC_INI
from app.main import create_app
from app.models import Analyst
from app.services import auth
from app.worker import runner

PASSWORD = "correct horse battery"


def _create_database_if_missing(url: str) -> None:
    target = make_url(url)
    server = create_engine(
        target.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )
    try:
        with server.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target.database}
            )
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{target.database}"'))
    finally:
        server.dispose()


@pytest.fixture(scope="session")
def migrated() -> None:
    """Bring the test database to the latest migration once per test run."""
    _create_database_if_missing(get_settings().database_url)
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


@pytest.fixture
def run_jobs(db_session: Session) -> Callable[[], int]:
    """Run queued jobs synchronously; returns how many ran.

    Like the real worker, every step gets its own session; here each one is a savepoint on the
    test connection, so its work is visible to the test and still rolled back afterwards.
    """
    connection = db_session.get_bind()

    def factory() -> Session:
        return Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )

    def run() -> int:
        count = 0
        while runner.run_once(factory):
            count += 1
        db_session.expire_all()  # the worker changed rows this session may have cached
        return count

    return run


@pytest.fixture
def analyst(db_session: Session) -> Analyst:
    return auth.create_analyst(
        db_session, email="analyst@example.com", name="Аналітик", password=PASSWORD
    )


@pytest.fixture
def auth_headers(client: TestClient, analyst: Analyst) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"email": analyst.email, "password": PASSWORD}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@cache
def _simulated_v2() -> dict[str, Any]:
    from libsim import engine, writer
    from libsim.params import preset

    return writer.build_dataset(engine.simulate(preset("demo", users=200, months=8, seed=11)))


@pytest.fixture
def v2_document() -> dict[str, Any]:
    """A small libsim dataset (200 members, 8 months); safe to modify in a test."""
    return copy.deepcopy(_simulated_v2())


@pytest.fixture
def v1_document() -> dict[str, Any]:
    """A hand-made bachelor-era (v1) file: 3 users, 5 book ids with 4 distinct titles, 6 loans."""

    def borrowed(book_id: str, title: str, author: str, genre: str, at: str, **extra: Any) -> dict:
        return {
            "book_id": book_id,
            "title": title,
            "author": author,
            "genre": genre,
            "borrowed_date": at,
            **extra,
        }

    def user(user_id: str, registered: str, plan: str | None, payments: list, activity: dict):
        return {
            "user_id": user_id,
            "account": {
                "registration_date": registered,
                "account_type": "premium" if plan else "standard",
                "subscription_status": "active" if plan else "none",
                "subscription_plan": plan,
                "payment_history": payments,
                "last_login": "2025-06-19T08:00:00Z",
                "login_frequency": "weekly",
                "devices": ["smartphone"],
                "communication_preferences": {"newsletters": plan is not None},
            },
            "profile": {
                "age_range": "25-34",
                "education_level": "bachelor",
                "profession": "teacher",
                "interests": ["fiction", "history"],
                "language_preferences": ["ukrainian", "english"],
            },
            "activity": activity,
        }

    shadows = ("b1", "Тіні забутих предків", "Михайло Коцюбинський", "fiction")
    dune = ("b3", "Dune", "Frank Herbert", "science_fiction")
    return {
        "users": [
            user(
                "u1",
                "2025-01-10T09:00:00Z",
                "monthly",
                [{"date": "2025-03-01", "amount": 99.0}, {"date": "2025-04-01", "amount": 99.0}],
                {
                    "books_borrowed": [
                        borrowed(
                            *shadows,
                            "2025-03-01T10:00:00Z",
                            return_date="2025-03-10T18:00:00Z",
                            completed=True,
                            rating=5,
                        ),
                        borrowed(*dune, "2025-04-02T12:00:00Z", completed=False),
                    ],
                    "reading_sessions": [
                        {
                            "book_id": "b1",
                            "date": "2025-03-02T20:00:00Z",
                            "duration_minutes": 45,
                            "pages_read": 30,
                            "device": "smartphone",
                        },
                    ],
                    "search_history": [
                        {"timestamp": "2025-02-28T19:00:00Z", "query": "Коцюбинський"}
                    ],
                },
            ),
            user(
                "u2",
                "2025-02-14T15:30:00Z",
                "annual",
                [{"date": "2025-03-15", "amount": 899.0}],
                {
                    "books_borrowed": [
                        borrowed(
                            *dune,
                            "2025-03-15T08:00:00Z",
                            return_date="2025-03-25T08:00:00Z",
                            completed=True,
                            rating=4,
                        ),
                        borrowed(
                            "b5", "Dune", "Frank Herbert", "science_fiction", "2025-05-01T08:00:00Z"
                        ),
                        borrowed(
                            "b2",
                            "Лісова пісня",
                            "Леся Українка",
                            "poetry",
                            "2025-05-03T09:00:00Z",
                            completed=True,
                            rating=5,
                        ),
                    ],
                    "reading_sessions": [
                        {
                            "book_id": "b5",
                            "date": "2025-05-02T21:15:00Z",
                            "duration_minutes": 60,
                            "pages_read": 40,
                            "device": "e-reader",
                        },
                    ],
                    "search_history": [{"timestamp": "2025-04-30T10:00:00Z", "query": "Dune"}],
                },
            ),
            user(
                "u3",
                "2025-06-01T12:00:00Z",
                None,
                [],
                {
                    "books_borrowed": [
                        borrowed(
                            "b4", "Тигролови", "Іван Багряний", "thriller", "2025-06-18T16:30:00Z"
                        ),
                    ],
                },
            ),
        ]
    }
