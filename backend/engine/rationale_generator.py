"""
TestSphere AI — Rationale Generator
Formulates transparent reasons for selecting or skipping tests.
"""
from typing import Dict, List, Any


def generate_rationale(
    test: Dict[str, Any],
    decision: str,
    score: int,
    evidence: List[str],
    overrides: List[Dict[str, str]],
    confidence: str,
) -> str:
    """
    Creates a human-readable explanation of why a test was skipped or selected to run.
    """
    test_id = test.get("test_id", "")
    module = test.get("module", "")

    if decision == "RUN":
        if overrides:
            # Join override reasons
            reasons = "; ".join([o["reason"] for o in overrides])
            return f"SAFETY OVERRIDE TRIGGERED: {reasons}"

        reasons = []
        if any("Direct coverage" in e for e in evidence):
            reasons.append("direct coverage of modified code")
        if any("Dependency path" in e for e in evidence):
            reasons.append("dependency chain connection")
        if any("Historical failure" in e for e in evidence):
            reasons.append("historical failure density in this module")
        if any("High-risk device" in e for e in evidence):
            reasons.append("high-risk device target configuration")

        joined = ", ".join(reasons) if reasons else "high computed risk score"
        return f"Selected to RUN because of: {joined} (Risk Score: {score}/100, Confidence: {confidence})."

    else:
        # SKIP rationale
        return "No relevant impact relationship was identified from the available evidence. Risk score is below threshold."


def format_decision_record(
    test: Dict[str, Any],
    decision: str,
    score: int,
    confidence: str,
    evidence: List[str],
    overrides: List[Dict[str, str]],
    rationale: str,
) -> Dict[str, Any]:
    """Combines test details and reasoning into a single structured record."""
    return {
        "test_id": test["test_id"],
        "test_name": test["test_name"],
        "module": test.get("module", "Unknown"),
        "device": test.get("device", "Unknown"),
        "os_version": test.get("os_version", "—"),
        "execution_time": test.get("execution_time", 0.5),
        "risk_score": score,
        "decision": decision,
        "confidence": confidence,
        "evidence": evidence,
        "overrides": overrides,
        "rationale": rationale,
    }
