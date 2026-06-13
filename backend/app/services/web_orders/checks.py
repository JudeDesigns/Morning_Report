"""Problem checks for web order lines (PRD Section 8.7)."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

SUBSTITUTION_KEYWORDS = ["sub", "substitute"]
PENDING_KEYWORDS = ["pending"]
OFFICE_MISTAKE_KEYWORDS = ["entry error", "change of mind", "office mistake"]
AVG_KEYWORDS = ["avg", "a.v.g"]
SP_KEYWORDS = ["sp", "special price"]

WEIGHT_TOLERANCE = Decimal("0.0001")  # small arithmetic tolerance
AVG_PCT_TOLERANCE = Decimal("0.15")


def safe_decimal(val) -> Optional[Decimal]:
    if val is None:
        return None
    try:
        if isinstance(val, Decimal):
            return val
        return Decimal(str(val))
    except (InvalidOperation, ValueError):
        return None


def remark_contains(remark: Optional[str], keywords: list) -> bool:
    if not remark:
        return False
    rl = remark.lower()
    return any(k in rl for k in keywords)


def check_remark_status(row: dict) -> list[str]:
    """PRD 8.7.1 - Remark and status checks."""
    reasons = []
    remark = row.get("remark") or ""
    status = (row.get("individual_weight_status") or "").upper().strip()
    qty = safe_decimal(row.get("qty"))

    is_sub_remark = remark_contains(remark, SUBSTITUTION_KEYWORDS)
    is_pending = remark_contains(remark, PENDING_KEYWORDS)
    is_mistake = remark_contains(remark, OFFICE_MISTAKE_KEYWORDS)

    if is_sub_remark and status != "SUBSTITUTED":
        reasons.append("Substitution remark but status is not SUBSTITUTED")

    if is_pending and not status:
        reasons.append("Pending remark with blank status")

    if is_mistake:
        if qty is None or qty != Decimal("0"):
            reasons.append("Office mistake remark with non-zero qty")

    return reasons


def check_lbs_weight(row: dict) -> list[str]:
    """PRD 8.7.2 - LBS weight cascade."""
    unit = (row.get("unit") or "").upper().strip()
    if unit != "LBS":
        return []

    reasons = []
    qty = safe_decimal(row.get("qty"))
    weight = safe_decimal(row.get("weight"))
    product_name = (row.get("product_name") or "").strip()
    case_avg = safe_decimal(row.get("case_avg_weight"))
    unit_avg = safe_decimal(row.get("unit_avg_weight"))

    if qty is None or weight is None:
        return []

    def approx_equal(a: Decimal, b: Decimal) -> bool:
        return abs(a - b) <= WEIGHT_TOLERANCE

    # Step 1: Qty × Case Avg Weight = Weight
    if case_avg is not None:
        expected = qty * case_avg
        if approx_equal(expected, weight):
            return []

    # Step 2: Product starts with "Unit" and Qty × Unit Avg = Weight
    if product_name.lower().startswith("unit") and unit_avg is not None:
        expected = qty * unit_avg
        if approx_equal(expected, weight):
            return []

    # Step 3: AVG product - check within ±15%
    pn_lower = product_name.lower()
    is_avg = any(k in pn_lower for k in AVG_KEYWORDS)
    if is_avg:
        for avg in [case_avg, unit_avg]:
            if avg is not None:
                expected = qty * avg
                if expected > 0 and abs(weight - expected) / expected <= AVG_PCT_TOLERANCE:
                    return []

    reasons.append(f"LBS weight mismatch: ordered {qty:f} cases, weight {weight:.2f}")
    return reasons


def _is_sp_remark(remark: Optional[str]) -> bool:
    """PRD §8.7.3 — 'SP' remark = special customer price. Token-level match so
    we don't false-positive on 'spaghetti' etc."""
    if not remark:
        return False
    tokens = remark.replace(",", " ").replace(";", " ").lower().split()
    if "sp" in tokens or "s.p" in tokens or "s.p." in tokens:
        return True
    rl = remark.lower()
    return "special price" in rl


def check_price_vs_cost(row: dict) -> list[str]:
    """PRD §8.7.3 — Price vs cost check.
    SP (special price) remark still flags below-cost rows, but with a distinct
    reason so the office team can triage them separately from regular issues."""
    cost = safe_decimal(row.get("current_cost_price"))
    price = safe_decimal(row.get("price"))

    if cost is None:
        return []

    reasons = []
    if price is None:
        return []

    is_sp = _is_sp_remark(row.get("remark"))
    prefix = "SP override — " if is_sp else ""

    if cost == 0 or price == 0:
        reasons.append(f"{prefix}Zero price or cost (cost={cost:f}, selling={price:f})")
    elif price < cost:
        reasons.append(f"{prefix}Selling below cost (cost={cost:f}, selling={price:f})")
    elif price == cost:
        reasons.append(f"{prefix}No margin: selling equals cost ({cost:f})")

    return reasons


def check_row(row: dict, run_date: date) -> list[str]:
    """Run all problem checks for a same-day row. Returns list of problem reasons."""
    status = (row.get("individual_weight_status") or "").upper().strip()

    # MISSING → always problematic
    if status == "MISSING":
        return ["Item status is MISSING"]

    # SUBSTITUTED → skip all checks
    if status == "SUBSTITUTED":
        return []

    # WITH and blank → run all checks
    reasons = []
    reasons.extend(check_remark_status(row))
    reasons.extend(check_lbs_weight(row))
    reasons.extend(check_price_vs_cost(row))
    return reasons


def split_same_day_future(rows: list[dict], run_date: date) -> tuple[list[dict], list[dict]]:
    """Split rows into same-day and future. Spacer rows inherit date from block above."""
    same_day = []
    future = []
    last_date = None

    for row in rows:
        if row.get("_empty") or row.get("is_spacer"):
            # Spacer inherits last known date
            row["transaction_date"] = last_date
            if last_date and last_date > run_date:
                future.append(row)
            else:
                same_day.append(row)
            continue

        txn_date = row.get("transaction_date")
        # openpyxl returns datetime for date-typed cells; normalize to date so
        # comparison with run_date (a plain date) is well-defined.
        if isinstance(txn_date, datetime):
            last_date = txn_date.date()
        elif isinstance(txn_date, date):
            last_date = txn_date
        elif txn_date is not None:
            try:
                if hasattr(txn_date, 'date'):
                    last_date = txn_date.date()
                else:
                    last_date = txn_date
            except Exception:
                last_date = None

        if last_date and last_date > run_date:
            row["is_future"] = True
            future.append(row)
        else:
            same_day.append(row)

    return same_day, future
