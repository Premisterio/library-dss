"""Contract fuzzing with Schemathesis: no request to any operation, valid or not, may get a 500,
and every response must match the documented schema, status codes and headers."""

import pytest
import schemathesis
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, settings
from schemathesis.checks import CheckFunction, positive_data_acceptance

Headers = dict[str, str]

# Registration also rejects syntactically valid e-mails on reserved domains (.test, .local, …),
# which the `email` format of the schema cannot express.
EXCLUDED_CHECKS: dict[str, list[CheckFunction]] = {
    "POST /api/v1/auth/register": [positive_data_acceptance],
}


@pytest.fixture
def api_schema(client: TestClient) -> schemathesis.BaseSchema:
    return schemathesis.openapi.from_asgi("/api/v1/openapi.json", client.app)


schema = schemathesis.pytest.from_fixture("api_schema")


@schema.parametrize()
@settings(max_examples=15, deadline=None, suppress_health_check=list(HealthCheck))
def test_api_contract(case: schemathesis.Case, auth_headers: Headers) -> None:
    case.call_and_validate(
        headers=auth_headers, excluded_checks=EXCLUDED_CHECKS.get(case.operation.label, [])
    )
