"""
TestSphere AI — Data Access Layer (DAL)
Mediator for all database interactions. Preserves SQLite as the single source of truth.
"""
import sqlite3
import pandas as pd
from typing import List, Dict, Any, Optional
from backend.database import get_db_connection

IN_MEMORY_MOCK_ACTIVE = False
_mock_data = {}

def set_in_memory_mock(active: bool):
    global IN_MEMORY_MOCK_ACTIVE
    IN_MEMORY_MOCK_ACTIVE = active

def _ensure_mock_data():
    global _mock_data
    if _mock_data:
        return
    from Data_Generation.generate_dataset import (
        generate_tests,
        generate_dependencies,
        generate_failure_history,
        generate_code_changes,
        DEVICES
    )
    tests = generate_tests(1000)
    deps = generate_dependencies()
    failures = generate_failure_history(tests)
    changes = generate_code_changes()
    
    device_rows = []
    from collections import Counter
    tc = Counter(t["device"] for t in tests)
    for d in DEVICES:
        device_rows.append({
            "device_id": d[0],
            "device_name": d[1],
            "os_type": d[2],
            "os_version": d[3],
            "risk_level": d[4],
            "failure_rate": d[5],
            "last_failure_date": "2025-08-01",
            "test_count": tc.get(d[1], 0)
        })
        
    _mock_data = {
        "tests": tests,
        "deps": deps,
        "failures": failures,
        "changes": changes,
        "devices": device_rows
    }


def get_data_health() -> Dict[str, Any]:
    """
    Scans tables and returns counts and overall readiness score.
    Returns:
        Dict detailing health, missing lists, warnings.
    """
    if IN_MEMORY_MOCK_ACTIVE:
        _ensure_mock_data()
        counts = {
            "test_coverage": len(_mock_data["tests"]),
            "dependency_map": len(_mock_data["deps"]),
            "failure_history": len(_mock_data["failures"]),
            "device_matrix": len(_mock_data["devices"]),
            "code_changes": len(_mock_data["changes"])
        }
        return {
            "ready": 5,
            "counts": counts,
            "missing": [],
            "warnings": [],
            "status": "READY"
        }

    tables = ["test_coverage", "dependency_map", "failure_history", "device_matrix", "code_changes"]
    counts = {}
    conn = get_db_connection()
    try:
        for t in tables:
            try:
                row = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()
                counts[t] = row[0] if row else 0
            except sqlite3.OperationalError:
                counts[t] = 0

        # Ready score counts number of populated datasets (0 to 5)
        ready_score = sum(1 for t in tables if counts[t] > 0)
        missing = [t for t in tables if counts[t] == 0]

        warnings = []
        if counts["test_coverage"] > 0 and counts["dependency_map"] == 0:
            warnings.append("Test coverage is present but dependency map is missing. Impact paths cannot be fully mapped.")
        if counts["failure_history"] == 0:
            warnings.append("Failure history database is empty. Risk scoring defaults to safe levels.")

        return {
            "ready": ready_score,
            "counts": counts,
            "missing": missing,
            "warnings": warnings,
            "status": "READY" if ready_score >= 4 else "SAFE_DEFAULT"
        }
    finally:
        conn.close()


def get_all_tests() -> List[Dict[str, Any]]:
    """Fetch all test specifications from SQLite."""
    if IN_MEMORY_MOCK_ACTIVE:
        _ensure_mock_data()
        return _mock_data["tests"]

    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT test_id, test_name, file_path, module, device, os_version, execution_time, is_security_critical, tags 
            FROM test_coverage
        """).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def get_all_dependencies() -> List[Dict[str, Any]]:
    """Fetch all edges from dependency map."""
    if IN_MEMORY_MOCK_ACTIVE:
        _ensure_mock_data()
        return _mock_data["deps"]

    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT source_file, depends_on, module, depth FROM dependency_map").fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def get_tests_covering_file(file_path: str) -> List[Dict[str, Any]]:
    """Find tests directly covering a source file."""
    if IN_MEMORY_MOCK_ACTIVE:
        _ensure_mock_data()
        return [t for t in _mock_data["tests"] if t["file_path"] == file_path]

    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT test_id, test_name, file_path, module, device, os_version FROM test_coverage WHERE file_path = ?",
            (file_path,)
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def get_device_matrix() -> List[Dict[str, Any]]:
    """Fetch the device inventory profiles."""
    if IN_MEMORY_MOCK_ACTIVE:
        _ensure_mock_data()
        return _mock_data["devices"]

    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT device_id, device_name, os_type, os_version, risk_level, failure_rate, last_failure_date, test_count 
            FROM device_matrix
        """).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def get_code_changes() -> List[Dict[str, Any]]:
    """Fetch recent recorded code changes."""
    if IN_MEMORY_MOCK_ACTIVE:
        _ensure_mock_data()
        return _mock_data["changes"]

    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT change_id, file_path, module, change_type, is_security_sensitive, risk_level, changed_at, changed_by, description 
            FROM code_changes
            ORDER BY changed_at DESC
        """).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def get_all_failures() -> List[Dict[str, Any]]:
    """Fetch historical failure logs."""
    if IN_MEMORY_MOCK_ACTIVE:
        _ensure_mock_data()
        return _mock_data["failures"]

    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT test_id, failure_date, module, device, os_version, severity, error_type, resolved 
            FROM failure_history
        """).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def get_current_strategy() -> str:
    """Read the active selection strategy configuration."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT value FROM strategy_config WHERE key = 'active_strategy'").fetchone()
        if row:
            return row[0]
        # Return default if config doesn't exist
        return "SMART_SELECTOR"
    except sqlite3.OperationalError:
        return "SMART_SELECTOR"
    finally:
        conn.close()


def set_current_strategy(strategy: str, user: str) -> bool:
    """Update active strategy."""
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO strategy_config (key, value, updated_at, updated_by)
            VALUES ('active_strategy', ?, CURRENT_TIMESTAMP, ?)
        """, (strategy, user))
        conn.commit()
        return True
    except sqlite3.OperationalError:
        # Create table if missing during migration
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategy_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_by TEXT
                )
            """)
            conn.execute("""
                INSERT OR REPLACE INTO strategy_config (key, value, updated_at, updated_by)
                VALUES ('active_strategy', ?, CURRENT_TIMESTAMP, ?)
            """, (strategy, user))
            conn.commit()
            return True
        except Exception:
            return False
    finally:
        conn.close()


def get_dataset_metadata() -> List[Dict[str, Any]]:
    """Fetch upload versions and metadata."""
    conn = get_db_connection()
    try:
        try:
            rows = conn.execute("SELECT dataset_type, version, record_count, source, last_updated FROM dataset_metadata").fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError as e:
            if "no such column: last_updated" in str(e) or "no column named last_updated" in str(e):
                # Fallback to Engine/database.py schema where it is uploaded_at and multiple records might exist.
                # We get the latest record for each dataset_type.
                rows = conn.execute("""
                    SELECT m.dataset_type, m.version, m.record_count, m.source, m.uploaded_at AS last_updated 
                    FROM dataset_metadata m
                    INNER JOIN (
                        SELECT dataset_type, MAX(id) as max_id 
                        FROM dataset_metadata 
                        GROUP BY dataset_type
                    ) latest ON m.id = latest.max_id
                """).fetchall()
                return [dict(r) for r in rows]
            else:
                raise e
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def upsert_dataset_metadata(dataset_type: str, record_count: int, source: str):
    """Increment version and update record count for a dataset type."""
    conn = get_db_connection()
    try:
        # Check current version
        try:
            row = conn.execute("SELECT version FROM dataset_metadata WHERE dataset_type = ? ORDER BY id DESC LIMIT 1", (dataset_type,)).fetchone()
        except sqlite3.OperationalError:
            row = conn.execute("SELECT version FROM dataset_metadata WHERE dataset_type = ?", (dataset_type,)).fetchone()
            
        current_ver = row[0] if row else 0
        new_ver = current_ver + 1

        try:
            conn.execute("""
                INSERT OR REPLACE INTO dataset_metadata (dataset_type, version, record_count, source, last_updated)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (dataset_type, new_ver, record_count, source))
        except sqlite3.OperationalError as e:
            if "no column named last_updated" in str(e) or "no such column: last_updated" in str(e):
                # Fallback to inserting with uploaded_at
                conn.execute("""
                    INSERT INTO dataset_metadata (dataset_type, version, record_count, source, uploaded_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (dataset_type, new_ver, record_count, source))
            else:
                raise e
        conn.commit()
    except sqlite3.OperationalError:
        # Create metadata table if missing
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dataset_metadata (
                    dataset_type TEXT PRIMARY KEY,
                    version INTEGER NOT NULL DEFAULT 1,
                    record_count INTEGER NOT NULL DEFAULT 0,
                    source TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                INSERT OR REPLACE INTO dataset_metadata (dataset_type, version, record_count, source, last_updated)
                VALUES (?, 1, ?, ?, CURRENT_TIMESTAMP)
            """, (dataset_type, record_count, source))
            conn.commit()
        except sqlite3.OperationalError:
            # Fallback table creation (Engine schema)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dataset_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset_type TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    file_name TEXT,
                    record_count INTEGER NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT 'unknown',
                    uploaded_by TEXT DEFAULT 'system',
                    uploaded_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'READY'
                )
            """)
            conn.execute("""
                INSERT INTO dataset_metadata (dataset_type, version, record_count, source, uploaded_at)
                VALUES (?, 1, ?, ?, CURRENT_TIMESTAMP)
            """, (dataset_type, record_count, source))
            conn.commit()
    finally:
        conn.close()


def clear_table(table_name: str) -> int:
    """Clear all records in a table. Returns count of rows deleted."""
    conn = get_db_connection()
    try:
        # Fetch count before delete
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        cursor.execute(f"DELETE FROM {table_name}")
        
        # Reset metadata (try both schemas)
        try:
            conn.execute("INSERT OR REPLACE INTO dataset_metadata (dataset_type, version, record_count, source, last_updated) VALUES (?, 0, 0, 'Cleared', CURRENT_TIMESTAMP)", (table_name,))
        except sqlite3.OperationalError as e:
            if "no column named last_updated" in str(e) or "no such column: last_updated" in str(e):
                conn.execute("INSERT INTO dataset_metadata (dataset_type, version, record_count, source, uploaded_at) VALUES (?, 0, 0, 'Cleared', CURRENT_TIMESTAMP)", (table_name,))
            else:
                raise e
                
        conn.commit()
        return count
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()
