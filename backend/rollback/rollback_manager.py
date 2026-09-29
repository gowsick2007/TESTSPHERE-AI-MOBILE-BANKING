"""
TestSphere AI — Rollback & Strategy Manager
Handles toggling the active test selection strategy.
"""
import logging
from typing import Dict, Any, List, Optional
from backend.database import get_db_connection
from backend.engine.data_access import get_current_strategy, set_current_strategy
from backend.engine.audit_logger import log_event

from datetime import datetime

logger = logging.getLogger(__name__)


def change_system_strategy(to_strategy: str, reason: str, changed_by: str) -> Dict[str, Any]:
    """
    Saves a rollback event and updates SQLite strategy_config in a single atomic transaction.
    Guarantees no partial rollback state if an error occurs.
    """
    if to_strategy not in ["SMART_SELECTOR", "LEGACY_FULL_SUITE"]:
        return {"success": False, "error": f"Invalid strategy: {to_strategy}"}

    current = get_current_strategy()
    if current == to_strategy:
        return {
            "success": True,
            "message": f"Strategy is already set to {to_strategy}.",
            "current_strategy": current,
            "from_strategy": current,
            "to_strategy": to_strategy
        }

    from datetime import timezone
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO rollback_history (from_strategy, to_strategy, version, changed_at, reason, changed_by)
                VALUES (?, ?, 'v1.0.0', ?, ?, ?)
            """, (current, to_strategy, now, reason, changed_by))
            
            conn.execute("""
                INSERT OR REPLACE INTO strategy_config (key, value, updated_at, updated_by)
                VALUES ('current_strategy', ?, ?, ?)
            """, (to_strategy, now, changed_by))
    except Exception as exc:
        logger.error("Failed to execute atomic rollback transaction: %s", exc)
        return {"success": False, "error": f"Rollback transaction aborted: {str(exc)}"}
    finally:
        conn.close()

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


def create_strategy_version(
    version_id: str,
    strategy_name: str,
    threshold: float,
    scoring_weights: Dict[str, Any],
    safety_rules: List[str],
    created_by: str = "admin",
    description: Optional[str] = None
) -> Dict[str, Any]:
    """Registers a new strategy version safely without modifying historical experiments."""
    import json
    from datetime import timezone
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO strategy_versions 
                (version_id, strategy_name, threshold, scoring_weights, safety_rules, created_by, created_at, status, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
            """, (
                version_id,
                strategy_name,
                threshold,
                json.dumps(scoring_weights),
                json.dumps(safety_rules),
                created_by,
                now,
                description or f"Strategy version {version_id}"
            ))
        
        log_event(
            action="CREATE_STRATEGY_VERSION",
            username=created_by,
            input_summary=f"Created version {version_id} (threshold={threshold})",
            decision="SUCCESS",
            result=f"Registered strategy version {version_id}"
        )
        return {
            "version_id": version_id,
            "strategy_name": strategy_name,
            "threshold": threshold,
            "scoring_weights": scoring_weights,
            "safety_rules": safety_rules,
            "created_by": created_by,
            "created_at": now,
            "status": "ACTIVE",
            "description": description
        }
    finally:
        conn.close()


def list_strategy_versions() -> List[Dict[str, Any]]:
    """Returns all recorded strategy versions."""
    import json
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT version_id, strategy_name, threshold, scoring_weights, safety_rules, created_by, created_at, status, description
            FROM strategy_versions
            ORDER BY id DESC
        """).fetchall()
        result = []
        for r in rows:
            item = dict(r)
            try:
                item["scoring_weights"] = json.loads(item["scoring_weights"])
                item["safety_rules"] = json.loads(item["safety_rules"])
            except Exception:
                pass
            result.append(item)
        return result
    finally:
        conn.close()

