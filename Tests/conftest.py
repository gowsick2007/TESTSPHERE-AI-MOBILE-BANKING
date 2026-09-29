"""
TestSphere AI — Pytest Configuration & Fixture Hub
Provides deterministic, isolated fixtures for:
- FastAPI TestClient
- Database connection & clean state
- Authenticated RBAC roles (ADMIN, QA_ENGINEER, VIEWER)
- Sample datasets & CSV fixtures
"""
import pytest
import sqlite3
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import get_db_connection, initialize_database
from backend.api.auth_routes import SESSIONS
from Data_Generation.generate_dataset import generate_and_load

BASE_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def session_init_db():
    """Ensure baseline database and demo data are initialized once per test session."""
    initialize_database()
    generate_and_load(seed=12345, load_db=True, verbose=False)


@pytest.fixture
def client():
    """FastAPI TestClient instance."""
    return TestClient(app)


@pytest.fixture
def db_conn():
    """Direct SQLite database connection with row factory."""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def auth_tokens(client):
    """
    Login helper that provisions verified session tokens for all RBAC roles.
    """
    res_admin = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@123"})
    assert res_admin.status_code == 200, f"Admin login failed: {res_admin.text}"
    admin_tok = res_admin.json()["token"]

    res_qa = client.post("/api/auth/login", json={"username": "qa", "password": "QA@123"})
    assert res_qa.status_code == 200, f"QA login failed: {res_qa.text}"
    qa_tok = res_qa.json()["token"]

    res_viewer = client.post("/api/auth/login", json={"username": "viewer", "password": "View@123"})
    assert res_viewer.status_code == 200, f"Viewer login failed: {res_viewer.text}"
    viewer_tok = res_viewer.json()["token"]

    return {
        "admin": admin_tok,
        "qa": qa_tok,
        "viewer": viewer_tok,
    }


@pytest.fixture
def admin_headers(auth_tokens):
    return {"Authorization": f"Bearer {auth_tokens['admin']}"}


@pytest.fixture
def qa_headers(auth_tokens):
    return {"Authorization": f"Bearer {auth_tokens['qa']}"}


@pytest.fixture
def viewer_headers(auth_tokens):
    return {"Authorization": f"Bearer {auth_tokens['viewer']}"}


@pytest.fixture
def invalid_headers():
    return {"Authorization": "Bearer invalid_unauthorized_token_xyz"}


@pytest.fixture
def sample_change_payload():
    return {
        "changed_files": ["payment/payment.py"],
        "change_type": "MODIFIED",
        "module": "Payment",
        "is_security_sensitive": False,
        "risk_level": "HIGH",
    }


@pytest.fixture
def sample_auth_change_payload():
    return {
        "changed_files": ["auth/login.py"],
        "change_type": "MODIFIED",
        "module": "Authentication",
        "is_security_sensitive": True,
        "risk_level": "HIGH",
    }


@pytest.fixture
def unauth_client():
    """TestClient instance guaranteed to have no authentication headers or session cookies."""
    return TestClient(app)


@pytest.fixture
def admin_client(auth_tokens):
    """TestClient instance pre-configured with ADMIN Authorization header."""
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {auth_tokens['admin']}"
    return c


@pytest.fixture
def qa_client(auth_tokens):
    """TestClient instance pre-configured with QA_ENGINEER Authorization header."""
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {auth_tokens['qa']}"
    return c


@pytest.fixture
def viewer_client(auth_tokens):
    """TestClient instance pre-configured with VIEWER Authorization header."""
    c = TestClient(app)
    c.headers["Authorization"] = f"Bearer {auth_tokens['viewer']}"
    return c


@pytest.fixture
def missing_token_headers():
    """Empty headers dict simulating missing token."""
    return {}


@pytest.fixture
def temp_db():
    """Provides a clean temporary isolated SQLite database connection with row factory."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = f.name
    conn = sqlite3.connect(temp_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
        try:
            Path(temp_path).unlink(missing_ok=True)
        except Exception:
            pass


@pytest.fixture
def sample_csv(tmp_path):
    """Provides a valid test_coverage CSV file."""
    csv_file = tmp_path / "sample_test_coverage.csv"
    csv_file.write_text(
        "test_id,test_name,file_path,module,device,os_version,execution_time\n"
        "TC-001,test_auth_success,auth/login.py,Authentication,Pixel 8,Android 15,0.45\n"
        "TC-002,test_payment_checkout,payment/payment.py,Payment,Samsung S24,Android 15,0.85\n",
        encoding="utf-8"
    )
    return csv_file


@pytest.fixture
def temp_dataset_dir(tmp_path):
    """Temporary directory for deterministic dataset generation verification."""
    d = tmp_path / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def experiment_state():
    """Canonical experiment configuration state for tests."""
    return {
        "scenario": "CHG001_Payment",
        "changed_files": ["payment/payment.py"],
        "module": "Payment",
        "is_security_sensitive": True,
        "risk_level": "HIGH",
        "threshold": 50.0,
        "seed": 12345,
    }


@pytest.fixture
def canonical_dir():
    return BASE_DIR / "Dataset" / "synthetic_canonical"

