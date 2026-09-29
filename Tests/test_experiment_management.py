"""
TestSphere AI — Managed Experiment Tests (Phase 2)
Verifies:
- Creation and persistence of experiments in SQLite
- Inspection of completed experiments by ID
- History listing of completed experiments
- Dynamic side-by-side comparison of multiple experiments
- Immutability: modifying a completed experiment returns 400
- Reproducibility: same input produces identical analytical metrics
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app


def test_experiment_creation_and_inspection(client, admin_headers, viewer_headers, unauth_client):
    """Test experiment creation, authorization, and retrieval."""
    exp_payload = {
        "scenario": "Payment_Regression_Bench",
        "changed_files": ["payment/payment.py"],
        "module": "Payment",
        "is_security_sensitive": True,
        "risk_level": "HIGH",
        "threshold": 50.0,
        "seed": 12345
    }

    # 1. Unauthenticated -> 401
    unauth_res = unauth_client.post("/api/experiment/create", json=exp_payload)
    assert unauth_res.status_code == 401

    # 2. VIEWER -> 403
    viewer_res = client.post("/api/experiment/create", json=exp_payload, headers=viewer_headers)
    assert viewer_res.status_code == 403

    # 3. ADMIN -> 200
    create_res = client.post("/api/experiment/create", json=exp_payload, headers=admin_headers)
    assert create_res.status_code == 200
    data = create_res.json()
    assert "experiment_id" in data
    exp_id = data["experiment_id"]
    assert data["status"] == "COMPLETED"

    # 4. Inspect by ID
    get_res = client.get(f"/api/experiment/{exp_id}")
    assert get_res.status_code == 200
    fetched = get_res.json()
    assert fetched["experiment_id"] == exp_id
    assert fetched["scenario"] == "Payment_Regression_Bench"
    assert fetched["status"] == "COMPLETED"

    # 5. List history
    history_res = client.get("/api/experiment/history")
    assert history_res.status_code == 200
    assert any(e["experiment_id"] == exp_id for e in history_res.json()["experiments"])

    # 6. Immutability: PUT must fail
    put_res = client.put(f"/api/experiment/{exp_id}", headers=admin_headers)
    assert put_res.status_code == 400
    assert "immutable" in put_res.json()["detail"].lower()


def test_experiment_comparison(client, admin_headers):
    """Test side-by-side comparison of multiple experiment runs."""
    # Create two experiments with different seeds
    res1 = client.post("/api/experiment/create", json={
        "scenario": "Exp_Run_A",
        "changed_files": ["payment/payment.py"],
        "module": "Payment",
        "threshold": 50.0,
        "seed": 12345
    }, headers=admin_headers)
    assert res1.status_code == 200
    id1 = res1.json()["experiment_id"]

    res2 = client.post("/api/experiment/create", json={
        "scenario": "Exp_Run_B",
        "changed_files": ["auth/login.py"],
        "module": "Authentication",
        "threshold": 50.0,
        "seed": 12345
    }, headers=admin_headers)
    assert res2.status_code == 200
    id2 = res2.json()["experiment_id"]

    # Compare them
    cmp_res = client.post("/api/experiment/compare", json={"experiment_ids": [id1, id2]})
    assert cmp_res.status_code == 200
    cmp_data = cmp_res.json()
    assert cmp_data["total_compared"] == 2
    assert len(cmp_data["experiments"]) == 2


def test_experiment_reproducibility_identical_metrics(client, admin_headers):
    """Running an experiment with identical parameters must yield identical metrics."""
    payload = {
        "changed_files": ["payment/payment.py"],
        "module": "Payment",
        "is_security_sensitive": False,
        "risk_level": "HIGH"
    }

    run1 = client.post("/api/experiment/run", json=payload, headers=admin_headers).json()
    run2 = client.post("/api/experiment/run", json=payload, headers=admin_headers).json()

    assert run1["comparison"]["tests_run_smart"] == run2["comparison"]["tests_run_smart"]
    assert run1["comparison"]["time_reduction_pct"] == run2["comparison"]["time_reduction_pct"]
    assert run1["quality"]["precision"] == run2["quality"]["precision"]
    assert run1["quality"]["recall"] == run2["quality"]["recall"]
