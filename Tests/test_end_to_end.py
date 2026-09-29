"""
TestSphere AI — Master End-to-End Acceptance Test (Phase 2 / 70% Milestone)
Executes the complete end-to-end lifecycle on an isolated database:
1. Database initialization & canonical dataset loading
2. Authentication & RBAC verification (ADMIN, QA_ENGINEER, VIEWER)
3. Change registration & impact analysis
4. Test selection with explainable rationales
5. Execution plan creation and controlled execution
6. Threshold sensitivity & failure scenario evaluation
7. Immutable experiment creation & delta comparison
8. What-if simulation without mutating active configuration
9. Strategy versioning & atomic rollback
10. Secret-redacted audit trail verification
11. Structured stakeholder feedback collection
"""
import pytest
import uuid
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import get_db_connection


def test_full_master_end_to_end_lifecycle(client, admin_headers, qa_headers, viewer_headers, unauth_client):
    # ── 1. Authenticated sessions check ──────────────────────────────────────
    me_admin = client.get("/api/auth/me", headers=admin_headers)
    assert me_admin.status_code == 200
    assert me_admin.json()["role"] == "ADMIN"

    me_qa = client.get("/api/auth/me", headers=qa_headers)
    assert me_qa.status_code == 200
    assert me_qa.json()["role"] == "QA_ENGINEER"

    me_viewer = client.get("/api/auth/me", headers=viewer_headers)
    assert me_viewer.status_code == 200
    assert me_viewer.json()["role"] == "VIEWER"

    # Seed clean canonical demo dataset
    demo_res = client.post("/api/data/demo", headers=admin_headers)
    assert demo_res.status_code == 200

    # ── 2. Register & Analyze a Code Change ───────────────────────────────────
    change_payload = {
        "changed_files": ["payment/payment.py"],
        "change_type": "MODIFIED",
        "module": "Payment",
        "is_security_sensitive": True,
        "risk_level": "HIGH"
    }

    # VIEWER blocked from registering change
    res_reg_viewer = client.post("/api/change/register", json=change_payload, headers=viewer_headers)
    assert res_reg_viewer.status_code == 403

    # QA allowed to register change
    res_reg = client.post("/api/change/register", json=change_payload, headers=qa_headers)
    assert res_reg.status_code == 200
    assert res_reg.json()["success"] is True

    # Analyze change
    res_an = client.post("/api/change/analyze", json=change_payload, headers=qa_headers)
    assert res_an.status_code == 200
    assert "change_context" in res_an.json()
    dep_impact = res_an.json()["dependency_impact"]
    assert "direct" in dep_impact

    # ── 3. Test Selection with Explainable Rationales ─────────────────────────
    res_sel = client.post("/api/tests/selection", json=change_payload, headers=qa_headers)
    assert res_sel.status_code == 200
    sel_data = res_sel.json()
    assert "decisions" in sel_data
    assert len(sel_data["decisions"]) > 0

    # Verify every decision has a human-readable rationale and valid score
    for dec in sel_data["decisions"]:
        assert dec["decision"] in ["RUN", "SKIP"]
        assert isinstance(dec["risk_score"], (int, float))
        assert len(dec["rationale"]) > 5

    # ── 4. Create Execution Plan & Run Simulated ──────────────────────────────
    plan_payload = {
        "change_id": "CHG-E2E-001",
        "changed_files": ["payment/payment.py"],
        "strategy": "SMART_SELECTOR"
    }
    plan_res = client.post("/api/execution/plan", json=plan_payload, headers=qa_headers)
    assert plan_res.status_code == 200
    plan_id = plan_res.json()["plan_id"]
    assert plan_res.json()["status"] == "CREATED"

    run_res = client.post("/api/execution/run", json={
        "plan_id": plan_id,
        "execution_type": "SIMULATED"
    }, headers=qa_headers)
    assert run_res.status_code == 200
    assert run_res.json()["status"] == "COMPLETED"

    # Inspect plan details
    plan_get = client.get(f"/api/execution/{plan_id}")
    assert plan_get.status_code == 200
    assert len(plan_get.json()["results"]) > 0

    # ── 5. Multi-Threshold Sensitivity Evaluation ────────────────────────────
    eval_res = client.get("/api/analytics/threshold-sensitivity?change_id=CHG001")
    assert eval_res.status_code == 200
    eval_data = eval_res.json()
    assert "threshold_evaluations" in eval_data
    assert len(eval_data["threshold_evaluations"]) == 5

    # Verify baseline threshold 50 is evaluated
    th50 = next(e for e in eval_data["threshold_evaluations"] if e["threshold"] == 50)
    assert th50["recall"] >= 0.99
    assert th50["verdict"] == "ACCEPTED"

    # ── 6. Immutable Experiment Creation & Compare ───────────────────────────
    res_exp1 = client.post("/api/experiment/create", json={
        "scenario": "PAYMENT_REFACTOR_A",
        "changed_files": ["payment/payment.py"],
        "module": "Payment",
        "threshold": 50.0,
        "seed": 12345
    }, headers=qa_headers)
    assert res_exp1.status_code == 200
    exp1_id = res_exp1.json()["experiment_id"]

    res_exp2 = client.post("/api/experiment/create", json={
        "scenario": "PAYMENT_REFACTOR_B",
        "changed_files": ["auth/login.py"],
        "module": "Authentication",
        "threshold": 50.0,
        "seed": 12345
    }, headers=qa_headers)
    assert res_exp2.status_code == 200
    exp2_id = res_exp2.json()["experiment_id"]

    # Immutability lock test (PUT returns 400)
    put_res = client.put(f"/api/experiment/{exp1_id}", json={"precision": 0.99}, headers=qa_headers)
    assert put_res.status_code == 400

    # Compare experiments
    comp_res = client.post("/api/experiment/compare", json={
        "experiment_ids": [exp1_id, exp2_id]
    }, headers=qa_headers)
    assert comp_res.status_code == 200
    assert comp_res.json()["total_compared"] == 2

    # ── 7. What-If Analysis (Does NOT mutate active config) ───────────────────
    strat_before = client.get("/api/strategy").json()["current_strategy"]
    whatif_res = client.post("/api/what-if", json={
        "module": "Payment",
        "device": "Pixel 8",
        "change_type": "MODIFIED",
        "risk_level": "HIGH",
        "is_security_sensitive": True
    }, headers=qa_headers)
    assert whatif_res.status_code == 200
    strat_after = client.get("/api/strategy").json()["current_strategy"]
    assert strat_before == strat_after

    # ── 8. Strategy Versioning & Atomic Rollback ──────────────────────────────
    v_id = f"v2-e2e-{uuid.uuid4().hex[:6]}"
    res_v = client.post("/api/strategy/versions", json={
        "version_id": v_id,
        "strategy_name": "SMART_SELECTOR_V2",
        "threshold": 52.0,
        "scoring_weights": {"direct": 40, "dependency": 30},
        "safety_rules": ["RULE_1_UNKNOWN_DEPENDENCY"],
        "description": "E2E test version"
    }, headers=admin_headers)
    assert res_v.status_code == 200

    # Rollback to legacy full suite (QA blocked, ADMIN allowed)
    rb_qa = client.post("/api/strategy/rollback", json={
        "to_strategy": "LEGACY_FULL_SUITE",
        "reason": "E2E rollback test"
    }, headers=qa_headers)
    assert rb_qa.status_code == 403

    rb_admin = client.post("/api/strategy/rollback", json={
        "to_strategy": "LEGACY_FULL_SUITE",
        "reason": "E2E drill"
    }, headers=admin_headers)
    assert rb_admin.status_code == 200
    assert client.get("/api/strategy").json()["current_strategy"] == "LEGACY_FULL_SUITE"

    # Restore to smart selector
    client.post("/api/strategy/rollback", json={
        "to_strategy": "SMART_SELECTOR",
        "reason": "Restore smart mode"
    }, headers=admin_headers)
    assert client.get("/api/strategy").json()["current_strategy"] == "SMART_SELECTOR"

    # ── 9. Audit Trail & Secret Redaction ────────────────────────────────────
    audit_res = client.get("/api/audit/logs?limit=50")
    assert audit_res.status_code == 200
    logs = audit_res.json()["logs"]
    assert len(logs) > 0
    # Verify no raw authorization bearer tokens leak in summaries
    for l in logs:
        assert "Bearer" not in l.get("input_summary", "")

    # ── 10. Structured Stakeholder Feedback ──────────────────────────────────
    fb_res = client.post("/api/audit/feedback", json={
        "reviewer_name": "QA Principal Engineer",
        "project_area": "Change Impact Selector",
        "rating": 5,
        "comments": "E2E validation complete and verified.",
        "linked_entity_id": "CHG-E2E-001"
    }, headers=viewer_headers)
    assert fb_res.status_code == 200
    assert fb_res.json()["success"] is True

    stats_res = client.get("/api/audit/feedback/stats")
    assert stats_res.status_code == 200
    assert stats_res.json()["response_count"] >= 1
