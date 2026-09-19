"""
TestSphere AI — Input & Data Validation Layer
Validates CSV files, sanitizes paths, and handles security assertions.
"""
import re
import pandas as pd
from typing import Tuple, List, Optional


def sanitize_filename(filename: str) -> str:
    """Strip path traversal components and dangerous characters."""
    clean = re.sub(r"[\\/]", "", filename)
    clean = re.sub(r"\.\.+", ".", clean)
    return clean


def detect_bypass_attempt(action: str, input_summary: str, role: str) -> Tuple[bool, str]:
    """
    Enforce backend permission limits.
    Returns:
        (is_blocked: bool, explanation: str)
    """
    role = (role or "VIEWER").upper()

    # Rule 1: VIEWER role cannot perform mutating/execution actions
    if role == "VIEWER" and action in [
        "ROLLBACK", "CLEAR_DATASET", "IMPORT_DATA", "LOAD_DEMO",
        "REGISTER_CHANGE", "RUN_TESTS", "RUN_EXPERIMENT", "RUN_SCENARIOS"
    ]:
        return True, f"Permission Denied: User role 'VIEWER' is not authorized to execute {action}."

    # Rule 2: QA_ENGINEER cannot execute Rollback
    if role == "QA_ENGINEER" and action == "ROLLBACK":
        return True, "Permission Denied: Emergency strategy rollback is restricted to ADMINISTRATORS only."

    # Rule 3: High-risk security bypass detection
    if "FORCE_SKIP_SECURITY_TEST" in input_summary or "DISABLE_SAFETY_OVERRIDES" in input_summary:
        return True, "Security Assertion Failed: Attempt to disable safety overrides is blocked by system policies."

    return False, ""


def validate_csv_content(dataset_type: str, file_content: bytes) -> Tuple[bool, Optional[str], Optional[pd.DataFrame]]:
    """
    Parse CSV bytes, validate columns, and perform data quality integrity checks.
    Returns:
        (is_valid: bool, error_message: str, parsed_dataframe)
    """
    # 1. Size Limit
    if len(file_content) > 5 * 1024 * 1024:
        return False, "File exceeds maximum size limit of 5MB.", None

    # 2. Parse CSV
    try:
        import io
        df = pd.read_csv(io.BytesIO(file_content))
    except Exception as exc:
        return False, f"Invalid CSV file format: {str(exc)}", None

    # 3. Check column configurations based on dataset type
    columns_mapping = {
        "test_coverage": ["test_id", "test_name", "file_path", "module", "device", "os_version", "execution_time"],
        "dependency_map": ["source_file", "depends_on", "module"],
        "failure_history": ["test_id", "failure_date", "module", "device", "os_version", "severity"],
        "device_matrix": ["device_id", "device_name", "os_type", "os_version", "risk_level", "failure_rate"],
        "code_changes": ["change_id", "file_path", "module", "change_type", "risk_level"]
    }

    if dataset_type not in columns_mapping:
        return False, f"Unknown dataset type classification: {dataset_type}", None

    required = columns_mapping[dataset_type]
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        return False, f"Missing required columns in CSV: {', '.join(missing_cols)}", None

    # 4. Data Quality Checks
    # Check duplicate rows
    duplicates = df.duplicated().sum()
    if duplicates > len(df) * 0.5: # Extreme duplicates
        return False, f"Excessive duplicate records detected ({duplicates} duplicates). File rejected.", None

    # Check for empty rows
    if df.empty:
        return False, "Uploaded CSV file contains no data rows.", None

    # Specific type checks
    if dataset_type == "test_coverage":
        if not pd.api.types.is_numeric_dtype(df["execution_time"]):
            return False, "Data Quality Error: column 'execution_time' must contain numeric values.", None
        # Verify negative runtime
        if (df["execution_time"] < 0).any():
            return False, "Data Quality Error: column 'execution_time' cannot contain negative values.", None

    elif dataset_type == "device_matrix":
        if not pd.api.types.is_numeric_dtype(df["failure_rate"]):
            return False, "Data Quality Error: column 'failure_rate' must contain numeric percentages.", None

    return True, None, df
