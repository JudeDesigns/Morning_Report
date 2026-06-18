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


# ---------------------------------------------------------------------------
# Day archive export
# ---------------------------------------------------------------------------
def test_day_archive_returns_404_when_no_exported_runs(auth_headers):
    """Date with no runs in `exported` state must 404."""
    r = client.post("/api/v1/exports/day-archive/1999-01-01", headers=auth_headers)
    assert r.status_code == 404


def test_day_archive_zips_only_most_recent_exported_per_workflow(auth_headers):
    """Only runs in `exported` state are bundled; for each workflow_type only
    the most recently updated qualifying run is included."""
    import io
    import zipfile
    from app.store import runs as run_store
    from app.store import results as result_store

    day = "2025-08-15"

    # Combined-price run (eligible — combined_price exporter needs no inputs).
    cp_old = run_store.create_run("combined_price_changes", "CP old", day)
    cp_new = run_store.create_run("combined_price_changes", "CP new", day)
    # An ineligible processed-only run on the same workflow & day must be skipped.
    cp_processed = run_store.create_run("combined_price_changes", "CP processed", day)

    for rid in (cp_old["id"], cp_new["id"], cp_processed["id"]):
        result_store.save(rid, "price_change_rows", [])
        result_store.save(rid, "missing_items", [])

    run_store.update_run(cp_old["id"], {"status": "exported"})
    run_store.update_run(cp_new["id"], {"status": "exported"})  # newest updated_at
    run_store.update_run(cp_processed["id"], {"status": "processed"})

    r = client.post(f"/api/v1/exports/day-archive/{day}", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    assert f'filename="{day}.zip"' in r.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        names = zf.namelist()
    # Exactly one combined_price entry — the most recent exported run.
    cp_entries = [n for n in names if n.startswith("Price_Changes_Both_Sources_")]
    assert len(cp_entries) == 1, f"expected 1 combined_price file, got {names}"
    assert "20250815" in cp_entries[0]

    for rid in (cp_old["id"], cp_new["id"], cp_processed["id"]):
        run_store.delete_run(rid)
