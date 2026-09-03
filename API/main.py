"""
TestSphere AI — FastAPI Backend
Provides REST endpoints consumed by the premium HTML/JS frontend.
"""
import sys
import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# Import routers from the backend package to enable premium HTML frontend API connectivity
from backend.api.auth_routes import router as auth_router
from backend.api.data_routes import router as data_router
from backend.api.change_routes import router as change_router
from backend.api.test_routes import router as test_router
from backend.api.experiment_routes import router as experiment_router
from backend.api.rollback_routes import router as rollback_router
from backend.api.audit_routes import router as audit_router
from backend.schemas import WhatIfRequest
from backend.engine.data_access import get_all_tests
from backend.engine.risk_scorer import compute_risk_score, RUN_THRESHOLD

from Engine.database import initialize_database
from Engine.test_selector import run_selection
from Engine.data_access import (
    get_all_tests as engine_get_all_tests, get_all_changes, get_data_health,
    get_current_strategy, get_device_matrix,
)
from Engine.change_analyzer import analyze_change, get_recent_changes
from Engine.audit_logger import get_audit_log, log_event
from Engine.failure_analyzer import get_failure_stats
from Engine.metrics_calculator import calculate_experiment_metrics, calculate_time_metrics
from Simulation.baseline_runner import run_baseline
from Simulation.smart_runner import run_smart
from Simulation.experiment_engine import run_experiment
from Simulation.failure_simulator import run_all_scenarios, SCENARIOS
from Rollback.rollback_manager import (
    get_strategy_info, switch_strategy,
    rollback_to_legacy, restore_smart_selector, get_rollback_history
)
from Security.input_validator import validate_file_paths, validate_test_id, detect_bypass_attempt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize DB on startup
initialize_database()

app = FastAPI(
    title="TestSphere AI API",
    description="Change Impact Test Selection Backend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Mount Backend Routers for HTML Frontend ─────────────────────────────────
api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(data_router)
api_router.include_router(change_router)
api_router.include_router(test_router)
api_router.include_router(experiment_router)
api_router.include_router(rollback_router)
api_router.include_router(audit_router)

@api_router.post("/what-if")
def what_if(payload: WhatIfRequest):
    """Simulates selector decisions for a custom changed module and device combination."""
    tests = get_all_tests()
    if not tests:
        return {
            "potentially_affected_tests": 0,
            "estimated_runtime_minutes": 0.0,
            "selected_tests": 0,
            "skipped_tests": 0,
            "overall_risk": "LOW"
        }
    
    from backend.engine.data_access import get_all_failures, get_device_matrix
    try:
        failures = get_all_failures()
        failed_ids = {f["test_id"] for f in failures}
    except Exception:
        failed_ids = set()

    try:
        matrix = get_device_matrix()
        device_risks = {}
        for d in matrix:
            key = (d["device_name"].lower(), d["os_version"].lower())
            risk = d["risk_level"].upper()
            score = 100 if risk == "CRITICAL" else (80 if risk == "HIGH" else (50 if risk == "MEDIUM" else 20))
            device_risks[key] = max(device_risks.get(key, 0), score)
    except Exception:
        device_risks = {}

    affected_count = 0
    selected_count = 0
    skipped_count = 0
    runtime = 0.0
    for t in tests:
        is_module_match = (t["module"].lower() == payload.module.lower())
        is_device_match = (t["device"].lower() == payload.device.lower())
        if is_module_match or is_device_match:
            affected_count += 1
            runtime += t["execution_time"]
            cov_set = {t["test_id"]} if is_module_match else set()
            dep_set = {t["test_id"]} if is_module_match else set()
            fail_set = {t["test_id"]} if is_module_match else set()
            score, evidence = compute_risk_score(
                test=t,
                covered_test_ids=cov_set,
                dependency_test_ids=dep_set,
                failure_associated_ids=fail_set,
                is_security_sensitive=payload.is_security_sensitive,
                affected_modules=[payload.module] if is_module_match else [],
                failed_ids=failed_ids,
                device_risks=device_risks,
            )
            if score >= RUN_THRESHOLD or payload.is_security_sensitive:
                selected_count += 1
            else:
                skipped_count += 1
    return {
        "potentially_affected_tests": affected_count,
        "estimated_runtime_minutes": round(runtime / 60.0, 2),
        "selected_tests": selected_count,
        "skipped_tests": skipped_count,
        "overall_risk": "HIGH" if payload.is_security_sensitive or payload.risk_level == "HIGH" else "MEDIUM"
    }

app.include_router(api_router)


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")

@app.get("/", response_class=HTMLResponse)
def read_root():
    index_path = FRONTEND_DIR / "index.html"
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()


# ─── Request Models ───────────────────────────────────────────────────────────

class ChangeAnalysisRequest(BaseModel):
    changed_files: list[str]
    change_type: str = "MODIFIED"
    module: Optional[str] = None
    is_security_sensitive: bool = False
    risk_level: str = "MEDIUM"


class RollbackRequest(BaseModel):
    to_strategy: str
    reason: str = ""
    changed_by: str = "system"


class WhatIfRequest(BaseModel):
    module: str
    device: str
    change_type: str = "MODIFIED"


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}


@app.get("/data-health")
def data_health():
    return get_data_health()


# ─── Change Analysis ──────────────────────────────────────────────────────────

@app.post("/analyze-change")
def api_analyze_change(req: ChangeAnalysisRequest):
    try:
        paths = validate_file_paths(req.changed_files)
    except Exception as e:
        log_event("SECURITY_REJECTION", result=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    ctx = analyze_change(
        changed_files=paths,
        change_type=req.change_type,
        module=req.module,
        is_security_sensitive=req.is_security_sensitive,
        risk_level=req.risk_level,
    )
    log_event("CHANGE_ANALYSIS", input_summary=str(paths), result="success")
    return ctx


@app.post("/test-selection")
def api_test_selection(req: ChangeAnalysisRequest):
    try:
        paths = validate_file_paths(req.changed_files)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = run_selection(
        changed_files=paths,
        change_type=req.change_type,
        module=req.module,
        is_security_sensitive=req.is_security_sensitive,
        risk_level=req.risk_level,
    )

    run_count  = sum(1 for d in result["decisions"] if d["decision"] == "RUN")
    skip_count = sum(1 for d in result["decisions"] if d["decision"] == "SKIP")
    log_event("TEST_SELECTION", decision=f"RUN={run_count} SKIP={skip_count}",
              system_mode=get_current_strategy(), result="success")
    return result


# ─── Baseline / Smart Runs ───────────────────────────────────────────────────

@app.post("/run-baseline")
def api_run_baseline():
    result = run_baseline()
    log_event("LEGACY_RUN", system_mode="LEGACY_FULL_SUITE",
              result=f"Executed {result['executed']} tests")
    return result


@app.post("/run-smart")
def api_run_smart(req: ChangeAnalysisRequest):
    selection = run_selection(
        changed_files=req.changed_files,
        change_type=req.change_type,
        module=req.module,
        is_security_sensitive=req.is_security_sensitive,
        risk_level=req.risk_level,
    )
    smart = run_smart(selection["decisions"])
    log_event("SMART_RUN", system_mode="SMART_SELECTOR",
              result=f"Executed {smart['executed']} tests")
    return {"selection": selection, "execution": smart}


# ─── Experiment ───────────────────────────────────────────────────────────────

@app.post("/experiment")
def api_experiment(req: ChangeAnalysisRequest):
    result = run_experiment(
        changed_files=req.changed_files,
        change_type=req.change_type,
        module=req.module,
        is_security_sensitive=req.is_security_sensitive,
        risk_level=req.risk_level,
    )
    log_event("EXPERIMENT_RUN", result=f"Time reduction {result['comparison']['time_reduction_pct']}%")
    return result


# ─── Failure Scenarios ────────────────────────────────────────────────────────

@app.get("/failure-scenarios")
def api_failure_scenarios():
    return {"scenarios": SCENARIOS}


@app.post("/run-failure-scenarios")
def api_run_failure_scenarios():
    results = run_all_scenarios()
    log_event("FAILURE_SCENARIO_RUN", result=f"{sum(1 for r in results if r['verdict']=='PASS')}/5 passed")
    return {"results": results}


# ─── Strategy / Rollback ──────────────────────────────────────────────────────

@app.get("/strategy")
def api_get_strategy():
    return get_strategy_info()


@app.post("/rollback")
def api_rollback(req: RollbackRequest):
    blocked, reason = detect_bypass_attempt("ROLLBACK", target=req.to_strategy, user_role="ADMIN")
    result = switch_strategy(req.to_strategy, req.reason, req.changed_by)
    return result


@app.get("/rollback-history")
def api_rollback_history():
    return {"history": get_rollback_history()}


# ─── Audit Log ────────────────────────────────────────────────────────────────

@app.get("/audit-log")
def api_audit_log(action: str = "", username: str = "", limit: int = 100):
    return {"logs": get_audit_log(action, username, limit)}


# ─── What-If ─────────────────────────────────────────────────────────────────

@app.post("/what-if")
def api_what_if(req: WhatIfRequest):
    from Engine.data_access import get_tests_by_module
    tests = get_tests_by_module(req.module)
    device_tests = [t for t in tests if t.get("device") == req.device]
    all_module_time = sum(t.get("execution_time", 0.5) for t in tests)
    return {
        "module": req.module,
        "device": req.device,
        "change_type": req.change_type,
        "potentially_affected_tests": len(tests),
        "device_specific_tests": len(device_tests),
        "estimated_runtime_minutes": round(all_module_time / 60, 2),
        "risk_level": "HIGH" if req.module in [
            "Authentication", "Payment", "OTP", "FraudDetection"
        ] else "MEDIUM",
    }


# ─── Data ────────────────────────────────────────────────────────────────────

@app.get("/changes")
def api_get_changes():
    return {"changes": get_recent_changes(30)}


@app.get("/devices")
def api_get_devices():
    return {"devices": get_device_matrix()}
@app.get("/failure-stats")
def api_failure_stats():
    return get_failure_stats()
if __name__ == "__main__":
    import uvicorn
    import sys
    print("========================================")
    print("TestSphere.AI Started")
    print("========================================")
    print()
    print("DIRECT WEBPAGE:")
    print("http://127.0.0.1:8001/")
    print()
    print("========================================")
    sys.stdout.flush()
    uvicorn.run(app, host="127.0.0.1", port=8001)
