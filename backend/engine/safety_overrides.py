"""
TestSphere AI — Safety Overrides
Checks system safety rules. When uncertain or critical module is altered, enforce RUN.
"""
from typing import List, Dict, Any
from backend.config import CONFIG

CRITICAL_MODULES = set(CONFIG["safety_overrides"]["force_run_high_risk_modules"])
FORCE_RUN_UNKNOWN_DEP = CONFIG["safety_overrides"]["force_run_on_unknown_dependency"]
FORCE_RUN_UNKNOWN_COV = CONFIG["safety_overrides"]["force_run_on_unknown_coverage"]
FORCE_RUN_SECURITY    = CONFIG["safety_overrides"]["force_run_security_critical"]


class SafetyOverride:
    """Triggered safety rule details."""
    def __init__(self, rule_id: str, reason: str, badge: str = "SAFE DEFAULT ACTIVE"):
        self.rule_id = rule_id
        self.reason = reason
        self.badge = badge

    def to_dict(self) -> Dict[str, str]:
        return {"rule_id": self.rule_id, "reason": self.reason, "badge": self.badge}


def evaluate_safety_overrides(
    test: Dict[str, Any],
    dep_info_available: bool,
    coverage_info_available: bool,
    failure_data_available: bool,
    confidence_level: str,
) -> List[SafetyOverride]:
    """
    Evaluates safety overrides for a given test.
    If any override triggers, decision must be RUN.
    """
    overrides: List[SafetyOverride] = []
    module = test.get("module", "")
    is_security_critical = bool(test.get("is_security_critical", 0))

    # Rule 1: Unknown Dependency graph
    if not dep_info_available and FORCE_RUN_UNKNOWN_DEP:
        overrides.append(SafetyOverride(
            rule_id="RULE_1_UNKNOWN_DEPENDENCY",
            reason="Dependency information is unavailable. Safe default RUN applied.",
            badge="SAFE DEFAULT: UNKNOWN DEPENDENCY ➔ RUN"
        ))

    # Rule 2: Unknown Coverage paths
    if not coverage_info_available and FORCE_RUN_UNKNOWN_COV:
        overrides.append(SafetyOverride(
            rule_id="RULE_2_UNKNOWN_COVERAGE",
            reason="Coverage map is unavailable or could not be verified. Safe default RUN applied.",
            badge="SAFE DEFAULT: UNKNOWN COVERAGE ➔ RUN"
        ))

    # Rule 3: Security-critical classification
    if is_security_critical and FORCE_RUN_SECURITY:
        overrides.append(SafetyOverride(
            rule_id="RULE_3_SECURITY_CRITICAL",
            reason="This test is marked as security-critical. Security regression tests are mandated to run.",
            badge="SECURITY CRITICAL ➔ RUN"
        ))

    # Rule 4: Critical module touched (Payment, Authentication, etc.)
    if module in CRITICAL_MODULES:
        overrides.append(SafetyOverride(
            rule_id="RULE_4_CRITICAL_MODULE",
            reason=f"Module '{module}' is a critical banking area. Mandated regression coverage applied.",
            badge=f"CRITICAL MODULE ({module}) ➔ RUN"
        ))

    # Rule 5: Missing historical failure data
    if not failure_data_available:
        overrides.append(SafetyOverride(
            rule_id="RULE_5_NO_FAILURE_DATA",
            reason="Failure history archives are empty. System cannot verify skipped test safety.",
            badge="SAFE DEFAULT: NO FAILURE DATA ➔ RUN"
        ))

    # Rule 6: Low selector confidence
    if confidence_level == "LOW":
        overrides.append(SafetyOverride(
            rule_id="RULE_6_LOW_CONFIDENCE",
            reason="Decision engine confidence is LOW. Safe default RUN applied.",
            badge="LOW CONFIDENCE ➔ RUN"
        ))

    return overrides


def determine_confidence(score: int, evidence: List[str]) -> str:
    """
    Computes selection decision confidence.
    """
    evidence_count = len(evidence)
    if evidence_count >= 3 and score >= 70:
        return "HIGH"
    elif evidence_count >= 1 or score >= 50:
        return "MEDIUM"
    else:
        return "LOW"
