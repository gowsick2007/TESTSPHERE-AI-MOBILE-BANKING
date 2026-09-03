"""
TestSphere AI — Change Analyzer
Maps changed files to affected modules and retrieves relevant change context.
"""
import json
import logging
from pathlib import Path
from typing import Optional
from Engine.data_access import get_all_changes, get_changes_by_file, get_device_matrix

logger = logging.getLogger(__name__)

_BASE = Path(__file__).resolve().parent.parent
with open(_BASE / "config.json") as _f:
    _CONFIG = json.load(_f)

CRITICAL_MODULES: set[str] = set(_CONFIG["safety_overrides"]["force_run_high_risk_modules"])


def analyze_change(
    changed_files: list[str],
    change_type: str = "MODIFIED",
    module: Optional[str] = None,
    is_security_sensitive: bool = False,
    risk_level: str = "MEDIUM",
) -> dict:
    """
    Analyze a set of changed files and return structured impact context.

    Returns:
        dict with keys: changed_files, affected_modules, is_security_sensitive,
                        is_critical, risk_level, change_type, file_module_map
    """
    if not changed_files:
        logger.warning("No changed files provided — defaulting to safe RUN behavior")
        return _empty_analysis()

    # Resolve module from file paths if not provided
    file_module_map: dict[str, str] = {}
    affected_modules: set[str] = set()

    all_changes_db = get_all_changes()
    # Build a file→module lookup from DB records
    db_file_module: dict[str, str] = {c["file_path"]: c["module"] for c in all_changes_db}

    for fp in changed_files:
        fp_clean = fp.strip()
        if module:
            file_module_map[fp_clean] = module
            affected_modules.add(module)
        elif fp_clean in db_file_module:
            m = db_file_module[fp_clean]
            file_module_map[fp_clean] = m
            affected_modules.add(m)
        else:
            # Infer from file path segments
            inferred = _infer_module_from_path(fp_clean)
            file_module_map[fp_clean] = inferred
            affected_modules.add(inferred)

    # Determine if any critical module is affected
    is_critical = bool(affected_modules & CRITICAL_MODULES)

    # Override security sensitivity for critical modules
    if is_critical and change_type == "SECURITY_PATCH":
        is_security_sensitive = True

    # Escalate risk if critical
    if is_critical and risk_level == "LOW":
        risk_level = "MEDIUM"

    return {
        "changed_files": changed_files,
        "affected_modules": list(affected_modules),
        "is_security_sensitive": is_security_sensitive,
        "is_critical": is_critical,
        "risk_level": risk_level,
        "change_type": change_type,
        "file_module_map": file_module_map,
        "critical_modules_hit": list(affected_modules & CRITICAL_MODULES),
    }


def _infer_module_from_path(file_path: str) -> str:
    """Best-effort module inference from file path segments."""
    path_lower = file_path.lower().replace("\\", "/")
    mappings = [
        ("auth",         "Authentication"),
        ("otp",          "OTP"),
        ("payment",      "Payment"),
        ("upi",          "UPI"),
        ("transaction",  "Transaction"),
        ("account",      "Account"),
        ("profile",      "Profile"),
        ("notification", "Notification"),
        ("fraud",        "FraudDetection"),
        ("dashboard",    "Dashboard"),
        ("device",       "DeviceSecurity"),
        ("biometric",    "Biometrics"),
        ("support",      "CustomerSupport"),
    ]
    for keyword, module in mappings:
        if keyword in path_lower:
            return module
    return "Unknown"


def _empty_analysis() -> dict:
    return {
        "changed_files": [],
        "affected_modules": [],
        "is_security_sensitive": False,
        "is_critical": False,
        "risk_level": "UNKNOWN",
        "change_type": "UNKNOWN",
        "file_module_map": {},
        "critical_modules_hit": [],
    }


def get_change_summary(change_id: str) -> Optional[dict]:
    """Return a specific change from the database for display."""
    changes = get_all_changes()
    for c in changes:
        if c["change_id"] == change_id:
            return c
    return None


def get_recent_changes(limit: int = 10) -> list[dict]:
    """Return the most recent code changes."""
    return get_all_changes()[:limit]
