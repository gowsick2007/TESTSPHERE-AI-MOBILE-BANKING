import sys
from fastapi.testclient import TestClient
from backend.main import app

# Dedicated client that never logs in
guest_client = TestClient(app, raise_server_exceptions=False)

# Dedicated client for testing login attempts
login_test_client = TestClient(app, raise_server_exceptions=False)

# Dedicated client for admin
admin_client = TestClient(app, raise_server_exceptions=False)
res_admin = admin_client.post("/api/auth/login", json={"username": "admin", "password": "Admin@123"})
admin_tok = res_admin.json()["token"]
admin_h = {"Authorization": f"Bearer {admin_tok}"}

# Dedicated client for QA
qa_client = TestClient(app, raise_server_exceptions=False)
res_qa = qa_client.post("/api/auth/login", json={"username": "qa", "password": "QA@123"})
qa_tok = res_qa.json()["token"]
qa_h = {"Authorization": f"Bearer {qa_tok}"}

# Dedicated client for viewer
viewer_client = TestClient(app, raise_server_exceptions=False)
res_viewer = viewer_client.post("/api/auth/login", json={"username": "viewer", "password": "View@123"})
viewer_tok = res_viewer.json()["token"]
viewer_h = {"Authorization": f"Bearer {viewer_tok}"}

endpoints_tested = []

def test_endpoint(name, method, url, expected_status, client_to_use, headers=None, json_data=None):
    if method == "GET":
        r = client_to_use.get(url, headers=headers)
    elif method == "POST":
        r = client_to_use.post(url, headers=headers, json=json_data)
    elif method == "DELETE":
        r = client_to_use.delete(url, headers=headers)
    
    status = r.status_code
    passed = (status == expected_status)
    endpoints_tested.append((name, method, url, expected_status, status, passed))
    mark = "PASS" if passed else "FAIL"
    print(f"[{mark}] {name} ({method} {url}) -> Expected: {expected_status}, Got: {status}")
    return r

print("=== STARTING COMPLETE API ENDPOINT VERIFICATION ===")

# 1. Health
test_endpoint("Health Check", "GET", "/api/health", 200, guest_client)

# 2. Auth Login & Check
test_endpoint("Auth Login (Success)", "POST", "/api/auth/login", 200, login_test_client, json_data={"username": "admin", "password": "Admin@123"})
r_bad = test_endpoint("Auth Login (Bad Credentials)", "POST", "/api/auth/login", 200, login_test_client, json_data={"username": "fake", "password": "wrong"})
assert r_bad.json()["success"] is False

test_endpoint("Auth Me (Admin)", "GET", "/api/auth/me", 200, admin_client, headers=admin_h)
r_me_unauth = test_endpoint("Auth Me (Guest)", "GET", "/api/auth/me", 200, guest_client)
assert r_me_unauth.json()["authenticated"] is False

# 3. Data status, template, preview
test_endpoint("Data Status", "GET", "/api/data/status", 200, guest_client)
test_endpoint("Data Template", "GET", "/api/data/template/test_coverage", 200, guest_client)
test_endpoint("Data Preview", "GET", "/api/data/test_coverage/preview", 200, guest_client)

# 4. Data Demo (RBAC)
test_endpoint("Data Demo (Unauth -> 401)", "POST", "/api/data/demo", 401, guest_client)
test_endpoint("Data Demo (Admin -> 200)", "POST", "/api/data/demo", 200, admin_client, headers=admin_h)

# 5. Change Analysis & Register
chg_payload = {
    "changed_files": ["payment/payment.py"],
    "change_type": "MODIFIED",
    "module": "Payment",
    "is_security_sensitive": True,
    "risk_level": "HIGH"
}
test_endpoint("Change Analyze", "POST", "/api/change/analyze", 200, qa_client, headers=qa_h, json_data=chg_payload)
test_endpoint("Change Register (Unauth -> 401)", "POST", "/api/change/register", 401, guest_client, json_data=chg_payload)
test_endpoint("Change Register (Viewer -> 403)", "POST", "/api/change/register", 403, viewer_client, headers=viewer_h, json_data=chg_payload)
test_endpoint("Change Register (QA -> 200)", "POST", "/api/change/register", 200, qa_client, headers=qa_h, json_data=chg_payload)
test_endpoint("Change History", "GET", "/api/change/history", 200, guest_client)

# 6. Test Selection
test_endpoint("Test Selection (Unauth -> 401)", "POST", "/api/tests/selection", 401, guest_client, json_data=chg_payload)
test_endpoint("Test Selection (QA -> 200)", "POST", "/api/tests/selection", 200, qa_client, headers=qa_h, json_data=chg_payload)
test_endpoint("Tests List", "GET", "/api/tests", 200, guest_client)
test_endpoint("Coverage Stats", "GET", "/api/tests/coverage", 200, guest_client)
test_endpoint("Failure Stats", "GET", "/api/tests/failures", 200, guest_client)

# 7. Execution Management
test_endpoint("Execution Plan (Unauth -> 401)", "POST", "/api/execution/plan", 401, guest_client, json_data=chg_payload)
test_endpoint("Execution Plan (Viewer -> 403)", "POST", "/api/execution/plan", 403, viewer_client, headers=viewer_h, json_data=chg_payload)
r_plan = test_endpoint("Execution Plan (QA -> 200)", "POST", "/api/execution/plan", 200, qa_client, headers=qa_h, json_data=chg_payload)
plan_id = r_plan.json()["plan_id"]

test_endpoint("Execution Run SIMULATED (Viewer -> 403)", "POST", "/api/execution/run", 403, viewer_client, headers=viewer_h, json_data={"plan_id": plan_id, "execution_type": "SIMULATED"})
test_endpoint("Execution Run SIMULATED (Admin -> 200)", "POST", "/api/execution/run", 200, admin_client, headers=admin_h, json_data={"plan_id": plan_id, "execution_type": "SIMULATED"})

r_plan2 = test_endpoint("Execution Plan 2 (QA -> 200)", "POST", "/api/execution/plan", 200, qa_client, headers=qa_h, json_data=chg_payload)
plan_id2 = r_plan2.json()["plan_id"]
test_endpoint("Execution Run ACTUAL (501 Unsupported)", "POST", "/api/execution/run", 501, admin_client, headers=admin_h, json_data={"plan_id": plan_id2, "execution_type": "ACTUAL"})
test_endpoint("Execution History", "GET", "/api/execution/history", 200, guest_client)

# 8. Strategy & Rollback
test_endpoint("Strategy Status", "GET", "/api/strategy", 200, guest_client)
test_endpoint("Strategy History", "GET", "/api/strategy/history", 200, guest_client)
test_endpoint("Strategy Versions Catalog (Public)", "GET", "/api/strategy/versions", 200, guest_client)

import uuid

strat_ver_payload = {
    "version_id": f"v-verify-{uuid.uuid4().hex[:6]}",
    "strategy_name": "SMART_SELECTOR_TEST",
    "threshold": 50.0,
    "scoring_weights": {"direct": 40},
    "safety_rules": ["RULE_1_UNKNOWN_DEPENDENCY"],
    "description": "Verification test"
}
test_endpoint("Strategy Versions Create (Unauth -> 401)", "POST", "/api/strategy/versions", 401, guest_client, json_data=strat_ver_payload)
test_endpoint("Strategy Versions Create (QA -> 403)", "POST", "/api/strategy/versions", 403, qa_client, headers=qa_h, json_data=strat_ver_payload)
test_endpoint("Strategy Versions Create (Admin -> 200)", "POST", "/api/strategy/versions", 200, admin_client, headers=admin_h, json_data=strat_ver_payload)

test_endpoint("Strategy Rollback (Viewer -> 403)", "POST", "/api/strategy/rollback", 403, viewer_client, headers=viewer_h, json_data={"to_strategy": "LEGACY_FULL_SUITE", "reason": "Viewer attempt"})
test_endpoint("Strategy Rollback (Admin -> 200)", "POST", "/api/strategy/rollback", 200, admin_client, headers=admin_h, json_data={"to_strategy": "LEGACY_FULL_SUITE", "reason": "Admin test"})
test_endpoint("Strategy Restore (Admin -> 200)", "POST", "/api/strategy/rollback", 200, admin_client, headers=admin_h, json_data={"to_strategy": "SMART_SELECTOR", "reason": "Admin restore"})

# 9. Audit & Feedback
test_endpoint("Audit Logs (Unauth -> 401)", "GET", "/api/audit/logs", 401, guest_client)
test_endpoint("Audit Logs (Viewer -> 403)", "GET", "/api/audit/logs", 403, viewer_client, headers=viewer_h)
test_endpoint("Audit Logs (QA -> 200)", "GET", "/api/audit/logs", 200, qa_client, headers=qa_h)
test_endpoint("Audit Logs (Admin -> 200)", "GET", "/api/audit/logs", 200, admin_client, headers=admin_h)

fb_payload = {
    "reviewer_name": "QA Principal",
    "project_area": "Test Selection",
    "rating": 5,
    "comments": "Audited and verified",
    "linked_entity_id": "CHG001"
}
test_endpoint("Feedback (Unauth -> 401)", "POST", "/api/audit/feedback", 401, guest_client, json_data=fb_payload)
test_endpoint("Feedback (Viewer -> 200)", "POST", "/api/audit/feedback", 200, viewer_client, headers=viewer_h, json_data=fb_payload)
test_endpoint("Feedback List", "GET", "/api/audit/feedback/list", 200, guest_client)
test_endpoint("Feedback Stats", "GET", "/api/audit/feedback/stats", 200, guest_client)

# 10. Analytics & Simulation
test_endpoint("Threshold Sensitivity", "GET", "/api/analytics/threshold-sensitivity?change_id=CHG001", 200, guest_client)
test_endpoint("What-If (Unauth -> 401)", "POST", "/api/what-if", 401, guest_client, json_data={"module": "Payment", "device": "Pixel 8", "change_type": "MODIFIED", "risk_level": "HIGH", "is_security_sensitive": True})
test_endpoint("What-If (QA -> 200)", "POST", "/api/what-if", 200, qa_client, headers=qa_h, json_data={"module": "Payment", "device": "Pixel 8", "change_type": "MODIFIED", "risk_level": "HIGH", "is_security_sensitive": True})
test_endpoint("Experiment Scenarios", "POST", "/api/experiment/run-scenarios", 200, qa_client, headers=qa_h)

total = len(endpoints_tested)
passed_count = sum(1 for e in endpoints_tested if e[5])
print(f"\nAPI VERIFICATION SUMMARY: {passed_count}/{total} endpoints passed")
if passed_count == total:
    print("ALL API ENDPOINTS IMPLEMENTED AND VERIFIED!")
else:
    sys.exit(1)
