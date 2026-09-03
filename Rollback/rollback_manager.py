"""
TestSphere AI — Rollback Manager
Manages strategy switching between SMART_SELECTOR and LEGACY_FULL_SUITE.
All changes are persisted to the database and audit logged.
"""
import logging
from datetime import datetime
from Engine.database import get_connection
from Engine.data_access import get_current_strategy, set_current_strategy
from Engine.audit_logger import log_rollback

logger = logging.getLogger(__name__)

STRATEGIES = {
    "SMART_SELECTOR": {
        "label": "Smart Selector",
        "version": "SMART_SELECTOR_V1",
        "description": "Runs only impact-selected tests. Maximizes efficiency.",
    },
    "LEGACY_FULL_SUITE": {
        "label": "Legacy Full Suite",
        "version": "LEGACY_FULL_SUITE_V1",
        "description": "Runs all tests unconditionally. Maximum safety, no efficiency gain.",
    },
}


def get_strategy_info() -> dict:
    """Return current and previous strategy with full metadata."""
    conn = get_connection()
    try:
        current = conn.execute(
            "SELECT value FROM strategy_config WHERE key = 'current_strategy'"
        ).fetchone()
        current_strategy = current["value"] if current else "SMART_SELECTOR"

        # Last rollback event
        last_rollback = conn.execute(
            "SELECT * FROM rollback_history ORDER BY id DESC LIMIT 1"
        ).fetchone()

        return {
            "current_strategy": current_strategy,
            "current_label": STRATEGIES.get(current_strategy, {}).get("label", current_strategy),
            "current_version": STRATEGIES.get(current_strategy, {}).get("version", "V1"),
            "current_description": STRATEGIES.get(current_strategy, {}).get("description", ""),
            "last_rollback": dict(last_rollback) if last_rollback else None,
            "available_strategies": list(STRATEGIES.keys()),
        }
    finally:
        conn.close()


def switch_strategy(
    to_strategy: str,
    reason: str = "",
    changed_by: str = "system",
) -> dict:
    """
    Switch the active test execution strategy.

    Args:
        to_strategy — target strategy name
        reason      — human-readable reason for the change
        changed_by  — username making the change

    Returns:
        dict with success status and new strategy info
    """
    if to_strategy not in STRATEGIES:
        return {"success": False, "error": f"Unknown strategy: {to_strategy}"}

    current = get_current_strategy()
    if current == to_strategy:
        return {"success": True, "message": f"Strategy is already {to_strategy}"}

    now = datetime.utcnow().isoformat()
    version = STRATEGIES[to_strategy]["version"]

    conn = get_connection()
    try:
        # Persist strategy change
        conn.execute(
            "INSERT OR REPLACE INTO strategy_config (key, value, updated_at, updated_by) VALUES (?, ?, ?, ?)",
            ("current_strategy", to_strategy, now, changed_by)
        )
        conn.execute(
            "INSERT OR REPLACE INTO strategy_config (key, value, updated_at, updated_by) VALUES (?, ?, ?, ?)",
            ("strategy_version", version, now, changed_by)
        )

        # Record rollback history
        conn.execute(
            """INSERT INTO rollback_history
               (from_strategy, to_strategy, version, changed_at, reason, changed_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (current, to_strategy, version, now, reason or "User request", changed_by)
        )
        conn.commit()

        # Audit log
        log_rollback(current, to_strategy, username=changed_by, reason=reason)

        logger.info("Strategy switched: %s → %s by %s", current, to_strategy, changed_by)

        return {
            "success": True,
            "from_strategy": current,
            "to_strategy": to_strategy,
            "version": version,
            "changed_at": now,
            "message": f"Successfully switched from {current} to {to_strategy}",
        }
    finally:
        conn.close()


def rollback_to_legacy(reason: str = "User requested rollback",
                        changed_by: str = "system") -> dict:
    """Shortcut: roll back to LEGACY_FULL_SUITE."""
    return switch_strategy("LEGACY_FULL_SUITE", reason, changed_by)


def restore_smart_selector(reason: str = "User restored smart selector",
                             changed_by: str = "system") -> dict:
    """Shortcut: restore SMART_SELECTOR."""
    return switch_strategy("SMART_SELECTOR", reason, changed_by)


def get_rollback_history(limit: int = 20) -> list[dict]:
    """Return the last N strategy changes."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM rollback_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
