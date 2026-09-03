"""
TestSphere AI — System Audit & Feedback Routes
Provides endpoints for monitoring logs and recording feedback.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from backend.schemas import FeedbackRequest
from backend.engine.audit_logger import get_audit_log, log_event
from backend.database import get_db_connection
from backend.api.auth_routes import get_user_from_token

router = APIRouter(prefix="/audit", tags=["Compliance Audit"])


@router.get("/logs")
def get_logs(limit: int = 100):
    """Retrieve system audit logs."""
    return {"logs": get_audit_log(limit)}


@router.post("/feedback")
def submit_feedback(payload: FeedbackRequest, token: Optional[str] = None):
    """Saves user survey responses into SQLite."""
    user = get_user_from_token(token)
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO feedback (username, understandable, clear_reasons, trust_system, rollback_useful, dashboard_clear, additional_comments, rating)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user["username"],
            payload.understandable,
            payload.clear_reasons,
            payload.trust_system,
            payload.rollback_useful,
            payload.dashboard_clear,
            payload.additional_comments or "",
            payload.rating
        ))
        conn.commit()

        # Log event
        log_event(
            action="SUBMIT_FEEDBACK",
            username=user["username"],
            input_summary=f"Submitted stakeholder feedback rating: {payload.rating}",
            result="SUCCESS"
        )
        return {"success": True, "message": "Feedback submitted successfully."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to record feedback response: {str(exc)}")
    finally:
        conn.close()


@router.get("/feedback/stats")
def get_feedback_stats():
    """Calculates aggregates for ratings and responses."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT COUNT(*), AVG(rating) FROM feedback").fetchone()
        count = row[0] if row else 0
        avg_rating = round(row[1], 1) if row and row[1] is not None else 0.0

        # Calculate positive ratio (ratings >= 4)
        pos_row = conn.execute("SELECT COUNT(*) FROM feedback WHERE rating >= 4").fetchone()
        pos_count = pos_row[0] if pos_row else 0
        pos_pct = round((pos_count / max(count, 1)) * 100, 1)

        # Get feedback lists
        rows = conn.execute("SELECT username, additional_comments, rating, created_at FROM feedback ORDER BY created_at DESC").fetchall()
        comments = [dict(r) for r in rows if r["additional_comments"]]

        return {
            "response_count": count,
            "average_rating": avg_rating,
            "positive_pct": pos_pct,
            "feedbacks": comments
        }
    except Exception:
        return {"response_count": 0, "average_rating": 0.0, "positive_pct": 0.0, "feedbacks": []}
    finally:
        conn.close()
