"""
TestSphere AI — Test Selector (Orchestrator Engine)
Executes the change-impact selection workflow from change input to decision array.
"""
import logging
from typing import List, Dict, Any
from backend.config import CONFIG
from backend.engine.data_access import get_all_tests, get_data_health
from backend.engine.change_analyzer import analyze_change
from backend.engine.dependency_analyzer import get_impacted_files, build_dependency_graph
from backend.engine.coverage_analyzer import find_covered_tests
from backend.engine.failure_analyzer import find_failure_associated_tests
from backend.engine.risk_scorer import score_all_tests, RUN_THRESHOLD
from backend.engine.safety_overrides import evaluate_safety_overrides, determine_confidence
from backend.engine.rationale_generator import generate_rationale, format_decision_record

logger = logging.getLogger(__name__)


def run_selection(
    changed_files: List[str],
    change_type: str = "MODIFIED",
    module: str | None = None,
    is_security_sensitive: bool = False,
    risk_level: str = "MEDIUM",
) -> Dict[str, Any]:
    """
    Full pipeline to decide whether each test should RUN or SKIP.
    """
    logger.info("Running selection pipeline for: %s", changed_files)

    # 1. Data Availability Check
    health = get_data_health()
    dep_available = health["ready"] > 0
    cov_available = health["ready"] > 0
    fail_available = health["ready"] > 0

    # 2. Analyze change
    change_ctx = analyze_change(
        changed_files=changed_files,
        change_type=change_type,
        module=module,
        is_security_sensitive=is_security_sensitive,
        risk_level=risk_level,
    )

    # 3. Find impacted files (dependencies)
    dep_info = get_impacted_files(changed_files)
    dep_available = dep_available and dep_info.get("graph_available", False)

    # Safety Check: If no files are given or a changed file is not in the graph, we do not know its dependencies.
    # Set dep_available = False to trigger RULE_1 safety override.
    try:
        graph = build_dependency_graph()
        if not changed_files or any(f not in graph for f in changed_files):
            dep_available = False
    except Exception:
        dep_available = False

    # 4. Find directly covered tests
    all_impacted = dep_info.get("all_impacted", []) + changed_files
    cov_info = find_covered_tests(list(set(all_impacted)))
    cov_available = cov_available and cov_info.get("coverage_available", False)
    covered_ids = set(cov_info.get("covered_tests", []))

    # 5. Fetch all tests
    all_tests = get_all_tests()
    if not all_tests:
        logger.warning("No tests found in database — returning empty selection")
        return _empty_result(change_ctx)

    # 6. Find dependency-related tests
    dep_cov = find_covered_tests(dep_info.get("direct", []) + dep_info.get("indirect", []))
    dep_test_ids = set(dep_cov.get("covered_tests", []))

    # 7. Find failure-associated tests
    fail_info = find_failure_associated_tests(
        affected_modules=change_ctx.get("affected_modules", []),
        all_tests=all_tests,
    )
    fail_available = fail_available and fail_info.get("failure_data_available", False)
    failure_ids = set(fail_info.get("associated_tests", []))

    # 8. Score all tests
    scored = score_all_tests(
        all_tests=all_tests,
        covered_test_ids=covered_ids,
        dependency_test_ids=dep_test_ids,
        failure_associated_ids=failure_ids,
        is_security_sensitive=is_security_sensitive or change_ctx.get("is_security_sensitive", False),
        affected_modules=change_ctx.get("affected_modules", []),
    )

    # 9. Apply overrides and make decisions
    decisions: List[Dict[str, Any]] = []
    for test_record in scored:
        score = test_record["risk_score"]
        evidence = test_record["evidence"]
        confidence = determine_confidence(score, evidence)

        overrides = evaluate_safety_overrides(
            test=test_record,
            dep_info_available=dep_available,
            coverage_info_available=cov_available,
            failure_data_available=fail_available,
            confidence_level=confidence,
        )

        if overrides:
            decision = "RUN"
        elif score >= RUN_THRESHOLD:
            decision = "RUN"
        else:
            decision = "SKIP"

        # Generate details
        overrides_dict = [o.to_dict() for o in overrides]
        rationale = generate_rationale(
            test=test_record,
            decision=decision,
            score=score,
            evidence=evidence,
            overrides=overrides_dict,
            confidence=confidence,
        )

        record = format_decision_record(
            test=test_record,
            decision=decision,
            score=score,
            confidence=confidence,
            evidence=evidence,
            overrides=overrides_dict,
            rationale=rationale,
        )
        decisions.append(record)

    # 10. Aggregated Summary
    run_tests    = [d for d in decisions if d["decision"] == "RUN"]
    skip_tests   = [d for d in decisions if d["decision"] == "SKIP"]
    total_time   = sum(t.get("execution_time", 0.5) for t in all_tests)
    selected_time = sum(t.get("execution_time", 0.5) for t in run_tests)
    time_saved   = total_time - selected_time
    time_saved_pct = round((time_saved / max(total_time, 1.0)) * 100, 1)

    summary = {
        "total_tests": len(all_tests),
        "tests_selected": len(run_tests),
        "tests_skipped": len(skip_tests),
        "total_runtime_minutes": round(total_time / 60.0, 2),
        "selected_runtime_minutes": round(selected_time / 60.0, 2),
        "time_saved_minutes": round(time_saved / 60.0, 2),
        "time_reduction_pct": time_saved_pct,
        "covered_tests": len(covered_ids),
        "dep_tests": len(dep_test_ids),
        "failure_tests": len(failure_ids),
        "dep_available": dep_available,
        "cov_available": cov_available,
        "fail_available": fail_available,
    }

    return {
        "change_context": change_ctx,
        "dependency_info": dep_info,
        "coverage_info": cov_info,
        "failure_info": fail_info,
        "decisions": decisions,
        "summary": summary,
    }


def _empty_result(change_ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "change_context": change_ctx,
        "dependency_info": {},
        "coverage_info": {},
        "failure_info": {},
        "decisions": [],
        "summary": {
            "total_tests": 0, "tests_selected": 0, "tests_skipped": 0,
            "time_reduction_pct": 0, "dep_available": False,
            "cov_available": False, "fail_available": False,
        },
    }
