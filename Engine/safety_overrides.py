"""
TestSphere AI — Safety Overrides
================================
Implements six explicit safety override conditions (RULE_1–RULE_6) that take
absolute precedence over the numerical risk score.

Design principle: Safety > Speed. When uncertain → RUN.

If ANY override condition fires for a test, the decision MUST be RUN,
regardless of what the risk score says. There is no way for a score to
override a safety condition — the override list is evaluated first in
Engine/test_selector.py.

RULE_7 (structural) is NOT evaluated here. It is enforced by
Engine/test_selector.py: every SKIP must carry a non-empty rationale string
or it is treated as a system error. RULE_7 does not independently force RUN;
it is a correctness constraint that prevents silent, unexplained skips.
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
    Evaluate all six explicit safety override conditions for a given test.

    Returns a list of triggered SafetyOverride objects.
    CALLER CONTRACT: If the returned list is non-empty, the decision MUST be
    RUN — regardless of the numerical risk score. Safety overrides are never
    optional.

    Parameters
    ----------
    test                  : Test record dict (must include 'module',
                            'is_security_critical', optionally 'evidence').
    dep_info_available    : False when the dependency graph cannot be queried
                            (e.g. graph not built or file not in graph).
    coverage_info_available: False when the coverage map returns no data.
    failure_data_available: False when the failure_history table is empty
                            or unreachable for the affected modules.
    confidence_level      : 'HIGH' | 'MEDIUM' | 'LOW' — computed by
                            determine_confidence() before calling this function.

    Note: RULE_7 (rationale enforcement) is structural and NOT evaluated here.
    It lives in Engine/test_selector.py and applies to SKIP outputs only.
    """
    overrides: list[SafetyOverride] = []
    module = test.get("module", "")
    is_security_critical = bool(test.get("is_security_critical", 0))

    # ── RULE_1: Unknown dependency → RUN ────────────────────────────────────
    # WHY: If the dependency graph is unavailable, we cannot determine which
    # tests are truly unaffected by the change. Skipping without this knowledge
    # risks a false negative (missed regression). The safe default is to RUN.
    if not dep_info_available and FORCE_RUN_UNKNOWN_DEP:
        overrides.append(SafetyOverride(
            rule_id="RULE_1_UNKNOWN_DEPENDENCY",
            reason="Dependency information is unavailable. The system applies the safe RUN behavior.",
            badge="SAFE DEFAULT: UNKNOWN DEPENDENCY → RUN",
        ))

    # ── RULE_2: Unknown coverage → RUN ──────────────────────────────────────
    # WHY: Without a coverage map we cannot tell whether a test exercises any
    # of the changed source files. An unmapped test is conservatively treated
    # as potentially affected, so we force RUN rather than silently skip it.
    if not coverage_info_available and FORCE_RUN_UNKNOWN_COV:
        overrides.append(SafetyOverride(
            rule_id="RULE_2_UNKNOWN_COVERAGE",
            reason="Coverage information is unavailable. The system applies the safe RUN behavior.",
            badge="SAFE DEFAULT: UNKNOWN COVERAGE → RUN",
        ))

    # ── RULE_3: Security-critical test → always RUN ─────────────────────────
    # WHY: Tests marked is_security_critical cover authentication, OTP, payment
    # authorisation, or fraud detection flows. A false negative here can result
    # in a security vulnerability reaching production. Cost of running > cost
    # of skipping in this category, always.
    if is_security_critical and FORCE_RUN_SECURITY:
        overrides.append(SafetyOverride(
            rule_id="RULE_3_SECURITY_CRITICAL",
            reason="This test is marked security-critical. Security-critical tests always run.",
            badge="SECURITY CRITICAL → RUN",
        ))

    # ── RULE_4a: Direct file modification → RUN ─────────────────────────────
    # WHY: If a test directly exercises a modified source file, the relationship
    # between the change and the test is immediate and certain. Numerical scoring
    # adds +40 for this, but a score <50 is still possible for non-critical,
    # low-failure, standard-device tests. RULE_4 eliminates that false-negative
    # gap by forcing RUN unconditionally whenever the test has direct coverage.
    # This is general: it checks the flag and evidence strings, never hardcodes
    # specific test IDs or change IDs.
    is_direct_coverage = (
        test.get("is_direct_coverage", False) or
        any("Direct coverage" in ev for ev in test.get("evidence", []))
    )
    if is_direct_coverage:
        overrides.append(SafetyOverride(
            rule_id="RULE_4_DIRECT_FILE_MODIFICATION",
            reason="Test directly covers a modified file. Direct code changes mandate test execution.",
            badge="DIRECT FILE MODIFICATION → RUN",
        ))

    # ── RULE_4b: Critical banking module → RUN ──────────────────────────────
    # WHY: Modules like Authentication, Payment, OTP, and FraudDetection carry
    # regulatory and financial risk. A defect escaping these modules could cause
    # direct customer harm. The CRITICAL_MODULES set is loaded from config.json
    # (safety_overrides.force_run_high_risk_modules) so it is configurable
    # without code changes.
    if module in CRITICAL_MODULES:
        overrides.append(SafetyOverride(
            rule_id="RULE_4_CRITICAL_MODULE",
            reason=f"Module '{module}' is a critical banking module (Authentication/Payment/OTP/etc). Prefer RUN.",
            badge=f"CRITICAL MODULE ({module}) → RUN",
        ))

    # ── RULE_5: No failure data → RUN ───────────────────────────────────────
    # WHY: Historical failure frequency is one of the seven scoring dimensions.
    # If that data is absent (empty table or DB unreachable), the score is
    # underestimated — the absence of evidence is not evidence of absence.
    # We cannot assume the test has never failed, so we must RUN.
    if not failure_data_available:
        overrides.append(SafetyOverride(
            rule_id="RULE_5_NO_FAILURE_DATA",
            reason="Historical failure data is unavailable. The system cannot assume this test is safe to skip.",
            badge="SAFE DEFAULT: NO FAILURE DATA → RUN",
        ))

    # ── RULE_6: Low confidence → RUN ────────────────────────────────────────
    # WHY: Confidence is LOW when score < 50 AND evidence count is 0. In this
    # state the system has no measurable signal that the test is unaffected.
    # A SKIP without supporting evidence would be a silent risk. RULE_6 makes
    # the safety-first philosophy explicit: if we cannot explain why it is safe
    # to skip, we run.
    if confidence_level == "LOW":
        overrides.append(SafetyOverride(
            rule_id="RULE_6_LOW_CONFIDENCE",
            reason="The system has insufficient evidence to justify a SKIP decision. Defaulting to RUN.",
            badge="LOW CONFIDENCE → RUN",
        ))

    # ── RULE_7 note ──────────────────────────────────────────────────────────
    # RULE_7_NEVER_SKIP_WITHOUT_RATIONALE is NOT evaluated here.
    # It is a structural correctness constraint enforced in Engine/test_selector.py:
    # any SKIP decision that does not carry a populated rationale string is
    # treated as a system error. RULE_7 does not produce a SafetyOverride object
    # and does not independently force RUN — it validates SKIP outputs only.

    return overrides


def determine_confidence(score: int, evidence: list[str]) -> str:
    """
    Deterministic confidence level based on evidence count and score.

    WHY these thresholds:
      HIGH   — 3+ independent evidence sources AND score ≥ 70: multiple
               orthogonal signals all agree the test is affected. A SKIP at
               this confidence level would require very clear contrary evidence.
      MEDIUM — 1-2 sources OR score 50-69: some evidence but not conclusive;
               the threshold check in test_selector still determines RUN/SKIP.
      LOW    — 0 sources AND score < 50: the system has no measurable signal;
               RULE_6 will force RUN at this confidence level.

    Note: LOW confidence cascades directly into RULE_6_LOW_CONFIDENCE in
    evaluate_safety_overrides(), making the confidence → override path explicit.
    """
    evidence_count = len(evidence)
    if evidence_count >= 3 and score >= 70:
        return "HIGH"
    elif evidence_count >= 1 or score >= 50:
        return "MEDIUM"
    else:
        return "LOW"
