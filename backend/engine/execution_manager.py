"""
TestSphere AI — Controlled Test Execution Manager (Phase 2)
Orchestrates the complete execution workflow:
CHANGE ➔ IMPACT ANALYSIS ➔ TEST SELECTION ➔ EXECUTION PLAN ➔ RUN SELECTED TESTS ➔
COLLECT RESULTS ➔ COMPARE EXPECTED/ACTUAL ➔ GENERATE REPORT ➔ AUDIT
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from backend.database import get_db_connection
from backend.engine.test_selector import run_selection
from backend.engine.data_access import get_all_tests
from backend.engine.audit_logger import log_event

logger = logging.getLogger(__name__)


class TestExecutionAdapter:
    """
    Extensible execution adapter interface. Enables plugging in actual
    mobile device farm drivers (Appium, AWS Device Farm, BrowserStack)
    without modifying the selection engine or database schema.
    """
    def execute_test(self, test_id: str, test_metadata: Dict[str, Any], is_affected: bool) -> Dict[str, Any]:
        raise NotImplementedError


class SimulatedExecutionAdapter(TestExecutionAdapter):
    """
    Simulated test execution using metadata runtime estimates and ground-truth failure anomalies.
    """
    def execute_test(self, test_id: str, test_metadata: Dict[str, Any], is_affected: bool) -> Dict[str, Any]:
        duration = test_metadata.get("execution_time", 0.5)
        if is_affected and any(k in test_id for k in ["Payment", "Auth", "Transfer"]):
            return {
                "execution_status": "FAILED",
                "result": "FAIL",
                "duration": duration,
                "failure_reason": "Simulated failure: Regression anomaly detected in impacted component"
            }
        return {
            "execution_status": "PASSED",
            "result": "PASS",
            "duration": duration,
            "failure_reason": None
        }


class PhysicalDeviceFarmAdapter(TestExecutionAdapter):
    """
    Adapter contract for physical mobile device farm dispatch (e.g. Appium / AWS Device Farm).
    Guarantees no fabricated outcomes: if physical hardware is unavailable,
    it raises NotImplementedError rather than generating fake test passes.
    """
    def __init__(self, endpoint: Optional[str] = None):
        self.endpoint = endpoint or "http://127.0.0.1:4723/wd/hub"

    def is_available(self) -> bool:
        """Checks if a physical mobile device farm / Appium runner is connected."""
        return False

    def execute_test(self, test_id: str, test_metadata: Dict[str, Any], is_affected: bool) -> Dict[str, Any]:
        if not self.is_available():
            raise NotImplementedError(
                f"Physical mobile execution unavailable for test '{test_id}': "
                f"No connected device farm / Appium server reachable at {self.endpoint}. "
                "Physical execution requires configured external hardware infrastructure."
            )


def create_execution_plan(
    changed_files: List[str],
    change_type: str = "MODIFIED",
    module: Optional[str] = None,
    is_security_sensitive: bool = False,
    risk_level: str = "MEDIUM",
    strategy: str = "SMART_SELECTOR",
    created_by: str = "system",
    change_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates an execution plan from test selection results and persists to SQLite.
    """
    if not change_id:
        change_id = f"CHG-{uuid.uuid4().hex[:6].upper()}"

    plan_id = f"PLAN-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    selection = run_selection(
        changed_files=changed_files,
        change_type=change_type,
        module=module,
        is_security_sensitive=is_security_sensitive,
        risk_level=risk_level,
    )

    decisions = selection.get("decisions", [])
    selected_tests = [d for d in decisions if d["decision"] == "RUN"]
    skipped_tests = [d for d in decisions if d["decision"] == "SKIP"]
    est_duration = sum(d.get("execution_time", 0.5) for d in selected_tests)

    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO execution_plans 
                (plan_id, change_id, strategy, created_at, created_by, total_tests, selected_tests, skipped_tests, estimated_duration_seconds, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'CREATED')
            """, (
                plan_id, change_id, strategy, now, created_by,
                len(decisions), len(selected_tests), len(skipped_tests), est_duration
            ))
    finally:
        conn.close()

    log_event(
        action="CREATE_EXECUTION_PLAN",
        username=created_by,
        input_summary=f"Plan {plan_id} for change {change_id} ({len(selected_tests)} selected)",
        system_mode=strategy,
        decision="CREATED",
        result=f"Selected {len(selected_tests)} of {len(decisions)} tests"
    )

    return {
        "plan_id": plan_id,
        "change_id": change_id,
        "strategy": strategy,
        "created_at": now,
        "created_by": created_by,
        "total_tests": len(decisions),
        "selected_tests": len(selected_tests),
        "skipped_tests": len(skipped_tests),
        "estimated_duration_seconds": round(est_duration, 2),
        "status": "CREATED",
        "decisions": decisions,
    }


def execute_plan(
    plan_id: str,
    execution_type: str = "SIMULATED",
    executed_by: str = "system",
    experiment_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes an existing plan (SIMULATED or ACTUAL), records each test outcome,
    compares expected vs actual results, and produces an execution report.
    """
    if execution_type not in ["SIMULATED", "ACTUAL"]:
        raise ValueError(f"Invalid execution_type '{execution_type}'. Must be 'SIMULATED' or 'ACTUAL'.")

    conn = get_db_connection()
    try:
        plan_row = conn.execute("SELECT * FROM execution_plans WHERE plan_id = ?", (plan_id,)).fetchone()
        if not plan_row:
            raise ValueError(f"Execution plan '{plan_id}' not found.")
        plan = dict(plan_row)
        change_id = plan["change_id"]

        # Fetch change details to re-run selection or look up ground truth
        change_row = conn.execute("SELECT * FROM code_changes WHERE change_id = ?", (change_id,)).fetchone()
        changed_files = [change_row["file_path"]] if change_row else ["payment/payment.py"]
        mod = change_row["module"] if change_row else "Payment"
        is_sec = bool(change_row["is_security_sensitive"]) if change_row else False
        risk = change_row["risk_level"] if change_row else "MEDIUM"

        selection = run_selection(
            changed_files=changed_files,
            module=mod,
            is_security_sensitive=is_sec,
            risk_level=risk,
        )
        decisions = selection.get("decisions", [])

        # Fetch ground truth for this change
        gt_rows = conn.execute(
            "SELECT test_id, actually_affected FROM experiment_ground_truth WHERE change_id = ?",
            (change_id,)
        ).fetchall()
        ground_truth = {r["test_id"]: bool(r["actually_affected"]) for r in gt_rows}

        now = datetime.now(timezone.utc).isoformat()
        results: List[Dict[str, Any]] = []
        passed = 0
        failed = 0
        skipped = 0
        total_duration = 0.0

        adapter: TestExecutionAdapter = (
            SimulatedExecutionAdapter() if execution_type == "SIMULATED" else PhysicalDeviceFarmAdapter()
        )

        if execution_type == "ACTUAL" and not getattr(adapter, "is_available", lambda: True)():
            msg = (
                "Physical mobile device execution is currently unavailable: "
                "No live Appium server or mobile device farm runner is connected. "
                "Use SIMULATED execution mode or configure external hardware runners."
            )
            with conn:
                conn.execute(
                    "UPDATE execution_plans SET status = 'FAILED' WHERE plan_id = ?",
                    (plan_id,)
                )
            log_event(
                action="RUN_EXECUTION_PLAN_FAILED",
                username=executed_by,
                input_summary=f"Plan {plan_id} (ACTUAL)",
                decision="REJECTED",
                result=msg
            )
            raise NotImplementedError(msg)

        with conn:
            conn.execute("UPDATE execution_plans SET status = 'RUNNING' WHERE plan_id = ?", (plan_id,))
            for d in decisions:
                test_id = d["test_id"]
                is_selected = (d["decision"] == "RUN")

                if is_selected:
                    is_affected = ground_truth.get(test_id, False)
                    exec_outcome = adapter.execute_test(test_id, d, is_affected)
                    test_status = exec_outcome["execution_status"]
                    res_val = exec_outcome["result"]
                    fail_reason = exec_outcome["failure_reason"]
                    duration = exec_outcome["duration"]
                    total_duration += duration
                    if test_status == "FAILED":
                        failed += 1
                    else:
                        passed += 1
                else:
                    test_status = "SKIPPED"
                    res_val = "SKIP"
                    fail_reason = None
                    duration = 0.0
                    skipped += 1

                conn.execute("""
                    INSERT INTO execution_results 
                    (plan_id, test_id, selected, execution_type, execution_status, duration, result, failure_reason, executed_at, change_id, experiment_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    plan_id, test_id, 1 if is_selected else 0, execution_type,
                    test_status, duration, res_val, fail_reason, now, change_id, experiment_id
                ))

                results.append({
                    "test_id": test_id,
                    "test_name": d.get("test_name", ""),
                    "selected": is_selected,
                    "execution_type": execution_type,
                    "execution_status": test_status,
                    "duration": duration,
                    "result": res_val,
                    "failure_reason": fail_reason,
                    "expected_affected": ground_truth.get(test_id, False),
                })

            conn.execute("UPDATE execution_plans SET status = 'COMPLETED' WHERE plan_id = ?", (plan_id,))

        log_event(
            action="EXECUTION_PLAN_RUN",
            username=executed_by,
            input_summary=f"Executed plan {plan_id} ({execution_type})",
            system_mode=plan["strategy"],
            decision="COMPLETED",
            result=f"Passed={passed}, Failed={failed}, Skipped={skipped}, Duration={round(total_duration, 2)}s"
        )

        return {
            "plan_id": plan_id,
            "change_id": change_id,
            "execution_type": execution_type,
            "status": "COMPLETED",
            "executed_by": executed_by,
            "executed_at": now,
            "summary": {
                "total_tests": len(decisions),
                "executed_tests": passed + failed,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "total_duration_seconds": round(total_duration, 2),
                "total_duration_minutes": round(total_duration / 60.0, 2),
            },
            "results": results[:50],  # preview of first 50 results
            "total_results_count": len(results),
        }
    finally:
        conn.close()


def get_execution_plan(plan_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves plan details and recorded test execution results."""
    conn = get_db_connection()
    try:
        plan_row = conn.execute("SELECT * FROM execution_plans WHERE plan_id = ?", (plan_id,)).fetchone()
        if not plan_row:
            return None
        plan = dict(plan_row)

        results = conn.execute(
            "SELECT * FROM execution_results WHERE plan_id = ? ORDER BY id ASC LIMIT 200",
            (plan_id,)
        ).fetchall()
        plan["results"] = [dict(r) for r in results]
        return plan
    finally:
        conn.close()


def list_execution_plans(limit: int = 50) -> List[Dict[str, Any]]:
    """Lists recent execution plans."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM execution_plans ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
