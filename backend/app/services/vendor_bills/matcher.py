"""Match vendor bill lines to PO Bank rows (PRD 10.9).

Multi-strategy matching pipeline:
  1. Exact item code (highest confidence)
  2. Normalised token Jaccard — handles abbreviations, word-order differences, noise
  3. Character SequenceMatcher — catches near-typos / different casing
  4. Number-overlap bonus — matching sizes/weights is strong corroborating evidence
  5. Partial-code fuzzy — bill code ≈ PO code (prefix/suffix match)
"""
import re
from decimal import Decimal
from typing import Optional
import difflib

# ── Vendor rules (PRD §10.9) ──────────────────────────────────────────────────
# Values are the canonical form produced by normalize_vendor() (lowercase, no
# punctuation, no business suffixes) so cross-source comparisons survive minor
# spelling variations like "Inc." vs "Inc" or stray commas.
VENDOR_MATCH_BY_DESC = {"d n produce", "jalisco fresh produce", "maui fresh", "la palma foods"}
VENDOR_ALIASES = {
    "Maui Fresh International": "Maui Fresh",
    "Jalisco Fresh Produce Inc": "Jalisco Fresh Produce Inc.",
}
VENDOR_WEIGHT_BASED = {"glen rose meat"}

# ── Token normalisation tables ────────────────────────────────────────────────

# Words that add zero product-identity information
_NOISE = frozenset({
    "and", "or", "the", "a", "an", "of", "for", "with", "per",
    "fresh", "conventional", "organic", "in", "at", "from", "to",
    "no", "not", "avg", "approx", "grade",
})

# Packaging/container words — irrelevant to product identity
_CONTAINER = frozenset({
    "ctn", "case", "cs", "box", "pallet", "bag", "pk", "pkg",
    "each", "ea", "pc", "pcs", "unit", "ct", "hd", "count",
    "ca",   # QB often uses "CA" as abbreviation for "case"
})

# Weight/unit normalisation (consolidate to single canonical form)
_UNIT_NORM: dict[str, str] = {
    "lbs": "lb", "pound": "lb", "pounds": "lb",
    "kgs": "kg", "kilogram": "kg", "kilograms": "kg",
    "ozs": "oz", "ounce": "oz", "ounces": "oz",
}

# Common produce/meat shorthand → full word
_ABBREV: dict[str, str] = {
    "med": "medium", "lg": "large", "sm": "small", "xl": "xlarge",
    "wh": "white", "rd": "red", "grn": "green", "blk": "black",
    "bch": "bunch", "bn": "bunch",
    "springmix": "spring mix", "sprmix": "spring mix",
    "bf": "beef", "chk": "chicken",
    "wog": "chicken whole",   # whole bird (Glen Rose term)
    "cvp": "cryovac",
    "conv": "conventional",
    "jbo": "jumbo",
    "hal": "halal", "hlal": "halal",
    "rb": "rib", "bk": "back",
    "bn": "bone",
}


def normalize_vendor(name: str) -> str:
    if not name:
        return name
    stripped = name.strip()
    aliased = VENDOR_ALIASES.get(stripped, stripped)
    # Aggressive comparable form: lowercase, drop punctuation and common business suffixes.
    # Used for cross-source vendor matching where commas, periods, "Inc." vs "Inc" diverge.
    canon = aliased.lower()
    canon = re.sub(r"[,\.&'\"/]", " ", canon)
    canon = re.sub(r"\b(inc|llc|ltd|co|corp|company|corporation|incorporated|limited)\b", " ", canon)
    canon = re.sub(r"\s+", " ", canon).strip()
    return canon


def vendors_match(a: str, b: str) -> bool:
    """Loose cross-source vendor equality.

    Bills often carry the full legal name ("Maui Fresh International") while the
    PO Bank uses a shortened trading name ("Maui Fresh"), so strict equality of
    the canonical forms drops legitimate candidates. Treat two names as the
    same vendor when their normalised forms are equal OR one is contained
    inside the other.
    """
    na, nb = normalize_vendor(a or ""), normalize_vendor(b or "")
    if not na or not nb:
        return False
    if na == nb:
        return True
    # Require at least 4 chars of overlap on the shorter side to avoid
    # accidental matches on very short tokens.
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    return len(shorter) >= 4 and shorter in longer


# ── Token extraction ──────────────────────────────────────────────────────────

def _clean_tokens(text: str) -> set[str]:
    """Return a set of normalised product-identity tokens from a description.

    Steps:
     - Drop source annotation after " - "  (e.g. "… - LOS ANGELES PRODUCE")
     - Strip UPC codes inside parentheses
     - Remove leading quantity prefix: "6 CS", "30 CS", "2 UNIT …"
     - Remove "PD" produce-code prefix
     - Expand abbreviations
     - Remove noise / container tokens
    """
    if not text:
        return set()

    # 1. Drop source suffix " - VENDOR SOURCE INFO"
    text = re.split(r"\s+-\s+", text)[0]
    # 2. Strip UPC / product codes in parentheses
    text = re.sub(r"\([^)]*\)", " ", text)
    # 3. Drop "#" (pack-size marker like "3#")
    text = text.replace("#", " ")
    # 4. Lowercase everything
    text = text.lower()
    # 5. Remove leading qty prefix like "6 cs ", "30 cs ", "2 unit "
    text = re.sub(r"^\d+\s+(?:cs|unit|units|pallet|bx|box|ca)\s+", "", text.strip())
    # 6. Remove "pd" produce-code prefix wherever it appears as a standalone token
    text = re.sub(r"\bpd\b", " ", text)
    # 7. Tokenise numbers stuck to letters: "10lbs" → "10 lbs"
    text = re.sub(r"(\d+)([a-z])", r"\1 \2", text)
    text = re.sub(r"([a-z])(\d)", r"\1 \2", text)
    # 8. Remove remaining punctuation
    text = re.sub(r"[^\w\s]", " ", text)

    tokens: set[str] = set()
    for tok in text.split():
        if not tok or tok in _NOISE:
            continue
        # Unit normalisation
        tok = _UNIT_NORM.get(tok, tok)
        if tok in _CONTAINER:
            continue
        # Abbreviation expansion (may produce multi-word result like "spring mix")
        expanded = _ABBREV.get(tok, tok)
        for t in expanded.split():
            if t and t not in _NOISE and t not in _CONTAINER:
                tokens.add(t)
    return tokens


# ── Individual scoring functions ──────────────────────────────────────────────

def _jaccard(a: str, b: str) -> float:
    ta, tb = _clean_tokens(a), _clean_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _seq_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _number_bonus(a: str, b: str) -> float:
    """Extra credit when numeric sizes / weights match (e.g. both say '10' lbs)."""
    nums_a = {n for n in re.findall(r"\b\d+(?:\.\d+)?\b", a) if float(n) >= 3}
    nums_b = {n for n in re.findall(r"\b\d+(?:\.\d+)?\b", b) if float(n) >= 3}
    if not nums_a or not nums_b:
        return 0.0
    return len(nums_a & nums_b) / max(len(nums_a), len(nums_b)) * 0.15


def _code_fuzzy(bill_code: str, po_code: str) -> float:
    """Partial item-code similarity — catches prefix/suffix code variants."""
    if not bill_code or not po_code:
        return 0.0
    b, p = bill_code.upper().strip(), po_code.upper().strip()
    if b == p:
        return 1.0
    # One is a prefix of the other (e.g. "42835" inside "PD-42835U")
    if b in p or p in b:
        return 0.90
    return difflib.SequenceMatcher(None, b, p).ratio()


def description_similarity(a: str, b: str) -> float:
    """Public helper — combined similarity score used by the matcher."""
    jaccard = _jaccard(a, b)
    seq = _seq_ratio(a, b)
    num = _number_bonus(a, b)
    # Best of individual strategies, then add number bonus
    base = max(jaccard, seq, (jaccard + seq) / 2)
    return min(1.0, base + num)


# ── Main matching entry point ─────────────────────────────────────────────────

def match_bill_line_to_po(
    bill_line: dict,
    po_rows: list[dict],
    vendor_name: str,
) -> tuple[Optional[dict], float, str]:
    """Match one bill line to the best available PO row.

    Returns (matched_po_row | None, confidence 0–1, human-readable reason).
    """
    vendor_norm = normalize_vendor(vendor_name)
    bill_code = (bill_line.get("bill_item_code") or "").strip()
    bill_desc = (bill_line.get("description") or "").strip()

    # Restrict to same vendor, unprocessed rows only — use loose match so
    # "Maui Fresh" (PO Bank) ≡ "Maui Fresh International" (bill).
    vendor_pos = [
        r for r in po_rows
        if vendors_match(r.get("vendor") or "", vendor_name)
        and r.get("status") == "unprocessed"
    ]

    if not vendor_pos:
        return (None, 0.0, "No unprocessed PO rows for this vendor")

    # Use loose containment so e.g. "maui fresh international" still triggers
    # the description-only path defined for the canonical "maui fresh".
    desc_only_vendor = any(vendors_match(vendor_name, v) for v in VENDOR_MATCH_BY_DESC)

    # ── Strategy 1: Exact item code ───────────────────────────────────────────
    if bill_code and not desc_only_vendor:
        for po in vendor_pos:
            if (po.get("item_code") or "").strip().upper() == bill_code.upper():
                return (po, 0.99, f"Exact item code: {bill_code}")

    # ── Strategy 2: Fuzzy item code (prefix/contained) ───────────────────────
    if bill_code and not desc_only_vendor:
        best_code_po, best_code_score = None, 0.0
        for po in vendor_pos:
            score = _code_fuzzy(bill_code, po.get("item_code") or "")
            if score > best_code_score:
                best_code_score, best_code_po = score, po
        if best_code_score >= 0.85:
            return (best_code_po, best_code_score,
                    f"Fuzzy item code match: {best_code_score:.0%}")

    # ── Strategy 3: Multi-strategy description matching ───────────────────────
    scored: list[tuple[float, str, dict]] = []
    for po in vendor_pos:
        po_desc = po.get("description") or ""
        jaccard  = _jaccard(bill_desc, po_desc)
        seq      = _seq_ratio(bill_desc, po_desc)
        num      = _number_bonus(bill_desc, po_desc)
        # Also try matching bill desc against PO item_code embedded in desc
        base     = max(jaccard, seq, (jaccard + seq) / 2)
        total    = min(1.0, base + num)
        reason   = (
            f"Token match {jaccard:.0%} · Sequence {seq:.0%}"
            + (f" · Size match +{num:.0%}" if num > 0 else "")
        )
        scored.append((total, reason, po))

    if not scored:
        return (None, 0.0, "No description candidates found")

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_reason, best_po = scored[0]

    # Confident match
    if best_score >= 0.55:
        return (best_po, best_score, f"Description matched — {best_reason}")
    # Weak / partial match — still return but flag for review
    if best_score >= 0.35:
        return (best_po, best_score,
                f"Partial match ({best_score:.0%}) — review recommended · {best_reason}")

    return (None, best_score, f"No confident match (best {best_score:.0%}) · {best_reason}")


def compute_discrepancies(
    bill_line: dict,
    po_row: dict,
    vendor_name: str,
) -> dict:
    """Compare bill line vs PO row. Returns discrepancy info for Summary Vendor sheet."""
    bill_rate = Decimal(str(bill_line.get("rate") or 0))
    po_cost = Decimal(str(po_row.get("po_cost") or 0))
    bill_qty = Decimal(str(bill_line.get("qty") or 0))
    po_qty = Decimal(str(po_row.get("quantity") or 0))

    rate_diff = bill_rate - po_cost
    qty_diff = bill_qty - po_qty
    total_impact = rate_diff * bill_qty if bill_qty else Decimal(0)

    # Summary block section (rate-first) per PRD §10.11
    section = None
    if abs(rate_diff) > Decimal("0.005"):
        section = "overcharged" if rate_diff > 0 else "undercharged"
    elif abs(qty_diff) > Decimal("0.001"):
        section = "qty_issue"

    # All Issues qty flag (v3 §10.4) — a line may also belong to All Issues
    # for a qty reason even if it already carries a rate move.
    has_qty_mismatch = abs(qty_diff) > Decimal("0.001")

    return {
        "section": section,
        "has_qty_mismatch": has_qty_mismatch,
        "item_code": po_row.get("item_code"),
        "item_description": po_row.get("description"),
        "po_rate": float(po_cost),
        "invoice_rate": float(bill_rate),
        "qty": float(bill_qty),
        "po_qty": float(po_qty),
        "bill_qty": float(bill_qty),
        "qty_diff": float(qty_diff),
        "po_ref_number": po_row.get("ref_number"),
        "difference_per_unit": float(rate_diff),
        "total_impact": float(total_impact),
        "action_needed": _action_text(section, rate_diff, qty_diff),
    }


def _action_text(section: Optional[str], rate_diff: Decimal, qty_diff: Decimal) -> str:
    if section == "overcharged":
        return f"Please issue credit of ${abs(rate_diff):.4f}/unit"
    if section == "undercharged":
        return f"Please confirm if lower price ${abs(rate_diff):.4f}/unit is correct"
    if section == "qty_issue":
        return f"Quantity difference of {qty_diff:+.2f} units"
    return ""
