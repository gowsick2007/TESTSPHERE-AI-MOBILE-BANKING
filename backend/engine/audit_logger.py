"""
TestSphere AI — System Audit Logger
Maintains transactional compliance audits.
"""
import logging
from datetime import datetime
from backend.database import get_db_connection

logger = logging.getLogger(__name__)


def log_event(
    action: str,
    username: str,
    input_summary: str | None = None,
    system_mode: str = "SMART_SELECTOR",
    decision: str | None = None,
    result: str | None = None,
):
    """Write an auditable action directly into SQLite."""
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO audit_log (timestamp, username, action, system_mode, input_summary, decision, result)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (datetime.utcnow().isoformat(), username, action, system_mode, input_summary, decision, result))
        conn.commit()
    except Exception as exc:
        logger.error("Failed to write to audit log: %s", exc)
    finally:
        conn.close()


def get_audit_log(limit: int = 100) -> list[dict]:
    """Fetch the latest audit logs from SQLite."""
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT id, timestamp, username, action, system_mode, input_summary, decision, result 
            FROM audit_log 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()
