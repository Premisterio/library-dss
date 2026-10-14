import re

from fastapi.testclient import TestClient

from app.domain.enums import ENUMS


def test_enums_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/meta/enums")
    assert response.status_code == 200
    enums = response.json()["enums"]
    assert set(enums) == set(ENUMS)
    assert {"code": "fantasy", "label": "Фентезі"} in enums["genre"]


def test_genres_match_the_simulator() -> None:
    from libsim.catalog.genres import GENRES

    assert ENUMS["genre"] == GENRES


def test_labels_are_ukrainian_not_russian() -> None:
    russian = re.compile(r"[ЁёЪъЫыЭэ]")
    for values in ENUMS.values():
        for label in values.values():
            assert label.strip()
            assert not russian.search(label), label
