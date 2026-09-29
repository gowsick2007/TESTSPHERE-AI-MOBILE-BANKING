"""
TestSphere AI — Database Initialization & Schema Manager
Sets up SQLite tables, indexes, and default users.
"""
import sqlite3
import logging
from backend.config import DB_PATH

logger = logging.getLogger(__name__)


def get_db_connection() -> sqlite3.Connection:
    """Get a raw SQLite connection with dict-like row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    """Create all SQLite tables and index structures if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Enable WAL mode for performance
    cursor.execute("PRAGMA journal_mode=WAL;")

    # ── 1. User Authentication table ──────────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ── 2. Test Coverage table ────────────────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS test_coverage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_id TEXT NOT NULL,
        test_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        module TEXT NOT NULL,
        device TEXT NOT NULL,
        os_version TEXT NOT NULL,
        execution_time REAL NOT NULL,
        is_security_critical INTEGER NOT NULL DEFAULT 0,
        tags TEXT
    );
    """)

    # ── 3. Dependency Map table ───────────────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dependency_map (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_file TEXT NOT NULL,
        depends_on TEXT NOT NULL,
        module TEXT NOT NULL,
        depth INTEGER NOT NULL DEFAULT 1
    );
    """)

    # ── 4. Failure History table ──────────────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS failure_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_id TEXT NOT NULL,
        failure_date TEXT NOT NULL,
        module TEXT NOT NULL,
        device TEXT NOT NULL,
        os_version TEXT NOT NULL,
        severity TEXT NOT NULL,
        error_type TEXT,
        resolved INTEGER DEFAULT 0
    );
    """)

    # ── 5. Device Matrix table ────────────────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS device_matrix (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT UNIQUE NOT NULL,
        device_name TEXT NOT NULL,
        os_type TEXT NOT NULL,
        os_version TEXT NOT NULL,
        risk_level TEXT NOT NULL,
        failure_rate REAL NOT NULL,
        last_failure_date TEXT,
        test_count INTEGER NOT NULL DEFAULT 0
    );
    """)

    # ── 6. Code Changes table ─────────────────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS code_changes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        change_id TEXT UNIQUE NOT NULL,
        file_path TEXT NOT NULL,
        module TEXT NOT NULL,
        change_type TEXT NOT NULL,
        is_security_sensitive INTEGER NOT NULL DEFAULT 0,
        risk_level TEXT NOT NULL,
        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        changed_by TEXT,
        description TEXT
    );
    """)

    # ── 7. Experiment Ground Truth table ──────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS experiment_ground_truth (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        change_id TEXT NOT NULL,
        test_id TEXT NOT NULL,
        affected INTEGER NOT NULL DEFAULT 0,
        actual_failure INTEGER NOT NULL DEFAULT 0
    );
    """)

    # ── 8. Dataset Metadata table (for versioning) ────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dataset_metadata (
        dataset_type TEXT PRIMARY KEY,
        version INTEGER NOT NULL DEFAULT 1,
        record_count INTEGER NOT NULL DEFAULT 0,
        source TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # ── 9. Audit Log table ────────────────────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        username TEXT NOT NULL,
        action TEXT NOT NULL,
        system_mode TEXT NOT NULL,
        input_summary TEXT,
        decision TEXT,
        result TEXT
    );
    """)

    # ── 10. Rollback History table ────────────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rollback_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_strategy TEXT NOT NULL,
        to_strategy TEXT NOT NULL,
        version TEXT NOT NULL,
        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        reason TEXT,
        changed_by TEXT NOT NULL
    );
    """)

    # ── 11. User Feedback table ───────────────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        feedback_id TEXT UNIQUE,
        username TEXT NOT NULL,
        project_area TEXT DEFAULT 'General',
        understandable TEXT NOT NULL DEFAULT 'Yes',
        clear_reasons TEXT NOT NULL DEFAULT 'Yes',
        trust_system TEXT NOT NULL DEFAULT 'Yes',
        rollback_useful TEXT NOT NULL DEFAULT 'Yes',
        dashboard_clear TEXT NOT NULL DEFAULT 'Yes',
        additional_comments TEXT,
        rating INTEGER NOT NULL DEFAULT 5,
        linked_entity_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seamless column migration for existing feedback tables
    try:
        existing_cols = {r[1] for r in cursor.execute("PRAGMA table_info(feedback)").fetchall()}
        cols_to_add = [
            ("feedback_id", "TEXT"),
            ("username", "TEXT DEFAULT 'system'"),
            ("project_area", "TEXT DEFAULT 'General'"),
            ("understandable", "TEXT DEFAULT 'Yes'"),
            ("clear_reasons", "TEXT DEFAULT 'Yes'"),
            ("trust_system", "TEXT DEFAULT 'Yes'"),
            ("rollback_useful", "TEXT DEFAULT 'Yes'"),
            ("dashboard_clear", "TEXT DEFAULT 'Yes'"),
            ("additional_comments", "TEXT"),
            ("rating", "INTEGER DEFAULT 5"),
            ("linked_entity_id", "TEXT"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ]
        for cname, ctype in cols_to_add:
            if cname not in existing_cols:
                cursor.execute(f"ALTER TABLE feedback ADD COLUMN {cname} {ctype}")
    except Exception as exc:
        logger.warning("Feedback column migration warning: %s", exc)

    # ── 12. Strategy Configuration table ──────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS strategy_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL,
        value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_by TEXT DEFAULT 'system'
    );
    """)

    # ── 13. Strategy Versions table ───────────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS strategy_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version_id TEXT UNIQUE NOT NULL,
        strategy_name TEXT NOT NULL,
        threshold REAL NOT NULL DEFAULT 50.0,
        scoring_weights TEXT NOT NULL,
        safety_rules TEXT NOT NULL,
        created_by TEXT NOT NULL DEFAULT 'admin',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        description TEXT
    );
    """)

    # ── 14. Execution Plans table (Phase 2 Workflow) ───────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS execution_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id TEXT UNIQUE NOT NULL,
        change_id TEXT NOT NULL,
        strategy TEXT NOT NULL DEFAULT 'SMART_SELECTOR',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_by TEXT NOT NULL DEFAULT 'system',
        total_tests INTEGER NOT NULL DEFAULT 0,
        selected_tests INTEGER NOT NULL DEFAULT 0,
        skipped_tests INTEGER NOT NULL DEFAULT 0,
        estimated_duration_seconds REAL NOT NULL DEFAULT 0.0,
        status TEXT NOT NULL DEFAULT 'CREATED'
    );
    """)

    # ── 15. Execution Results table (Phase 2 Workflow) ────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS execution_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id TEXT NOT NULL,
        test_id TEXT NOT NULL,
        selected INTEGER NOT NULL DEFAULT 1,
        execution_type TEXT NOT NULL DEFAULT 'SIMULATED',
        execution_status TEXT NOT NULL DEFAULT 'PASSED',
        duration REAL NOT NULL DEFAULT 0.5,
        result TEXT NOT NULL DEFAULT 'PASS',
        failure_reason TEXT,
        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        change_id TEXT NOT NULL,
        experiment_id TEXT
    );
    """)

    # ── 16. Managed Experiments table (Phase 2 Lab) ───────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        experiment_id TEXT UNIQUE NOT NULL,
        scenario TEXT NOT NULL,
        configuration TEXT NOT NULL,
        threshold REAL NOT NULL DEFAULT 50.0,
        dataset_version INTEGER NOT NULL DEFAULT 1,
        seed INTEGER NOT NULL DEFAULT 12345,
        start_time TIMESTAMP NOT NULL,
        end_time TIMESTAMP,
        metrics TEXT,
        results TEXT,
        status TEXT NOT NULL DEFAULT 'COMPLETED',
        created_by TEXT NOT NULL DEFAULT 'system'
    );
    """)

    # Create indexes for search optimization
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_coverage_test_id ON test_coverage(test_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_coverage_file_path ON test_coverage(file_path);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dep_source_file ON dependency_map(source_file);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_failure_test_id ON failure_history(test_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_plan_id ON execution_plans(plan_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_exec_plan_id ON execution_results(plan_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_exec_test_id ON execution_results(test_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_exp_id ON experiments(experiment_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_strat_ver_id ON strategy_versions(version_id);")

    # Seed baseline strategy version if not present
    cursor.execute("SELECT COUNT(*) FROM strategy_versions")
    if cursor.fetchone()[0] == 0:
        import json
        weights = {
            "direct_coverage": 40,
            "dependency_relationship": 30,
            "security_sensitive_module": 30,
            "critical_banking_module": 25,
            "historical_failure": 20,
            "recent_failure": 15,
            "high_risk_device": 10
        }
        rules = [
            "RULE_1_UNKNOWN_DEPENDENCY",
            "RULE_2_UNKNOWN_COVERAGE",
            "RULE_3_SECURITY_CRITICAL",
            "RULE_4_CRITICAL_MODULE",
            "RULE_5_NO_FAILURE_DATA",
            "RULE_6_LOW_CONFIDENCE",
            "RULE_7_RATIONALE_MANDATED"
        ]
        cursor.execute("""
            INSERT INTO strategy_versions 
            (version_id, strategy_name, threshold, scoring_weights, safety_rules, created_by, status, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "v1.0.0-canonical",
            "SMART_SELECTOR",
            50.0,
            json.dumps(weights),
            json.dumps(rules),
            "admin",
            "ACTIVE",
            "Canonical Phase 1/2 baseline strategy with 50 threshold and safety overrides"
        ))

    # Create default users if empty (using hashed passwords)
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        import bcrypt
        default_users = [
            ("admin", "Admin@123", "ADMIN"),
            ("qa", "QA@123", "QA_ENGINEER"),
            ("viewer", "View@123", "VIEWER")
        ]
        for username, password, role in default_users:
            hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, hashed, role)
            )

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully at %s", DB_PATH)


if __name__ == "__main__":
    initialize_database()

