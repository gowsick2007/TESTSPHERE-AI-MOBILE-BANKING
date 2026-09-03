"""
TestSphere AI — Engine and Safety Override Unit Tests
Run via pytest to verify all functional rules and formulas.
"""
import sys
import os
from pathlib import Path

# Add root folder to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from Engine.database import initialize_database, get_connection
from Engine.data_access import get_all_tests, get_device_matrix, set_current_strategy, get_current_strategy
from Engine.safety_overrides import evaluate_safety_overrides, determine_confidence
from Engine.risk_scorer import compute_risk_score
from Engine.test_selector import run_selection
from Simulation.baseline_runner import run_baseline
from Simulation.smart_runner import run_smart
from Simulation.experiment_engine import run_experiment
from Simulation.failure_simulator import run_scenario, SCENARIOS


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Ensure database is initialized and populated for tests."""
    initialize_database()
    from Data_Generation.generate_dataset import generate_and_load
    generate_and_load(verbose=False)


def test_database_connection():
    conn = get_connection()
    assert conn is not None
    row = conn.execute("SELECT 1").fetchone()
    assert row[0] == 1
    conn.close()


def test_risk_scoring_formula():
    """Verify that the risk scoring formula matches math specification."""
    # Case 1: Low risk profile
    test_low = {
        "test_id": "T1",
        "module": "Dashboard",
        "device": "Pixel 7",
        "os_version": "Android 14"
    }
    score_low, _ = compute_risk_score(
        test=test_low,
        covered_test_ids=set(),
        dependency_test_ids=set(),
        failure_associated_ids=set(),
        is_security_sensitive=False,
        affected_modules=[],
    )
    assert score_low == 0

    # Case 2: High risk critical profile
    test_high = {
        "test_id": "T2",
        "module": "Authentication",
        "device": "Pixel 8",
        "os_version": "Android 15"
    }
    score_high, _ = compute_risk_score(
        test=test_high,
        covered_test_ids={"T2"},
        dependency_test_ids={"T2"},
        failure_associated_ids={"T2"},
        is_security_sensitive=True,
        affected_modules=["Authentication"],
    )
    # direct (40) + dep (30) + hist (20) + device (10) + security (30) + critical (25) = 155
    assert score_high == 155


def test_safety_override_rules():
    """Verify triggering rules on test records."""
    # Rule 3: Security Critical override
    overrides_sec = evaluate_safety_overrides(
        test={"is_security_critical": 1, "module": "GeneralSecurity", "device": "Pixel 8"},
        dep_info_available=True,
        coverage_info_available=True,
        failure_data_available=True,
        confidence_level="HIGH"
    )
    assert any(o.rule_id == "RULE_3_SECURITY_CRITICAL" for o in overrides_sec)

    # Rule 4: Critical Module override
    overrides_crit = evaluate_safety_overrides(
        test={"is_security_critical": 0, "module": "Payment", "device": "Pixel 8"},
        dep_info_available=True,
        coverage_info_available=True,
        failure_data_available=True,
        confidence_level="HIGH"
    )
    assert any(o.rule_id == "RULE_4_CRITICAL_MODULE" for o in overrides_crit)


def test_confidence_assessment():
    """Verify that confidence is determined correctly based on rules."""
    # Triggers override -> MEDIUM/LOW confidence depending on score
    conf_low = determine_confidence(score=10, evidence=[])
    assert conf_low == "LOW"

    # High score, 3+ evidence -> HIGH confidence
    conf_high = determine_confidence(score=85, evidence=["a", "b", "c"])
    assert conf_high == "HIGH"


def test_baseline_and_smart_runners():
    """Verify runners handle selections without crashing."""
    baseline = run_baseline()
    assert baseline["strategy"] == "LEGACY_FULL_SUITE"
    assert "test_results" in baseline

    # Run select for a dummy input
    sel = run_selection(changed_files=["payment/payment.py"], risk_level="HIGH")
    assert "decisions" in sel
    smart = run_smart(sel["decisions"])
    assert smart["strategy"] == "SMART_SELECTOR"
    assert len(smart["test_results"]) == len(sel["decisions"])


def test_failure_scenarios():
    """Verify all 5 failure scenarios pass safety defaults."""
    for s in SCENARIOS:
        res = run_scenario(s)
        assert res["verdict"] == "PASS"
