"""Store-layer unit tests — no DB, no network, no file I/O beyond temp dir."""
import os
import tempfile
import pytest

STORAGE = tempfile.mkdtemp()
os.environ.setdefault("STORAGE_PATH", STORAGE)
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-store-tests")


# ---------------------------------------------------------------------------
# _base.py
# ---------------------------------------------------------------------------
def test_base_decimal_serialisation():
    from pathlib import Path
    from decimal import Decimal
    from datetime import date
    from app.store._base import write_json, read_json

    p = Path(STORAGE) / "base_test.json"
    write_json(p, {"amount": Decimal("12.34"), "d": date(2025, 1, 15), "none": None})
    loaded = read_json(p)
    assert loaded["amount"] == 12.34, "Decimal should become float"
    assert loaded["d"] == "2025-01-15", "date should become ISO string"
    assert loaded["none"] is None


def test_base_missing_file_returns_default():
    from pathlib import Path
    from app.store._base import read_json

    p = Path(STORAGE) / "nonexistent.json"
    assert read_json(p, []) == []
    assert read_json(p) is None


# ---------------------------------------------------------------------------
# runs.py
# ---------------------------------------------------------------------------
def test_run_crud_and_filter():
    from app.store import runs as rs

    r = rs.create_run("web_orders_check", "Test Run", "2025-01-15", created_by="user1")
    assert r["status"] == "draft"
    assert r["workflow_type"] == "web_orders_check"

    fetched = rs.get_run(r["id"])
    assert fetched["name"] == "Test Run"

    updated = rs.update_run(r["id"], {"status": "processing"})
    assert updated["status"] == "processing"

    all_runs = rs.list_runs(workflow_type="web_orders_check")
    assert any(x["id"] == r["id"] for x in all_runs)

    deleted = rs.delete_run(r["id"])
    assert deleted
    assert rs.get_run(r["id"]) is None


def test_run_increment_file_count():
    from app.store import runs as rs

    r = rs.create_run("jetro_reconciliation", "Jetro", "2025-02-01")
    rs.increment_file_count(r["id"], 1)
    rs.increment_file_count(r["id"], 1)
    updated = rs.get_run(r["id"])
    assert updated["file_count"] == 2
    rs.increment_file_count(r["id"], -1)
    assert rs.get_run(r["id"])["file_count"] == 1
    rs.delete_run(r["id"])


# ---------------------------------------------------------------------------
# users.py
# ---------------------------------------------------------------------------
def test_user_crud_and_duplicate_rejection():
    from app.store import users as us

    u = us.create_user("alice@br.com", "Alice", "hashed-pw", "admin")
    assert u["email"] == "alice@br.com"
    assert u["role"] == "admin"

    assert us.get_user_by_email("alice@br.com") is not None
    assert us.get_user_by_id(u["id"])["name"] == "Alice"

    with pytest.raises(ValueError):
        us.create_user("alice@br.com", "Alice2", "pw", "admin")


# ---------------------------------------------------------------------------
# files_meta.py
# ---------------------------------------------------------------------------
def test_files_meta_crud():
    from app.store import runs as rs, files_meta as fm

    r = rs.create_run("vendor_bill_po_bank", "VB Run", "2025-03-01")
    f = fm.add_file(r["id"], "quickbooks_po_export", "po.xlsx", "/tmp/po.xlsx", "application/vnd.ms-excel")
    assert f["file_type"] == "quickbooks_po_export"

    listed = fm.list_files(r["id"])
    assert len(listed) == 1

    by_type = fm.get_file_by_type(r["id"], "quickbooks_po_export")
    assert by_type["id"] == f["id"]

    assert fm.get_file(r["id"], f["id"])["original_filename"] == "po.xlsx"

    deleted = fm.delete_file(r["id"], f["id"])
    assert deleted
    assert fm.list_files(r["id"]) == []

    rs.delete_run(r["id"])


# ---------------------------------------------------------------------------
# results.py
# ---------------------------------------------------------------------------
def test_results_save_load_exists():
    from app.store import runs as rs, results as res

    r = rs.create_run("jetro_reconciliation", "Jetro2", "2025-04-01")
    res.save(r["id"], "jetro_invoices", [{"invoice_number": "INV-001"}])

    loaded = res.load(r["id"], "jetro_invoices", [])
    assert loaded[0]["invoice_number"] == "INV-001"
    assert res.exists(r["id"], "jetro_invoices")
    assert not res.exists(r["id"], "no_such_key")

    res.append(r["id"], "jetro_invoices", [{"invoice_number": "INV-002"}])
    assert len(res.load(r["id"], "jetro_invoices")) == 2

    rs.delete_run(r["id"])


# ---------------------------------------------------------------------------
# audit.py
# ---------------------------------------------------------------------------
def test_audit_log_and_list():
    from app.store import runs as rs, audit as au

    r = rs.create_run("combined_price_changes", "CP Run", "2025-05-01")
    evt = au.log(r["id"], "run_created", "Run created", "user1")
    assert evt["event_type"] == "run_created"

    events = au.list_events(r["id"])
    assert len(events) == 1
    assert events[0]["message"] == "Run created"

    rs.delete_run(r["id"])
