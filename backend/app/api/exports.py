from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse as FastAPIFileResponse
from app.core.auth import get_current_user, require_roles
from app.store import runs as run_store, results as result_store, audit as audit_store
from app.services import web_orders as wo_service
from app.services import jetro as jetro_service
from app.services import vendor_bills as vb_service
from app.services import combined_price as cp_service

router = APIRouter(prefix="/exports", tags=["exports"])

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_WORKFLOW_TYPES = {
    "web_orders_check": "web orders",
    "jetro_reconciliation": "Jetro reconciliation",
    "vendor_bill_po_bank": "vendor bills",
    "combined_price_changes": "combined price",
}
# Roles that may export per PRD §17.2
_EXPORT_ROLES = ("admin", "accounting", "office", "management")


def _resolve(run_id: str, expected_workflow: str, current_user: dict) -> dict:
    run = run_store.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.get("workflow_type") != expected_workflow:
        raise HTTPException(400, f"Run is not a {_WORKFLOW_TYPES.get(expected_workflow)} run")
    if current_user.get("role") != "admin" and run.get("created_by") != current_user["id"]:
        raise HTTPException(403, "Access denied")
    if run.get("status") not in ("processed", "exported"):
        raise HTTPException(409, "Run has not been processed yet — process it first")
    return run


def _check_integrity(run_id: str, workflow_type: str) -> None:
    """PRD §7.3/§16.1 — block export if blocking validation failed and no override."""
    if workflow_type == "jetro_reconciliation":
        invoices = result_store.load(run_id, "jetro_invoices", [])
        bad = [i for i in invoices if i.get("integrity_status") != "ok"]
        if bad and not run_store.has_override(run_id, "jetro_integrity_mismatch"):
            invoice_nums = ", ".join(str(i.get("invoice_number")) for i in bad)
            raise HTTPException(
                409,
                detail={
                    "error": "integrity_mismatch",
                    "message": (
                        f"Grand total mismatch on invoice(s) {invoice_nums}. "
                        "Resolve the discrepancy or record an authorized override "
                        "(POST /runs/{run_id}/override with check='jetro_integrity_mismatch') before exporting."
                    ),
                    "invoices": [i.get("invoice_number") for i in bad],
                },
            )


def _send(file_path: str, filename: str) -> FastAPIFileResponse:
    p = Path(file_path)
    if not p.exists():
        raise HTTPException(500, "Export file not found on disk — try re-exporting")
    return FastAPIFileResponse(path=str(p), filename=filename, media_type=XLSX_MEDIA)


@router.post("/web-orders/{run_id}")
async def export_web_orders(
    run_id: str,
    current_user: dict = Depends(require_roles(*_EXPORT_ROLES)),
):
    run = _resolve(run_id, "web_orders_check", current_user)
    _check_integrity(run_id, "web_orders_check")
    file_path = await wo_service.export_workbook(run_id)
    run_store.update_run(run_id, {"status": "exported"})
    audit_store.log(run_id, "exported", "Web orders workbook exported", current_user["id"])
    date_str = (run.get("run_date") or "").replace("-", "")
    return _send(file_path, f"Web_Orders_Check_{date_str}.xlsx")


@router.post("/jetro/{run_id}")
async def export_jetro(
    run_id: str,
    current_user: dict = Depends(require_roles(*_EXPORT_ROLES)),
):
    run = _resolve(run_id, "jetro_reconciliation", current_user)
    _check_integrity(run_id, "jetro_reconciliation")
    file_path = await jetro_service.export_workbook(run_id)
    run_store.update_run(run_id, {"status": "exported"})
    audit_store.log(run_id, "exported", "Jetro workbook exported", current_user["id"])
    date_str = (run.get("run_date") or "").replace("-", "")
    return _send(file_path, f"Jetro_Restaurant_Depot_Reconciliation_{date_str}.xlsx")


@router.post("/vendor-bills/{run_id}")
async def export_vendor_bills(
    run_id: str,
    current_user: dict = Depends(require_roles(*_EXPORT_ROLES)),
):
    run = _resolve(run_id, "vendor_bill_po_bank", current_user)
    _check_integrity(run_id, "vendor_bill_po_bank")
    file_path = await vb_service.export_workbook(run_id)
    run_store.update_run(run_id, {"status": "exported"})
    audit_store.log(run_id, "exported", "Vendor bills workbook exported", current_user["id"])
    date_str = (run.get("run_date") or "").replace("-", "")
    return _send(file_path, f"QB_Vendor_Bill_Import_{date_str}_Accumulating.xlsx")


@router.post("/combined-price/{run_id}")
async def export_combined_price(
    run_id: str,
    current_user: dict = Depends(require_roles(*_EXPORT_ROLES)),
):
    run = _resolve(run_id, "combined_price_changes", current_user)
    _check_integrity(run_id, "combined_price_changes")
    file_path = await cp_service.export_workbook(run_id)
    run_store.update_run(run_id, {"status": "exported"})
    audit_store.log(run_id, "exported", "Combined price workbook exported", current_user["id"])
    date_str = (run.get("run_date") or "").replace("-", "")
    return _send(file_path, f"Price_Changes_Both_Sources_{date_str}.xlsx")
