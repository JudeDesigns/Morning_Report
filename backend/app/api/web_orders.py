from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user, require_roles
from app.store import runs as run_store, results as result_store, audit as audit_store
from app.services import web_orders as wo_service

router = APIRouter(prefix="/web-orders", tags=["web-orders"])

# PRD §17.2 — roles that may run processing
_PROCESS_ROLES = ("admin", "accounting", "office", "management")


def _resolve(run_id: str, current_user: dict) -> dict:
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.get("workflow_type") != "web_orders_check":
        raise HTTPException(400, "Run is not a web orders run")
    if current_user.get("role") != "admin" and run.get("created_by") != current_user["id"]:
        raise HTTPException(403, "Access denied")
    return run


@router.post("/{run_id}/process")
async def process_web_orders(
    run_id: str,
    current_user: dict = Depends(require_roles(*_PROCESS_ROLES)),
):
    run = _resolve(run_id, current_user)
    run_store.update_run(run_id, {"status": "processing"})
    audit_store.log(run_id, "processing_started", "Web orders processing started", current_user["id"])

    outcome = await wo_service.process_run(run_id)

    if not outcome.get("success"):
        run_store.update_run(run_id, {"status": "validation_failed"})
        audit_store.log(run_id, "processing_failed", str(outcome.get("errors")), current_user["id"])
        raise HTTPException(422, detail=outcome.get("errors"))

    audit_store.log(run_id, "processing_complete", f"Processed {outcome.get('total_rows', 0)} rows", current_user["id"])
    return outcome


@router.get("/{run_id}/lines")
async def get_web_order_lines(
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    _resolve(run_id, current_user)
    return result_store.load(run_id, "web_orders_lines", [])


@router.get("/{run_id}/summary")
async def get_web_orders_summary(
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    _resolve(run_id, current_user)
    lines = result_store.load(run_id, "web_orders_lines", [])
    meta = result_store.load(run_id, "web_orders_meta", {})
    return {
        "total": len(lines),
        "same_day": sum(1 for l in lines if not l.get("is_future") and not l.get("is_spacer")),
        "future": sum(1 for l in lines if l.get("is_future")),
        "problematic": sum(1 for l in lines if l.get("is_problematic")),
        "warnings": meta.get("warnings") or [],
        "reference_sheets": meta.get("reference_sheets") or {},
    }
