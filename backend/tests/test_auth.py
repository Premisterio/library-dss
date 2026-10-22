"""Authentication flows, including regressions from the 2026-10-08 audit of the previous app."""

from collections.abc import Callable

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.v1.auth import REFRESH_COOKIE

PASSWORD = "correct horse battery"


def register(client: TestClient, email: str = "olena@example.com") -> dict:
    response = client.post(
        "/api/v1/auth/register", json={"email": email, "name": "Олена", "password": PASSWORD}
    )
    assert response.status_code == 201, response.text
    return response.json()


def login(client: TestClient, email: str = "olena@example.com", **extra: object) -> dict:
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD, **extra}
    )
    assert response.status_code == 200, response.text
    return response.json()


def me(client: TestClient, token: str) -> tuple[int, dict]:
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    return response.status_code, response.json()


def test_register_login_me(client: TestClient) -> None:
    created = register(client, "Olena@Example.com")
    assert created["email"] == "olena@example.com"  # normalised
    tokens = login(client, "OLENA@example.com")
    assert tokens["token_type"] == "bearer"
    assert tokens["refresh_token"] is None  # browsers get it only as a cookie
    status, body = me(client, tokens["access_token"])
    assert status == 200
    assert body["name"] == "Олена"


def test_refresh_cookie_is_http_only(client: TestClient) -> None:
    register(client)
    response = client.post(
        "/api/v1/auth/login", json={"email": "olena@example.com", "password": PASSWORD}
    )
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{REFRESH_COOKIE}=")
    assert "HttpOnly" in cookie
    assert "Path=/api/v1/auth" in cookie


def test_duplicate_email_is_a_conflict(client: TestClient) -> None:
    register(client)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "olena@example.com", "name": "x", "password": PASSWORD},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "auth.email_taken"


def test_short_password_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register", json={"email": "a@example.com", "name": "a", "password": "short"}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "request.invalid"


def test_registration_can_be_disabled(make_client: Callable[..., TestClient]) -> None:
    client = make_client(allow_registration=False)
    response = client.post(
        "/api/v1/auth/register", json={"email": "a@example.com", "name": "a", "password": PASSWORD}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "auth.registration_disabled"


def test_wrong_password(client: TestClient) -> None:
    register(client)
    response = client.post(
        "/api/v1/auth/login", json={"email": "olena@example.com", "password": "wrong password"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "auth.invalid_credentials"
    assert response.headers["www-authenticate"] == "Bearer"


def test_missing_token(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == "auth.not_authenticated"


@pytest.mark.parametrize("minutes", [5, 1440])
def test_access_token_lifetime_comes_from_settings(
    make_client: Callable[..., TestClient], minutes: int
) -> None:
    """Audit 2026-10-08: ACCESS_TOKEN_EXPIRE_MINUTES was ignored; tokens always lived 15 min."""
    client = make_client(access_token_minutes=minutes)
    register(client)
    tokens = login(client)
    claims = jwt.decode(tokens["access_token"], options={"verify_signature": False})
    assert claims["exp"] - claims["iat"] == minutes * 60
    assert tokens["expires_in"] == minutes * 60


def test_refresh_token_is_not_an_access_token(client: TestClient) -> None:
    """Audit 2026-10-08: a 7-day refresh token was accepted on every protected endpoint."""
    register(client)
    tokens = login(client, include_refresh_token=True)
    status, body = me(client, tokens["refresh_token"])
    assert status == 401
    assert body["code"] == "auth.token_invalid"


def test_access_token_cannot_refresh(client: TestClient) -> None:
    register(client)
    tokens = login(client)
    client.cookies.clear()
    response = client.post(
        "/api/v1/auth/refresh", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "auth.token_invalid"


def test_refresh_with_cookie(client: TestClient) -> None:
    register(client)
    login(client)  # the TestClient keeps the refresh cookie
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["refresh_token"] is None
    assert me(client, body["access_token"])[0] == 200


def test_refresh_with_bearer_for_cli(client: TestClient) -> None:
    register(client)
    tokens = login(client, include_refresh_token=True)
    client.cookies.clear()
    response = client.post(
        "/api/v1/auth/refresh", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["refresh_token"]


def test_logout_revokes_every_token(client: TestClient) -> None:
    register(client)
    tokens = login(client, include_refresh_token=True)
    response = client.post(
        "/api/v1/auth/logout", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert response.status_code == 204
    status, body = me(client, tokens["access_token"])
    assert status == 401
    assert body["code"] == "auth.token_revoked"
    client.cookies.clear()
    response = client.post(
        "/api/v1/auth/refresh", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}
    )
    assert response.status_code == 401


def test_nul_characters_are_rejected_not_crashing(client: TestClient) -> None:
    """Found by contract fuzzing: PostgreSQL text cannot hold NUL, which gave a 500."""
    login = client.post("/api/v1/auth/login", json={"email": "a\u0000b", "password": "x"})
    assert login.status_code == 422
    register = client.post(
        "/api/v1/auth/register",
        json={"email": "nul@example.com", "name": "a\u0000b", "password": PASSWORD},
    )
    assert register.status_code == 422
