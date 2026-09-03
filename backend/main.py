"""
TestSphere AI — FastAPI Application Entry Point
Orchestrates API routers, database schema migrations, and serves the static Web UI.
"""
import uvicorn
from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from backend.database import initialize_database
from backend.schemas import WhatIfRequest
from backend.engine.data_access import get_all_tests
from backend.engine.risk_scorer import compute_risk_score, RUN_THRESHOLD
from backend.engine.safety_overrides import determine_confidence

# Import routers
from backend.api.auth_routes import router as auth_router
from backend.api.data_routes import router as data_router
from backend.api.change_routes import router as change_router
from backend.api.test_routes import router as test_router
from backend.api.experiment_routes import router as experiment_router
from backend.api.rollback_routes import router as rollback_router
from backend.api.audit_routes import router as audit_router

app = FastAPI(
    title="TestSphere AI",
    description="Intelligent Change Impact Test Selection & Risk Analysis Platform",
    version="1.0.0"
)

# Enable CORS for development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Initialization
@app.on_event("startup")
def on_startup():
    initialize_database()


# Include Router API prefixes under /api
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
    """
    Simulates selector decisions for a custom changed module and device combination.
    """
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

    # We evaluate tests based on target module
    for t in tests:
        is_module_match = (t["module"].lower() == payload.module.lower())
        is_device_match = (t["device"].lower() == payload.device.lower())

        if is_module_match or is_device_match:
            affected_count += 1
            runtime += t["execution_time"]

            # Calculate mock score
            # (If it matches module and device, risk scoring will evaluate it)
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


@api_router.get("/health")
def health():
    return {"status": "ok", "service": "TestSphere AI Engine"}


app.include_router(api_router)

# Mount static frontend files
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

# Mount frontend files under /frontend path
app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")


# Serve index.html at root url /
@app.get("/")
def get_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "TestSphere Frontend Static Directory Mounted. Add index.html to serve."}


# Serve pages directly at /pages/page_name.html to match routing path expectations
@app.get("/pages/{page_name}")
def get_page(page_name: str):
    page_file = FRONTEND_DIR / "pages" / page_name
    if page_file.exists():
        return FileResponse(str(page_file))
    raise HTTPException(status_code=404, detail=f"Page {page_name} not found.")


if __name__ == "__main__":
    import sys
    print("========================================")
    print("TestSphere.AI Frontend Started")
    print("========================================")
    print()
    print("DIRECT WEBPAGE:")
    print("http://127.0.0.1:8001/")
    print()
    print("ALTERNATIVE:")
    print("http://localhost:8001/")
    print()
    print("========================================")
    sys.stdout.flush()
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8001, reload=True)
