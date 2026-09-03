"""
TestSphere AI — Rationale Generator
Produces human-readable, evidence-based explanations for every RUN/SKIP decision.
Every SKIP must have a rationale. Silent skips are prohibited.
"""
import logging

logger = logging.getLogger(__name__)


def generate_rationale(
    test: dict,
    decision: str,
    score: int,
    evidence: list[str],
    overrides: list[dict],
    confidence: str,
) -> str:
    """
    Generate a transparent, human-readable rationale for a RUN or SKIP decision.

    Args:
        test        — test record dict
        decision    — "RUN" or "SKIP"
        score       — numeric risk score
        evidence    — list of evidence strings
        overrides   — list of safety override dicts (if any triggered)
        confidence  — "HIGH" | "MEDIUM" | "LOW"

    Returns:
        str — complete rationale text
    """
    test_name = test.get("test_name", test.get("test_id", "?"))
    module = test.get("module", "Unknown")
    device = test.get("device", "Unknown")

    if decision == "RUN":
        return _build_run_rationale(test_name, module, device, score, evidence, overrides, confidence)
    elif decision == "SKIP":
        return _build_skip_rationale(test_name, module, device, score, evidence, confidence)
    else:
        return f"Decision: {decision} — No rationale available."


def _build_run_rationale(
    test_name: str, module: str, device: str,
    score: int, evidence: list[str], overrides: list[dict], confidence: str
) -> str:
    parts = []

    if overrides:
        override_reasons = [o["reason"] for o in overrides]
        parts.append("Safety override triggered: " + "; ".join(override_reasons[:2]))

    if evidence:
        evi_str = "; ".join(evidence[:4])
        parts.append(f"Evidence: {evi_str}")

    if score >= 70:
        parts.append(
            f"Selected because the test has strong impact evidence (score {score}) "
            f"for the {module} module on {device}."
        )
    elif score >= 50:
        parts.append(
            f"Selected because the test meets the risk threshold (score {score}) "
            f"for the affected {module} module."
        )
    else:
        parts.append(
            f"Selected via safety override despite a low raw score ({score}). "
            f"The system cannot safely justify skipping this test."
        )

    return " ".join(parts) if parts else f"Selected for execution (score={score}, confidence={confidence})."


def _build_skip_rationale(
    test_name: str, module: str, device: str,
    score: int, evidence: list[str], confidence: str
) -> str:
    if not evidence:
        return (
            f"Skipped because no impact relationship was found between this test and the "
            f"changed files. No dependency path, no direct coverage, no historical failure "
            f"association, and no device risk was identified. Score: {score}. "
            f"Confidence: {confidence}."
        )
    evi_str = "; ".join(evidence)
    return (
        f"Skipped because the available evidence (score={score}) did not meet the "
        f"run threshold. Partial evidence: {evi_str}. "
        f"No safety override applies. Confidence: {confidence}."
    )


def generate_why_run(evidence: list[str], overrides: list[dict]) -> list[str]:
    """Generate bullet-point 'Why RUN?' reasons."""
    reasons = []
    for o in overrides:
        reasons.append(o.get("badge", o.get("reason", "Safety override")))
    for e in evidence:
        reasons.append(e)
    return reasons if reasons else ["Selected via conservative safe-default policy"]


def generate_why_skip(score: int, evidence: list[str]) -> list[str]:
    """Generate bullet-point 'Why SKIP?' reasons."""
    reasons = []
    if not evidence or all("+" not in e for e in evidence):
        reasons += [
            "No dependency path to changed files",
            "No direct test coverage of changed files",
            "No historical failure association",
            "Low device risk profile",
        ]
    else:
        reasons.append(f"Score ({score}) below run threshold")
        reasons += [f"Partial: {e}" for e in evidence[:3]]
    return reasons


def format_decision_record(
    test: dict,
    decision: str,
    score: int,
    confidence: str,
    evidence: list[str],
    overrides: list[dict],
    rationale: str,
) -> dict:
    """Return a fully structured decision record for display and storage."""
    return {
        "test_id":     test.get("test_id"),
        "test_name":   test.get("test_name"),
        "module":      test.get("module"),
        "device":      test.get("device"),
        "os_version":  test.get("os_version"),
        "decision":    decision,
        "risk_score":  score,
        "confidence":  confidence,
        "evidence":    evidence,
        "overrides":   [o if isinstance(o, dict) else o.to_dict() for o in overrides],
        "rationale":   rationale,
        "why_run":     generate_why_run(evidence, overrides) if decision == "RUN" else [],
        "why_skip":    generate_why_skip(score, evidence) if decision == "SKIP" else [],
        "execution_time": test.get("execution_time", 0.5),
    }
