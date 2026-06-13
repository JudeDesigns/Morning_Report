from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.auth import get_current_user, require_roles
from app.store import runs as run_store, results as result_store, audit as audit_store
from app.services import combined_price as cp_service

router = APIRouter(prefix="/combined-price", tags=["combined-price"])

_PROCESS_ROLES = ("admin", "accounting", "office", "management")


class ProcessRequest(BaseModel):
    jetro_run_id: Optional[str] = None
    vendor_run_id: Optional[str] = None


def _resolve(run_id: str, current_user: dict) -> dict:
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.get("workflow_type") != "combined_price_changes":
        raise HTTPException(400, "Run is not a combined price run")
    if current_user.get("role") != "admin" and run.get("created_by") != current_user["id"]:
        raise HTTPException(403, "Access denied")
    return run


@router.post("/{run_id}/process")
async def process_combined_price(
    run_id: str,
    request: ProcessRequest,
    current_user: dict = Depends(require_roles(*_PROCESS_ROLES)),
):
    _resolve(run_id, current_user)
    if not request.jetro_run_id and not request.vendor_run_id:
        raise HTTPException(400, "At least one source run ID (jetro_run_id or vendor_run_id) is required")

    run_store.update_run(run_id, {"status": "processing"})
    audit_store.log(run_id, "processing_started", "Combined price processing started", current_user["id"])

    outcome = await cp_service.process_run(
        run_id,
        jetro_run_id=request.jetro_run_id,
        vendor_run_id=request.vendor_run_id,
    )

    if not outcome.get("success"):
        run_store.update_run(run_id, {"status": "validation_failed"})
        audit_store.log(run_id, "processing_failed", str(outcome.get("errors")), current_user["id"])
        raise HTTPException(422, detail=outcome.get("errors"))

    audit_store.log(run_id, "processing_complete",
                    f"{outcome.get('total_changes', 0)} price changes found", current_user["id"])
    return outcome


@router.get("/{run_id}/rows")
async def get_price_change_rows(run_id: str, current_user: dict = Depends(get_current_user)):
    _resolve(run_id, current_user)
    return result_store.load(run_id, "combined_price_rows", [])
