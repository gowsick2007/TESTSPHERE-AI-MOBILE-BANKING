import sqlite3
import pytest
import io
import sys
import glob

def run_all_pytests():
    print("\n=== RUNNING ALL PYTESTS IN Tests/ ===")
    test_files = glob.glob("Tests/test_*.py")
    # exclude our own wrapper
    test_files = [f for f in test_files if "test_structure_and_pytest.py" not in f and "test_complete_validation.py" not in f and "test_register_change.py" not in f and "test_api_save.py" not in f]
    print(f"Running tests in files: {test_files}")
    
    stdout_backup = sys.stdout
    string_io = io.StringIO()
    sys.stdout = string_io
    
    ret_code = pytest.main(["-v"] + test_files)
    
    sys.stdout = stdout_backup
    pytest_output = string_io.getvalue()
    print("Pytest stdout:")
    print(pytest_output)
    print(f"Pytest return code: {ret_code}")

if __name__ == "__main__":
    run_all_pytests()
