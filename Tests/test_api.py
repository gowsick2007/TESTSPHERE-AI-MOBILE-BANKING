"""
TestSphere AI — FastAPI Endpoint Integration Tests
Verifies all REST API routes using TestClient.
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

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def setup_api_db():
    """Ensure database is initialized and populated for API tests."""
    initialize_database()
    generate_and_load(verbose=False)


def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"


def test_data_health_endpoint():
    res = client.get("/data-health")
    assert res.status_code == 200
    data = res.json()
    assert data["ready"] >= 4


def test_changes_endpoint():
    res = client.get("/changes")
    assert res.status_code == 200
    data = res.json()
    assert "changes" in data


def test_devices_endpoint():
    res = client.get("/devices")
    assert res.status_code == 200
    data = res.json()
    assert len(data["devices"]) > 0


def test_failure_stats_endpoint():
    res = client.get("/failure-stats")
    assert res.status_code == 200
    data = res.json()
    assert "total_failures" in data


def test_analyze_change_endpoint():
    payload = {
        "changed_files": ["payment/payment.py", "payment/payment_controller.py"],
        "change_type": "MODIFIED",
        "module": "Payment",
        "is_security_sensitive": False,
        "risk_level": "HIGH"
    }
    res = client.post("/analyze-change", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "affected_modules" in data
    assert "Payment" in data["affected_modules"]


def test_test_selection_endpoint():
    payload = {
        "changed_files": ["payment/payment.py"],
        "change_type": "MODIFIED",
        "module": "Payment",
        "is_security_sensitive": False,
        "risk_level": "HIGH"
    }
    res = client.post("/test-selection", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "decisions" in data
    assert "summary" in data


def test_run_baseline_endpoint():
    res = client.post("/run-baseline")
    assert res.status_code == 200
    data = res.json()
    assert data["strategy"] == "LEGACY_FULL_SUITE"
    assert data["total_tests"] > 0


def test_run_smart_endpoint():
    payload = {
        "changed_files": ["payment/payment.py"],
        "change_type": "MODIFIED",
        "module": "Payment",
        "is_security_sensitive": False,
        "risk_level": "HIGH"
    }
    res = client.post("/run-smart", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "selection" in data
    assert "execution" in data


def test_experiment_endpoint():
    payload = {
        "changed_files": ["payment/payment.py"],
        "change_type": "MODIFIED",
        "module": "Payment",
        "is_security_sensitive": False,
        "risk_level": "HIGH"
    }
    res = client.post("/experiment", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "comparison" in data
    assert "quality" in data


def test_failure_scenarios_endpoint():
    res = client.get("/failure-scenarios")
    assert res.status_code == 200
    data = res.json()
    assert "scenarios" in data


def test_run_failure_scenarios_endpoint():
    res = client.post("/run-failure-scenarios")
    assert res.status_code == 200
    data = res.json()
    assert "results" in data


def test_strategy_endpoints():
    # Get strategy
    res = client.get("/strategy")
    assert res.status_code == 200
    data = res.json()
    assert "current_strategy" in data

    # Rollback
    payload = {
        "to_strategy": "LEGACY_FULL_SUITE",
        "reason": "API test rollback",
        "changed_by": "api_test"
    }
    res = client.post("/rollback", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True

    # Check that current strategy changed
    res = client.get("/strategy")
    assert res.json()["current_strategy"] == "LEGACY_FULL_SUITE"

    # Restore
    payload["to_strategy"] = "SMART_SELECTOR"
    payload["reason"] = "API test restore"
    res = client.post("/rollback", json=payload)
    assert res.status_code == 200

    res = client.get("/strategy")
    assert res.json()["current_strategy"] == "SMART_SELECTOR"


def test_audit_log_endpoint():
    res = client.get("/audit-log")
    assert res.status_code == 200
    data = res.json()
    assert "logs" in data


def test_what_if_endpoint():
    payload = {
        "module": "Payment",
        "device": "Pixel 8",
        "change_type": "MODIFIED"
    }
    res = client.post("/what-if", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "potentially_affected_tests" in data
    assert "estimated_runtime_minutes" in data
