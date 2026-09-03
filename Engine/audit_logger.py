"""
TestSphere AI — Audit Logger
Append-only audit trail for all significant system events.
"""
import sqlite3
import logging
from datetime import datetime
from Engine.database import get_connection

logger = logging.getLogger(__name__)


def log_event(
    action: str,
    username: str = "system",
    input_summary: str = "",
    decision: str = "",
    system_mode: str = "",
    result: str = "",
    ip_address: str = "",
) -> None:
    """Append a new audit log entry to the database."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO audit_log
               (timestamp, username, action, input_summary, decision, system_mode, result, ip_address)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.utcnow().isoformat(),
                username,
                action,
                input_summary[:500] if input_summary else "",
                decision[:200] if decision else "",
                system_mode,
                result[:500] if result else "",
                ip_address,
            )
        )
        conn.commit()
    except Exception as exc:
        logger.error("Failed to write audit log: %s", exc)
    finally:
        conn.close()


def get_audit_log(
    action_filter: str = "",
    username_filter: str = "",
    limit: int = 200,
) -> list[dict]:
    """Retrieve audit log entries with optional filters."""
    conn = get_connection()
    try:
        query = "SELECT * FROM audit_log WHERE 1=1"
        params: list = []
        if action_filter:
            query += " AND action LIKE ?"
            params.append(f"%{action_filter}%")
        if username_filter:
            query += " AND username = ?"
            params.append(username_filter)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# Convenience wrappers for common actions
def log_change_analysis(changed_files: list[str], username: str = "system",
                         result: str = "") -> None:
    log_event("CHANGE_ANALYSIS", username,
              input_summary=f"Files: {', '.join(changed_files)}",
              system_mode="SMART_SELECTOR", result=result)


def log_test_selection(selected: int, skipped: int, username: str = "system") -> None:
    log_event("TEST_SELECTION", username,
              decision=f"RUN={selected}, SKIP={skipped}",
              system_mode="SMART_SELECTOR",
              result=f"Selected {selected} tests, skipped {skipped}")


def log_rollback(from_strategy: str, to_strategy: str, username: str = "system",
                  reason: str = "") -> None:
    log_event("ROLLBACK", username,
              input_summary=f"From={from_strategy} To={to_strategy}",
              decision=f"Strategy changed to {to_strategy}",
              system_mode=to_strategy, result=reason)


def log_security_rejection(reason: str, username: str = "system") -> None:
    log_event("SECURITY_REJECTION", username,
              result=f"REJECTED: {reason}", system_mode="SECURITY_GUARD")


def log_data_upload(dataset_type: str, record_count: int,
                     username: str = "system", source: str = "upload") -> None:
    log_event("DATA_UPLOAD", username,
              input_summary=f"Dataset={dataset_type}, records={record_count}, source={source}",
              result="SUCCESS")
