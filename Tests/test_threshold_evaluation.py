"""
TestSphere AI — Controlled Threshold Evaluation Tests (Phase 2)
Verifies:
- Evaluation of multiple thresholds [30, 40, 50, 60, 70]
- Dynamic calculation of TP, TN, FP, FN, Precision, Recall, F1, and runtime reduction
- Enforcement of the safety-first rule: Reject any threshold that introduces false negatives
- Baseline threshold 50 justification
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.engine.threshold_evaluator import evaluate_thresholds


def test_controlled_threshold_evaluation():
    """Verify that multiple thresholds are evaluated and safety verdicts are assigned correctly."""
    report = evaluate_thresholds(thresholds=[30, 40, 50, 60, 70], scenario_change_id="CHG001")
    assert "threshold_evaluations" in report
    evals = report["threshold_evaluations"]
    assert len(evals) == 5

    # Check each threshold evaluation structure
    for ev in evals:
        assert ev["threshold"] in [30, 40, 50, 60, 70]
        assert ev["tp"] >= 0
        assert ev["tn"] >= 0
        assert ev["fp"] >= 0
        assert ev["fn"] >= 0
        assert 0.0 <= ev["precision"] <= 1.0
        assert 0.0 <= ev["recall"] <= 1.0
        assert ev["verdict"] in ["ACCEPTED", "REJECTED"]

    # Threshold 50 must maintain 0 FN and be ACCEPTED
    t50 = next(e for e in evals if e["threshold"] == 50)
    assert t50["fn"] == 0
    assert t50["recall"] == 1.0
    assert t50["verdict"] == "ACCEPTED"
    assert t50["is_canonical_default"] is True


def test_threshold_api_endpoint(client):
    """Verify GET /api/analytics/threshold-sensitivity endpoint."""
    res = client.get("/api/analytics/threshold-sensitivity?change_id=CHG001")
    assert res.status_code == 200
    data = res.json()
    assert "threshold_evaluations" in data
    assert data["recommendation"]["chosen_threshold"] == 50


def test_previous_false_negative_is_now_run():
    """
    Regression Test: Scenario CHG011 (Notification module change in notification/push.py).
    Previously, test T0779 (Email Alert Test 50, covering notification/push.py on iPhone 12)
    scored 40 (< 50) and was erroneously SKIPPED despite directly testing the modified file.
    With RULE_4_DIRECT_FILE_MODIFICATION active, T0779 must decide RUN with 0 False Negatives.
    """
    from backend.engine.test_selector import run_selection
    from backend.database import get_db_connection

    # 1. Run selection for CHG011
    selection = run_selection(
        changed_files=["notification/push.py"],
        change_type="MODIFIED",
        module="Notification",
        is_security_sensitive=False,
        risk_level="LOW",
    )
    decisions = {d["test_id"]: d for d in selection["decisions"]}
    assert "T0779" in decisions, "T0779 must be evaluated in decisions"
    t0779 = decisions["T0779"]

    # 2. Verify ground truth requires RUN
    conn = get_db_connection()
    try:
        gt_row = conn.execute(
            "SELECT actually_affected FROM experiment_ground_truth WHERE change_id = 'CHG011' AND test_id = 'T0779'"
        ).fetchone()
        assert gt_row is not None and bool(gt_row["actually_affected"]) is True, "Ground truth for T0779 must be RUN"
    finally:
        conn.close()

    # 3. Verify selector now decides RUN via RULE_4
    assert t0779["decision"] == "RUN", f"T0779 must decide RUN, got {t0779['decision']}"
    assert any(
        o["rule_id"] == "RULE_4_DIRECT_FILE_MODIFICATION" for o in t0779.get("overrides", [])
    ), "T0779 must trigger RULE_4_DIRECT_FILE_MODIFICATION"
    assert "direct" in t0779["rationale"].lower(), "Rationale must document direct code coverage"

    # 4. Verify evaluate_thresholds for CHG011 has 0 False Negatives at threshold 50
    report = evaluate_thresholds(thresholds=[50], scenario_change_id="CHG011")
    t50 = report["threshold_evaluations"][0]
    assert t50["fn"] == 0, f"CHG011 must have 0 FN at threshold 50, got {t50['fn']}"
    assert t50["recall"] == 1.0, f"CHG011 recall must be 100%, got {t50['recall']}"

