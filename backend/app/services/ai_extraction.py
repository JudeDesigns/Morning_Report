"""Claude-based invoice image extraction service (PRD Section 22)."""
import asyncio
import base64
import json
from typing import Optional
import anthropic
from app.config import settings

CONFIDENCE_THRESHOLD = settings.EXTRACTION_CONFIDENCE_THRESHOLD


def _anthropic_client() -> anthropic.Anthropic:
    """Construct a Claude client with bounded timeout/retries.

    Centralised so every call site picks up the same safety limits — a single
    upstream stall cannot tie up a worker thread for the SDK's 10-minute default.
    """
    return anthropic.Anthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
        max_retries=settings.AI_MAX_RETRIES,
    )

RD_INVOICE_PROMPT = """You are an invoice data extraction specialist. Extract all line items from this Restaurant Depot invoice image.

Return ONLY valid JSON in this exact structure:
{
  "invoice_number": "string or null",
  "invoice_date": "YYYY-MM-DD or null",
  "grand_total": number or null,
  "lines": [
    {
      "line": "string",
      "upc": "string or null",
      "item": "string (item code)",
      "description": "string",
      "price": number,
      "cu": "C or U",
      "qty": number,
      "total": number,
      "confidence": 0.0-1.0
    }
  ]
}

Rules:
- invoice_number must come from the row labeled "Invoice", NOT "Convert From Quote"
- Include CRV/Surcharge rows as separate lines with item="Surcharge"
- Include coupon rows with upc="Coupon" and negative price
- Include void rows with qty marked as negative
- confidence reflects extraction certainty per line (0.0 = uncertain, 1.0 = certain)
- Return null for fields you cannot read clearly"""

VENDOR_BILL_PROMPT = """You are an invoice data extraction specialist for a food-service distributor. Your job is to extract ONLY genuine product line items from this vendor bill/invoice image — nothing else.

STEP 1 — UNDERSTAND THE BILL FIRST (do this before extracting):
- Identify the vendor (letterhead/header), the invoice number, and the invoice date.
- Locate the line-items table: find its column headers (e.g. "Item", "Description", "Qty", "Price/Rate", "Amount/Total") and where the table starts and ends.
- COUNT the number of distinct PRODUCT rows in the table. Write that count down mentally before extracting — your final "lines" array must have exactly that many entries (no more, no less).
- A genuine product line has: a product description, a quantity, a unit price/rate, and a line total. Most also have an item code/SKU/UPC.

STEP 2 — EXCLUDE these rows entirely (do NOT put them in "lines"):
- Subtotals, Totals, Grand Total, Invoice Total, Balance Due, Amount Due, Previous Balance
- Tax, Sales Tax, VAT, GST
- Freight, Shipping, Delivery Fee, Fuel Surcharge, Handling Fee, Service Fee
- Bottle Deposit, CRV, Recycling Fee  (UNLESS the bill clearly treats them as a separately-billed product line tied to a product — when in doubt, exclude)
- Discount lines that are not tied to a specific product
- Payment, Payment Received, Credit Applied
- Column header rows, section labels (e.g. "DAIRY", "PRODUCE"), page totals, "continued on next page"
- Blank/decorative rows, instructions, terms text, signature lines, driver notes (capture driver notes in the line's "notes" field if they belong to a specific line)
- Anything without a clear quantity AND a clear unit price — if both are missing, it is not a product line
- Country-of-origin annotations like "Product of USA", "Product of Mexico", "Grown in California", "Origin: ..." — these are METADATA attached to the product above, never a product on their own. Merge them into the previous line's description (e.g. "BELL PEPPER GREEN - Product of USA") and do NOT emit them as a separate line.

STEP 3 — INCLUDE every genuine product line, even if:
- It is a credit/void line (keep amounts positive; sign is handled downstream — set bill_type="credit_memo" if the whole document is a credit memo)
- It is a catch-weight item with individual weights listed (put them in individual_weights)
- The item code is missing (set bill_item_code=null but still include the line)

STEP 3b — MULTI-LINE PRODUCT ROWS (READ THE WORKED EXAMPLE BELOW — THIS IS THE #1 SOURCE OF EXTRACTION BUGS):

Many produce/food invoices print ONE product row across TWO visual lines:
    Visual line A: ONLY the product name (e.g. "BELL PEPPER GREEN") — no numbers
    Visual line B: the country-of-origin tag (e.g. "Product of USA") AND the row's CH / QTY / PRICE / AMOUNT values

The numbers always belong to the product name on the line DIRECTLY ABOVE the continuation line. They do NOT belong to the product name appearing further down.

WORKED EXAMPLE — this is the exact layout you must handle correctly:

    DESCRIPTION              CH       QTY       PRICE       AMOUNT
    BELL PEPPER GREEN
      Product of USA                    2       18.00        36.00
    HONEYDEW
      Product of MEXICO      55        11       10.50       115.50
    BELL PEPPER GREEN
      Product of MEXICO      XLGE       4       20.00        80.00

CORRECT extraction (exactly 3 entries — one per AMOUNT):
  1. {bill_item_code: null,   description: "BELL PEPPER GREEN Product of USA",     qty:  2, rate: 18.00, total:  36.00}
  2. {bill_item_code: "55",   description: "HONEYDEW Product of MEXICO",           qty: 11, rate: 10.50, total: 115.50}
  3. {bill_item_code: "XLGE", description: "BELL PEPPER GREEN Product of MEXICO",  qty:  4, rate: 20.00, total:  80.00}

INCORRECT extractions you MUST NOT produce:
  X Reusing (qty=2, rate=18, total=36) on the HONEYDEW line — that is the BELL PEPPER row's numbers, not HONEYDEW's.
  X Pairing HONEYDEW with (11, 10.50, 115.50) but then pairing the third BELL PEPPER row with the SAME (11, 10.50, 115.50). Each AMOUNT belongs to exactly ONE entry.
  X Emitting a fourth standalone entry whose description is just "Product of MEXICO".
  X Skipping the third row entirely so the (4, 20, 80) numbers vanish.

HOW TO EXTRACT CORRECTLY:
1. First, count the distinct AMOUNTS printed in the AMOUNT column (3 in the example above). Your final "lines" array will have exactly this many entries.
2. For each AMOUNT, the CH (item code), QTY, and PRICE on the SAME horizontal line as that AMOUNT belong to the SAME entry. The bill_item_code comes from the CH column on the numbers line — it is NOT carried over from anywhere else.
3. For each AMOUNT, the product name is the LAST product-name text printed ABOVE the continuation line. Concatenate the product name with the origin/pack text on the numbers line into one description string.
4. NO two entries may share the same (qty, rate, total) triple. If you find yourself writing the same three numbers twice, you have misaligned — go back, re-read the AMOUNT column row by row, and fix it.

STEP 3c — CATCH-WEIGHT / WEIGHT-PRICED LINES (poultry, meat, seafood, cheese — many wholesale food bills):

Some bills price by POUND, not by case. The columns typically look like:
    PRODUCT CODE | DESCRIPTION | ORDERED | SHIPPED | (WEIGHT or LBS or SHIPPED-LBS) | RATE | AMOUNT

For these lines the arithmetic is **weight × rate = amount**, NOT qty × rate = amount.

Example (verbatim layout from a real chicken bill):

    PRODUCT CODE     DESCRIPTION                          ORDERED   SHIPPED   LBS       RATE    AMOUNT
    0031110087-01    Chicken Wog 20HD 3.5 up (CVP)             18       10    761.00    1.35    1,027.35
                     Golden Rod
                     77.00, 76.00, 76.00, 78.00, 75.00,
                     73.00, 77.00, 78.00, 75.00, 76.00
    0031125087-01    Chicken Wog 28hd 2.50 (CVP) 8 Cut          5        5    380.00    1.64      623.20
                     Golden Rod
                     77.00, 76.00, 75.00, 75.00, 77.00
    0031190087-01    Chicken Wog 28HD 2.50up (CVP) Split        6      OUT      0.00    1.69        0.00
                     Golden Rod   HALAL

CORRECT extraction for those three rows:
  1. {bill_item_code: "0031110087-01", description: "Chicken Wog 20HD 3.5 up (CVP) Golden Rod",
      qty: 10, rate: 1.35, total: 1027.35,
      individual_weights: [77.00, 76.00, 76.00, 78.00, 75.00, 73.00, 77.00, 78.00, 75.00, 76.00]}
  2. {bill_item_code: "0031125087-01", description: "Chicken Wog 28hd 2.50 (CVP) 8 Cut Golden Rod",
      qty:  5, rate: 1.64, total:  623.20,
      individual_weights: [77.00, 76.00, 75.00, 75.00, 77.00]}
  3. {bill_item_code: "0031190087-01", description: "Chicken Wog 28HD 2.50up (CVP) Split Golden Rod HALAL",
      qty:  0, rate: 1.69, total:    0.00, individual_weights: null, notes: "OUT — not shipped"}

KEY RULES for catch-weight lines:
- qty is the SHIPPED CASE COUNT (10, 5, 0 in the example) — not the ordered count, not the total pounds.
- rate is the per-pound price ($1.35, $1.64, $1.69).
- total is the line amount as printed on the bill.
- individual_weights captures the per-piece weights listed under the description, IF they are printed (e.g. "77.00, 76.00, 76.00, ..."). If no per-piece list is printed BUT a single total-weight number is printed in the LBS/WEIGHT column (e.g. "80.00" alongside qty 2 and rate 0.72), put that single number into individual_weights as a one-element list (e.g. [80.00]) so downstream math validates. Only leave individual_weights null when there is no weight column at all (standard case-priced bills).
- Brand names like "Golden Rod", grade tags like "HALAL", and pack notations belong in the description string — they are NOT origin tags and must NOT be dropped.
- Ignore handwritten ink (dates, checkmarks, initials) overlaying cells unless that is the only source for a printed-but-unreadable value.
- A "SHIPPED" cell reading "OUT", "0", or blank means qty=0 and total=0. Keep the line so the office sees it; put "OUT — not shipped" in notes.
- For catch-weight lines, qty × rate will NOT equal total. Do NOT drop the line for that reason. The line is valid when (weight × rate ≈ total) where weight is the printed LBS total or sum(individual_weights).

STEP 4 — RETURN ONLY VALID JSON in this exact structure (no prose, no markdown fences):
{
  "vendor": "string",
  "invoice_number": "string or null",
  "invoice_date": "YYYY-MM-DD or null",
  "bill_type": "invoice or credit_memo",
  "header_confidence": {
    "vendor": 0.0-1.0,
    "invoice_number": 0.0-1.0,
    "invoice_date": 0.0-1.0
  },
  "lines": [
    {
      "bill_item_code": "string or null",
      "description": "string",
      "qty": number,
      "rate": number,
      "total": number,
      "individual_weights": [list of numbers] or null,
      "notes": "string or null",
      "confidence": 0.0-1.0,
      "field_confidence": {
        "bill_item_code": 0.0-1.0,
        "description": 0.0-1.0,
        "qty": 0.0-1.0,
        "rate": 0.0-1.0,
        "total": 0.0-1.0
      }
    }
  ]
}

FIELD RULES:
- confidence is the overall line confidence (0.0-1.0); field_confidence reports per-field certainty so reviewers can highlight only the unsure values
- header_confidence reports per-header-field certainty (vendor, invoice_number, invoice_date)
- Return null for any field you cannot read clearly — never guess

FINAL SANITY CHECKS before returning — do all of these:
1. Every entry in "lines" must have description AND rate. qty is also required UNLESS the line is a zero-shipped/OUT line (qty=0, total=0).
2. For each line, the arithmetic must be consistent with ONE of the following — pick whichever applies to that line:
   (a) Case/each-priced lines:  qty × rate ≈ total  (within $0.05 or 1%).
   (b) Catch-weight lines (poultry/meat/seafood/cheese, see STEP 3c):
       sum(individual_weights) × rate ≈ total  (within $0.05 or 1%),
       or the printed LBS/WEIGHT column × rate ≈ total.
   (c) OUT / not-shipped lines:  qty=0 and total=0.
   If NONE of (a)(b)(c) hold, you likely pulled the description from the wrong row — re-check and fix or drop.
3. The "description" of each line must be a real product name (e.g. "BELL PEPPER GREEN", "HONEYDEW MELON", "CHICKEN WOG 20HD"). Drop any line whose description is just a country, an origin tag ("Product of …", "Grown in …"), or a packaging word with no product noun. Brand names ("Golden Rod") and grade tags ("HALAL", "CHOICE") attached to a real product noun are valid — keep them.
4. Compare your line count to the printed AMOUNT count from STEP 3b. They MUST match. If you have too many, the most likely cause is a wrap line emitted as its own row — find it and merge it back. OUT / zero-amount rows still count as one line each.
5. NO TWO ENTRIES may share the same (qty, rate, total) triple — UNLESS both are catch-weight lines with distinct individual_weights (very rare). If two share, the lower one is almost certainly wrong — re-read the AMOUNT column carefully, find the correct numbers for the second entry, and fix it.
6. Every printed AMOUNT in the table must appear as the `total` of exactly one entry. If an AMOUNT is missing from your output, find which entry should carry it and add it back."""


def _encode_image(image_bytes: bytes, mime_type: str) -> tuple[str, str]:
    """Encode image bytes to base64 for Claude API."""
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    return b64, mime_type


async def extract_rd_invoice(image_bytes: bytes, mime_type: str) -> dict:
    """Extract Restaurant Depot invoice using Claude vision."""
    if not settings.ANTHROPIC_API_KEY:
        return _mock_rd_extraction()

    client = _anthropic_client()
    b64_data, media_type = _encode_image(image_bytes, mime_type)

    # Run the blocking SDK call in a worker thread so the FastAPI event loop
    # stays responsive to other requests (e.g. page refreshes mid-extraction).
    message = await asyncio.to_thread(
        client.messages.create,
        model="claude-opus-4-5",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": RD_INVOICE_PROMPT,
                    },
                ],
            }
        ],
    )

    text = message.content[0].text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": "Failed to parse extraction response", "raw": text}


async def extract_vendor_bill(image_bytes: bytes, mime_type: str) -> dict:
    """Extract vendor bill using Claude vision."""
    if not settings.ANTHROPIC_API_KEY:
        return _mock_vendor_extraction()

    client = _anthropic_client()
    b64_data, media_type = _encode_image(image_bytes, mime_type)

    message = await asyncio.to_thread(
        client.messages.create,
        model="claude-opus-4-5",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": VENDOR_BILL_PROMPT,
                    },
                ],
            }
        ],
    )

    text = message.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": "Failed to parse extraction response", "raw": text}


PO_MATCH_PROMPT = """You are a QuickBooks purchasing assistant. Your job is to match vendor bill lines to the correct PO (Purchase Order) rows from the PO Bank.

You will be given:
1. A list of bill lines extracted from a vendor invoice
2. A list of available PO rows from the PO Bank for the same vendor

Match each bill line to the best PO row based on:
- Item code (strongest signal — exact or near-exact match)
- Description similarity (product name, size, weight, packaging)
- If no reasonable match exists, set po_id to null

Return ONLY valid JSON in this exact structure:
{
  "matches": [
    {
      "line_id": "exact line id string from the bill lines",
      "po_id": "exact po id string from the PO rows, or null if no match",
      "confidence": 0.0-1.0,
      "reason": "brief explanation"
    }
  ]
}

Rules:
- Every bill line must have an entry in matches
- Use the exact id values provided — do not generate or modify ids
- If a bill line clearly matches a PO row, set confidence >= 0.8
- If it is a partial/uncertain match, set confidence 0.4-0.79
- If there is genuinely no match, set po_id to null and confidence < 0.4
- Do not match the same PO row to more than one bill line"""


async def ai_match_bill_lines(bill_lines: list[dict], po_rows: list[dict]) -> dict:
    """Use Claude to match extracted bill lines to PO Bank rows.

    Returns {"success": True, "matches": [{line_id, po_id, confidence, reason}, ...]}
    or      {"success": False, "error": "..."}
    """
    if not settings.ANTHROPIC_API_KEY:
        return {"success": False, "error": "No API key configured"}

    if not bill_lines or not po_rows:
        return {"success": False, "error": "No bill lines or PO rows to match"}

    # Build a compact text representation — only the fields Claude needs
    lines_text = "\n".join(
        f"  - line_id={bl['id']} | code={bl.get('bill_item_code') or 'n/a'} | desc={bl.get('description') or 'n/a'}"
        for bl in bill_lines
    )
    po_text = "\n".join(
        f"  - po_id={po['id']} | code={po.get('item_code') or 'n/a'} | desc={po.get('description') or 'n/a'} | vendor={po.get('vendor') or 'n/a'}"
        for po in po_rows
        if po.get("status") == "unprocessed"
    )

    if not po_text:
        return {"success": False, "error": "No unprocessed PO rows available"}

    user_message = (
        f"BILL LINES TO MATCH:\n{lines_text}\n\n"
        f"AVAILABLE PO ROWS:\n{po_text}\n\n"
        "Match each bill line to the best PO row. Return only JSON."
    )

    try:
        client = _anthropic_client()
        message = await asyncio.to_thread(
            client.messages.create,
            model="claude-opus-4-5",
            max_tokens=2048,
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": PO_MATCH_PROMPT},
                    {"type": "text", "text": user_message},
                ]},
            ],
        )

        text = message.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        result = json.loads(text)
        return {"success": True, "matches": result.get("matches", [])}

    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Claude returned invalid JSON: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def flag_low_confidence(extracted: dict, threshold: float = CONFIDENCE_THRESHOLD) -> dict:
    """PRD §22 / §13.4 — mark lines, individual fields, and header fields with
    confidence below threshold so the review UI can highlight only the unsure
    values."""
    # Header-level
    hc = extracted.get("header_confidence") or {}
    header_needs_review: list[str] = []
    for field in ("vendor", "invoice_number", "invoice_date"):
        conf = hc.get(field)
        if conf is not None and conf < threshold:
            header_needs_review.append(field)
    extracted["header_needs_review"] = header_needs_review

    # Line-level
    lines = extracted.get("lines", [])
    for line in lines:
        conf = line.get("confidence", 1.0)
        line["needs_review"] = conf < threshold
        fc = line.get("field_confidence") or {}
        field_needs_review: list[str] = []
        for field, fconf in fc.items():
            if fconf is None:
                continue
            if fconf < threshold:
                field_needs_review.append(field)
        # Auto-flag fields that are obviously missing but expected
        for required in ("description", "qty", "rate", "total"):
            if line.get(required) in (None, "") and required not in field_needs_review:
                field_needs_review.append(required)
        line["field_needs_review"] = field_needs_review
        if field_needs_review:
            line["needs_review"] = True

    extracted["has_low_confidence"] = (
        bool(header_needs_review)
        or any(l.get("needs_review") for l in lines)
    )
    return extracted


def _mock_rd_extraction() -> dict:
    """Return mock data when no API key is set (dev mode)."""
    return {
        "invoice_number": "MOCK-001",
        "invoice_date": "2026-06-11",
        "grand_total": 500.00,
        "lines": [
            {"line": "1", "upc": "012345678901", "item": "24514",
             "description": "SAMPLE PRODUCT A", "price": 10.50,
             "cu": "C", "qty": 5, "total": 52.50, "confidence": 0.95},
        ],
        "_mock": True,
    }


def _mock_vendor_extraction() -> dict:
    """Return mock data when no API key is set (dev mode)."""
    return {
        "vendor": "Sample Vendor Inc.",
        "invoice_number": "INV-MOCK-001",
        "invoice_date": "2026-06-11",
        "bill_type": "invoice",
        "lines": [
            {"bill_item_code": "SV-001", "description": "Sample Product",
             "qty": 10, "rate": 12.34, "total": 123.40,
             "individual_weights": None, "notes": None, "confidence": 0.95},
        ],
        "_mock": True,
    }
