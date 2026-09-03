"""
TestSphere AI — Synthetic Dataset Generator (Updated)
Generates realistic, deterministic demo data (seed=42) for all 5 core datasets.
"""
import sqlite3
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add root folder to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Engine.database import get_connection as get_db_connection, initialize_database, upsert_dataset_metadata

SEED = 42
random.seed(SEED)

MODULES = [
    "Authentication", "Authorization", "OTP", "Payment", "UPI",
    "Transaction", "Account", "Profile", "Notification",
    "FraudDetection", "Dashboard", "DeviceSecurity",
    "AccountSecurity", "Biometrics", "CustomerSupport"
]

CRITICAL_MODULES = {
    "Authentication", "Authorization", "OTP", "Payment", "UPI",
    "Transaction", "FraudDetection", "AccountSecurity"
}

DEVICES = [
    ("D001", "Pixel 8",      "Android", "Android 15", "HIGH",   0.08),
    ("D002", "Pixel 7",      "Android", "Android 14", "MEDIUM", 0.05),
    ("D003", "Samsung S24",  "Android", "Android 15", "HIGH",   0.07),
    ("D004", "Samsung A54",  "Android", "Android 14", "MEDIUM", 0.04),
    ("D005", "Samsung A34",  "Android", "Android 13", "LOW",    0.03),
    ("D006", "iPhone 15",    "iOS",     "iOS 18",      "HIGH",   0.06),
    ("D007", "iPhone 14",    "iOS",     "iOS 17",      "MEDIUM", 0.05),
    ("D008", "iPhone 12",    "iOS",     "iOS 17",      "LOW",    0.03),
]

DEVICE_NAMES  = [d[1] for d in DEVICES]
DEVICE_OS_MAP = {d[1]: (d[3]) for d in DEVICES}

MODULE_FILES = {
    "Authentication":   ["auth/login.py",         "auth/session.py",     "auth/token_manager.py"],
    "Authorization":    ["auth/permissions.py",   "auth/role_check.py",  "auth/policy.py"],
    "OTP":              ["otp/otp_generator.py",  "otp/otp_validator.py","otp/otp_delivery.py"],
    "Payment":          ["payment/payment.py",    "payment/payment_controller.py","payment/payment_api.py","payment/payment_screen.py"],
    "UPI":              ["upi/upi_handler.py",    "upi/upi_validator.py","upi/upi_api.py"],
    "Transaction":      ["transaction/txn.py",    "transaction/txn_history.py","transaction/txn_limit.py"],
    "Account":          ["account/account.py",    "account/balance.py",  "account/statement.py"],
    "Profile":          ["profile/profile.py",    "profile/profile_update.py","profile/kyc.py"],
    "Notification":     ["notification/push.py",  "notification/sms.py", "notification/email_notif.py"],
    "FraudDetection":   ["fraud/fraud_engine.py", "fraud/anomaly.py",    "fraud/rules.py"],
    "Dashboard":        ["dashboard/home.py",     "dashboard/widgets.py","dashboard/analytics.py"],
    "DeviceSecurity":   ["device/device_bind.py", "device/device_trust.py","device/cert_pinning.py"],
    "AccountSecurity":  ["account/security.py",   "account/mpin.py",     "account/biometric_link.py"],
    "Biometrics":       ["biometrics/face_id.py", "biometrics/fingerprint.py","biometrics/liveness.py"],
    "CustomerSupport":  ["support/ticket.py",     "support/chat.py",     "support/faq.py"],
}

ALL_FILES = [f for files in MODULE_FILES.values() for f in files]
FILE_MODULE_MAP = {f: mod for mod, files in MODULE_FILES.items() for f in files}

TEST_NAME_TEMPLATES = {
    "Authentication":  ["Login Test", "Session Expiry Test", "Token Refresh Test", "Logout Test", "Multi-device Login Test"],
    "Authorization":   ["Role Permission Test", "Policy Enforcement Test", "Unauthorized Access Test", "RBAC Test"],
    "OTP":             ["OTP Generation Test", "OTP Validation Test", "OTP Expiry Test", "OTP Resend Test"],
    "Payment":         ["Payment Flow Test", "Payment Failure Test", "Refund Test", "Payment Limit Test", "UPI Payment Test"],
    "UPI":             ["UPI Transfer Test", "UPI Collect Test", "UPI QR Test", "VPA Validation Test"],
    "Transaction":     ["Transaction History Test", "Transaction Limit Test", "Concurrent Transaction Test"],
    "Account":         ["Balance Fetch Test", "Statement Download Test", "Account Summary Test"],
    "Profile":         ["Profile Update Test", "KYC Verification Test", "Profile Photo Test"],
    "Notification":    ["Push Notification Test", "SMS Notification Test", "Email Alert Test"],
    "FraudDetection":  ["Fraud Rule Test", "Anomaly Detection Test", "High-Value Alert Test"],
    "Dashboard":       ["Home Screen Test", "Widget Load Test", "Analytics Test"],
    "DeviceSecurity":  ["Device Binding Test", "Certificate Pinning Test", "Root Detection Test"],
    "AccountSecurity": ["MPIN Change Test", "Biometric Link Test", "Security Question Test"],
    "Biometrics":      ["Face ID Test", "Fingerprint Test", "Liveness Detection Test"],
    "CustomerSupport": ["Ticket Creation Test", "Chat Test", "FAQ Search Test"],
}

CHANGE_TYPES = ["MODIFIED", "ADDED", "DELETED", "REFACTORED"]
SEVERITY_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
ERROR_TYPES = ["NullPointerException", "TimeoutError", "AssertionError", "NetworkError", "AuthError", "ValueError"]


def generate_tests(n: int = 1000) -> list[dict]:
    tests = []
    counters = {m: 0 for m in MODULES}
    rng = random.Random(SEED)

    for i in range(1, n + 1):
        module = rng.choice(MODULES)
        counters[module] += 1
        file_path = rng.choice(MODULE_FILES[module])
        device = rng.choice(DEVICE_NAMES)
        os_version = DEVICE_OS_MAP[device]
        is_critical = module in CRITICAL_MODULES
        templates = TEST_NAME_TEMPLATES[module]
        base_name = templates[counters[module] % len(templates)]
        test_name = f"{base_name} {counters[module]}"
        exec_time = round(rng.uniform(0.2, 3.0), 2)
        if is_critical:
            exec_time = round(rng.uniform(0.5, 5.0), 2)

        tests.append({
            "test_id": f"T{i:04d}",
            "test_name": test_name,
            "file_path": file_path,
            "module": module,
            "device": device,
            "os_version": os_version,
            "execution_time": exec_time,
            "is_security_critical": 1 if is_critical else 0,
            "tags": module.lower(),
        })
    return tests


def generate_dependencies() -> list[dict]:
    rng = random.Random(SEED + 1)
    deps = []
    seen = set()

    for module, files in MODULE_FILES.items():
        for src in files:
            for dep in files:
                if src != dep and rng.random() < 0.4:
                    key = (src, dep)
                    if key not in seen:
                        seen.add(key)
                        deps.append({"source_file": src, "depends_on": dep, "module": module, "depth": 1})

    cross_deps = [
        ("payment/payment_controller.py", "auth/token_manager.py",    "Payment",        2),
        ("payment/payment_api.py",        "fraud/fraud_engine.py",    "Payment",        2),
        ("upi/upi_handler.py",            "payment/payment.py",       "UPI",            2),
        ("transaction/txn.py",            "account/balance.py",       "Transaction",    2),
        ("transaction/txn.py",            "fraud/anomaly.py",         "Transaction",    2),
        ("otp/otp_validator.py",          "auth/session.py",          "OTP",            2),
        ("account/security.py",           "auth/permissions.py",      "AccountSecurity",2),
        ("biometrics/face_id.py",         "auth/token_manager.py",    "Biometrics",     2),
        ("dashboard/home.py",             "account/balance.py",       "Dashboard",      2),
        ("dashboard/analytics.py",        "transaction/txn_history.py","Dashboard",     2),
        ("notification/push.py",          "account/account.py",       "Notification",   2),
        ("fraud/rules.py",                "transaction/txn_limit.py", "FraudDetection", 2),
        ("device/device_trust.py",        "auth/token_manager.py",    "DeviceSecurity", 2),
        ("support/ticket.py",             "profile/profile.py",       "CustomerSupport",2),
    ]
    for row in cross_deps:
        key = (row[0], row[1])
        if key not in seen:
            seen.add(key)
            deps.append({"source_file": row[0], "depends_on": row[1], "module": row[2], "depth": row[3]})

    # Add 40 additional random depth=3 edges
    for _ in range(40):
        src = rng.choice(ALL_FILES)
        dep = rng.choice(ALL_FILES)
        if src != dep:
            key = (src, dep)
            if key not in seen:
                seen.add(key)
                deps.append({"source_file": src, "depends_on": dep, "module": FILE_MODULE_MAP.get(src, "Unknown"), "depth": 3})
    return deps


def generate_failure_history(tests: list[dict], n_failures: int = 2400) -> list[dict]:
    rng = random.Random(SEED + 2)
    records = []
    critical_tests = [t for t in tests if t["module"] in CRITICAL_MODULES]
    non_critical_tests = [t for t in tests if t["module"] not in CRITICAL_MODULES]

    critical_count = int(n_failures * 0.70)
    non_critical_count = n_failures - critical_count
    base_date = datetime(2025, 1, 1)

    def random_date():
        delta = rng.randint(0, 365)
        return (base_date + timedelta(days=delta)).strftime("%Y-%m-%d")

    for _ in range(critical_count):
        t = rng.choice(critical_tests)
        records.append({
            "test_id": t["test_id"],
            "failure_date": random_date(),
            "module": t["module"],
            "device": t["device"],
            "os_version": t["os_version"],
            "severity": rng.choice(["HIGH", "CRITICAL", "MEDIUM"]),
            "error_type": rng.choice(ERROR_TYPES),
            "resolved": rng.choice([0, 1]),
        })

    for _ in range(non_critical_count):
        t = rng.choice(non_critical_tests)
        records.append({
            "test_id": t["test_id"],
            "failure_date": random_date(),
            "module": t["module"],
            "device": t["device"],
            "os_version": t["os_version"],
            "severity": rng.choice(["LOW", "MEDIUM"]),
            "error_type": rng.choice(ERROR_TYPES),
            "resolved": rng.choice([0, 1]),
        })

    return records


def generate_code_changes() -> list[dict]:
    rng = random.Random(SEED + 3)
    changes = []
    base_date = datetime(2025, 6, 1)

    change_scenarios = [
        ("payment/payment.py",         "Payment",        "MODIFIED",        1, "HIGH"),
        ("payment/payment_controller.py","Payment",       "MODIFIED",        1, "HIGH"),
        ("auth/login.py",              "Authentication", "SECURITY_PATCH",  1, "HIGH"),
        ("auth/token_manager.py",      "Authentication", "MODIFIED",        1, "HIGH"),
        ("otp/otp_generator.py",       "OTP",            "MODIFIED",        1, "MEDIUM"),
        ("fraud/fraud_engine.py",      "FraudDetection", "MODIFIED",        1, "HIGH"),
        ("upi/upi_handler.py",         "UPI",            "MODIFIED",        0, "HIGH"),
        ("transaction/txn_limit.py",   "Transaction",    "MODIFIED",        0, "MEDIUM"),
        ("profile/profile_update.py",  "Profile",        "MODIFIED",        0, "LOW"),
        ("dashboard/analytics.py",     "Dashboard",      "ADDED",           0, "LOW"),
        ("notification/push.py",       "Notification",   "MODIFIED",        0, "LOW"),
        ("account/balance.py",         "Account",        "MODIFIED",        0, "MEDIUM"),
        ("device/cert_pinning.py",     "DeviceSecurity", "SECURITY_PATCH",  1, "HIGH"),
        ("biometrics/face_id.py",      "Biometrics",     "MODIFIED",        0, "MEDIUM"),
        ("support/ticket.py",          "CustomerSupport","ADDED",           0, "LOW"),
    ]

    for i, (fp, mod, ct, iss, risk) in enumerate(change_scenarios):
        changed_at = (base_date + timedelta(days=i * 7 + rng.randint(0, 3))).isoformat()
        changes.append({
            "change_id": f"CHG{i+1:03d}",
            "file_path": fp,
            "module": mod,
            "change_type": ct,
            "is_security_sensitive": iss,
            "risk_level": risk,
            "changed_at": changed_at,
            "changed_by": rng.choice(["dev_alice", "dev_bob", "dev_charlie", "dev_diana"]),
            "description": f"{ct} in {mod} module: {fp}",
        })
    return changes


def generate_ground_truth(tests: list[dict], changes: list[dict], deps: list[dict]) -> list[dict]:
    rng = random.Random(SEED + 4)
    
    scenario_configs = [
        ("CHG001", ["payment/payment.py"], "Payment"),
        ("CHG003", ["auth/login.py"], "Authentication"),
        ("CHG008", ["transaction/txn_limit.py"], "Transaction"),
        ("CHG011", ["notification/push.py"], "Notification"),
        ("CHG_MULTI", ["payment/payment.py", "auth/login.py"], "Payment"),
    ]
    
    records = []
    for change_id, changed_files, changed_module in scenario_configs:
        affected_files = set(changed_files)
        for row in deps:
            for cf in changed_files:
                if row["source_file"] == cf or row["depends_on"] == cf:
                    affected_files.add(row["source_file"])
                    affected_files.add(row["depends_on"])
                    
        for t in tests:
            directly = t["file_path"] in affected_files
            same_module = t["module"] == changed_module or (change_id == "CHG_MULTI" and t["module"] in ["Payment", "Authentication"])
            indirect = same_module and rng.random() < 0.10
            affected = directly or indirect or (same_module and rng.random() < 0.05)
            
            records.append({
                "test_id": t["test_id"],
                "change_id": change_id,
                "actually_affected": 1 if affected else 0,
                "reason": f"Scenario {change_id}: Direct, dependency or module association"
            })
            
    return records


def _bulk_insert(conn: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    keys = list(rows[0].keys())
    placeholders = ", ".join("?" for _ in keys)
    cols = ", ".join(keys)
    sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
    conn.executemany(sql, [tuple(r[k] for k in keys) for r in rows])


def load_into_db(tests, deps, failures, changes, ground_truth) -> None:
    conn = get_db_connection()
    try:
        for table in ["test_coverage", "dependency_map", "failure_history", "device_matrix", "code_changes", "experiment_ground_truth"]:
            conn.execute(f"DELETE FROM {table}")

        _bulk_insert(conn, "test_coverage", tests)

        device_rows = []
        for d in DEVICES:
            device_rows.append({
                "device_id": d[0], "device_name": d[1], "os_type": d[2],
                "os_version": d[3], "risk_level": d[4], "failure_rate": d[5],
                "last_failure_date": "2025-08-01", "test_count": 0,
            })
        from collections import Counter
        tc = Counter(t["device"] for t in tests)
        for dr in device_rows:
            dr["test_count"] = tc.get(dr["device_name"], 0)
        _bulk_insert(conn, "device_matrix", device_rows)

        _bulk_insert(conn, "dependency_map", deps)
        _bulk_insert(conn, "failure_history", failures)
        _bulk_insert(conn, "code_changes", changes)
        _bulk_insert(conn, "experiment_ground_truth", ground_truth)

        conn.commit()

        # Update metadata counts
        upsert_dataset_metadata("test_coverage", len(tests), "Demo Generator")
        upsert_dataset_metadata("dependency_map", len(deps), "Demo Generator")
        upsert_dataset_metadata("failure_history", len(failures), "Demo Generator")
        upsert_dataset_metadata("device_matrix", len(device_rows), "Demo Generator")
        upsert_dataset_metadata("code_changes", len(changes), "Demo Generator")
    finally:
        conn.close()


def generate_and_load(verbose: bool = True) -> dict:
    initialize_database()
    tests = generate_tests(1000)
    deps = generate_dependencies()
    failures = generate_failure_history(tests)
    changes = generate_code_changes()
    ground_truth = generate_ground_truth(tests, changes, deps)

    load_into_db(tests, deps, failures, changes, ground_truth)

    return {
        "tests": len(tests),
        "dependencies": len(deps),
        "failures": len(failures),
        "changes": len(changes),
        "ground_truth": len(ground_truth),
        "devices": len(DEVICES),
        "modules": len(MODULES),
        "files": len(ALL_FILES),
    }


if __name__ == "__main__":
    result = generate_and_load(verbose=True)
    print("\n=== Demo Dataset Generated and Loaded ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
