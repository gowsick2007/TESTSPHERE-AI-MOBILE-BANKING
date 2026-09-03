"""
TestSphere AI — Smart Runner
Simulates execution of the smart-selected test subset.
"""
import logging
import random
from datetime import datetime

logger = logging.getLogger(__name__)

FAILURE_RATE = 0.05
SEED = 42


def run_smart(decisions: list[dict], seed: int = SEED) -> dict:
    """
    Simulate execution of tests the smart selector chose to RUN.

    Args:
        decisions — list of decision records from test_selector.run_selection()

    Returns a dict with execution summary and per-test results.
    """
    if not decisions:
        return _empty_run()

    rng = random.Random(seed)
    run_tests  = [d for d in decisions if d.get("decision") == "RUN"]
    skip_tests = [d for d in decisions if d.get("decision") == "SKIP"]

    results = []
    total_runtime = 0.0

    for test in run_tests:
        exec_time = test.get("execution_time", 0.5)
        failed = rng.random() < FAILURE_RATE
        status = "FAILED" if failed else "PASSED"
        results.append({
            "test_id":        test["test_id"],
            "test_name":      test.get("test_name", ""),
            "module":         test.get("module", ""),
            "device":         test.get("device", ""),
            "os_version":     test.get("os_version", ""),
            "status":         status,
            "execution_time": exec_time,
            "decision":       "RUN",
            "risk_score":     test.get("risk_score", 0),
            "rationale":      test.get("rationale", ""),
        })
        total_runtime += exec_time

    # Skipped tests are shown with status=SKIPPED
    for test in skip_tests:
        results.append({
            "test_id":        test["test_id"],
            "test_name":      test.get("test_name", ""),
            "module":         test.get("module", ""),
            "device":         test.get("device", ""),
            "os_version":     test.get("os_version", ""),
            "status":         "SKIPPED",
            "execution_time": 0,
            "decision":       "SKIP",
            "risk_score":     test.get("risk_score", 0),
            "rationale":      test.get("rationale", ""),
        })

    passed       = sum(1 for r in results if r["status"] == "PASSED")
    failed_count = sum(1 for r in results if r["status"] == "FAILED")

    return {
        "strategy":         "SMART_SELECTOR",
        "run_timestamp":    datetime.utcnow().isoformat(),
        "total_tests":      len(decisions),
        "executed":         len(run_tests),
        "passed":           passed,
        "failed":           failed_count,
        "skipped":          len(skip_tests),
        "runtime_seconds":  round(total_runtime, 2),
        "runtime_minutes":  round(total_runtime / 60, 2),
        "test_results":     results,
    }


def _empty_run() -> dict:
    return {
        "strategy": "SMART_SELECTOR", "total_tests": 0, "executed": 0,
        "passed": 0, "failed": 0, "skipped": 0,
        "runtime_seconds": 0, "runtime_minutes": 0, "test_results": [],
        "run_timestamp": datetime.utcnow().isoformat(),
    }
