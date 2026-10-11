"""Admin JWT login, refresh, and role walls."""

from fastapi.testclient import TestClient


def test_login_wrong_password(client: TestClient) -> None:
    response = client.post(
        "/api/auth/admin/login",
        json={"email": "admin@demo.shop", "password": "wrong"},
    )
    assert response.status_code == 401
    body = response.json()
    assert "error" in body
    assert "code" in body["error"]


def test_login_and_me(client: TestClient, admin_token: str) -> None:
    me = client.get("/api/auth/me", headers={"Authorization": "Bearer " + admin_token})
    assert me.status_code == 200
    data = me.json()
    assert data["email"] == "admin@demo.shop"
    assert data["role"] == "admin"


def test_refresh(client: TestClient) -> None:
    login = client.post(
        "/api/auth/admin/login",
        json={"email": "admin@demo.shop", "password": "Admin@123"},
    )
    refresh = login.json()["refresh_token"]
    again = client.post("/api/auth/admin/refresh", json={"refresh_token": refresh})
    assert again.status_code == 200
    assert "access_token" in again.json()
