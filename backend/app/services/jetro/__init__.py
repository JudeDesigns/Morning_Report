"""Jetro / Restaurant Depot reconciliation service (PRD Module B) — file-based, no DB."""
import types
from io import BytesIO
from decimal import Decimal
import openpyxl

from app.services.storage import read_file
from app.services.jetro.parser import parse_jetro_source, parse_rd_invoice_xlsx, parse_sales_per_week
from app.services.jetro.reconciler import (
    fold_invoice_lines, deduplicate_lines, match_invoice_to_jetro,
    generate_issues, generate_price_updates, generate_coupons,
)
from app.services.jetro.exporter import generate_workbook
from app.store import files_meta as file_store, results as result_store
from app.store.runs import get_run, update_run


def _f(v) -> float | None:
    """Safe Decimal/None → float conversion."""
    return float(v) if v is not None else None


async def process_run(run_id: str) -> dict:
    run = get_run(run_id)
    if not run:
        return {"success": False, "errors": ["Run not found"]}

    # Group uploaded files by type
    files_by_type: dict[str, list] = {}
    for f in file_store.list_files(run_id):
        files_by_type.setdefault(f["file_type"], []).append(f)

    if "jetro_source" not in files_by_type:
        return {"success": False, "errors": ["Missing Jetro source file"]}
    if "restaurant_depot_invoice_xlsx" not in files_by_type:
        return {"success": False, "errors": ["Missing Restaurant Depot invoice XLSX"]}

    async def load_wb(f: dict) -> openpyxl.Workbook:
        content = await read_file(f["storage_path"])
        return openpyxl.load_workbook(BytesIO(content), data_only=True)

    jetro_wb = await load_wb(files_by_type["jetro_source"][0])
    jetro_rows = parse_jetro_source(jetro_wb)

    spw: dict = {}
    if "sales_per_week" in files_by_type:
        spw_wb = await load_wb(files_by_type["sales_per_week"][0])
        spw = parse_sales_per_week(spw_wb)

    all_import_rows, all_issues, all_price_updates, all_coupons, invoice_records = [], [], [], [], []

    for inv_file in files_by_type["restaurant_depot_invoice_xlsx"]:
        inv_wb = await load_wb(inv_file)
        inv_data = parse_rd_invoice_xlsx(inv_wb)
        if not inv_data.get("invoice_number"):
            continue

        grand_total = inv_data.get("grand_total") or Decimal(0)
        inv_type = "credit" if grand_total < 0 else "charge"

        folded = fold_invoice_lines(inv_data["lines"])
        deduped = deduplicate_lines([l for l in folded if l.get("row_type") == "item"])

        if inv_type == "charge":
            mr = match_invoice_to_jetro(deduped, jetro_rows)
            all_issues.extend(generate_issues(mr["matched"], mr["extra"], jetro_rows))
            all_price_updates.extend(generate_price_updates(mr["matched"]))
            all_coupons.extend(generate_coupons(folded, spw))

        processed_total = sum((r.get("total") or Decimal(0)) for r in deduped)
        integrity = "ok" if abs(processed_total - grand_total) < Decimal("0.02") else "mismatch"

        invoice_records.append({
            "invoice_number": inv_data["invoice_number"],
            "invoice_type": inv_type,
            "printed_grand_total": _f(grand_total),
            "processed_total": _f(processed_total),
            "integrity_status": integrity,
        })

        inv_date = inv_data.get("invoice_date")
        inv_date_str = inv_date.isoformat() if hasattr(inv_date, "isoformat") else (str(inv_date) if inv_date else None)

        for row in deduped:
            qty = row.get("qty") or Decimal(0)
            total = row.get("total") or Decimal(0)
            cost = total / qty if qty != 0 else Decimal(0)
            all_import_rows.append({
                "line": row.get("line"),
                "upc": row.get("upc"),
                "item_code": row.get("full_code"),
                "description": row.get("description"),
                "cost": _f(cost),
                "qty": _f(qty),
                "total": _f(total),
                "vendor": "Jetro",
                "invoice_number": inv_data["invoice_number"],
                "invoice_date": inv_date_str,
                "type": "Inventory Part",
            })

    # Normalise issues / price updates / coupons to plain floats
    serialised_issues = [{
        "issue_type": i["issue_type"], "item_code": i["item_code"],
        "quantity": _f(i.get("quantity")), "item_description": i["item_description"],
        "used_by": i["used_by"], "detail": i["detail"],
        "dollar_size": _f(i.get("dollar_size")),
    } for i in all_issues]

    serialised_pu = [{
        "item_code": p["item_code"], "qty_charged": _f(p.get("qty_charged")),
        "item_description": p["item_description"],
        "old_cost": _f(p.get("old_cost")), "new_cost": _f(p.get("new_cost")),
        "cost_change_old_minus_new": _f(p.get("cost_change_old_minus_new")),
        "used_by": p["used_by"],
    } for p in all_price_updates]

    serialised_coupons = [{
        "item_code": c["item_code"], "description": c["description"],
        "coupon_amount": _f(c.get("coupon_amount")), "qty": _f(c.get("qty")),
        "invoice_total_savings": _f(c.get("invoice_total_savings")),
        "eight_week_usage": _f(c.get("eight_week_usage")),
        "projected_savings": _f(c.get("projected_savings")),
    } for c in all_coupons]

    # Persist to JSON store
    result_store.save(run_id, "jetro_invoices", invoice_records)
    result_store.save(run_id, "jetro_import_rows", all_import_rows)
    result_store.save(run_id, "jetro_issues", serialised_issues)
    result_store.save(run_id, "jetro_price_updates", serialised_pu)
    result_store.save(run_id, "jetro_coupons", serialised_coupons)
    update_run(run_id, {"status": "processed"})

    return {
        "success": True,
        "invoices": len(invoice_records),
        "import_rows": len(all_import_rows),
        "issues": len(serialised_issues),
        "price_updates": len(serialised_pu),
        "coupons": len(serialised_coupons),
    }


async def export_workbook(run_id: str) -> str:
    run = get_run(run_id)
    # Wrap dict in namespace so exporter can use run.name, run.id, run.run_date
    run_ns = types.SimpleNamespace(**run) if run else types.SimpleNamespace(id=run_id, name="", run_date="")

    invoices = result_store.load(run_id, "jetro_invoices", [])
    import_rows = result_store.load(run_id, "jetro_import_rows", [])
    issues = result_store.load(run_id, "jetro_issues", [])
    price_updates = result_store.load(run_id, "jetro_price_updates", [])
    coupons = result_store.load(run_id, "jetro_coupons", [])
    return generate_workbook(run_ns, invoices, import_rows, issues, price_updates, coupons)
