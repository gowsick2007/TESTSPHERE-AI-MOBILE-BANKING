"""
TestSphere AI — Test Selector (Core Engine)
Orchestrates the full selection pipeline:
  Change Analysis → Dependency → Coverage → Failure → Scoring → Safety Overrides → Decision
"""
import logging
import json
from pathlib import Path
from Engine.data_access import get_all_tests, get_data_health
from Engine.change_analyzer import analyze_change
from Engine.dependency_analyzer import get_impacted_files, build_dependency_graph
from Engine.coverage_analyzer import find_covered_tests
from Engine.failure_analyzer import find_failure_associated_tests
from Engine.risk_scorer import score_all_tests, RUN_THRESHOLD
from Engine.safety_overrides import evaluate_safety_overrides, determine_confidence
from Engine.rationale_generator import generate_rationale, format_decision_record

logger = logging.getLogger(__name__)

_BASE = Path(__file__).resolve().parent.parent
with open(_BASE / "config.json") as _f:
    _CFG = json.load(_f)


def run_selection(
    changed_files: list[str],
    change_type: str = "MODIFIED",
    module: str | None = None,
    is_security_sensitive: bool = False,
    risk_level: str = "MEDIUM",
) -> dict:
    """
    Full test selection pipeline.

    Returns:
        dict with:
            change_context   — output of change_analyzer
            dependency_info  — impacted files
            coverage_info    — covered test IDs
            failure_info     — failure-associated test IDs
            decisions        — list of decision records (RUN/SKIP + rationale)
            summary          — aggregated metrics
    """
    logger.info("Starting test selection for: %s", changed_files)

    # ── Step 1: Check data availability ───────────────────────────────────────
    health = get_data_health()
    dep_available = health["ready"] > 0
    cov_available = health["ready"] > 0
    fail_available = health["ready"] > 0

    # ── Step 2: Analyze change ─────────────────────────────────────────────────
    change_ctx = analyze_change(
        changed_files=changed_files,
        change_type=change_type,
        module=module,
        is_security_sensitive=is_security_sensitive,
        risk_level=risk_level,
    )

    # ── Step 3: Find impacted files via dependency graph ───────────────────────
    dep_info = get_impacted_files(changed_files)
    dep_available = dep_info.get("graph_available", False)
    # Safety Check: If we have no changed files, or any changed file is not tracked in the graph,
    # we treat dependency information as unavailable to trigger the RULE_1 safety override.
    try:
        graph = build_dependency_graph()
        if not changed_files or any(f not in graph for f in changed_files):
            dep_available = False
    except Exception:
        dep_available = False

    # ── Step 4: Find tests covering impacted files ─────────────────────────────
    all_impacted = dep_info.get("all_impacted", []) + changed_files
    cov_info = find_covered_tests(list(set(all_impacted)))
    cov_available = cov_info.get("coverage_available", False)
    covered_ids: set[str] = set(cov_info.get("covered_tests", []))

    # ── Step 5: Get all tests ──────────────────────────────────────────────────
    all_tests = get_all_tests()
    if not all_tests:
        logger.warning("No tests found in database — returning empty selection")
        return _empty_result(change_ctx)

    # ── Step 6: Find dependency-related tests ──────────────────────────────────
    # Tests covering files in the dependency graph (not just direct coverage)
    dep_cov = find_covered_tests(dep_info.get("direct", []) + dep_info.get("indirect", []))
    dep_test_ids: set[str] = set(dep_cov.get("covered_tests", []))

    # ── Step 7: Find failure-associated tests ─────────────────────────────────
    fail_info = find_failure_associated_tests(
        affected_modules=change_ctx.get("affected_modules", []),
        all_tests=all_tests,
    )
    fail_available = fail_info.get("failure_data_available", False)
    failure_ids: set[str] = set(fail_info.get("associated_tests", []))

    # ── Step 8: Score all tests ────────────────────────────────────────────────
    scored = score_all_tests(
        all_tests=all_tests,
        covered_test_ids=covered_ids,
        dependency_test_ids=dep_test_ids,
        failure_associated_ids=failure_ids,
        is_security_sensitive=is_security_sensitive or change_ctx.get("is_security_sensitive", False),
        affected_modules=change_ctx.get("affected_modules", []),
    )

    # ── Step 9: Apply safety overrides + determine final decision ─────────────
    decisions: list[dict] = []
    for scored_test in scored:
        score = scored_test["risk_score"]
        evidence = scored_test["evidence"]
        confidence = determine_confidence(score, evidence)

        overrides = evaluate_safety_overrides(
            test=scored_test,
            dep_info_available=dep_available,
            coverage_info_available=cov_available,
            failure_data_available=fail_available,
            confidence_level=confidence,
        )

        # Decision logic
        if overrides:
            decision = "RUN"
        elif score >= RUN_THRESHOLD:
            decision = "RUN"
        else:
            decision = "SKIP"

        rationale = generate_rationale(
            test=scored_test,
            decision=decision,
            score=score,
            evidence=evidence,
            overrides=[o.to_dict() for o in overrides],
            confidence=confidence,
        )

        record = format_decision_record(
            test=scored_test,
            decision=decision,
            score=score,
            confidence=confidence,
            evidence=evidence,
            overrides=[o.to_dict() for o in overrides],
            rationale=rationale,
        )
        decisions.append(record)

    # ── Step 10: Compute summary ───────────────────────────────────────────────
    run_tests    = [d for d in decisions if d["decision"] == "RUN"]
    skip_tests   = [d for d in decisions if d["decision"] == "SKIP"]
    total_time   = sum(t.get("execution_time", 0.5) for t in all_tests)
    selected_time = sum(t.get("execution_time", 0.5) for t in run_tests)
    time_saved   = total_time - selected_time
    time_saved_pct = round((time_saved / max(total_time, 1)) * 100, 1)

    summary = {
        "total_tests": len(all_tests),
        "tests_selected": len(run_tests),
        "tests_skipped": len(skip_tests),
        "total_runtime_minutes": round(total_time / 60, 2),
        "selected_runtime_minutes": round(selected_time / 60, 2),
        "time_saved_minutes": round(time_saved / 60, 2),
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


def _empty_result(change_ctx: dict) -> dict:
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
