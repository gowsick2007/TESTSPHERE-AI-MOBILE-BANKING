"""
TestSphere AI — FastAPI Endpoint Integration Tests
Verifies all REST API routes using TestClient with authenticated and unauthenticated assertions.
"""
import sys
from pathlib import Path

# Add root folder to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from API.main import app
from Engine.database import initialize_database
from Data_Generation.generate_dataset import generate_and_load


@pytest.fixture(scope="session", autouse=True)
def setup_api_db():
    """Ensure database is initialized and populated for API tests."""
    initialize_database()
    generate_and_load(verbose=False)


@pytest.fixture
def unauth_client():
    """Client with no authentication headers or session cookies."""
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_headers():
    """Obtain valid admin credentials without contaminating client cookies."""
    login_client = TestClient(app)
    res = login_client.post("/api/auth/login", json={"username": "admin", "password": "Admin@123"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    token = res.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    """Client for general testing."""
    return TestClient(app)


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"


def test_data_health_endpoint(client):
    res = client.get("/data-health")
    assert res.status_code == 200
    data = res.json()
    assert data["ready"] >= 4


def test_changes_endpoint(client):
    res = client.get("/changes")
    assert res.status_code == 200
    data = res.json()
    assert "changes" in data


def test_devices_endpoint(client):
    res = client.get("/devices")
    assert res.status_code == 200
    data = res.json()
    assert len(data["devices"]) > 0


def test_failure_stats_endpoint(client):
    res = client.get("/failure-stats")
    assert res.status_code == 200
    data = res.json()
    assert "total_failures" in data


def test_analyze_change_endpoint(client, unauth_client, auth_headers):
    payload = {
        "changed_files": ["payment/payment.py", "payment/payment_controller.py"],
        "change_type": "MODIFIED",
        "module": "Payment",
        "is_security_sensitive": False,
        "risk_level": "HIGH"
    }
    # Unauthenticated should fail with 401
    unauth_res = unauth_client.post("/analyze-change", json=payload)
    assert unauth_res.status_code == 401

    # Authenticated succeeds
    res = client.post("/analyze-change", json=payload, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "affected_modules" in data
    assert "Payment" in data["affected_modules"]


def test_test_selection_endpoint(client, unauth_client, auth_headers):
    payload = {
        "changed_files": ["payment/payment.py"],
        "change_type": "MODIFIED",
        "module": "Payment",
        "is_security_sensitive": False,
        "risk_level": "HIGH"
    }
    # Unauthenticated should fail with 401
    unauth_res = unauth_client.post("/test-selection", json=payload)
    assert unauth_res.status_code == 401

    res = client.post("/test-selection", json=payload, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "decisions" in data
    assert "summary" in data


def test_run_baseline_endpoint(client, unauth_client, auth_headers):
    # Unauthenticated should fail with 401
    unauth_res = unauth_client.post("/run-baseline")
    assert unauth_res.status_code == 401

    res = client.post("/run-baseline", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["strategy"] == "LEGACY_FULL_SUITE"
    assert data["total_tests"] > 0


def test_run_smart_endpoint(client, unauth_client, auth_headers):
    payload = {
        "changed_files": ["payment/payment.py"],
        "change_type": "MODIFIED",
        "module": "Payment",
        "is_security_sensitive": False,
        "risk_level": "HIGH"
    }
    # Unauthenticated should fail with 401
    unauth_res = unauth_client.post("/run-smart", json=payload)
    assert unauth_res.status_code == 401

    res = client.post("/run-smart", json=payload, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "selection" in data
    assert "execution" in data


def test_experiment_endpoint(client, unauth_client, auth_headers):
    payload = {
        "changed_files": ["payment/payment.py"],
        "change_type": "MODIFIED",
        "module": "Payment",
        "is_security_sensitive": False,
        "risk_level": "HIGH"
    }
    # Unauthenticated should fail with 401
    unauth_res = unauth_client.post("/experiment", json=payload)
    assert unauth_res.status_code == 401

    res = client.post("/experiment", json=payload, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "comparison" in data
    assert "quality" in data


def test_failure_scenarios_endpoint(client):
    res = client.get("/failure-scenarios")
    assert res.status_code == 200
    data = res.json()
    assert "scenarios" in data


def test_run_failure_scenarios_endpoint(client, unauth_client, auth_headers):
    # Unauthenticated should fail with 401
    unauth_res = unauth_client.post("/run-failure-scenarios")
    assert unauth_res.status_code == 401

    res = client.post("/run-failure-scenarios", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "results" in data


def test_strategy_endpoints(client, unauth_client, auth_headers):
    # Get strategy is public
    res = client.get("/strategy")
    assert res.status_code == 200
    data = res.json()
    assert "current_strategy" in data

    # Rollback requires auth
    payload = {
        "to_strategy": "LEGACY_FULL_SUITE",
        "reason": "API test rollback",
        "changed_by": "api_test"
    }
    unauth_res = unauth_client.post("/rollback", json=payload)
    assert unauth_res.status_code == 401

    res = client.post("/rollback", json=payload, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True

    # Check that current strategy changed
    res = client.get("/strategy")
    assert res.json()["current_strategy"] == "LEGACY_FULL_SUITE"

    # Restore
    payload["to_strategy"] = "SMART_SELECTOR"
    payload["reason"] = "API test restore"
    res = client.post("/rollback", json=payload, headers=auth_headers)
    assert res.status_code == 200

    res = client.get("/strategy")
    assert res.json()["current_strategy"] == "SMART_SELECTOR"


def test_audit_log_endpoint(client):
    res = client.get("/audit-log")
    assert res.status_code == 200
    data = res.json()
    assert "logs" in data


def test_what_if_endpoint(client, unauth_client, auth_headers):
    payload = {
        "module": "Payment",
        "device": "Pixel 8",
        "change_type": "MODIFIED"
    }
    # Unauthenticated should fail with 401
    unauth_res = unauth_client.post("/what-if", json=payload)
    assert unauth_res.status_code == 401

    res = client.post("/what-if", json=payload, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "potentially_affected_tests" in data
    assert "estimated_runtime_minutes" in data
