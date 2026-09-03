import urllib.request
import urllib.error
import json
import sqlite3
from datetime import datetime

API_ROOT = "http://127.0.0.1:8001/api"
results = {}

def encode_multipart_formdata(fields, files):
    boundary = b'----WebKitFormBoundary7MA4YWxkTrZu0gW'
    lines = []
    for name, value in fields.items():
        lines.append(b'--' + boundary)
        lines.append(f'Content-Disposition: form-data; name="{name}"'.encode('utf-8'))
        lines.append(b'')
        lines.append(str(value).encode('utf-8'))
    for name, filename, file_content in files:
        lines.append(b'--' + boundary)
        lines.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'.encode('utf-8'))
        lines.append(b'Content-Type: text/csv')
        lines.append(b'')
        lines.append(file_content)
    lines.append(b'--' + boundary + b'--')
    body = b'\r\n'.join(lines)
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary.decode("utf-8")}',
        'Content-Length': str(len(body))
    }
    return body, headers

def make_request(url, data=None, headers=None, method='GET', cookie=None):
    if headers is None:
        headers = {}
    if cookie:
        headers['Cookie'] = cookie
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as res:
            res_headers = res.info()
            set_cookie = res_headers.get('Set-Cookie')
            body = res.read().decode('utf-8')
            return res.status, body, set_cookie
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8'), None
    except Exception as e:
        return 0, str(e), None

print("=== STARTING END-TO-END VALIDATION ===")

# 1. Login
login_payload = json.dumps({"username": "admin", "password": "Admin@123"}).encode('utf-8')
status, body, set_cookie = make_request(f"{API_ROOT}/auth/login", data=login_payload, headers={'Content-Type': 'application/json'}, method='POST')
print(f"1. Login Status: {status}")
if status == 200:
    res_json = json.loads(body)
    token = res_json.get('token')
    results['Login'] = ("PASS", f"Status 200, Token: {token[:10]}...")
else:
    results['Login'] = ("FAIL", f"Status {status}: {body}")
    token = None

# 2. Authentication check
if token:
    status, body, _ = make_request(f"{API_ROOT}/auth/me", cookie=set_cookie)
    print(f"2. Auth Me Status: {status}")
    if status == 200:
        results['Authentication'] = ("PASS", f"Status 200: {body}")
    else:
        results['Authentication'] = ("FAIL", f"Status {status}: {body}")
else:
    results['Authentication'] = ("FAIL", "Skipped (no token)")

# 3. Dataset status
status, body, _ = make_request(f"{API_ROOT}/data/status")
print(f"3. Dataset Status Code: {status}")
if status == 200:
    results['Dataset status'] = ("PASS", "Status 200")
else:
    results['Dataset status'] = ("FAIL", f"Status {status}: {body}")

# CSV Content for upload tests
csv_content = (
    "test_id,test_name,file_path,module,device,os_version,execution_time,"
    "source_file,depends_on,failure_date,severity,device_id,device_name,"
    "os_type,risk_level,failure_rate,change_id,change_type,changed_at\n"
    "T101,Verify Login,auth.py,Auth,iPhone,15.2,1.5,"
    "auth.py,db.py,2026-08-01,HIGH,D01,iPhone,iOS,LOW,0.02,CHG-T01,MODIFIED,2026-08-01 12:00:00\n"
).encode('utf-8')

# 4. Dataset upload preview (commit=false)
if token:
    body_data, upload_headers = encode_multipart_formdata({}, [('file', 'test_dataset.csv', csv_content)])
    status, body, _ = make_request(f"{API_ROOT}/data/upload/full?commit=false&token={token}", data=body_data, headers=upload_headers, method='POST')
    print(f"4. Dataset upload preview Status: {status}")
    if status == 200:
        results['Dataset upload preview'] = ("PASS", "Status 200")
    else:
        results['Dataset upload preview'] = ("FAIL", f"Status {status}: {body}")
else:
    results['Dataset upload preview'] = ("FAIL", "Skipped (no token)")

# 5. Dataset import (commit=true)
if token:
    body_data, upload_headers = encode_multipart_formdata({}, [('file', 'test_dataset.csv', csv_content)])
    status, body, _ = make_request(f"{API_ROOT}/data/upload/full?commit=true&token={token}", data=body_data, headers=upload_headers, method='POST')
    print(f"5. Dataset import Status: {status}")
    if status == 200:
        results['Dataset import'] = ("PASS", "Status 200")
    else:
        results['Dataset import'] = ("FAIL", f"Status {status}: {body}")
else:
    results['Dataset import'] = ("FAIL", "Skipped (no token)")

# 6. Delete one dataset table (DELETE /api/data/code_changes)
if token:
    status, body, _ = make_request(f"{API_ROOT}/data/code_changes?token={token}", method='DELETE')
    print(f"6. Delete table Status: {status}")
    if status == 200:
        results['Delete dataset table'] = ("PASS", "Status 200")
    else:
        results['Delete dataset table'] = ("FAIL", f"Status {status}: {body}")
else:
    results['Delete dataset table'] = ("FAIL", "Skipped (no token)")

# 7. Verify audit_log contains timestamp for the delete event
try:
    conn = sqlite3.connect("Data/testsphere.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 5")
    rows = cursor.fetchall()
    print("Recent Audit Logs in SQLite:")
    found_timestamp = False
    for r in rows:
        print(f"  ID: {r['id']}, Timestamp: {r['timestamp']}, Action: {r['action']}, Username: {r['username']}")
        if r['action'] == 'CLEAR_DATASET' and r['timestamp']:
            found_timestamp = True
    conn.close()
    if found_timestamp:
        results['Audit log timestamp'] = ("PASS", "Found timestamp for delete event")
    else:
        results['Audit log timestamp'] = ("FAIL", "Delete event timestamp not found or null")
except Exception as e:
    results['Audit log timestamp'] = ("FAIL", f"Database error: {str(e)}")

# 8. Change analysis
change_payload = {
    "changed_files": ["auth.py"],
    "change_type": "MODIFIED",
    "module": "Auth",
    "is_security_sensitive": True,
    "risk_level": "HIGH"
}
status, body, _ = make_request(f"{API_ROOT}/change/analyze", data=json.dumps(change_payload).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
print(f"8. Change Analysis Status: {status}")
if status == 200:
    results['Change analysis'] = ("PASS", "Status 200")
else:
    results['Change analysis'] = ("FAIL", f"Status {status}: {body}")

# 9. Change registration
if token:
    status, body, _ = make_request(f"{API_ROOT}/change/register?token={token}", data=json.dumps(change_payload).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
    print(f"9. Change Registration Status: {status}")
    if status == 200:
        results['Change registration'] = ("PASS", f"Status 200: {body}")
    else:
        results['Change registration'] = ("FAIL", f"Status {status}: {body}")
else:
    results['Change registration'] = ("FAIL", "Skipped (no token)")

# 10. Test selection
status, body, _ = make_request(f"{API_ROOT}/tests/selection", data=json.dumps(change_payload).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
print(f"10. Test Selection Status: {status}")
if status == 200:
    results['Test selection'] = ("PASS", "Status 200")
else:
    results['Test selection'] = ("FAIL", f"Status {status}: {body}")

# 11. Dependency Graph (GET /api/data/dependency_map/preview)
status, body, _ = make_request(f"{API_ROOT}/data/dependency_map/preview")
print(f"11. Dependency Graph Status: {status}")
if status == 200:
    results['Dependency Graph'] = ("PASS", "Status 200")
else:
    results['Dependency Graph'] = ("FAIL", f"Status {status}: {body}")

# 12. Experiment Lab
if token:
    status, body, _ = make_request(f"{API_ROOT}/experiment/run-scenarios?token={token}", method='POST')
    print(f"12. Experiment Run Scenarios Status: {status}")
    if status == 200:
        results['Experiment Lab'] = ("PASS", "Status 200")
    else:
        results['Experiment Lab'] = ("FAIL", f"Status {status}: {body}")
else:
    results['Experiment Lab'] = ("FAIL", "Skipped (no token)")

# 13. What-if analysis
whatif_payload = {
    "module": "Auth",
    "device": "iPhone",
    "change_type": "MODIFIED",
    "risk_level": "HIGH",
    "is_security_sensitive": True
}
status, body, _ = make_request(f"{API_ROOT}/what-if", data=json.dumps(whatif_payload).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
print(f"13. What-If Status: {status}")
if status == 200:
    results['What-if analysis'] = ("PASS", "Status 200")
else:
    results['What-if analysis'] = ("FAIL", f"Status {status}: {body}")

# Final summary print
print("\n=== FINAL RESULTS SUMMARY ===")
for test_name, (verdict, info) in results.items():
    print(f"{test_name}: {verdict} ({info})")
