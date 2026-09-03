"""
TestSphere AI — Test full API save flow via HTTP
"""
import sys, io, json, urllib.request
sys.path.insert(0, '.')

CSV = b"""test_id,test_name,file_path,module,device,os_version,execution_time,source_file,depends_on,failure_date,severity,device_id,device_name,os_type,risk_level,failure_rate,change_id,change_type
T001,Login Test,auth/login.py,Authentication,Pixel 8,Android 15,1.5,auth/login.py,db/user.py,2026-01-15,HIGH,D001,Pixel 8,Android,HIGH,0.05,CHG001,MODIFIED
T002,Payment Test,payment/pay.py,Payment,iPhone 15,iOS 18,2.0,payment/pay.py,auth/login.py,2026-02-10,CRITICAL,D002,iPhone 15,iOS,HIGH,0.08,CHG002,ADDED
"""

def make_multipart(csv_bytes, filename=b'test.csv'):
    bnd = b'boundary12345'
    disp = b'Content-Disposition: form-data; name="file"; filename="' + filename + b'"'
    ctype = b'Content-Type: text/csv'
    body = (b'--' + bnd + b'\r\n' + disp + b'\r\n' + ctype + b'\r\n\r\n' +
            csv_bytes + b'\r\n--' + bnd + b'--')
    ct = 'multipart/form-data; boundary=boundary12345'
    return body, ct

def post(url, body, ct):
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Content-Type', ct)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

body, ct = make_multipart(CSV)

# Test commit=false (analyze)
status, data = post('http://127.0.0.1:8001/api/data/upload/full?commit=false', body, ct)
print(f'ANALYZE: HTTP {status}')
print(f'  success={data.get("success")} status={data.get("status")}')
print(f'  coverage={data.get("coverage")}')
print(f'  is_valid={data.get("is_valid_to_save")}')

# Test commit=true (save)
body2, ct2 = make_multipart(CSV)
status2, data2 = post('http://127.0.0.1:8001/api/data/upload/full?commit=true', body2, ct2)
print(f'\nSAVE: HTTP {status2}')
if status2 == 200:
    print(f'  SUCCESS updated_tables={data2.get("updated_tables")}')
else:
    detail = data2.get('detail', data2)
    if isinstance(detail, dict):
        print(f'  FAILED status={detail.get("status")} message={detail.get("message")}')
        print(f'  technical_detail={detail.get("technical_detail")}')
        print(f'  issues={detail.get("issues")}')
    else:
        print(f'  FAILED detail={str(detail)[:500]}')
