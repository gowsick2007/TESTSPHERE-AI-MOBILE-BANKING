import urllib.request
import json

payload = {
    "changed_files": ["payment/payment_service.py"],
    "change_type": "MODIFIED",
    "module": "payment",
    "is_security_sensitive": True,
    "risk_level": "HIGH"
}

data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(
    'http://127.0.0.1:8001/api/change/register',
    data=data,
    headers={'Content-Type': 'application/json'},
    method='POST'
)

try:
    with urllib.request.urlopen(req) as response:
        print("Status Code:", response.status)
        print("Response:", json.loads(response.read().decode()))
except urllib.error.HTTPError as e:
    print("HTTP Error Code:", e.code)
    print("Error Detail:", e.read().decode())
except Exception as e:
    print("Error:", e)
