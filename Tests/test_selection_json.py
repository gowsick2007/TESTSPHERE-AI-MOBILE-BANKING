"""
TestSphere AI — Selection API JSON Validation Tests
Verifies that the /api/tests/selection endpoint always returns valid, machine-parseable
JSON conforming to SelectionResponse, and that control characters (newlines, tabs,
quotes, backslashes, Unicode) never corrupt the JSON serialization.
"""
import json
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


@pytest.fixture(scope="module")
def auth_header():
    res = client.post("/api/auth/login", json={"username": "qa", "password": "QA@123"})
    assert res.status_code == 200
    token = res.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_selection_endpoint_valid_json(auth_header):
    """1. Authorized request succeeds, returns 200, parses cleanly with response.json()."""
    payload = {
        "changed_files": ["auth/login.py"],
        "change_type": "MODIFIED",
        "module": "Authentication",
        "is_security_sensitive": True,
        "risk_level": "HIGH"
    }
    res = client.post("/api/tests/selection", json=payload, headers=auth_header)
    assert res.status_code == 200

    # Verify response body is machine-parseable JSON
    data = res.json()
    assert isinstance(data, dict)

    # Verify expected top-level keys exist
    expected_keys = {"change_context", "dependency_info", "coverage_info", "failure_info", "decisions", "summary"}
    assert expected_keys.issubset(set(data.keys())), f"Missing keys in response: {expected_keys - set(data.keys())}"

    # Verify decisions structure
    decisions = data["decisions"]
    assert isinstance(decisions, list)
    assert len(decisions) > 0

    for d in decisions[:10]:
        assert "test_id" in d
        assert "test_name" in d
        assert "decision" in d
        assert d["decision"] in ["RUN", "SKIP"]
        assert "risk_score" in d
        assert "rationale" in d
        # Rationale must be a clean string
        assert isinstance(d["rationale"], str)
        assert len(d["rationale"]) > 0


def test_selection_json_special_characters_resilience(auth_header):
    """Verifies that newlines, tabs, double quotes, backslashes, and Unicode in inputs do not corrupt JSON."""
    tricky_payload = {
        "changed_files": [
            'payment/payment"test.py',
            "auth/login\nwith\nnewlines.py",
            "otp/service\twith\ttabs.py",
            r"device\security\backslash.py",
            "biometrics/café_auth_🚀.py"
        ],
        "change_type": 'MODIFIED "CRITICAL"\nPATCH',
        "module": 'Payment & Auth\t\n"Special"',
        "is_security_sensitive": True,
        "risk_level": "HIGH"
    }

    res = client.post("/api/tests/selection", json=tricky_payload, headers=auth_header)
    assert res.status_code == 200

    # Ensure response.text is valid JSON
    raw_text = res.text
    parsed = json.loads(raw_text)
    assert isinstance(parsed, dict)
    assert "decisions" in parsed

    for d in parsed["decisions"]:
        assert isinstance(d["rationale"], str)
        assert isinstance(d["test_name"], str)
