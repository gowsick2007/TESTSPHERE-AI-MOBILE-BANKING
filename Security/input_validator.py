"""
TestSphere AI — Input Validator
Validates all user-provided inputs before they reach the engine.
Rejects malformed, suspicious, or unsafe inputs with clear messages.
"""
import re
import io
import logging
import pandas as pd
from pathlib import PurePosixPath

logger = logging.getLogger(__name__)

# ─── Schema definitions ───────────────────────────────────────────────────────

REQUIRED_COLUMNS: dict[str, list[str]] = {
    "test_coverage": [
        "test_id", "test_name", "file_path", "module", "device", "os_version", "execution_time"
    ],
    "dependency_map": ["source_file", "depends_on", "module"],
    "failure_history": ["test_id", "failure_date", "module", "device", "severity"],
    "device_matrix": ["device_id", "device_name", "os_type", "os_version", "risk_level"],
    "code_changes": ["change_id", "file_path", "module", "change_type", "risk_level"],
}

VALID_CHANGE_TYPES = {"MODIFIED", "ADDED", "DELETED", "REFACTORED", "SECURITY_PATCH"}
VALID_RISK_LEVELS  = {"LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"}
VALID_SEVERITY     = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
VALID_ROLES        = {"ADMIN", "QA_ENGINEER", "VIEWER"}

# File path: allow only relative paths with safe characters
_SAFE_PATH_RE = re.compile(r'^[\w\-/.]+$')
# Test ID: alphanumeric prefix + digits
_TEST_ID_RE   = re.compile(r'^[A-Za-z0-9_\-]{1,50}$')


class ValidationError(Exception):
    """Raised when input validation fails."""


# ─── File path validation ─────────────────────────────────────────────────────

def validate_file_path(path: str) -> str:
    """Validate a changed-file path. Returns the sanitized path or raises."""
    if not path or not path.strip():
        raise ValidationError("File path cannot be empty.")
    path = path.strip()
    if len(path) > 300:
        raise ValidationError("File path exceeds maximum length (300 chars).")
    if not _SAFE_PATH_RE.match(path):
        raise ValidationError(
            f"File path '{path}' contains invalid characters. "
            "Only alphanumeric characters, hyphens, underscores, dots and slashes are allowed."
        )
    # Prevent path traversal
    if ".." in path:
        raise ValidationError("Path traversal ('..') is not allowed.")
    return path


def validate_file_paths(paths: list[str]) -> list[str]:
    """Validate a list of file paths. Returns sanitized list."""
    if not paths:
        raise ValidationError("At least one changed file must be provided.")
    return [validate_file_path(p) for p in paths]


# ─── Test ID validation ───────────────────────────────────────────────────────

def validate_test_id(test_id: str) -> str:
    if not test_id or not test_id.strip():
        raise ValidationError("Test ID cannot be empty.")
    test_id = test_id.strip()
    if not _TEST_ID_RE.match(test_id):
        raise ValidationError(f"Invalid test ID format: '{test_id}'.")
    return test_id


# ─── CSV validation ───────────────────────────────────────────────────────────

def validate_csv(
    file_bytes: bytes,
    dataset_type: str,
) -> dict:
    """
    Validate a CSV file for a given dataset type.

    Returns:
        {
          "valid": bool,
          "df": DataFrame | None,
          "errors": list[str],
          "warnings": list[str],
          "row_count": int,
          "duplicate_count": int,
          "missing_value_cols": list[str],
        }
    """
    errors: list[str] = []
    warnings: list[str] = []

    # File type check (must be parseable CSV)
    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as exc:
        return {
            "valid": False, "df": None, "errors": [f"Cannot parse CSV: {exc}"],
            "warnings": [], "row_count": 0, "duplicate_count": 0, "missing_value_cols": [],
        }

    # Required columns
    required = REQUIRED_COLUMNS.get(dataset_type, [])
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        errors.append(f"Missing required columns: {', '.join(missing_cols)}")

    if errors:
        return {
            "valid": False, "df": None, "errors": errors,
            "warnings": warnings, "row_count": len(df),
            "duplicate_count": 0, "missing_value_cols": [],
        }

    # Empty dataset
    if len(df) == 0:
        errors.append("CSV is empty — no records found.")

    # Missing values in required columns
    mv_cols = [c for c in required if df[c].isnull().any()]
    if mv_cols:
        for col in mv_cols:
            count = df[col].isnull().sum()
            warnings.append(f"Column '{col}' has {count} missing value(s).")

    # Duplicate records
    dup_count = df.duplicated().sum()
    if dup_count > 0:
        warnings.append(f"{dup_count} duplicate row(s) detected.")

    # Type/enum checks per dataset
    _validate_enum_columns(df, dataset_type, warnings, errors)

    valid = len(errors) == 0
    return {
        "valid": valid,
        "df": df if valid else None,
        "errors": errors,
        "warnings": warnings,
        "row_count": len(df),
        "duplicate_count": int(dup_count),
        "missing_value_cols": mv_cols,
    }


def _validate_enum_columns(df: pd.DataFrame, dataset_type: str,
                             warnings: list, errors: list) -> None:
    if dataset_type == "code_changes":
        if "change_type" in df.columns:
            invalid = df[~df["change_type"].isin(VALID_CHANGE_TYPES)]["change_type"].unique()
            if len(invalid):
                warnings.append(f"Unknown change_type values: {list(invalid)[:5]}")
        if "risk_level" in df.columns:
            invalid = df[~df["risk_level"].isin(VALID_RISK_LEVELS)]["risk_level"].unique()
            if len(invalid):
                warnings.append(f"Unknown risk_level values: {list(invalid)[:5]}")

    if dataset_type == "failure_history":
        if "severity" in df.columns:
            invalid = df[~df["severity"].isin(VALID_SEVERITY)]["severity"].unique()
            if len(invalid):
                warnings.append(f"Unknown severity values: {list(invalid)[:5]}")

    if dataset_type == "device_matrix":
        if "risk_level" in df.columns:
            invalid = df[~df["risk_level"].isin(VALID_RISK_LEVELS)]["risk_level"].unique()
            if len(invalid):
                warnings.append(f"Unknown risk_level values: {list(invalid)[:5]}")

    if dataset_type == "test_coverage":
        if "execution_time" in df.columns:
            try:
                df["execution_time"] = pd.to_numeric(df["execution_time"], errors="coerce")
                neg_count = (df["execution_time"] < 0).sum()
                if neg_count > 0:
                    warnings.append(f"{neg_count} record(s) have negative execution_time.")
            except Exception:
                pass


# ─── Bypass / misuse detection ───────────────────────────────────────────────

def detect_bypass_attempt(
    action: str,
    target: str = "",
    user_role: str = "VIEWER",
) -> tuple[bool, str]:
    """
    Check if an action is a potential bypass or misuse attempt.

    Returns: (is_blocked: bool, reason: str)
    """
    dangerous_actions = {
        "FORCE_SKIP_SECURITY_TEST",
        "DISABLE_SAFETY_OVERRIDES",
        "CLEAR_AUDIT_LOG",
        "DROP_TABLE",
        "SKIP_CRITICAL_MODULE",
    }
    if action.upper() in dangerous_actions:
        return True, f"Action '{action}' is blocked — it would bypass safety controls."

    # Role-based access
    if action in ("ROLLBACK", "CHANGE_STRATEGY") and user_role not in ("ADMIN",):
        return True, f"Role '{user_role}' is not authorized to perform '{action}'."

    if action in ("CLEAR_DATASET", "DROP_DATASET") and user_role not in ("ADMIN",):
        return True, f"Only ADMIN role can clear datasets."

    return False, ""
