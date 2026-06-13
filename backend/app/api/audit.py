"""Audit log API — reads the per-run append-only audit.json."""
from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user, require_roles
from app.store import runs as run_store, audit as audit_store

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/run/{run_id}")
async def get_run_audit_trail(
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Return all audit events for a run (chronological order)."""
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    # Non-admins can only view audit for their own runs
    if current_user.get("role") != "admin" and run.get("created_by") != current_user["id"]:
        raise HTTPException(403, "Access denied")
    events = audit_store.list_events(run_id)
    return sorted(events, key=lambda e: e.get("created_at", ""))
