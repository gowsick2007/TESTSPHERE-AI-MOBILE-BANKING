"""
TestSphere AI — Test Operations Routes
Endpoints to query test metadata, fetch selections, and run simulations.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from backend.schemas import ChangeAnalysisRequest, SelectionResponse
from backend.engine.test_selector import run_selection
from backend.simulation.smart_runner import run_smart_regression
from backend.simulation.baseline_runner import run_baseline_regression
from backend.engine.data_access import get_all_tests, get_db_connection
from backend.engine.coverage_analyzer import compute_coverage_stats
from backend.engine.failure_analyzer import get_failure_stats
from backend.api.auth_routes import get_user_from_token
from backend.engine.audit_logger import log_event

from backend.security.input_validator import detect_bypass_attempt

router = APIRouter(prefix="/tests", tags=["Test Selection"])


@router.post("/selection", response_model=SelectionResponse)
def get_selection(payload: ChangeAnalysisRequest, user: dict = Depends(get_user_from_token)):
    """Computes selector decisions (RUN/SKIP) for all tests."""
    try:
        res = run_selection(
            changed_files=payload.changed_files,
            change_type=payload.change_type,
            module=payload.module,
            is_security_sensitive=payload.is_security_sensitive,
            risk_level=payload.risk_level
        )
        return res
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Selection engine crash: {str(exc)}")


@router.post("/run-smart")
def run_smart(payload: ChangeAnalysisRequest, user: dict = Depends(get_user_from_token)):
    """Executes selector and simulates selected test runs."""
    role = user["role"]
    blocked, msg = detect_bypass_attempt("RUN_TESTS", f"Run smart tests for {payload.changed_files}", role)
    if blocked:
        raise HTTPException(status_code=403, detail=msg)
    try:
        res = run_smart_regression(
            changed_files=payload.changed_files,
            change_type=payload.change_type,
            module=payload.module,
            is_security_sensitive=payload.is_security_sensitive,
            risk_level=payload.risk_level
        )
        log_event(
            action="RUN_SMART_SUITE",
            username=user["username"],
            input_summary=f"Ran smart regression for {payload.changed_files}",
            system_mode="SMART_SELECTOR",
            decision="SUCCESS",
            result=f"Executed {res['execution']['total_selected']} tests"
        )
        return res
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Smart execution crash: {str(exc)}")


@router.post("/run-baseline")
def run_baseline(user: dict = Depends(get_user_from_token)):
    """Executes simulated baseline regression (runs all tests)."""
    role = user["role"]
    blocked, msg = detect_bypass_attempt("RUN_TESTS", "Run baseline tests", role)
    if blocked:
        raise HTTPException(status_code=403, detail=msg)
    try:
        res = run_baseline_regression()
        log_event(
            action="RUN_BASELINE_SUITE",
            username=user["username"],
            input_summary="Ran legacy full regression suite",
            system_mode="LEGACY_FULL_SUITE",
            decision="SUCCESS",
            result=f"Executed {res['total_tests']} tests"
        )
        return res
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Baseline execution crash: {str(exc)}")


@router.get("/coverage")
def get_coverage():
    """Computes test coverage stats."""
    tests = get_all_tests()
    stats = compute_coverage_stats(tests)
    return {"stats": stats, "tests": tests}


@router.get("/failures")
def get_failures():
    """Computes test failures stats."""
    stats = get_failure_stats()
    return stats


@router.get("/{test_id}")
def get_test_by_id(test_id: str):
    """Fetches details for a single test."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM test_coverage WHERE test_id = ?", (test_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Test {test_id} not found.")
        return dict(row)
    finally:
        conn.close()


@router.get("")
def list_tests():
    """Fetch all tests in the system."""
    return {"tests": get_all_tests()}
