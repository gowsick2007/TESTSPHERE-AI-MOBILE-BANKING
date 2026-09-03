"""
TestSphere AI — Risk Scorer
Deterministic, rule-based risk scoring engine.
No ML. No LLM. Transparent additive scoring only.
"""
import json
import logging
from pathlib import Path
from Engine.device_risk_analyzer import get_device_risk_score, is_high_risk_device
from Engine.failure_analyzer import is_recently_failed

logger = logging.getLogger(__name__)

_BASE = Path(__file__).resolve().parent.parent
with open(_BASE / "config.json") as _f:
    _CFG = json.load(_f)

_SCORING = _CFG["risk_scoring"]
CRITICAL_MODULES: set[str] = set(_CFG["safety_overrides"]["force_run_high_risk_modules"])

# Score contributions (all additive, transparent)
SCORE_DIRECT_COVERAGE     = _SCORING["direct_coverage"]          # +40
SCORE_DEPENDENCY          = _SCORING["dependency_relationship"]  # +30
SCORE_HISTORICAL_FAILURE  = _SCORING["historical_failure"]       # +20
SCORE_HIGH_RISK_DEVICE    = _SCORING["high_risk_device"]         # +10
SCORE_SECURITY_MODULE     = _SCORING["security_sensitive_module"]# +30
SCORE_CRITICAL_BANKING    = _SCORING["critical_banking_module"]  # +25
SCORE_RECENT_FAILURE      = _SCORING["recent_failure"]           # +15
RUN_THRESHOLD             = _SCORING["run_threshold"]            # >= 50 → RUN


def compute_risk_score(
    test: dict,
    covered_test_ids: set[str],
    dependency_test_ids: set[str],
    failure_associated_ids: set[str],
    is_security_sensitive: bool,
    affected_modules: list[str],
    failed_ids: set[str] | None = None,
    device_risks: dict | None = None,
) -> tuple[int, list[str]]:
    """
    Compute the deterministic risk score for a single test.

    Returns:
        (score: int, evidence: list[str])
    """
    score = 0
    evidence: list[str] = []
    test_id = test["test_id"]
    module = test.get("module", "")
    device = test.get("device", "")
    os_ver = test.get("os_version", "")

    # Direct coverage of changed file
    if test_id in covered_test_ids:
        score += SCORE_DIRECT_COVERAGE
        evidence.append(f"Direct coverage of changed file (+{SCORE_DIRECT_COVERAGE})")

    # Dependency relationship
    if test_id in dependency_test_ids:
        score += SCORE_DEPENDENCY
        evidence.append(f"Dependency path to changed file (+{SCORE_DEPENDENCY})")

    # Historical failure association
    if test_id in failure_associated_ids:
        score += SCORE_HISTORICAL_FAILURE
        evidence.append(f"Historical failure in affected module (+{SCORE_HISTORICAL_FAILURE})")

    # Recent failure (within 90 days)
    has_failed = (test_id in failed_ids) if failed_ids is not None else is_recently_failed(test_id)
    if has_failed:
        score += SCORE_RECENT_FAILURE
        evidence.append(f"Recent failure record (+{SCORE_RECENT_FAILURE})")

    # High-risk device
    if device_risks is not None:
        key = (device.lower(), os_ver.lower())
        risk_score = device_risks.get(key)
        if risk_score is None:
            # Fallback
            risk_score = 80 if device in {"Pixel 8", "Samsung S24", "iPhone 15"} else 20
        is_high = risk_score >= 80
    else:
        is_high = is_high_risk_device(device, os_ver)

    if is_high:
        score += SCORE_HIGH_RISK_DEVICE
        evidence.append(f"High-risk device/OS ({device} {os_ver}) (+{SCORE_HIGH_RISK_DEVICE})")

    # Security-sensitive change
    if is_security_sensitive:
        score += SCORE_SECURITY_MODULE
        evidence.append(f"Security-sensitive change (+{SCORE_SECURITY_MODULE})")

    # Critical banking module
    if module in CRITICAL_MODULES:
        score += SCORE_CRITICAL_BANKING
        evidence.append(f"Critical banking module ({module}) (+{SCORE_CRITICAL_BANKING})")

    return score, evidence


def score_all_tests(
    all_tests: list[dict],
    covered_test_ids: set[str],
    dependency_test_ids: set[str],
    failure_associated_ids: set[str],
    is_security_sensitive: bool,
    affected_modules: list[str],
) -> list[dict]:
    """
    Score all tests and return a list with score + evidence for each.
    """
    try:
        from Engine.data_access import get_failure_history
        from datetime import datetime, timedelta
        failures = get_failure_history()
        cutoff = datetime.utcnow() - timedelta(days=90)
        failed_ids = set()
        for f in failures:
            try:
                fd = datetime.fromisoformat(f["failure_date"])
                if fd >= cutoff:
                    failed_ids.add(f["test_id"])
            except (ValueError, TypeError):
                pass
    except Exception:
        failed_ids = set()

    try:
        from Engine.data_access import get_device_matrix
        matrix = get_device_matrix()
        device_risks = {}
        for d in matrix:
            key = (d["device_name"].lower(), d["os_version"].lower())
            risk = d["risk_level"].upper()
            score = 100 if risk == "CRITICAL" else (80 if risk == "HIGH" else (50 if risk == "MEDIUM" else 20))
            device_risks[key] = max(device_risks.get(key, 0), score)
    except Exception:
        device_risks = {}

    results = []
    for test in all_tests:
        score, evidence = compute_risk_score(
            test=test,
            covered_test_ids=covered_test_ids,
            dependency_test_ids=dependency_test_ids,
            failure_associated_ids=failure_associated_ids,
            is_security_sensitive=is_security_sensitive,
            affected_modules=affected_modules,
            failed_ids=failed_ids,
            device_risks=device_risks,
        )
        results.append({**test, "risk_score": score, "evidence": evidence})
    return results
