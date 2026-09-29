"""
TestSphere AI — Rollback & Strategy Routes (Phase 2)
Endpoints to query current selection strategy, trigger rolling back to legacy full suite,
and manage strategy versioning.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from backend.schemas import RollbackRequest, StrategyVersionCreateRequest
from backend.rollback.rollback_manager import (
    change_system_strategy,
    get_rollback_logs,
    create_strategy_version,
    list_strategy_versions,
)
from backend.engine.data_access import get_current_strategy
from backend.security.input_validator import detect_bypass_attempt
from backend.api.auth_routes import get_user_from_token

router = APIRouter(prefix="/strategy", tags=["Rollback & Strategy Control"])


@router.get("")
def get_strategy():
    """Retrieve the current active strategy configuration."""
    curr = get_current_strategy()
    return {"current_strategy": curr}


@router.post("/rollback")
def rollback(payload: RollbackRequest, user: dict = Depends(get_user_from_token)):
    """Triggers an emergency fallback toggle."""
    role = user["role"]

    # Server-side authorization check (ADMIN ONLY)
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


@router.get("/versions")
def get_strategy_versions():
    """Retrieve all recorded strategy versions."""
    versions = list_strategy_versions()
    return {"versions": versions}


@router.post("/versions")
def api_create_strategy_version(payload: StrategyVersionCreateRequest, user: dict = Depends(get_user_from_token)):
    """Registers a new strategy version (ADMIN role required)."""
    role = user["role"]
    if role != "ADMIN":
        raise HTTPException(status_code=403, detail="Permission Denied: Only ADMIN can register strategy versions.")

    try:
        ver = create_strategy_version(
            version_id=payload.version_id,
            strategy_name=payload.strategy_name,
            threshold=payload.threshold,
            scoring_weights=payload.scoring_weights,
            safety_rules=payload.safety_rules,
            created_by=user["username"],
            description=payload.description
        )
        return ver
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create strategy version: {str(exc)}")

