"""
TestSphere AI — Coverage Analyzer
Maps changed/impacted files to the tests that cover them.
"""
import logging
from Engine.data_access import get_all_tests, get_tests_covering_file

logger = logging.getLogger(__name__)


def find_covered_tests(impacted_files: list[str]) -> dict:
    """
    For each impacted file, find tests that directly cover it.

    Returns:
        dict with:
            file_test_map  — file → [test_ids]
            covered_tests  — deduplicated list of all covered test IDs
            coverage_available — False if test_coverage table is empty
    """
    if not impacted_files:
        return {
            "file_test_map": {},
            "covered_tests": [],
            "coverage_available": True,
        }

    all_tests = get_all_tests()
    if not all_tests:
        logger.warning("Test coverage table is empty — safe RUN behavior applies")
        return {
            "file_test_map": {},
            "covered_tests": [],
            "coverage_available": False,
        }

    # Build an in-memory mapping of file_path -> list of test_ids
    lookup: dict[str, list[str]] = {}
    for t in all_tests:
        fp = t.get("file_path")
        if fp:
            lookup.setdefault(fp, []).append(t["test_id"])

    file_test_map: dict[str, list[str]] = {}
    covered_set: set[str] = set()

    for file_path in impacted_files:
        test_ids = lookup.get(file_path, [])
        file_test_map[file_path] = test_ids
        covered_set.update(test_ids)

    return {
        "file_test_map": file_test_map,
        "covered_tests": sorted(covered_set),
        "coverage_available": True,
    }


def get_coverage_for_test(test_id: str, all_tests: list[dict] | None = None) -> dict:
    """
    Return coverage detail for a specific test.

    Returns:
        dict with test_id, file_path, module, coverage_available
    """
    if all_tests is None:
        all_tests = get_all_tests()

    for t in all_tests:
        if t["test_id"] == test_id:
            return {
                "test_id": test_id,
                "file_path": t.get("file_path"),
                "module": t.get("module"),
                "coverage_available": True,
            }
    return {
        "test_id": test_id,
        "file_path": None,
        "module": None,
        "coverage_available": False,
    }


def compute_coverage_stats(all_tests: list[dict]) -> dict:
    """Compute overall coverage statistics across all tests."""
    if not all_tests:
        return {
            "total_tests": 0, "covered_files": 0, "uncovered": 0,
            "coverage_pct": 0.0, "module_coverage": {}
        }

    covered_files = {t["file_path"] for t in all_tests if t.get("file_path")}
    module_groups: dict[str, list] = {}
    for t in all_tests:
        m = t.get("module", "Unknown")
        module_groups.setdefault(m, []).append(t)

    return {
        "total_tests": len(all_tests),
        "covered_files": len(covered_files),
        "uncovered": sum(1 for t in all_tests if not t.get("file_path")),
        "coverage_pct": round((len(covered_files) / max(1, len(all_tests))) * 100, 1),
        "module_coverage": {m: len(ts) for m, ts in module_groups.items()},
    }
