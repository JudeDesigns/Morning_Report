"""Uploaded file metadata — stored per-run in storage/runs/{run_id}/files.json."""
import uuid
from pathlib import Path
from typing import Optional

from app.store._base import now_iso, read_json, write_json
from app.store.runs import run_dir


def _files_path(run_id: str) -> Path:
    return run_dir(run_id) / "files.json"


def _load(run_id: str) -> list:
    return read_json(_files_path(run_id), [])


def _save(run_id: str, records: list) -> None:
    write_json(_files_path(run_id), records)


# ── Public API ────────────────────────────────────────────────────────────────

def list_files(run_id: str) -> list:
    return _load(run_id)


def get_file(run_id: str, file_id: str) -> Optional[dict]:
    return next((f for f in _load(run_id) if f["id"] == file_id), None)


def get_file_by_type(run_id: str, file_type: str) -> Optional[dict]:
    """Return first file matching file_type for this run."""
    return next((f for f in _load(run_id) if f["file_type"] == file_type), None)


def get_files_by_type(run_id: str, file_type: str) -> list:
    """Return all files matching file_type (e.g. multiple RD invoices)."""
    return [f for f in _load(run_id) if f["file_type"] == file_type]


def add_file(
    run_id: str,
    file_type: str,
    original_filename: str,
    storage_path: str,
    mime_type: Optional[str] = None,
    sha256: Optional[str] = None,
    uploaded_by: Optional[str] = None,
) -> dict:
    records = _load(run_id)
    record = {
        "id": str(uuid.uuid4()),
        "run_id": run_id,
        "file_type": file_type,
        "original_filename": original_filename,
        "storage_path": storage_path,
        "mime_type": mime_type,
        "sha256": sha256,
        "uploaded_by": uploaded_by,
        "uploaded_at": now_iso(),
        "parse_status": "pending",
    }
    records.append(record)
    _save(run_id, records)
    return record


def update_file(run_id: str, file_id: str, updates: dict) -> Optional[dict]:
    records = _load(run_id)
    for i, f in enumerate(records):
        if f["id"] == file_id:
            records[i] = {**f, **updates}
            _save(run_id, records)
            return records[i]
    return None


def delete_file(run_id: str, file_id: str) -> bool:
    records = _load(run_id)
    new_records = [f for f in records if f["id"] != file_id]
    if len(new_records) == len(records):
        return False
    _save(run_id, new_records)
    return True
