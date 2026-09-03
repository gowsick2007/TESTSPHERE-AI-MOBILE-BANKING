"""
TestSphere AI — Experiment Engine
Orchestrates a side-by-side Baseline vs Smart comparison experiment.
All metrics are computed from actual selection decisions — not hardcoded.
"""
import logging
from Engine.test_selector import run_selection
from Engine.metrics_calculator import calculate_experiment_metrics, calculate_time_metrics
from Engine.data_access import get_all_tests
from Simulation.baseline_runner import run_baseline
from Simulation.smart_runner import run_smart

logger = logging.getLogger(__name__)

# Default change for experiment (payment.py from demo data)
DEFAULT_CHANGED_FILES = ["payment/payment.py", "payment/payment_controller.py"]
DEFAULT_CHANGE_TYPE = "MODIFIED"
DEFAULT_MODULE = "Payment"
DEFAULT_RISK = "HIGH"
DEFAULT_IS_SECURITY = False


def run_experiment(
    changed_files: list[str] = DEFAULT_CHANGED_FILES,
    change_type: str = DEFAULT_CHANGE_TYPE,
    module: str | None = DEFAULT_MODULE,
    is_security_sensitive: bool = DEFAULT_IS_SECURITY,
    risk_level: str = DEFAULT_RISK,
    change_id: str = "CHG001",
) -> dict:
    """
    Run a full comparison experiment.

    Returns:
        dict with baseline_run, smart_run, selection_result, metrics
    """
    logger.info("Running experiment for: %s", changed_files)

    # ── Baseline (all tests) ───────────────────────────────────────────────────
    baseline = run_baseline()

    # ── Smart selection ────────────────────────────────────────────────────────
    selection = run_selection(
        changed_files=changed_files,
        change_type=change_type,
        module=module,
        is_security_sensitive=is_security_sensitive,
        risk_level=risk_level,
    )
    smart = run_smart(selection["decisions"])

    # ── Experiment metrics ─────────────────────────────────────────────────────
    all_tests = get_all_tests()
    selected_tests = [d for d in selection["decisions"] if d["decision"] == "RUN"]

    quality_metrics = calculate_experiment_metrics(selection["decisions"], change_id)
    time_metrics    = calculate_time_metrics(all_tests, selected_tests)

    return {
        "baseline":    baseline,
        "smart":       smart,
        "selection":   selection,
        "quality":     quality_metrics,
        "time":        time_metrics,
        "comparison": {
            "baseline_tests":     baseline["total_tests"],
            "smart_tests":        smart["executed"],
            "tests_skipped":      smart["skipped"],
            "baseline_runtime_m": baseline["runtime_minutes"],
            "smart_runtime_m":    smart["runtime_minutes"],
            "time_saved_m":       round(baseline["runtime_minutes"] - smart["runtime_minutes"], 2),
            "time_reduction_pct": time_metrics["time_reduction_pct"],
            "recall":             quality_metrics["recall"],
            "precision":          quality_metrics["precision"],
            "f1_score":           quality_metrics["f1_score"],
            "miss_rate":          quality_metrics["miss_rate"],
            "missed_affected":    quality_metrics["missed_affected"],
            "false_positives":    quality_metrics["false_positives"],
            "false_negatives":    quality_metrics["false_negatives"],
        },
    }
