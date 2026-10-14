"""The OpenAPI document is the contract for every client; keep it well-formed."""

import re
from typing import Any

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


@pytest.fixture(scope="module")
def operations() -> list[dict[str, Any]]:
    settings = Settings.model_construct(database_url="unused", secret_key=SecretStr("x" * 32))
    schema = create_app(settings).openapi()
    return [
        op
        for path_item in schema["paths"].values()
        for method, op in path_item.items()
        if method in HTTP_METHODS
    ]


def test_all_routes_are_versioned() -> None:
    settings = Settings.model_construct(database_url="unused", secret_key=SecretStr("x" * 32))
    paths = create_app(settings).openapi()["paths"]
    assert paths, "no documented routes"
    assert all(path.startswith("/api/v1/") for path in paths)


def test_operation_ids_are_unique_snake_case(operations: list[dict[str, Any]]) -> None:
    ids = [op["operationId"] for op in operations]
    assert len(ids) == len(set(ids))
    assert all(SNAKE_CASE.match(op_id) for op_id in ids), ids


def test_every_operation_documents_problem_errors(operations: list[dict[str, Any]]) -> None:
    for op in operations:
        default = op["responses"].get("default")
        assert default is not None, op["operationId"]
        assert "Problem" in str(default), op["operationId"]
