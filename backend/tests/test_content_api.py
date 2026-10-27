"""The content decision through the API: evaluation under judgements and a budget, the checks on
judgements, and approval as a decision (a report of kind `content`) that exports like any
report."""

from collections import Counter
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.enums import ENUMS
from app.services import auth

Headers = dict[str, str]
BUDGET = {"budget": 3000, "max_per_genre": 2}
CONSISTENT = [  # demand_searches 3× genre_loans and 3× author_loans; the rest equal
    {"criterion": "demand_searches", "compared_with": "genre_loans", "value": 3},
    {"criterion": "demand_searches", "compared_with": "author_loans", "value": 3},
]
# Each says the next criterion beats the one before, round in a circle.
CIRCULAR = [
    {"criterion": "demand_searches", "compared_with": "author_loans", "value": 9},
    {"criterion": "author_loans", "compared_with": "genre_loans", "value": 9},
    {"criterion": "genre_loans", "compared_with": "demand_searches", "value": 9},
]


@pytest.fixture
def dataset(
    import_document: Callable[[dict[str, Any]], dict[str, Any]],
    tabular_document: dict[str, Any],
) -> dict[str, Any]:
    return import_document(tabular_document)


def evaluate(client: TestClient, headers: Headers, dataset_id: int, **body: Any) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/datasets/{dataset_id}/content/evaluate", headers=headers, json=body
    )
    assert response.status_code == 200, response.text
    return response.json()


def kpis(section: dict[str, Any]) -> dict[str, Any]:
    return {kpi["key"]: kpi["value"] for kpi in section["kpis"]}


def chart(section: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return next(c["rows"] for c in section["charts"] if c["key"] == key)


def test_equal_weights_rank_every_title_and_fill_the_budget(
    client: TestClient, auth_headers: Headers, dataset: dict[str, Any]
) -> None:
    section = evaluate(client, auth_headers, dataset["id"], **BUDGET)
    assert section["key"] == "content_portfolio"
    assert [note["code"] for note in section["notes"]] == ["content.equal_weights"]
    weights = chart(section, "criterion_weights")
    assert [row["weight"] for row in weights] == pytest.approx([0.25] * 4)
    assert all(row["stable_from"] <= row["weight"] <= row["stable_to"] for row in weights)
    ranking = chart(section, "title_ranking")
    assert len(ranking) == 60  # libsim offers 60 titles
    assert [row["rank_topsis"] for row in ranking] == sorted(row["rank_topsis"] for row in ranking)
    chosen = [row for row in ranking if row["choice"] == "licensed"]
    found = kpis(section)
    assert found["consistency_ratio"] == 0
    assert found["portfolio_titles"] == len(chosen) > 0
    assert found["portfolio_spend"] == pytest.approx(sum(row["license_cost"] for row in chosen))
    assert found["portfolio_spend"] <= 3000
    assert max(Counter(row["genre"] for row in chosen).values()) <= 2
    assert all(0 <= row["stability"] <= 1 for row in ranking)
    assert chart(section, "inconsistent_judgements") == []


def test_judgements_move_the_weights(
    client: TestClient, auth_headers: Headers, dataset: dict[str, Any]
) -> None:
    section = evaluate(client, auth_headers, dataset["id"], judgements=CONSISTENT, **BUDGET)
    weights = {row["criterion"]: row["weight"] for row in chart(section, "criterion_weights")}
    assert weights["demand_searches"] == max(weights.values())
    assert weights["genre_loans"] == pytest.approx(weights["author_loans"])
    assert section["notes"] == []
    assert kpis(section)["consistency_ratio"] < 0.1


def test_inconsistent_judgements_are_named_and_cannot_be_approved(
    client: TestClient, auth_headers: Headers, dataset: dict[str, Any]
) -> None:
    section = evaluate(client, auth_headers, dataset["id"], judgements=CIRCULAR, **BUDGET)
    assert kpis(section)["consistency_ratio"] > 0.1
    assert [note["code"] for note in section["notes"]] == ["content.inconsistent"]
    named = chart(section, "inconsistent_judgements")
    assert 0 < len(named) <= 3
    response = client.post(
        f"/api/v1/datasets/{dataset['id']}/content/approve",
        headers=auth_headers,
        json={"title": "Закупівля", "decision": {"judgements": CIRCULAR, **BUDGET}},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "content.inconsistent"


def test_approval_freezes_a_decision(
    client: TestClient, auth_headers: Headers, dataset: dict[str, Any]
) -> None:
    body = {"title": "Закупівля, жовтень", "decision": {"judgements": CONSISTENT, **BUDGET}}
    approved = client.post(
        f"/api/v1/datasets/{dataset['id']}/content/approve", headers=auth_headers, json=body
    )
    assert approved.status_code == 201, approved.text
    report = approved.json()
    assert (report["kind"], report["sections"]) == ("content", ["content_portfolio"])
    assert report["params"]["budget"] == 3000
    assert report["params"]["judgements"][0] == CONSISTENT[0]
    listed = client.get("/api/v1/reports", headers=auth_headers, params={"kind": "content"})
    assert [item["id"] for item in listed.json()["items"]] == [report["id"]]
    detail = client.get(f"/api/v1/reports/{report['id']}", headers=auth_headers).json()
    shown = evaluate(client, auth_headers, dataset["id"], judgements=CONSISTENT, **BUDGET)
    assert kpis(detail["content"][0]) == kpis(shown)
    for fmt in ("pdf", "xlsx", "csv", "json"):
        export = client.get(
            f"/api/v1/reports/{report['id']}/export",
            headers=auth_headers,
            params={"format": fmt},
        )
        assert export.status_code == 200, (fmt, export.text)


def test_every_code_of_the_decision_has_a_label(
    client: TestClient, auth_headers: Headers, dataset: dict[str, Any]
) -> None:
    section = evaluate(client, auth_headers, dataset["id"], judgements=CIRCULAR, **BUDGET)
    assert section["key"] in ENUMS["analytics_section"]
    for kpi in section["kpis"]:
        assert kpi["key"] in ENUMS["metric"], kpi["key"]
    for drawn in section["charts"]:
        assert drawn["key"] in ENUMS["chart"], drawn["key"]
        for column in drawn["dimensions"] + drawn["attributes"]:
            assert column["key"] in ENUMS["dimension"], column["key"]
            if column["enum"]:
                values = {row[column["key"]] for row in drawn["rows"]}
                assert values <= set(ENUMS[column["enum"]]), (drawn["key"], values)
        for measure in drawn["measures"]:
            assert measure["key"] in ENUMS["metric"], measure["key"]


def test_a_dataset_without_an_offer_or_another_owner(
    client: TestClient,
    auth_headers: Headers,
    db_session: Session,
    dataset: dict[str, Any],
    import_document: Callable[[dict[str, Any]], dict[str, Any]],
    nested_document: dict[str, Any],
) -> None:
    nested = import_document(nested_document)
    response = client.post(
        f"/api/v1/datasets/{nested['id']}/content/evaluate", headers=auth_headers, json=BUDGET
    )
    assert response.status_code == 409
    assert response.json()["code"] == "content.no_candidates"

    auth.create_analyst(db_session, email="other@example.com", name="Інша", password="x" * 12)
    login = client.post(
        "/api/v1/auth/login", json={"email": "other@example.com", "password": "x" * 12}
    )
    other = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.post(
        f"/api/v1/datasets/{dataset['id']}/content/evaluate", headers=other, json=BUDGET
    )
    assert response.status_code == 404


def test_inputs_are_checked(
    client: TestClient, auth_headers: Headers, dataset: dict[str, Any]
) -> None:
    url = f"/api/v1/datasets/{dataset['id']}/content/evaluate"
    same = {"criterion": "genre_loans", "compared_with": "genre_loans", "value": 3}
    beyond = {"criterion": "genre_loans", "compared_with": "author_loans", "value": 10}
    for body in (
        {"budget": -1},
        {},
        {"budget": 100, "judgements": [same]},
        {"budget": 100, "judgements": [beyond]},
        {"budget": 100, "max_per_genre": 0},
    ):
        response = client.post(url, headers=auth_headers, json=body)
        assert response.status_code == 422, body
