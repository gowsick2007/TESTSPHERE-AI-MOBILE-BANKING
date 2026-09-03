"""
TestSphere AI — Metrics Calculator
Computes experiment metrics: Precision, Recall, F1, Miss Rate, Time Reduction.
"""
import logging
from Engine.data_access import get_ground_truth

logger = logging.getLogger(__name__)


def calculate_experiment_metrics(
    decisions: list[dict],
    change_id: str = "CHG001",
) -> dict:
    """
    Compare selection decisions against ground truth to compute experiment metrics.

    Returns:
        dict with TP, TN, FP, FN, Precision, Recall, F1, Miss Rate, etc.
    """
    ground_truth = get_ground_truth(change_id)
    if not ground_truth:
        logger.warning("No ground truth available for change_id=%s", change_id)
        return _no_ground_truth()

    gt_map: dict[str, bool] = {
        row["test_id"]: bool(row["actually_affected"]) for row in ground_truth
    }
    decision_map: dict[str, str] = {d["test_id"]: d["decision"] for d in decisions}

    tp = tn = fp = fn = 0
    for test_id, actually_affected in gt_map.items():
        selected = decision_map.get(test_id, "RUN") == "RUN"
        if actually_affected and selected:
            tp += 1
        elif not actually_affected and not selected:
            tn += 1
        elif not actually_affected and selected:
            fp += 1
        elif actually_affected and not selected:
            fn += 1

    total_affected   = tp + fn
    total_unaffected = tn + fp
    precision = round(tp / max(tp + fp, 1), 4)
    recall    = round(tp / max(tp + fn, 1), 4)
    f1        = round(2 * precision * recall / max(precision + recall, 1e-9), 4)
    miss_rate = round(fn / max(total_affected, 1), 4)

    return {
        "true_positives":   tp,
        "true_negatives":   tn,
        "false_positives":  fp,
        "false_negatives":  fn,
        "total_affected":   total_affected,
        "total_unaffected": total_unaffected,
        "precision":        precision,
        "recall":           recall,
        "f1_score":         f1,
        "miss_rate":        miss_rate,
        "missed_affected":  fn,
        "ground_truth_available": True,
    }


def calculate_time_metrics(
    all_tests: list[dict],
    selected_tests: list[dict],
) -> dict:
    """Calculate runtime reduction between baseline and smart selection."""
    baseline_time = sum(t.get("execution_time", 0.5) for t in all_tests)
    smart_time    = sum(t.get("execution_time", 0.5) for t in selected_tests)
    time_saved    = baseline_time - smart_time
    reduction_pct = round((time_saved / max(baseline_time, 1)) * 100, 1)

    return {
        "baseline_runtime_seconds":  round(baseline_time, 2),
        "smart_runtime_seconds":     round(smart_time, 2),
        "time_saved_seconds":        round(time_saved, 2),
        "baseline_runtime_minutes":  round(baseline_time / 60, 2),
        "smart_runtime_minutes":     round(smart_time / 60, 2),
        "time_saved_minutes":        round(time_saved / 60, 2),
        "time_reduction_pct":        reduction_pct,
    }


def _no_ground_truth() -> dict:
    return {
        "true_positives": 0, "true_negatives": 0,
        "false_positives": 0, "false_negatives": 0,
        "total_affected": 0, "total_unaffected": 0,
        "precision": 0.0, "recall": 0.0, "f1_score": 0.0,
        "miss_rate": 0.0, "missed_affected": 0,
        "ground_truth_available": False,
    }
