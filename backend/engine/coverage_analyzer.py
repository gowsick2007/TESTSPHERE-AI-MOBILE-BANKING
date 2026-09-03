"""
TestSphere AI — Coverage Analyzer
Finds tests covering changed or dependency-impacted files.
"""
import logging
from typing import List, Dict, Any
from backend.engine.data_access import get_all_tests, get_tests_covering_file

logger = logging.getLogger(__name__)


def find_covered_tests(impacted_files: List[str]) -> Dict[str, Any]:
    """
    Finds tests directly covering a list of files.
    """
    if not impacted_files:
        return {
            "file_test_map": {},
            "covered_tests": [],
            "coverage_available": True,
        }

    all_tests = get_all_tests()
    if not all_tests:
        logger.warning("Test coverage database is empty — safe RUN applies")
        return {
            "file_test_map": {},
            "covered_tests": [],
            "coverage_available": False,
        }

    # Build an in-memory mapping of file_path -> list of test_ids
    lookup: Dict[str, List[str]] = {}
    for t in all_tests:
        fp = t.get("file_path")
        if fp:
            lookup.setdefault(fp, []).append(t["test_id"])

    file_test_map: Dict[str, List[str]] = {}
    covered_set = set()

    for file_path in impacted_files:
        test_ids = lookup.get(file_path, [])
        file_test_map[file_path] = test_ids
        covered_set.update(test_ids)

    return {
        "file_test_map": file_test_map,
        "covered_tests": sorted(list(covered_set)),
        "coverage_available": True,
    }


def get_coverage_for_test(test_id: str, all_tests: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    """Retrieves file path coverage mapping for a single test."""
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


def compute_coverage_stats(all_tests: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates metadata, ratios, and coverage metrics across modules."""
    if not all_tests:
        return {
            "total_tests": 0, "covered_files": 0, "uncovered": 0,
            "coverage_pct": 0.0, "module_coverage": {}
        }

    covered_files = {t["file_path"] for t in all_tests if t.get("file_path")}
    module_groups: Dict[str, List] = {}
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
