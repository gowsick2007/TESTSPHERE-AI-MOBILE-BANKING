"""
TestSphere AI — Experiment Lab Routes (Phase 2)
Benchmarks Smart vs Baseline, executes failure mode simulations,
manages immutable experiment history, and compares multi-scenario metrics.
"""
import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List

from backend.schemas import ChangeAnalysisRequest, ExperimentCreateRequest, ExperimentCompareRequest
from backend.simulation.experiment_engine import run_experiment_comparison
from backend.simulation.failure_simulator import run_all_failure_scenarios, SCENARIOS
from backend.api.auth_routes import get_user_from_token
from backend.engine.audit_logger import log_event
from backend.database import get_db_connection
from backend.security.input_validator import detect_bypass_attempt

router = APIRouter(prefix="/experiment", tags=["Experiment Lab"])


@router.post("/run")
def run_experiment(payload: ChangeAnalysisRequest, user: dict = Depends(get_user_from_token)):
    """Executes a side-by-side benchmark comparison."""
    role = user["role"]
    blocked, msg = detect_bypass_attempt("RUN_EXPERIMENT", f"Compared Smart vs Baseline for changes: {payload.changed_files}", role)
    if blocked:
        raise HTTPException(status_code=403, detail=msg)
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


@router.post("/create")
def api_create_experiment(payload: ExperimentCreateRequest, user: dict = Depends(get_user_from_token)):
    """Creates a managed, immutable experiment record with deterministic execution results."""
    role = user["role"]
    blocked, msg = detect_bypass_attempt("CREATE_EXPERIMENT", f"Created experiment for {payload.scenario}", role)
    if blocked:
        raise HTTPException(status_code=403, detail=msg)

    exp_id = f"EXP-{uuid.uuid4().hex[:8].upper()}"
    start_time = datetime.now(timezone.utc).isoformat()

    try:
        res = run_experiment_comparison(
            changed_files=payload.changed_files,
            module=payload.module,
            is_security_sensitive=payload.is_security_sensitive,
            risk_level=payload.risk_level,
        )
        end_time = datetime.now(timezone.utc).isoformat()

        conn = get_db_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT INTO experiments 
                    (experiment_id, scenario, configuration, threshold, dataset_version, seed, start_time, end_time, metrics, results, status, created_by)
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, 'COMPLETED', ?)
                """, (
                    exp_id,
                    payload.scenario,
                    json.dumps({
                        "changed_files": payload.changed_files,
                        "module": payload.module,
                        "is_security_sensitive": payload.is_security_sensitive,
                        "risk_level": payload.risk_level
                    }),
                    payload.threshold,
                    payload.seed,
                    start_time,
                    end_time,
                    json.dumps(res.get("comparison", {})),
                    json.dumps(res.get("quality", {})),
                    user.get("username", "system")
                ))
        finally:
            conn.close()

        log_event(
            action="CREATE_EXPERIMENT",
            username=user["username"],
            input_summary=f"Saved experiment {exp_id} ({payload.scenario})",
            decision="COMPLETED",
            result=f"Reduction: {res['comparison']['time_reduction_pct']}%, Precision: {res['quality']['precision']}"
        )

        return {
            "experiment_id": exp_id,
            "scenario": payload.scenario,
            "threshold": payload.threshold,
            "seed": payload.seed,
            "start_time": start_time,
            "end_time": end_time,
            "status": "COMPLETED",
            "metrics": res.get("comparison", {}),
            "quality": res.get("quality", {}),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to record experiment: {str(exc)}")


@router.get("/history")
def api_list_experiments(limit: int = 50):
    """Retrieves list of immutable completed experiments."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT experiment_id, scenario, threshold, seed, start_time, end_time, status, created_by, metrics FROM experiments ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        result = []
        for r in rows:
            item = dict(r)
            if item.get("metrics"):
                try:
                    item["metrics"] = json.loads(item["metrics"])
                except Exception:
                    pass
            result.append(item)
        return {"experiments": result}
    finally:
        conn.close()


@router.get("/scenarios")
def get_scenarios():
    """Fetch the list of failure scenarios."""
    return {"scenarios": SCENARIOS}


@router.post("/run-scenarios")
def run_scenarios(user: dict = Depends(get_user_from_token)):
    """Executes all 5 failure mode simulation assertions."""
    role = user["role"]
    blocked, msg = detect_bypass_attempt("RUN_SCENARIOS", "Executed 5 safety scenarios", role)
    if blocked:
        raise HTTPException(status_code=403, detail=msg)
    try:
        results = run_all_failure_scenarios()
        passes = sum(1 for r in results if r["verdict"] == "PASS")
        log_event(
            action="RUN_FAILURE_SCENARIOS",
            username=user["username"],
            input_summary="Executed 5 safety scenarios",
            result=f"Passed {passes}/5 scenarios"
        )
        return {"results": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failure simulator run crashed: {str(exc)}")


@router.post("/compare")
def api_compare_experiments(payload: ExperimentCompareRequest):
    """Dynamically compares multiple saved experiments side-by-side."""
    if not payload.experiment_ids:
        raise HTTPException(status_code=400, detail="experiment_ids list cannot be empty.")

    conn = get_db_connection()
    try:
        placeholders = ",".join("?" for _ in payload.experiment_ids)
        rows = conn.execute(
            f"SELECT * FROM experiments WHERE experiment_id IN ({placeholders})",
            payload.experiment_ids
        ).fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="No matching experiments found.")

        comparisons = []
        for r in rows:
            data = dict(r)
            try:
                data["configuration"] = json.loads(data["configuration"])
                data["metrics"] = json.loads(data["metrics"])
                data["results"] = json.loads(data["results"])
            except Exception:
                pass
            comparisons.append(data)

        return {
            "total_compared": len(comparisons),
            "experiments": comparisons,
        }
    finally:
        conn.close()


@router.get("/{experiment_id}")
def api_get_experiment(experiment_id: str):
    """Retrieves an immutable experiment record by ID."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM experiments WHERE experiment_id = ?", (experiment_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
        data = dict(row)
        try:
            data["configuration"] = json.loads(data["configuration"])
            data["metrics"] = json.loads(data["metrics"])
            data["results"] = json.loads(data["results"])
        except Exception:
            pass
        return data
    finally:
        conn.close()


@router.put("/{experiment_id}")
def api_update_experiment_blocked(experiment_id: str, user: dict = Depends(get_user_from_token)):
    """Completed experiment records are immutable by design and cannot be modified."""
    raise HTTPException(status_code=400, detail="Completed experiment records are locked and immutable.")

