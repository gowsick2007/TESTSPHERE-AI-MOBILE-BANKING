"""
TestSphere AI — Controlled Execution Plan Routes (Phase 2)
Manages the controlled execution workflow:
CHANGE ➔ IMPACT ➔ SELECTION ➔ PLAN ➔ EXECUTE (SIMULATED or ACTUAL) ➔ REPORT ➔ AUDIT
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from backend.schemas import ExecutionPlanRequest, ExecutePlanRequest
from backend.engine.execution_manager import (
    create_execution_plan,
    execute_plan,
    get_execution_plan,
    list_execution_plans,
)
from backend.api.auth_routes import get_user_from_token
from backend.security.input_validator import detect_bypass_attempt

router = APIRouter(prefix="/execution", tags=["Execution Management"])


@router.post("/plan")
def api_create_execution_plan(payload: ExecutionPlanRequest, user: dict = Depends(get_user_from_token)):
    """Creates a controlled execution plan from change impact selection."""
    role = user.get("role", "VIEWER")
    blocked, msg = detect_bypass_attempt("CREATE_PLAN", f"Create execution plan for {payload.changed_files}", role)
    if blocked:
        raise HTTPException(status_code=403, detail=msg)

    try:
        plan = create_execution_plan(
            changed_files=payload.changed_files,
            change_type=payload.change_type,
            module=payload.module,
            is_security_sensitive=payload.is_security_sensitive,
            risk_level=payload.risk_level,
            strategy=payload.strategy,
            created_by=user.get("username", "system"),
            change_id=payload.change_id,
        )
        return plan
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create execution plan: {str(exc)}")


@router.post("/run")
def api_execute_plan(payload: ExecutePlanRequest, user: dict = Depends(get_user_from_token)):
    """Executes a previously staged plan (SIMULATED or ACTUAL) and generates report."""
    role = user.get("role", "VIEWER")
    blocked, msg = detect_bypass_attempt("RUN_PLAN", f"Execute plan {payload.plan_id} ({payload.execution_type})", role)
    if blocked:
        raise HTTPException(status_code=403, detail=msg)

    try:
        report = execute_plan(
            plan_id=payload.plan_id,
            execution_type=payload.execution_type,
            executed_by=user.get("username", "system"),
            experiment_id=payload.experiment_id,
        )
        return report
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except NotImplementedError as nie:
        raise HTTPException(status_code=501, detail=str(nie))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to execute plan: {str(exc)}")


@router.get("/history")
def api_list_execution_plans(limit: int = 50):
    """Retrieves list of past execution plans."""
    return {"plans": list_execution_plans(limit=limit)}


@router.get("/{plan_id}")
def api_get_execution_plan(plan_id: str):
    """Retrieves execution plan metadata and individual test execution outcomes."""
    plan = get_execution_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Execution plan '{plan_id}' not found.")
    return plan
