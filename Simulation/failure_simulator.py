"""
TestSphere AI — Failure Mode Simulator
Demonstrates how the system behaves under 5 failure scenarios.
All scenarios validate that safety defaults are preserved.
"""
import logging
from Engine.test_selector import run_selection
from Engine.safety_overrides import evaluate_safety_overrides, determine_confidence
from Engine.data_access import get_all_tests
from Data_Generation.generate_dataset import generate_and_load

logger = logging.getLogger(__name__)


SCENARIOS = [
    {
        "id": "SCENARIO_1",
        "name": "Unknown Dependency",
        "description": "Dependency graph is unavailable. System must default to RUN for all tests.",
        "input": {
            "changed_files": ["unknown/nonexistent.py"],
            "change_type": "MODIFIED",
            "module": None,
            "is_security_sensitive": False,
            "risk_level": "MEDIUM",
        },
        "expected_behavior": "All tests RUN (safe default for unknown dependency)",
        "expected_decision": "RUN",
        "expected_rule": "RULE_1_UNKNOWN_DEPENDENCY",
    },
    {
        "id": "SCENARIO_2",
        "name": "Missing Coverage Data",
        "description": "Test coverage data is unavailable. System must not skip tests.",
        "input": {
            "changed_files": ["payment/payment.py"],
            "change_type": "MODIFIED",
            "module": "Payment",
            "is_security_sensitive": False,
            "risk_level": "HIGH",
        },
        "expected_behavior": "Critical module tests RUN via safety override",
        "expected_decision": "RUN",
        "expected_rule": "RULE_4_CRITICAL_MODULE",
    },
    {
        "id": "SCENARIO_3",
        "name": "High-Risk Authentication Change",
        "description": "Authentication module change — must always run security tests.",
        "input": {
            "changed_files": ["auth/login.py", "auth/token_manager.py"],
            "change_type": "SECURITY_PATCH",
            "module": "Authentication",
            "is_security_sensitive": True,
            "risk_level": "HIGH",
        },
        "expected_behavior": "All authentication + security tests RUN",
        "expected_decision": "RUN",
        "expected_rule": "RULE_3_SECURITY_CRITICAL",
    },
    {
        "id": "SCENARIO_4",
        "name": "Historical Payment Failure",
        "description": "Payment module with known historical failures — must increase risk and RUN.",
        "input": {
            "changed_files": ["payment/payment.py"],
            "change_type": "MODIFIED",
            "module": "Payment",
            "is_security_sensitive": False,
            "risk_level": "HIGH",
        },
        "expected_behavior": "Payment tests with historical failures scored higher, RUN",
        "expected_decision": "RUN",
        "expected_rule": "RULE_4_CRITICAL_MODULE",
    },
    {
        "id": "SCENARIO_5",
        "name": "Incorrect Selector Configuration",
        "description": "Selector receives invalid/empty changed files. Must not crash and must default to RUN.",
        "input": {
            "changed_files": [],
            "change_type": "UNKNOWN",
            "module": None,
            "is_security_sensitive": False,
            "risk_level": "UNKNOWN",
        },
        "expected_behavior": "System defaults to safe RUN for all tests, no crash",
        "expected_decision": "RUN",
        "expected_rule": "RULE_1_UNKNOWN_DEPENDENCY",
    },
]


def run_scenario(scenario: dict) -> dict:
    """
    Execute a single failure-mode scenario and compare actual vs expected behavior.

    Returns:
        dict with scenario metadata, actual_result, verdict (PASS/FAIL)
    """
    scenario_id = scenario["id"]
    inp = scenario["input"]

    try:
        result = run_selection(
            changed_files=inp["changed_files"],
            change_type=inp["change_type"],
            module=inp.get("module"),
            is_security_sensitive=inp.get("is_security_sensitive", False),
            risk_level=inp.get("risk_level", "MEDIUM"),
        )

        decisions = result.get("decisions", [])
        run_count  = sum(1 for d in decisions if d["decision"] == "RUN")
        skip_count = sum(1 for d in decisions if d["decision"] == "SKIP")

        # Check if expected rule was triggered anywhere
        triggered_rules: set[str] = set()
        for d in decisions:
            for o in d.get("overrides", []):
                triggered_rules.add(o.get("rule_id", ""))

        expected_rule = scenario.get("expected_rule", "")
        rule_triggered = expected_rule in triggered_rules if expected_rule else True

        # Verdict: pass if RUN tests > 0 AND expected rule triggered
        passed = run_count > 0 and rule_triggered

        actual_behavior = (
            f"{run_count} tests RUN, {skip_count} tests SKIPPED. "
            f"Rules triggered: {', '.join(triggered_rules) or 'none'}"
        )

        return {
            "scenario_id":       scenario_id,
            "name":              scenario["name"],
            "description":       scenario["description"],
            "input":             inp,
            "expected_behavior": scenario["expected_behavior"],
            "actual_behavior":   actual_behavior,
            "run_count":         run_count,
            "skip_count":        skip_count,
            "triggered_rules":   list(triggered_rules),
            "expected_rule":     expected_rule,
            "rule_triggered":    rule_triggered,
            "verdict":           "PASS" if passed else "FAIL",
            "error":             None,
        }

    except Exception as exc:
        logger.error("Scenario %s crashed: %s", scenario_id, exc)
        return {
            "scenario_id":       scenario_id,
            "name":              scenario["name"],
            "description":       scenario["description"],
            "input":             inp,
            "expected_behavior": scenario["expected_behavior"],
            "actual_behavior":   f"ERROR: {exc}",
            "run_count":         0,
            "skip_count":        0,
            "triggered_rules":   [],
            "expected_rule":     scenario.get("expected_rule", ""),
            "rule_triggered":    False,
            "verdict":           "FAIL",
            "error":             str(exc),
        }


def run_all_scenarios() -> list[dict]:
    """Run all 5 failure-mode scenarios and return results."""
    # Ensure database is seeded with mock tests if empty
    tests = get_all_tests()
    if not tests:
        import Engine.database as db_mod
        db_mod.IN_MEMORY_MOCK_ACTIVE = True
        try:
            results = [run_scenario(s) for s in SCENARIOS]
            return results
        finally:
            db_mod.IN_MEMORY_MOCK_ACTIVE = False
            if db_mod._MOCK_CONN:
                db_mod._MOCK_CONN.close()
                db_mod._MOCK_CONN = None
    else:
        return [run_scenario(s) for s in SCENARIOS]

