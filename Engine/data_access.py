"""
TestSphere AI — Common Data Access Layer
All engine components read from SQLite exclusively through this module.
The engine never knows whether data originated from the demo generator or user upload.
"""
import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_BASE = Path(__file__).resolve().parent.parent
with open(_BASE / "config.json") as _f:
    _CONFIG = json.load(_f)


def _conn():
    """Internal: get a live connection."""
    from Engine.database import get_connection
    return get_connection()


# ─── Test Coverage ───────────────────────────────────────────────────────────

def get_all_tests() -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM test_coverage").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_tests_covering_file(file_path: str) -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM test_coverage WHERE file_path = ?", (file_path,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_tests_by_module(module: str) -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM test_coverage WHERE module = ?", (module,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_test_by_id(test_id: str) -> Optional[dict]:
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT * FROM test_coverage WHERE test_id = ?", (test_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ─── Dependency Map ───────────────────────────────────────────────────────────

def get_all_dependencies() -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM dependency_map").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_dependencies_for_file(file_path: str) -> list[dict]:
    """Files that `file_path` depends on, or that depend on `file_path`."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM dependency_map WHERE source_file = ? OR depends_on = ?",
            (file_path, file_path)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── Failure History ─────────────────────────────────────────────────────────

def get_failure_history() -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM failure_history").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_failures_for_test(test_id: str) -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM failure_history WHERE test_id = ?", (test_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_failures_by_module(module: str) -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM failure_history WHERE module = ?", (module,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── Device Matrix ────────────────────────────────────────────────────────────

def get_device_matrix() -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM device_matrix").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_device_risk(device_name: str) -> str:
    """Return risk level for a device or 'UNKNOWN'."""
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT risk_level FROM device_matrix WHERE device_name = ?", (device_name,)
        ).fetchone()
        return row["risk_level"] if row else "UNKNOWN"
    finally:
        conn.close()


# ─── Code Changes ─────────────────────────────────────────────────────────────

def get_all_changes() -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM code_changes ORDER BY changed_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_change_by_id(change_id: str) -> Optional[dict]:
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT * FROM code_changes WHERE change_id = ?", (change_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_changes_by_file(file_path: str) -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM code_changes WHERE file_path = ?", (file_path,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── Ground Truth ──────────────────────────────────────────────────────────────

def get_ground_truth(change_id: str = "CHG001") -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM experiment_ground_truth WHERE change_id = ?", (change_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── Strategy ─────────────────────────────────────────────────────────────────

def get_current_strategy() -> str:
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT value FROM strategy_config WHERE key = 'current_strategy'"
        ).fetchone()
        return row["value"] if row else "SMART_SELECTOR"
    finally:
        conn.close()


def set_current_strategy(strategy: str, updated_by: str = "system") -> None:
    from datetime import datetime
    conn = _conn()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO strategy_config (key, value, updated_at, updated_by) VALUES (?, ?, ?, ?)",
            ("current_strategy", strategy, now, updated_by)
        )
        conn.commit()
    finally:
        conn.close()


# ─── Data Health ──────────────────────────────────────────────────────────────

def get_data_health() -> dict:
    """Return health summary for all 5 core datasets."""
    from Engine.database import get_dataset_status
    status = get_dataset_status()
    total = len(status)
    ready = sum(1 for v in status.values() if v.get("status") == "READY")
    missing = sum(1 for v in status.values() if v.get("status") == "MISSING")
    invalid = total - ready - missing
    warnings = []
    for ds, info in status.items():
        if info.get("status") != "READY":
            warnings.append(f"{ds} is {info.get('status', 'UNKNOWN')}")
        elif info.get("record_count", 0) == 0:
            warnings.append(f"{ds} has 0 records")
    return {
        "total": total,
        "ready": ready,
        "missing": missing,
        "invalid": invalid,
        "warnings": warnings,
        "datasets": status,
    }


def is_data_available() -> bool:
    """True only if all 5 core datasets have records."""
    health = get_data_health()
    return health["ready"] == health["total"] and health["missing"] == 0
