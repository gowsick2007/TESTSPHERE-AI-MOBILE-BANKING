"""
TestSphere AI — Historical Failure Analyzer
Identifies tests with historical failure associations for the changed modules.
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from Engine.data_access import get_failure_history, get_failures_for_test

logger = logging.getLogger(__name__)

RECENT_FAILURE_DAYS = 90  # Failures within this window are "recent"


def find_failure_associated_tests(
    affected_modules: list[str],
    all_tests: list[dict],
) -> dict:
    """
    Find tests that have historical failure associations with the affected modules.

    Returns:
        dict with:
            module_failure_map  — module → [test_ids with failures]
            associated_tests    — unique list of test IDs
            failure_data_available
    """
    failures = get_failure_history()
    if not failures:
        logger.warning("No failure history data — safe RUN behavior applies")
        return {
            "module_failure_map": {},
            "associated_tests": [],
            "failure_data_available": False,
        }

    module_set = set(affected_modules)
    # test_id → failure records
    test_failures: dict[str, list[dict]] = defaultdict(list)
    for f in failures:
        if f.get("module") in module_set:
            test_failures[f["test_id"]].append(f)

    # Cross-reference with test_id in test_coverage for extra safety
    test_id_set = {t["test_id"] for t in all_tests}
    associated = [tid for tid in test_failures if tid in test_id_set]

    module_failure_map: dict[str, list[str]] = defaultdict(list)
    for tid in associated:
        for f in test_failures[tid]:
            module_failure_map[f["module"]].append(tid)

    return {
        "module_failure_map": dict(module_failure_map),
        "associated_tests": sorted(set(associated)),
        "failure_data_available": True,
    }


def is_recently_failed(test_id: str, days: int = RECENT_FAILURE_DAYS) -> bool:
    """Return True if test has a failure within the last `days` days."""
    failures = get_failures_for_test(test_id)
    if not failures:
        return False
    cutoff = datetime.utcnow() - timedelta(days=days)
    for f in failures:
        try:
            fd = datetime.fromisoformat(f["failure_date"])
            if fd >= cutoff:
                return True
        except (ValueError, TypeError):
            pass
    return False


def get_failure_stats() -> dict:
    """Aggregate failure statistics for the Failure Intelligence dashboard."""
    failures = get_failure_history()
    if not failures:
        return {
            "total_failures": 0, "failure_rate": 0.0,
            "by_module": {}, "by_device": {}, "by_test": {},
            "most_failed_test": None, "highest_risk_module": None,
        }

    by_module: dict[str, int] = defaultdict(int)
    by_device: dict[str, int] = defaultdict(int)
    by_test: dict[str, int] = defaultdict(int)

    for f in failures:
        by_module[f.get("module", "Unknown")] += 1
        by_device[f.get("device", "Unknown")] += 1
        by_test[f.get("test_id", "?")] += 1

    most_failed_test = max(by_test, key=by_test.get) if by_test else None
    highest_risk_module = max(by_module, key=by_module.get) if by_module else None

    return {
        "total_failures": len(failures),
        "by_module": dict(sorted(by_module.items(), key=lambda x: -x[1])),
        "by_device": dict(sorted(by_device.items(), key=lambda x: -x[1])),
        "by_test": dict(sorted(by_test.items(), key=lambda x: -x[1])[:20]),
        "most_failed_test": most_failed_test,
        "highest_risk_module": highest_risk_module,
        "failure_rate": round(len(set(by_test.keys())) / max(1, len(by_test)) * 100, 1),
    }
