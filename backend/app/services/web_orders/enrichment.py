"""Enrich All Orders rows with Item List, Shopping History, and Inventory data."""
from decimal import Decimal
from typing import Optional


def normalize_code(val) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def shopping_history_match(code: str, sh_dict: dict) -> Optional[dict]:
    """Try exact match, then try stripping trailing U or C."""
    if code in sh_dict:
        return sh_dict[code]
    # Try with trailing U or C stripped
    if code and code[-1].upper() in ("U", "C"):
        base = code[:-1]
        if base in sh_dict:
            return sh_dict[base]
    # Try adding U or C
    for suffix in ("U", "C"):
        candidate = code + suffix
        if candidate in sh_dict:
            return sh_dict[candidate]
    return None


def enrich_rows(
    order_rows: list[dict],
    item_list: dict,
    shopping_history: dict,
    inventory: dict,
) -> list[dict]:
    """Enrich order rows with reference data. Mutates and returns rows."""
    for row in order_rows:
        if row.get("_empty"):
            continue
        code = normalize_code(row.get("code"))
        if not code:
            row["is_spacer"] = True
            continue

        row["is_spacer"] = False

        # Item List enrichment (exact match)
        il = item_list.get(code)
        if il:
            row["category_name"] = il.get("category_name")
            row["current_cost_price"] = il.get("current_cost_price")
            row["current_selling_price"] = il.get("current_selling_price")
            row["unit"] = il.get("unit")

        # Shopping History enrichment (with suffix tolerance)
        sh = shopping_history_match(code, shopping_history)
        if sh:
            row["shopping_product"] = sh.get("shopping_product")
            row["new_bin"] = sh.get("new_bin")
            row["unit_price"] = sh.get("unit_price")
            row["case_price"] = sh.get("case_price")

        # Inventory enrichment
        inv = inventory.get(code)
        if inv:
            row["quantity_on_hand"] = inv.get("quantity_on_hand")
            row["inventory_cost"] = inv.get("inventory_cost")
            row["case_avg_weight"] = inv.get("case_avg_weight")
            row["unit_avg_weight"] = inv.get("unit_avg_weight")
            row["bin_internal"] = inv.get("bin_internal")

    return order_rows
