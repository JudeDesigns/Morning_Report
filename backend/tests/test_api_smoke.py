"""API smoke tests — no real files, no AI calls, no DB."""
import os
import tempfile
import pytest

STORAGE = tempfile.mkdtemp()
os.environ.setdefault("STORAGE_PATH", STORAGE)
os.environ.setdefault("SECRET_KEY", "api-smoke-test-secret-key-xyz")

from fastapi.testclient import TestClient
from app.main import app
from app.store import users as user_store
from app.core.security import get_password_hash, create_access_token
from datetime import timedelta

client = TestClient(app)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def admin_token():
    """Create admin user and return a valid JWT."""
    try:
        user_store.create_user("admin@test.com", "Admin User", get_password_hash("admin1234"), "admin")
    except ValueError:
        pass  # already exists from a previous test run
    token = create_access_token(
        data={"sub": user_store.get_user_by_email("admin@test.com")["id"]},
        expires_delta=timedelta(minutes=60),
    )
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def test_login_wrong_password(auth_headers):
    r = client.post("/api/v1/auth/login", data={"username": "admin@test.com", "password": "wrong"})
    assert r.status_code == 401


def test_login_success():
    r = client.post("/api/v1/auth/login", data={"username": "admin@test.com", "password": "admin1234"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["user"]["role"] == "admin"


def test_me(auth_headers):
    r = client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "admin@test.com"


def test_register_requires_admin():
    # No auth header -> 403
    r = client.post("/api/v1/auth/register", json={
        "email": "new@test.com", "name": "New", "password": "pass1234", "role": "office"
    })
    assert r.status_code in (401, 403)


def test_register_weak_password(auth_headers):
    r = client.post("/api/v1/auth/register", json={
        "email": "weak@test.com", "name": "Weak", "password": "short", "role": "office"
    }, headers=auth_headers)
    assert r.status_code == 422  # validation error


# ---------------------------------------------------------------------------
# Runs CRUD
# ---------------------------------------------------------------------------
def test_create_and_get_run(auth_headers):
    r = client.post("/api/v1/runs", json={
        "workflow_type": "web_orders_check",
        "name": "Smoke Test Run",
        "run_date": "2025-06-01",
    }, headers=auth_headers)
    assert r.status_code == 201
    run = r.json()
    assert run["status"] == "draft"
    run_id = run["id"]

    r2 = client.get(f"/api/v1/runs/{run_id}", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["name"] == "Smoke Test Run"

    return run_id


def test_list_runs_with_filter(auth_headers):
    r = client.get("/api/v1/runs?workflow_type=web_orders_check", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_run_invalid_workflow(auth_headers):
    r = client.post("/api/v1/runs", json={
        "workflow_type": "invalid_type",
        "name": "Bad Run",
        "run_date": "2025-06-01",
    }, headers=auth_headers)
    assert r.status_code == 422


def test_delete_run_requires_admin(auth_headers):
    # Create a run and then delete it
    r = client.post("/api/v1/runs", json={
        "workflow_type": "jetro_reconciliation",
        "name": "Delete Me",
        "run_date": "2025-06-15",
    }, headers=auth_headers)
    assert r.status_code == 201
    run_id = r.json()["id"]
    del_r = client.delete(f"/api/v1/runs/{run_id}", headers=auth_headers)
    assert del_r.status_code == 204


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
def test_audit_trail_for_run(auth_headers):
    r = client.post("/api/v1/runs", json={
        "workflow_type": "combined_price_changes",
        "name": "Audit Test Run",
        "run_date": "2025-07-01",
    }, headers=auth_headers)
    run_id = r.json()["id"]

    audit_r = client.get(f"/api/v1/audit/run/{run_id}", headers=auth_headers)
    assert audit_r.status_code == 200
    events = audit_r.json()
    assert any(e["event_type"] == "run_created" for e in events)
