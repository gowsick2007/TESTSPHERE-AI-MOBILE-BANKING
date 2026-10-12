import urllib.request
import sys

base = 'http://127.0.0.1:8001'
pages = [
    '/',
    '/frontend/css/main.css',
    '/frontend/css/components.css',
    '/frontend/css/dashboard.css',
    '/frontend/css/tables.css',
    '/frontend/js/api.js',
    '/frontend/js/navigation.js',
    '/frontend/pages/dashboard.html',
    '/frontend/pages/data-management.html',
    '/frontend/pages/change-analysis.html',
    '/frontend/pages/test-selector.html',
    '/frontend/pages/dependency-graph.html',
    '/frontend/pages/coverage.html',
    '/frontend/pages/failure-intelligence.html',
    '/frontend/pages/experiment-lab.html',
    '/frontend/pages/rollback.html',
    '/frontend/pages/audit-security.html',
    '/frontend/pages/documentation.html',
]

all_ok = True
for p in pages:
    url = base + p
    try:
        with urllib.request.urlopen(url) as res:
            data = res.read()
            print(f"[{res.status}] {p} ({len(data)} bytes)")
    except Exception as e:
        print(f"[FAIL] {p}: {e}")
        all_ok = False

if all_ok:
    print("\n[SUCCESS] All 18 frontend static assets and pages verified OK!")
else:
    print("\n[FAIL] Some frontend assets failed.")
    sys.exit(1)
