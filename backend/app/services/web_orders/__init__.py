"""Web Orders Check workflow service (PRD Module A) — file-based, no DB."""
from datetime import date
from io import BytesIO
from decimal import Decimal
import openpyxl

from app.services.storage import read_file
from app.services.web_orders.parser import (
    parse_all_orders, parse_item_list, parse_shopping_history, parse_inventory
)
from app.services.web_orders.enrichment import enrich_rows
from app.services.web_orders.checks import check_row, split_same_day_future
from app.services.web_orders.exporter import generate_workbook
from app.store import files_meta as file_store, results as result_store
from app.store.runs import update_run


def _safe_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


async def process_run(run_id: str) -> dict:
    """Full processing pipeline for a web orders run."""
    from app.store.runs import get_run
    run = get_run(run_id)
    if not run:
        return {"success": False, "errors": ["Run not found"]}

    run_date_raw = run.get("run_date")
    try:
        run_date = date.fromisoformat(run_date_raw) if run_date_raw else date.today()
    except ValueError:
        run_date = date.today()

    files_by_type: dict[str, dict] = {}
    for f in file_store.list_files(run_id):
        files_by_type.setdefault(f["file_type"], f)

    # Accept either the new single-spreadsheet upload or the legacy 4-file layout
    if "web_orders_spreadsheet" in files_by_type:
        content = await read_file(files_by_type["web_orders_spreadsheet"]["storage_path"])
        wb = openpyxl.load_workbook(BytesIO(content), data_only=True)
        wb_orders = wb_items = wb_inventory = wb_shopping = wb
    else:
        # Legacy multi-file path
        required = [
            "web_orders_all_orders", "web_orders_item_list",
            "web_orders_inventory", "web_orders_shopping_history",
        ]
        missing = [r for r in required if r not in files_by_type]
        if missing:
            return {"success": False, "errors": [f"Missing required files: {missing}"]}

        async def load_wb(file_type: str) -> openpyxl.Workbook:
            content = await read_file(files_by_type[file_type]["storage_path"])
            return openpyxl.load_workbook(BytesIO(content), data_only=True)

        wb_orders = await load_wb("web_orders_all_orders")
        wb_items = await load_wb("web_orders_item_list")
        wb_inventory = await load_wb("web_orders_inventory")
        wb_shopping = await load_wb("web_orders_shopping_history")

    order_rows, source_headers = parse_all_orders(wb_orders)
    item_list = parse_item_list(wb_items)
    inventory = parse_inventory(wb_inventory)
    shopping_history = parse_shopping_history(wb_shopping)

    warnings: list[str] = []
    if not item_list:
        warnings.append(
            "Item List sheet not found or empty — enrichment columns T, U, V, AF will be blank."
        )
    if not inventory:
        warnings.append(
            "Inventory sheet not found or empty — enrichment columns AA, AB, AC, AD, AE will be blank."
        )
    if not shopping_history:
        warnings.append(
            "Shopping History sheet not found or empty — enrichment columns W, X, Y, Z will be blank."
        )

    enrich_rows(order_rows, item_list, shopping_history, inventory)
    same_day, future = split_same_day_future(order_rows, run_date)

    problematic = []
    for row in same_day:
        if row.get("_empty") or row.get("is_spacer"):
            continue
        reasons = check_row(row, run_date)
        if reasons:
            row["problem_reasons"] = reasons
            row["is_problematic"] = True
            problematic.append(row)

    # Serialise rows → JSON-safe dicts
    lines = []
    for i, row in enumerate(order_rows):
        if row.get("_empty"):
            continue
        txn = row.get("transaction_date")
        if txn is not None and hasattr(txn, "date"):
            txn = txn.date()
        lines.append({
            "source_row_number": i,
            "product_name": row.get("product_name"),
            "code": row.get("code"),
            "qty": _safe_float(row.get("qty")),
            "weight": _safe_float(row.get("weight")),
            "individual_weight_status": row.get("individual_weight_status"),
            "price": _safe_float(row.get("price")),
            "customer_name": row.get("customer_name"),
            "transaction_date": txn.isoformat() if isinstance(txn, date) else None,
            "route": row.get("route"),
            "remark": row.get("remark"),
            "category_name": row.get("category_name"),
            "current_cost_price": _safe_float(row.get("current_cost_price")),
            "current_selling_price": _safe_float(row.get("current_selling_price")),
            "unit": row.get("unit"),
            "shopping_product": row.get("shopping_product"),
            "new_bin": row.get("new_bin"),
            "unit_price": _safe_float(row.get("unit_price")),
            "case_price": _safe_float(row.get("case_price")),
            "quantity_on_hand": _safe_float(row.get("quantity_on_hand")),
            "inventory_cost": _safe_float(row.get("inventory_cost")),
            "case_avg_weight": _safe_float(row.get("case_avg_weight")),
            "unit_avg_weight": _safe_float(row.get("unit_avg_weight")),
            "bin_internal": row.get("bin_internal"),
            "passthrough": row.get("passthrough") or {},
            "is_spacer": bool(row.get("is_spacer")),
            "is_future": bool(row.get("is_future")),
            "is_problematic": bool(row.get("is_problematic")),
            "problem_reasons": row.get("problem_reasons"),
        })

    result_store.save(run_id, "web_orders_lines", lines)
    result_store.save(run_id, "web_orders_meta", {
        "source_headers": source_headers,
        "warnings": warnings,
        "reference_sheets": {
            "item_list": bool(item_list),
            "inventory": bool(inventory),
            "shopping_history": bool(shopping_history),
        },
    })
    update_run(run_id, {"status": "processed"})

    return {
        "success": True,
        "total_rows": len(lines),
        "same_day_rows": sum(1 for l in lines if not l["is_future"] and not l["is_spacer"]),
        "future_rows": sum(1 for l in lines if l["is_future"]),
        "problematic_rows": len(problematic),
        "warnings": warnings,
    }


async def export_workbook(run_id: str) -> str:
    all_lines = result_store.load(run_id, "web_orders_lines", [])
    meta = result_store.load(run_id, "web_orders_meta", {})
    same_day = [l for l in all_lines if not l.get("is_future") and not l.get("is_spacer")]
    future = [l for l in all_lines if l.get("is_future")]
    problematic = [l for l in all_lines if l.get("is_problematic")]
    return generate_workbook(
        same_day, future, problematic, run_id,
        source_headers=meta.get("source_headers") or [],
    )
