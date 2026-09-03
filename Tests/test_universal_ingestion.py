"""
TestSphere AI — Universal Dataset Ingestion & Self-Healing Pipeline Tests
Verifies advanced parsing, malformed row repairs, semantic mapping, safety statuses, and database isolation.
"""
import io
import sys
import json
import pytest
import sqlite3
import pandas as pd
from pathlib import Path

# Add root folder to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import get_db_connection
from backend.security.csv_validator import parse_and_validate_full_csv, SCHEMAS
from Engine.database import get_connection, IN_MEMORY_MOCK_ACTIVE
from Simulation.failure_simulator import run_all_scenarios

client = TestClient(app)


def test_encoding_and_delimiter_detection():
    # CSV encoded with latin-1 and separated by semicolons
    csv_data = (
        "Test ID;Test Name;File Path;Module;Device;OS Version;Execution Time\n"
        "T101;Verify Login Café;auth.py;Auth;iPhone;15.2;1.5\n"
    )
    content = csv_data.encode("latin-1")
    report = parse_and_validate_full_csv(
        file_content=content,
        original_filename="latin1_semicolon.csv",
        commit=False
    )
    assert report["success"] is True
    assert report["encoding"].lower() in ["latin-1", "iso-8859-1", "cp1252"]
    assert report["delimiter"] == ";"
    # Check that column mapping mapped Test ID to test_id, and French character was preserved
    assert report["final_mapping"]["test_id"] == "Test ID"
    assert report["preview"]["after"]["test_coverage"][0]["test_name"] == "Verify Login Café"


def test_structural_repairs_and_isolation():
    # Row 1: Valid
    # Row 2: Malformed (8 fields instead of 7) - will be repaired by truncating extra fields
    # Row 3: Malformed (5 fields instead of 7) - will be padded
    # Row 4: Unrecoverable quoting mismatch
    csv_data = (
        "test_id,test_name,file_path,module,device,os_version,execution_time\n"
        "T201,Verify Login,auth.py,Auth,iPhone,15.2,1.5\n"
        "T202,Verify Signup,auth.py,Auth,iPhone,15.2,2.0,EXTRA_VAL\n"
        "T203,Verify Logout,auth.py,Auth,iPhone\n"
        'T204,"Verify Quoting Fail,auth.py,Auth,iPhone,15.2,1.5\n'
    )
    report = parse_and_validate_full_csv(
        file_content=csv_data.encode(),
        original_filename="repairable.csv",
        commit=False
    )
    assert report["success"] is True
    # The repairs log should document repaired rows
    repairs = report["repairs"]
    assert any("repaired" in r.lower() for r in repairs)
    # The isolated rows should contain the quoting fail row
    assert len(report["isolated_rows"]) > 0
    assert any("isolated" in r.lower() for r in repairs)


def test_semantic_column_mapping_and_fuzzy_matching():
    # Headers are uppercase, lowercase, with spaces, underscores, and fuzzy synonyms
    csv_data = (
        "TEST_IDENTIFIER,test name,FILE_PATH,module,Target Device,OS_VER,Execution_Secs\n"
        "T301,Verify Login,auth.py,Auth,iPhone,15.2,1.5\n"
    )
    report = parse_and_validate_full_csv(
        file_content=csv_data.encode(),
        original_filename="fuzzy.csv",
        commit=False
    )
    assert report["success"] is True
    # Verify synonyms mapped correctly
    assert report["final_mapping"]["test_id"] == "TEST_IDENTIFIER"
    assert report["final_mapping"]["test_name"] == "test name"
    assert report["final_mapping"]["device"] == "Target Device"
    assert report["final_mapping"]["os_version"] == "OS_VER"
    assert report["final_mapping"]["execution_time"] == "Execution_Secs"


def test_data_quality_remediation_and_safety_statuses():
    # 1. READY_TO_IMPORT
    csv_valid = (
        "test_id,test_name,file_path,module,device,os_version,execution_time,"
        "source_file,depends_on,failure_date,severity,device_id,device_name,os_type,risk_level,failure_rate,change_id,change_type\n"
        "T401,Verify Login,auth.py,Auth,iPhone,15.2,-1.5,"
        "auth.py,db.py,2026-02-15,HIGH,D1,iPhone,iOS,LOW,0.0,C1,MODIFIED\n"
        "T402,Verify Signup,auth.py,Auth,iPhone,15.2,two_seconds,"
        "auth.py,db.py,2026-02-15,HIGH,D1,iPhone,iOS,LOW,0.0,C1,MODIFIED\n"
    )
    report_valid = parse_and_validate_full_csv(
        file_content=csv_valid.encode(),
        original_filename="valid_data.csv",
        commit=False
    )
    assert report_valid["status"] == "READY_TO_IMPORT"
    assert report_valid["is_valid_to_save"] is True
    # Verify absolute value conversion
    assert report_valid["preview"]["after"]["test_coverage"][0]["execution_time"] == 1.5
    # Verify fallback to default value
    assert report_valid["preview"]["after"]["test_coverage"][1]["execution_time"] == 0.5

    # 2. NEEDS_REVIEW (incomplete schema coverage / missing required fields)
    csv_incomplete = (
        "test_id,file_path,module,device,os_version,execution_time\n" # test_name is missing and has no synonym
        "T403,auth.py,Auth,iPhone,15.2,1.5\n"
    )
    report_inc = parse_and_validate_full_csv(
        file_content=csv_incomplete.encode(),
        original_filename="incomplete.csv",
        commit=False
    )
    assert report_inc["status"] == "NEEDS_REVIEW"
    assert report_inc["is_valid_to_save"] is False

    # 3. PARTIALLY_USABLE (some schemas complete, some incomplete/unavailable)
    # This CSV contains all columns for test_coverage, but none for other schemas
    csv_partial = (
        "test_id,test_name,file_path,module,device,os_version,execution_time\n"
        "T404,Verify Login,auth.py,Auth,iPhone,15.2,1.5\n"
    )
    report_part = parse_and_validate_full_csv(
        file_content=csv_partial.encode(),
        original_filename="partial.csv",
        commit=False
    )
    # The coverage of test_coverage will be DETECTED, others UNAVAILABLE.
    # Therefore, status is PARTIALLY_USABLE and is_valid_to_save is True.
    assert report_part["status"] == "PARTIALLY_USABLE"
    assert report_part["is_valid_to_save"] is True
    assert report_part["coverage"]["test_coverage"] == "DETECTED"
    assert report_part["coverage"]["dependency_map"] == "UNAVAILABLE"

    # 4. UNRECOVERABLE (no schemas detected at all)
    csv_bad = (
        "unrelated_a,unrelated_b,unrelated_c\n"
        "1,2,3\n"
    )
    report_bad = parse_and_validate_full_csv(
        file_content=csv_bad.encode(),
        original_filename="bad.csv",
        commit=False
    )
    assert report_bad["status"] == "UNRECOVERABLE"
    assert report_bad["is_valid_to_save"] is False


def test_experiment_lab_database_isolation():
    # Verify that running safety assertions does NOT seed the physical database.
    # Works regardless of whether the database is empty or contains real data.

    # Check that IN_MEMORY_MOCK_ACTIVE is initially False
    assert IN_MEMORY_MOCK_ACTIVE is False

    # Record the row count BEFORE running scenarios
    conn = get_connection()
    try:
        before_count = conn.execute("SELECT COUNT(*) FROM test_coverage").fetchone()[0]
    except sqlite3.OperationalError:
        before_count = 0
    finally:
        conn.close()

    # Monkeypatch get_all_tests to simulate an empty database state
    import Simulation.failure_simulator as fs
    orig_get_all_tests = fs.get_all_tests

    fs.get_all_tests = lambda: []
    try:
        results = run_all_scenarios()
        assert len(results) == 5
    finally:
        fs.get_all_tests = orig_get_all_tests

    # Row count must be IDENTICAL — no physical seeding must have occurred.
    conn = get_connection()
    try:
        after_count = conn.execute("SELECT COUNT(*) FROM test_coverage").fetchone()[0]
    except sqlite3.OperationalError:
        after_count = 0
    finally:
        conn.close()

    assert after_count == before_count, (
        f"run_all_scenarios() must NOT seed the physical database. "
        f"Before: {before_count}, After: {after_count}."
    )
