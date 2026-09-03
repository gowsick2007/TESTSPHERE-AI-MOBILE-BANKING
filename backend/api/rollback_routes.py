"""
TestSphere AI — Rollback & Strategy Routes
Endpoints to query current selection strategy and trigger rolling back to legacy full suite.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from backend.schemas import RollbackRequest
from backend.rollback.rollback_manager import change_system_strategy, get_rollback_logs
from backend.engine.data_access import get_current_strategy
from backend.security.input_validator import detect_bypass_attempt
from backend.api.auth_routes import get_user_from_token

router = APIRouter(prefix="/strategy", tags=["Rollback Control"])


@router.get("")
def get_strategy():
    """Retrieve the current active strategy configuration."""
    curr = get_current_strategy()
    return {"current_strategy": curr}


@router.post("/rollback")
def rollback(payload: RollbackRequest, token: Optional[str] = None):
    """Triggers an emergency fallback toggle."""
    user = get_user_from_token(token)
    role = user["role"]

    # Server-side authorization check
    blocked, msg = detect_bypass_attempt("ROLLBACK", f"Switch strategy to {payload.to_strategy}", role)
    if blocked:
        raise HTTPException(status_code=403, detail=msg)

    # Perform strategy switch
    res = change_system_strategy(
        to_strategy=payload.to_strategy,
        reason=payload.reason,
        changed_by=user["username"]
    )
    if not res.get("success", False):
        raise HTTPException(status_code=400, detail=res.get("error", "Rollback failed."))

    return res


@router.get("/history")
def get_history():
    """Retrieve strategy switch records."""
    logs = get_rollback_logs()
    return {"history": logs}
