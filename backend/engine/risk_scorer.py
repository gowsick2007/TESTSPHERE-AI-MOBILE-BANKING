"""
TestSphere AI — Risk Scorer
Computes additive, transparent risk scores for individual tests.
"""
import logging
from typing import List, Dict, Any, Tuple
from backend.config import CONFIG
from backend.engine.device_risk_analyzer import is_high_risk_device
from backend.engine.failure_analyzer import is_recently_failed

logger = logging.getLogger(__name__)

# Scoring configurations (loaded from config.json)
_SCORING = CONFIG["risk_scoring"]
CRITICAL_MODULES = set(CONFIG["safety_overrides"]["force_run_high_risk_modules"])

SCORE_DIRECT_COVERAGE      = _SCORING["direct_coverage"]
SCORE_DEPENDENCY           = _SCORING["dependency_relationship"]
SCORE_HISTORICAL_FAILURE   = _SCORING["historical_failure"]
SCORE_HIGH_RISK_DEVICE     = _SCORING["high_risk_device"]
SCORE_SECURITY_MODULE      = _SCORING["security_sensitive_module"]
SCORE_CRITICAL_BANKING     = _SCORING["critical_banking_module"]
SCORE_RECENT_FAILURE       = _SCORING["recent_failure"]
RUN_THRESHOLD              = _SCORING["run_threshold"]


HIGH_RISK_DEVICES = set(CONFIG.get("devices", {}).get("high_risk", []))

def compute_risk_score(
    test: Dict[str, Any],
    covered_test_ids: set,
    dependency_test_ids: set,
    failure_associated_ids: set,
    is_security_sensitive: bool,
    affected_modules: List[str],
    failed_ids: set | None = None,
    device_risks: dict | None = None,
) -> Tuple[int, List[str]]:
    """
    Computes additive risk score based on rule weights.
    Returns:
        (score, evidence_list)
    """
    score = 0
    evidence: List[str] = []
    test_id = test["test_id"]
    module = test.get("module", "")
    device = test.get("device", "")
    os_ver = test.get("os_version", "")

    # 1. Direct coverage
    if test_id in covered_test_ids:
        score += SCORE_DIRECT_COVERAGE
        evidence.append(f"Direct coverage of changed file (+{SCORE_DIRECT_COVERAGE})")

    # 2. Dependency path
    if test_id in dependency_test_ids:
        score += SCORE_DEPENDENCY
        evidence.append(f"Dependency path to changed file (+{SCORE_DEPENDENCY})")

    # 3. Historical failure association (same module)
    if test_id in failure_associated_ids:
        score += SCORE_HISTORICAL_FAILURE
        evidence.append(f"Historical failure in affected module (+{SCORE_HISTORICAL_FAILURE})")

    # 4. Recent failure record
    has_failed = (test_id in failed_ids) if failed_ids is not None else is_recently_failed(test_id)
    if has_failed:
        score += SCORE_RECENT_FAILURE
        evidence.append(f"Recent failure record (+{SCORE_RECENT_FAILURE})")

    # 5. High-risk device OS combination
    if device_risks is not None:
        key = (device.lower(), os_ver.lower())
        risk_score = device_risks.get(key)
        if risk_score is None:
            # Fallback to config constants
            risk_score = 80 if device in HIGH_RISK_DEVICES else 20
        is_high = risk_score >= 80
    else:
        is_high = is_high_risk_device(device, os_ver)

    if is_high:
        score += SCORE_HIGH_RISK_DEVICE
        evidence.append(f"High-risk device/OS ({device} {os_ver}) (+{SCORE_HIGH_RISK_DEVICE})")

    # 6. Security sensitive change
    if is_security_sensitive:
        score += SCORE_SECURITY_MODULE
        evidence.append(f"Security-sensitive change (+{SCORE_SECURITY_MODULE})")

    # 7. Critical banking module
    if module in CRITICAL_MODULES:
        score += SCORE_CRITICAL_BANKING
        evidence.append(f"Critical banking module ({module}) (+{SCORE_CRITICAL_BANKING})")

    return score, evidence


def score_all_tests(
    all_tests: List[Dict[str, Any]],
    covered_test_ids: set,
    dependency_test_ids: set,
    failure_associated_ids: set,
    is_security_sensitive: bool,
    affected_modules: List[str],
) -> List[Dict[str, Any]]:
    """Scores all test specifications."""
    from backend.engine.data_access import get_all_failures, get_device_matrix

    try:
        failures = get_all_failures()
        failed_ids = {f["test_id"] for f in failures}
    except Exception:
        failed_ids = set()

    try:
        matrix = get_device_matrix()
        device_risks = {}
        for d in matrix:
            key = (d["device_name"].lower(), d["os_version"].lower())
            risk = d["risk_level"].upper()
            score = 100 if risk == "CRITICAL" else (80 if risk == "HIGH" else (50 if risk == "MEDIUM" else 20))
            device_risks[key] = max(device_risks.get(key, 0), score)
    except Exception:
        device_risks = {}

    res = []
    for t in all_tests:
        score, evidence = compute_risk_score(
            test=t,
            covered_test_ids=covered_test_ids,
            dependency_test_ids=dependency_test_ids,
            failure_associated_ids=failure_associated_ids,
            is_security_sensitive=is_security_sensitive,
            affected_modules=affected_modules,
            failed_ids=failed_ids,
            device_risks=device_risks,
        )
        res.append({**t, "risk_score": score, "evidence": evidence})
    return res
