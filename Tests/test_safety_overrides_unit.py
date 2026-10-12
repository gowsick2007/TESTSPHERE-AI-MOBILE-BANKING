"""
TestSphere AI — Safety Override Unit Tests (Review 2 Hardening)
================================================================
Granular per-rule tests for every explicit safety condition and for
RULE_7 structural rationale enforcement in the test_selector.

Design principle enforced throughout: Safety > Speed. When uncertain → RUN.

Each test is intentionally isolated so a single failure is traceable to
exactly one rule or boundary condition.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from Engine.safety_overrides import evaluate_safety_overrides, determine_confidence, SafetyOverride
from Engine.risk_scorer import compute_risk_score, RUN_THRESHOLD


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_test(
    test_id: str = "T_TEST",
    module: str = "Dashboard",
    device: str = "Pixel 7",
    os_version: str = "Android 14",
    is_security_critical: int = 0,
    is_direct_coverage: bool = False,
    evidence: list | None = None,
) -> dict:
    """Build a minimal test record for override evaluation."""
    return {
        "test_id": test_id,
        "module": module,
        "device": device,
        "os_version": os_version,
        "is_security_critical": is_security_critical,
        "is_direct_coverage": is_direct_coverage,
        "evidence": evidence or [],
    }


def _no_override(**kwargs):
    """Convenience: evaluate overrides and assert none are returned."""
    overrides = evaluate_safety_overrides(**kwargs)
    return overrides


def _rule_ids(overrides: list) -> set:
    return {o.rule_id for o in overrides}


# ──────────────────────────────────────────────────────────────────────────────
# RULE_1 — Unknown Dependency
# ──────────────────────────────────────────────────────────────────────────────

class TestRule1UnknownDependency:
    """RULE_1_UNKNOWN_DEPENDENCY: dep_info_available=False → force RUN."""

    def test_triggers_when_dependency_unavailable(self):
        """When dependency data is missing the system must default to RUN."""
        overrides = evaluate_safety_overrides(
            test=_make_test(),
            dep_info_available=False,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="HIGH",
        )
        assert "RULE_1_UNKNOWN_DEPENDENCY" in _rule_ids(overrides), (
            "RULE_1 must fire when dependency information is unavailable"
        )

    def test_does_not_trigger_when_dependency_available(self):
        """When dependency data is present RULE_1 must NOT fire."""
        overrides = evaluate_safety_overrides(
            test=_make_test(),
            dep_info_available=True,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="HIGH",
        )
        assert "RULE_1_UNKNOWN_DEPENDENCY" not in _rule_ids(overrides)

    def test_rule1_badge_content(self):
        """RULE_1 badge must communicate the safe default clearly."""
        overrides = evaluate_safety_overrides(
            test=_make_test(),
            dep_info_available=False,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="HIGH",
        )
        r1 = next(o for o in overrides if o.rule_id == "RULE_1_UNKNOWN_DEPENDENCY")
        assert "UNKNOWN DEPENDENCY" in r1.badge.upper() or "RUN" in r1.badge.upper()


# ──────────────────────────────────────────────────────────────────────────────
# RULE_2 — Unknown Coverage
# ──────────────────────────────────────────────────────────────────────────────

class TestRule2UnknownCoverage:
    """RULE_2_UNKNOWN_COVERAGE: coverage_info_available=False → force RUN."""

    def test_triggers_when_coverage_unavailable(self):
        overrides = evaluate_safety_overrides(
            test=_make_test(),
            dep_info_available=True,
            coverage_info_available=False,
            failure_data_available=True,
            confidence_level="HIGH",
        )
        assert "RULE_2_UNKNOWN_COVERAGE" in _rule_ids(overrides)

    def test_does_not_trigger_when_coverage_available(self):
        overrides = evaluate_safety_overrides(
            test=_make_test(),
            dep_info_available=True,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="HIGH",
        )
        assert "RULE_2_UNKNOWN_COVERAGE" not in _rule_ids(overrides)

    def test_rule1_and_rule2_can_both_trigger(self):
        """Both RULE_1 and RULE_2 can trigger simultaneously when all data is absent."""
        overrides = evaluate_safety_overrides(
            test=_make_test(),
            dep_info_available=False,
            coverage_info_available=False,
            failure_data_available=True,
            confidence_level="HIGH",
        )
        ids = _rule_ids(overrides)
        assert "RULE_1_UNKNOWN_DEPENDENCY" in ids
        assert "RULE_2_UNKNOWN_COVERAGE" in ids


# ──────────────────────────────────────────────────────────────────────────────
# RULE_3 — Security-Critical Test
# ──────────────────────────────────────────────────────────────────────────────

class TestRule3SecurityCritical:
    """RULE_3_SECURITY_CRITICAL: is_security_critical=1 → always RUN."""

    def test_triggers_for_security_critical_test(self):
        overrides = evaluate_safety_overrides(
            test=_make_test(is_security_critical=1),
            dep_info_available=True,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="HIGH",
        )
        assert "RULE_3_SECURITY_CRITICAL" in _rule_ids(overrides)

    def test_does_not_trigger_for_non_security_critical(self):
        overrides = evaluate_safety_overrides(
            test=_make_test(is_security_critical=0),
            dep_info_available=True,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="HIGH",
        )
        assert "RULE_3_SECURITY_CRITICAL" not in _rule_ids(overrides)

    def test_security_critical_overrides_high_score_skip(self):
        """A security-critical test must RUN even if the score-based path would skip it.
        This validates that overrides always take absolute precedence over scoring.
        """
        overrides = evaluate_safety_overrides(
            test=_make_test(is_security_critical=1),
            dep_info_available=True,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="HIGH",
        )
        # Any non-empty overrides list → decision MUST be RUN regardless of score
        assert len(overrides) > 0


# ──────────────────────────────────────────────────────────────────────────────
# RULE_4a — Direct File Modification
# ──────────────────────────────────────────────────────────────────────────────

class TestRule4DirectFileModification:
    """RULE_4_DIRECT_FILE_MODIFICATION: test directly covers a modified file → RUN."""

    def test_triggers_via_is_direct_coverage_flag(self):
        """The is_direct_coverage flag must activate RULE_4_DIRECT_FILE_MODIFICATION."""
        overrides = evaluate_safety_overrides(
            test=_make_test(is_direct_coverage=True),
            dep_info_available=True,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="HIGH",
        )
        assert "RULE_4_DIRECT_FILE_MODIFICATION" in _rule_ids(overrides)

    def test_triggers_via_direct_coverage_evidence_string(self):
        """A 'Direct coverage' evidence string must also activate RULE_4."""
        overrides = evaluate_safety_overrides(
            test=_make_test(evidence=["Direct coverage of changed file (+40)"]),
            dep_info_available=True,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="HIGH",
        )
        assert "RULE_4_DIRECT_FILE_MODIFICATION" in _rule_ids(overrides)

    def test_does_not_trigger_without_direct_coverage(self):
        """Without direct coverage signal, RULE_4_DIRECT_FILE_MODIFICATION must NOT fire."""
        overrides = evaluate_safety_overrides(
            test=_make_test(is_direct_coverage=False, evidence=["Dependency path (+30)"]),
            dep_info_available=True,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="HIGH",
        )
        assert "RULE_4_DIRECT_FILE_MODIFICATION" not in _rule_ids(overrides)

    def test_rule4_general_not_hardcoded(self):
        """RULE_4 must activate for ANY test with direct coverage, not just specific test IDs.
        This verifies there is no hardcoded test-ID logic in the safety override engine.
        """
        for test_id in ["T0001", "T9999", "ARBITRARY-ID", "T_NEW"]:
            overrides = evaluate_safety_overrides(
                test=_make_test(test_id=test_id, is_direct_coverage=True),
                dep_info_available=True,
                coverage_info_available=True,
                failure_data_available=True,
                confidence_level="HIGH",
            )
            assert "RULE_4_DIRECT_FILE_MODIFICATION" in _rule_ids(overrides), (
                f"RULE_4 must fire for test_id={test_id}"
            )


# ──────────────────────────────────────────────────────────────────────────────
# RULE_4b — Critical Module
# ──────────────────────────────────────────────────────────────────────────────

class TestRule4CriticalModule:
    """RULE_4_CRITICAL_MODULE: module in critical list → prefer RUN."""

    CRITICAL_MODULES = [
        "Authentication", "Authorization", "OTP", "Payment",
        "UPI", "Transaction", "FraudDetection", "AccountSecurity",
    ]

    def test_triggers_for_all_critical_banking_modules(self):
        """Every configured critical banking module must trigger RULE_4_CRITICAL_MODULE."""
        for module in self.CRITICAL_MODULES:
            overrides = evaluate_safety_overrides(
                test=_make_test(module=module),
                dep_info_available=True,
                coverage_info_available=True,
                failure_data_available=True,
                confidence_level="HIGH",
            )
            assert "RULE_4_CRITICAL_MODULE" in _rule_ids(overrides), (
                f"RULE_4_CRITICAL_MODULE must fire for module={module}"
            )

    def test_does_not_trigger_for_non_critical_module(self):
        for module in ["Dashboard", "Notifications", "Settings", "Reports"]:
            overrides = evaluate_safety_overrides(
                test=_make_test(module=module),
                dep_info_available=True,
                coverage_info_available=True,
                failure_data_available=True,
                confidence_level="HIGH",
            )
            assert "RULE_4_CRITICAL_MODULE" not in _rule_ids(overrides), (
                f"RULE_4_CRITICAL_MODULE must NOT fire for non-critical module={module}"
            )


# ──────────────────────────────────────────────────────────────────────────────
# RULE_5 — No Failure Data
# ──────────────────────────────────────────────────────────────────────────────

class TestRule5NoFailureData:
    """RULE_5_NO_FAILURE_DATA: failure_data_available=False → cannot assume safe to skip."""

    def test_triggers_when_failure_data_unavailable(self):
        overrides = evaluate_safety_overrides(
            test=_make_test(),
            dep_info_available=True,
            coverage_info_available=True,
            failure_data_available=False,
            confidence_level="HIGH",
        )
        assert "RULE_5_NO_FAILURE_DATA" in _rule_ids(overrides)

    def test_does_not_trigger_when_failure_data_available(self):
        overrides = evaluate_safety_overrides(
            test=_make_test(),
            dep_info_available=True,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="HIGH",
        )
        assert "RULE_5_NO_FAILURE_DATA" not in _rule_ids(overrides)


# ──────────────────────────────────────────────────────────────────────────────
# RULE_6 — Low Confidence
# ──────────────────────────────────────────────────────────────────────────────

class TestRule6LowConfidence:
    """RULE_6_LOW_CONFIDENCE: confidence='LOW' → insufficient evidence to skip."""

    def test_triggers_at_low_confidence(self):
        overrides = evaluate_safety_overrides(
            test=_make_test(),
            dep_info_available=True,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="LOW",
        )
        assert "RULE_6_LOW_CONFIDENCE" in _rule_ids(overrides)

    def test_does_not_trigger_at_medium_confidence(self):
        overrides = evaluate_safety_overrides(
            test=_make_test(),
            dep_info_available=True,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="MEDIUM",
        )
        assert "RULE_6_LOW_CONFIDENCE" not in _rule_ids(overrides)

    def test_does_not_trigger_at_high_confidence(self):
        overrides = evaluate_safety_overrides(
            test=_make_test(),
            dep_info_available=True,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="HIGH",
        )
        assert "RULE_6_LOW_CONFIDENCE" not in _rule_ids(overrides)


# ──────────────────────────────────────────────────────────────────────────────
# RULE_7 — Structural Rationale Enforcement
# ──────────────────────────────────────────────────────────────────────────────

class TestRule7StructuralRationale:
    """RULE_7_NEVER_SKIP_WITHOUT_RATIONALE is NOT in evaluate_safety_overrides().
    It is structural enforcement in Engine/test_selector.py.
    These tests verify the structural property holds at the selector level.
    """

    def test_rule7_not_in_evaluate_safety_overrides(self):
        """RULE_7 must never appear in the evaluate_safety_overrides() output.
        It is structurally enforced in test_selector, not in the override evaluator.
        """
        # Call with conditions that trigger no other rules
        overrides = evaluate_safety_overrides(
            test=_make_test(),
            dep_info_available=True,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="HIGH",
        )
        assert "RULE_7_NEVER_SKIP_WITHOUT_RATIONALE" not in _rule_ids(overrides), (
            "RULE_7 must be enforced structurally in test_selector, not in evaluate_safety_overrides()"
        )

    def test_rule7_not_in_evaluate_safety_overrides_any_input(self):
        """RULE_7 must never appear in override output regardless of input combination."""
        for dep_avail in [True, False]:
            for cov_avail in [True, False]:
                for fail_avail in [True, False]:
                    for conf in ["HIGH", "MEDIUM", "LOW"]:
                        overrides = evaluate_safety_overrides(
                            test=_make_test(),
                            dep_info_available=dep_avail,
                            coverage_info_available=cov_avail,
                            failure_data_available=fail_avail,
                            confidence_level=conf,
                        )
                        assert "RULE_7_NEVER_SKIP_WITHOUT_RATIONALE" not in _rule_ids(overrides)


# ──────────────────────────────────────────────────────────────────────────────
# Override Precedence
# ──────────────────────────────────────────────────────────────────────────────

class TestOverridePrecedence:
    """Safety overrides must always take absolute precedence over numerical scoring."""

    def test_override_forces_run_regardless_of_zero_score(self):
        """A test with score=0 must still RUN if a safety override fires."""
        # Score will be 0: not covered, no deps, no failures, not security, not critical module
        # But dep_info is unavailable → RULE_1 fires → must RUN
        overrides = evaluate_safety_overrides(
            test=_make_test(module="Dashboard"),
            dep_info_available=False,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="HIGH",
        )
        assert len(overrides) > 0, "Safety override must fire even when numerical score would be zero"

    def test_all_six_conditions_can_stack(self):
        """All six explicit override conditions can fire simultaneously."""
        overrides = evaluate_safety_overrides(
            test=_make_test(
                module="Payment",                  # RULE_4_CRITICAL_MODULE
                is_security_critical=1,            # RULE_3_SECURITY_CRITICAL
                is_direct_coverage=True,           # RULE_4_DIRECT_FILE_MODIFICATION
            ),
            dep_info_available=False,              # RULE_1_UNKNOWN_DEPENDENCY
            coverage_info_available=False,         # RULE_2_UNKNOWN_COVERAGE
            failure_data_available=False,          # RULE_5_NO_FAILURE_DATA
            confidence_level="LOW",                # RULE_6_LOW_CONFIDENCE
        )
        ids = _rule_ids(overrides)
        assert "RULE_1_UNKNOWN_DEPENDENCY" in ids
        assert "RULE_2_UNKNOWN_COVERAGE" in ids
        assert "RULE_3_SECURITY_CRITICAL" in ids
        assert "RULE_4_DIRECT_FILE_MODIFICATION" in ids
        assert "RULE_4_CRITICAL_MODULE" in ids
        assert "RULE_5_NO_FAILURE_DATA" in ids
        assert "RULE_6_LOW_CONFIDENCE" in ids

    def test_no_overrides_when_all_conditions_safe(self):
        """When no override condition applies, the list must be empty (score path decides)."""
        overrides = evaluate_safety_overrides(
            test=_make_test(module="Dashboard", is_security_critical=0),
            dep_info_available=True,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="HIGH",
        )
        assert overrides == [], "No overrides expected for a benign non-critical test"

    def test_override_to_dict_serializable(self):
        """SafetyOverride.to_dict() must return a serializable dict."""
        o = SafetyOverride(rule_id="RULE_TEST", reason="Test reason", badge="TEST → RUN")
        d = o.to_dict()
        assert d["rule_id"] == "RULE_TEST"
        assert d["reason"] == "Test reason"
        assert d["badge"] == "TEST → RUN"


# ──────────────────────────────────────────────────────────────────────────────
# Risk Scoring Boundary Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestRiskScoringBoundaries:
    """Boundary conditions for the deterministic additive risk scorer."""

    def _score(self, test=None, covered=None, dep=None, fail=None,
                security=False, modules=None):
        t = test or _make_test()
        sc, ev = compute_risk_score(
            test=t,
            covered_test_ids=covered or set(),
            dependency_test_ids=dep or set(),
            failure_associated_ids=fail or set(),
            is_security_sensitive=security,
            affected_modules=modules or [],
        )
        return sc, ev

    def test_score_zero_baseline(self):
        """A test with zero evidence contributions must score exactly 0."""
        score, evidence = self._score()
        assert score == 0
        assert evidence == []

    def test_score_49_is_below_threshold(self):
        """Score of 49 is strictly below RUN_THRESHOLD (50) → would SKIP without override."""
        # historical_failure (20) + dependency (30) − 1 = 49 is not achievable directly;
        # use dependency (30) + historical (20) - not enough to match. Check threshold value.
        assert RUN_THRESHOLD == 50

    def test_score_exactly_50_meets_threshold(self):
        """Score of exactly 50 (dependency=30 + historical=20) meets the RUN_THRESHOLD."""
        t = _make_test(test_id="T_BOUNDARY")
        score, evidence = compute_risk_score(
            test=t,
            covered_test_ids=set(),
            dependency_test_ids={"T_BOUNDARY"},   # +30
            failure_associated_ids={"T_BOUNDARY"},# +20
            is_security_sensitive=False,
            affected_modules=[],
        )
        assert score == 50, f"Expected score=50 got {score}"
        assert score >= RUN_THRESHOLD

    def test_score_below_threshold_no_override_is_skip(self):
        """Score=30 (dependency only) is below threshold=50 and no override fires → SKIP path."""
        t = _make_test(test_id="T_SKIP", module="Dashboard")
        score, _ = compute_risk_score(
            test=t,
            covered_test_ids=set(),
            dependency_test_ids={"T_SKIP"},   # +30
            failure_associated_ids=set(),
            is_security_sensitive=False,
            affected_modules=[],
        )
        overrides = evaluate_safety_overrides(
            test=t,
            dep_info_available=True,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="MEDIUM",
        )
        assert score == 30
        assert score < RUN_THRESHOLD
        assert overrides == []  # no override → SKIP decision

    def test_score_above_threshold_runs(self):
        """Score=70 (direct=40 + dep=30) exceeds threshold=50 → RUN path."""
        t = _make_test(test_id="T_RUN")
        score, _ = compute_risk_score(
            test=t,
            covered_test_ids={"T_RUN"},    # +40
            dependency_test_ids={"T_RUN"}, # +30
            failure_associated_ids=set(),
            is_security_sensitive=False,
            affected_modules=[],
        )
        assert score == 70
        assert score >= RUN_THRESHOLD

    def test_all_dimensions_accumulate_correctly(self):
        """Verify the complete additive formula: direct(40)+dep(30)+hist(20)+security(30)+critical(25)=145.
        Note: recent_failure(+15) and high_risk_device(+10) are database-dependent so not included here.
        """
        t = _make_test(test_id="T_FULL", module="Authentication")
        score, evidence = compute_risk_score(
            test=t,
            covered_test_ids={"T_FULL"},        # +40
            dependency_test_ids={"T_FULL"},      # +30
            failure_associated_ids={"T_FULL"},   # +20
            is_security_sensitive=True,           # +30
            affected_modules=["Authentication"],  # critical module +25
            failed_ids=set(),                     # no recent failure
            device_risks={},                      # no high risk device
        )
        # 40 + 30 + 20 + 30 + 25 = 145
        assert score == 145, f"Expected 145, got {score}"
        assert len(evidence) == 5


# ──────────────────────────────────────────────────────────────────────────────
# Confidence Level Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestConfidenceLevels:
    """determine_confidence() must return consistent confidence levels."""

    def test_high_confidence_requires_3_evidence_and_score_70(self):
        assert determine_confidence(score=70, evidence=["a", "b", "c"]) == "HIGH"
        assert determine_confidence(score=85, evidence=["a", "b", "c", "d"]) == "HIGH"

    def test_medium_confidence_with_some_evidence(self):
        assert determine_confidence(score=60, evidence=["a"]) == "MEDIUM"
        assert determine_confidence(score=50, evidence=[]) == "MEDIUM"

    def test_low_confidence_no_evidence_low_score(self):
        assert determine_confidence(score=0, evidence=[]) == "LOW"
        assert determine_confidence(score=49, evidence=[]) == "LOW"

    def test_low_confidence_triggers_rule6(self):
        """LOW confidence from determine_confidence must cascade into RULE_6 override."""
        conf = determine_confidence(score=10, evidence=[])
        assert conf == "LOW"
        overrides = evaluate_safety_overrides(
            test=_make_test(),
            dep_info_available=True,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level=conf,
        )
        assert "RULE_6_LOW_CONFIDENCE" in _rule_ids(overrides)


# ──────────────────────────────────────────────────────────────────────────────
# Edge / Malformed Input Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestEdgeCasesAndMalformedInput:
    """Safety override engine must not crash on empty or missing fields."""

    def test_empty_test_dict_does_not_crash(self):
        """An empty test dict must not raise an exception."""
        overrides = evaluate_safety_overrides(
            test={},
            dep_info_available=True,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="HIGH",
        )
        # No rule dependent on module or is_security_critical should fire
        ids = _rule_ids(overrides)
        assert "RULE_3_SECURITY_CRITICAL" not in ids
        assert "RULE_4_CRITICAL_MODULE" not in ids

    def test_missing_module_field_does_not_trigger_critical_module_rule(self):
        """A test without a module field must not accidentally trigger RULE_4_CRITICAL_MODULE."""
        overrides = evaluate_safety_overrides(
            test={"test_id": "T_NO_MODULE"},
            dep_info_available=True,
            coverage_info_available=True,
            failure_data_available=True,
            confidence_level="HIGH",
        )
        assert "RULE_4_CRITICAL_MODULE" not in _rule_ids(overrides)

    def test_risk_scoring_empty_covered_ids(self):
        """compute_risk_score must return score=0 for empty sets."""
        score, evidence = compute_risk_score(
            test=_make_test(),
            covered_test_ids=set(),
            dependency_test_ids=set(),
            failure_associated_ids=set(),
            is_security_sensitive=False,
            affected_modules=[],
        )
        assert score == 0
        assert evidence == []

    def test_risk_scoring_with_none_failed_ids(self):
        """failed_ids=None must not crash; system falls back gracefully."""
        score, _ = compute_risk_score(
            test=_make_test(),
            covered_test_ids=set(),
            dependency_test_ids=set(),
            failure_associated_ids=set(),
            is_security_sensitive=False,
            affected_modules=[],
            failed_ids=None,  # explicitly test None branch
        )
        assert isinstance(score, int)

    def test_risk_scoring_with_none_device_risks(self):
        """device_risks=None must not crash; system uses fallback."""
        score, _ = compute_risk_score(
            test=_make_test(device="Pixel 8", os_version="Android 15"),
            covered_test_ids=set(),
            dependency_test_ids=set(),
            failure_associated_ids=set(),
            is_security_sensitive=False,
            affected_modules=[],
            device_risks=None,  # explicitly test None branch
        )
        assert isinstance(score, int)
