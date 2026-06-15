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
    match_bill_line_to_po, compute_discrepancies, normalize_vendor, vendors_match,
)
from app.services.vendor_bills.exporter import generate_workbook
from app.services.ai_extraction import extract_vendor_bill, flag_low_confidence, _anthropic_client
from app.store import files_meta as file_store, results as result_store
from app.store.runs import get_run, update_run



def _f(v) -> float | None:
    return float(v) if v is not None else None


# Regex matching common country-of-origin / metadata annotations the AI
# sometimes emits as standalone "product" rows. Lower-cased before testing.
import re as _re
_ORIGIN_ONLY_RE = _re.compile(
    r"^(product\s+of\b|origin[:\s]|grown\s+in\b|country\s+of\s+origin\b|imported\s+from\b)",
    _re.IGNORECASE,
)


def _is_junk_line(line: dict) -> bool:
    """Reject rows the AI may have hallucinated from non-product content.

    Catches: empty rows, country-of-origin annotations ("Product of USA"),
    and rows where qty × rate is wildly out of line with the stated total
    (a strong signal the description and numbers came from different visual
    rows on the bill).
    """
    desc = (line.get("description") or "").strip()
    qty = line.get("qty")
    rate = line.get("rate")
    total = line.get("total")

    # Completely empty
    if not desc and qty in (None, 0) and rate in (None, 0):
        return True

    # Description is just an origin annotation — never a real product line
    if desc and _ORIGIN_ONLY_RE.match(desc):
        return True

    # Description shorter than 3 chars AND no item code — too sparse to trust
    if len(desc) < 3 and not (line.get("bill_item_code") or "").strip():
        return True

    # Arithmetic sanity: if qty, rate, and total are all present and
    # qty*rate disagrees with total by more than 5% AND $0.50, the row is
    # likely a column-misalignment artefact (description from row N, numbers
    # from row N+1).
    try:
        if qty is not None and rate is not None and total is not None:
            expected = float(qty) * float(rate)
            diff = abs(expected - float(total))
            if diff > 0.5 and (expected == 0 or diff / max(abs(expected), 0.01) > 0.05):
                return True
    except (TypeError, ValueError):
        pass

    return False


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

    # Persist the raw extraction JSON so we can audit prompts/responses when
    # the reviewer reports a misaligned row. One file per bill, written next
    # to the source image.
    try:
        import json as _json_dbg, os as _os_dbg
        src_path = file_rec.get("storage_path") or ""
        if src_path:
            dbg_dir = _os_dbg.path.join(_os_dbg.path.dirname(src_path), "_extracted")
            _os_dbg.makedirs(dbg_dir, exist_ok=True)
            dbg_path = _os_dbg.path.join(dbg_dir, f"{file_id}.json")
            with open(dbg_path, "w") as _f_dbg:
                _json_dbg.dump(extracted, _f_dbg, indent=2, default=str)
    except Exception as _dbg_e:
        print(f"[EXTRACT] failed to write debug json: {_dbg_e}")

    bill_id = str(_uuid_mod.uuid4())
    lines = []
    # Detect duplicate (qty, rate, total) triples — the signature of the
    # off-by-one row-alignment bug where Claude reuses numbers across two
    # different products. The first occurrence is kept; later duplicates are
    # flagged for review with an explicit reason so the user sees the issue.
    seen_triples: dict[tuple, int] = {}
    for i, line in enumerate(extracted.get("lines", [])):
        # Safety net: drop rows that are clearly not product lines (subtotals,
        # taxes, freight, country-of-origin annotations, etc. that may have
        # slipped past the AI prompt).
        if _is_junk_line(line):
            continue

        qty_v = _f(line.get("qty"))
        rate_v = _f(line.get("rate"))
        total_v = _f(line.get("total"))
        triple = (qty_v, rate_v, total_v)
        is_dup = (
            triple in seen_triples
            and qty_v is not None
            and rate_v is not None
            and total_v is not None
        )
        if not is_dup:
            seen_triples[triple] = i

        weights = line.get("individual_weights")
        field_needs_review = list(line.get("field_needs_review") or [])
        needs_review = bool(line.get("needs_review"))
        if is_dup:
            # Mark every numeric field on the duplicate row so the reviewer
            # sees red highlights on the cells that were almost certainly
            # copied from the row above.
            for field in ("qty", "rate", "total"):
                if field not in field_needs_review:
                    field_needs_review.append(field)
            needs_review = True

        lines.append({
            "id": str(_uuid_mod.uuid4()),
            "source_line_number": i,
            "bill_item_code": line.get("bill_item_code"),
            "description": line.get("description"),
            "qty": qty_v,
            "rate": rate_v,
            "total": total_v,
            "is_credit": bool(line.get("is_credit")),
            "individual_weights": [float(w) for w in weights] if weights else None,
            "notes": line.get("notes"),
            "confidence": _f(line.get("confidence")),
            "field_confidence": line.get("field_confidence") or {},
            "field_needs_review": field_needs_review,
            "needs_review": needs_review,
            "user_confirmed": False,
            "match_status": None,
            "extraction_warning": (
                "Duplicate qty/rate/total from a previous row — likely "
                "misaligned with the bill image; please verify."
            ) if is_dup else None,
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

    # Auto AI-match immediately after extraction so the review dialog opens pre-filled.
    # The local ai_match_bill_lines(run_id, bill_id) loads its own PO Bank and filters by vendor.
    print(f"[AI-MATCH] Starting for bill {bill_id}, run {run_id}")
    try:
        ai_result = await ai_match_bill_lines(run_id, bill_id)
        print(f"[AI-MATCH] Claude result: success={ai_result.get('success')} error={ai_result.get('error')!r}")
        if not ai_result.get("success"):
            print(f"[AI-MATCH] Failed: {ai_result.get('error')}")
        else:
            matched_any = False
            for match in ai_result.get("matches", []):
                po_id = match.get("po_id")
                conf  = match.get("confidence", 0)
                if po_id and conf >= 0.4:
                    for line in bill["lines"]:
                        if line["id"] == match["line_id"]:
                            line["forced_po_id"] = po_id
                            # Auto-confirm only on high-confidence AI matches so the
                            # user does not have to tick every OK box manually. They
                            # can still untick in the Review dialog to override.
                            if conf >= 0.7:
                                line["user_confirmed"] = True
                            matched_any = True
                            break
            n_matched = sum(1 for ln in bill["lines"] if ln.get("forced_po_id"))
            print(f"[AI-MATCH] {n_matched}/{len(bill['lines'])} lines matched — saving")
            if matched_any:
                # Reload and patch so we don't overwrite concurrent writes
                fresh_bills = result_store.load(run_id, "vendor_bills", [])
                for fb in fresh_bills:
                    if fb["id"] == bill_id:
                        fb["lines"] = bill["lines"]
                        break
                result_store.save(run_id, "vendor_bills", fresh_bills)
                print(f"[AI-MATCH] Saved {n_matched} matches to disk")
    except Exception as _e:
        import traceback
        print(f"[AI-MATCH] EXCEPTION: {_e}")
        traceback.print_exc()

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

    # Duplicate-invoice guard. Sha256 dedupe at upload catches byte-identical
    # files; this catches the softer case of the same logical invoice arriving
    # as two different files (e.g. phone photo + scan of the same paper bill).
    # Skipped when this bill is itself being re-processed.
    this_invoice = (bill.get("invoice_number") or "").strip()
    this_vendor = (bill.get("vendor_confirmed") or bill.get("vendor_extracted") or "").strip()
    if this_invoice and this_vendor:
        dup = next(
            (
                b for b in bills
                if b["id"] != bill_id
                and b.get("extraction_status") == "processed"
                and (b.get("invoice_number") or "").strip().lower() == this_invoice.lower()
                and vendors_match(
                    (b.get("vendor_confirmed") or b.get("vendor_extracted") or ""),
                    this_vendor,
                )
            ),
            None,
        )
        if dup:
            return {
                "success": False,
                "errors": [
                    f"Invoice #{this_invoice} from {this_vendor} was already "
                    "matched in this run. If this is actually a different bill, "
                    "edit the invoice number in the Review dialog. If it is a "
                    "duplicate, delete this bill."
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


async def ai_match_bill_lines(run_id: str, bill_id: str) -> dict:
    """Use Claude to suggest the best PO match for each bill line.

    Returns a list of {line_id, po_id|None, confidence, reason}.
    Falls back to a graceful "no suggestion" response when no API key is set.
    """
    import json as _json
    from app.config import settings

    bills = result_store.load(run_id, "vendor_bills", [])
    bill = next((b for b in bills if b["id"] == bill_id), None)
    if not bill:
        return {"success": False, "errors": ["Bill not found"]}

    bill_lines = bill.get("lines", [])
    if not bill_lines:
        return {"success": True, "matches": []}

    po_rows = result_store.load(run_id, "po_bank", [])
    vendor_name = bill.get("vendor_confirmed") or bill.get("vendor_extracted") or ""

    # Only unprocessed POs for this vendor are candidates. Loose match so the
    # full legal name on a bill ("Maui Fresh International") still finds the
    # shortened trading name in the PO Bank ("Maui Fresh").
    available_pos = [
        p for p in po_rows
        if vendors_match(p.get("vendor") or "", vendor_name)
        and p.get("status") == "unprocessed"
    ]
    fallback_used = False
    if not available_pos:
        # Safety net: if the vendor name does not match any PO Bank vendor,
        # send Claude the full list of unprocessed POs and let it decide.
        # Better to give the model some context than zero candidates.
        available_pos = [p for p in po_rows if p.get("status") == "unprocessed"]
        fallback_used = bool(available_pos)

    # Build readable lists for the prompt — include each PO's vendor so the
    # model can reject candidates from the wrong vendor when the fallback was
    # used.
    line_list = "\n".join(
        f"  LINE_ID={l['id']} | code={l.get('bill_item_code') or 'N/A'} | "
        f"desc={l.get('description') or 'N/A'} | qty={l.get('qty')} | rate=${l.get('rate')}"
        for l in bill_lines
    )
    po_list = (
        "\n".join(
            f"  PO_ID={p['id']} | vendor={p.get('vendor') or 'N/A'} | "
            f"code={p.get('item_code') or 'N/A'} | desc={p.get('description') or 'N/A'} | "
            f"qty={p.get('quantity')} | cost=${p.get('po_cost')}"
            for p in available_pos
        )
        if available_pos
        else "  (none)"
    )

    pool_note = (
        "The PO list below was pre-filtered to the bill's vendor."
        if not fallback_used
        else (
            "NOTE: the bill vendor name did not exactly match any PO Bank vendor, "
            "so ALL unprocessed POs are shown. Treat vendor names loosely (e.g. "
            "'Maui Fresh' and 'Maui Fresh International' are the same business) "
            "and reject candidates whose vendor is clearly a different company."
        )
    )

    prompt = f"""You are a produce/food-service invoice specialist matching vendor bill lines to purchase order rows for B&R Food Services.

Bill vendor (as printed on invoice): {vendor_name}

{pool_note}

=== Bill Lines ===
{line_list}

=== Available PO Rows (unprocessed) ===
{po_list}

Matching rules:
1. A bill line matches a PO row when they share the same item code OR a clearly similar product description (consider abbreviations, pack sizes, weights, plural forms, country of origin tags).
2. Each PO row may be matched to at most one bill line.
3. If no PO row reasonably matches a bill line, set po_id to null and confidence < 0.4.
4. Treat vendor-name variations as the same business when one name is contained in the other (e.g. "Maui Fresh" ≡ "Maui Fresh International"). Do NOT match across genuinely different vendors.
5. PRICE IS A STRONG TIE-BREAKER. When two or more PO rows look plausible for the same bill line (e.g. two different sizes of bell pepper), prefer the PO whose `cost` is closest to the bill line's `rate`. An exact or near-exact (within ~2%) price match is a very strong signal the row is correct, even when descriptions look ambiguous. Mention the price comparison in your reason field whenever you used it.
6. Set confidence ≥ 0.8 only when you are highly certain (item code match, near-identical description, or description match plus close price agreement).

Return ONLY valid JSON — no prose before or after:
{{
  "matches": [
    {{
      "line_id": "<exact LINE_ID from above>",
      "po_id": "<exact PO_ID from above or null>",
      "confidence": <0.0 to 1.0>,
      "reason": "<one short sentence>"
    }}
  ]
}}"""

    if not settings.ANTHROPIC_API_KEY:
        return {
            "success": True,
            "matches": [
                {"line_id": l["id"], "po_id": None, "confidence": 0.0,
                 "reason": "AI unavailable — no API key configured"}
                for l in bill_lines
            ],
        }

    import asyncio as _asyncio
    client = _anthropic_client()
    # Off-load the blocking SDK call to a worker thread so the FastAPI event
    # loop stays responsive (page refreshes during matching no longer hang).
    message = await _asyncio.to_thread(
        client.messages.create,
        model="claude-opus-4-5",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text.strip()
    # Strip optional markdown fence
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        result = _json.loads(text)
        return {"success": True, "matches": result.get("matches", [])}
    except _json.JSONDecodeError:
        return {"success": False, "errors": ["Failed to parse AI response"]}


def delete_bill(run_id: str, bill_id: str) -> dict:
    """Remove an extracted bill. If it was already processed (matched to POs),
    restore those PO rows to 'unprocessed' and purge all derived rows."""
    bills = result_store.load(run_id, "vendor_bills", [])
    bill = next((b for b in bills if b["id"] == bill_id), None)
    if not bill:
        return {"success": False, "errors": ["Bill not found"]}

    # Restore matched PO rows when the bill was already processed
    if bill.get("extraction_status") == "processed":
        matched_po_ids = {
            bl.get("matched_po_id")
            for bl in bill.get("lines", [])
            if bl.get("matched_po_id")
        }
        if matched_po_ids:
            po_rows = result_store.load(run_id, "po_bank", [])
            for po in po_rows:
                if po.get("id") in matched_po_ids:
                    po["status"] = "unprocessed"
                    po.pop("processed_bill_id", None)
            result_store.save(run_id, "po_bank", po_rows)

        # Remove all rows that were generated by this bill
        for store_key in ("bill_import_rows", "weight_rows", "cost_comparison", "vendor_summary_blocks"):
            rows = result_store.load(run_id, store_key, [])
            filtered = [r for r in rows if r.get("bill_id") != bill_id]
            if len(filtered) != len(rows):
                result_store.save(run_id, store_key, filtered)

    # Remove the bill itself
    bills = [b for b in bills if b["id"] != bill_id]
    result_store.save(run_id, "vendor_bills", bills)
    return {"success": True, "deleted_bill_id": bill_id}


def finalize_unbilled_po(run_id: str) -> dict:
    """Sweep remaining unprocessed POs (for vendors that had at least one bill
    confirmed) into the 'PO Items Not Charged' list. PRD §10.12 — runs once at
    export time so multi-bill vendors are not flagged prematurely."""
    po_rows = result_store.load(run_id, "po_bank", [])
    bills = result_store.load(run_id, "vendor_bills", [])

    # Build (raw bill vendor name) → list of processed invoice numbers. We keep
    # the original strings so we can apply loose vendor matching below — set
    # membership on the canonical form misses "Maui Fresh" vs
    # "Maui Fresh International" style variations.
    vendor_invoices: dict[str, list[str]] = {}
    confirmed_vendors: list[str] = []
    for b in bills:
        if b.get("extraction_status") != "processed":
            continue
        vname = b.get("vendor_confirmed") or b.get("vendor_extracted") or ""
        if vname and vname not in confirmed_vendors:
            confirmed_vendors.append(vname)
        inv = b.get("invoice_number")
        if inv and vname:
            vendor_invoices.setdefault(vname, []).append(inv)

    po_not_charged = result_store.load(run_id, "po_not_charged", [])
    added = 0
    for po in po_rows:
        if po.get("status") != "unprocessed":
            continue
        po_vendor = po.get("vendor") or ""
        matched_bill_vendor = next(
            (v for v in confirmed_vendors if vendors_match(v, po_vendor)),
            None,
        )
        if not matched_bill_vendor:
            continue
        po["status"] = "processed"
        po["processed_bill_id"] = None
        po_not_charged.append({
            "item_code": po.get("item_code"), "description": po.get("description"),
            "vendor": po.get("vendor"), "ref_number": po.get("ref_number"),
            "qty_ordered": po.get("quantity"), "po_cost": po.get("po_cost"),
            "invoice_numbers": vendor_invoices.get(matched_bill_vendor, []),
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
