"""
TestSphere AI — Database Initialization
Creates and manages the SQLite schema for all application data.
"""
import sqlite3
import os
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Resolve config
_BASE = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _BASE / "config.json"
with open(_CONFIG_PATH) as _f:
    _CONFIG = json.load(_f)

DB_PATH = _BASE / _CONFIG["data"]["db_path"]


IN_MEMORY_MOCK_ACTIVE = False
_MOCK_CONN = None


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory set."""
    global _MOCK_CONN
    if IN_MEMORY_MOCK_ACTIVE:
        if _MOCK_CONN is None:
            # Create in-memory database using shared cache
            _MOCK_CONN = sqlite3.connect("file:mock_db?mode=memory&cache=shared", uri=True)
            _MOCK_CONN.row_factory = sqlite3.Row
            _create_data_tables(_MOCK_CONN)
            _create_meta_tables(_MOCK_CONN)
            _seed_default_users(_MOCK_CONN)
            
            # Generate and load mock datasets in memory
            from Data_Generation.generate_dataset import generate_tests, generate_dependencies, generate_failure_history, generate_code_changes, generate_ground_truth, DEVICES
            tests = generate_tests(1000)
            deps = generate_dependencies()
            failures = generate_failure_history(tests)
            changes = generate_code_changes()
            ground_truth = generate_ground_truth(tests, changes, deps)
            
            def _bulk_insert_direct(db_conn, table: str, rows: list[dict]) -> None:
                if not rows:
                    return
                keys = list(rows[0].keys())
                placeholders = ", ".join("?" for _ in keys)
                cols = ", ".join(keys)
                sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
                db_conn.executemany(sql, [tuple(r[k] for k in keys) for r in rows])
                
            _bulk_insert_direct(_MOCK_CONN, "test_coverage", tests)
            _bulk_insert_direct(_MOCK_CONN, "dependency_map", deps)
            
            device_rows = []
            for d in DEVICES:
                device_rows.append({
                    "device_id": d[0], "device_name": d[1], "os_type": d[2],
                    "os_version": d[3], "risk_level": d[4], "failure_rate": d[5],
                    "last_failure_date": "2025-08-01", "test_count": 0,
                })
            from collections import Counter
            tc = Counter(t["device"] for t in tests)
            for dr in device_rows:
                dr["test_count"] = tc.get(dr["device_name"], 0)
            _bulk_insert_direct(_MOCK_CONN, "device_matrix", device_rows)
            _bulk_insert_direct(_MOCK_CONN, "failure_history", failures)
            _bulk_insert_direct(_MOCK_CONN, "code_changes", changes)
            _bulk_insert_direct(_MOCK_CONN, "experiment_ground_truth", ground_truth)
            _MOCK_CONN.commit()
            
        conn = sqlite3.connect("file:mock_db?mode=memory&cache=shared", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn



def initialize_database() -> None:
    """Create all tables if they do not already exist."""
    conn = get_connection()
    try:
        _create_data_tables(conn)
        _create_meta_tables(conn)
        _seed_default_users(conn)
        conn.commit()
        logger.info("Database initialized at %s", DB_PATH)
    finally:
        conn.close()


def _create_data_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS test_coverage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id TEXT NOT NULL,
            test_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            module TEXT NOT NULL,
            device TEXT NOT NULL,
            os_version TEXT NOT NULL,
            execution_time REAL NOT NULL DEFAULT 0.5,
            is_security_critical INTEGER NOT NULL DEFAULT 0,
            tags TEXT
        );

        CREATE TABLE IF NOT EXISTS dependency_map (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL,
            depends_on TEXT NOT NULL,
            module TEXT NOT NULL,
            depth INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS failure_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id TEXT NOT NULL,
            failure_date TEXT NOT NULL,
            module TEXT NOT NULL,
            device TEXT NOT NULL,
            os_version TEXT,
            severity TEXT NOT NULL DEFAULT 'MEDIUM',
            error_type TEXT,
            resolved INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS device_matrix (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            device_name TEXT NOT NULL,
            os_type TEXT NOT NULL,
            os_version TEXT NOT NULL,
            risk_level TEXT NOT NULL DEFAULT 'LOW',
            failure_rate REAL DEFAULT 0.0,
            last_failure_date TEXT,
            test_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS code_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            change_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            module TEXT NOT NULL,
            change_type TEXT NOT NULL DEFAULT 'MODIFIED',
            is_security_sensitive INTEGER NOT NULL DEFAULT 0,
            risk_level TEXT NOT NULL DEFAULT 'LOW',
            changed_at TEXT NOT NULL,
            changed_by TEXT DEFAULT 'system',
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS experiment_ground_truth (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id TEXT NOT NULL,
            change_id TEXT NOT NULL,
            actually_affected INTEGER NOT NULL DEFAULT 0,
            reason TEXT
        );

        CREATE TABLE IF NOT EXISTS selection_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            change_id TEXT NOT NULL,
            test_id TEXT NOT NULL,
            decision TEXT NOT NULL,
            risk_score REAL NOT NULL DEFAULT 0,
            confidence TEXT NOT NULL DEFAULT 'LOW',
            rationale TEXT,
            evidence TEXT,
            strategy TEXT NOT NULL DEFAULT 'SMART_SELECTOR',
            created_at TEXT NOT NULL
        );
    """)


def _create_meta_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
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
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            username TEXT NOT NULL DEFAULT 'system',
            action TEXT NOT NULL,
            input_summary TEXT,
            decision TEXT,
            system_mode TEXT,
            result TEXT,
            ip_address TEXT
        );

        CREATE TABLE IF NOT EXISTS rollback_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_strategy TEXT NOT NULL,
            to_strategy TEXT NOT NULL,
            version TEXT,
            changed_at TEXT NOT NULL,
            reason TEXT,
            changed_by TEXT DEFAULT 'system'
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q1_understandable INTEGER,
            q2_skip_reasons_clear INTEGER,
            q3_trust_low_risk INTEGER,
            q4_rollback_useful INTEGER,
            q5_dashboard_easy INTEGER,
            overall_comment TEXT,
            submitted_at TEXT NOT NULL,
            submitted_by TEXT DEFAULT 'anonymous',
            is_demo INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL DEFAULT 'VIEWER',
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_login TEXT
        );

        CREATE TABLE IF NOT EXISTS strategy_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            updated_by TEXT DEFAULT 'system'
        );
    """)


def _seed_default_users(conn: sqlite3.Connection) -> None:
    """Seed default users if not already present."""
    try:
        import bcrypt
    except ImportError:
        logger.warning("bcrypt not available — skipping user seeding")
        return

    with open(_CONFIG_PATH) as f:
        cfg = json.load(f)

    existing = {row[0] for row in conn.execute("SELECT username FROM users").fetchall()}
    now = datetime.utcnow().isoformat()

    for u in cfg["auth"]["default_users"]:
        if u["username"] not in existing:
            hashed = bcrypt.hashpw(u["password"].encode(), bcrypt.gensalt(rounds=12))
            conn.execute(
                "INSERT INTO users (username, role, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (u["username"], u["role"], hashed.decode(), now)
            )

    # Seed initial strategy
    conn.execute(
        "INSERT OR IGNORE INTO strategy_config (key, value, updated_at) VALUES (?, ?, ?)",
        ("current_strategy", "SMART_SELECTOR", now)
    )
    conn.execute(
        "INSERT OR IGNORE INTO strategy_config (key, value, updated_at) VALUES (?, ?, ?)",
        ("strategy_version", "SMART_SELECTOR_V1", now)
    )


def get_dataset_status() -> dict:
    """Return metadata for all 5 core datasets."""
    datasets = ["test_coverage", "dependency_map", "failure_history", "device_matrix", "code_changes"]
    conn = get_connection()
    result = {}
    try:
        for ds in datasets:
            row = conn.execute(
                "SELECT * FROM dataset_metadata WHERE dataset_type=? ORDER BY id DESC LIMIT 1",
                (ds,)
            ).fetchone()
            if row:
                result[ds] = dict(row)
            else:
                result[ds] = {
                    "dataset_type": ds, "version": 0, "record_count": 0,
                    "source": "None", "status": "MISSING", "uploaded_at": None
                }
    finally:
        conn.close()
    return result


def upsert_dataset_metadata(
    dataset_type: str, record_count: int, source: str,
    file_name: str = None, uploaded_by: str = "system"
) -> None:
    """Insert a new metadata row for the given dataset (versioned)."""
    conn = get_connection()
    try:
        last = conn.execute(
            "SELECT version FROM dataset_metadata WHERE dataset_type=? ORDER BY id DESC LIMIT 1",
            (dataset_type,)
        ).fetchone()
        version = (last["version"] + 1) if last else 1
        now = datetime.utcnow().isoformat()
        conn.execute(
            """INSERT INTO dataset_metadata
               (dataset_type, version, file_name, record_count, source, uploaded_by, uploaded_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (dataset_type, version, file_name, record_count, source, uploaded_by, now, "READY")
        )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    initialize_database()
    print("Database initialized successfully.")
