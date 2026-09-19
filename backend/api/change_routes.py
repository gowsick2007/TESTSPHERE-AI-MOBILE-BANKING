"""
TestSphere AI — Change Analysis Routes
Endpoints to record and inspect code changes.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from backend.schemas import ChangeAnalysisRequest
from backend.engine.change_analyzer import analyze_change
from backend.engine.dependency_analyzer import get_impacted_files
from backend.engine.coverage_analyzer import find_covered_tests
from backend.engine.data_access import get_code_changes, get_db_connection
from backend.api.auth_routes import get_user_from_token

from backend.security.input_validator import detect_bypass_attempt

router = APIRouter(prefix="/change", tags=["Change Analysis"])


@router.post("/analyze")
def analyze(payload: ChangeAnalysisRequest, user: dict = Depends(get_user_from_token)):
    """Analyze changed files and report impact predictions."""
    try:
        ctx = analyze_change(
            changed_files=payload.changed_files,
            change_type=payload.change_type,
            module=payload.module,
            is_security_sensitive=payload.is_security_sensitive,
            risk_level=payload.risk_level
        )
        dep_info = get_impacted_files(payload.changed_files)
        
        all_impacted = dep_info.get("all_impacted", []) + payload.changed_files
        cov_info = find_covered_tests(list(set(all_impacted)))

        return {
            "change_context": ctx,
            "dependency_impact": dep_info,
            "coverage_impact": cov_info
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis calculation error: {str(exc)}")


@router.get("/history")
def get_history():
    """Retrieve database change records."""
    return {"changes": get_code_changes()}


@router.post("/register")
def register_change(payload: ChangeAnalysisRequest, user: dict = Depends(get_user_from_token)):
    """Saves a new change request into SQLite."""
    role = user["role"]
    blocked, msg = detect_bypass_attempt("REGISTER_CHANGE", f"Register change targeting {payload.changed_files}", role)
    if blocked:
        raise HTTPException(status_code=403, detail=msg)
    conn = get_db_connection()
    try:
        import uuid
        from datetime import datetime
        chg_id = f"CHG-{uuid.uuid4().hex[:6].upper()}"
        fp_str = ",".join(payload.changed_files)
        mod = payload.module or "Payment"
        
        conn.execute("""
            INSERT INTO code_changes (change_id, file_path, module, change_type, is_security_sensitive, risk_level, changed_at, changed_by, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            chg_id,
            fp_str,
            mod,
            payload.change_type,
            1 if payload.is_security_sensitive else 0,
            payload.risk_level,
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            user["username"],
            f"Code change submission targeting: {fp_str}"
        ))
        conn.commit()
        return {"success": True, "change_id": chg_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database change save failed: {str(exc)}")
    finally:
        conn.close()
