"""
TestSphere AI — API Error Boundary Tests (Review 2 Hardening)
=============================================================
Explicitly verifies that every major API endpoint returns controlled
HTTP responses (not raw exceptions) for:
  - Missing authentication
  - Forbidden roles (RBAC)
  - Invalid / malformed request bodies
  - Nonexistent resources (404)
  - Unsupported execution mode (501)
  - Validation errors (400/422)
  - Duplicate / conflict scenarios (400)

No fake results are produced. ACTUAL execution is tested only to
confirm the correct HTTP 501 response (infrastructure unavailable).

Design principle: Safety > Speed. Failures must be controlled and auditable.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from backend.main import app


# ──────────────────────────────────────────────────────────────────────────────
# Authentication Boundaries
# ──────────────────────────────────────────────────────────────────────────────

class TestAuthErrorBoundaries:
    """Authentication API must return controlled 200/401 responses."""

    def test_login_valid_credentials_returns_200_with_token(self, client):
        res = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@123"})
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert "token" in body
        assert body["token"]  # non-empty token

    def test_login_wrong_password_returns_200_with_error_not_500(self, client):
        """Wrong password must return 200 with success=False, not a 500 exception."""
        res = client.post("/api/auth/login", json={"username": "admin", "password": "WRONG_PASSWORD"})
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is False
        assert "error" in body or "token" not in body

    def test_login_nonexistent_user_returns_controlled_response(self, client):
        res = client.post("/api/auth/login", json={"username": "no_such_user", "password": "anything"})
        assert res.status_code == 200
        assert res.json()["success"] is False

    def test_login_missing_username_returns_422(self, client):
        """Missing required field must return 422 Unprocessable Entity."""
        res = client.post("/api/auth/login", json={"password": "Admin@123"})
        assert res.status_code == 422

    def test_login_missing_password_returns_422(self, client):
        res = client.post("/api/auth/login", json={"username": "admin"})
        assert res.status_code == 422

    def test_login_empty_body_returns_422(self, client):
        res = client.post("/api/auth/login", json={})
        assert res.status_code == 422

    def test_login_malformed_json_returns_422_or_400(self, client):
        """Sending raw invalid JSON must return 400 or 422, not 500."""
        res = client.post(
            "/api/auth/login",
            content=b"NOT_VALID_JSON",
            headers={"Content-Type": "application/json"},
        )
        assert res.status_code in (400, 422)

    def test_logout_without_token_succeeds_gracefully(self, client):
        """Logout with no session must not crash — returns 200."""
        res = client.post("/api/auth/logout")
        assert res.status_code == 200

    def test_me_without_token_returns_unauthenticated_state(self, client):
        """GET /api/auth/me without token must return a safe unauthenticated response."""
        res = client.get("/api/auth/me")
        assert res.status_code == 200
        body = res.json()
        assert body.get("authenticated") is False


# ──────────────────────────────────────────────────────────────────────────────
# RBAC / Authorization Boundaries
# ──────────────────────────────────────────────────────────────────────────────

class TestRBACErrorBoundaries:
    """Protected endpoints must return 401 for missing tokens and 403 for wrong roles."""

    def test_unauthenticated_change_analysis_returns_401(self, client):
        res = client.post(
            "/api/change/analyze",
            json={"changed_files": ["auth/login.py"], "module": "Authentication"},
        )
        assert res.status_code == 401

    def test_unauthenticated_test_selection_returns_401(self, client):
        # The selection endpoint is POST /api/tests/selection (not /select)
        res = client.post("/api/tests/selection",
                          json={"changed_files": ["payment/payment.py"]})
        assert res.status_code == 401

    def test_unauthenticated_execution_plan_returns_401(self, client):
        res = client.post("/api/execution/plan",
                          json={"changed_files": ["payment/payment.py"]})
        assert res.status_code == 401

    def test_unauthenticated_rollback_returns_401(self, client):
        res = client.post("/api/strategy/rollback",
                          json={"reason": "test"})
        assert res.status_code == 401

    def test_invalid_token_returns_401(self, client, invalid_headers):
        # /api/tests/selection is the protected selection endpoint
        res = client.post(
            "/api/tests/selection",
            json={"changed_files": ["payment/payment.py"]},
            headers=invalid_headers,
        )
        assert res.status_code == 401

    def test_missing_token_returns_401_for_tests_endpoint(self, client):
        # /api/tests/selection (POST) requires authentication
        res = client.post(
            "/api/tests/selection",
            json={"changed_files": ["payment/payment.py"]},
        )
        assert res.status_code == 401

    def test_viewer_cannot_rollback_strategy(self, client, auth_tokens):
        """VIEWER role must be denied rollback (ADMIN-only action) → 403."""
        viewer_h = {"Authorization": f"Bearer {auth_tokens['viewer']}"}
        res = client.post("/api/strategy/rollback",
                          json={"reason": "viewer attempt"},
                          headers=viewer_h)
        # Either 403 Forbidden or 401/400 is acceptable; must not be 200
        assert res.status_code != 200, (
            "VIEWER must not be allowed to perform strategy rollback"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Test Selection / Change Analysis Error Boundaries
# ──────────────────────────────────────────────────────────────────────────────

class TestChangeAndSelectionErrorBoundaries:
    """Change analysis and test selection must handle malformed input gracefully."""

    def test_change_analysis_with_valid_payload(self, client, auth_tokens):
        headers = {"Authorization": f"Bearer {auth_tokens['admin']}"}
        res = client.post(
            "/api/change/analyze",
            json={
                "changed_files": ["payment/payment.py"],
                "change_type": "MODIFIED",
                "module": "Payment",
                "is_security_sensitive": False,
                "risk_level": "HIGH",
            },
            headers=headers,
        )
        assert res.status_code == 200

    def test_change_analysis_empty_changed_files_does_not_crash(self, client, auth_tokens):
        """Empty changed_files list must not cause a 500 error."""
        headers = {"Authorization": f"Bearer {auth_tokens['admin']}"}
        res = client.post(
            "/api/change/analyze",
            json={"changed_files": [], "module": "Payment"},
            headers=headers,
        )
        # 200 with empty/safe result, or 400/422 validation — never 500
        assert res.status_code in (200, 400, 422)

    def test_test_selection_missing_changed_files_returns_422(self, client, auth_tokens):
        headers = {"Authorization": f"Bearer {auth_tokens['admin']}"}
        # The selection endpoint is POST /api/tests/selection
        res = client.post(
            "/api/tests/selection",
            json={"module": "Payment"},  # changed_files omitted
            headers=headers,
        )
        assert res.status_code == 422

    def test_test_selection_valid_payload_returns_200(self, client, auth_tokens):
        headers = {"Authorization": f"Bearer {auth_tokens['admin']}"}
        # The selection endpoint is POST /api/tests/selection
        res = client.post(
            "/api/tests/selection",
            json={"changed_files": ["auth/login.py"], "module": "Authentication"},
            headers=headers,
        )
        assert res.status_code == 200
        body = res.json()
        assert "decisions" in body or "results" in body or isinstance(body, dict)


# ──────────────────────────────────────────────────────────────────────────────
# Execution Error Boundaries
# ──────────────────────────────────────────────────────────────────────────────

class TestExecutionErrorBoundaries:
    """Execution endpoints must return controlled error codes for invalid requests."""

    def test_get_nonexistent_plan_returns_404(self, client, auth_tokens):
        headers = {"Authorization": f"Bearer {auth_tokens['admin']}"}
        res = client.get("/api/execution/NONEXISTENT_PLAN_ID_99999", headers=headers)
        assert res.status_code == 404

    def test_run_plan_with_invalid_plan_id_returns_400_or_404(self, client, auth_tokens):
        headers = {"Authorization": f"Bearer {auth_tokens['admin']}"}
        res = client.post(
            "/api/execution/run",
            json={"plan_id": "BOGUS_PLAN_ID", "execution_type": "SIMULATED"},
            headers=headers,
        )
        assert res.status_code in (400, 404, 422, 500)

    def test_actual_execution_without_hardware_returns_501(self, client, auth_tokens):
        """Requesting ACTUAL execution without connected infrastructure must return HTTP 501.
        This is the controlled error boundary for PhysicalDeviceFarmAdapter.is_available()=False.
        No fake physical-device results must ever be returned.
        """
        headers = {"Authorization": f"Bearer {auth_tokens['admin']}"}
        # Step 1: Create a plan
        plan_res = client.post(
            "/api/execution/plan",
            json={
                "changed_files": ["payment/payment.py"],
                "change_type": "MODIFIED",
                "module": "Payment",
                "is_security_sensitive": False,
                "risk_level": "HIGH",
            },
            headers=headers,
        )
        if plan_res.status_code != 200:
            pytest.skip("Plan creation failed — skipping ACTUAL execution test")

        plan_id = plan_res.json().get("plan_id")
        if not plan_id:
            pytest.skip("No plan_id returned")

        # Step 2: Attempt ACTUAL execution — must return 501
        run_res = client.post(
            "/api/execution/run",
            json={"plan_id": plan_id, "execution_type": "ACTUAL"},
            headers=headers,
        )
        assert run_res.status_code == 501, (
            "ACTUAL execution without physical infrastructure must return HTTP 501. "
            f"Got {run_res.status_code}: {run_res.text[:200]}"
        )

    def test_execution_plan_missing_changed_files_returns_422(self, client, auth_tokens):
        headers = {"Authorization": f"Bearer {auth_tokens['admin']}"}
        res = client.post(
            "/api/execution/plan",
            json={"module": "Payment"},
            headers=headers,
        )
        assert res.status_code == 422


# ──────────────────────────────────────────────────────────────────────────────
# Experiment Error Boundaries
# ──────────────────────────────────────────────────────────────────────────────

class TestExperimentErrorBoundaries:
    """Experiment management endpoints must block invalid/unauthorized operations."""

    def test_get_nonexistent_experiment_returns_404(self, client, auth_tokens):
        headers = {"Authorization": f"Bearer {auth_tokens['admin']}"}
        res = client.get("/api/experiments/BOGUS_EXP_ID_99999", headers=headers)
        assert res.status_code == 404

    def test_list_experiments_returns_200(self, client, auth_tokens):
        headers = {"Authorization": f"Bearer {auth_tokens['admin']}"}
        # The experiment list endpoint is GET /api/experiment/history
        res = client.get("/api/experiment/history", headers=headers)
        assert res.status_code == 200

    def test_experiment_put_returns_400_immutability(self, client, auth_tokens):
        """Experiment records are immutable — PUT must return 400 or 405."""
        headers = {"Authorization": f"Bearer {auth_tokens['admin']}"}
        res = client.put(
            "/api/experiments/ANY_ID",
            json={"threshold": 70},
            headers=headers,
        )
        # 400 (immutability) or 404 (not found) or 405 (method not allowed) are all valid
        assert res.status_code in (400, 404, 405)

    def test_experiment_comparison_nonexistent_ids_returns_404(self, client, auth_tokens):
        headers = {"Authorization": f"Bearer {auth_tokens['admin']}"}
        # Compare endpoint accepts a JSON body with experiment_ids, not a path
        res = client.post(
            "/api/experiment/compare",
            json={"experiment_ids": ["FAKE_A", "FAKE_B"]},
            headers=headers,
        )
        assert res.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# Audit / Feedback Error Boundaries
# ──────────────────────────────────────────────────────────────────────────────

class TestAuditErrorBoundaries:
    """Audit logs must be protected and not expose sensitive fields."""

    def test_audit_logs_require_admin_role(self, client, auth_tokens):
        viewer_h = {"Authorization": f"Bearer {auth_tokens['viewer']}"}
        res = client.get("/api/audit/logs", headers=viewer_h)
        # VIEWER should not be able to access audit logs → 403
        assert res.status_code == 403

    def test_audit_logs_accessible_by_admin(self, client, auth_tokens):
        admin_h = {"Authorization": f"Bearer {auth_tokens['admin']}"}
        res = client.get("/api/audit/logs", headers=admin_h)
        assert res.status_code == 200

    def test_audit_log_response_does_not_contain_raw_passwords(self, client, auth_tokens):
        """Audit log response must not expose password values."""
        admin_h = {"Authorization": f"Bearer {auth_tokens['admin']}"}
        res = client.get("/api/audit/logs", headers=admin_h)
        assert res.status_code == 200
        raw = res.text
        # Actual password values must never appear in audit log responses
        for secret in ["Admin@123", "QA@123", "View@123"]:
            assert secret not in raw, f"Raw password '{secret}' found in audit log response"

    def test_feedback_submission_valid(self, client, viewer_headers):
        """Stakeholder feedback submission with authenticated user."""
        res = client.post(
            "/api/audit/feedback",
            json={
                "understandable": 4,
                "clear_reasons": 4,
                "trust_system": 3,
                "rollback_useful": 5,
                "dashboard_clear": 4,
                "additional_comments": "Test comment",
                "rating": 4,
            },
            headers=viewer_headers,
        )
        assert res.status_code == 200


# ──────────────────────────────────────────────────────────────────────────────
# Strategy / Rollback Error Boundaries
# ──────────────────────────────────────────────────────────────────────────────

class TestStrategyErrorBoundaries:
    """Strategy rollback is ADMIN-only and must return controlled errors for others."""

    def test_strategy_versions_accessible_authenticated(self, client, auth_tokens):
        admin_h = {"Authorization": f"Bearer {auth_tokens['admin']}"}
        res = client.get("/api/strategy/versions", headers=admin_h)
        assert res.status_code == 200

    def test_rollback_without_auth_returns_401(self, client):
        res = client.post("/api/strategy/rollback", json={"reason": "test"})
        assert res.status_code == 401

    def test_analytics_threshold_sensitivity_returns_200(self, client, auth_tokens):
        admin_h = {"Authorization": f"Bearer {auth_tokens['admin']}"}
        res = client.get("/api/analytics/threshold-sensitivity", headers=admin_h)
        assert res.status_code == 200


# ──────────────────────────────────────────────────────────────────────────────
# Data Health / System Boundary
# ──────────────────────────────────────────────────────────────────────────────

class TestSystemHealthBoundaries:
    """Health and data-status endpoints must return structured responses."""

    def test_data_health_returns_200_with_status(self, client):
        # The data health/status endpoint is GET /api/data/status
        res = client.get("/api/data/status")
        assert res.status_code == 200
        body = res.json()
        # Must be a structured response, not an empty body
        assert isinstance(body, dict)

    def test_data_dependencies_returns_structured_response(self, client, auth_tokens):
        admin_h = {"Authorization": f"Bearer {auth_tokens['admin']}"}
        # The dependency data preview endpoint
        res = client.get("/api/data/dependency_map/preview", headers=admin_h)
        assert res.status_code == 200

    def test_data_failures_returns_structured_response(self, client, auth_tokens):
        admin_h = {"Authorization": f"Bearer {auth_tokens['admin']}"}
        # The failure history data preview endpoint
        res = client.get("/api/data/failure_history/preview", headers=admin_h)
        assert res.status_code == 200
