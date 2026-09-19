"""
TestSphere AI — Security Misuse & Negative Authorization Tests
Asserts strict 401 (unauthenticated / invalid token) vs 403 (unauthorized role)
across all protected mutation and analysis endpoints.
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import initialize_database

client = TestClient(app)

SAMPLE_CHANGE = {
    "changed_files": ["auth/login.py"],
    "change_type": "MODIFIED",
    "module": "Authentication",
    "is_security_sensitive": True,
    "risk_level": "HIGH"
}

SAMPLE_WHATIF = {
    "module": "Authentication",
    "device": "Pixel 8",
    "change_type": "MODIFIED",
    "risk_level": "HIGH",
    "is_security_sensitive": True
}


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    initialize_database()


@pytest.fixture(scope="module")
def tokens():
    # Obtain tokens for all roles
    res_admin = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@123"})
    assert res_admin.status_code == 200
    admin_tok = res_admin.json()["token"]

    res_qa = client.post("/api/auth/login", json={"username": "qa", "password": "QA@123"})
    assert res_qa.status_code == 200
    qa_tok = res_qa.json()["token"]

    res_viewer = client.post("/api/auth/login", json={"username": "viewer", "password": "View@123"})
    assert res_viewer.status_code == 200
    viewer_tok = res_viewer.json()["token"]

    return {
        "admin": admin_tok,
        "qa": qa_tok,
        "viewer": viewer_tok,
    }


# ============================================================================
# 1. Negative Tests: Missing or Invalid Authentication -> HTTP 401
# ============================================================================

@pytest.mark.parametrize("endpoint,method,payload", [
    ("/api/change/analyze", "POST", SAMPLE_CHANGE),
    ("/api/change/register", "POST", SAMPLE_CHANGE),
    ("/api/tests/selection", "POST", SAMPLE_CHANGE),
    ("/api/tests/run-smart", "POST", SAMPLE_CHANGE),
    ("/api/tests/run-baseline", "POST", None),
    ("/api/experiment/run", "POST", SAMPLE_CHANGE),
    ("/api/experiment/run-scenarios", "POST", None),
    ("/api/data/demo", "POST", None),
    ("/api/strategy/rollback", "POST", {"to_strategy": "LEGACY_FULL_SUITE", "reason": "test"}),
    ("/api/what-if", "POST", SAMPLE_WHATIF),
])
def test_unauthenticated_requests_return_401(endpoint, method, payload):
    """Endpoints requiring authentication must reject unauthenticated requests with 401."""
    if method == "POST":
        res = client.post(endpoint, json=payload)
    elif method == "DELETE":
        res = client.delete(endpoint)
    else:
        res = client.get(endpoint)

    assert res.status_code == 401, f"{endpoint} expected 401, got {res.status_code}"
    detail = res.json().get("detail", "")
    assert "unauthorized" in detail.lower() or "token" in detail.lower()


def test_invalid_token_returns_401():
    """Supplying an invalid/malformed token must return 401."""
    res = client.post(
        "/api/change/analyze",
        headers={"Authorization": "Bearer invalid_secret_token_12345"},
        json=SAMPLE_CHANGE
    )
    assert res.status_code == 401

    res2 = client.post(
        "/api/tests/selection?token=bogus_token_xyz",
        json=SAMPLE_CHANGE
    )
    assert res2.status_code == 401


# ============================================================================
# 2. Negative Tests: Authenticated but Unauthorized -> HTTP 403
# ============================================================================

def test_viewer_blocked_from_register_change(tokens):
    """VIEWER role cannot register code changes."""
    res = client.post(
        f"/api/change/register?token={tokens['viewer']}",
        json=SAMPLE_CHANGE
    )
    assert res.status_code == 403
    assert "Permission Denied" in res.json().get("detail", "")


def test_viewer_blocked_from_run_smart(tokens):
    """VIEWER role cannot execute smart test runner."""
    res = client.post(
        f"/api/tests/run-smart?token={tokens['viewer']}",
        json=SAMPLE_CHANGE
    )
    assert res.status_code == 403


def test_viewer_blocked_from_run_baseline(tokens):
    """VIEWER role cannot execute baseline regression suite."""
    res = client.post(f"/api/tests/run-baseline?token={tokens['viewer']}")
    assert res.status_code == 403


def test_viewer_blocked_from_experiment_run(tokens):
    """VIEWER role cannot run experiment benchmark."""
    res = client.post(
        f"/api/experiment/run?token={tokens['viewer']}",
        json=SAMPLE_CHANGE
    )
    assert res.status_code == 403


def test_viewer_blocked_from_experiment_scenarios(tokens):
    """VIEWER role cannot run failure mode simulations."""
    res = client.post(f"/api/experiment/run-scenarios?token={tokens['viewer']}")
    assert res.status_code == 403


def test_viewer_blocked_from_rollback(tokens):
    """VIEWER role cannot execute strategy rollback."""
    res = client.post(
        f"/api/strategy/rollback?token={tokens['viewer']}",
        json={"to_strategy": "LEGACY_FULL_SUITE", "reason": "Unauthorized attempt"}
    )
    assert res.status_code == 403


def test_qa_blocked_from_rollback(tokens):
    """QA_ENGINEER role is strictly forbidden from emergency strategy rollback."""
    res = client.post(
        f"/api/strategy/rollback?token={tokens['qa']}",
        json={"to_strategy": "LEGACY_FULL_SUITE", "reason": "QA attempts rollback"}
    )
    assert res.status_code == 403
    assert "ADMINISTRATORS only" in res.json().get("detail", "")


def test_viewer_blocked_from_load_demo(tokens):
    """VIEWER role cannot load demo synthetic dataset."""
    res = client.post(f"/api/data/demo?token={tokens['viewer']}")
    assert res.status_code == 403


def test_viewer_blocked_from_delete_dataset(tokens):
    """VIEWER role cannot delete dataset tables."""
    res = client.delete(f"/api/data/code_changes?token={tokens['viewer']}")
    assert res.status_code == 403


# ============================================================================
# 3. Positive Tests: Authorized Roles Succeed -> HTTP 200
# ============================================================================

def test_viewer_allowed_read_analysis(tokens):
    """VIEWER is authorized to inspect change impact and test selection."""
    res_ana = client.post(f"/api/change/analyze?token={tokens['viewer']}", json=SAMPLE_CHANGE)
    assert res_ana.status_code == 200

    res_sel = client.post(f"/api/tests/selection?token={tokens['viewer']}", json=SAMPLE_CHANGE)
    assert res_sel.status_code == 200

    res_wif = client.post(f"/api/what-if?token={tokens['viewer']}", json=SAMPLE_WHATIF)
    assert res_wif.status_code == 200


def test_qa_engineer_allowed_mutation_and_execution(tokens):
    """QA_ENGINEER is authorized for testing, experiments, and change registration."""
    res_reg = client.post(f"/api/change/register?token={tokens['qa']}", json=SAMPLE_CHANGE)
    assert res_reg.status_code == 200
    assert res_reg.json().get("success") is True

    res_exp = client.post(f"/api/experiment/run-scenarios?token={tokens['qa']}")
    assert res_exp.status_code == 200


def test_admin_allowed_full_control(tokens):
    """ADMIN is authorized for all administrative actions including rollback."""
    res_roll = client.post(
        f"/api/strategy/rollback?token={tokens['admin']}",
        json={"to_strategy": "LEGACY_FULL_SUITE", "reason": "Admin test switch"}
    )
    assert res_roll.status_code == 200

    # Restore to SMART_SELECTOR
    res_res = client.post(
        f"/api/strategy/rollback?token={tokens['admin']}",
        json={"to_strategy": "SMART_SELECTOR", "reason": "Admin test restore"}
    )
    assert res_res.status_code == 200


# ============================================================================
# 4. Public Endpoints: Remain Public Without Authentication -> HTTP 200
# ============================================================================

@pytest.mark.parametrize("endpoint", [
    "/health",
    "/data-health",
    "/api/health",
    "/api/data/status",
    "/api/data/template/test_coverage",
    "/api/data/test_coverage/preview",
    "/api/strategy",
    "/api/audit-log",
    "/api/experiment/scenarios",
])
def test_public_endpoints_accessible_without_token(endpoint):
    """Public discovery and status endpoints must remain unauthenticated."""
    res = client.get(endpoint)
    assert res.status_code == 200, f"Expected 200 for public endpoint {endpoint}, got {res.status_code}"
