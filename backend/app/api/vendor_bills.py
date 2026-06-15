from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.auth import get_current_user, require_roles
from app.store import runs as run_store, results as result_store, audit as audit_store
from app.services import vendor_bills as vb_service

router = APIRouter(prefix="/vendor-bills", tags=["vendor-bills"])

_PROCESS_ROLES = ("admin", "accounting", "office", "management")


class BillLineUpdate(BaseModel):
    bill_item_code: Optional[str] = None
    description: Optional[str] = None
    qty: Optional[float] = None
    rate: Optional[float] = None
    total: Optional[float] = None
    user_confirmed: Optional[bool] = None
    forced_po_id: Optional[str] = None  # PO id to force-match, or "NOT_ON_PO" to mark explicitly


class BillConfirmRequest(BaseModel):
    vendor_confirmed: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None


def _resolve(run_id: str, current_user: dict) -> dict:
    run = run_store.get_run(run_id)
    if not run or run.get("workflow_type") != "vendor_bill_po_bank":
        raise HTTPException(404, "Run not found or wrong workflow type")
    if current_user.get("role") != "admin" and run.get("created_by") != current_user["id"]:
        raise HTTPException(403, "Access denied")
    return run


# ── PO Bank ──────────────────────────────────────────────────────────────────

@router.post("/{run_id}/load-po")
async def load_po_export(
    run_id: str,
    current_user: dict = Depends(require_roles(*_PROCESS_ROLES)),
):
    """Parse the uploaded QB PO export and populate the PO Bank."""
    _resolve(run_id, current_user)
    outcome = await vb_service.process_po_upload(run_id)
    if not outcome.get("success"):
        raise HTTPException(422, detail=outcome.get("errors"))
    audit_store.log(run_id, "po_loaded",
                    f"PO bank loaded: {outcome.get('product_lines', 0)} rows", current_user["id"])
    return outcome


@router.get("/{run_id}/po-bank")
async def get_po_bank(run_id: str, current_user: dict = Depends(get_current_user)):
    _resolve(run_id, current_user)
    return result_store.load(run_id, "po_bank", [])


# ── Bill extraction ───────────────────────────────────────────────────────────

@router.post("/{run_id}/extract-bill/{file_id}")
async def extract_bill(
    run_id: str, file_id: str,
    current_user: dict = Depends(require_roles(*_PROCESS_ROLES)),
):
    """Trigger Claude AI extraction on a vendor bill image/PDF."""
    _resolve(run_id, current_user)
    outcome = await vb_service.extract_bill_image(run_id, file_id)
    audit_store.log(run_id, "bill_extracted", f"Bill extracted from file {file_id}", current_user["id"])
    return outcome


@router.get("/{run_id}/bills")
async def list_bills(run_id: str, current_user: dict = Depends(get_current_user)):
    _resolve(run_id, current_user)
    bills = result_store.load(run_id, "vendor_bills", [])
    return [
        {k: b.get(k) for k in [
            "id", "source_file_id", "vendor_extracted", "vendor_confirmed",
            "invoice_number", "invoice_date", "bill_type", "extraction_status",
            "header_confidence", "header_needs_review",
        ]}
        for b in bills
    ]


@router.get("/{run_id}/bills/{bill_id}/lines")
async def get_bill_lines(
    run_id: str, bill_id: str, current_user: dict = Depends(get_current_user)
):
    _resolve(run_id, current_user)
    bills = result_store.load(run_id, "vendor_bills", [])
    bill = next((b for b in bills if b["id"] == bill_id), None)
    if not bill:
        raise HTTPException(404, "Bill not found")
    return bill.get("lines", [])


@router.patch("/{run_id}/bills/{bill_id}/lines/{line_id}")
async def update_bill_line(
    run_id: str, bill_id: str, line_id: str,
    update: BillLineUpdate,
    current_user: dict = Depends(get_current_user),
):
    _resolve(run_id, current_user)
    bills = result_store.load(run_id, "vendor_bills", [])
    bill = next((b for b in bills if b["id"] == bill_id), None)
    if not bill:
        raise HTTPException(404, "Bill not found")
    line = next((l for l in bill.get("lines", []) if l["id"] == line_id), None)
    if not line:
        raise HTTPException(404, "Line not found")
    line.update({k: v for k, v in update.model_dump(exclude_unset=True).items()})
    result_store.save(run_id, "vendor_bills", bills)
    audit_store.log(run_id, "bill_line_updated", f"Line {line_id} updated", current_user["id"])
    return {"success": True}


@router.delete("/{run_id}/bills/{bill_id}/lines/{line_id}")
async def delete_bill_line(
    run_id: str, bill_id: str, line_id: str,
    current_user: dict = Depends(get_current_user),
):
    _resolve(run_id, current_user)
    bills = result_store.load(run_id, "vendor_bills", [])
    bill = next((b for b in bills if b["id"] == bill_id), None)
    if not bill:
        raise HTTPException(404, "Bill not found")
    original = len(bill.get("lines", []))
    bill["lines"] = [l for l in bill.get("lines", []) if l["id"] != line_id]
    if len(bill["lines"]) == original:
        raise HTTPException(404, "Line not found")
    result_store.save(run_id, "vendor_bills", bills)
    audit_store.log(run_id, "bill_line_deleted", f"Line {line_id} deleted", current_user["id"])
    return {"success": True}


@router.post("/{run_id}/bills/{bill_id}/confirm")
async def confirm_bill_header(
    run_id: str, bill_id: str,
    data: BillConfirmRequest,
    current_user: dict = Depends(get_current_user),
):
    """Confirm extracted bill header after human review."""
    _resolve(run_id, current_user)
    bills = result_store.load(run_id, "vendor_bills", [])
    bill = next((b for b in bills if b["id"] == bill_id), None)
    if not bill:
        raise HTTPException(404, "Bill not found")
    for field in ["vendor_confirmed", "invoice_number", "invoice_date"]:
        val = getattr(data, field)
        if val is not None:
            bill[field] = val
    result_store.save(run_id, "vendor_bills", bills)
    audit_store.log(run_id, "bill_header_confirmed", f"Bill {bill_id} confirmed", current_user["id"])
    return {"success": True}


@router.post("/{run_id}/bills/{bill_id}/ai-match")
async def ai_match_bill(
    run_id: str, bill_id: str,
    current_user: dict = Depends(require_roles(*_PROCESS_ROLES)),
):
    """Use Claude to suggest the best PO match for each line of this bill."""
    _resolve(run_id, current_user)
    outcome = await vb_service.ai_match_bill_lines(run_id, bill_id)
    if not outcome.get("success"):
        raise HTTPException(422, detail=outcome.get("errors"))
    audit_store.log(run_id, "ai_match_requested", f"AI match requested for bill {bill_id}", current_user["id"])
    return outcome


@router.delete("/{run_id}/bills/{bill_id}", status_code=204)
async def delete_bill(
    run_id: str, bill_id: str,
    current_user: dict = Depends(require_roles(*_PROCESS_ROLES)),
):
    """Delete an extracted bill and restore any matched PO rows to unprocessed."""
    _resolve(run_id, current_user)
    outcome = vb_service.delete_bill(run_id, bill_id)
    if not outcome.get("success"):
        raise HTTPException(404, detail=outcome.get("errors"))
    audit_store.log(run_id, "bill_deleted", f"Bill {bill_id} deleted", current_user["id"])


@router.get("/{run_id}/import-rows")
async def get_import_rows(run_id: str, current_user: dict = Depends(get_current_user)):
    """Return bill import rows (live preview of what will appear in the export workbook)."""
    _resolve(run_id, current_user)
    rows = result_store.load(run_id, "bill_import_rows", [])
    return sorted(rows, key=lambda r: r.get("line") or 0)


@router.post("/{run_id}/bills/{bill_id}/process")
async def process_bill(
    run_id: str, bill_id: str,
    current_user: dict = Depends(require_roles(*_PROCESS_ROLES)),
):
    """Match confirmed bill lines to PO Bank and generate import rows."""
    _resolve(run_id, current_user)
    outcome = await vb_service.process_confirmed_bill(run_id, bill_id)
    if not outcome.get("success"):
        raise HTTPException(422, detail=outcome.get("errors"))
    audit_store.log(run_id, "bill_processed", f"Bill {bill_id} matched to PO Bank", current_user["id"])
    return outcome


@router.post("/{run_id}/finalize")
async def finalize_run(
    run_id: str,
    current_user: dict = Depends(require_roles(*_PROCESS_ROLES)),
):
    """Mark the run as ready to export. Safe to call before all bills arrive —
    use Reopen after export to add more."""
    _resolve(run_id, current_user)
    outcome = vb_service.finalize_run(run_id)
    if not outcome.get("success"):
        raise HTTPException(422, detail=outcome.get("errors"))
    audit_store.log(run_id, "run_finalized",
                    f"Run finalized; {outcome.get('processed_bills', 0)} bill(s) matched",
                    current_user["id"])
    return outcome


@router.post("/{run_id}/reopen")
async def reopen_run(
    run_id: str,
    current_user: dict = Depends(require_roles("admin", "accounting")),
):
    """Undo the export finalize sweep so additional bills can be added."""
    run = _resolve(run_id, current_user)
    if run.get("status") != "exported":
        raise HTTPException(409, "Run is not in 'exported' state")
    outcome = vb_service.reopen_run(run_id)
    audit_store.log(
        run_id, "run_reopened",
        f"Run reopened; {outcome.get('reverted_pos', 0)} PO(s) restored to unprocessed",
        current_user["id"],
    )
    return outcome
