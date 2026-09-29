"""
TestSphere AI — System Audit Logger (Phase 2)
Maintains transactional compliance audits with automatic secret redaction
and multi-parameter filtering.
"""
import re
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from backend.database import get_db_connection

logger = logging.getLogger(__name__)

# Patterns to redact from audit logs
SECRET_PATTERNS = [
    re.compile(r'("?(?:password|token|secret|api_key|access_token|key)"?\s*[:=]\s*)"[^"]+"', re.IGNORECASE),
    re.compile(r'("?(?:password|token|secret|api_key|access_token|key)"?\s*[:=]\s*)\'[^\']+\'', re.IGNORECASE),
    re.compile(r'(Bearer\s+)[A-Za-z0-9_\-\.]+', re.IGNORECASE),
]


def _redact_secrets(text: Optional[str]) -> Optional[str]:
    """Redacts passwords, tokens, and secret keys from text."""
    if not text:
        return text
    redacted = str(text)
    for pat in SECRET_PATTERNS:
        redacted = pat.sub(r'\1"[REDACTED]"', redacted)
    return redacted


def log_event(
    action: str,
    username: str,
    input_summary: str | None = None,
    system_mode: str = "SMART_SELECTOR",
    decision: str | None = None,
    result: str | None = None,
):
    """Write an auditable action directly into SQLite with automatic secret redaction."""
    safe_summary = _redact_secrets(input_summary)
    safe_result = _redact_secrets(result)
    safe_decision = _redact_secrets(decision)

    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO audit_log (timestamp, username, action, system_mode, input_summary, decision, result)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (datetime.now(timezone.utc).isoformat(), username, action, system_mode, safe_summary, safe_decision, safe_result))
        conn.commit()
    except Exception as exc:
        logger.error("Failed to write to audit log: %s", exc)
    finally:
        conn.close()


def get_audit_log(
    limit: int = 100,
    action: Optional[str] = None,
    username: Optional[str] = None,
    system_mode: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch filtered audit logs from SQLite."""
    conn = get_db_connection()
    try:
        query = "SELECT id, timestamp, username, action, system_mode, input_summary, decision, result FROM audit_log WHERE 1=1"
        params: List[Any] = []

        if action:
            query += " AND action = ?"
            params.append(action)
        if username:
            query += " AND username = ?"
            params.append(username)
        if system_mode:
            query += " AND system_mode = ?"
            params.append(system_mode)
        if date_from:
            query += " AND timestamp >= ?"
            params.append(date_from)
        if date_to:
            query += " AND timestamp <= ?"
            params.append(date_to)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()

