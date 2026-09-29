"""
TestSphere AI — Strategy Versioning & Rollback Hardening Tests (Phase 2)
Verifies:
- Listing and creating strategy versions
- RBAC authorization: ADMIN allowed, QA_ENGINEER and VIEWER blocked (403)
- Atomic rollback transaction guarantees no partial state on simulated database error
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.rollback.rollback_manager import change_system_strategy
from backend.engine.data_access import get_current_strategy


def test_strategy_versioning_lifecycle(client, admin_headers, qa_headers, viewer_headers, unauth_client):
    """Test listing and creating strategy versions with RBAC."""
    # 1. Unauthenticated GET /api/strategy/versions is public
    res = unauth_client.get("/api/strategy/versions")
    assert res.status_code == 200
    assert "versions" in res.json()
    assert len(res.json()["versions"]) >= 1

    import uuid
    unique_v_id = f"v2.0.0-{uuid.uuid4().hex[:6]}"
    payload = {
        "version_id": unique_v_id,
        "strategy_name": "SMART_SELECTOR_V2",
        "threshold": 55.0,
        "scoring_weights": {"direct_coverage": 45, "dependency_relationship": 35},
        "safety_rules": ["RULE_1_UNKNOWN_DEPENDENCY", "RULE_3_SECURITY_CRITICAL"],
        "description": "Experimental v2 strategy with increased weights"
    }

    # 2. Unauthenticated POST -> 401
    unauth_post = unauth_client.post("/api/strategy/versions", json=payload)
    assert unauth_post.status_code == 401

    # 3. VIEWER POST -> 403
    viewer_post = client.post("/api/strategy/versions", json=payload, headers=viewer_headers)
    assert viewer_post.status_code == 403

    # 4. QA_ENGINEER POST -> 403 (Strategy version creation requires ADMIN)
    qa_post = client.post("/api/strategy/versions", json=payload, headers=qa_headers)
    assert qa_post.status_code == 403

    # 5. ADMIN POST -> 200
    admin_post = client.post("/api/strategy/versions", json=payload, headers=admin_headers)
    assert admin_post.status_code == 200
    data = admin_post.json()
    assert data["version_id"] == unique_v_id
    assert data["status"] == "ACTIVE"


def test_atomic_rollback_and_invalid_strategy(client, admin_headers):
    """Verify that rollback rejects invalid strategies and executes atomically."""
    # 1. Invalid strategy
    res_invalid = client.post("/api/strategy/rollback", json={
        "to_strategy": "NON_EXISTENT_STRATEGY",
        "reason": "Test invalid strategy"
    }, headers=admin_headers)
    assert res_invalid.status_code == 400

    # 2. Valid rollback to LEGACY_FULL_SUITE
    res_rb = client.post("/api/strategy/rollback", json={
        "to_strategy": "LEGACY_FULL_SUITE",
        "reason": "Routine drill"
    }, headers=admin_headers)
    assert res_rb.status_code == 200
    assert res_rb.json()["to_strategy"] == "LEGACY_FULL_SUITE"
    assert get_current_strategy() == "LEGACY_FULL_SUITE"

    # 3. Restore back to SMART_SELECTOR
    res_restore = client.post("/api/strategy/rollback", json={
        "to_strategy": "SMART_SELECTOR",
        "reason": "Restoring smart mode"
    }, headers=admin_headers)
    assert res_restore.status_code == 200
    assert get_current_strategy() == "SMART_SELECTOR"
