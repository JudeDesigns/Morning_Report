"""Claude-based invoice image extraction service (PRD Section 22)."""
import base64
import json
from typing import Optional
import anthropic
from app.config import settings

CONFIDENCE_THRESHOLD = settings.EXTRACTION_CONFIDENCE_THRESHOLD

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

VENDOR_BILL_PROMPT = """You are an invoice data extraction specialist. Extract all line items from this vendor bill/invoice image.

Return ONLY valid JSON in this exact structure:
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

Rules:
- Extract vendor name from letterhead or header
- If individual weights are listed per item (e.g. for catch-weight items), include them in individual_weights
- For credit memos, bill_type = "credit_memo" and amounts should be positive (sign handled separately)
- confidence is the overall line confidence (0.0-1.0)
- field_confidence reports the per-field certainty so reviewers can highlight only the unsure values
- header_confidence reports per-header-field certainty (vendor, invoice_number, invoice_date)
- Include any handwritten driver notes in the notes field
- Return null for fields you cannot read clearly"""


def _encode_image(image_bytes: bytes, mime_type: str) -> tuple[str, str]:
    """Encode image bytes to base64 for Claude API."""
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    return b64, mime_type


async def extract_rd_invoice(image_bytes: bytes, mime_type: str) -> dict:
    """Extract Restaurant Depot invoice using Claude vision."""
    if not settings.ANTHROPIC_API_KEY:
        return _mock_rd_extraction()

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    b64_data, media_type = _encode_image(image_bytes, mime_type)

    message = client.messages.create(
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

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    b64_data, media_type = _encode_image(image_bytes, mime_type)

    message = client.messages.create(
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
