"""
TestSphere AI — Rollback & Strategy Manager
Handles toggling the active test selection strategy.
"""
import logging
from typing import Dict, Any, List
from backend.database import get_db_connection
from backend.engine.data_access import get_current_strategy, set_current_strategy
from backend.engine.audit_logger import log_event

from datetime import datetime

logger = logging.getLogger(__name__)


def change_system_strategy(to_strategy: str, reason: str, changed_by: str) -> Dict[str, Any]:
    """
    Saves a rollback event, updates SQLite strategy_config and logs action.
    """
    if to_strategy not in ["SMART_SELECTOR", "LEGACY_FULL_SUITE"]:
        return {"success": False, "error": f"Invalid strategy: {to_strategy}"}

    current = get_current_strategy()
    if current == to_strategy:
        return {
            "success": True,
            "message": f"Strategy is already set to {to_strategy}.",
            "current_strategy": current
        }

    # Save to rollback_history
    now = datetime.utcnow().isoformat()
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO rollback_history (from_strategy, to_strategy, version, changed_at, reason, changed_by)
            VALUES (?, ?, 'v1.0.0', ?, ?, ?)
        """, (current, to_strategy, now, reason, changed_by))
        conn.commit()
    except Exception as exc:
        logger.error("Failed to insert rollback history record: %s", exc)
        return {"success": False, "error": f"Failed to persist rollback history: {str(exc)}"}
    finally:
        conn.close()

    # Update active config
    success = set_current_strategy(to_strategy, changed_by)
    if success:
        log_event(
            action="ROLLBACK" if to_strategy == "LEGACY_FULL_SUITE" else "RESTORE",
            username=changed_by,
            input_summary=f"Changed strategy from {current} to {to_strategy}. Reason: {reason}",
            system_mode=to_strategy,
            decision="SUCCESS",
            result=f"Active strategy updated to {to_strategy}"
        )
        return {
            "success": True,
            "from_strategy": current,
            "to_strategy": to_strategy,
            "message": f"Successfully switched to {to_strategy} strategy."
        }
    else:
        return {"success": False, "error": "Failed to update strategy configuration table."}


def get_rollback_logs() -> List[Dict[str, Any]]:
    """Retrieves list of rollback audit records."""
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT id, from_strategy, to_strategy, version, changed_at, reason, changed_by 
            FROM rollback_history 
            ORDER BY changed_at DESC
        """).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()
