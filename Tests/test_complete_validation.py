"""
TestSphere AI — Complete End-to-End Pipeline Validation Tests
Verifies authentication, dataset upload, audit logging, change analysis,
test selection, dependency graph, experiment scenarios, and what-if simulation.
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import initialize_database, get_db_connection

client = TestClient(app)

CSV_CONTENT = (
    "test_id,test_name,file_path,module,device,os_version,execution_time,"
    "source_file,depends_on,failure_date,severity,device_id,device_name,"
    "os_type,risk_level,failure_rate,change_id,change_type,changed_at\n"
    "T101,Verify Login,auth/login.py,Authentication,Pixel 8,Android 15,1.5,"
    "auth/login.py,db/user.py,2026-08-01,HIGH,D001,Pixel 8,Android,LOW,0.02,CHG-T01,MODIFIED,2026-08-01 12:00:00\n"
).encode("utf-8")


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    initialize_database()


@pytest.fixture(scope="module")
def admin_session():
    res = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@123"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    cookie_val = res.cookies.get("session_token")
    return {
        "token": data["token"],
        "cookie": cookie_val
    }


def test_login():
    res = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@123"})
    assert res.status_code == 200
    data = res.json()
    assert data.get("success") is True
    assert "token" in data


def test_auth_me(admin_session):
    headers = {"Authorization": f"Bearer {admin_session['token']}"}
    cookies = {"session_token": admin_session["cookie"]} if admin_session["cookie"] else None
    res = client.get("/api/auth/me", headers=headers, cookies=cookies)
    assert res.status_code == 200
    assert res.json().get("authenticated") is True
    assert res.json().get("role") == "ADMIN"


def test_dataset_status():
    res = client.get("/api/data/status")
    assert res.status_code == 200
    assert "health" in res.json()


def test_dataset_upload_preview(admin_session):
    token = admin_session["token"]
    res = client.post(
        f"/api/data/upload/full?commit=false&token={token}",
        files={"file": ("test_dataset.csv", CSV_CONTENT, "text/csv")}
    )
    assert res.status_code == 200
    assert res.json().get("success") is True


def test_dataset_import(admin_session):
    token = admin_session["token"]
    res = client.post(
        f"/api/data/upload/full?commit=true&token={token}",
        files={"file": ("test_dataset.csv", CSV_CONTENT, "text/csv")}
    )
    assert res.status_code == 200
    assert res.json().get("success") is True


def test_delete_dataset_table_and_audit(admin_session):
    token = admin_session["token"]
    res = client.delete(f"/api/data/code_changes?token={token}")
    assert res.status_code == 200
    assert res.json().get("success") is True

    # Verify audit log in SQLite
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM audit_log WHERE action = 'CLEAR_DATASET' ORDER BY id DESC LIMIT 1").fetchone()
        assert row is not None
        assert row["timestamp"] is not None
    finally:
        conn.close()


def test_change_analysis(admin_session):
    token = admin_session["token"]
    change_payload = {
        "changed_files": ["auth/login.py"],
        "change_type": "MODIFIED",
        "module": "Authentication",
        "is_security_sensitive": True,
        "risk_level": "HIGH"
    }
    res = client.post(f"/api/change/analyze?token={token}", json=change_payload)
    assert res.status_code == 200
    assert "change_context" in res.json()


def test_change_registration(admin_session):
    token = admin_session["token"]
    change_payload = {
        "changed_files": ["auth/login.py"],
        "change_type": "MODIFIED",
        "module": "Authentication",
        "is_security_sensitive": True,
        "risk_level": "HIGH"
    }
    res = client.post(f"/api/change/register?token={token}", json=change_payload)
    assert res.status_code == 200
    assert res.json().get("success") is True


def test_test_selection(admin_session):
    token = admin_session["token"]
    change_payload = {
        "changed_files": ["auth/login.py"],
        "change_type": "MODIFIED",
        "module": "Authentication",
        "is_security_sensitive": True,
        "risk_level": "HIGH"
    }
    res = client.post(f"/api/tests/selection?token={token}", json=change_payload)
    assert res.status_code == 200
    assert "decisions" in res.json()


def test_dependency_graph_preview():
    res = client.get("/api/data/dependency_map/preview")
    assert res.status_code == 200


def test_experiment_lab_run_scenarios(admin_session):
    token = admin_session["token"]
    res = client.post(f"/api/experiment/run-scenarios?token={token}")
    assert res.status_code == 200
    assert "results" in res.json()


def test_what_if_analysis(admin_session):
    token = admin_session["token"]
    whatif_payload = {
        "module": "Authentication",
        "device": "Pixel 8",
        "change_type": "MODIFIED",
        "risk_level": "HIGH",
        "is_security_sensitive": True
    }
    res = client.post(f"/api/what-if?token={token}", json=whatif_payload)
    assert res.status_code == 200
    assert "selected_tests" in res.json()
