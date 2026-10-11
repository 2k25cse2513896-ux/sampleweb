"""Categories, brands, products CRUD and public search."""

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import SessionLocal
from app.models.base import Base
from app.models.entities import Product
from app.services.seed import seed_if_empty


def test_lists_seeded_catalogue(client: TestClient) -> None:
    cats = client.get("/api/categories")
    brands = client.get("/api/brands")
    products = client.get("/api/products?page_size=60")
    assert cats.status_code == 200
    assert brands.status_code == 200
    assert products.status_code == 200
    assert len(cats.json()) == 8
    names = []
    for row in brands.json():
        names.append(row["name"])
    assert "boAt" in names
    assert "Sony" in names
    assert products.json()["total"] >= 60


def test_search_earbuds(client: TestClient) -> None:
    response = client.get("/api/products", params={"q": "earbuds"})
    assert response.status_code == 200
    assert response.json()["total"] > 0


def test_startup_seed_is_idempotent(client: TestClient) -> None:
    db = SessionLocal()
    try:
        before = db.query(Product).count()
        seed_if_empty(db)
        after = db.query(Product).count()
        assert before > 0
        assert after == before
    finally:
        db.close()


def test_empty_production_startup_seed_is_idempotent(tmp_path) -> None:
    """An empty database gets one catalogue and a second startup adds nothing."""
    engine = create_engine("sqlite:///" + str(tmp_path / "startup_seed.db").replace("\\", "/"))
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(bind=engine)
    db = test_session()
    try:
        inserted = seed_if_empty(db, "ProductionTestPassword123!")
        first_count = db.query(Product).count()
        repeated = seed_if_empty(db, "ProductionTestPassword123!")
        second_count = db.query(Product).count()
        assert inserted == first_count
        assert inserted > 0
        assert repeated == 0
        assert second_count == first_count
    finally:
        db.close()
        engine.dispose()


def test_staff_cannot_change_price(client: TestClient, staff_token: str) -> None:
    listed = client.get("/api/products", params={"page_size": 1})
    product_id = listed.json()["items"][0]["id"]
    response = client.put(
        "/api/admin/products/" + str(product_id),
        headers={"Authorization": "Bearer " + staff_token},
        json={"price": 1},
    )
    assert response.status_code == 403


def test_admin_create_and_deactivate(
    client: TestClient, admin_token: str
) -> None:
    cats = client.get("/api/categories").json()
    brands = client.get("/api/brands").json()
    payload = {
        "sku": "TEST-NEW-1",
        "name": "Test cable",
        "slug": "test-cable-phase1",
        "description": "Created by pytest.",
        "category_id": cats[0]["id"],
        "brand_id": brands[0]["id"],
        "price": 199,
        "mrp": 299,
        "cost_price": 80,
        "stock_qty": 5,
        "specs_json": "{\"color\":\"black\"}",
    }
    created = client.post(
        "/api/admin/products",
        headers={"Authorization": "Bearer " + admin_token},
        json=payload,
    )
    assert created.status_code == 200
    body = created.json()
    assert body["stock_qty"] == 5
    assert body["price"] == 199
    deleted = client.delete(
        "/api/admin/products/" + str(body["id"]),
        headers={"Authorization": "Bearer " + admin_token},
    )
    assert deleted.status_code == 200


def test_admin_product_crud_stock_image_and_hinglish_quick_add(
    client: TestClient, admin_token: str
) -> None:
    headers = {"Authorization": "Bearer " + admin_token}
    cats = client.get("/api/categories").json()
    brands = client.get("/api/brands").json()
    payload = {
        "sku": "CRUD-FULL-1",
        "name": "CRUD cable",
        "slug": "crud-full-cable",
        "description": "Before update",
        "category_id": cats[4]["id"],
        "brand_id": brands[0]["id"],
        "price": 199,
        "mrp": 299,
        "cost_price": 80,
        "stock_qty": 2,
    }
    created = client.post("/api/admin/products", headers=headers, json=payload)
    assert created.status_code == 200
    product = created.json()
    assert product["stock_qty"] == 2

    read = client.get("/api/products/" + product["slug"])
    assert read.status_code == 200
    assert read.json()["id"] == product["id"]

    updated = client.put(
        "/api/admin/products/" + str(product["id"]),
        headers=headers,
        json={"name": "CRUD cable updated", "price": 249, "mrp": 349},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "CRUD cable updated"
    assert updated.json()["price"] == 249

    stock = client.post(
        "/api/admin/stock",
        headers=headers,
        json={"product_id": product["id"], "change_qty": 3, "reason": "pytest"},
    )
    assert stock.status_code == 200
    assert stock.json()["stock_qty"] == 5

    image_bytes = BytesIO()
    Image.new("RGB", (20, 20), "#3B82F6").save(image_bytes, format="PNG")
    image = client.post(
        "/api/admin/products/" + str(product["id"]) + "/images",
        headers=headers,
        files={"file": ("crud.png", image_bytes.getvalue(), "image/png")},
    )
    assert image.status_code == 200
    assert len(image.json()["images"]) == 1

    quick = client.post(
        "/api/admin/products/from-prompt",
        headers=headers,
        json={"prompt": "boAt Airdopes 141 earbuds price 999 mrp 1499 stock 20"},
    )
    assert quick.status_code == 200
    quick_body = quick.json()
    assert quick_body["name"] == "boAt Airdopes 141"
    assert quick_body["price"] == 999
    assert quick_body["mrp"] == 1499
    assert quick_body["stock_qty"] == 20
    assert len(quick_body["images"]) == 1

    deleted = client.delete("/api/admin/products/" + str(product["id"]), headers=headers)
    assert deleted.status_code == 200
    assert client.get("/api/products/" + product["slug"]).json()["is_active"] is False
