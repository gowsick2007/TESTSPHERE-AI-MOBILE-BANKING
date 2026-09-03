"""
TestSphere AI — Baseline Runner
Simulates running the entire regression test suite.
"""
from typing import Dict, Any, List
from backend.engine.data_access import get_all_tests


def run_baseline_regression() -> Dict[str, Any]:
    """
    Simulates executing 100% of the regression suite.
    """
    tests = get_all_tests()
    total_tests = len(tests)
    total_time = sum(t.get("execution_time", 0.5) for t in tests)

    # All decisions are forced to RUN
    decisions = []
    for t in tests:
        decisions.append({
            "test_id": t["test_id"],
            "test_name": t["test_name"],
            "module": t.get("module", ""),
            "device": t.get("device", ""),
            "os_version": t.get("os_version", ""),
            "execution_time": t.get("execution_time", 0.5),
            "risk_score": 100,
            "decision": "RUN",
            "confidence": "HIGH",
            "rationale": "Legacy baseline regression run: 100% test execution mandated."
        })

    return {
        "strategy": "LEGACY_FULL_SUITE",
        "total_tests": total_tests,
        "tests_selected": total_tests,
        "tests_skipped": 0,
        "runtime_minutes": round(total_time / 60.0, 2),
        "decisions": decisions
    }
