"""Vendor Bills / PO Bank service (PRD Module C) — file-based, no DB."""
import types
import uuid as _uuid_mod
from datetime import datetime, timezone
from io import BytesIO
from decimal import Decimal
import openpyxl

from app.services.storage import read_file
from app.services.vendor_bills.parser import parse_po_export
from app.services.vendor_bills.matcher import (
    match_bill_line_to_po, compute_discrepancies, normalize_vendor,
)
from app.services.vendor_bills.exporter import generate_workbook
from app.services.ai_extraction import extract_vendor_bill, flag_low_confidence
from app.store import files_meta as file_store, results as result_store
from app.store.runs import get_run, update_run



def _f(v) -> float | None:
    return float(v) if v is not None else None


async def process_po_upload(run_id: str) -> dict:
    """Parse QB PO export XLSX → PO Bank + Office/Driver tasks (JSON store)."""
    file_rec = file_store.get_file_by_type(run_id, "quickbooks_po_export")
    if not file_rec:
        return {"success": False, "errors": ["No QB PO export file uploaded yet"]}

    content = await read_file(file_rec["storage_path"])
    wb = openpyxl.load_workbook(BytesIO(content), data_only=True)
    parsed = parse_po_export(wb)

    po_rows = []
    for pl in parsed["product_lines"]:
        txn = pl.get("txn_date")
        po_rows.append({
            "id": str(_uuid_mod.uuid4()),
            "terms": pl.get("terms"),
            "ref_number": pl.get("ref_number"),
            "txn_date": txn.isoformat() if hasattr(txn, "isoformat") else txn,
            "vendor": pl.get("vendor"),
            "memo": pl.get("memo"),
            "total_amount": _f(pl.get("total_amount")),
            "po_cost": _f(pl.get("po_cost")),
            "description": pl.get("description"),
            "item_code": pl.get("item_code"),
            "quantity": _f(pl.get("quantity")),
            "class_name": pl.get("class_name"),
            "case_avg_weight": _f(pl.get("case_avg_weight")),
            "unit_avg_weight": _f(pl.get("unit_avg_weight")),
            "status": "unprocessed",
        })

    office_tasks = [
        {
            "vendor_name": t.get("vendor_name"), "ref_number": t.get("ref_number"),
            "task_type": t.get("task_type"), "item": t.get("item"),
            "need_review": t.get("need_review"), "task_instructions": t.get("task_instructions"),
        }
        for t in parsed.get("office_tasks", [])
    ]

    result_store.save(run_id, "po_bank", po_rows)
    result_store.save(run_id, "office_tasks", office_tasks)
    update_run(run_id, {"status": "files_uploaded"})

    return {"success": True, "product_lines": len(po_rows), "office_tasks": len(office_tasks)}


async def extract_bill_image(run_id: str, file_id: str) -> dict:
    """Run Claude AI extraction on vendor bill image/PDF → save for human review."""
    file_rec = file_store.get_file(run_id, file_id)
    if not file_rec:
        return {"success": False, "errors": ["File not found"]}

    content = await read_file(file_rec["storage_path"])
    extracted = await extract_vendor_bill(content, file_rec.get("mime_type") or "image/jpeg")
    extracted = flag_low_confidence(extracted)

    bill_id = str(_uuid_mod.uuid4())
    lines = []
    for i, line in enumerate(extracted.get("lines", [])):
        weights = line.get("individual_weights")
        lines.append({
            "id": str(_uuid_mod.uuid4()),
            "source_line_number": i,
            "bill_item_code": line.get("bill_item_code"),
            "description": line.get("description"),
            "qty": _f(line.get("qty")),
            "rate": _f(line.get("rate")),
            "total": _f(line.get("total")),
            "is_credit": bool(line.get("is_credit")),
            "individual_weights": [float(w) for w in weights] if weights else None,
            "notes": line.get("notes"),
            "confidence": _f(line.get("confidence")),
            "field_confidence": line.get("field_confidence") or {},
            "field_needs_review": line.get("field_needs_review") or [],
            "needs_review": bool(line.get("needs_review")),
            "user_confirmed": False,
            "match_status": None,
        })

    bill = {
        "id": bill_id,
        "source_file_id": file_id,
        "vendor_extracted": extracted.get("vendor"),
        "vendor_confirmed": None,
        "invoice_number": extracted.get("invoice_number"),
        "invoice_date": None,
        "bill_type": extracted.get("bill_type", "invoice"),
        "extraction_status": "review",
        "header_confidence": extracted.get("header_confidence") or {},
        "header_needs_review": extracted.get("header_needs_review") or [],
        "lines": lines,
    }

    bills = result_store.load(run_id, "vendor_bills", [])
    bills.append(bill)
    result_store.save(run_id, "vendor_bills", bills)

    return {
        "bill_id": bill_id,
        "extracted": extracted,
        "has_low_confidence": extracted.get("has_low_confidence", False),
    }


async def process_confirmed_bill(run_id: str, bill_id: str) -> dict:
    """Match confirmed bill lines to PO Bank → generate QB import rows, summary, weights."""
    bills = result_store.load(run_id, "vendor_bills", [])
    bill = next((b for b in bills if b["id"] == bill_id), None)
    if not bill:
        return {"success": False, "errors": ["Bill not found"]}

    bill_lines = bill.get("lines", [])
    # Only lines flagged for review require explicit user sign-off.
    # High-confidence lines (needs_review=False) are auto-approved.
    unconfirmed_review = [l for l in bill_lines if l.get("needs_review") and not l.get("user_confirmed")]
    if unconfirmed_review:
        return {
            "success": False,
            "errors": [
                f"{len(unconfirmed_review)} flagged line(s) still need review — "
                "open the Review dialog and check the OK checkbox for each highlighted row."
            ],
        }

    po_rows = result_store.load(run_id, "po_bank", [])

    # If this bill was already processed, undo its previous effects so re-processing is clean.
    # This prevents duplicate rows when the button is clicked more than once.
    prev_matched_po_ids = {
        bl.get("matched_po_id") for bl in bill.get("lines", [])
        if bl.get("matched_po_id")
    }
    if prev_matched_po_ids:
        for po in po_rows:
            if po.get("id") in prev_matched_po_ids:
                po["status"] = "unprocessed"
                po.pop("processed_bill_id", None)

    # Reset line match state so we start fresh
    for bl in bill.get("lines", []):
        bl["match_status"] = None
        bl.pop("matched_po_id", None)

    po_unprocessed = [r for r in po_rows if r.get("status") == "unprocessed"]

    vendor_name = bill.get("vendor_confirmed") or bill.get("vendor_extracted") or ""
    summary_items: list = []

    # Load accumulators, stripping any rows previously produced by this bill
    import_rows = [r for r in result_store.load(run_id, "bill_import_rows", [])
                   if r.get("bill_id") != bill_id]
    weight_rows = [r for r in result_store.load(run_id, "weight_rows", [])
                   if r.get("bill_id") != bill_id]
    cost_comparison = [r for r in result_store.load(run_id, "cost_comparison", [])
                       if r.get("bill_id") != bill_id]
    summary_blocks = [b for b in result_store.load(run_id, "vendor_summary_blocks", [])
                      if b.get("bill_id") != bill_id]
    import_line_num = len(import_rows) + 1

    for bl in bill_lines:
        bl_dict = {
            "bill_item_code": bl.get("bill_item_code"),
            "description": bl.get("description"),
            "qty": bl.get("qty"),
            "rate": bl.get("rate"),
            "total": bl.get("total"),
        }

        # User manually assigned a PO (or explicitly marked "Not on PO")
        forced = bl.get("forced_po_id")
        if forced == "NOT_ON_PO":
            matched_po, _conf, _reason = None, 1.0, "Manually marked as not on PO"
        elif forced:
            matched_po = next((p for p in po_rows if p["id"] == forced), None)
            _conf, _reason = (1.0, "Manually assigned by user") if matched_po else (0.0, "Forced PO not found")
        else:
            matched_po, _conf, _reason = match_bill_line_to_po(bl_dict, po_unprocessed, vendor_name)

        highlight = None
        item_code = None

        if matched_po:
            bl["matched_po_id"] = matched_po["id"]
            bl["match_status"] = "matched"
            item_code = matched_po.get("item_code")
            po_cost_val = matched_po.get("po_cost")

            # Mark PO row as processed in-place
            for po in po_rows:
                if po["id"] == matched_po["id"]:
                    po["status"] = "processed"
                    po["processed_bill_id"] = bill_id
                    break

            disc = compute_discrepancies(bl_dict, matched_po, vendor_name)
            # Tag every item with bill metadata so the All Issues sheet can
            # render vendor/invoice/PO references without a back-lookup.
            disc["bill_id"] = bill_id
            disc["vendor"] = vendor_name
            disc["invoice_number"] = bill.get("invoice_number")
            if disc.get("section") or disc.get("has_qty_mismatch"):
                summary_items.append(disc)

            bill_rate = float(bl.get("rate") or 0)
            po_c = float(po_cost_val or 0)
            diff = bill_rate - po_c
            pct = (diff / po_c * 100) if po_c != 0 else None
            cost_comparison.append({
                "bill_id": bill_id,
                "item_code": item_code,
                "description": matched_po.get("description"),
                "vendor": vendor_name,
                "po_cost": po_c,
                "vendor_bill_cost": bill_rate,
                "difference": diff,
                "percent_change": pct,
            })
        else:
            bl["match_status"] = "not_on_po"
            highlight = "not_on_po"

        desc_parts = [matched_po.get("description", "") if matched_po else "", bl.get("description") or ""]
        desc = "\n".join(p for p in desc_parts if p).strip()
        iw = bl.get("individual_weights")
        if iw:
            desc += "\nweights: " + "+".join(f"{w:.2f}" for w in iw)
            weight_rows.append({
                "bill_id": bill_id,
                "item_code_po": item_code,
                "item_code_bill": bl.get("bill_item_code"),
                "product_name_po": matched_po.get("description") if matched_po else None,
                "weights": iw,
                "total": sum(iw),
            })

        import_rows.append({
            "line": import_line_num,
            "bill_id": bill_id,
            "item_code": item_code,
            "description": desc,
            "price": bl.get("rate"),
            "qty": bl.get("qty"),
            "total": bl.get("total"),
            "ref": bill.get("invoice_number"),
            "date": bill.get("invoice_date"),
            "vendor": vendor_name,
            "type": "Inventory Part",
            "highlight_status": highlight,
        })
        import_line_num += 1

    # NOTE: PRD §10.7/§10.12 — remaining unprocessed POs for the vendor are NOT
    # flagged here. A vendor may split delivery across multiple bills in the same
    # run; leftover POs must stay "unprocessed" so subsequent bills can match.
    # Final "PO ordered but not billed" reconciliation happens at export time
    # (see finalize_unbilled_po below) or via an explicit finalize endpoint.

    # Build summary block (items embedded)
    has_issue = bool(summary_items)
    block_id = str(_uuid_mod.uuid4())
    inv_num = bill.get("invoice_number") or ""
    summary_blocks.append({
        "id": block_id,
        "bill_id": bill_id,
        "vendor": vendor_name,
        "invoice_number": inv_num,
        "invoice_date": bill.get("invoice_date"),
        "email_subject": f"Invoice Review — {vendor_name} {inv_num}",
        "email_body": _build_email_body(vendor_name, inv_num),
        "has_reportable_issue": has_issue,
        "items": summary_items,
    })

    # Update bill status — "processed" hides the Match to POs button in the UI
    bill["extraction_status"] = "processed"
    bill["user_confirmed_at"] = datetime.now(timezone.utc).isoformat()

    # Persist all changes atomically
    result_store.save(run_id, "vendor_bills", bills)
    result_store.save(run_id, "po_bank", po_rows)
    result_store.save(run_id, "bill_import_rows", import_rows)
    result_store.save(run_id, "vendor_summary_blocks", summary_blocks)
    # po_not_charged is populated only by finalize_unbilled_po (PRD §10.12).
    result_store.save(run_id, "weight_rows", weight_rows)
    result_store.save(run_id, "cost_comparison", cost_comparison)

    return {
        "success": True,
        "import_rows": import_line_num - 1,
        "discrepancies": len(summary_items),
        "has_reportable_issue": has_issue,
    }


def _build_email_body(vendor: str, invoice_number: str) -> str:
    return (
        f"Dear {vendor} team,\n\n"
        f"We are writing regarding invoice #{invoice_number}.\n"
        "Please review the items listed below and confirm the following:\n\n"
        "For overcharged items: Please issue a credit for the difference.\n"
        "For undercharged items: Please confirm whether the lower price is correct.\n\n"
        "Thank you for your prompt attention.\n\n"
        "Best regards,\nB&R Food Services"
    )


def finalize_unbilled_po(run_id: str) -> dict:
    """Sweep remaining unprocessed POs (for vendors that had at least one bill
    confirmed) into the 'PO Items Not Charged' list. PRD §10.12 — runs once at
    export time so multi-bill vendors are not flagged prematurely."""
    po_rows = result_store.load(run_id, "po_bank", [])
    bills = result_store.load(run_id, "vendor_bills", [])

    # Build vendor → list of processed invoice numbers for All Issues detail text
    vendor_invoices: dict[str, list[str]] = {}
    confirmed_vendors: set[str] = set()
    for b in bills:
        if b.get("extraction_status") != "processed":
            continue
        v_norm = normalize_vendor(b.get("vendor_confirmed") or b.get("vendor_extracted") or "")
        confirmed_vendors.add(v_norm)
        inv = b.get("invoice_number")
        if inv:
            vendor_invoices.setdefault(v_norm, []).append(inv)

    po_not_charged = result_store.load(run_id, "po_not_charged", [])
    added = 0
    for po in po_rows:
        if po.get("status") != "unprocessed":
            continue
        v_norm = normalize_vendor(po.get("vendor") or "")
        if v_norm not in confirmed_vendors:
            continue
        po["status"] = "processed"
        po["processed_bill_id"] = None
        po_not_charged.append({
            "item_code": po.get("item_code"), "description": po.get("description"),
            "vendor": po.get("vendor"), "ref_number": po.get("ref_number"),
            "qty_ordered": po.get("quantity"), "po_cost": po.get("po_cost"),
            "invoice_numbers": vendor_invoices.get(v_norm, []),
            "eta_request": True,
        })
        added += 1
    if added:
        result_store.save(run_id, "po_bank", po_rows)
        result_store.save(run_id, "po_not_charged", po_not_charged)
    return {"added": added}


def finalize_run(run_id: str) -> dict:
    """Advance run status to 'processed' so the Download Workbook button appears.
    Safe to call even if more bills arrive later — just reopen after export."""
    bills = result_store.load(run_id, "vendor_bills", [])
    processed_count = sum(1 for b in bills if b.get("extraction_status") == "processed")
    if processed_count == 0:
        return {"success": False, "errors": ["No bills have been matched yet."]}
    update_run(run_id, {"status": "processed"})
    return {"success": True, "processed_bills": processed_count}


def reopen_run(run_id: str) -> dict:
    """Undo the export-time finalize sweep so the office can add more bills.

    `finalize_unbilled_po` marks any leftover vendor PO as ``processed`` with
    ``processed_bill_id=None`` and appends an entry to ``po_not_charged``. This
    reverses both, then resets the run status from ``exported`` to
    ``processed`` so subsequent bills can match against the restored PO Bank.
    """
    po_rows = result_store.load(run_id, "po_bank", [])
    reverted = 0
    for po in po_rows:
        if po.get("status") == "processed" and po.get("processed_bill_id") in (None, ""):
            po["status"] = "unprocessed"
            po.pop("processed_bill_id", None)
            reverted += 1
    if reverted:
        result_store.save(run_id, "po_bank", po_rows)
    result_store.save(run_id, "po_not_charged", [])
    update_run(run_id, {"status": "processed"})
    return {"reverted_pos": reverted}


async def export_workbook(run_id: str) -> str:
    run = get_run(run_id)
    run_ns = types.SimpleNamespace(**run) if run else types.SimpleNamespace(id=run_id)

    finalize_unbilled_po(run_id)

    po_rows = result_store.load(run_id, "po_bank", [])
    office_tasks = result_store.load(run_id, "office_tasks", [])
    import_rows = sorted(result_store.load(run_id, "bill_import_rows", []),
                         key=lambda r: r.get("line") or 0)
    summary_blocks = result_store.load(run_id, "vendor_summary_blocks", [])
    items_by_block = {b["id"]: b.get("items", []) for b in summary_blocks}
    po_not_charged = result_store.load(run_id, "po_not_charged", [])
    weight_rows = result_store.load(run_id, "weight_rows", [])
    cost_comparison = sorted(
        result_store.load(run_id, "cost_comparison", []),
        key=lambda r: (r.get("vendor") or "", r.get("item_code") or ""),
    )

    return generate_workbook(
        run_ns, po_rows, office_tasks, import_rows, summary_blocks,
        items_by_block, po_not_charged, weight_rows, cost_comparison,
    )
