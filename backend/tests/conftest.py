import os
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any

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
from app.ingest import reader
from app.ingest.frames import ParsedDataset
from app.main import create_app
from app.models import Analyst
from app.services import auth
from app.worker import runner

if TYPE_CHECKING:
    from libsim.engine import Result

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
def _simulation() -> Result:
    from libsim import engine
    from libsim.params import preset

    return engine.simulate(preset("demo", users=200, months=8, seed=11))


@cache
def _simulated_tabular() -> dict[str, Any]:
    from libsim import writer

    return writer.build_dataset(_simulation())


@pytest.fixture
def tabular_document() -> dict[str, Any]:
    """A small libsim dataset (200 members, 8 months); safe to modify in a test."""
    return copy.deepcopy(_simulated_tabular())


@pytest.fixture(scope="session")
def tabular_dataset() -> ParsedDataset:
    """`tabular_document` parsed once and shared, so never modify its frames."""
    return reader.parse(copy.deepcopy(_simulated_tabular()))


@pytest.fixture(scope="session")
def tabular_truth() -> dict[str, Any]:
    """libsim's ground truth of `tabular_document`, to check the domain against what it planted."""
    from libsim import writer

    return writer.build_ground_truth(_simulation())


@pytest.fixture
def nested_document() -> dict[str, Any]:
    """A hand-made nested-format file: 3 users, 5 book ids with 4 distinct titles, 6 loans."""

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


@pytest.fixture
def mini_document() -> dict[str, Any]:
    """A hand-made tabular dataset (5 members, as of 2026-03-31, Kyiv) with known analytics.

    Expected values are derived in tests/test_analytics.py; keep both in sync.
    """
    from app.ingest.schema import TABLES

    rows: dict[str, list[list[Any]]] = {name: [] for name in TABLES}
    rows["users"] = [
        ["u1", "2025-10-05T09:00:00Z", "25-34", "master", "uk+en", True, ["fantasy"]],
        ["u2", "2025-11-10T09:00:00Z", "18-24", "student", "uk", True, ["science_fiction"]],
        ["u3", "2026-01-15T09:00:00Z", "35-44", "bachelor", "uk", False, ["history"]],
        ["u4", "2026-03-20T09:00:00Z", "25-34", "bachelor", "uk+en", True, ["fantasy"]],
        ["u5", "2025-10-01T09:00:00Z", "65+", "phd", "uk", False, ["classics"]],
    ]
    rows["books"] = [
        ["b1", "Кобзар", "Тарас Шевченко", "poetry_drama", "uk", 300, 1840, 2],
        ["b2", "Dune", "Frank Herbert", "science_fiction", "en", 600, 1965, 1],
        ["b3", "Тигролови", "Іван Багряний", "mystery_thriller", "uk", 280, 1944, 1],
        ["b4", "Лісова пісня", "Леся Українка", "poetry_drama", "uk", 150, 1911, 1],
    ]
    rows["subscription_periods"] = [
        [
            "u1",
            "monthly",
            "2026-01-05T21:00:00Z",
            "2026-02-04T21:00:00Z",
            149,
            149,
            None,
            "renewed",
        ],
        [
            "u1",
            "monthly",
            "2026-02-04T21:00:00Z",
            "2026-03-06T21:00:00Z",
            149,
            149,
            None,
            "renewed",
        ],
        ["u1", "monthly", "2026-03-06T21:00:00Z", "2026-04-05T21:00:00Z", 149, 119.2, 0.2, "open"],
        ["u2", "student", "2026-02-10T22:00:00Z", "2026-03-12T22:00:00Z", 79, 79, None, "churned"],
        ["u3", "trial", "2026-01-15T22:00:00Z", "2026-01-29T22:00:00Z", 0, 0, None, "converted"],
        ["u3", "annual", "2026-01-29T22:00:00Z", "2027-01-29T22:00:00Z", 1290, 1290, None, "open"],
        ["u4", "trial", "2026-03-20T22:00:00Z", "2026-04-03T21:00:00Z", 0, 0, None, "open"],
        ["u5", "trial", "2025-10-01T21:00:00Z", "2025-10-15T21:00:00Z", 0, 0, None, "expired"],
    ]
    rows["loans"] = [
        ["l1", "u1", "b1", "2026-03-02T10:00:00Z", "2026-03-12T10:00:00Z", True, 5, False],
        ["l2", "u1", "b2", "2026-03-20T18:00:00Z", None, None, None, False],
        ["l3", "u2", "b2", "2026-02-12T10:00:00Z", "2026-03-01T10:00:00Z", False, 3, False],
        ["l4", "u3", "b3", "2026-03-25T08:00:00Z", None, None, None, True],
        ["l5", "u4", "b1", "2026-03-21T12:00:00Z", "2026-03-28T12:00:00Z", True, 4, False],
        ["l6", "u3", "b1", "2025-12-20T10:00:00Z", "2026-01-05T10:00:00Z", True, 4, False],
    ]
    rows["reading_sessions"] = [
        ["u1", "b1", "2026-03-03T17:00:00Z", 40, 30, "mobile_android"],  # Tue 19:00 Kyiv
        ["u1", "b1", "2026-03-04T17:30:00Z", 30, 25, "mobile_android"],  # Wed 19:30
        ["u1", "b2", "2026-03-21T06:00:00Z", 60, 50, "mobile_android"],  # Sat 08:00
        ["u4", "b1", "2026-03-22T19:00:00Z", 45, 40, "mobile_ios"],  # Sun 21:00
        ["u3", "b3", "2026-03-30T06:00:00Z", 50, 45, "desktop"],  # Mon 09:00 (summer time)
        ["u2", "b2", "2026-02-15T12:00:00Z", 20, 15, "e_reader"],  # Sun 14:00
    ]
    rows["searches"] = [
        ["u1", "2026-03-01T22:00:00Z", "Кобзар", 1],
        ["u2", "2026-03-05T09:00:00Z", "Дюна", 0],
        ["u4", "2026-03-20T10:00:00Z", "дюна ", 0],
        ["u3", "2026-02-20T10:00:00Z", "Багряний", 1],
    ]
    rows["holds"] = [
        ["h1", "u3", "b3", "2026-03-10T08:00:00Z", "2026-03-25T08:00:00Z", "fulfilled"],
        ["h2", "u2", "b2", "2026-03-05T10:00:00Z", "2026-03-26T10:00:00Z", "lapsed"],
        ["h3", "u4", "b2", "2026-03-28T10:00:00Z", None, "open"],
    ]
    return {
        "schema_version": 2,
        "meta": {"as_of": "2026-03-31", "timezone": "Europe/Kyiv", "seed": 0},
        "tables": {
            name: {"columns": [col for col, _, _ in spec], "rows": rows[name]}
            for name, spec in TABLES.items()
        },
    }


@pytest.fixture
def churn_document() -> dict[str, Any]:
    """A hand-made tabular dataset (6 members, as of 2026-06-30, Kyiv) for the churn target.

    Expected features and labels are derived in tests/test_churn_features.py; keep both in sync.
    Rows marked "later" happen after the cutoff of 2026-05-31 and must not change its features.
    """
    from app.ingest.schema import TABLES

    rows: dict[str, list[list[Any]]] = {name: [] for name in TABLES}
    rows["users"] = [
        ["u1", "2026-02-20T09:00:00Z", "25-34", "master", "uk+en", True, ["fantasy"]],
        ["u2", "2026-04-24T09:00:00Z", "18-24", "student", "uk", False, ["science_fiction"]],
        ["u3", "2026-01-10T09:00:00Z", "45-54", "bachelor", "uk", True, ["history"]],
        ["u4", "2026-05-01T09:00:00Z", "35-44", "phd", "uk+en", True, ["business"]],
        ["u5", "2026-04-01T09:00:00Z", "55-64", "secondary", "uk", False, ["classics"]],
        ["u6", "2026-05-25T09:00:00Z", "16-17", "secondary", "uk", True, ["young_adult"]],
    ]
    rows["books"] = [
        ["b1", "Кобзар", "Тарас Шевченко", "poetry_drama", "uk", 300, 1840, 2],
        ["b2", "Dune", "Frank Herbert", "science_fiction", "en", 600, 1965, 1],
        ["b3", "Тигролови", "Іван Багряний", "mystery_thriller", "uk", 280, 1944, 1],
        ["b4", "Лісова пісня", "Леся Українка", "poetry_drama", "uk", 150, 1911, 1],
    ]

    def period(user: str, plan: str, start: str, end: str, paid: float, outcome: str) -> list:
        price = {"trial": 0, "monthly": 149, "student": 79, "annual": 1290}[plan]
        discount = round(1 - paid / price, 2) if price and paid < price else None
        return [user, plan, f"{start}Z", f"{end}Z", price, paid, discount, outcome]

    rows["subscription_periods"] = [
        period("u1", "monthly", "2026-03-03T21:00:00", "2026-04-02T21:00:00", 149, "renewed"),
        period("u1", "monthly", "2026-04-02T21:00:00", "2026-05-02T21:00:00", 149, "renewed"),
        period("u1", "monthly", "2026-05-02T21:00:00", "2026-06-01T21:00:00", 119.2, "renewed"),
        period("u1", "monthly", "2026-06-01T21:00:00", "2026-07-01T21:00:00", 149, "open"),
        period("u2", "trial", "2026-04-24T21:00:00", "2026-05-08T21:00:00", 0, "converted"),
        period("u2", "student", "2026-05-08T21:00:00", "2026-06-07T21:00:00", 79, "churned"),
        period("u3", "annual", "2026-01-10T22:00:00", "2027-01-10T22:00:00", 1290, "open"),
        period("u4", "monthly", "2026-05-10T21:00:00", "2026-06-09T21:00:00", 149, "renewed"),
        period("u4", "monthly", "2026-06-09T21:00:00", "2026-07-09T21:00:00", 119.2, "open"),
        period("u5", "monthly", "2026-05-12T21:00:00", "2026-06-11T21:00:00", 149, "churned"),
        period("u6", "trial", "2026-05-25T21:00:00", "2026-06-08T21:00:00", 0, "converted"),
        period("u6", "monthly", "2026-06-08T21:00:00", "2026-07-08T21:00:00", 149, "open"),
    ]
    rows["loans"] = [
        ["l1", "u1", "b1", "2026-04-15T09:00:00Z", "2026-04-28T09:00:00Z", True, 5, False],
        ["l2", "u1", "b2", "2026-05-05T09:00:00Z", "2026-05-21T09:00:00Z", False, 2, False],
        ["l3", "u1", "b3", "2026-05-25T09:00:00Z", "2026-06-08T09:00:00Z", True, 4, False],
        ["l4", "u1", "b4", "2026-06-10T09:00:00Z", None, None, None, True],  # later
        ["l5", "u2", "b2", "2026-06-02T09:00:00Z", "2026-06-07T20:59:00Z", False, None, False],
    ]
    rows["reading_sessions"] = [
        ["u1", "b1", "2026-04-20T18:00:00Z", 60, 50, "mobile_android"],
        ["u1", "b2", "2026-05-10T18:00:00Z", 50, 40, "mobile_android"],
        ["u1", "b2", "2026-05-20T18:00:00Z", 40, 35, "mobile_android"],
        ["u1", "b3", "2026-05-30T18:00:00Z", 30, 25, "mobile_android"],
        ["u1", "b3", "2026-05-31T21:00:00Z", 70, 60, "mobile_android"],  # at the cutoff
        ["u1", "b3", "2026-06-05T18:00:00Z", 80, 70, "mobile_android"],  # later
        ["u2", "b2", "2026-06-03T18:00:00Z", 20, 15, "mobile_ios"],  # later
        ["u3", "b1", "2026-05-15T18:00:00Z", 30, 20, "desktop"],
    ]
    rows["searches"] = [
        ["u1", "2026-04-25T09:00:00Z", "Лісова пісня", 2],
        ["u1", "2026-05-15T09:00:00Z", "Дюна", 0],
        ["u1", "2026-05-29T22:00:00Z", "Кобзар", 3],  # 05-30 01:00 in Kyiv
        ["u1", "2026-05-31T21:00:00Z", "Тигролови", 0],  # at the cutoff
        ["u2", "2026-04-28T09:00:00Z", "Дюна", 0],
    ]
    rows["holds"] = [
        ["h1", "u1", "b4", "2026-04-20T09:00:00Z", "2026-05-11T09:00:00Z", "lapsed"],
        ["h2", "u1", "b4", "2026-05-28T09:00:00Z", "2026-06-10T09:00:00Z", "fulfilled"],
        ["h3", "u2", "b1", "2026-05-10T09:00:00Z", "2026-06-01T09:00:00Z", "lapsed"],
    ]
    rows["campaigns"] = [
        [
            "camp-1",
            "Утримання підписників",
            "2026-05-15T00:00:00Z",
            "2026-06-15T00:00:00Z",
            "randomized_at_renewal",
            ["control", "email", "discount"],
        ]
    ]
    rows["campaign_assignments"] = [
        ["camp-1", "u4", "2026-06-02T07:00:00Z", "discount", True, 0.2, "2026-06-09T21:00:00Z"],
        ["camp-1", "u5", "2026-06-04T07:00:00Z", "email", False, 0, "2026-06-11T21:00:00Z"],
    ]
    return {
        "schema_version": 2,
        "meta": {"as_of": "2026-06-30", "timezone": "Europe/Kyiv", "seed": 0},
        "tables": {
            name: {"columns": [col for col, _, _ in spec], "rows": rows[name]}
            for name, spec in TABLES.items()
        },
    }
