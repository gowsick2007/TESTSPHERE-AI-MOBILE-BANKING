"""
TestSphere AI — Baseline Runner
Simulates running the full test suite (legacy behavior).
No actual test execution — uses per-test execution_time for simulation.
"""
import logging
import random
from datetime import datetime
from Engine.data_access import get_all_tests

logger = logging.getLogger(__name__)

FAILURE_RATE = 0.05  # 5% tests will "fail" in simulation
SEED = 42


def run_baseline(seed: int = SEED) -> dict:
    """
    Simulate a full baseline run of all tests.

    Returns a dict with:
        strategy, total_tests, executed, passed, failed, skipped,
        runtime_seconds, runtime_minutes, test_results (list)
    """
    all_tests = get_all_tests()
    if not all_tests:
        return _empty_run("LEGACY_FULL_SUITE")

    rng = random.Random(seed)
    results = []
    total_runtime = 0.0

    for test in all_tests:
        exec_time = test.get("execution_time", 0.5)
        # Simulate realistic failure rate
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
        })
        total_runtime += exec_time

    passed  = sum(1 for r in results if r["status"] == "PASSED")
    failed_count = sum(1 for r in results if r["status"] == "FAILED")

    return {
        "strategy":         "LEGACY_FULL_SUITE",
        "run_timestamp":    datetime.utcnow().isoformat(),
        "total_tests":      len(all_tests),
        "executed":         len(all_tests),
        "passed":           passed,
        "failed":           failed_count,
        "skipped":          0,
        "runtime_seconds":  round(total_runtime, 2),
        "runtime_minutes":  round(total_runtime / 60, 2),
        "test_results":     results,
    }


def _empty_run(strategy: str) -> dict:
    return {
        "strategy": strategy, "total_tests": 0, "executed": 0,
        "passed": 0, "failed": 0, "skipped": 0,
        "runtime_seconds": 0, "runtime_minutes": 0, "test_results": [],
        "run_timestamp": datetime.utcnow().isoformat(),
    }
