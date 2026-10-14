import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

# Defaults for running tests on the host against the dev compose database (port 5433).
# CI and the api container provide their own values.
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-0123456789abcdef0123")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://dss:dss@localhost:5433/dss")

from app.main import create_app  # imported after the environment defaults above


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(), raise_server_exceptions=False) as test_client:
        yield test_client
