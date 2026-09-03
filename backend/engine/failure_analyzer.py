"""
TestSphere AI — Failure Analyzer
Examines failure history records and detects test defect profiles.
"""
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any, Set
from backend.engine.data_access import get_all_failures

logger = logging.getLogger(__name__)


def get_failure_stats() -> Dict[str, Any]:
    """
    Computes diagnostic analytics for historical regression failures.
    """
    failures = get_all_failures()
    if not failures:
        return {
            "total_failures": 0,
            "failure_rate": 0.0,
            "most_failed_test": None,
            "highest_risk_module": None,
            "by_module": {},
            "by_device": {},
            "by_test": {},
        }

    total_failures = len(failures)

    by_module: Dict[str, int] = {}
    by_device: Dict[str, int] = {}
    by_test: Dict[str, int] = {}

    for f in failures:
        m = f.get("module", "Unknown")
        d = f.get("device", "Unknown")
        t_id = f.get("test_id", "Unknown")

        by_module[m] = by_module.get(m, 0) + 1
        by_device[d] = by_device.get(d, 0) + 1
        by_test[t_id] = by_test.get(t_id, 0) + 1

    # Sorting
    sorted_modules = sorted(by_module.items(), key=lambda x: x[1], reverse=True)
    sorted_tests = sorted(by_test.items(), key=lambda x: x[1], reverse=True)

    most_failed = sorted_tests[0][0] if sorted_tests else None
    high_risk_mod = sorted_modules[0][0] if sorted_modules else None

    # Percentages
    from backend.engine.data_access import get_all_tests
    tests_count = len(get_all_tests()) or 1000
    defect_density = (len(by_test) / tests_count) * 100

    return {
        "total_failures": total_failures,
        "failure_rate": defect_density,
        "most_failed_test": most_failed,
        "highest_risk_module": high_risk_mod,
        "by_module": dict(sorted_modules[:10]),
        "by_device": by_device,
        "by_test": dict(sorted_tests[:20]),
    }


def find_failure_associated_tests(affected_modules: List[str], all_tests: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Identifies tests that belong to modules containing failures.
    """
    failures = get_all_failures()
    if not failures:
        return {
            "associated_tests": [],
            "failure_data_available": False,
        }

    # Gather test_ids that have historical failures
    failed_test_ids = {f["test_id"] for f in failures}

    # Filter all tests that belong to affected modules AND have failed previously
    associated = []
    modules_set = set(affected_modules)

    for t in all_tests:
        # If the test belongs to a changed module AND has failed historically
        if t["module"] in modules_set and t["test_id"] in failed_test_ids:
            associated.append(t["test_id"])

    return {
        "associated_tests": sorted(associated),
        "failure_data_available": True,
    }


def is_recently_failed(test_id: str) -> bool:
    """Returns True if the test has a recorded failure in the database."""
    failures = get_all_failures()
    for f in failures:
        if f["test_id"] == test_id:
            # We can check dates or just treat any presence as a failure risk
            return True
    return False
