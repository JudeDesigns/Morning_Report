"""Append-only audit log — storage/runs/{run_id}/audit.json."""
import uuid
from pathlib import Path

from app.store._base import now_iso, read_json, write_json
from app.store.runs import run_dir


def _audit_path(run_id: str) -> Path:
    return run_dir(run_id) / "audit.json"


def log(
    run_id: str,
    event_type: str,
    message: str = "",
    user_id: str = "",
    entity_type: str = "",
) -> dict:
    events: list = read_json(_audit_path(run_id), [])
    event = {
        "id": str(uuid.uuid4()),
        "run_id": run_id,
        "event_type": event_type,
        "message": message,
        "user_id": user_id,
        "entity_type": entity_type,
        "created_at": now_iso(),
    }
    events.append(event)
    write_json(_audit_path(run_id), events)
    return event


def list_events(run_id: str) -> list:
    return read_json(_audit_path(run_id), [])
