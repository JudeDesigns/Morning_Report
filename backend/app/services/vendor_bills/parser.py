"""Parse QuickBooks PO export (PRD 10.3–10.5)."""
from decimal import Decimal, InvalidOperation
from typing import Optional
import openpyxl


def safe_decimal(val) -> Optional[Decimal]:
    if val is None:
        return None
    try:
        return Decimal(str(val).strip())
    except (InvalidOperation, ValueError):
        return None


def classify_po_row(raw: list) -> str:
    """Classify a PO row as: order_header, spacer, or product_line. PRD 10.4."""
    def get(idx):
        return str(raw[idx]).strip() if idx < len(raw) and raw[idx] is not None else ""

    desc = get(7)   # H - TxnLine Description
    item = get(8)   # I - TxnLine Item
    cost = safe_decimal(raw[6] if len(raw) > 6 else None)   # G - TxnLine Cost
    vendor = get(3)  # D - Vendor

    # Spacer
    if not desc and not item:
        return "spacer"

    # Order header patterns
    is_header = (
        desc.upper().startswith("ORDER PLACED BY")
        or desc.strip().startswith("***")
        or "NEED TO CHECK AVAILABILITY" in desc.upper()
        or (not item or item == vendor)
        and (cost is None or cost == 0)
    )
    if is_header and not item:
        return "order_header"

    # Product line: has item code, not equal to vendor, has cost and qty
    if item and item != vendor and cost is not None:
        return "product_line"

    return "order_header"


def split_description_task(description: str) -> tuple[str, Optional[str]]:
    """Split description at first blank line into (product_desc, task). PRD 10.5."""
    if not description:
        return ("", None)
    lines = description.split("\n")
    product_lines = []
    task_lines = []
    blank_found = False
    for line in lines:
        if not blank_found and not line.strip():
            blank_found = True
            continue
        if blank_found:
            task_lines.append(line)
        else:
            product_lines.append(line)
    product = "\n".join(product_lines).strip()
    task = "\n".join(task_lines).strip() if task_lines else None
    return (product, task)


def parse_po_export(wb: openpyxl.Workbook) -> dict:
    """Parse QuickBooks PO export. Returns dict with product_lines and office_tasks."""
    ws = wb.active
    product_lines = []
    office_tasks = []
    header_found = False
    current_vendor = None
    current_ref = None

    for row in ws.iter_rows(values_only=True):
        raw = list(row)
        if not any(raw):
            continue

        if not header_found:
            # Detect header row by looking for known column names
            row_str = " ".join(str(c).lower() for c in raw if c)
            if "vendor" in row_str and ("txnline" in row_str or "description" in row_str):
                header_found = True
            continue

        def get(idx):
            return raw[idx] if idx < len(raw) and raw[idx] is not None else None

        # Track current vendor/ref from header rows
        vendor_val = str(get(3)).strip() if get(3) else None
        ref_val = str(get(1)).strip() if get(1) else None
        if vendor_val:
            current_vendor = vendor_val
        if ref_val:
            current_ref = ref_val

        row_type = classify_po_row(raw)
        desc_raw = str(get(7)).strip() if get(7) else ""
        product_desc, task = split_description_task(desc_raw)

        if row_type == "spacer":
            continue

        if row_type == "order_header":
            # v3 §1.4: need_review = vendor name; task = order note
            office_tasks.append({
                "vendor_name": current_vendor,
                "ref_number": current_ref,
                "task_type": "order_header",
                "item": str(get(8)) if get(8) else None,
                "need_review": current_vendor,
                "task_instructions": desc_raw,
            })
            if task:
                office_tasks.append({
                    "vendor_name": current_vendor,
                    "ref_number": current_ref,
                    "task_type": "item_task",
                    "item": str(get(8)) if get(8) else None,
                    "need_review": product_desc or None,
                    "task_instructions": task,
                })
            continue

        # Product line: v3 §1.4 item_task — need_review = first part of product
        # description; task = the embedded task (second part).
        if task:
            office_tasks.append({
                "vendor_name": current_vendor,
                "ref_number": current_ref,
                "task_type": "item_task",
                "item": str(get(8)) if get(8) else None,
                "need_review": product_desc or None,
                "task_instructions": task,
            })

        txn_date = get(2)
        if txn_date and hasattr(txn_date, 'date'):
            txn_date = txn_date.date()

        product_lines.append({
            "terms": str(get(0)).strip() if get(0) else None,
            "ref_number": current_ref,
            "txn_date": txn_date,
            "vendor": current_vendor,
            "memo": str(get(4)).strip() if get(4) else None,
            "total_amount": safe_decimal(get(5)),
            "po_cost": safe_decimal(get(6)),
            "description": product_desc,
            "item_code": str(get(8)).strip() if get(8) else None,
            "quantity": safe_decimal(get(9)),
            "class_name": str(get(10)).strip() if get(10) else None,
            "case_avg_weight": safe_decimal(get(11)),
            "unit_avg_weight": safe_decimal(get(12)),
            "status": "unprocessed",
            "_raw": raw,
        })

    return {"product_lines": product_lines, "office_tasks": office_tasks}
