"""
TestSphere AI — Register Change API Test
Verifies the /api/change/register endpoint via TestClient.
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import initialize_database

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    initialize_database()


def test_register_change_endpoint():
    login_res = client.post("/api/auth/login", json={"username": "qa", "password": "QA@123"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]

    payload = {
        "changed_files": ["payment/payment_service.py"],
        "change_type": "MODIFIED",
        "module": "payment",
        "is_security_sensitive": True,
        "risk_level": "HIGH"
    }
    res = client.post(f"/api/change/register?token={token}", json=payload)
    assert res.status_code == 200
    assert res.json().get("success") is True

