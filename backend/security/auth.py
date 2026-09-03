"""
TestSphere AI — Authentication Manager
Provides user retrieval, password verification, and helper roles.
"""
import bcrypt
import logging
from backend.database import get_db_connection

logger = logging.getLogger(__name__)


def get_user(username: str) -> dict | None:
    """Retrieve user details from the database."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT username, password_hash, role FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def verify_password(username: str, password_plain: str) -> dict | None:
    """Verify password hash against stored value."""
    user = get_user(username)
    if not user:
        return None

    hashed = user["password_hash"].encode("utf-8")
    if bcrypt.checkpw(password_plain.encode("utf-8"), hashed):
        return {
            "username": user["username"],
            "role": user["role"]
        }
    return None


def get_demo_user() -> dict:
    """Fallback guest user for unauthenticated browser runs."""
    return {"username": "demo_user", "role": "QA_ENGINEER"}
