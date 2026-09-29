"""
TestSphere AI — Analytics & Diagnostic API Routes (Phase 2)
Provides endpoints for:
- Precision / Recall benchmarks and module risk distribution
- False Negative investigation
- False Positive over-selection breakdown
- Threshold sensitivity evaluation
"""
from fastapi import APIRouter, Query
from typing import Optional, List

from backend.engine.analytics_reporter import (
    get_analytics_summary,
    get_false_negative_investigation,
    get_false_positive_analysis,
)
from backend.engine.threshold_evaluator import evaluate_thresholds

router = APIRouter(prefix="/analytics", tags=["Analytics & Diagnostics"])


@router.get("/summary")
def analytics_summary():
    """Provides high-level performance metrics, scenario comparisons, and risk distributions."""
    return get_analytics_summary()


@router.get("/false-negatives")
def false_negative_audit(change_id: str = Query("CHG001", description="Change ID to investigate")):
    """Audits false negatives (missed affected tests) for a change submission."""
    return get_false_negative_investigation(change_id=change_id)


@router.get("/false-positives")
def false_positive_breakdown(change_id: str = Query("CHG001", description="Change ID to investigate")):
    """Categorizes root causes of over-selection (safety overrides, dependency propagation, etc.)."""
    return get_false_positive_analysis(change_id=change_id)


@router.get("/threshold-sensitivity")
def threshold_sensitivity(change_id: str = Query("CHG001", description="Change ID to evaluate against")):
    """Evaluates candidate risk thresholds [30, 40, 50, 60, 70] against ground truth."""
    return evaluate_thresholds(scenario_change_id=change_id)
