"""
TestSphere AI — CSV Validation & Cleaning Pipeline Integration Tests
Verifies the robust validation, mapping, cleaning, and persistence of all 5 CSV uploads.
"""
import io
import sys
import json
import pytest
from pathlib import Path

# Add root folder to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import get_db_connection, initialize_database
from backend.security.csv_validator import parse_and_validate_csv, get_storage_paths

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def init_db():
    initialize_database()


def test_valid_csv():
    # 1. Test Coverage Valid CSV
    csv_data = (
        "test_id,test_name,file_path,module,device,os_version,execution_time\n"
        "T001,Verify Login,auth.py,Auth,iPhone,15.2,1.5\n"
        "T002,Verify Signup,auth.py,Auth,iPhone,15.2,2.0\n"
    )
    report = parse_and_validate_csv(
        dataset_type="test_coverage",
        file_content=csv_data.encode(),
        original_filename="test_coverage_valid.csv",
        commit=False
    )
    assert report["success"] is True
    assert report["is_valid_to_save"] is True
    assert report["status"] == "valid"
    assert report["total_rows_before"] == 2
    assert report["total_rows_after"] == 2
    assert report["statistics"]["missing_values"] == 0
    assert report["statistics"]["duplicate_rows"] == 0


def test_empty_csv():
    csv_data = ""
    report = parse_and_validate_csv(
        dataset_type="test_coverage",
        file_content=csv_data.encode(),
        original_filename="empty.csv",
        commit=False
    )
    assert report["success"] is False
    assert report["status"] == "empty"
    assert "no data rows" in report["error_message"].lower()


def test_corrupted_csv():
    # Unclosed quote is a classic pandas parsing failure trigger
    csv_data = 'test_id,test_name,file_path\nT001,"Verify Login,auth.py'
    report = parse_and_validate_csv(
        dataset_type="test_coverage",
        file_content=csv_data.encode(),
        original_filename="corrupt.csv",
        commit=False
    )
    assert report["success"] is False
    assert report["status"] == "corrupted"
    assert "corrupted" in report["error_message"].lower() or "parsing" in report["error_message"].lower() or "tokenizing" in report["error_message"].lower()


def test_missing_required_column_and_synonym_mapping():
    # 'os_version' is missing, but 'OS' (synonym) is present
    csv_data = (
        "test_id,test_name,file_path,module,device,OS,execution_time\n"
        "T001,Verify Login,auth.py,Auth,iPhone,15.2,1.5\n"
    )
    report = parse_and_validate_csv(
        dataset_type="test_coverage",
        file_content=csv_data.encode(),
        original_filename="test_coverage_syn.csv",
        commit=False
    )
    # Since os_version is missing, it returns status="needs_mapping" and proposes "OS" -> "os_version"
    assert report["is_valid_to_save"] is False
    assert report["status"] == "needs_mapping"
    assert "os_version" in report["columns"]["missing"]
    assert report["proposed_mapping"]["os_version"] == "OS"

    # Now apply the user mapping
    report_mapped = parse_and_validate_csv(
        dataset_type="test_coverage",
        file_content=csv_data.encode(),
        original_filename="test_coverage_syn.csv",
        user_mapping={"os_version": "OS"},
        commit=False
    )
    assert report_mapped["success"] is True
    assert report_mapped["is_valid_to_save"] is True
    assert report_mapped["status"] == "valid"
    assert "os_version" in report_mapped["columns"]["valid"]


def test_missing_values_and_id_rules():
    # test_name is missing (will fill with default "Unknown")
    # test_id is missing on row 2 (which is a unique key / required ID, so it should fail to save)
    csv_data = (
        "test_id,test_name,file_path,module,device,os_version,execution_time\n"
        "T001,,auth.py,Auth,iPhone,15.2,1.5\n"
        ",Verify Login,auth.py,Auth,iPhone,15.2,1.5\n"
    )
    report = parse_and_validate_csv(
        dataset_type="test_coverage",
        file_content=csv_data.encode(),
        original_filename="test_missing.csv",
        commit=False
    )
    assert report["statistics"]["missing_values"] == 2
    # Second row has missing test_id, so is_valid_to_save must be False
    assert report["is_valid_to_save"] is False
    assert any("Missing required identifier 'test_id'" in issue for issue in report["issues"])


def test_duplicate_rows_and_ids():
    csv_data = (
        "test_id,test_name,file_path,module,device,os_version,execution_time\n"
        "T001,Verify Login,auth.py,Auth,iPhone,15.2,1.5\n"
        "T001,Verify Login,auth.py,Auth,iPhone,15.2,1.5\n" # Exact Duplicate Row
        "T001,Verify Login Updated,auth.py,Auth,iPhone,15.2,1.5\n" # Duplicate ID
    )
    report = parse_and_validate_csv(
        dataset_type="test_coverage",
        file_content=csv_data.encode(),
        original_filename="test_dupes.csv",
        commit=False
    )
    assert report["statistics"]["duplicate_rows"] == 1
    assert report["statistics"]["duplicate_ids"] == 1
    assert report["total_rows_after"] == 1 # Deduplicated to 1 row
    assert report["before_after"]["duplicates"]["before"] == 1


def test_invalid_dates():
    # 2026-02-31 is invalid, so that row should be dropped
    csv_data = (
        "test_id,failure_date,module,device,os_version,severity\n"
        "T001,2026-02-15,Auth,iPhone,15.2,MEDIUM\n"
        "T002,2026-02-31,Auth,iPhone,15.2,MEDIUM\n" # Invalid Date
    )
    report = parse_and_validate_csv(
        dataset_type="failure_history",
        file_content=csv_data.encode(),
        original_filename="failures_date.csv",
        commit=False
    )
    assert report["statistics"]["invalid_dates"] == 1
    assert report["total_rows_after"] == 1 # Row with invalid date dropped
    assert any("Dropped 1 rows due to invalid/missing date" in action for action in report["actions"])


def test_invalid_numeric_values():
    # row 1: negative execution time (takes absolute value)
    # row 2: non-numeric execution time (resets to default 0.5)
    csv_data = (
        "test_id,test_name,file_path,module,device,os_version,execution_time\n"
        "T001,Verify Login,auth.py,Auth,iPhone,15.2,-1.5\n"
        "T002,Verify Signup,auth.py,Auth,iPhone,15.2,two_seconds\n"
    )
    report = parse_and_validate_csv(
        dataset_type="test_coverage",
        file_content=csv_data.encode(),
        original_filename="test_nums.csv",
        commit=False
    )
    assert report["statistics"]["invalid_numeric"] == 2
    # Verify absolute value conversion for T001
    assert report["preview"]["after"][0]["execution_time"] == 1.5
    # Verify default conversion for T002
    assert report["preview"]["after"][1]["execution_time"] == 0.5


def test_invalid_categorical_values_and_case_normalization():
    # row 1: severity 'high' (case normalized to 'HIGH')
    # row 2: severity 'SUPER_HIGH' (invalid, reset to default 'MEDIUM')
    csv_data = (
        "test_id,failure_date,module,device,os_version,severity\n"
        "T001,2026-02-15,Auth,iPhone,15.2,high\n"
        "T002,2026-02-15,Auth,iPhone,15.2,SUPER_HIGH\n"
    )
    report = parse_and_validate_csv(
        dataset_type="failure_history",
        file_content=csv_data.encode(),
        original_filename="failures_cat.csv",
        commit=False
    )
    assert report["statistics"]["invalid_categories"] == 1 # high is just case normalized, SUPER_HIGH is invalid
    assert report["preview"]["after"][0]["severity"] == "HIGH"
    assert report["preview"]["after"][1]["severity"] == "MEDIUM"


def test_extra_columns():
    csv_data = (
        "test_id,test_name,file_path,module,device,os_version,execution_time,author_name\n"
        "T001,Verify Login,auth.py,Auth,iPhone,15.2,1.5,Developer_A\n"
    )
    report = parse_and_validate_csv(
        dataset_type="test_coverage",
        file_content=csv_data.encode(),
        original_filename="test_extra.csv",
        commit=False
    )
    assert report["statistics"]["extra_columns"] == 1
    assert "author_name" in report["columns"]["extra"]
    assert "author_name" not in report["preview"]["after"][0] # Dropped from clean schema


def test_whitespace_trimming():
    csv_data = (
        "test_id,test_name,file_path,module,device,os_version,execution_time\n"
        " T001 , Verify Login ,auth.py,Auth,iPhone,15.2,1.5\n"
    )
    report = parse_and_validate_csv(
        dataset_type="test_coverage",
        file_content=csv_data.encode(),
        original_filename="test_trim.csv",
        commit=False
    )
    assert report["preview"]["after"][0]["test_id"] == "T001"
    assert report["preview"]["after"][0]["test_name"] == "Verify Login"


def test_api_commit_false_vs_commit_true():
    # Clean up leftovers first
    conn = get_db_connection()
    conn.execute("DELETE FROM test_coverage WHERE test_id='T099'")
    conn.commit()
    conn.close()

    # Login as admin to get auth token
    login_res = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@123"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]

    csv_data = (
        "test_id,test_name,file_path,module,device,os_version,execution_time\n"
        "T099,Temp Test,temp.py,Temp,Simulator,12,3.5\n"
    )
    
    # 1. Commit=False
    res_false = client.post(
        f"/api/data/upload/test_coverage?token={token}&commit=false",
        files={"file": ("temp_test.csv", csv_data.encode(), "text/csv")}
    )
    assert res_false.status_code == 200
    report = res_false.json()
    assert report["total_rows_after"] == 1
    
    # Verify NOT in SQLite
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM test_coverage WHERE test_id='T099'").fetchone()
    assert row is None
    conn.close()

    # 2. Commit=True
    res_true = client.post(
        f"/api/data/upload/test_coverage?token={token}&commit=true",
        files={"file": ("temp_test.csv", csv_data.encode(), "text/csv")}
    )
    assert res_true.status_code == 200
    assert res_true.json()["success"] is True
    
    # Verify Saved to SQLite
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM test_coverage WHERE test_id='T099'").fetchone()
    assert row is not None
    assert row["test_name"] == "Temp Test"
    assert row["execution_time"] == 3.5
    conn.close()
