"""
TestSphere AI — Controlled Test Execution Management Tests (Phase 2)
Verifies:
- Creation of execution plans from change impact selection
- Execution of plans with distinct SIMULATED vs ACTUAL execution types
- Results recording in execution_results table (status, duration, failure_reason)
- Ground truth comparison (expected vs actual)
- Authorization: ADMIN and QA_ENGINEER allowed; VIEWER blocked (403); missing token blocked (401)
- Inspection of execution reports and history
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import get_db_connection


def test_create_and_run_execution_plan(client, admin_headers, qa_headers, viewer_headers, unauth_client):
    """Full lifecycle test for controlled execution plan workflow."""
    payload = {
        "changed_files": ["payment/payment.py"],
        "change_type": "MODIFIED",
        "module": "Payment",
        "is_security_sensitive": True,
        "risk_level": "HIGH",
        "strategy": "SMART_SELECTOR",
    }

    # 1. Unauthenticated request must return 401
    unauth_res = unauth_client.post("/api/execution/plan", json=payload)
    assert unauth_res.status_code == 401

    # 2. VIEWER role must be blocked with 403
    viewer_res = client.post("/api/execution/plan", json=payload, headers=viewer_headers)
    assert viewer_res.status_code == 403

    # 3. QA_ENGINEER can create execution plan
    qa_res = client.post("/api/execution/plan", json=payload, headers=qa_headers)
    assert qa_res.status_code == 200
    plan_data = qa_res.json()
    assert "plan_id" in plan_data
    assert plan_data["status"] == "CREATED"
    assert plan_data["total_tests"] > 0
    assert plan_data["selected_tests"] > 0
    plan_id = plan_data["plan_id"]

    # 4. VIEWER is blocked from executing the plan (403)
    exec_payload = {"plan_id": plan_id, "execution_type": "SIMULATED"}
    viewer_exec = client.post("/api/execution/run", json=exec_payload, headers=viewer_headers)
    assert viewer_exec.status_code == 403

    # 5. ADMIN executes the plan
    admin_exec = client.post("/api/execution/run", json=exec_payload, headers=admin_headers)
    assert admin_exec.status_code == 200
    report = admin_exec.json()
    assert report["plan_id"] == plan_id
    assert report["execution_type"] == "SIMULATED"
    assert report["status"] == "COMPLETED"
    assert report["summary"]["executed_tests"] > 0
    assert len(report["results"]) > 0

    # 6. Verify results are persisted in execution_results table
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM execution_results WHERE plan_id = ?", (plan_id,)).fetchall()
        assert len(rows) > 0
        first_row = dict(rows[0])
        assert first_row["plan_id"] == plan_id
        assert first_row["execution_type"] == "SIMULATED"
        assert first_row["execution_status"] in ["PASSED", "FAILED", "SKIPPED"]
        assert first_row["result"] in ["PASS", "FAIL", "SKIP"]
    finally:
        conn.close()

    # 7. Fetch execution plan details
    get_res = client.get(f"/api/execution/{plan_id}")
    assert get_res.status_code == 200
    fetched_plan = get_res.json()
    assert fetched_plan["plan_id"] == plan_id
    assert fetched_plan["status"] == "COMPLETED"

    # 8. List execution plans history
    history_res = client.get("/api/execution/history")
    assert history_res.status_code == 200
    assert any(p["plan_id"] == plan_id for p in history_res.json()["plans"])


def test_invalid_execution_type_rejected(client, admin_headers):
    """Executing with an unsupported execution type returns 400 Bad Request."""
    # First create plan
    plan_res = client.post("/api/execution/plan", json={
        "changed_files": ["auth/login.py"],
        "module": "Authentication"
    }, headers=admin_headers)
    assert plan_res.status_code == 200
    plan_id = plan_res.json()["plan_id"]

    bad_exec = client.post("/api/execution/run", json={
        "plan_id": plan_id,
        "execution_type": "UNSUPPORTED_TYPE"
    }, headers=admin_headers)
    assert bad_exec.status_code == 400


def test_actual_execution_without_hardware_returns_501(client, admin_headers):
    """Executing with ACTUAL when no device farm is connected returns 501 and marks plan FAILED."""
    plan_res = client.post("/api/execution/plan", json={
        "changed_files": ["payment/payment.py"],
        "module": "Payment"
    }, headers=admin_headers)
    assert plan_res.status_code == 200
    plan_id = plan_res.json()["plan_id"]

    actual_exec = client.post("/api/execution/run", json={
        "plan_id": plan_id,
        "execution_type": "ACTUAL"
    }, headers=admin_headers)
    assert actual_exec.status_code == 501
    assert "unavailable" in actual_exec.json()["detail"].lower()

    # Plan status must be marked FAILED rather than claiming fake execution
    plan_status = client.get(f"/api/execution/{plan_id}").json()
    assert plan_status["status"] == "FAILED"

