"""
TestSphere AI — Analytics & Reporting Layer Tests (Phase 2)
Verifies:
- GET /api/analytics/summary: scenario benchmarks, distributions, and overall time reduction
- GET /api/analytics/false-negatives: verification of 0 false negatives
- GET /api/analytics/false-positives: root cause breakdown (safety overrides, dependency propagation, etc.)
- GET /api/analytics/threshold-sensitivity: multi-threshold evaluations
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app


def test_analytics_summary_endpoint(client):
    """Verify aggregated metrics, distributions, and scenario benchmarks."""
    res = client.get("/api/analytics/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["total_tests"] > 0
    assert "module_test_distribution" in data
    assert "failure_density_by_module" in data
    assert "scenario_benchmarks" in data
    assert len(data["scenario_benchmarks"]) >= 5

    # Check precision/recall in benchmarks
    for bench in data["scenario_benchmarks"]:
        assert 0.0 <= bench["precision"] <= 1.0
        assert 0.0 <= bench["recall"] <= 1.0
        assert bench["total_tests"] == data["total_tests"]


def test_false_negative_audit_endpoint(client):
    """Verify false-negative investigation endpoint confirms safety-first zero escapes."""
    res = client.get("/api/analytics/false-negatives?change_id=CHG001")
    assert res.status_code == 200
    data = res.json()
    assert data["change_id"] == "CHG001"
    assert data["false_negative_count"] == 0
    assert data["recall_rate"] == 1.0
    assert data["safety_verdict"] == "VERIFIED_ZERO_FALSE_NEGATIVES"


def test_false_positive_analysis_endpoint(client):
    """Verify false-positive root cause categorization."""
    res = client.get("/api/analytics/false-positives?change_id=CHG001")
    assert res.status_code == 200
    data = res.json()
    assert data["change_id"] == "CHG001"
    assert "cause_breakdown" in data
    assert "safety_override" in data["cause_breakdown"]
    assert "dependency_propagation" in data["cause_breakdown"]
    assert data["total_false_positives"] >= 0
