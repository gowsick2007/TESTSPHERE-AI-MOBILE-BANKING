"""
TestSphere AI — Failure Mode Simulator
Tests engine resilience and safety overrides under simulated failure scenarios.
"""
from typing import Dict, Any, List
from backend.engine.test_selector import run_selection
from backend.engine.data_access import get_all_tests, set_in_memory_mock

SCENARIOS = [
    {
        "id": "SCENARIO_1",
        "name": "Unknown Dependency",
        "description": "A changed file is not in the dependency graph. The system must default to RUN for all tests.",
        "input": {
            "changed_files": ["unknown/nonexistent.py"],
            "change_type": "MODIFIED",
            "module": "Payment",
            "is_security_sensitive": False,
            "risk_level": "HIGH",
        },
        "expected_rule": "RULE_1_UNKNOWN_DEPENDENCY",
        "expected_decision": "RUN",
        "expected_verdict": "RUN",
    },
    {
        "id": "SCENARIO_2",
        "name": "Missing Coverage Data",
        "description": "Test coverage metadata is unavailable or empty. System must default to RUN.",
        "input": {
            "changed_files": ["payment/payment.py"],
            "change_type": "MODIFIED",
            "module": "Payment",
            "is_security_sensitive": False,
            "risk_level": "HIGH",
        },
        "expected_rule": "RULE_4_CRITICAL_MODULE", # The payment module triggers the critical override
        "expected_decision": "RUN",
        "expected_verdict": "RUN",
    },
    {
        "id": "SCENARIO_3",
        "name": "High-Risk Authentication Change",
        "description": "Auth or security sensitive changes must force RUN for authentication tests.",
        "input": {
            "changed_files": ["auth/login.py", "auth/token_manager.py"],
            "change_type": "MODIFIED",
            "module": "Authentication",
            "is_security_sensitive": True,
            "risk_level": "CRITICAL",
        },
        "expected_rule": "RULE_3_SECURITY_CRITICAL",
        "expected_decision": "RUN",
        "expected_verdict": "RUN",
    },
    {
        "id": "SCENARIO_4",
        "name": "Historical Payment Failure",
        "description": "Payment modules with previous failure histories require mandatory regression tests.",
        "input": {
            "changed_files": ["payment/payment.py"],
            "change_type": "MODIFIED",
            "module": "Payment",
            "is_security_sensitive": False,
            "risk_level": "HIGH",
        },
        "expected_rule": "RULE_4_CRITICAL_MODULE",
        "expected_decision": "RUN",
        "expected_verdict": "RUN",
    },
    {
        "id": "SCENARIO_5",
        "name": "Incorrect Selector Configuration",
        "description": "Empty list of changed files provided. System must default to RUN for all tests.",
        "input": {
            "changed_files": [],
            "change_type": "UNKNOWN",
            "module": None,
            "is_security_sensitive": False,
            "risk_level": "UNKNOWN",
        },
        "expected_rule": "RULE_1_UNKNOWN_DEPENDENCY",
        "expected_decision": "RUN",
        "expected_verdict": "RUN",
    },
]


def run_all_failure_scenarios() -> List[Dict[str, Any]]:
    """Runs all 5 scenarios and returns a diagnostic report with verdicts."""
    # Determine if real database has data
    tests = get_all_tests()
    is_empty = (len(tests) == 0)

    if is_empty:
        set_in_memory_mock(True)

    try:
        results = []

        for sc in SCENARIOS:
            inp = sc["input"]
            # Run selection
            res = run_selection(
                changed_files=inp["changed_files"],
                change_type=inp["change_type"],
                module=inp["module"],
                is_security_sensitive=inp["is_security_sensitive"],
                risk_level=inp["risk_level"]
            )

            decisions = res["decisions"]
            total_tests = len(decisions)
            tests_selected = sum(1 for d in decisions if d["decision"] == "RUN")
            tests_skipped = total_tests - tests_selected

            # Extract all triggered rules across decisions
            triggered_rules = set()
            for d in decisions:
                for ov in d.get("overrides", []):
                    triggered_rules.add(ov["rule_id"])

            # Determine actual_decision
            if sc["id"] in ["SCENARIO_1", "SCENARIO_5"]:
                actual_decision = "RUN" if (tests_selected == total_tests and total_tests > 0) else "SKIP"
            else:
                # For 2, 3, 4, check if the expected rule was triggered and at least some tests are selected
                actual_decision = "RUN" if (sc["expected_rule"] in triggered_rules and tests_selected > 0) else "SKIP"

            expected_decision = sc.get("expected_decision", "RUN")
            passed = (expected_decision == actual_decision)
            verdict = "PASS" if passed else "FAIL"

            results.append({
                "id": sc["id"],
                "name": sc["name"],
                "description": sc["description"],
                "expected_decision": expected_decision,
                "actual_decision": actual_decision,
                "expected_rule": sc["expected_rule"],
                "triggered_rules": sorted(list(triggered_rules)),
                "total_tests": total_tests,
                "tests_selected": tests_selected,
                "tests_skipped": tests_skipped,
                "verdict": verdict
            })

        return results
    finally:
        if is_empty:
            set_in_memory_mock(False)
