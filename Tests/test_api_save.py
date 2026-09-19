"""
TestSphere AI — Test full API save flow via TestClient
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import initialize_database

client = TestClient(app)

CSV = b"""test_id,test_name,file_path,module,device,os_version,execution_time,source_file,depends_on,failure_date,severity,device_id,device_name,os_type,risk_level,failure_rate,change_id,change_type
T001,Login Test,auth/login.py,Authentication,Pixel 8,Android 15,1.5,auth/login.py,db/user.py,2026-01-15,HIGH,D001,Pixel 8,Android,HIGH,0.05,CHG001,MODIFIED
T002,Payment Test,payment/pay.py,Payment,iPhone 15,iOS 18,2.0,payment/pay.py,auth/login.py,2026-02-10,CRITICAL,D002,iPhone 15,iOS,HIGH,0.08,CHG002,ADDED
"""


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    initialize_database()


@pytest.fixture
def admin_token():
    login_res = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@123"})
    assert login_res.status_code == 200
    return login_res.json()["token"]


def test_full_csv_upload_analyze(admin_token):
    # Test commit=false (analyze/preview)
    res = client.post(
        f"/api/data/upload/full?commit=false&token={admin_token}",
        files={"file": ("test.csv", CSV, "text/csv")}
    )
    assert res.status_code == 200
    data = res.json()
    assert data.get("success") is True
    assert data.get("is_valid_to_save") is True
    assert "coverage" in data


def test_full_csv_upload_save(admin_token):
    # Test commit=true (save)
    res = client.post(
        f"/api/data/upload/full?commit=true&token={admin_token}",
        files={"file": ("test.csv", CSV, "text/csv")}
    )
    assert res.status_code == 200
    data = res.json()
    assert data.get("success") is True
    assert "updated_tables" in data
