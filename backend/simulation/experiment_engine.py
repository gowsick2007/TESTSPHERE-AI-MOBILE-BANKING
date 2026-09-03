"""
TestSphere AI — Experiment Benchmarking Engine
Performs precision/recall comparisons against experiment ground truth records.
"""
from typing import Dict, Any, List
from backend.database import get_db_connection
from backend.engine.test_selector import run_selection


def run_experiment_comparison(
    changed_files: List[str],
    change_type: str = "MODIFIED",
    module: str | None = None,
    is_security_sensitive: bool = False,
    risk_level: str = "MEDIUM",
) -> Dict[str, Any]:
    """
    Computes confusion matrix, precision, recall, and time savings.
    """
    # 1. Run the selector
    selection_res = run_selection(
        changed_files=changed_files,
        change_type=change_type,
        module=module,
        is_security_sensitive=is_security_sensitive,
        risk_level=risk_level
    )

    decisions = selection_res["decisions"]
    summary = selection_res["summary"]

    # 2. Fetch ground truth from SQLite
    conn = get_db_connection()
    ground_truth = {}
    try:
        # We look up CHG001 as the baseline reference change
        rows = conn.execute("SELECT test_id, affected FROM experiment_ground_truth WHERE change_id = 'CHG001'").fetchall()
        for r in rows:
            ground_truth[r["test_id"]] = bool(r["affected"])
    except Exception:
        pass
    finally:
        conn.close()

    # 3. Calculate Confusion Matrix
    tp, fp, tn, fn = 0, 0, 0, 0

    for d in decisions:
        t_id = d["test_id"]
        actual_affected = ground_truth.get(t_id, False)
        system_decision = d["decision"]  # RUN or SKIP

        if system_decision == "RUN":
            if actual_affected:
                tp += 1
            else:
                fp += 1
        else: # SKIP
            if actual_affected:
                fn += 1
            else:
                tn += 1

    # Ratios
    precision = round(tp / max(tp + fp, 1), 3)
    recall = round(tp / max(tp + fn, 1), 3)
    f1 = round(2 * precision * recall / max(precision + recall, 0.001), 3)
    miss_rate = round(fn / max(tp + fn, 1), 3)

    return {
        "comparison": {
            "strategy_smart": "SMART_SELECTOR",
            "strategy_baseline": "LEGACY_FULL_SUITE",
            "total_tests": len(decisions),
            "tests_run_smart": tp + fp,
            "tests_skipped_smart": tn + fn,
            "runtime_smart_minutes": summary["selected_runtime_minutes"],
            "runtime_baseline_minutes": summary["total_runtime_minutes"],
            "time_saved_minutes": summary["time_saved_minutes"],
            "time_reduction_pct": summary["time_reduction_pct"],
        },
        "quality": {
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn,
            "precision": round(precision * 100, 1),
            "recall": round(recall * 100, 1),
            "f1_score": round(f1 * 100, 1),
            "miss_rate": round(miss_rate * 100, 1)
        }
    }
