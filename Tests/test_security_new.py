"""
TestSphere AI — Security & Role-Based Access Control Integration Tests
Asserts that unauthorized access to ROLLBACK and DATA_CLEAR endpoints is correctly blocked.
"""
import sys
from pathlib import Path

# Add root folder to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import initialize_database

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Ensure database is initialized for security testing."""
    initialize_database()


def test_viewer_role_blocked_from_rollback():
    """VIEWER role must be forbidden from triggering emergency rollback strategy."""
    # Obtain VIEWER token
    login_res = client.post("/api/auth/login", json={"username": "viewer", "password": "View@123"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]

    # Attempt rollback
    rollback_payload = {
        "to_strategy": "LEGACY_FULL_SUITE",
        "reason": "Intruder attempt by viewer"
    }
    
    # Send request with token parameter in URL (as in apiFetch)
    res = client.post(f"/api/strategy/rollback?token={token}", json=rollback_payload)
    assert res.status_code == 403
    assert "Permission Denied" in res.json()["detail"]


def test_viewer_role_blocked_from_data_clear():
    """VIEWER role must be forbidden from deleting database records."""
    # Obtain VIEWER token
    login_res = client.post("/api/auth/login", json={"username": "viewer", "password": "View@123"})
    token = login_res.json()["token"]

    # Attempt to clear test coverage table
    res = client.delete(f"/api/data/test_coverage?token={token}")
    assert res.status_code == 403
    assert "Permission Denied" in res.json()["detail"]


def test_qa_engineer_role_blocked_from_rollback():
    """QA_ENGINEER role must be forbidden from triggering strategy rollback."""
    # Obtain QA_ENGINEER token
    login_res = client.post("/api/auth/login", json={"username": "qa", "password": "QA@123"})
    token = login_res.json()["token"]

    rollback_payload = {
        "to_strategy": "LEGACY_FULL_SUITE",
        "reason": "QA engineer attempts rollback"
    }
    res = client.post(f"/api/strategy/rollback?token={token}", json=rollback_payload)
    assert res.status_code == 403


def test_admin_role_allowed_rollback():
    """ADMIN role must have full authorized access to trigger rollback strategy."""
    # Obtain ADMIN token
    login_res = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@123"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]

    rollback_payload = {
        "to_strategy": "LEGACY_FULL_SUITE",
        "reason": "Authorized Admin Override"
    }
    res = client.post(f"/api/strategy/rollback?token={token}", json=rollback_payload)
    assert res.status_code == 200
    assert res.json()["success"] is True

    # Restore to SMART_SELECTOR
    restore_payload = {
        "to_strategy": "SMART_SELECTOR",
        "reason": "Authorized Admin Restore"
    }
    res_restore = client.post(f"/api/strategy/rollback?token={token}", json=restore_payload)
    assert res_restore.status_code == 200
