from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from app.core.auth import get_current_user, require_roles
from app.store import runs as run_store, audit as audit_store

router = APIRouter(prefix="/runs", tags=["runs"])

WORKFLOW_TYPES = [
    "web_orders_check", "jetro_reconciliation",
    "vendor_bill_po_bank", "combined_price_changes",
]
VALID_STATUSES = [
    "draft", "files_uploaded", "extraction_pending", "extraction_review",
    "ready_to_process", "processing", "validation_failed",
    "processed", "exported", "archived",
]


class RunCreate(BaseModel):
    workflow_type: str
    name: str
    run_date: date
    notes: Optional[str] = None

    @field_validator("workflow_type")
    @classmethod
    def validate_workflow_type(cls, v: str) -> str:
        if v not in WORKFLOW_TYPES:
            raise ValueError(f"workflow_type must be one of {WORKFLOW_TYPES}")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 200:
            raise ValueError("name must be 1–200 characters")
        return v


class RunUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        return v


def _resolve(run_id: str, current_user: dict) -> dict:
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    # Non-admins can only see runs they created
    if current_user.get("role") != "admin" and run.get("created_by") != current_user["id"]:
        raise HTTPException(403, "Access denied")
    return run


@router.post("", status_code=201)
async def create_run(
    data: RunCreate,
    current_user: dict = Depends(get_current_user),
):
    run = run_store.create_run(
        workflow_type=data.workflow_type,
        name=data.name,
        run_date=str(data.run_date),
        notes=data.notes,
        created_by=current_user["id"],
    )
    audit_store.log(run["id"], "run_created", f"Run '{run['name']}' created", current_user["id"])
    return run


@router.get("", response_model=List[dict])
async def list_runs(
    workflow_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    runs = run_store.list_runs(workflow_type=workflow_type, status=status)
    # Non-admins see only their own runs
    if current_user.get("role") != "admin":
        runs = [r for r in runs if r.get("created_by") == current_user["id"]]
    return runs


@router.get("/{run_id}")
async def get_run(
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    return _resolve(run_id, current_user)


@router.patch("/{run_id}")
async def update_run(
    run_id: str,
    data: RunUpdate,
    current_user: dict = Depends(get_current_user),
):
    _resolve(run_id, current_user)
    updates = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    run = run_store.update_run(run_id, updates)
    audit_store.log(run_id, "run_updated", str(updates), current_user["id"])
    return run


@router.delete("/{run_id}", status_code=204)
async def delete_run(
    run_id: str,
    current_user: dict = Depends(require_roles("admin", "accounting")),
):
    if not run_store.delete_run(run_id):
        raise HTTPException(404, "Run not found")
    audit_store.log(run_id, "run_deleted", "Run deleted", current_user["id"])


class OverrideRequest(BaseModel):
    check: str
    reason: str
    original_value: Optional[str] = None
    affected_rows: Optional[List[str]] = None

    @field_validator("check")
    @classmethod
    def validate_check(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("check must not be empty")
        return v.strip()

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 5:
            raise ValueError("reason must be at least 5 characters")
        return v


@router.post("/{run_id}/override")
async def record_override(
    run_id: str,
    data: OverrideRequest,
    current_user: dict = Depends(require_roles("admin", "accounting")),
):
    """PRD §16.3 — authorized override of a blocking validation."""
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    updated = run_store.record_override(
        run_id,
        check=data.check,
        reason=data.reason,
        user_id=current_user["id"],
        original_value=data.original_value,
        affected_rows=data.affected_rows,
    )
    audit_store.log(
        run_id, "override_recorded",
        f"Override '{data.check}' by {current_user['email']}: {data.reason}",
        current_user["id"],
    )
    return {"success": True, "overrides": updated.get("overrides") if updated else []}
