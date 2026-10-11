"""Smoke tests for the customer-facing commerce flows added after the foundation phase."""

from fastapi.testclient import TestClient


def test_assistant_under_budget_phrase(client: TestClient) -> None:
    response = client.post("/api/assistant", json={"text": "2000 tak ke earbuds"})
    assert response.status_code == 200
    assert response.json()["parsed"]["budget"] == 2000
    assert len(response.json()["products"]) > 0


def test_customer_demo_otp_and_quote(client: TestClient) -> None:
    phone = "9876599999"
    requested = client.post("/api/auth/customer/request-otp", json={"phone": phone})
    assert requested.status_code == 200
    code = requested.json()["demo_otp"]
    verified = client.post(
        "/api/auth/customer/verify-otp",
        json={"phone": phone, "code": code, "name": "Commerce Test"},
    )
    assert verified.status_code == 200
    headers = {"Authorization": "Bearer " + verified.json()["access_token"]}
    product = client.get("/api/products?page_size=1").json()["items"][0]
    quote = client.post(
        "/api/cart/quote",
        headers=headers,
        json={"items": [{"product_id": product["id"], "qty": 1}], "fulfilment": "pickup_15min"},
    )
    assert quote.status_code == 200
    assert type(quote.json()["total"]) is int
