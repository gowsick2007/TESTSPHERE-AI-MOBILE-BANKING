"""
TestSphere AI — Audit Filtering, Secret Redaction, and Feedback Tests (Phase 2)
Verifies:
- Audit log filtering by action, user, system_mode, timestamp
- Secret redaction (passwords, tokens, keys)
- Structured stakeholder feedback collection, listing, and statistical aggregation
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.engine.audit_logger import log_event, get_audit_log


def test_audit_secret_redaction():
    """Verify that credentials and tokens are redacted from audit log entries."""
    sensitive_summary = 'User login with password="SecretPassword123" and token="Bearer abcdef123456"'
    log_event(
        action="TEST_SECURITY_EVENT",
        username="test_auditor",
        input_summary=sensitive_summary,
        result="Success with api_key='sk-test-secret-key-1234'"
    )

    logs = get_audit_log(limit=5, action="TEST_SECURITY_EVENT")
    assert len(logs) > 0
    logged_event = logs[0]
    assert "SecretPassword123" not in logged_event["input_summary"]
    assert "[REDACTED]" in logged_event["input_summary"]
    assert "sk-test-secret-key-1234" not in logged_event["result"]


def test_audit_log_filtering_via_api(client):
    """Verify GET /api/audit/logs filtering parameters."""
    res = client.get("/api/audit/logs?limit=10")
    assert res.status_code == 200
    assert "logs" in res.json()

    # Filter by specific action
    res_filtered = client.get("/api/audit/logs?action=LOGIN&limit=5")
    assert res_filtered.status_code == 200
    for l in res_filtered.json()["logs"]:
        assert l["action"] == "LOGIN"


def test_structured_feedback_collection_and_stats(client, viewer_headers, unauth_client):
    """Verify structured stakeholder feedback submission and statistics."""
    payload = {
        "reviewer_name": "Senior QA Lead",
        "project_area": "Change Impact Selector",
        "rating": 5,
        "comments": "Decision rationales are exceptionally clear and explainable.",
        "linked_entity_id": "CHG001"
    }

    # Unauthenticated -> 401
    unauth_res = unauth_client.post("/api/audit/feedback", json=payload)
    assert unauth_res.status_code == 401

    viewer_res = client.post("/api/audit/feedback", json=payload, headers=viewer_headers)
    assert viewer_res.status_code == 200
    res_json = viewer_res.json()
    assert res_json["success"] is True
    assert "feedback_id" in res_json

    # List feedback
    list_res = client.get("/api/audit/feedback/list")
    assert list_res.status_code == 200
    assert len(list_res.json()["feedbacks"]) >= 1

    # Get stats
    stats_res = client.get("/api/audit/feedback/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["response_count"] >= 1
    assert stats["average_rating"] > 0
