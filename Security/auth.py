"""
TestSphere AI — Authentication Module
Simple local authentication with bcrypt password hashing.
Roles: ADMIN, QA_ENGINEER, VIEWER
No JWT — session token managed by the FastAPI/JS frontend.
"""
import logging
from datetime import datetime
from Engine.database import get_connection

logger = logging.getLogger(__name__)


def _get_bcrypt():
    try:
        import bcrypt
        return bcrypt
    except ImportError:
        raise RuntimeError("bcrypt is required. Run: pip install bcrypt")


def verify_password(username: str, password: str) -> dict | None:
    """
    Verify credentials against the database.

    Returns user dict on success, None on failure.
    """
    if not username or not password:
        return None

    bcrypt = _get_bcrypt()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username.strip().lower(),)
        ).fetchone()
        if not row:
            return None

        stored_hash = row["password_hash"].encode()
        if not bcrypt.checkpw(password.encode(), stored_hash):
            return None

        # Update last_login
        conn.execute(
            "UPDATE users SET last_login = ? WHERE username = ?",
            (datetime.utcnow().isoformat(), username)
        )
        conn.commit()
        return dict(row)
    finally:
        conn.close()


def get_user(username: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def is_authorized(role: str, required_role: str) -> bool:
    """Role hierarchy: ADMIN > QA_ENGINEER > VIEWER."""
    hierarchy = {"ADMIN": 3, "QA_ENGINEER": 2, "VIEWER": 1}
    return hierarchy.get(role, 0) >= hierarchy.get(required_role, 999)


def get_demo_user() -> dict:
    """Return a demo QA_ENGINEER user for unauthenticated sessions."""
    return {
        "username": "demo_user",
        "role": "QA_ENGINEER",
        "id": 0,
    }
