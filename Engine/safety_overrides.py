"""
TestSphere AI — Safety Overrides
Implements the 7 explicit safety rules that take precedence over scoring.
Safety > Speed. When uncertain → RUN.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_BASE = Path(__file__).resolve().parent.parent
with open(_BASE / "config.json") as _f:
    _CFG = json.load(_f)

CRITICAL_MODULES: set[str] = set(_CFG["safety_overrides"]["force_run_high_risk_modules"])
FORCE_RUN_UNKNOWN_DEP: bool    = _CFG["safety_overrides"]["force_run_on_unknown_dependency"]
FORCE_RUN_UNKNOWN_COV: bool    = _CFG["safety_overrides"]["force_run_on_unknown_coverage"]
FORCE_RUN_SECURITY: bool       = _CFG["safety_overrides"]["force_run_security_critical"]


class SafetyOverride:
    """Represents an active safety override that forces a RUN decision."""
    def __init__(self, rule_id: str, reason: str, badge: str = "SAFE DEFAULT ACTIVE"):
        self.rule_id = rule_id
        self.reason = reason
        self.badge = badge

    def to_dict(self) -> dict:
        return {"rule_id": self.rule_id, "reason": self.reason, "badge": self.badge}


def evaluate_safety_overrides(
    test: dict,
    dep_info_available: bool,
    coverage_info_available: bool,
    failure_data_available: bool,
    confidence_level: str,
) -> list[SafetyOverride]:
    """
    Evaluate all 7 safety rules for a given test.
    Returns a list of triggered SafetyOverride objects.
    If any SafetyOverride is returned, the decision MUST be RUN.
    """
    overrides: list[SafetyOverride] = []
    module = test.get("module", "")
    is_security_critical = bool(test.get("is_security_critical", 0))

    # Rule 1: Unknown dependency → RUN
    if not dep_info_available and FORCE_RUN_UNKNOWN_DEP:
        overrides.append(SafetyOverride(
            rule_id="RULE_1_UNKNOWN_DEPENDENCY",
            reason="Dependency information is unavailable. The system applies the safe RUN behavior.",
            badge="SAFE DEFAULT: UNKNOWN DEPENDENCY → RUN",
        ))

    # Rule 2: Unknown coverage → RUN
    if not coverage_info_available and FORCE_RUN_UNKNOWN_COV:
        overrides.append(SafetyOverride(
            rule_id="RULE_2_UNKNOWN_COVERAGE",
            reason="Coverage information is unavailable. The system applies the safe RUN behavior.",
            badge="SAFE DEFAULT: UNKNOWN COVERAGE → RUN",
        ))

    # Rule 3: Security-critical test → always RUN
    if is_security_critical and FORCE_RUN_SECURITY:
        overrides.append(SafetyOverride(
            rule_id="RULE_3_SECURITY_CRITICAL",
            reason="This test is marked security-critical. Security-critical tests always run.",
            badge="SECURITY CRITICAL → RUN",
        ))

    # Rule 4: Critical banking module → prefer RUN
    if module in CRITICAL_MODULES:
        overrides.append(SafetyOverride(
            rule_id="RULE_4_CRITICAL_MODULE",
            reason=f"Module '{module}' is a critical banking module (Authentication/Payment/OTP/etc). Prefer RUN.",
            badge=f"CRITICAL MODULE ({module}) → RUN",
        ))

    # Rule 5: No failure data → do not assume safe
    if not failure_data_available:
        overrides.append(SafetyOverride(
            rule_id="RULE_5_NO_FAILURE_DATA",
            reason="Historical failure data is unavailable. The system cannot assume this test is safe to skip.",
            badge="SAFE DEFAULT: NO FAILURE DATA → RUN",
        ))

    # Rule 6: Low confidence + cannot explain skip → RUN
    if confidence_level == "LOW":
        overrides.append(SafetyOverride(
            rule_id="RULE_6_LOW_CONFIDENCE",
            reason="The system has insufficient evidence to justify a SKIP decision. Defaulting to RUN.",
            badge="LOW CONFIDENCE → RUN",
        ))

    # Rule 7: Never silently skip — this is enforced in test_selector, not here
    # (Rule 7 is structural: rationale is required for every SKIP)

    return overrides


def determine_confidence(score: int, evidence: list[str]) -> str:
    """
    Deterministic confidence level based on evidence count and score.
      HIGH   — 3+ evidence sources, score ≥ 70
      MEDIUM — 1-2 sources OR score 50-69
      LOW    — 0 sources OR score < 50
    """
    evidence_count = len(evidence)
    if evidence_count >= 3 and score >= 70:
        return "HIGH"
    elif evidence_count >= 1 or score >= 50:
        return "MEDIUM"
    else:
        return "LOW"
