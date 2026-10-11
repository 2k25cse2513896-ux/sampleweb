"""Shop identity comes from the settings table, not from components."""

from fastapi.testclient import TestClient


def test_public_settings_have_shop_identity(client: TestClient) -> None:
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["shop_name"] == "TECH TOYS"
    assert data["phone"] == "+916307001812"
    assert data["timing"] == "10 AM to 10 PM"
    assert "upi_id" in data


def test_staff_cannot_edit_settings(client: TestClient, staff_token: str) -> None:
    response = client.put(
        "/api/admin/settings",
        headers={"Authorization": "Bearer " + staff_token},
        json={"items": [{"key": "shop_name", "value": "Hacked"}]},
    )
    assert response.status_code == 403


def test_admin_can_edit_and_restore(client: TestClient, admin_token: str) -> None:
    headers = {"Authorization": "Bearer " + admin_token}
    response = client.put(
        "/api/admin/settings",
        headers=headers,
        json={"items": [{"key": "tagline", "value": "pytest tagline"}]},
    )
    assert response.status_code == 200
    public = client.get("/api/settings").json()
    assert public["tagline"] == "pytest tagline"
    restore = client.put(
        "/api/admin/settings",
        headers=headers,
        json={"items": [{"key": "tagline", "value": "Gadgets that last. Advice you can trust."}]},
    )
    assert restore.status_code == 200
