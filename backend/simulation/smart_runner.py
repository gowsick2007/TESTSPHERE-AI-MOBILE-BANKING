"""
TestSphere AI — Smart Runner
Simulates running selected tests and measures savings.
"""
from typing import Dict, Any, List
from backend.engine.test_selector import run_selection


def run_smart_regression(
    changed_files: List[str],
    change_type: str = "MODIFIED",
    module: str | None = None,
    is_security_sensitive: bool = False,
    risk_level: str = "MEDIUM",
) -> Dict[str, Any]:
    """
    Executes selection and runs the chosen subset of tests.
    """
    result = run_selection(
        changed_files=changed_files,
        change_type=change_type,
        module=module,
        is_security_sensitive=is_security_sensitive,
        risk_level=risk_level
    )

    decisions = result["decisions"]
    summary = result["summary"]

    # Execute simulation (split selected tests into status buckets)
    selected_tests = [d for d in decisions if d["decision"] == "RUN"]
    skipped_tests = [d for d in decisions if d["decision"] == "SKIP"]

    execution_list = []
    import random
    # Stable seed
    rng = random.Random(42)

    for i, t in enumerate(selected_tests):
        # We determine pass/fail using ground truth or a tiny chance of failure for simulation
        # 3% chance of test failure in normal smart execution
        status = "PASSED"
        fail_reason = None
        if rng.random() < 0.03:
            status = "FAILED"
            fail_reason = "AssertionError: Element not visible in UI layout check."

        execution_list.append({
            "test_id": t["test_id"],
            "test_name": t["test_name"],
            "module": t["module"],
            "device": t["device"],
            "status": status,
            "error": fail_reason,
            "execution_time": t["execution_time"]
        })

    return {
        "selection": result,
        "execution": {
            "total_selected": len(selected_tests),
            "total_skipped": len(skipped_tests),
            "time_reduction_pct": summary["time_reduction_pct"],
            "time_saved_minutes": summary["time_saved_minutes"],
            "tests": execution_list
        }
    }
