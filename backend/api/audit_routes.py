"""
TestSphere AI — System Audit & Feedback Routes (Phase 2)
Provides endpoints for monitoring filtered audit logs and recording/inspecting structured feedback.
"""
import uuid
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from backend.schemas import FeedbackRequest
from backend.engine.audit_logger import get_audit_log, log_event
from backend.database import get_db_connection
from backend.api.auth_routes import get_user_from_token

router = APIRouter(prefix="/audit", tags=["Compliance Audit"])


@router.get("/logs")
def get_logs(
    limit: int = Query(100, ge=1, le=1000),
    action: Optional[str] = Query(None, description="Filter by event action"),
    username: Optional[str] = Query(None, description="Filter by user"),
    system_mode: Optional[str] = Query(None, description="Filter by system strategy mode"),
    date_from: Optional[str] = Query(None, description="ISO timestamp start filter"),
    date_to: Optional[str] = Query(None, description="ISO timestamp end filter"),
):
    """Retrieve system audit logs with multi-parameter filtering."""
    logs = get_audit_log(
        limit=limit,
        action=action,
        username=username,
        system_mode=system_mode,
        date_from=date_from,
        date_to=date_to,
    )
    return {"logs": logs}


@router.post("/feedback")
def submit_feedback(payload: FeedbackRequest, user: dict = Depends(get_user_from_token)):
    """Saves structured stakeholder feedback responses into SQLite."""
    conn = get_db_connection()
    feedback_id = f"FBK-{uuid.uuid4().hex[:8].upper()}"
    reviewer = payload.reviewer_name or user["username"]
    comments = payload.comments or payload.additional_comments or ""
    area = payload.project_area or "General"

    from datetime import datetime, timezone
    now_str = datetime.now(timezone.utc).isoformat()

    try:
        with conn:
            conn.execute("""
                INSERT INTO feedback 
                (feedback_id, username, project_area, understandable, clear_reasons, trust_system, rollback_useful, dashboard_clear, additional_comments, rating, linked_entity_id, submitted_at, submitted_by, overall_comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                feedback_id,
                reviewer,
                area,
                str(payload.understandable),
                str(payload.clear_reasons),
                str(payload.trust_system),
                str(payload.rollback_useful),
                str(payload.dashboard_clear),
                comments,
                payload.rating,
                payload.linked_entity_id,
                now_str,
                reviewer,
                comments,
            ))

        log_event(
            action="SUBMIT_FEEDBACK",
            username=user["username"],
            input_summary=f"Stakeholder feedback {feedback_id} for {area}: {payload.rating} stars",
            result="SUCCESS"
        )
        return {
            "success": True,
            "feedback_id": feedback_id,
            "message": "Structured feedback submitted successfully."
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to record feedback response: {str(exc)}")
    finally:
        conn.close()


@router.get("/feedback/list")
def list_feedback(limit: int = 50):
    """Retrieves full list of recorded stakeholder feedback."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM feedback ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return {"feedbacks": [dict(r) for r in rows]}
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
        rows = conn.execute("SELECT username, additional_comments, rating, created_at, project_area, linked_entity_id FROM feedback ORDER BY id DESC").fetchall()
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

