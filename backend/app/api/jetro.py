from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user, require_roles
from app.store import runs as run_store, results as result_store, audit as audit_store
from app.services import jetro as jetro_service

router = APIRouter(prefix="/jetro", tags=["jetro"])

_PROCESS_ROLES = ("admin", "accounting", "office", "management")


def _resolve(run_id: str, current_user: dict) -> dict:
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.get("workflow_type") != "jetro_reconciliation":
        raise HTTPException(400, "Run is not a Jetro run")
    if current_user.get("role") != "admin" and run.get("created_by") != current_user["id"]:
        raise HTTPException(403, "Access denied")
    return run


@router.post("/{run_id}/process")
async def process_jetro(
    run_id: str,
    current_user: dict = Depends(require_roles(*_PROCESS_ROLES)),
):
    _resolve(run_id, current_user)
    run_store.update_run(run_id, {"status": "processing"})
    audit_store.log(run_id, "processing_started", "Jetro processing started", current_user["id"])

    outcome = await jetro_service.process_run(run_id)
    if not outcome.get("success"):
        run_store.update_run(run_id, {"status": "validation_failed"})
        audit_store.log(run_id, "processing_failed", str(outcome.get("errors")), current_user["id"])
        raise HTTPException(422, detail=outcome.get("errors"))

    audit_store.log(run_id, "processing_complete",
                    f"Processed {outcome.get('invoices', 0)} invoices", current_user["id"])
    return outcome


@router.get("/{run_id}/invoices")
async def list_invoices(run_id: str, current_user: dict = Depends(get_current_user)):
    _resolve(run_id, current_user)
    return result_store.load(run_id, "jetro_invoices", [])


@router.get("/{run_id}/issues")
async def list_issues(run_id: str, current_user: dict = Depends(get_current_user)):
    _resolve(run_id, current_user)
    return result_store.load(run_id, "jetro_issues", [])


@router.get("/{run_id}/price-updates")
async def list_price_updates(run_id: str, current_user: dict = Depends(get_current_user)):
    _resolve(run_id, current_user)
    return result_store.load(run_id, "jetro_price_updates", [])


@router.get("/{run_id}/coupons")
async def list_coupons(run_id: str, current_user: dict = Depends(get_current_user)):
    _resolve(run_id, current_user)
    return result_store.load(run_id, "jetro_coupons", [])


@router.get("/{run_id}/summary")
async def get_jetro_summary(run_id: str, current_user: dict = Depends(get_current_user)):
    _resolve(run_id, current_user)
    invoices = result_store.load(run_id, "jetro_invoices", [])
    issues = result_store.load(run_id, "jetro_issues", [])
    coupons = result_store.load(run_id, "jetro_coupons", [])
    price_updates = result_store.load(run_id, "jetro_price_updates", [])
    return {
        "invoices": len(invoices),
        "credit_invoices": sum(1 for i in invoices if i.get("invoice_type") == "credit"),
        "invoice_total": sum(i.get("printed_grand_total") or 0 for i in invoices),
        "integrity_ok": all(i.get("integrity_status") == "ok" for i in invoices) if invoices else True,
        "missing": sum(1 for i in issues if i.get("issue_type") == "Missing"),
        "extra": sum(1 for i in issues if i.get("issue_type") == "Extra"),
        "qty_mismatch": sum(1 for i in issues if i.get("issue_type") == "Qty mismatch"),
        "coupons": len(coupons),
        "total_coupon_savings": sum(c.get("invoice_total_savings") or 0 for c in coupons),
        "price_changes": len(price_updates),
    }
