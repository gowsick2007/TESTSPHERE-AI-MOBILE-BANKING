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
        username TEXT NOT NULL,
        understandable TEXT NOT NULL,
        clear_reasons TEXT NOT NULL,
        trust_system TEXT NOT NULL,
        rollback_useful TEXT NOT NULL,
        dashboard_clear TEXT NOT NULL,
        additional_comments TEXT,
        rating INTEGER NOT NULL DEFAULT 5,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Create indexes for search optimization
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_coverage_test_id ON test_coverage(test_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_coverage_file_path ON test_coverage(file_path);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dep_source_file ON dependency_map(source_file);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_failure_test_id ON failure_history(test_id);")

    # Create default users if empty (using hashed passwords)
    # Admin@123 -> $2b$12$KkQ/v1u/s7P.k5.P1YtM4u86PjHjGzC4w5YtqS7rN.Z.W5/v1u/s7
    # (We will use bcrypt in security, but let's pre-populate with known hashed values)
    # Actually, we can import bcrypt and hash them dynamically on startup!
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        import bcrypt
        default_users = [
            ("admin", "admin123", "ADMIN"),
            ("qa_eng", "qa123", "QA_ENGINEER"),
            ("viewer", "view123", "VIEWER")
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
