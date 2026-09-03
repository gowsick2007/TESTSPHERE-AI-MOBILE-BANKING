"""
TestSphere AI — Experiment Lab Routes
Benchmarks Smart vs Baseline, and runs failure mode simulations.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from backend.schemas import ChangeAnalysisRequest
from backend.simulation.experiment_engine import run_experiment_comparison
from backend.simulation.failure_simulator import run_all_failure_scenarios, SCENARIOS
from backend.api.auth_routes import get_user_from_token
from backend.engine.audit_logger import log_event

router = APIRouter(prefix="/experiment", tags=["Experiment Lab"])


@router.post("/run")
def run_experiment(payload: ChangeAnalysisRequest, token: Optional[str] = None):
    """Executes a side-by-side benchmark comparison."""
    user = get_user_from_token(token)
    try:
        res = run_experiment_comparison(
            changed_files=payload.changed_files,
            change_type=payload.change_type,
            module=payload.module,
            is_security_sensitive=payload.is_security_sensitive,
            risk_level=payload.risk_level
        )
        log_event(
            action="RUN_EXPERIMENT",
            username=user["username"],
            input_summary=f"Compared Smart vs Baseline for changes: {payload.changed_files}",
            result=f"Smart: {res['comparison']['tests_run_smart']} tests, Time Saved: {res['comparison']['time_reduction_pct']}%"
        )
        return res
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Experiment benchmark failed: {str(exc)}")


@router.get("/scenarios")
def get_scenarios():
    """Fetch the list of failure scenarios."""
    return {"scenarios": SCENARIOS}


@router.post("/run-scenarios")
def run_scenarios(token: Optional[str] = None):
    """Executes all 5 failure mode simulation assertions."""
    user = get_user_from_token(token)
    try:
        results = run_all_failure_scenarios()
        # Count passes
        passes = sum(1 for r in results if r["verdict"] == "PASS")
        log_event(
            action="RUN_FAILURE_SCENARIOS",
            username=user["username"],
            input_summary=f"Executed 5 safety scenarios",
            result=f"Passed {passes}/5 scenarios"
        )
        return {"results": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failure simulator run crashed: {str(exc)}")
