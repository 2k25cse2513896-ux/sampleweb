"""Point the app at a throwaway SQLite file before anything imports the engine."""

import os
from pathlib import Path

TEST_DB = Path(__file__).resolve().parent / "pytest_shop.db"
os.environ["DATABASE_URL"] = "sqlite:///" + str(TEST_DB).replace("\\", "/")
os.environ["SECRET_KEY"] = "pytest-secret-key-please-change"
os.environ["DEMO_MODE"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    if TEST_DB.exists():
        TEST_DB.unlink()
    wal = Path(str(TEST_DB) + "-wal")
    shm = Path(str(TEST_DB) + "-shm")
    if wal.exists():
        wal.unlink()
    if shm.exists():
        shm.unlink()
    with TestClient(app) as test_client:
        yield test_client
    if TEST_DB.exists():
        TEST_DB.unlink()


@pytest.fixture
def admin_token(client: TestClient) -> str:
    response = client.post(
        "/api/auth/admin/login",
        json={"email": "admin@demo.shop", "password": "Admin@123"},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


@pytest.fixture
def staff_token(client: TestClient) -> str:
    response = client.post(
        "/api/auth/admin/login",
        json={"email": "staff@demo.shop", "password": "Staff@123"},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])
