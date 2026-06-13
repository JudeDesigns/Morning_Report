"""Run CRUD — each run lives in storage/runs/{run_id}/run.json.
A flat index at storage/runs-index.json enables fast listing.
"""
import shutil
import uuid
from pathlib import Path
from typing import Optional

from app.store._base import now_iso, read_json, write_json


def _storage() -> Path:
    from app.config import settings
    p = Path(settings.STORAGE_PATH)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _index_path() -> Path:
    return _storage() / "runs-index.json"


def run_dir(run_id: str) -> Path:
    d = _storage() / "runs" / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _run_path(run_id: str) -> Path:
    return _storage() / "runs" / run_id / "run.json"


def _index_entry(run: dict) -> dict:
    return {k: run.get(k) for k in
            ["id", "workflow_type", "name", "run_date", "status", "updated_at"]}


def _upsert_index(run: dict) -> None:
    idx: list = read_json(_index_path(), [])
    pos = next((i for i, r in enumerate(idx) if r["id"] == run["id"]), None)
    entry = _index_entry(run)
    if pos is not None:
        idx[pos] = entry
    else:
        idx.insert(0, entry)
    write_json(_index_path(), idx)


# ── Public API ────────────────────────────────────────────────────────────────

def create_run(
    workflow_type: str,
    name: str,
    run_date: str,
    notes: Optional[str] = None,
    created_by: Optional[str] = None,
) -> dict:
    run_id = str(uuid.uuid4())
    now = now_iso()
    run = {
        "id": run_id,
        "workflow_type": workflow_type,
        "name": name,
        "run_date": run_date,
        "status": "draft",
        "notes": notes,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
        "file_count": 0,
    }
    run_dir(run_id)
    write_json(_run_path(run_id), run)
    _upsert_index(run)
    return run


def get_run(run_id: str) -> Optional[dict]:
    return read_json(_run_path(run_id))


def list_runs(
    workflow_type: Optional[str] = None,
    status: Optional[str] = None,
) -> list:
    idx: list = read_json(_index_path(), [])
    if workflow_type:
        idx = [r for r in idx if r.get("workflow_type") == workflow_type]
    if status:
        idx = [r for r in idx if r.get("status") == status]
    idx.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
    # Enrich with file_count from each run.json
    result = []
    for entry in idx:
        full = get_run(entry["id"])
        if full:
            result.append(full)
    return result


def update_run(run_id: str, updates: dict) -> Optional[dict]:
    run = get_run(run_id)
    if run is None:
        return None
    run.update(updates)
    run["updated_at"] = now_iso()
    write_json(_run_path(run_id), run)
    _upsert_index(run)
    return run


def delete_run(run_id: str) -> bool:
    d = _storage() / "runs" / run_id
    if not d.exists():
        return False
    shutil.rmtree(d)
    idx: list = read_json(_index_path(), [])
    write_json(_index_path(), [r for r in idx if r["id"] != run_id])
    return True


def record_override(
    run_id: str,
    *,
    check: str,
    reason: str,
    user_id: str,
    original_value=None,
    affected_rows: Optional[list] = None,
) -> Optional[dict]:
    """PRD §16.3 — record an authorized override of a blocking validation.

    Overrides are stored on the run under `overrides` and persisted atomically.
    """
    run = get_run(run_id)
    if run is None:
        return None
    overrides = run.get("overrides") or []
    overrides.append({
        "id": str(uuid.uuid4()),
        "check": check,
        "reason": reason,
        "user_id": user_id,
        "original_value": original_value,
        "affected_rows": affected_rows or [],
        "created_at": now_iso(),
    })
    run["overrides"] = overrides
    run["updated_at"] = now_iso()
    write_json(_run_path(run_id), run)
    _upsert_index(run)
    return run


def has_override(run_id: str, check: str) -> bool:
    run = get_run(run_id)
    if not run:
        return False
    return any(o.get("check") == check for o in (run.get("overrides") or []))


def increment_file_count(run_id: str, delta: int = 1) -> None:
    run = get_run(run_id)
    if run:
        run["file_count"] = run.get("file_count", 0) + delta
        run["updated_at"] = now_iso()
        if run.get("status") == "draft" and delta > 0:
            run["status"] = "files_uploaded"
        write_json(_run_path(run_id), run)
        _upsert_index(run)
