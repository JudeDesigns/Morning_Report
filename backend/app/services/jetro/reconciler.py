"""Core Jetro reconciliation logic: fold CRV/coupons, match, generate issues/prices/coupons."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


def fold_invoice_lines(lines: list[dict]) -> list[dict]:
    """Fold surcharge and coupon rows into preceding real item. PRD 9.6."""
    result = []
    for line in lines:
        rt = line.get("row_type", "item")
        if rt in ("surcharge", "coupon") and result:
            prev = result[-1]
            total = (prev.get("total") or Decimal(0)) + (line.get("total") or Decimal(0))
            prev["total"] = total
            prev["_folded"].append(line)
            # Track coupon separately
            if rt == "coupon":
                prev["_coupon_amount"] = (prev.get("_coupon_amount") or Decimal(0)) + abs(line.get("total") or Decimal(0))
                prev["_coupon_per_unit"] = abs(line.get("price") or Decimal(0))
                prev["_coupon_qty"] = line.get("qty")
        elif rt in ("void", "return") and result:
            # Net into same item code (PRD 9.6/9.7 — voids and "R" returns both
            # reverse). Match by (base_code, kind) so a void on a CASE item
            # doesn't incorrectly fold into a same-base UNIT item or vice versa.
            prev = next(
                (
                    r for r in reversed(result)
                    if r.get("base_code") == line.get("base_code")
                    and r.get("kind") == line.get("kind")
                ),
                None,
            )
            if prev:
                prev["qty"] = (prev.get("qty") or Decimal(0)) + (line.get("qty") or Decimal(0))
                prev["total"] = (prev.get("total") or Decimal(0)) + (line.get("total") or Decimal(0))
            else:
                line["_folded"] = []
                result.append(line)
        else:
            line["_folded"] = []
            result.append(line)

    # Remove net-zero rows
    result = [r for r in result if r.get("total") != Decimal(0) or r.get("qty") != Decimal(0)]
    return result


def deduplicate_lines(lines: list[dict]) -> list[dict]:
    """Deduplicate by full_code within same invoice. PRD 9.8."""
    seen = {}
    for line in lines:
        key = line.get("full_code") or line.get("item_raw") or line.get("description")
        if key in seen:
            prev = seen[key]
            prev["qty"] = (prev.get("qty") or Decimal(0)) + (line.get("qty") or Decimal(0))
            prev["total"] = (prev.get("total") or Decimal(0)) + (line.get("total") or Decimal(0))
            if prev.get("qty") and prev["qty"] != 0:
                prev["cost"] = prev["total"] / prev["qty"]
        else:
            seen[key] = dict(line)

    # PRD §9.8 — "Drop rows that net to zero" means qty AND total both zero.
    # A residual coupon or surcharge can leave qty=0 with a non-zero total;
    # those must remain so processed total matches the printed Grand Total.
    result = [
        v for v in seen.values()
        if (v.get("qty") or Decimal(0)) != Decimal(0)
        or (v.get("total") or Decimal(0)) != Decimal(0)
    ]
    for i, r in enumerate(result, start=1):
        r["line"] = i
        if r.get("qty") and r["qty"] != 0:
            r["cost"] = (r.get("total") or Decimal(0)) / r["qty"]
    return result


def match_invoice_to_jetro(invoice_lines: list[dict], jetro_rows: list[dict]) -> dict:
    """Match invoice lines to Jetro source by (base_code, kind). PRD 9.5."""
    jetro_by_key = {}
    for row in jetro_rows:
        if row.get("is_internal_inventory"):
            continue
        key = (row.get("base_code"), row.get("kind"))
        if key not in jetro_by_key:
            jetro_by_key[key] = []
        jetro_by_key[key].append(row)

    matched = []    # (invoice_line, jetro_rows_list)
    extra = []      # invoice lines with no jetro match

    for line in invoice_lines:
        key = (line.get("base_code"), line.get("kind"))
        jetro_matches = jetro_by_key.get(key, [])
        if jetro_matches:
            matched.append((line, jetro_matches))
        else:
            extra.append(line)

    return {"matched": matched, "extra": extra}


def generate_issues(matched: list, extra: list, jetro_rows: list[dict]) -> list[dict]:
    """Generate All Issues rows. PRD 9.9."""
    issues = []
    matched_keys = set()

    for line, jrows in matched:
        matched_keys.add((line.get("base_code"), line.get("kind")))
        # Aggregate jetro ordered qty
        total_ordered = sum((r.get("qty") or Decimal(0)) for r in jrows)
        billed_qty = line.get("qty") or Decimal(0)
        unit = (jrows[0].get("unit") or "").upper() if jrows else ""

        if unit == "LBS":
            # Compare in pounds
            total_lbs = sum(
                (r.get("qty") or Decimal(0)) * (r.get("case_avg_weight") or Decimal(0)) for r in jrows
            )
            if abs(total_lbs - billed_qty) > Decimal("0.01"):
                used_by = "; ".join(
                    f"{r.get('customer_name')} x{(r.get('qty') or Decimal(0)):f}" for r in jrows if r.get("customer_name")
                )
                issues.append({
                    "issue_type": "Qty mismatch",
                    "item_code": line.get("full_code"),
                    "quantity": total_lbs,
                    "item_description": line.get("description"),
                    "used_by": used_by,
                    "detail": f"Ordered {total_lbs:f} lbs, billed {billed_qty:f} lbs",
                    "dollar_size": abs((line.get("cost") or Decimal(0)) * (billed_qty - total_lbs)),
                })
        else:
            if abs(total_ordered - billed_qty) > Decimal("0.001"):
                used_by = "; ".join(
                    f"{r.get('customer_name')} x{(r.get('qty') or Decimal(0)):f}" for r in jrows if r.get("customer_name")
                )
                issues.append({
                    "issue_type": "Qty mismatch",
                    "item_code": line.get("full_code"),
                    "quantity": total_ordered,
                    "item_description": line.get("description"),
                    "used_by": used_by,
                    "detail": f"Ordered {total_ordered:f}, billed {billed_qty:f}",
                    "dollar_size": abs((line.get("cost") or Decimal(0)) * (billed_qty - total_ordered)),
                })

    # Missing: in Jetro but not billed — PRD §9.9 expects ONE row per item
    # code with "Used by:" listing all ordering customers and their quantities.
    missing_by_key: dict[tuple, dict] = {}
    for row in jetro_rows:
        if row.get("is_internal_inventory"):
            continue
        key = (row.get("base_code"), row.get("kind"))
        if key in matched_keys:
            continue
        qty = row.get("qty") or Decimal(0)
        cost = row.get("current_cost_price") or Decimal(0)
        entry = missing_by_key.get(key)
        if entry is None:
            missing_by_key[key] = {
                "issue_type": "Missing",
                "item_code": row.get("full_code"),
                "quantity": qty,
                "item_description": row.get("product_name"),
                "_customers": [(row.get("customer_name"), qty)] if row.get("customer_name") else [],
                "detail": "Ordered but not billed",
                "dollar_size": cost * qty,
            }
        else:
            entry["quantity"] = (entry["quantity"] or Decimal(0)) + qty
            entry["dollar_size"] = (entry["dollar_size"] or Decimal(0)) + (cost * qty)
            if row.get("customer_name"):
                entry["_customers"].append((row.get("customer_name"), qty))
    for entry in missing_by_key.values():
        entry["used_by"] = "; ".join(f"{c} x{(q or Decimal(0)):f}" for c, q in entry.pop("_customers"))
        issues.append(entry)

    # Extra: billed but not in Jetro
    for line in extra:
        issues.append({
            "issue_type": "Extra",
            "item_code": line.get("full_code"),
            "quantity": line.get("qty"),
            "item_description": line.get("description"),
            "used_by": None,
            "detail": "Billed but not in Jetro source",
            "dollar_size": (line.get("cost") or Decimal(0)) * (line.get("qty") or Decimal(0)),
        })

    # Sort: Missing, Extra, Qty mismatch; within group by dollar_size desc
    order = {"Missing": 0, "Extra": 1, "Qty mismatch": 2}
    issues.sort(key=lambda x: (order.get(x["issue_type"], 9), -(x.get("dollar_size") or Decimal(0))))
    return issues


def generate_price_updates(matched: list) -> list[dict]:
    """Generate Price Update rows. PRD 9.10."""
    updates = []
    for line, jrows in matched:
        new_cost = line.get("cost")
        if new_cost is None and line.get("qty") and line.get("qty") != 0:
            new_cost = (line.get("total") or Decimal(0)) / line["qty"]

        # Use first jetro row for old cost; aggregate used_by
        old_cost = jrows[0].get("current_cost_price") if jrows else None
        used_by = "; ".join(
            f"{r.get('customer_name')} x{(r.get('qty') or Decimal(0)):f}" for r in jrows if r.get("customer_name")
        )
        unit = (jrows[0].get("unit") or "").upper() if jrows else ""
        qty_charged = line.get("qty")
        if unit == "LBS":
            qty_charged = sum(
                (r.get("qty") or Decimal(0)) * (r.get("case_avg_weight") or Decimal(0)) for r in jrows
            )

        change = (old_cost - new_cost) if (old_cost is not None and new_cost is not None) else None
        updates.append({
            "item_code": line.get("full_code"),
            "qty_charged": qty_charged,
            "item_description": line.get("description"),
            "old_cost": old_cost,
            "new_cost": new_cost,
            "cost_change_old_minus_new": change,
            "used_by": used_by,
        })

    # Sort: largest positive change first, then negative, then zero
    def sort_key(u):
        c = u.get("cost_change_old_minus_new")
        if c is None:
            return (1, Decimal(0))
        if c > 0:
            return (0, -c)
        if c < 0:
            return (1, -c)
        return (2, Decimal(0))

    updates.sort(key=sort_key)
    return updates


def generate_coupons(invoice_lines: list[dict], sales_per_week: dict) -> list[dict]:
    """Generate Coupon rows. PRD 9.11."""
    coupons = []
    for line in invoice_lines:
        if not line.get("_coupon_amount"):
            continue
        code = line.get("full_code") or line.get("base_code")
        savings = line.get("_coupon_amount") or Decimal(0)
        coupon_per_unit = line.get("_coupon_per_unit")
        coupon_qty = line.get("_coupon_qty")
        eight_week = sales_per_week.get(code)
        projected = (eight_week * 8 * coupon_per_unit) if (eight_week and coupon_per_unit) else None

        coupons.append({
            "item_code": code,
            "description": line.get("description"),
            "coupon_amount": coupon_per_unit,
            "qty": coupon_qty,
            "invoice_total_savings": savings,
            "eight_week_usage": eight_week * 8 if eight_week else None,
            "projected_savings": projected,
        })

    coupons.sort(key=lambda c: -(c.get("projected_savings") or Decimal(0)))
    return coupons
