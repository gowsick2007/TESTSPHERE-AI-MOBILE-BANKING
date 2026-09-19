import nbformat as nbf

nb = nbf.v4.new_notebook()

text = """\
# TestSphere.AI Experiment Notebook
This notebook loads the dataset, dependency map, test coverage, and failure history to evaluate the change-impact test selection.
It runs a baseline (all tests) and TestSphere.AI's smart selection, then compares simulated execution time reduction and affected-test false negatives against ground truth.
All timing values represent SIMULATED EXECUTION TIME calculated from test execution time metadata.
"""
nb['cells'].append(nbf.v4.new_markdown_cell(text))

code1 = """\
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(os.getcwd()).parent))

from Engine.database import get_connection
from Engine.test_selector import run_selection
from Simulation.baseline_runner import run_baseline
from Simulation.smart_runner import run_smart
from Engine.metrics_calculator import calculate_experiment_metrics, calculate_time_metrics
import pandas as pd

print("Environment setup complete.")
"""
nb['cells'].append(nbf.v4.new_code_cell(code1))

code2 = """\
# 1-4. Load Data
def load_data(table_name):
    conn = get_connection()
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    conn.close()
    return df

coverage_df = load_data("test_coverage")
deps_df = load_data("dependency_map")
failures_df = load_data("failure_history")
changes_df = load_data("code_changes")

print(f"Loaded {len(coverage_df)} tests, {len(deps_df)} dependencies, {len(failures_df)} failures.")
"""
nb['cells'].append(nbf.v4.new_code_cell(code2))

code3 = """\
# 5. Define code-change scenarios matching canonical ground truth
scenarios = [
    {"id": "CHG001", "name": "Scenario 1: Payment core change", "files": ["payment/payment.py"], "module": "Payment", "risk": "HIGH", "is_sec": False},
    {"id": "CHG003", "name": "Scenario 2: Auth login patch", "files": ["auth/login.py"], "module": "Authentication", "risk": "HIGH", "is_sec": True},
    {"id": "CHG008", "name": "Scenario 3: Transaction limit change", "files": ["transaction/txn_limit.py"], "module": "Transaction", "risk": "MEDIUM", "is_sec": False},
    {"id": "CHG011", "name": "Scenario 4: Notification push update", "files": ["notification/push.py"], "module": "Notification", "risk": "LOW", "is_sec": False},
    {"id": "CHG_MULTI", "name": "Scenario 5: Multi-module change", "files": ["payment/payment.py", "auth/login.py"], "module": "Payment", "risk": "HIGH", "is_sec": True}
]
"""
nb['cells'].append(nbf.v4.new_code_cell(code3))

code4 = """\
# 6-11. Run Baseline vs Smart Selector and compute verified metrics
results = []
for s in scenarios:
    print(f"\\nRunning {s['name']} (ID: {s['id']})...")
    
    # Baseline run
    baseline = run_baseline()
    
    # TestSphere.AI selection
    selection = run_selection(
        changed_files=s["files"],
        change_type="MODIFIED",
        module=s["module"],
        is_security_sensitive=s["is_sec"],
        risk_level=s["risk"]
    )
    decisions = selection["decisions"]
    
    # Smart execution simulation
    smart_exec = run_smart(decisions)
    
    # Calculate runtime reduction (SIMULATED EXECUTION TIME)
    all_tests = coverage_df.to_dict('records')
    selected_tests = [t for t in all_tests if any(d["test_id"] == t["test_id"] and d["decision"] == "RUN" for d in decisions)]
    time_metrics = calculate_time_metrics(all_tests, selected_tests)
    
    # Calculate quality metrics against actual synthetic ground truth
    metrics = calculate_experiment_metrics(decisions, change_id=s["id"])
    
    res = {
        "Scenario ID": s['id'],
        "Scenario Name": s['name'],
        "Total Tests": baseline['total_tests'],
        "RUN Tests": smart_exec['executed'],
        "SKIP Tests": smart_exec['skipped'],
        "TP": metrics['true_positives'],
        "TN": metrics['true_negatives'],
        "FP": metrics['false_positives'],
        "FN": metrics['false_negatives'],
        "Precision": metrics['precision'],
        "Recall": metrics['recall'],
        "Simulated Time Reduction %": time_metrics['time_reduction_pct'],
        "Simulated Time Saved (min)": time_metrics['time_saved_minutes']
    }
    results.append(res)

results_df = pd.DataFrame(results)
display(results_df)
"""
nb['cells'].append(nbf.v4.new_code_cell(code4))

with open('experiments/testsphere_experiment.ipynb', 'w') as f:
    nbf.write(nb, f)

print("experiments/testsphere_experiment.ipynb successfully generated.")
